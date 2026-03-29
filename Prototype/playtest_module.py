"""
playtest_module.py
==================
DesignVoyager — Playtest Module

Step 3 of the loop: runs automated games to measure how good the
mechanic is. Uses pure Python agents — NO OpenAI API calls here.

Measures three things:
  1. Playability  — what fraction of games finish normally?
  2. Balance      — how even are the win rates? (lower gap = fairer)
  3. Depth        — does a stronger MCTS budget outperform a weaker one?
"""

import multiprocessing as mp
import queue

from boardwalk import Board
from base_game import BaseGame, RandomAgent, BOARD_SIZE, PLAYER_1, PLAYER_2
from compile_check import load_mechanic_fn
from mcts_agent import MCTSAgent

# How many games to run per measurement
N_GAMES_BALANCE = 60    # for playability + balance
N_GAMES_DEPTH   = 40    # for strategic depth
MAX_TURNS       = 100   # safety cap — gives complex mechanics more room to resolve
GAME_TIMEOUT    = 4.0   # wall-clock seconds per game

BALANCE_MCTS_SIMS = 20
DEPTH_STRONG_SIMS = 50
DEPTH_WEAK_SIMS   = 10


def _build_agent(spec: dict):
    kind = spec.get("kind", "random")
    if kind == "mcts":
        return MCTSAgent(
            simulations=spec.get("simulations", BALANCE_MCTS_SIMS),
            exploration=spec.get("exploration", 1.4),
            rollout_depth=spec.get("rollout_depth", 16),
        )
    return RandomAgent()


def run_single_game(mechanic_fn=None, agent1=None, agent2=None) -> tuple:
    """
    Run one game and return (winner, completed_normally).

    Args:
        mechanic_fn : optional Python function to add as a mechanic
        agent1      : AIPlayer for PLAYER_1 (default: RandomAgent)
        agent2      : AIPlayer for PLAYER_2 (default: RandomAgent)

    Returns:
        (winner: int or None, completed: bool)
        winner=None means draw or did not complete
    """
    agent1 = agent1 or RandomAgent()
    agent2 = agent2 or RandomAgent()

    board    = Board((BOARD_SIZE, BOARD_SIZE))
    mechanics = [mechanic_fn] if mechanic_fn else []
    game     = BaseGame(board, ai_players={PLAYER_1: agent1, PLAYER_2: agent2},
                        mechanics=mechanics)

    turn_count = 0
    while True:
        if turn_count > MAX_TURNS:
            return None, False   # Safety: didn't finish in time

        state = game.get_state()
        moves = game.possible_moves(state)

        if not moves:
            return None, True   # Draw — board full

        agent = game.ai_players[game.current_player]
        move  = agent.get_action(game, state)

        if not game.validate_move(move):
            return None, False  # Invalid move = broken mechanic

        game.perform_move(move)

        if game.game_finished():
            winner = game.get_winner()
            return winner, True

        game.current_player = game.next_player()
        game.turn           = game.turn_counter()
        turn_count += 1


def _play_game_worker(code: str, agent1_spec: dict, agent2_spec: dict, result_queue):
    """
    Child-process entry point for a single game.
    """
    try:
        mechanic_fn = load_mechanic_fn(code) if code else None
        result = run_single_game(
            mechanic_fn=mechanic_fn,
            agent1=_build_agent(agent1_spec),
            agent2=_build_agent(agent2_spec),
        )
        result_queue.put(result)
    except Exception:
        result_queue.put((None, False))


def _run_game_safe(code: str, agent1_spec: dict, agent2_spec: dict) -> tuple:
    """
    Run a single game inside a subprocess so timeouts work on Windows and macOS.
    """
    ctx = mp.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_play_game_worker,
        args=(code, agent1_spec, agent2_spec, result_queue),
    )
    process.start()
    process.join(GAME_TIMEOUT)

    if process.is_alive():
        process.terminate()
        process.join()
        return None, False

    try:
        return result_queue.get_nowait()
    except queue.Empty:
        return None, False


def measure_playability_and_balance(code: str = "") -> tuple:
    """
    Run N games with symmetric low-budget MCTS agents.

    Returns:
        playability : fraction of games that completed normally (0.0 - 1.0)
        balance_gap : |P1_wins - P2_wins| / completed_games (0.0 = perfect balance)
    """
    completed = 0
    p1_wins   = 0
    p2_wins   = 0

    agent_specs = [
        {"kind": "mcts", "simulations": BALANCE_MCTS_SIMS},
        {"kind": "mcts", "simulations": BALANCE_MCTS_SIMS},
    ]

    for _ in range(N_GAMES_BALANCE):
        winner, ok = _run_game_safe(code, agent_specs[0], agent_specs[1])
        if ok:
            completed += 1
            if winner == PLAYER_1:
                p1_wins += 1
            elif winner == PLAYER_2:
                p2_wins += 1

    playability = completed / N_GAMES_BALANCE
    if completed == 0:
        return 0.0, 1.0

    balance_gap = abs(p1_wins - p2_wins) / completed
    return playability, balance_gap


def measure_depth(code: str = "") -> float:
    """
    Run N games alternating seats: strong-budget MCTS vs weak-budget MCTS.
    A higher strong-agent win rate suggests the game rewards better decisions
    and deeper search.

    Returns:
        depth_proxy : strong-budget win rate (0.0 - 1.0)
    """
    strong_wins = 0
    completed   = 0

    strong_spec = {"kind": "mcts", "simulations": DEPTH_STRONG_SIMS}
    weak_spec   = {"kind": "mcts", "simulations": DEPTH_WEAK_SIMS}

    for game_index in range(N_GAMES_DEPTH):
        strong_as_p1 = (game_index % 2 == 0)
        agent1_spec = strong_spec if strong_as_p1 else weak_spec
        agent2_spec = weak_spec if strong_as_p1 else strong_spec

        winner, ok = _run_game_safe(code, agent1_spec, agent2_spec)
        if ok:
            completed += 1
            if strong_as_p1 and winner == PLAYER_1:
                strong_wins += 1
            elif (not strong_as_p1) and winner == PLAYER_2:
                strong_wins += 1

    if completed == 0:
        return 0.0

    return strong_wins / completed


def playtest(mechanic: dict) -> dict:
    """
    Full playtest of a mechanic. Runs automated games and returns scores.

    Args:
        mechanic : dict from proposal_module (must have 'python_code')

    Returns:
        scores dict with keys:
            playability  (higher is better, target >= 0.8)
            balance_gap  (lower is better, target <= 0.4)
            depth        (higher is better)
            aggregate    (combined score for ranking)
    """
    name = mechanic.get("mechanic_name", "unknown")
    code = mechanic.get("python_code", "")

    print(f"[Playtest] Running games for '{name}'...")

    playability, balance_gap = measure_playability_and_balance(code)
    depth                    = measure_depth(code)

    # Aggregate score — playability is a hard binary gate in verification,
    # so it is excluded here to avoid inflating scores.
    # Balance and depth each carry 50% weight.
    aggregate = (
        0.5 * (1.0 - balance_gap) +
        0.5 * depth
    )

    scores = {
        "playability":  round(playability, 3),
        "balance_gap":  round(balance_gap, 3),
        "depth":        round(depth, 3),
        "aggregate":    round(aggregate, 3),
    }

    print(f"  [Playtest] playability={scores['playability']:.2f}  "
          f"balance_gap={scores['balance_gap']:.2f}  "
          f"depth={scores['depth']:.2f}  "
          f"aggregate={scores['aggregate']:.2f}")

    return scores
