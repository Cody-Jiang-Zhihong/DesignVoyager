"""
game_interface.py
=================
DesignVoyager — Game Interface Contract

Any game plugged into DesignVoyager must implement GameInterface.
The playtester, main loop, and compile checker call only these
methods, so they do not need to know whether the active game is
board-based, card-based, or something else.
"""

from abc import ABC, abstractmethod


class GameAgent(ABC):
    """Abstract agent compatible with any GameInterface."""

    @abstractmethod
    def choose_move(self, game: 'GameInterface', state: dict, moves: list):
        """Return one move chosen from the provided list of valid moves."""
        ...


class GameInterface(ABC):
    """Abstract contract that any DesignVoyager game must implement."""

    @abstractmethod
    def get_skeleton_description(self) -> str:
        """Plain-English game description for proposal prompts."""
        ...

    @abstractmethod
    def get_state_description(self) -> str:
        """Description of the state dict keys available to mechanic code."""
        ...

    @abstractmethod
    def get_state(self) -> dict:
        """Return the current game state as a plain dict."""
        ...

    @abstractmethod
    def get_dummy_state(self) -> dict:
        """Return a realistic dummy state for compile checking."""
        ...

    @abstractmethod
    def possible_moves(self, state: dict) -> list:
        """Return all valid moves for the current player."""
        ...

    @abstractmethod
    def is_valid_move(self, move) -> bool:
        """Return True if the move is currently legal."""
        ...

    @abstractmethod
    def perform_move(self, move) -> None:
        """Apply the move and any active mechanics."""
        ...

    @abstractmethod
    def simulate_move(self, state: dict, move):
        """
        Simulate one move from the provided state and return:
        (next_state, ended, winner)
        where next_state already reflects turn advancement when the game continues.
        """
        ...

    @abstractmethod
    def game_finished(self) -> bool:
        """Return True if the game has ended."""
        ...

    @abstractmethod
    def get_winner(self):
        """Return the winning player ID, or None for draw/unfinished."""
        ...

    @abstractmethod
    def get_current_agent(self) -> GameAgent:
        """Return the agent for the current player."""
        ...

    @abstractmethod
    def advance_turn(self) -> None:
        """Advance the game to the next turn."""
        ...

    @abstractmethod
    def get_coverage_stats(self, state: dict) -> tuple:
        """
        Return (covered_cells, board_cell_count) for reporting coverage.
        The field names stay generic even for non-board games.
        """
        ...

    @classmethod
    @abstractmethod
    def make_random_agent(cls) -> GameAgent:
        """Return a new random-play agent for this game type."""
        ...

    @classmethod
    @abstractmethod
    def make_greedy_agent(cls) -> GameAgent:
        """Return a new greedy-play agent for this game type."""
        ...

    @classmethod
    @abstractmethod
    def create(cls, mechanic_fn=None, agent1: GameAgent = None,
               agent2: GameAgent = None) -> 'GameInterface':
        """Return a fresh game instance ready to play."""
        ...
