"""Cerberus (venture-submission assessment) reviewer output models.

Shape follows the engine's three-output protocol — assessment, cross-review
response, judgment — with venture-specific content: a verdict, a six-dimension
rubric score, strengths, weaknesses and written feedback for the founder.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from conclave.packs.cerberus.vocabulary import VentureVerdict
from conclave.packs.claims import AssessmentClaim, PeerClaimReview

Score = int


class VentureScores(BaseModel):
    """Rubric scores, 1 (weak) to 5 (strong). ``risk_exposure`` is inverted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    problem_clarity: Score = Field(ge=1, le=5)
    market_opportunity: Score = Field(ge=1, le=5)
    differentiation: Score = Field(ge=1, le=5)
    feasibility: Score = Field(ge=1, le=5)
    team_capability: Score = Field(ge=1, le=5)
    risk_exposure: Score = Field(ge=1, le=5)


class VentureAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: VentureVerdict
    summary: str = Field(min_length=1)
    claims: tuple[str | AssessmentClaim, ...] = ()
    scores: VentureScores
    strengths: tuple[str, ...] = ()
    weaknesses: tuple[str, ...] = ()
    feedback: str = Field(min_length=1)
    material: bool = True
    risk: Literal["low", "medium", "high"] = "medium"
    confidence: float = Field(ge=0, le=1)
    evidence_quality: Literal["strong", "adequate", "weak", "insufficient"]
    missing_evidence: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_claim_ids(self) -> "VentureAssessment":
        claim_ids = [
            claim.claim_id
            for claim in self.claims
            if isinstance(claim, AssessmentClaim) and claim.claim_id is not None
        ]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("assessment claim IDs must be unique")
        return self


class VentureCrossReviewResponse(BaseModel):
    """One bounded cross-review response plus the reviewer's complete assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    disposition: Literal["affirm", "revise"]
    peer_claim_reviews: tuple[PeerClaimReview, ...] = Field(min_length=1)
    assessment: VentureAssessment

    @model_validator(mode="after")
    def validate_peer_claim_ids(self) -> "VentureCrossReviewResponse":
        claim_ids = [review.claim_id for review in self.peer_claim_reviews]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("cross review cannot classify a peer claim more than once")
        return self


class VentureJudgment(BaseModel):
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
    resolution_assessment: VentureAssessment | None = None
    confidence: float = Field(ge=0, le=1)
    evidence_quality: Literal["strong", "adequate", "weak", "insufficient"]
    supporting_claim_ids: tuple[str, ...] = ()
    rejected_claim_ids: tuple[str, ...] = ()
    unresolved_claim_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_verdict(self) -> "VentureJudgment":
        classified_ids = (
            *self.supporting_claim_ids,
            *self.rejected_claim_ids,
            *self.unresolved_claim_ids,
        )
        if len(classified_ids) != len(set(classified_ids)):
            raise ValueError("judge claim classifications must not overlap")
        if any(not claim_id.startswith("clm_") for claim_id in classified_ids):
            raise ValueError("judge claim classifications require claim IDs")
        expected_slot = {"select_a": "A", "select_b": "B"}.get(self.verdict)
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

    # The engine reads this legacy field on every judgment type.
    @property
    def unresolved_claims(self) -> tuple[str, ...]:
        return ()


class VentureAssessmentProviderOutput(VentureAssessment):
    """Provider-authored assessment before Conclave assigns claim IDs."""

    claims: tuple[AssessmentClaim, ...] = Field(min_length=1)


class VentureCrossReviewProviderOutput(VentureCrossReviewResponse):
    assessment: VentureAssessmentProviderOutput


class VentureJudgmentProviderOutput(VentureJudgment):
    resolution_assessment: VentureAssessmentProviderOutput | None = None
