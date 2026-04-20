"""
pipeline_runner.py
==================
Web-adapted pipeline loop for Prototype.

Runs the current Prototype pipeline and emits structured events that the
dashboard consumes over WebSocket.
"""

import contextlib
import io
import json
import os
import queue
import threading

from base_game import BaseGame
from card_game import CardGame
from compile_check import compile_check, load_mechanic_fn
from curriculum import Curriculum
import discarded_library
from mechanic_library import MechanicLibrary
from playtest_module import get_last_runtime_report, playtest, run_single_game_recorded
from proposal_module import MODEL
from proposal_module import propose_mechanic
from verification_module import ACCEPT, DISCARD, REVISE, verify

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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

LIBRARY_CARDS_FILE = os.path.join(PROJECT_DIR, "library_cards.json")
MAX_REPLAY_ATTEMPTS = 5


def _save_library_card(card: dict):
    cards = []
    try:
        with open(LIBRARY_CARDS_FILE, "r", encoding="utf-8") as f:
            cards = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        cards = []
    cards.append(card)
    try:
        with open(LIBRARY_CARDS_FILE, "w", encoding="utf-8") as f:
            json.dump(cards, f, indent=2)
    except Exception:
        pass


class EventEmitter:
    def __init__(self, event_queue: queue.Queue):
        self._queue = event_queue

    def emit(self, event_type: str, data: dict = None):
        self._queue.put({"type": event_type, "data": data or {}})


