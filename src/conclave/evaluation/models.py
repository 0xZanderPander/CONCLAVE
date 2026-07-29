from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from conclave.domain.enums import ReviewState


class AssessmentFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    assessment_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    category: str


class DirectionalIndicators(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    panel_changed: bool
    category_changed: bool
    caller_preference: Literal[
        "preferred_panel",
        "preferred_baseline",
        "neither",
        "not_comparable",
    ]
    additional_issue_count: int = Field(ge=0)
    cross_review_invoked: bool
    cross_review_resolved: bool
    reviewer_c_invoked: bool
    caller_override: bool
    outcome_classification: Literal[
        "beneficial",
        "harmful",
        "no_effect",
        "mixed",
        "inconclusive",
    ]
    outcome_evidence_quality: Literal[
        "strong",
        "adequate",
        "weak",
        "insufficient",
    ] | None
    action_executed: bool
    confounder_count: int = Field(ge=0)
    provider_attempt_count: int = Field(ge=0)
    total_latency_ms: int = Field(ge=0)
    total_cost_usd: float = Field(ge=0)


class ReviewerEvaluationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["reviewer-evaluation-candidate/v1"]
    review_session_id: str
    evidence_version: str
    result_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    feedback_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    route: Literal[
        "a_only",
        "ab_agreement",
        "cross_review_resolved",
        "c_tie_broken",
    ]
    interpretation: Literal["directional_only"]
    baseline: AssessmentFingerprint
    final: AssessmentFingerprint
    indicators: DirectionalIndicators


@dataclass(frozen=True, slots=True)
class EvaluationAcceptance:
    candidate_id: str
    candidate_hash: str
    session_id: str
    state: ReviewState


@dataclass(frozen=True, slots=True)
class RouteEvaluationMetrics:
    candidate_count: int
    average_latency_ms: float
    total_cost_usd: float
    average_cost_usd: float


@dataclass(frozen=True, slots=True)
class DirectionalEvaluationMetrics:
    interpretation: str
    candidate_count: int
    panel_change_rate: float | None
    caller_preferred_panel_rate: float | None
    average_additional_issue_count: float | None
    cross_review_resolution_rate: float | None
    reviewer_c_invocation_rate: float | None
    caller_override_rate: float | None
    routes: dict[str, RouteEvaluationMetrics]
