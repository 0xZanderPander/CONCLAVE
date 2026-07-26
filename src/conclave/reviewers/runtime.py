from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from conclave.domain.enums import (
    RecommendationCategory,
    ReviewerSlot,
    ReviewerType,
    ReviewStage,
)


class RecommendedAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    magnitude: float | None = None
    urgency: Literal["low", "normal", "high"] = "normal"
    confidence: float = Field(ge=0, le=1)


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: RecommendationCategory
    summary: str = Field(min_length=1)
    claims: tuple[str, ...] = ()
    actions: tuple[RecommendedAction, ...] = ()
    experiment: dict[str, Any] | None = None
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
    tie_break_verdict: (
        Literal["select_a", "select_b", "synthesize", "insufficient_evidence", "escalate"] | None
    ) = None
    selected_slot: Literal["A", "B"] | None = None


class PeerAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slot: ReviewerSlot
    stage: ReviewStage
    round: int = Field(ge=1)
    assessment: Assessment


class ReviewCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str
    snapshot_hash: str
    slot: ReviewerSlot
    stage: ReviewStage
    round: int = Field(ge=1)
    reviewer_type: ReviewerType
    provider: str
    model: str
    role_version: str
    prompt_version: str
    schema_version: str
    snapshot: dict[str, Any]
    prior_claims: tuple[str, ...] = ()
    peer_assessments: tuple[PeerAssessment, ...] = ()
    requested_at: datetime


class ReviewerRuntime(Protocol):
    def review(self, call: ReviewCall) -> Assessment:
        """Return one structured assessment without changing external state."""


class ReviewerProvider(Protocol):
    def invoke(self, call: ReviewCall) -> Assessment | Mapping[str, Any]:
        """Return a structured response without changing external state."""


class UnknownReviewerProviderError(LookupError):
    pass


class ReviewerProviderExhaustedError(RuntimeError):
    pass


class ProviderRegistryRuntime:
    """Routes reviewer calls through replaceable, contract-checked providers."""

    def __init__(
        self,
        providers: Mapping[str, ReviewerProvider],
        *,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        self._providers = dict(providers)
        self._max_attempts = max_attempts
        self._assessment_adapter = TypeAdapter(Assessment)

    def review(self, call: ReviewCall) -> Assessment:
        try:
            provider = self._providers[call.provider]
        except KeyError as exc:
            raise UnknownReviewerProviderError(
                f"reviewer provider {call.provider!r} is not registered"
            ) from exc
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = provider.invoke(call)
                return self._assessment_adapter.validate_python(response)
            except Exception as exc:
                if attempt == self._max_attempts:
                    raise ReviewerProviderExhaustedError(
                        f"reviewer provider {call.provider!r} failed "
                        f"after {self._max_attempts} attempts"
                    ) from exc
        raise AssertionError("provider retry loop exited unexpectedly")


class FakeReviewerRuntime:
    """Deterministic runtime for orchestration and ledger tests."""

    def __init__(
        self,
        responses: Mapping[tuple[ReviewerSlot, ReviewStage, int], Assessment],
    ) -> None:
        self._responses = dict(responses)
        self.calls: list[ReviewCall] = []

    def review(self, call: ReviewCall) -> Assessment:
        key = (call.slot, call.stage, call.round)
        try:
            response = self._responses[key]
        except KeyError as exc:
            raise LookupError(f"no fake reviewer response registered for {key}") from exc
        self.calls.append(call)
        return response
