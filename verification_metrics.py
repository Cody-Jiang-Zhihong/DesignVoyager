from __future__ import annotations

from typing import Any, Dict, List

from verification_schema import (
    CrossGameVerificationRecord,
    DeltaMetrics,
    PlaytestMetrics,
    TriggerStats,
    VerificationOutput,
)


HARD_CONSTRAINT_FAILURE_MODES = {
    "schema_failure",
    "syntax_failure",
    "hook_failure",
    "instantiation_failure",
    "dry_run_failure",
    "low_playability",
    "extreme_imbalance",
    "low_decisiveness",
    "low_agency",
    "no_trigger",
    "no_state_change",
}


def compute_playability(metrics: PlaytestMetrics) -> float:
    if metrics.total_matches <= 0:
        return 0.0
    return metrics.completed_matches / metrics.total_matches


def compute_balance_gap(metrics: PlaytestMetrics) -> float:
    return abs(metrics.p1_win_rate - metrics.p2_win_rate)


def compute_balance_score(metrics: PlaytestMetrics) -> float:
    gap = compute_balance_gap(metrics)
    return max(0.0, min(1.0, 1.0 - gap))


def compute_depth(metrics: PlaytestMetrics) -> float:
    """
    Strategic-depth proxy from the proposal:
    stronger agent should outperform weaker agent if decisions matter.
    """
    raw = metrics.strong_agent_win_rate - metrics.weak_agent_win_rate
    return max(0.0, min(1.0, raw))


def compute_decisiveness(metrics: PlaytestMetrics) -> float:
    """
    Fraction of games that do NOT end in a draw.
    """
    return max(0.0, min(1.0, 1.0 - metrics.draw_rate))


def compute_agency(metrics: PlaytestMetrics) -> float:
    """
    Fraction of turns where the player had more than one legal move.
    This matches the simple GAVEL-inspired interpretation.
    """
    if metrics.total_turns <= 0:
        return 0.0
    return metrics.multi_choice_turns / metrics.total_turns


def compute_coverage(metrics: PlaytestMetrics) -> float:
    """
    Fraction of board cells that were used at least once.
    Optional diagnostic metric.
    """
    if metrics.board_cell_count <= 0:
        return 0.0
    return metrics.covered_cells / metrics.board_cell_count


def compute_trigger_rate(trigger_stats: TriggerStats, by: str = "match") -> float:
    if by == "turn":
        return trigger_stats.trigger_rate_by_turn()
    return trigger_stats.trigger_rate_by_match()


def build_absolute_metric_dict(metrics: PlaytestMetrics) -> Dict[str, float]:
    return {
        "playability": compute_playability(metrics),
        "balance_gap": compute_balance_gap(metrics),
        "balance_score": compute_balance_score(metrics),
        "depth": compute_depth(metrics),
        "decisiveness": compute_decisiveness(metrics),
        "agency": compute_agency(metrics),
        "coverage": compute_coverage(metrics),
        "avg_game_length": metrics.avg_game_length,
    }


def compute_delta_metrics(parent: PlaytestMetrics, child: PlaytestMetrics) -> DeltaMetrics:
    parent_abs = build_absolute_metric_dict(parent)
    child_abs = build_absolute_metric_dict(child)

    return DeltaMetrics(
        delta_playability=child_abs["playability"] - parent_abs["playability"],
        delta_balance_gap=child_abs["balance_gap"] - parent_abs["balance_gap"],
        delta_depth=child_abs["depth"] - parent_abs["depth"],
        delta_decisiveness=child_abs["decisiveness"] - parent_abs["decisiveness"],
        delta_agency=child_abs["agency"] - parent_abs["agency"],
        delta_coverage=child_abs["coverage"] - parent_abs["coverage"],
    )


def compute_overall_score(child: PlaytestMetrics) -> float:
    """
    Overall absolute quality of the child game.
    Hard constraints should be checked separately before relying on this score.
    """
    abs_metrics = build_absolute_metric_dict(child)

    return (
        0.45 * abs_metrics["playability"]
        + 0.25 * abs_metrics["balance_score"]
        + 0.20 * abs_metrics["depth"]
        + 0.10 * abs_metrics["decisiveness"]
    )