@contextlib.contextmanager
def _suppress_stdout():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def run_web_pipeline(emitter: EventEmitter, game_name: str,
                     n_iterations: int, top_k: int,
                     stop_event: threading.Event = None,
                     user_prompt: str = ""):
    if game_name not in GAME_REGISTRY:
        emitter.emit("error", {"message": f"Unknown game: {game_name}"})
        return

    game_class, library_file, discarded_file = GAME_REGISTRY[game_name]
    dummy_game = game_class.create()
    skeleton = dummy_game.get_skeleton_description()
    state_desc = dummy_game.get_state_description()
    dummy_state = dummy_game.get_dummy_state()

    with _suppress_stdout():
        library = MechanicLibrary(filepath=library_file)
    curriculum = Curriculum()
    banned_names = discarded_library.load(discarded_file)
    tried_this_run = set()

    emitter.emit("welcome", {
        "game_name": game_name,
        "game_class": game_class.__name__,
        "model_name": MODEL,
        "iterations": n_iterations,
        "top_k": top_k,
        "library_size": library.size(),
        "library_mechanics": [m["mechanic_name"] for m in library.mechanics],
        "curriculum_stage": curriculum.stage_name(),
        "curriculum_progress": curriculum.progress_str(),
        "banned_count": len(banned_names),
        "user_prompt": user_prompt,
    })

    accepted_count = 0
    discarded_count = 0

    for iteration in range(1, n_iterations + 1):
        if stop_event and stop_event.is_set():
            emitter.emit("error", {"message": "Run stopped by user."})
            break

        emitter.emit("iteration_start", {
            "iteration": iteration,
            "total": n_iterations,
            "stage_name": curriculum.stage_name(),
        })

        retrieval_query = f"{skeleton} {curriculum.stage_name()} {user_prompt}".strip()
        with _suppress_stdout():
            retrieved = library.retrieve(k=top_k, query=retrieval_query)
        emitter.emit("retrieve", {
            "mechanic_names": [m["mechanic_name"] for m in retrieved],
            "count": len(retrieved),
        })

        all_banned = list(set(banned_names) | tried_this_run)
        emitter.emit("propose_start", {"context_count": len(retrieved)})
        with _suppress_stdout():
            mechanic = propose_mechanic(
                skeleton,
                retrieved,
                stage_prompt=curriculum.stage_prompt(),
                user_prompt=user_prompt,
                state_description=state_desc,
                banned_names=all_banned,
            )

        if mechanic is None:
            emitter.emit("propose_result", {"failed": True})
            emitter.emit("verify_result", {
                "decision": DISCARD,
                "feedback": "Proposal failed completely.",
            })
            curriculum.on_discard()
            discarded_count += 1
            continue

        tried_this_run.add(mechanic.get("mechanic_name", ""))
        emitter.emit("propose_result", {
            "failed": False,
            "mechanic_name": mechanic.get("mechanic_name", "unknown"),
            "mechanic_type": mechanic.get("mechanic_type", ""),
            "description": mechanic.get("description", ""),
            "python_code": mechanic.get("python_code", ""),
        })

        pre_playtest_revised = False
        similarity_outcome = _check_novelty_gate(mechanic, library, already_revised=False)
        if similarity_outcome == REVISE:
            emitter.emit("verify_result", {
                "decision": REVISE,
                "feedback": mechanic.get("_revision_feedback", ""),
                "scores": {},
            })

            feedback = mechanic.get("_revision_feedback", "Please propose a more distinct mechanic.")
            revision_ctx = retrieved + [{
                "mechanic_name": f"{mechanic['mechanic_name']} (PREVIOUS ATTEMPT - TOO SIMILAR)",
                "mechanic_type": mechanic.get("mechanic_type", "other"),
                "description": mechanic.get("description", ""),
                "python_code": mechanic.get("python_code", ""),
            }]
            revised_skeleton = (
                skeleton
                + f"\n\nNOVELTY GATE FEEDBACK for '{mechanic['mechanic_name']}':\n{feedback}\n"
                + "Please propose a more distinct mechanic before playtesting."
            )

            emitter.emit("revision_start", {
                "mechanic_name": mechanic.get("mechanic_name", "unknown"),
            })
            with _suppress_stdout():
                revised = propose_mechanic(
                    revised_skeleton,
                    revision_ctx,
                    stage_prompt=curriculum.stage_prompt(),
                    user_prompt=user_prompt,
                    state_description=state_desc,
                    banned_names=all_banned,
                    is_revision=True,
                )

            if revised is None:
                emitter.emit("revision_result", {"failed": True})
                emitter.emit("verify_result", {
                    "decision": DISCARD,
                    "feedback": "Revision failed.",
                })
                discarded_library.save_name(mechanic.get("mechanic_name", ""), discarded_file)
                banned_names.append(mechanic.get("mechanic_name", ""))
                curriculum.on_discard()
                discarded_count += 1
                continue

            tried_this_run.add(revised.get("mechanic_name", ""))
            emitter.emit("revision_result", {
                "failed": False,
                "mechanic_name": revised.get("mechanic_name", "unknown"),
                "mechanic_type": revised.get("mechanic_type", ""),
                "description": revised.get("description", ""),
                "python_code": revised.get("python_code", ""),
            })
            if _check_novelty_gate(revised, library, already_revised=True) == DISCARD:
                emitter.emit("verify_result", {
                    "decision": DISCARD,
                    "feedback": revised.get("_revision_feedback", ""),
                    "scores": {},
                })
                discarded_library.save_name(revised.get("mechanic_name", ""), discarded_file)
                banned_names.append(revised.get("mechanic_name", ""))
                curriculum.on_discard()
                discarded_count += 1
                continue
            mechanic = revised
            pre_playtest_revised = True

        decision, scores, replay_data = _compile_playtest_verify(
            emitter, mechanic, already_revised=pre_playtest_revised,
            game_class=game_class, game_name=game_name,
            dummy_state=dummy_state,
        )

        if decision == REVISE:
            emitter.emit("verify_result", {
                "decision": REVISE,
                "feedback": mechanic.get("_revision_feedback", ""),
                "scores": scores,
            })

            feedback = mechanic.get("_revision_feedback", "Please improve this mechanic.")
            revision_ctx = retrieved + [{
                "mechanic_name": f"{mechanic['mechanic_name']} (PREVIOUS ATTEMPT - FAILED)",
                "mechanic_type": mechanic.get("mechanic_type", "other"),
                "description": mechanic.get("description", ""),
                "python_code": mechanic.get("python_code", ""),
            }]
            revised_skeleton = (
                skeleton
                + f"\n\nREVISION FEEDBACK for '{mechanic['mechanic_name']}':\n{feedback}\n"
                + "Please propose a corrected version that fixes the issue described above."
            )

            emitter.emit("revision_start", {
                "mechanic_name": mechanic.get("mechanic_name", "unknown"),
            })
            with _suppress_stdout():
                revised = propose_mechanic(
                    revised_skeleton,
                    revision_ctx,
                    stage_prompt=curriculum.stage_prompt(),
                    user_prompt=user_prompt,
                    state_description=state_desc,
                    banned_names=all_banned,
                    is_revision=True,
                )

            if revised is None:
                emitter.emit("revision_result", {"failed": True})
                emitter.emit("verify_result", {
                    "decision": DISCARD,
                    "feedback": "Revision failed.",
                })
                discarded_library.save_name(mechanic.get("mechanic_name", ""), discarded_file)
                banned_names.append(mechanic.get("mechanic_name", ""))
                curriculum.on_discard()
                discarded_count += 1
                continue

            tried_this_run.add(revised.get("mechanic_name", ""))
            emitter.emit("revision_result", {
                "failed": False,
                "mechanic_name": revised.get("mechanic_name", "unknown"),
                "mechanic_type": revised.get("mechanic_type", ""),
                "description": revised.get("description", ""),
                "python_code": revised.get("python_code", ""),
            })
            mechanic = revised
            decision, scores, replay_data = _compile_playtest_verify(
                emitter, mechanic, already_revised=True,
                game_class=game_class, game_name=game_name,
                dummy_state=dummy_state,
            )

        emitter.emit("verify_result", {
            "decision": decision,
            "feedback": mechanic.get("_revision_feedback", ""),
            "scores": scores,
        })

        if decision == ACCEPT:
            advanced = curriculum.on_accept()
            accepted_count += 1
            added = False
            with _suppress_stdout():
                added = library.add(mechanic, scores, iteration=iteration)
            if added:
                card = {
                    "game_type": game_name,
                    "mechanic_name": mechanic.get("mechanic_name", ""),
                    "description": mechanic.get("description", ""),
                    "scores": scores,
                    "replay": replay_data,
                    "iteration": iteration,
                    "runtime_report": get_last_runtime_report(),
                }
                if replay_data:
                    _save_library_card(card)
                emitter.emit("mechanic_accepted", card)
            else:
                emitter.emit("library_skip", {
                    "mechanic_name": mechanic.get("mechanic_name", ""),
                    "reason": "duplicate_library_entry",
                })
            if advanced:
                emitter.emit("curriculum_advance", {
                    "new_stage_name": curriculum.stage_name(),
                })
        else:
            discarded_library.save_name(mechanic.get("mechanic_name", ""), discarded_file)
            banned_names.append(mechanic.get("mechanic_name", ""))
            curriculum.on_discard()
            discarded_count += 1

    emitter.emit("run_complete", {
        "accepted_count": accepted_count,
        "discarded_count": discarded_count,
        "library_size": library.size(),
        "mechanic_names": [m["mechanic_name"] for m in library.mechanics],
    })


