"""
verification_module.py
======================
DesignVoyager - Self-Verification Module

This module is the canonical verifier used by the Prototype CLI and dashboard.
It keeps the legacy verify() API while routing runtime reports through the
structured SelfVerifier schema.
"""

from __future__ import annotations

from typing import Dict, List, Tuple, Union

try:
    from .verification_metrics import (
        build_absolute_metric_dict,
        compute_delta_metrics,
        compute_overall_score,
        compute_relative_score,
        compute_trigger_rate,
        summarize_cross_game_results,
    )
    from .verification_schema import (
        CrossGameVerificationInput,
        CrossGameVerificationOutput,
        CrossGameVerificationRecord,
        IntegrationReport,
        MechanicCandidate,
        PlaytestMetrics,
        TriggerStats,
        VerificationInput,
        VerificationOutput,
    )
except ImportError:
    from verification_metrics import (
        build_absolute_metric_dict,
        compute_delta_metrics,
        compute_overall_score,
        compute_relative_score,
        compute_trigger_rate,
        summarize_cross_game_results,
    )
    from verification_schema import (
        CrossGameVerificationInput,
        CrossGameVerificationOutput,
        CrossGameVerificationRecord,
        IntegrationReport,
        MechanicCandidate,
        PlaytestMetrics,
        TriggerStats,
        VerificationInput,
        VerificationOutput,
    )


ACCEPT = "accept"
REVISE = "revise"
DISCARD = "discard"

MIN_PLAYABILITY = 1.0
MAX_BALANCE_GAP = 0.45
MIN_AGGREGATE = 0.70

ALLOWED_HOOKS = {
    "validate_move",
    "perform_move",
    "game_finished",
    "get_winner",
    "next_player",
}


