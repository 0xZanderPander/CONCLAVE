from collections.abc import Mapping
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from conclave.domain.enums import (
    RecommendationCategory,
    ReviewerSlot,
    ReviewStage,
)


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: RecommendationCategory
    summary: str = Field(min_length=1)
    claims: tuple[str, ...] = ()
    material: bool = False
    risk: str = "low"
    confidence: float = Field(ge=0, le=1)
    evidence_quality: str


class ReviewCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str
    snapshot_hash: str
    slot: ReviewerSlot
    stage: ReviewStage
    round: int = Field(ge=1)
    prompt_version: str
    schema_version: str
    prior_claims: tuple[str, ...] = ()
    requested_at: datetime


class ReviewerRuntime(Protocol):
    def review(self, call: ReviewCall) -> Assessment:
        """Return one structured assessment without changing external state."""


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
