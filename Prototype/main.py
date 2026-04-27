"""
main.py
=======
DesignVoyager - Full Loop

Supports multiple game types while preserving board-game MCTS playtesting.
"""

import argparse
import json
import os
import re

from dotenv import load_dotenv

from base_game import BaseGame
from card_game import CardGame
from compile_check import check_runtime, check_syntax, compile_check, load_mechanic_fn
from curriculum import Curriculum
from mechanic_library import MechanicLibrary
from playtest_module import dry_run_integration, get_last_runtime_report, playtest
from proposal_module import propose_mechanic
from verification_module import ACCEPT, DISCARD, REVISE, verify
import discarded_library

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PROJECT_DIR, ".env"))

GAME_REGISTRY = {
    "board": (
        BaseGame,
        os.path.join(PROJECT_DIR, "library.json"),
        os.path.join(PROJECT_DIR, "discarded_board.json"),
    ),
    "card": (
        CardGame,
        os.path.join(PROJECT_DIR, "library_card.json"),
        os.path.join(PROJECT_DIR, "discarded_card.json"),
    ),
}

DEFAULT_ITERATIONS = 1
DEFAULT_TOP_K = 3
DEFAULT_GAME = "board"
DEFAULT_USER_PROMPT = "I want a score-based mechanic."

_last_scores: dict = {}
_last_runtime_report: dict = {}


def run_loop(n_iterations: int = DEFAULT_ITERATIONS, top_k: int = DEFAULT_TOP_K,
             game_name: str = DEFAULT_GAME, user_prompt: str = DEFAULT_USER_PROMPT):
    game_class, library_file, discarded_file = GAME_REGISTRY[game_name]
    game_template = game_class.create()
    game_skeleton = game_template.get_skeleton_description()
    state_desc = game_template.get_state_description()
    dummy_state = game_template.get_dummy_state()

    library = MechanicLibrary(filepath=library_file)
    curriculum = Curriculum()
    banned_names = discarded_library.load(discarded_file)
    tried_this_run = set()

    print("\n" + "=" * 60)
    print("  DesignVoyager - Autonomous Game Mechanic Designer")
    print("=" * 60)
    print(f"  Game       : {game_name} ({game_class.__name__})")
    print(f"  Iterations : {n_iterations}")
    print(f"  Context k  : {top_k}")
    if user_prompt:
        print(f"  User Prompt: {user_prompt[:50]}..." if len(user_prompt) > 50 else f"  User Prompt: {user_prompt}")
    print(f"  Library    : {library.summary()}")
    print(f"  Curriculum : {curriculum.progress_str()}")
    print(f"  Banned     : {len(banned_names)} previously discarded mechanics")
    print("=" * 60 + "\n")

    accepted_count = 0
    discarded_count = 0

    for iteration in range(1, n_iterations + 1):
        print(f"\n{'-' * 60}")
        print(f"  ITERATION {iteration} / {n_iterations}  |  {curriculum.progress_str()}")
        print(f"{'-' * 60}")

        retrieval_query = f"{game_skeleton} {curriculum.stage_name()} {user_prompt}".strip()
        retrieved = library.retrieve(k=top_k, query=retrieval_query)
        print(f"[Loop] Retrieved {len(retrieved)} mechanics for context.")

        mechanic = propose_mechanic(
            game_skeleton,
            retrieved,
            stage_prompt=curriculum.stage_prompt(),
            user_prompt=user_prompt,
            state_description=state_desc,
            banned_names=list(set(banned_names) | tried_this_run),
        )
        if mechanic is None:
            print("[Loop] Proposal failed - skipping this iteration.\n")
            curriculum.on_discard()
            discarded_count += 1
            continue
        tried_this_run.add(mechanic.get("mechanic_name", ""))

        pre_playtest_revised = False
        similarity_outcome = _check_novelty_gate(mechanic, library, already_revised=False)
        if similarity_outcome == REVISE:
            print("[Loop] Proposed mechanic is too similar to the existing library - revising before playtest.\n")
            revised_mechanic = _revise(
                mechanic,
                game_skeleton,
                retrieved,
                curriculum.stage_prompt(),
                user_prompt,
                state_description=state_desc,
                banned_names=list(set(banned_names) | tried_this_run),
            )
            if revised_mechanic is None:
                print("[Loop] Revision failed - discarding.\n")
                discarded_library.save_name(mechanic.get("mechanic_name", ""), discarded_file)
                banned_names.append(mechanic.get("mechanic_name", ""))
                curriculum.on_discard()
                discarded_count += 1
                continue
            tried_this_run.add(revised_mechanic.get("mechanic_name", ""))

            similarity_outcome = _check_novelty_gate(revised_mechanic, library, already_revised=True)
            if similarity_outcome == DISCARD:
                discarded_library.save_name(revised_mechanic.get("mechanic_name", ""), discarded_file)
                banned_names.append(revised_mechanic.get("mechanic_name", ""))
                curriculum.on_discard()
                discarded_count += 1
                print("[Loop] discarded before playtest because the revised mechanic still duplicates the library.")
                continue
            mechanic = revised_mechanic
            pre_playtest_revised = True

        outcome = _compile_playtest_verify(
            mechanic,
            already_revised=pre_playtest_revised,
            game_class=game_class,
            dummy_state=dummy_state,
            game_name=game_name,
            iteration=iteration,
            stage=curriculum.stage,
        )

        if outcome == REVISE:
            print("[Loop] Sending for revision...\n")
            revised_mechanic = _revise(
                mechanic,
                game_skeleton,
                retrieved,
                curriculum.stage_prompt(),
                user_prompt,
                state_description=state_desc,
                banned_names=list(set(banned_names) | tried_this_run),
            )
            if revised_mechanic is None:
                print("[Loop] Revision failed - discarding.\n")
                discarded_library.save_name(mechanic.get("mechanic_name", ""), discarded_file)
                banned_names.append(mechanic.get("mechanic_name", ""))
                curriculum.on_discard()
                discarded_count += 1
                continue
            tried_this_run.add(revised_mechanic.get("mechanic_name", ""))
            outcome = _compile_playtest_verify(
                revised_mechanic,
                already_revised=True,
                game_class=game_class,
                dummy_state=dummy_state,
                game_name=game_name,
                iteration=iteration,
                stage=curriculum.stage,
            )
            mechanic = revised_mechanic

        if outcome == ACCEPT:
            scores = _get_scores()
            mechanic["_game_type"] = game_name
            added = library.add(mechanic, scores, iteration=iteration)
            advanced = curriculum.on_accept()
            accepted_count += 1
            if added:
                print(f"[Loop] accepted and stored. Library now has {library.size()} mechanics.")
            else:
                print("[Loop] accepted by verification, but not stored because it duplicates an existing library entry.")
            if advanced:
                print(f"[Curriculum] advanced to {curriculum.stage_name()}.")
        else:
            discarded_library.save_name(mechanic.get("mechanic_name", ""), discarded_file)
            banned_names.append(mechanic.get("mechanic_name", ""))
            curriculum.on_discard()
            discarded_count += 1
            print("[Loop] discarded after revision.")

    print("\n" + "=" * 60)
    print("  Run complete!")
    print(f"  Accepted  : {accepted_count}")
    print(f"  Discarded : {discarded_count}")
    print(f"  {library.summary()}")
    print("=" * 60 + "\n")