class SelfVerifier:
    """
    Delta-gated verifier for DesignVoyager.

    It checks integration status, absolute playability/fairness constraints,
    relative improvement over the parent game, and cross-game robustness.
    """

    def __init__(self) -> None:
        self.min_playability = 0.80
        self.max_balance_gap = 0.45
        self.min_decisiveness = 0.20
        self.min_agency = 0.40
        self.require_trigger = True
        self.max_retry_before_discard = 1

        self.robust_min_tested_games = 2
        self.robust_min_pass_rate = 0.70
        self.robust_min_positive_rate = 0.70
        self.robust_min_mean_relative_score = 0.02
        self.robust_max_hard_failure_rate = 0.20
        self.context_min_local_pass_rate = 0.50
        self.repeated_hard_failure_min_count = 2

    def accept_threshold_for_stage(self, stage: int) -> float:
        if stage <= 1:
            return 0.03
        if stage == 2:
            return 0.02
        return 0.01

    def build_feedback(self, failure_modes: List[str]) -> str:
        templates = {
            "schema_failure": (
                "The mechanic output is missing required fields. Please return a complete mechanic with "
                "name, type, description, justification, code, and hook location."
            ),
            "syntax_failure": "The mechanic code is not valid Python. Please fix syntax errors.",
            "hook_failure": (
                "The mechanic is attached to an invalid hook. Please place it in a valid location such as "
                "validate_move, perform_move, game_finished, or get_winner."
            ),
            "instantiation_failure": (
                "The modified game could not be instantiated. Please fix the integration logic or state fields."
            ),
            "dry_run_failure": (
                "The mechanic fails during a short dry run. Please fix state transitions or illegal effects."
            ),
            "low_playability": (
                "The mechanic causes too many invalid or non-terminating matches. Please simplify it or add a guard."
            ),
            "extreme_imbalance": (
                "The mechanic creates too much player advantage. Please reduce asymmetry or add counterplay."
            ),
            "low_decisiveness": (
                "The mechanic creates too many draws or unresolved outcomes. Please make progress more decisive."
            ),
            "low_agency": (
                "The mechanic leaves players with too few meaningful choices. Please add branching decisions."
            ),
            "no_trigger": (
                "The mechanic was not meaningfully triggered during playtesting. Please revise the trigger condition."
            ),
            "no_state_change": (
                "The mechanic triggered but did not materially change state. Please ensure it changes gameplay."
            ),
            "negative_relative_gain": (
                "The mechanic passes basic checks but does not improve the game relative to the parent version."
            ),
        }
        unique_modes = []
        seen = set()
        for mode in failure_modes:
            if mode not in seen:
                seen.add(mode)
                unique_modes.append(mode)
        return " ".join(templates[m] for m in unique_modes if m in templates).strip()

    def check_integration_gate(self, verification_input: VerificationInput) -> Tuple[bool, List[str]]:
        failures: List[str] = []
        mech = verification_input.mechanic
        integration = verification_input.integration

        if not integration.schema_ok:
            failures.append("schema_failure")
        if not integration.syntax_ok:
            failures.append("syntax_failure")
        if mech.hook_location not in ALLOWED_HOOKS or not integration.hook_ok:
            failures.append("hook_failure")
        if not integration.instantiation_ok:
            failures.append("instantiation_failure")
        if not integration.dry_run_ok:
            failures.append("dry_run_failure")
        return len(failures) == 0, failures

    def check_behavioral_gate(self, verification_input: VerificationInput) -> Tuple[bool, List[str], Dict[str, float]]:
        child_abs = build_absolute_metric_dict(verification_input.child_metrics)
        trigger_rate = compute_trigger_rate(verification_input.trigger_stats, by="match")
        failures: List[str] = []

        if child_abs["playability"] < self.min_playability:
            failures.append("low_playability")
        if child_abs["balance_gap"] > self.max_balance_gap:
            failures.append("extreme_imbalance")
        if child_abs["decisiveness"] < self.min_decisiveness:
            failures.append("low_decisiveness")
        if child_abs["agency"] < self.min_agency:
            failures.append("low_agency")
        if self.require_trigger and trigger_rate <= 0:
            failures.append("no_trigger")
        if (
            verification_input.trigger_stats.trigger_count > 0
            and verification_input.trigger_stats.state_changed_by_mechanic_count <= 0
        ):
            failures.append("no_state_change")

        child_abs["trigger_rate"] = trigger_rate
        return len(failures) == 0, failures, child_abs

    def evaluate_relative_gain(self, verification_input: VerificationInput) -> Tuple[float, Dict[str, float], List[str]]:
        delta = compute_delta_metrics(verification_input.parent_metrics, verification_input.child_metrics)
        relative_score = compute_relative_score(
            verification_input.parent_metrics,
            verification_input.child_metrics,
            novelty_score=0.0,
        )

        failures: List[str] = []
        if relative_score < self.accept_threshold_for_stage(verification_input.stage):
            failures.append("negative_relative_gain")

        return relative_score, {
            "delta_playability": delta.delta_playability,
            "delta_balance_gap": delta.delta_balance_gap,
            "delta_depth": delta.delta_depth,
            "delta_decisiveness": delta.delta_decisiveness,
            "delta_agency": delta.delta_agency,
            "delta_coverage": delta.delta_coverage,
        }, failures

    def decide(self, verification_input: VerificationInput) -> VerificationOutput:
        integration_pass, integration_failures = self.check_integration_gate(verification_input)
        if not integration_pass:
            return self._failure_output(verification_input, integration_failures, {}, {})

        behavior_pass, behavior_failures, child_abs = self.check_behavioral_gate(verification_input)
        overall_score = compute_overall_score(verification_input.child_metrics)
        if not behavior_pass:
            return self._failure_output(verification_input, behavior_failures, child_abs, {}, overall_score)

        relative_score, delta_dict, delta_failures = self.evaluate_relative_gain(verification_input)
        if delta_failures:
            return self._failure_output(
                verification_input,
                delta_failures,
                child_abs,
                delta_dict,
                overall_score,
                relative_score,
            )

        return VerificationOutput(
            decision=ACCEPT,
            reason="positive_relative_gain",
            stage=verification_input.stage,
            absolute_metrics=child_abs,
            delta_metrics=delta_dict,
            trigger_stats=_trigger_stats_dict(verification_input.trigger_stats),
            overall_score=overall_score,
            relative_score=relative_score,
            failure_modes=[],
            repair_feedback=None,
            metadata_for_library={
                "accepted_stage": verification_input.stage,
                "failure_mode": None,
                "hook_location": verification_input.mechanic.hook_location,
                "delta_metrics": delta_dict,
                "absolute_metrics": child_abs,
                "parent_summary": verification_input.parent_summary,
            },
        )

    def _failure_output(
        self,
        verification_input: VerificationInput,
        failures: List[str],
        absolute_metrics: Dict[str, float],
        delta_metrics: Dict[str, float],
        overall_score: float = 0.0,
        relative_score: float = 0.0,
    ) -> VerificationOutput:
        decision = DISCARD if verification_input.retry_count >= self.max_retry_before_discard else REVISE
        feedback = self.build_feedback(failures)
        return VerificationOutput(
            decision=decision,
            reason=failures[0] if failures else "verification_failure",
            stage=verification_input.stage,
            absolute_metrics=absolute_metrics,
            delta_metrics=delta_metrics,
            trigger_stats=_trigger_stats_dict(verification_input.trigger_stats),
            overall_score=overall_score,
            relative_score=relative_score,
            failure_modes=failures,
            repair_feedback=feedback,
            metadata_for_library={
                "accepted_stage": None,
                "failure_mode": failures[0] if failures else "verification_failure",
                "hook_location": verification_input.mechanic.hook_location,
                "delta_metrics": delta_metrics,
            },
        )

    def classify_cross_game_robustness(
        self,
        results: Union[List[CrossGameVerificationRecord], CrossGameVerificationInput],
    ) -> CrossGameVerificationOutput:
        records = results.records if isinstance(results, CrossGameVerificationInput) else results
        summary = summarize_cross_game_results(
            records,
            context_min_local_pass_rate=self.context_min_local_pass_rate,
            repeated_hard_failure_min_count=self.repeated_hard_failure_min_count,
        )

        tested_games = summary["tested_games"]
        pass_rate = summary["pass_rate"]
        positive_rate = summary["positive_rate"]
        mean_relative_score = summary["mean_relative_score"]
        hard_failure_rate = summary["hard_failure_rate"]
        compatible_game_types = summary["compatible_game_types"]
        failed_game_types = summary["failed_game_types"]

        is_robust = (
            tested_games >= self.robust_min_tested_games
            and pass_rate >= self.robust_min_pass_rate
            and positive_rate >= self.robust_min_positive_rate
            and mean_relative_score >= self.robust_min_mean_relative_score
            and hard_failure_rate <= self.robust_max_hard_failure_rate
        )
        has_game_type_dependency = bool(set(compatible_game_types)) and bool(
            set(failed_game_types) - set(compatible_game_types)
        )

        if tested_games <= 0:
            robustness_label = "non_robust"
            reason = "no_cross_game_results"
        elif is_robust:
            robustness_label = "robust"
            reason = "mostly_positive_across_tested_games"
        elif has_game_type_dependency:
            robustness_label = "context_sensitive"
            reason = "performance_depends_on_game_type"
        else:
            robustness_label = "non_robust"
            reason = "insufficient_or_unstable_cross_game_performance"

        metadata_for_library = {
            "robustness_label": robustness_label,
            "compatible_game_types": compatible_game_types,
            "failed_game_types": failed_game_types,
            "mean_relative_score": mean_relative_score,
            "pass_rate": pass_rate,
            "positive_rate": positive_rate,
            "tested_games": tested_games,
            "hard_failure_rate": hard_failure_rate,
            "game_type_summaries": summary["game_type_summaries"],
        }
        return CrossGameVerificationOutput(
            robustness_label=robustness_label,
            reason=reason,
            tested_games=tested_games,
            pass_rate=pass_rate,
            positive_rate=positive_rate,
            mean_relative_score=mean_relative_score,
            compatible_game_types=compatible_game_types,
            failed_game_types=failed_game_types,
            metadata_for_library=metadata_for_library,
        )


