"""
cross_game_robustness_pass.py
=============================

Run accepted mechanics across board and card domains, classify robustness, and
write the result back to the library metadata.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

from base_game import BaseGame
from card_game import CardGame
from main import _build_failure_report, _build_integration_report
from playtest_module import get_last_runtime_report, playtest
from verification_module import (
    SelfVerifier,
    build_cross_game_record_from_runtime_report,
    verify_runtime_report,
)


PROJECT_DIR = Path(__file__).resolve().parent
REPO_DIR = PROJECT_DIR.parent
BOARD_LIBRARY = PROJECT_DIR / "library.json"
CARD_LIBRARY = PROJECT_DIR / "library_card.json"
ROOT_LIBRARY = REPO_DIR / "library.json"
REPORT_JSON = PROJECT_DIR / "cross_game_robustness_results.json"
REPORT_MD = PROJECT_DIR / "cross_game_robustness_report.md"

GAME_TARGETS = {
    "board": BaseGame,
    "card": CardGame,
}


def load_json(path: Path) -> list:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _identity(entry: dict) -> Tuple[str, str]:
    return entry.get("mechanic_name", ""), entry.get("python_code", "")


def collect_candidates(limit: int) -> List[dict]:
    candidates = []
    for path, game_type in [(BOARD_LIBRARY, "board"), (CARD_LIBRARY, "card")]:
        for index, entry in enumerate(load_json(path)):
            if entry.get("verification", {}).get("decision", "accept") != "accept":
                continue
            candidate = copy.deepcopy(entry)
            candidate["_source_path"] = str(path)
            candidate["_source_index"] = index
            candidate["_original_game_type"] = entry.get("game_type") or game_type
            candidates.append(candidate)

    candidates.sort(key=lambda m: m.get("scores", {}).get("aggregate", 0.0), reverse=True)
    return candidates[:limit] if limit > 0 else candidates


def _integration_failure_report(mechanic: dict, game_type: str, game_class) -> dict:
    integration = _build_integration_report(
        mechanic,
        game_class=game_class,
        dummy_state=game_class.create().get_dummy_state(),
    )
    report = _build_failure_report(mechanic, integration, stage=1, retry_count=1)
    report["game_type"] = game_type
    report["game_name"] = game_type
    return report


def run_mechanic_on_game(mechanic: dict, game_type: str) -> dict:
    game_class = GAME_TARGETS[game_type]
    integration = _build_integration_report(
        mechanic,
        game_class=game_class,
        dummy_state=game_class.create().get_dummy_state(),
    )
    if not all(
        [
            integration.get("schema_ok"),
            integration.get("syntax_ok"),
            integration.get("hook_ok"),
            integration.get("instantiation_ok"),
            integration.get("dry_run_ok"),
        ]
    ):
        return _integration_failure_report(mechanic, game_type, game_class)

    playtest(
        mechanic,
        game_class=game_class,
        integration=integration,
        stage=1,
        retry_count=1,
    )
    report = get_last_runtime_report()
    report["game_type"] = game_type
    report["game_name"] = game_type
    return report


def classify_mechanic(mechanic: dict, game_types: List[str]) -> dict:
    reports = []
    records = []
    for game_type in game_types:
        report = run_mechanic_on_game(mechanic, game_type)
        reports.append(report)
        records.append(
            build_cross_game_record_from_runtime_report(
                report,
                game_name=game_type,
                game_type=game_type,
            )
        )

    verifier = SelfVerifier()
    robustness = verifier.classify_cross_game_robustness(records)

    per_game = []
    for report, record in zip(reports, records):
        output = record.verification_output
        per_game.append(
            {
                "game_type": record.game_type,
                "decision": output.decision,
                "reason": output.reason,
                "relative_score": output.relative_score,
                "overall_score": output.overall_score,
                "failure_modes": output.failure_modes,
                "absolute_metrics": output.absolute_metrics,
                "delta_metrics": output.delta_metrics,
                "trigger_stats": output.trigger_stats,
                "integration": report.get("integration", {}),
            }
        )

    metadata = robustness.metadata_for_library
    return {
        "mechanic_name": mechanic.get("mechanic_name", ""),
        "original_game_type": mechanic.get("_original_game_type", ""),
        "source_path": mechanic.get("_source_path", ""),
        "source_index": mechanic.get("_source_index"),
        "robustness": {
            "label": metadata.get("robustness_label", robustness.robustness_label),
            "reason": robustness.reason,
            "compatible_game_types": metadata.get("compatible_game_types", []),
            "failed_game_types": metadata.get("failed_game_types", []),
            "tested_games": metadata.get("tested_games", 0),
            "pass_rate": metadata.get("pass_rate", 0.0),
            "positive_rate": metadata.get("positive_rate", 0.0),
            "mean_relative_score": metadata.get("mean_relative_score", 0.0),
            "hard_failure_rate": metadata.get("hard_failure_rate", 0.0),
            "game_type_summaries": metadata.get("game_type_summaries", {}),
        },
        "per_game_results": per_game,
    }


def update_libraries(results: List[dict]) -> None:
    loaded: Dict[str, list] = {}
    for path in [BOARD_LIBRARY, CARD_LIBRARY, ROOT_LIBRARY]:
        if path.exists():
            loaded[str(path)] = load_json(path)

    result_by_identity = {}
    result_by_name = {}
    for result in results:
        source_entries = loaded.get(result["source_path"], [])
        source_index = result.get("source_index")
        if isinstance(source_index, int) and 0 <= source_index < len(source_entries):
            result_by_identity[_identity(source_entries[source_index])] = result
        if result.get("mechanic_name"):
            result_by_name[result["mechanic_name"]] = result

    for path_str, entries in loaded.items():
        changed = False
        for entry in entries:
            result = result_by_identity.get(_identity(entry))
            if result is None:
                result = result_by_name.get(entry.get("mechanic_name", ""))
            if result is None:
                continue
            entry["robustness"] = result["robustness"]
            entry["robustness"]["per_game_results"] = result["per_game_results"]
            changed = True
        if changed:
            save_json(Path(path_str), entries)


def write_reports(results: List[dict]) -> None:
    save_json(REPORT_JSON, results)

    counts: Dict[str, int] = {}
    for result in results:
        label = result["robustness"]["label"]
        counts[label] = counts.get(label, 0) + 1

    lines = [
        "# Cross-Game Robustness Pass",
        "",
        f"Tested mechanics: {len(results)}",
        "",
        "## Summary",
        "",
    ]
    for label in ["robust", "context_sensitive", "non_robust", "untested"]:
        if label in counts:
            lines.append(f"- {label}: {counts[label]}")

    lines.extend(["", "## Results", ""])
    for result in results:
        robustness = result["robustness"]
        lines.append(
            f"### {result['mechanic_name']} - {robustness['label']}"
        )
        lines.append(
            f"- compatible: {', '.join(robustness['compatible_game_types']) or 'none'}"
        )
        lines.append(
            f"- failed: {', '.join(robustness['failed_game_types']) or 'none'}"
        )
        lines.append(
            f"- pass_rate: {robustness['pass_rate']:.3f}; "
            f"positive_rate: {robustness['positive_rate']:.3f}; "
            f"mean_relative_score: {robustness['mean_relative_score']:.3f}"
        )
        for per_game in result["per_game_results"]:
            lines.append(
                f"- {per_game['game_type']}: {per_game['decision']} / "
                f"{per_game['reason']} / relative={per_game['relative_score']:.3f}"
            )
        lines.append("")

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run cross-game robustness verification for accepted mechanics.")
    parser.add_argument("--limit", type=int, default=10, help="Number of top aggregate accepted mechanics to test. 0 means all.")
    parser.add_argument("--games", nargs="+", choices=sorted(GAME_TARGETS), default=["board", "card"])
    args = parser.parse_args()

    candidates = collect_candidates(args.limit)
    results = []
    for index, mechanic in enumerate(candidates, start=1):
        print(f"[{index}/{len(candidates)}] {mechanic.get('mechanic_name')} -> {', '.join(args.games)}")
        result = classify_mechanic(mechanic, args.games)
        print(f"  robustness={result['robustness']['label']}")
        results.append(result)

    update_libraries(results)
    write_reports(results)
    print(f"Wrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")


if __name__ == "__main__":
    main()
