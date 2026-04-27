"""
playtest_module.py
==================
DesignVoyager - Playtest Module

Produces both the compact score summary used by verification and a richer
runtime report for self-verification integration.
"""

import copy
import multiprocessing as mp
import os
import queue
import sys

import numpy as np

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from base_game import BaseGame, PLAYER_1, PLAYER_2
from card_game import CardGame
from compile_check import load_mechanic_fn
from mcts_agent import MCTSAgent

N_GAMES_BALANCE = 12
N_GAMES_DEPTH = 12
MAX_TURNS = 100
GAME_TIMEOUT = 4.0

# Recommended default budgets:
# - balance: low-vs-low MCTS, enough games to reduce obvious noise
# - depth: strong-vs-weak MCTS, with a clear simulation gap
BALANCE_MCTS_SIMS = 24
DEPTH_STRONG_SIMS = 64
DEPTH_WEAK_SIMS = 16

CARD_N_GAMES_BALANCE = 16
CARD_N_GAMES_DEPTH = 16
CARD_BALANCE_MCTS_SIMS = 40
CARD_DEPTH_STRONG_SIMS = 96
CARD_DEPTH_WEAK_SIMS = 24

_last_runtime_report = {}


def _normalize(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    return value


def serialize_state(state: dict) -> dict:
    return _normalize(state)


def _states_differ(before: dict, after: dict) -> bool:
    return _normalize(before) != _normalize(after)


def _build_agent(game_class, spec: dict):
    kind = spec.get("kind", "random")
    if kind == "mcts":
        return MCTSAgent(
            simulations=spec.get("simulations", BALANCE_MCTS_SIMS),
            exploration=spec.get("exploration", 1.4),
            rollout_depth=spec.get("rollout_depth", 16),
        )
    if kind == "greedy":
        return game_class.make_greedy_agent()
    return game_class.make_random_agent()


def _metric_config(game_class) -> dict:
    is_card = issubclass(game_class, CardGame)
    if is_card:
        return {
            "n_balance": CARD_N_GAMES_BALANCE,
            "n_depth": CARD_N_GAMES_DEPTH,
            "balance_sims": CARD_BALANCE_MCTS_SIMS,
            "depth_strong_sims": CARD_DEPTH_STRONG_SIMS,
            "depth_weak_sims": CARD_DEPTH_WEAK_SIMS,
        }
    return {
        "n_balance": N_GAMES_BALANCE,
        "n_depth": N_GAMES_DEPTH,
        "balance_sims": BALANCE_MCTS_SIMS,
        "depth_strong_sims": DEPTH_STRONG_SIMS,
        "depth_weak_sims": DEPTH_WEAK_SIMS,
    }


def _wrap_mechanic(mechanic_fn, tracker: dict):
    if mechanic_fn is None:
        return None

    def wrapped(game_state: dict):
        tracker["trigger_count"] += 1
        before = copy.deepcopy(game_state)
        result = mechanic_fn(game_state)
        after = result if isinstance(result, dict) else game_state
        if _states_differ(before, after):
            tracker["state_changed_by_mechanic_count"] += 1
        return result

    wrapped._inner_mechanic = mechanic_fn
    return wrapped


def _set_starting_player(game, starting_player):
    if starting_player is None:
        return
    if hasattr(game, "state") and isinstance(game.state, dict):
        game.state["current_player"] = starting_player


def run_single_game(mechanic_fn=None, agent1=None, agent2=None, game_class=None, starting_player=None) -> dict:
    game_class = game_class or BaseGame
    agent1 = agent1 or game_class.make_random_agent()
    agent2 = agent2 or game_class.make_random_agent()

    tracker = {
        "trigger_count": 0,
        "state_changed_by_mechanic_count": 0,
    }
    wrapped_mechanic = _wrap_mechanic(mechanic_fn, tracker)
    game = game_class.create(mechanic_fn=wrapped_mechanic, agent1=agent1, agent2=agent2)
    _set_starting_player(game, starting_player)

    total_turns = 0
    multi_choice_turns = 0

    while True:
        if total_turns > MAX_TURNS:
            return {
                "winner": None,
                "completed": False,
                "turns": total_turns,
                "multi_choice_turns": multi_choice_turns,
                "covered_cells": 0,
                "board_cell_count": 0,
                "trigger_count": tracker["trigger_count"],
                "state_changed_by_mechanic_count": tracker["state_changed_by_mechanic_count"],
                "triggered": tracker["trigger_count"] > 0,
            }

        state = game.get_state()
        moves = game.possible_moves(state)

        if len(moves) > 1:
            multi_choice_turns += 1
        total_turns += 1

        if not moves:
            covered_cells, board_cell_count = game.get_coverage_stats(game.get_state())
            return {
                "winner": None,
                "completed": True,
                "turns": total_turns,
                "multi_choice_turns": multi_choice_turns,
                "covered_cells": covered_cells,
                "board_cell_count": board_cell_count,
                "trigger_count": tracker["trigger_count"],
                "state_changed_by_mechanic_count": tracker["state_changed_by_mechanic_count"],
                "triggered": tracker["trigger_count"] > 0,
            }

        agent = game.get_current_agent()
        move = agent.choose_move(game, state, moves)

        if not game.is_valid_move(move):
            covered_cells, board_cell_count = game.get_coverage_stats(game.get_state())
            return {
                "winner": None,
                "completed": False,
                "turns": total_turns,
                "multi_choice_turns": multi_choice_turns,
                "covered_cells": covered_cells,
                "board_cell_count": board_cell_count,
                "trigger_count": tracker["trigger_count"],
                "state_changed_by_mechanic_count": tracker["state_changed_by_mechanic_count"],
                "triggered": tracker["trigger_count"] > 0,
            }

        game.perform_move(move)

        if game.game_finished():
            covered_cells, board_cell_count = game.get_coverage_stats(game.get_state())
            return {
                "winner": game.get_winner(),
                "completed": True,
                "turns": total_turns,
                "multi_choice_turns": multi_choice_turns,
                "covered_cells": covered_cells,
                "board_cell_count": board_cell_count,
                "trigger_count": tracker["trigger_count"],
                "state_changed_by_mechanic_count": tracker["state_changed_by_mechanic_count"],
                "triggered": tracker["trigger_count"] > 0,
            }

        game.advance_turn()


def run_single_game_recorded(mechanic_fn=None, game_class=None, agent1=None, agent2=None, starting_player=None) -> dict:
    game_class = game_class or BaseGame
    config = _metric_config(game_class)
    agent1 = agent1 or MCTSAgent(simulations=config["depth_strong_sims"])
    agent2 = agent2 or MCTSAgent(simulations=config["depth_strong_sims"])

    tracker = {
        "trigger_count": 0,
        "state_changed_by_mechanic_count": 0,
    }
    wrapped_mechanic = _wrap_mechanic(mechanic_fn, tracker)
    game = game_class.create(mechanic_fn=wrapped_mechanic, agent1=agent1, agent2=agent2)
    _set_starting_player(game, starting_player)

    initial_state = serialize_state(game.get_state())
    move_log = []
    turn_count = 0

    while True:
        if turn_count > MAX_TURNS:
            return {
                "winner": None,
                "completed": False,
                "turns": turn_count,
                "initial_state": initial_state,
                "moves": move_log,
                "trigger_count": tracker["trigger_count"],
                "state_changed_by_mechanic_count": tracker["state_changed_by_mechanic_count"],
            }

        state = game.get_state()
        moves = game.possible_moves(state)

        if not moves:
            return {
                "winner": None,
                "completed": True,
                "turns": turn_count,
                "initial_state": initial_state,
                "moves": move_log,
                "trigger_count": tracker["trigger_count"],
                "state_changed_by_mechanic_count": tracker["state_changed_by_mechanic_count"],
            }

        player = state.get("current_player")
        agent = game.get_current_agent()
        move = agent.choose_move(game, state, moves)

        if not game.is_valid_move(move):
            return {
                "winner": None,
                "completed": False,
                "turns": turn_count,
                "initial_state": initial_state,
                "moves": move_log,
                "trigger_count": tracker["trigger_count"],
                "state_changed_by_mechanic_count": tracker["state_changed_by_mechanic_count"],
            }

        game.perform_move(move)
        turn_count += 1

        state_before_mechanics = None
        if hasattr(game, "_state_before_mechanics") and game._state_before_mechanics is not None:
            state_before_mechanics = serialize_state(game._state_before_mechanics)

        move_log.append(
            {
                "turn": turn_count,
                "player": player,
                "move": move if isinstance(move, (int, float, str, bool)) else str(move),
                "state_before_mechanics": state_before_mechanics,
                "state_after": serialize_state(game.get_state()),
            }
        )

        if game.game_finished():
            return {
                "winner": game.get_winner(),
                "completed": True,
                "turns": turn_count,
                "initial_state": initial_state,
                "moves": move_log,
                "trigger_count": tracker["trigger_count"],
                "state_changed_by_mechanic_count": tracker["state_changed_by_mechanic_count"],
            }

        game.advance_turn()


def _play_game_worker(code: str, agent1_spec: dict, agent2_spec: dict, game_class, result_queue, starting_player):
    try:
        mechanic_fn = load_mechanic_fn(code) if code else None
        result = run_single_game(
            mechanic_fn=mechanic_fn,
            agent1=_build_agent(game_class, agent1_spec),
            agent2=_build_agent(game_class, agent2_spec),
            game_class=game_class,
            starting_player=starting_player,
        )
        result_queue.put(result)
    except Exception:
        result_queue.put({
            "winner": None,
            "completed": False,
            "turns": 0,
            "multi_choice_turns": 0,
            "covered_cells": 0,
            "board_cell_count": 0,
            "trigger_count": 0,
            "state_changed_by_mechanic_count": 0,
            "triggered": False,
        })


def _run_game_safe(code: str, agent1_spec: dict, agent2_spec: dict, game_class=None, starting_player=None) -> dict:
    game_class = game_class or BaseGame
    ctx = mp.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_play_game_worker,
        args=(code, agent1_spec, agent2_spec, game_class, result_queue, starting_player),
    )
    process.start()
    process.join(GAME_TIMEOUT)

    if process.is_alive():
        process.terminate()
        process.join()
        return {
            "winner": None,
            "completed": False,
            "turns": 0,
            "multi_choice_turns": 0,
            "covered_cells": 0,
            "board_cell_count": 0,
            "trigger_count": 0,
            "state_changed_by_mechanic_count": 0,
            "triggered": False,
        }

    try:
        return result_queue.get_nowait()
    except queue.Empty:
        return {
            "winner": None,
            "completed": False,
            "turns": 0,
            "multi_choice_turns": 0,
            "covered_cells": 0,
            "board_cell_count": 0,
            "trigger_count": 0,
            "state_changed_by_mechanic_count": 0,
            "triggered": False,
        }


