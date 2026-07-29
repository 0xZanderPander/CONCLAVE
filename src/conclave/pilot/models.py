from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PilotScenario = Literal[
    "a_observe",
    "a_collect",
    "ab_collect",
    "ab_tracking",
    "ab_pause",
    "ab_experiment",
    "cross_collect",
    "cross_pause",
    "failed_goal_collect",
    "c_select_a",
    "c_select_b",
    "c_synthesize",
    "c_insufficient",
    "stale",
]

PilotFault = Literal[
    "none",
    "timeout_a",
    "timeout_b",
    "timeout_cross",
    "malformed_a",
    "malformed_cross",
    "cross_failure_once",
]

PilotFeedbackProfile = Literal[
    "none",
    "beneficial_panel",
    "beneficial_baseline",
    "harmful_baseline",
    "mixed_panel",
    "no_effect_neither",
    "inconclusive",
]


class Phase7ExpectedOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    final_state: Literal[
        "evaluated",
        "stale_or_ineligible_evidence",
        "reviewer_a_failed",
        "cross_review_failed",
    ]
    route: Literal[
        "a_only",
        "ab_agreement",
        "cross_review_resolved",
        "c_tie_broken",
    ] | None = None
    status: Literal["auto_resolved", "caller_decision_required"] | None = None
    category: Literal[
        "observe",
        "collect_more_data",
        "experiment",
        "operational_change",
        "tracking_or_data_problem",
        "freeze",
    ] | None = None

    @model_validator(mode="after")
    def require_result_fields_for_evaluated_cases(self) -> "Phase7ExpectedOutcome":
        result_fields = (self.route, self.status, self.category)
        if self.final_state == "evaluated" and any(value is None for value in result_fields):
            raise ValueError("evaluated pilot cases require route, status, and category")
        if self.final_state != "evaluated" and any(
            value is not None for value in result_fields
        ):
            raise ValueError("terminal pilot cases cannot declare result fields")
        return self


class Phase7PilotCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(pattern=r"^phase7-\d{3}$")
    title: str = Field(min_length=1)
    request_fixture: Literal[
        "01-normal-healthy.json",
        "02-weak-evidence.json",
        "03-tracking-unhealthy.json",
        "04-surviving-reviewer-conflict.json",
    ]
    scenario: PilotScenario
    trigger_kind: Literal["scheduled_a", "scheduled_b", "failed_goal", "manual"]
    fault: PilotFault = "none"
    feedback_profile: PilotFeedbackProfile = "inconclusive"
    repeat_intake: bool = False
    recover_cross_review: bool = False
    coverage: tuple[str, ...] = Field(min_length=1)
    expected: Phase7ExpectedOutcome

    @model_validator(mode="after")
    def validate_case_consistency(self) -> "Phase7PilotCase":
        if self.scenario == "stale" and self.expected.final_state != (
            "stale_or_ineligible_evidence"
        ):
            raise ValueError("stale cases require the stale terminal state")
        if self.expected.final_state != "evaluated" and self.feedback_profile != "none":
            raise ValueError("terminal cases cannot submit feedback")
        if self.recover_cross_review and self.fault != "cross_failure_once":
            raise ValueError("cross-review recovery requires cross_failure_once")
        return self


class Phase7PilotDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_version: Literal["phase7-pilot/v1"]
    as_of: Literal["2026-07-28"]
    cases: tuple[Phase7PilotCase, ...] = Field(min_length=30)

    @model_validator(mode="after")
    def validate_case_ids_and_coverage(self) -> "Phase7PilotDataset":
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("phase 7 pilot case IDs must be unique")
        coverage = {
            tag
            for case in self.cases
            for tag in case.coverage
        }
        required = {
            "material",
            "stale",
            "partial",
            "malformed_output",
            "timeout",
            "tracking_unhealthy",
            "disagreement",
            "cross_review",
            "tie_breaker",
        }
        missing = required - coverage
        if missing:
            raise ValueError(
                f"phase 7 pilot is missing required coverage: {sorted(missing)!r}"
            )
        return self
