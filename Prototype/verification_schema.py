from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MechanicCandidate:
    mechanic_name: str
    mechanic_type: str
    description: str
    python_code: str
    justification: str = ""
    hook_location: str = "perform_move"


@dataclass
class IntegrationReport:
    schema_ok: bool
    syntax_ok: bool
    hook_ok: bool
    instantiation_ok: bool
    dry_run_ok: bool
    error_message: str = ""


@dataclass
class PlaytestMetrics:
    total_matches: int
    completed_matches: int
    p1_win_rate: float
    p2_win_rate: float
    strong_agent_win_rate: float
    weak_agent_win_rate: float
    draw_rate: float = 0.0
    avg_game_length: float = 0.0
    avg_legal_actions: float = 0.0
    multi_choice_turns: int = 0
    total_turns: int = 0
    covered_cells: int = 0
    board_cell_count: int = 0


@dataclass
class TriggerStats:
    trigger_count: int
    triggered_matches: int
    total_matches: int
    total_turns: int
    state_changed_by_mechanic_count: int = 0

    def trigger_rate_by_match(self) -> float:
        if self.total_matches <= 0:
            return 0.0
        return self.triggered_matches / self.total_matches

    def trigger_rate_by_turn(self) -> float:
        if self.total_turns <= 0:
            return 0.0
        return self.trigger_count / self.total_turns


@dataclass
class DeltaMetrics:
    delta_playability: float
    delta_balance_gap: float
    delta_depth: float
    delta_decisiveness: float
    delta_agency: float
    delta_coverage: float = 0.0


@dataclass
class VerificationInput:
    stage: int
    mechanic: MechanicCandidate
    integration: IntegrationReport
    parent_metrics: PlaytestMetrics
    child_metrics: PlaytestMetrics
    trigger_stats: TriggerStats
    retry_count: int = 0
    parent_summary: str = ""


@dataclass
class VerificationOutput:
    decision: str
    reason: str
    stage: int
    absolute_metrics: Dict[str, Any]
    delta_metrics: Dict[str, Any]
    trigger_stats: Dict[str, Any]
    overall_score: float
    relative_score: float
    failure_modes: List[str] = field(default_factory=list)
    repair_feedback: Optional[str] = None
    metadata_for_library: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CrossGameVerificationRecord:
    game_name: str
    game_type: str
    verification_output: VerificationOutput


@dataclass
class CrossGameVerificationInput:
    records: List[CrossGameVerificationRecord]


@dataclass
class CrossGameVerificationOutput:
    robustness_label: str
    reason: str
    tested_games: int
    pass_rate: float
    positive_rate: float
    mean_relative_score: float
    compatible_game_types: List[str]
    failed_game_types: List[str]
    metadata_for_library: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