def _compile_playtest_verify(emitter, mechanic, already_revised,
                             game_class, game_name, dummy_state):
    with _suppress_stdout():
        ok, error = compile_check(mechanic, dummy_state=dummy_state)

    emitter.emit("compile_result", {
        "passed": ok,
        "error": error if not ok else None,
    })

    if not ok:
        if already_revised:
            return DISCARD, {}, None
        mechanic["_revision_feedback"] = f"The code crashed: {error}. Please rewrite to fix this."
        return REVISE, {}, None

    replay_data = None
    try:
        mechanic_fn = load_mechanic_fn(mechanic.get("python_code", ""))
        replay = _record_best_replay(
            mechanic_fn=mechanic_fn,
            game_class=game_class,
        )
        replay_data = {
            "game_type": game_name,
            "mechanic_name": mechanic.get("mechanic_name", ""),
            "mechanic_description": mechanic.get("description", ""),
            "initial_state": replay["initial_state"],
            "moves": replay["moves"],
            "winner": replay["winner"],
            "total_turns": replay["turns"],
            "trigger_count": replay.get("trigger_count", 0),
            "state_changed_by_mechanic_count": replay.get("state_changed_by_mechanic_count", 0),
        }
        emitter.emit("replay_data", replay_data)
    except Exception:
        replay_data = None

    emitter.emit("playtest_start", {
        "mechanic_name": mechanic.get("mechanic_name", "unknown"),
    })
    with _suppress_stdout():
        scores = playtest(mechanic, game_class=game_class)
    emitter.emit("playtest_result", {"scores": scores})

    with _suppress_stdout():
        decision, feedback = verify(mechanic, scores, already_revised)
    if decision == REVISE:
        mechanic["_revision_feedback"] = feedback
    return decision, scores, replay_data


def _check_novelty_gate(mechanic: dict, library: MechanicLibrary, already_revised: bool) -> str | None:
    similar_entry, similarity = library.find_most_similar(mechanic)
    if similar_entry is None:
        return None

    mechanic["_revision_feedback"] = (
        f"This mechanic is too similar to accepted library mechanic "
        f"'{similar_entry['mechanic_name']}' (similarity {similarity:.3f}). "
        "Please propose a functionally distinct mechanic before playtesting."
    )
    return DISCARD if already_revised else REVISE


def _record_best_replay(mechanic_fn, game_class):
    best_replay = None
    best_score = -1

    for _ in range(MAX_REPLAY_ATTEMPTS):
        replay = run_single_game_recorded(
            mechanic_fn=mechanic_fn,
            game_class=game_class,
        )
        score = _score_replay_for_tutorial(replay)
        if score > best_score:
            best_replay = replay
            best_score = score
        if score >= 100:
            return replay

    return best_replay


def _score_replay_for_tutorial(replay: dict) -> int:
    moves = replay.get("moves", [])
    if not moves:
        return 0

    # Strongest signal: mechanic visibly changed board state on a turn.
    for move in moves:
        before = move.get("state_before_mechanics") or {}
        after = move.get("state_after") or {}
        before_board = before.get("board")
        after_board = after.get("board")
        if before_board and after_board and before_board != after_board:
            return 100

    # Extra-turn signal: same player moves twice in a row.
    for i in range(len(moves) - 1):
        if moves[i].get("player") == moves[i + 1].get("player"):
            return 80

    # Custom-state change still gives the tutorial something to explain.
    for i in range(1, len(moves)):
        prev_state = moves[i - 1].get("state_after") or {}
        curr_state = moves[i].get("state_after") or {}
        if prev_state.get("custom_state") != curr_state.get("custom_state"):
            return 60

    # Fallback: prefer replays where the mechanic at least triggered internally.
    trigger_count = replay.get("trigger_count", 0)
    state_changed = replay.get("state_changed_by_mechanic_count", 0)
    if state_changed > 0:
        return 50 + state_changed
    if trigger_count > 0:
        return 10 + trigger_count
    return 1