def dry_run_integration(code: str, game_class=None) -> tuple:
    game_class = game_class or BaseGame
    result = _run_game_safe(code, {"kind": "random"}, {"kind": "random"}, game_class=game_class)
    return result["completed"], "" if result["completed"] else "Single integration dry run did not complete."


def _collect_balance_metrics(code: str = "", game_class=None) -> dict:
    game_class = game_class or BaseGame
    config = _metric_config(game_class)
    alternate_starting_player = issubclass(game_class, CardGame)
    completed = 0
    p1_wins = 0
    p2_wins = 0
    draws = 0
    total_turns = 0
    multi_choice_turns = 0
    covered_total = 0
    board_cell_count = 0
    trigger_count = 0
    triggered_matches = 0
    state_changed = 0
    total_matches = config["n_balance"]

    low_spec_a = {"kind": "mcts", "simulations": config["balance_sims"]}
    low_spec_b = {"kind": "mcts", "simulations": config["balance_sims"]}

    for game_index in range(total_matches):
        # We alternate the seat assignment explicitly even though both agents use
        # the same low MCTS budget, so the balance protocol stays symmetric and
        # easy to explain in reports/slides.
        agent1_spec = low_spec_a if game_index % 2 == 0 else low_spec_b
        agent2_spec = low_spec_b if game_index % 2 == 0 else low_spec_a
        starting_player = (PLAYER_1 if game_index % 2 == 0 else PLAYER_2) if alternate_starting_player else PLAYER_1
        result = _run_game_safe(
            code,
            agent1_spec,
            agent2_spec,
            game_class=game_class,
            starting_player=starting_player,
        )
        total_turns += result["turns"]
        multi_choice_turns += result["multi_choice_turns"]
        covered_total += result["covered_cells"]
        board_cell_count = max(board_cell_count, result["board_cell_count"])
        trigger_count += result["trigger_count"]
        state_changed += result["state_changed_by_mechanic_count"]
        if result["triggered"]:
            triggered_matches += 1

        if result["completed"]:
            completed += 1
            if result["winner"] == PLAYER_1:
                p1_wins += 1
            elif result["winner"] == PLAYER_2:
                p2_wins += 1
            else:
                draws += 1

    avg_game_length = total_turns / total_matches if total_matches else 0.0
    playability = completed / total_matches if total_matches else 0.0
    p1_win_rate = p1_wins / total_matches if total_matches else 0.0
    p2_win_rate = p2_wins / total_matches if total_matches else 0.0
    balance_gap = abs(p1_win_rate - p2_win_rate)
    draw_rate = draws / total_matches if total_matches else 0.0
    decisiveness = 1.0 - draw_rate
    agency = multi_choice_turns / total_turns if total_turns else 0.0
    coverage = (covered_total / total_matches) / board_cell_count if total_matches and board_cell_count else 0.0

    return {
        "total_matches": total_matches,
        "completed_matches": completed,
        "p1_wins": p1_wins,
        "p2_wins": p2_wins,
        "draws": draws,
        "p1_win_rate": round(p1_win_rate, 3),
        "p2_win_rate": round(p2_win_rate, 3),
        "balance_gap": round(balance_gap, 3),
        "draw_rate": round(draw_rate, 3),
        "decisiveness": round(decisiveness, 3),
        "avg_game_length": round(avg_game_length, 3),
        "multi_choice_turns": multi_choice_turns,
        "total_turns": total_turns,
        "agency": round(agency, 3),
        "covered_cells": int(round(covered_total / total_matches)) if total_matches else 0,
        "board_cell_count": board_cell_count,
        "coverage": round(coverage, 3),
        "trigger_count": trigger_count,
        "triggered_matches": triggered_matches,
        "state_changed_by_mechanic_count": state_changed,
    }


