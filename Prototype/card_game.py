"""
card_game.py
============
DesignVoyager — Card Game

A simple two-player card game that implements GameInterface.
This demonstrates that the pipeline can evaluate non-board games too.
"""

import copy
import random

from game_interface import GameInterface, GameAgent


PLAYER_1 = 1
PLAYER_2 = 2
HAND_SIZE = 5
MAX_CARD = 10
TARGET_SCORE = 21


class CardGame(GameInterface):
    def __init__(self, state: dict = None, ai_players: dict = None, mechanics: list = None):
        self.state = state or _fresh_state()
        self.ai_players = ai_players or {}
        self.mechanics = mechanics or []

    def get_skeleton_description(self) -> str:
        return (
            f"Two-player card game. Each player starts with {HAND_SIZE} cards "
            f"drawn from values 1 to {MAX_CARD}. Players alternate playing one "
            f"card from their hand, and the card's value is added to their score. "
            f"First player to reach {TARGET_SCORE} or more wins. "
            f"If both hands are exhausted without a winner it is a draw. "
            f"Mechanics can modify scores or hands after each play."
        )

    def get_state_description(self) -> str:
        return (
            "The game uses a state dictionary with these keys:\n"
            "  - 'hands'          : dict {1: [list of int card values], 2: [list of int card values]}\n"
            "  - 'scores'         : dict {1: int, 2: int}\n"
            "  - 'current_player' : integer (1 or 2)\n"
            "  - 'turn'           : integer turn count\n"
            "  - 'last_played'    : int value of the last card played, or None\n"
            "  - 'extra_turn'     : boolean, default False. Set to True to keep the same player next turn.\n"
            "  - 'custom_state'   : dict, default {}. Use this to persist mechanic-specific state.\n"
            f"Win condition: first player to reach {TARGET_SCORE} points wins."
        )

    def get_state(self) -> dict:
        return copy.deepcopy(self.state)

    def get_dummy_state(self) -> dict:
        return {
            "hands": {1: [3, 7], 2: [5, 9]},
            "scores": {1: 10, 2: 8},
            "current_player": PLAYER_1,
            "turn": 4,
            "last_played": 7,
            "extra_turn": False,
            "custom_state": {},
        }

    def possible_moves(self, state: dict) -> list:
        hand = state["hands"][state["current_player"]]
        if not hand:
            return [-1]
        return list(range(len(hand)))

    def is_valid_move(self, move) -> bool:
        hand = self.state["hands"][self.state["current_player"]]
        if not hand:
            return move == -1
        try:
            idx = int(move)
        except (TypeError, ValueError):
            return False
        return 0 <= idx < len(hand)

    def perform_move(self, move) -> None:
        player = self.state["current_player"]
        hand = self.state["hands"][player]

        if move == -1 or not hand:
            self.state["last_played"] = None
        else:
            card = hand.pop(int(move))
            self.state["scores"][player] += card
            self.state["last_played"] = card

        self._state_before_mechanics = copy.deepcopy(self.state)
        for mechanic_fn in self.mechanics:
            try:
                result = mechanic_fn(self.state)
                if isinstance(result, dict):
                    self.state.update(result)
            except Exception:
                pass

    def simulate_move(self, state: dict, move):
        temp = CardGame(
            state=copy.deepcopy(state),
            ai_players={PLAYER_1: CardRandomAgent(), PLAYER_2: CardRandomAgent()},
            mechanics=[getattr(fn, "_inner_mechanic", fn) for fn in self.mechanics],
        )
        temp.perform_move(move)
        ended = temp.game_finished()
        winner = temp.get_winner() if ended else None
        if not ended:
            temp.advance_turn()
        return temp.get_state(), ended, winner

    def game_finished(self) -> bool:
        if self.get_winner() is not None:
            return True
        return len(self.state["hands"][PLAYER_1]) == 0 and len(self.state["hands"][PLAYER_2]) == 0

    def get_winner(self):
        s1 = self.state["scores"][PLAYER_1]
        s2 = self.state["scores"][PLAYER_2]
        p1_done = s1 >= TARGET_SCORE
        p2_done = s2 >= TARGET_SCORE

        if p1_done and p2_done:
            if s1 > s2:
                return PLAYER_1
            if s2 > s1:
                return PLAYER_2
            return None
        if p1_done:
            return PLAYER_1
        if p2_done:
            return PLAYER_2
        return None

    def get_current_agent(self) -> GameAgent:
        return self.ai_players[self.state["current_player"]]

    def advance_turn(self) -> None:
        if self.state.get("extra_turn", False):
            self.state["extra_turn"] = False
        else:
            self.state["current_player"] = PLAYER_2 if self.state["current_player"] == PLAYER_1 else PLAYER_1
        self.state["turn"] += 1

    def get_coverage_stats(self, state: dict) -> tuple:
        covered_cells = HAND_SIZE * 2 - sum(len(hand) for hand in state["hands"].values())
        board_cell_count = HAND_SIZE * 2
        return covered_cells, board_cell_count

    @classmethod
    def make_random_agent(cls) -> 'CardRandomAgent':
        return CardRandomAgent()

    @classmethod
    def make_greedy_agent(cls) -> 'CardGreedyAgent':
        return CardGreedyAgent()

    @classmethod
    def create(cls, mechanic_fn=None, agent1=None, agent2=None) -> 'CardGame':
        agent1 = agent1 or cls.make_random_agent()
        agent2 = agent2 or cls.make_random_agent()
        mechanics = [mechanic_fn] if mechanic_fn else []
        return cls(state=_fresh_state(), ai_players={PLAYER_1: agent1, PLAYER_2: agent2}, mechanics=mechanics)


def _fresh_state() -> dict:
    return {
        "hands": {
            PLAYER_1: [random.randint(1, MAX_CARD) for _ in range(HAND_SIZE)],
            PLAYER_2: [random.randint(1, MAX_CARD) for _ in range(HAND_SIZE)],
        },
        "scores": {PLAYER_1: 0, PLAYER_2: 0},
        "current_player": PLAYER_1,
        "turn": 0,
        "last_played": None,
        "extra_turn": False,
        "custom_state": {},
    }


class CardRandomAgent(GameAgent):
    def choose_move(self, game: CardGame, state: dict, moves: list):
        return random.choice(moves)


class CardGreedyAgent(GameAgent):
    def choose_move(self, game: CardGame, state: dict, moves: list):
        if moves == [-1]:
            return -1
        player = state["current_player"]
        hand = state["hands"][player]
        return max(moves, key=lambda idx: hand[idx])


def get_skeleton_description() -> str:
    return CardGame().get_skeleton_description()