def _trigger_stats_dict(trigger_stats: TriggerStats) -> Dict[str, float]:
    return {
        "trigger_count": trigger_stats.trigger_count,
        "triggered_matches": trigger_stats.triggered_matches,
        "trigger_rate": compute_trigger_rate(trigger_stats),
        "trigger_rate_by_match": trigger_stats.trigger_rate_by_match(),
        "trigger_rate_by_turn": trigger_stats.trigger_rate_by_turn(),
        "state_changed_by_mechanic_count": trigger_stats.state_changed_by_mechanic_count,
    }


def build_verification_input_from_runtime_report(runtime_report: dict) -> VerificationInput:
    """
    Adapter from Prototype playtest runtime reports to SelfVerifier input.
    """
    mechanic = runtime_report.get("mechanic", {})
    integration = runtime_report.get("integration", {})
    parent_metrics = runtime_report.get("parent_metrics", {})
    child_metrics = runtime_report.get("child_metrics", {})
    trigger_stats = runtime_report.get("trigger_stats", {})

    return VerificationInput(
        stage=int(runtime_report.get("stage", 1) or 1),
        retry_count=int(runtime_report.get("retry_count", 0) or 0),
        mechanic=MechanicCandidate(
            mechanic_name=mechanic.get("mechanic_name", "unknown"),
            mechanic_type=mechanic.get("mechanic_type", "other"),
            description=mechanic.get("description", ""),
            python_code=mechanic.get("python_code", ""),
            justification=mechanic.get("justification", ""),
            hook_location=mechanic.get("hook_location", "perform_move"),
        ),
        integration=IntegrationReport(
            schema_ok=bool(integration.get("schema_ok", False)),
            syntax_ok=bool(integration.get("syntax_ok", False)),
            hook_ok=bool(integration.get("hook_ok", False)),
            instantiation_ok=bool(integration.get("instantiation_ok", False)),
            dry_run_ok=bool(integration.get("dry_run_ok", False)),
            error_message=integration.get("error_message", ""),
        ),
        parent_metrics=_playtest_metrics_from_dict(parent_metrics),
        child_metrics=_playtest_metrics_from_dict(child_metrics),
        trigger_stats=TriggerStats(
            trigger_count=int(trigger_stats.get("trigger_count", 0) or 0),
            triggered_matches=int(trigger_stats.get("triggered_matches", 0) or 0),
            total_matches=int(trigger_stats.get("total_matches", child_metrics.get("total_matches", 0)) or 0),
            total_turns=int(trigger_stats.get("total_turns", child_metrics.get("total_turns", 0)) or 0),
            state_changed_by_mechanic_count=int(
                trigger_stats.get("state_changed_by_mechanic_count", 0) or 0
            ),
        ),
        parent_summary=runtime_report.get("parent_summary", ""),
    )