def _collect_depth_metrics(code: str = "", game_class=None) -> dict:
    game_class = game_class or BaseGame
    config = _metric_config(game_class)
    alternate_starting_player = issubclass(game_class, CardGame)
    strong_wins = 0
    weak_wins = 0
    completed = 0

    n_matches = config["n_depth"]
    strong_spec = {"kind": "mcts", "simulations": config["depth_strong_sims"]}
    weak_spec = {"kind": "mcts", "simulations": config["depth_weak_sims"]}

    for game_index in range(n_matches):
        strong_as_p1 = (game_index % 2 == 0)
        starting_player = (PLAYER_1 if strong_as_p1 else PLAYER_2) if alternate_starting_player else PLAYER_1
        agent1_spec = strong_spec if strong_as_p1 else weak_spec
        agent2_spec = weak_spec if strong_as_p1 else strong_spec
        result = _run_game_safe(
            code,
            agent1_spec,
            agent2_spec,
            game_class=game_class,
            starting_player=starting_player,
        )
        if result["completed"]:
            completed += 1
            if strong_as_p1 and result["winner"] == PLAYER_1:
                strong_wins += 1
            elif (not strong_as_p1) and result["winner"] == PLAYER_2:
                strong_wins += 1
            elif result["winner"] in (PLAYER_1, PLAYER_2):
                weak_wins += 1

    strong_rate = strong_wins / completed if completed else 0.0
    weak_rate = weak_wins / completed if completed else 0.0
    depth = strong_rate - weak_rate

    return {
        "strong_vs_weak_matches": n_matches,
        "strong_agent_wins": strong_wins,
        "weak_agent_wins": weak_wins,
        "strong_agent_win_rate": round(strong_rate, 3),
        "weak_agent_win_rate": round(weak_rate, 3),
        "depth": round(depth, 3),
    }


