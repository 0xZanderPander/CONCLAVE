"""Chimera (marketing ad-performance) reviewer output models.

Moved verbatim from ``conclave.reviewers.runtime`` in B2. Field order and
validation messages are preserved: the 34 Phase 7 fixtures are the oracle.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from conclave.packs.chimera.vocabulary import RecommendationCategory
from conclave.packs.claims import AssessmentClaim, PeerClaimReview


class RecommendedAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    magnitude: float | None = None
    urgency: Literal["low", "normal", "high"] = "normal"
    confidence: float = Field(ge=0, le=1)


class ExperimentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis: str = Field(min_length=1)
    control: str = Field(min_length=1)
    isolated_change: str = Field(min_length=1)
    success_metric: str = Field(min_length=1)
    minimum_evidence: str = Field(min_length=1)
    exposure_limit: str = Field(min_length=1)
    stop_conditions: tuple[str, ...] = Field(min_length=1)
    review_after_hours: float = Field(gt=0)


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: RecommendationCategory
    summary: str = Field(min_length=1)
    claims: tuple[str | AssessmentClaim, ...] = ()
    actions: tuple[RecommendedAction, ...] = ()
    experiment: ExperimentDefinition | None = None
    material: bool = False
    risk: Literal["low", "medium", "high"] = "low"
    confidence: float = Field(ge=0, le=1)
    evidence_quality: Literal["strong", "adequate", "weak", "insufficient"]
    expected_goal_impact: Literal["negative", "neutral", "uncertain", "positive"] | None = None
    tracking_health: Literal["healthy", "degraded", "unhealthy"] | None = None
    optimization_eligible: bool | None = None
    primary_conversion: str | None = None
    missing_evidence: tuple[str, ...] = ()
    review_after_hours: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_claim_ids(self) -> "Assessment":
        claim_ids = [
            claim.claim_id
            for claim in self.claims
            if isinstance(claim, AssessmentClaim) and claim.claim_id is not None
        ]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("assessment claim IDs must be unique")
        return self


class CrossReviewResponse(BaseModel):
    """One bounded cross-review response plus the reviewer's complete assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    disposition: Literal["affirm", "revise"]
    peer_claim_reviews: tuple[PeerClaimReview, ...] = Field(min_length=1)
    assessment: Assessment

    @model_validator(mode="after")
    def validate_peer_claim_ids(self) -> "CrossReviewResponse":
        claim_ids = [review.claim_id for review in self.peer_claim_reviews]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("cross review cannot classify a peer claim more than once")
        return self


class ReviewerCJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: Literal[
        "select_a",
        "select_b",
        "synthesize",
        "insufficient_evidence",
        "escalate",
    ]
    summary: str = Field(min_length=1)
    selected_slot: Literal["A", "B"] | None = None
    resolution_assessment: Assessment | None = None
    confidence: float = Field(ge=0, le=1)
    evidence_quality: Literal["strong", "adequate", "weak", "insufficient"]
    supporting_claim_ids: tuple[str, ...] = ()
    rejected_claim_ids: tuple[str, ...] = ()
    unresolved_claim_ids: tuple[str, ...] = ()
    # Retained for exact assessment-v1 history compatibility.
    unresolved_claims: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_verdict(self) -> "ReviewerCJudgment":
        classified_ids = (
            *self.supporting_claim_ids,
            *self.rejected_claim_ids,
            *self.unresolved_claim_ids,
        )
        if len(classified_ids) != len(set(classified_ids)):
            raise ValueError("reviewer-C claim classifications must not overlap")
        if any(not claim_id.startswith("clm_") for claim_id in classified_ids):
            raise ValueError("reviewer-C claim classifications require claim IDs")
        expected_slot = {
            "select_a": "A",
            "select_b": "B",
        }.get(self.verdict)
        if expected_slot is not None:
            if self.selected_slot != expected_slot:
                raise ValueError(f"{self.verdict} requires selected_slot={expected_slot}")
            if self.resolution_assessment is not None:
                raise ValueError("select verdicts cannot include a resolution assessment")
            return self
        if self.selected_slot is not None:
            raise ValueError(f"{self.verdict} cannot select a reviewer slot")
        if self.resolution_assessment is None:
            raise ValueError(f"{self.verdict} requires a resolution assessment")
        return self


class AssessmentV2ProviderOutput(Assessment):
    """Provider-authored assessment-v2 before Conclave assigns claim IDs."""

    claims: tuple[AssessmentClaim, ...] = Field(min_length=1)


class CrossReviewV1ProviderOutput(CrossReviewResponse):
    assessment: AssessmentV2ProviderOutput


class ReviewerCJudgmentV2ProviderOutput(ReviewerCJudgment):
    resolution_assessment: AssessmentV2ProviderOutput | None = None


ReviewOutput = Assessment | CrossReviewResponse | ReviewerCJudgment