def _playtest_metrics_from_dict(metrics: dict) -> PlaytestMetrics:
    return PlaytestMetrics(
        total_matches=int(metrics.get("total_matches", 0) or 0),
        completed_matches=int(metrics.get("completed_matches", 0) or 0),
        p1_win_rate=float(metrics.get("p1_win_rate", 0.0) or 0.0),
        p2_win_rate=float(metrics.get("p2_win_rate", 0.0) or 0.0),
        strong_agent_win_rate=float(metrics.get("strong_agent_win_rate", 0.0) or 0.0),
        weak_agent_win_rate=float(metrics.get("weak_agent_win_rate", 0.0) or 0.0),
        draw_rate=float(metrics.get("draw_rate", 0.0) or 0.0),
        avg_game_length=float(metrics.get("avg_game_length", 0.0) or 0.0),
        avg_legal_actions=float(metrics.get("avg_legal_actions", 0.0) or 0.0),
        multi_choice_turns=int(metrics.get("multi_choice_turns", 0) or 0),
        total_turns=int(metrics.get("total_turns", 0) or 0),
        covered_cells=int(metrics.get("covered_cells", 0) or 0),
        board_cell_count=int(metrics.get("board_cell_count", 0) or 0),
    )


def verify_runtime_report(runtime_report: dict) -> VerificationOutput:
    verification_input = build_verification_input_from_runtime_report(runtime_report)
    return SelfVerifier().decide(verification_input)


