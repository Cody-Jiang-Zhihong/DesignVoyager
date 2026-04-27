import unittest

from self_verification import SelfVerifier
from verification_schema import (
    CrossGameVerificationRecord,
    IntegrationReport,
    MechanicCandidate,
    PlaytestMetrics,
    TriggerStats,
    VerificationInput,
    VerificationOutput,
)


def make_output(decision, relative_score, failure_modes=None, stage=1):
    return VerificationOutput(
        decision=decision,
        reason="sample",
        stage=stage,
        absolute_metrics={},
        delta_metrics={},
        trigger_stats={},
        overall_score=0.8 if decision == "accept" else 0.3,
        relative_score=relative_score,
        failure_modes=failure_modes or [],
        repair_feedback=None,
        metadata_for_library={},
    )


def make_record(game_name, game_type, decision, relative_score, failure_modes=None):
    return CrossGameVerificationRecord(
        game_name=game_name,
        game_type=game_type,
        verification_output=make_output(decision, relative_score, failure_modes),
    )


class CrossGameVerificationTests(unittest.TestCase):
    def test_classifies_robust_when_most_games_accept(self):
        verifier = SelfVerifier()
        records = [
            make_record("boardwalk", "board", "accept", 0.04),
            make_record("cardduel", "card", "accept", 0.03),
            make_record("gridbattle", "board", "accept", 0.05),
        ]

        result = verifier.classify_cross_game_robustness(records)

        self.assertEqual(result.robustness_label, "robust")
        self.assertEqual(result.compatible_game_types, ["board", "card"])
        self.assertEqual(result.failed_game_types, [])
        self.assertEqual(result.metadata_for_library["robustness_label"], "robust")

    def test_classifies_context_sensitive_when_game_type_dependency_is_clear(self):
        verifier = SelfVerifier()
        records = [
            make_record("boardwalk", "board", "accept", 0.04),
            make_record("gridbattle", "board", "accept", 0.03),
            make_record("cardduel", "card", "revise", -0.01),
            make_record("trickcards", "card", "discard", 0.00),
        ]

        result = verifier.classify_cross_game_robustness(records)

        self.assertEqual(result.robustness_label, "context_sensitive")
        self.assertEqual(result.compatible_game_types, ["board"])
        self.assertEqual(result.failed_game_types, ["card"])

    def test_failed_game_types_include_repeated_hard_constraint_failures(self):
        verifier = SelfVerifier()
        records = [
            make_record("boardwalk", "board", "accept", 0.04),
            make_record("gridbattle", "board", "accept", 0.03),
            make_record("cardduel-a", "card", "accept", 0.03),
            make_record("cardduel-b", "card", "accept", 0.02),
            make_record("cardduel-c", "card", "accept", 0.02, ["low_playability"]),
            make_record("cardduel-d", "card", "accept", 0.02, ["extreme_imbalance"]),
        ]

        result = verifier.classify_cross_game_robustness(records)

        self.assertEqual(result.robustness_label, "context_sensitive")
        self.assertIn("card", result.failed_game_types)
        self.assertTrue(
            result.metadata_for_library["game_type_summaries"]["card"]["repeated_hard_failures"]
        )

    def test_classifies_non_robust_when_most_results_fail(self):
        verifier = SelfVerifier()
        records = [
            make_record("boardwalk", "board", "revise", -0.02),
            make_record("gridbattle", "board", "discard", -0.01),
            make_record("cardduel", "card", "revise", 0.00),
        ]

        result = verifier.classify_cross_game_robustness(records)

        self.assertEqual(result.robustness_label, "non_robust")

    def test_single_game_decide_still_accepts_passing_case(self):
        verifier = SelfVerifier()
        verification_input = VerificationInput(
            stage=1,
            mechanic=MechanicCandidate(
                mechanic_name="Sample Bonus",
                mechanic_type="Scoring",
                description="Awards a small positional bonus.",
                python_code="def apply_bonus(game):\n    return game",
                justification="Adds strategic depth.",
                hook_location="perform_move",
            ),
            integration=IntegrationReport(
                schema_ok=True,
                syntax_ok=True,
                hook_ok=True,
                instantiation_ok=True,
                dry_run_ok=True,
            ),
            parent_metrics=PlaytestMetrics(
                total_matches=10,
                completed_matches=10,
                p1_win_rate=0.50,
                p2_win_rate=0.50,
                strong_agent_win_rate=0.55,
                weak_agent_win_rate=0.35,
                draw_rate=0.20,
                multi_choice_turns=50,
                total_turns=100,
            ),
            child_metrics=PlaytestMetrics(
                total_matches=10,
                completed_matches=10,
                p1_win_rate=0.50,
                p2_win_rate=0.50,
                strong_agent_win_rate=0.75,
                weak_agent_win_rate=0.25,
                draw_rate=0.10,
                multi_choice_turns=70,
                total_turns=100,
            ),
            trigger_stats=TriggerStats(
                trigger_count=10,
                triggered_matches=8,
                total_matches=10,
                total_turns=100,
                state_changed_by_mechanic_count=10,
            ),
        )

        result = verifier.decide(verification_input)

        self.assertEqual(result.decision, "accept")
        self.assertEqual(result.reason, "positive_relative_gain")


if __name__ == "__main__":
    unittest.main()