def _merge_metrics(balance_metrics: dict, depth_metrics: dict) -> dict:
    merged = dict(balance_metrics)
    merged.update(depth_metrics)
    return merged


def _build_scores(child_metrics: dict) -> dict:
    playability = child_metrics["completed_matches"] / child_metrics["total_matches"] if child_metrics["total_matches"] else 0.0
    balance_gap = child_metrics["balance_gap"]
    depth = child_metrics["depth"]
    balance_score = (1.0 - balance_gap) if child_metrics["completed_matches"] > 0 else None
    raw_quality = 0.5 * (balance_score if balance_score is not None else 0.0) + 0.5 * max(depth, 0.0)
    aggregate = playability * raw_quality
    return {
        "playability": round(playability, 3),
        "balance_gap": round(balance_gap, 3),
        "balance_score": round(balance_score, 3) if balance_score is not None else None,
        "depth": round(depth, 3),
        "aggregate": round(aggregate, 3),
    }


def build_runtime_report(mechanic: dict, integration: dict, parent_metrics: dict,
                         child_metrics: dict, stage: int = 1, retry_count: int = 0) -> dict:
    scores = _build_scores(child_metrics)
    trigger_stats = {
        "trigger_count": child_metrics["trigger_count"],
        "triggered_matches": child_metrics["triggered_matches"],
        "total_matches": child_metrics["total_matches"],
        "total_turns": child_metrics["total_turns"],
        "state_changed_by_mechanic_count": child_metrics["state_changed_by_mechanic_count"],
        "trigger_rate_by_match": round(
            child_metrics["triggered_matches"] / child_metrics["total_matches"], 3
        ) if child_metrics["total_matches"] else 0.0,
        "trigger_rate_by_turn": round(
            child_metrics["trigger_count"] / child_metrics["total_turns"], 3
        ) if child_metrics["total_turns"] else 0.0,
    }

    return {
        "stage": stage,
        "retry_count": retry_count,
        "mechanic": {
            "mechanic_name": mechanic.get("mechanic_name", "unknown"),
            "mechanic_type": mechanic.get("mechanic_type", "other"),
            "description": mechanic.get("description", ""),
            "python_code": mechanic.get("python_code", ""),
            "justification": mechanic.get("justification", ""),
            "hook_location": mechanic.get("hook_location", "perform_move"),
        },
        "integration": integration,
        "parent_metrics": {
            k: v for k, v in parent_metrics.items()
            if k not in {"trigger_count", "triggered_matches", "state_changed_by_mechanic_count"}
        },
        "child_metrics": {
            k: v for k, v in child_metrics.items()
            if k not in {"trigger_count", "triggered_matches", "state_changed_by_mechanic_count"}
        },
        "trigger_stats": trigger_stats,
        "derived_scores": {
            "playability": scores["playability"],
            "balance_gap": scores["balance_gap"],
            "depth": scores["depth"],
            "aggregate": scores["aggregate"],
        },
        "parent_summary": "Baseline game without the new mechanic.",
    }