def _compile_playtest_verify(mechanic: dict, already_revised: bool,
                             game_class=None, dummy_state: dict = None,
                             game_name: str = DEFAULT_GAME, iteration: int = 0,
                             stage: int = 1) -> str:
    global _last_scores, _last_runtime_report

    integration = _build_integration_report(mechanic, game_class=game_class, dummy_state=dummy_state)
    ok, error = compile_check(mechanic, dummy_state=dummy_state)
    if not ok:
        _last_runtime_report = _build_failure_report(
            mechanic, integration, stage=stage, retry_count=int(already_revised)
        )
        _save_runtime_report(_last_runtime_report, game_name, mechanic.get("mechanic_name", "unknown"), iteration, already_revised)
        feedback = (
            f"The code failed a syntax or runtime check: {error}. "
            f"Please rewrite the function so it runs without errors."
        )
        if already_revised:
            return DISCARD
        mechanic["_revision_feedback"] = feedback
        return REVISE

    scores = playtest(
        mechanic,
        game_class=game_class,
        integration=integration,
        stage=stage,
        retry_count=int(already_revised),
    )
    _last_scores = scores
    _last_runtime_report = get_last_runtime_report()
    mechanic["_self_verification_report"] = _last_runtime_report
    _save_runtime_report(_last_runtime_report, game_name, mechanic.get("mechanic_name", "unknown"), iteration, already_revised)

    decision, feedback = verify(mechanic, scores, already_revised)
    if decision == REVISE:
        mechanic["_revision_feedback"] = feedback
    return decision


def _check_novelty_gate(mechanic: dict, library: MechanicLibrary, already_revised: bool) -> str | None:
    similar_entry, similarity = library.find_most_similar(mechanic)
    if similar_entry is None:
        return None

    feedback = (
        f"This mechanic is too similar to existing library mechanic "
        f"'{similar_entry['mechanic_name']}' (similarity {similarity:.3f}). "
        "Please propose a functionally distinct mechanic before running playtests."
    )
    mechanic["_revision_feedback"] = feedback
    return DISCARD if already_revised else REVISE


def _get_scores() -> dict:
    return _last_scores.copy()