def build_cross_game_record_from_runtime_report(
    runtime_report: dict,
    game_name: str = "",
    game_type: str = "",
) -> CrossGameVerificationRecord:
    mechanic = runtime_report.get("mechanic", {})
    inferred_name = game_name or runtime_report.get("game_name") or mechanic.get("mechanic_name", "unknown_game")
    inferred_type = game_type or runtime_report.get("game_type") or "unknown"
    return CrossGameVerificationRecord(
        game_name=inferred_name,
        game_type=inferred_type,
        verification_output=verify_runtime_report(runtime_report),
    )


def classify_cross_game_runtime_reports(
    runtime_reports: List[dict],
    game_type_by_index: List[str] | None = None,
) -> CrossGameVerificationOutput:
    records = []
    for index, report in enumerate(runtime_reports):
        game_type = ""
        if game_type_by_index and index < len(game_type_by_index):
            game_type = game_type_by_index[index]
        records.append(
            build_cross_game_record_from_runtime_report(
                report,
                game_name=report.get("game_name", f"game_{index + 1}"),
                game_type=game_type,
            )
        )
    return SelfVerifier().classify_cross_game_robustness(records)


def verify(mechanic: dict, scores: dict, already_revised: bool = False) -> tuple:
    """
    Backward-compatible verifier used by main.py and the dashboard.

    If a playtest runtime report is attached to the mechanic, the structured
    SelfVerifier path is used. Otherwise this falls back to the legacy compact
    score gate so older tests/utilities keep working.
    """
    name = mechanic.get("mechanic_name", "unknown")
    runtime_report = mechanic.get("_self_verification_report")
    print(f"[Verify] Evaluating '{name}'...")

    if runtime_report:
        output = verify_runtime_report(runtime_report)
        mechanic["_verification_output"] = output.to_dict()
        if output.decision == ACCEPT:
            print(f"  [Verify] ACCEPT - relative={output.relative_score:.3f}")
            return ACCEPT, "Mechanic accepted."
        if output.decision == REVISE:
            print(f"  [Verify] REVISE - {output.reason}")
            return REVISE, output.repair_feedback or output.reason
        print(f"  [Verify] DISCARD - {output.reason}")
        return DISCARD, output.repair_feedback or output.reason

    return _legacy_verify_scores(scores, already_revised)


def _legacy_verify_scores(scores: dict, already_revised: bool = False) -> tuple:
    playability = scores.get("playability", 0)
    balance_gap = scores.get("balance_gap", 1)
    aggregate = scores.get("aggregate", 0)

    if playability < MIN_PLAYABILITY:
        feedback = (
            f"The mechanic caused too many games to not finish properly "
            f"(playability={playability:.0%}, minimum is {MIN_PLAYABILITY:.0%}). "
            "The mechanic may be causing infinite loops, crashes, or removing all valid moves."
        )
        print(f"  [Verify] DISCARD - failed playability gate ({playability:.0%})")
        return DISCARD, feedback

    if balance_gap > MAX_BALANCE_GAP:
        feedback = (
            f"The mechanic creates a large first-player advantage "
            f"(balance_gap={balance_gap:.0%}, maximum is {MAX_BALANCE_GAP:.0%})."
        )
        if already_revised:
            print("  [Verify] DISCARD - extreme imbalance after revision")
            return DISCARD, feedback
        print("  [Verify] REVISE - extreme imbalance")
        return REVISE, feedback

    if aggregate < MIN_AGGREGATE:
        feedback = (
            f"The mechanic's overall score is too low (aggregate={aggregate:.2f}, "
            f"minimum is {MIN_AGGREGATE:.2f})."
        )
        if already_revised:
            print("  [Verify] DISCARD - low aggregate score after revision")
            return DISCARD, feedback
        print("  [Verify] REVISE - low aggregate score")
        return REVISE, feedback

    print(f"  [Verify] ACCEPT - aggregate={aggregate:.2f}")
    return ACCEPT, "Mechanic accepted."