def get_last_runtime_report() -> dict:
    return copy.deepcopy(_last_runtime_report)


def playtest(mechanic: dict, game_class=None, integration: dict = None,
             stage: int = 1, retry_count: int = 0) -> dict:
    global _last_runtime_report

    game_class = game_class or BaseGame
    name = mechanic.get("mechanic_name", "unknown")
    code = mechanic.get("python_code", "")

    print(f"[Playtest] Running games for '{name}'...")

    parent_balance = _collect_balance_metrics("", game_class=game_class)
    parent_depth = _collect_depth_metrics("", game_class=game_class)
    child_balance = _collect_balance_metrics(code, game_class=game_class)
    child_depth = _collect_depth_metrics(code, game_class=game_class)

    parent_metrics = _merge_metrics(parent_balance, parent_depth)
    child_metrics = _merge_metrics(child_balance, child_depth)
    scores = _build_scores(child_metrics)

    if integration is None:
        integration = {
            "schema_ok": True,
            "syntax_ok": True,
            "hook_ok": True,
            "instantiation_ok": True,
            "dry_run_ok": True,
            "error_message": "",
        }

    _last_runtime_report = build_runtime_report(
        mechanic,
        integration,
        parent_metrics,
        child_metrics,
        stage=stage,
        retry_count=retry_count,
    )

    print(
        f"  [Playtest] playability={scores['playability']:.2f}  "
        f"balance_gap={scores['balance_gap']:.2f}  "
        f"depth={scores['depth']:.2f}  "
        f"aggregate={scores['aggregate']:.2f}"
    )

    return scores
