"""
mcts_agent.py
=============
Basic Monte Carlo Tree Search agent for DesignVoyager playtesting.

This implementation is intentionally lightweight:
  - Works with the existing Boardwalk-style state API
  - Uses random rollouts
  - Scores outcomes from the root player's perspective
"""

import copy
import math
import random

from base_game import AIPlayer, PLAYER_1, PLAYER_2


def _next_player(player: int) -> int:
    return PLAYER_2 if player == PLAYER_1 else PLAYER_1


def _advance_state(game, state: dict, move: str):
    """
    Apply a move to a copied game state and advance turn bookkeeping.

    Game.next_state() simulates the move itself, but the returned state still
    reflects the acting player and current turn. We normalize that here so MCTS
    can keep traversing future turns.
    """
    next_state, ended, acting_player_won = game.next_state(state, move)

    if ended:
        winner = state["current_player"] if acting_player_won else None
        return next_state, True, winner

    advanced_state = copy.deepcopy(next_state)
    advanced_state["current_player"] = _next_player(state["current_player"])
    advanced_state["turn"] = state["turn"] + 1
    return advanced_state, False, None


class _Node:
    def __init__(self, state: dict, parent=None, move: str = None):
        self.state = state
        self.parent = parent
        self.move = move
        self.children = []
        self.visits = 0
        self.value = 0.0
        self.untried_moves = None

    def fully_expanded(self) -> bool:
        return self.untried_moves is not None and len(self.untried_moves) == 0


class MCTSAgent(AIPlayer):
    """
    Simple MCTS agent with random rollouts.

    Args:
        simulations   : number of tree iterations per move
        exploration   : UCB exploration constant
        rollout_depth : cap on rollout length
    """

    def __init__(self, simulations: int = 40, exploration: float = 1.4, rollout_depth: int = 16):
        self.simulations = simulations
        self.exploration = exploration
        self.rollout_depth = rollout_depth

    def get_action(self, game, state: dict) -> str:
        moves = game.possible_moves(state)
        if not moves:
            return ""
        if len(moves) == 1:
            return moves[0]

        root = _Node(copy.deepcopy(state))
        root.untried_moves = list(moves)
        root_player = state["current_player"]

        for _ in range(self.simulations):
            node = root

            while node.fully_expanded() and node.children:
                node = self._select_child(node)

            if node.untried_moves is None:
                node.untried_moves = list(game.possible_moves(node.state))

            if node.untried_moves:
                move = random.choice(node.untried_moves)
                node.untried_moves.remove(move)
                child_state, ended, winner = _advance_state(game, node.state, move)
                child = _Node(child_state, parent=node, move=move)
                child.untried_moves = [] if ended else None
                child.terminal_winner = winner
                child.terminal = ended
                node.children.append(child)
                node = child

            reward = self._rollout(game, node.state, root_player)
            self._backpropagate(node, reward)

        best_child = max(root.children, key=lambda child: child.visits)
        return best_child.move

    def _select_child(self, node: _Node) -> _Node:
        log_parent_visits = math.log(max(node.visits, 1))

        def ucb(child: _Node) -> float:
            if child.visits == 0:
                return float("inf")
            exploit = child.value / child.visits
            explore = self.exploration * math.sqrt(log_parent_visits / child.visits)
            return exploit + explore

        return max(node.children, key=ucb)

    def _rollout(self, game, state: dict, root_player: int) -> float:
        rollout_state = copy.deepcopy(state)

        for _ in range(self.rollout_depth):
            moves = game.possible_moves(rollout_state)
            if not moves:
                return 0.5

            move = random.choice(moves)
            rollout_state, ended, winner = _advance_state(game, rollout_state, move)
            if ended:
                if winner is None:
                    return 0.5
                return 1.0 if winner == root_player else 0.0

        return 0.5

    def _backpropagate(self, node: _Node, reward: float):
        current = node
        while current is not None:
            current.visits += 1
            current.value += reward
            current = current.parent