def compute_relative_score(parent: PlaytestMetrics, child: PlaytestMetrics, novelty_score: float = 0.0) -> float:
    """
    Measures whether the new mechanic actually improved the parent game,
    rather than only checking whether the child game looks decent in isolation.
    """
    d = compute_delta_metrics(parent, child)
    return (
        0.45 * d.delta_depth
        - 0.20 * d.delta_balance_gap
        + 0.15 * d.delta_playability
        + 0.10 * d.delta_agency
        + 0.10 * d.delta_decisiveness
        + 0.10 * novelty_score
    )


def is_hard_constraint_failure(output: VerificationOutput) -> bool:
    return any(mode in HARD_CONSTRAINT_FAILURE_MODES for mode in output.failure_modes)


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def summarize_cross_game_results(
    records: List[CrossGameVerificationRecord],
    context_min_local_pass_rate: float = 0.50,
    repeated_hard_failure_min_count: int = 2,
) -> Dict[str, Any]:
    """
    Summarize several single-game verification outputs for robustness checks.
    Classification remains in SelfVerifier so thresholds are easy to tune there.
    """
    tested_games = len(records)
    if tested_games <= 0:
        return {
            "tested_games": 0,
            "pass_rate": 0.0,
            "positive_rate": 0.0,
            "mean_relative_score": 0.0,
            "hard_failure_rate": 0.0,
            "compatible_game_types": [],
            "failed_game_types": [],
            "game_type_summaries": {},
        }

    relative_scores = [record.verification_output.relative_score for record in records]
    hard_failure_flags = [
        is_hard_constraint_failure(record.verification_output)
        for record in records
    ]
    pass_flags = [
        record.verification_output.decision == "accept" and not hard_failure
        for record, hard_failure in zip(records, hard_failure_flags)
    ]
    positive_flags = [
        record.verification_output.relative_score > 0 and not hard_failure
        for record, hard_failure in zip(records, hard_failure_flags)
    ]

    by_game_type: Dict[str, List[CrossGameVerificationRecord]] = {}
    for record in records:
        by_game_type.setdefault(record.game_type, []).append(record)

    game_type_summaries: Dict[str, Dict[str, Any]] = {}
    compatible_game_types: List[str] = []
    failed_game_types: List[str] = []

    for game_type, game_records in by_game_type.items():
        local_count = len(game_records)
        local_scores = [
            record.verification_output.relative_score
            for record in game_records
        ]
        local_hard_failures = sum(
            1 for record in game_records
            if is_hard_constraint_failure(record.verification_output)
        )
        local_pass_count = sum(
            1 for record in game_records
            if (
                record.verification_output.decision == "accept"
                and not is_hard_constraint_failure(record.verification_output)
            )
        )
        local_pass_rate = local_pass_count / local_count if local_count > 0 else 0.0
        local_mean_relative_score = _mean(local_scores)
        repeated_hard_failures = local_hard_failures >= repeated_hard_failure_min_count

        is_positive_game_type = (
            local_pass_rate >= context_min_local_pass_rate
            and local_mean_relative_score > 0
            and not repeated_hard_failures
        )
        is_failed_or_risky_game_type = (
            local_pass_rate < context_min_local_pass_rate
            or local_mean_relative_score <= 0
            or repeated_hard_failures
        )

        if is_positive_game_type:
            compatible_game_types.append(game_type)
        if is_failed_or_risky_game_type:
            failed_game_types.append(game_type)

        game_type_summaries[game_type] = {
            "tested_games": local_count,
            "pass_rate": local_pass_rate,
            "mean_relative_score": local_mean_relative_score,
            "hard_failure_count": local_hard_failures,
            "repeated_hard_failures": repeated_hard_failures,
            "is_positive_game_type": is_positive_game_type,
            "is_failed_or_risky_game_type": is_failed_or_risky_game_type,
        }

    return {
        "tested_games": tested_games,
        "pass_rate": sum(pass_flags) / tested_games,
        "positive_rate": sum(positive_flags) / tested_games,
        "mean_relative_score": _mean(relative_scores),
        "hard_failure_rate": sum(hard_failure_flags) / tested_games,
        "compatible_game_types": sorted(compatible_game_types),
        "failed_game_types": sorted(failed_game_types),
        "game_type_summaries": game_type_summaries,
    }