def _build_integration_report(mechanic: dict, game_class=None, dummy_state: dict = None) -> dict:
    game_class = game_class or BaseGame
    required_fields = ["mechanic_name", "mechanic_type", "description", "python_code", "justification"]
    schema_ok = all(field in mechanic for field in required_fields)
    code = mechanic.get("python_code", "")
    syntax_ok, syntax_error = check_syntax(code)
    runtime_ok, runtime_error = check_runtime(code, dummy_state=dummy_state) if syntax_ok else (False, syntax_error)

    hook_location = mechanic.get("hook_location", "perform_move")
    hook_ok = hook_location == "perform_move"

    mechanic_fn = None
    instantiation_ok = False
    instantiation_error = ""
    if runtime_ok:
        try:
            mechanic_fn = load_mechanic_fn(code)
            game_class.create(mechanic_fn=mechanic_fn)
            instantiation_ok = True
        except Exception as e:
            instantiation_error = f"{type(e).__name__}: {e}"

    dry_run_ok, dry_run_error = dry_run_integration(code, game_class=game_class) if instantiation_ok else (False, instantiation_error or runtime_error)
    error_message = ""
    for err in [syntax_error, runtime_error, instantiation_error, dry_run_error]:
        if err:
            error_message = err
            break

    return {
        "schema_ok": schema_ok,
        "syntax_ok": syntax_ok,
        "hook_ok": hook_ok,
        "instantiation_ok": instantiation_ok,
        "dry_run_ok": dry_run_ok,
        "error_message": error_message,
    }


def _build_failure_report(mechanic: dict, integration: dict, stage: int, retry_count: int) -> dict:
    empty_metrics = {
        "total_matches": 0,
        "completed_matches": 0,
        "p1_wins": 0,
        "p2_wins": 0,
        "draws": 0,
        "p1_win_rate": 0.0,
        "p2_win_rate": 0.0,
        "balance_gap": 0.0,
        "draw_rate": 0.0,
        "decisiveness": 0.0,
        "strong_vs_weak_matches": 0,
        "strong_agent_wins": 0,
        "weak_agent_wins": 0,
        "strong_agent_win_rate": 0.0,
        "weak_agent_win_rate": 0.0,
        "depth": 0.0,
        "avg_game_length": 0.0,
        "multi_choice_turns": 0,
        "total_turns": 0,
        "agency": 0.0,
        "covered_cells": 0,
        "board_cell_count": 0,
        "coverage": 0.0,
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
        "parent_metrics": empty_metrics,
        "child_metrics": empty_metrics,
        "trigger_stats": {
            "trigger_count": 0,
            "triggered_matches": 0,
            "total_matches": 0,
            "total_turns": 0,
            "state_changed_by_mechanic_count": 0,
            "trigger_rate_by_match": 0.0,
            "trigger_rate_by_turn": 0.0,
        },
        "derived_scores": {
            "playability": 0.0,
            "balance_gap": 0.0,
            "depth": 0.0,
            "aggregate": 0.0,
        },
        "parent_summary": "Baseline game without the new mechanic.",
    }


def _save_runtime_report(report: dict, game_name: str, mechanic_name: str, iteration: int, revised: bool):
    reports_dir = os.path.join(os.path.dirname(__file__), "runtime_reports")
    os.makedirs(reports_dir, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", mechanic_name).strip("_") or "unknown"
    suffix = "revised" if revised else "initial"
    filename = f"{game_name}_iter{iteration:02d}_{safe_name}_{suffix}.json"
    filepath = os.path.join(reports_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


def _revise(original_mechanic: dict, game_skeleton: str, retrieved: list,
            stage_prompt: str = "", user_prompt: str = "", state_description: str = None,
            banned_names: list = None):
    feedback = original_mechanic.get("_revision_feedback", "Please improve this mechanic.")
    name = original_mechanic.get("mechanic_name", "unknown")

    revision_context = retrieved + [{
        "mechanic_name": f"{name} (PREVIOUS ATTEMPT - FAILED)",
        "mechanic_type": original_mechanic.get("mechanic_type", "other"),
        "description": original_mechanic.get("description", ""),
        "python_code": original_mechanic.get("python_code", ""),
    }]

    skeleton_with_feedback = (
        game_skeleton
        + f"\n\nREVISION FEEDBACK for '{name}':\n{feedback}\n"
        + "Please propose a corrected version of this mechanic that fixes the issue above."
    )

    return propose_mechanic(
        skeleton_with_feedback,
        revision_context,
        stage_prompt=stage_prompt,
        user_prompt=user_prompt,
        state_description=state_description,
        banned_names=banned_names,
        is_revision=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DesignVoyager - autonomous mechanic designer")
    parser.add_argument("--iterations", "-n", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--top-k", "-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--game", "-g", type=str, choices=list(GAME_REGISTRY.keys()), default=DEFAULT_GAME)
    parser.add_argument("--user-prompt", "-u", type=str, default=DEFAULT_USER_PROMPT)
    args = parser.parse_args()
    run_loop(
        n_iterations=args.iterations,
        top_k=args.top_k,
        game_name=args.game,
        user_prompt=args.user_prompt,
    )
