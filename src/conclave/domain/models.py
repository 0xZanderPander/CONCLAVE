from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from conclave.domain.enums import (
    ReviewerSlot,
    ReviewerType,
    ReviewStage,
    TriggerKind,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReviewTrigger(FrozenModel):
    occurrence_id: str = Field(min_length=1)
    kind: TriggerKind
    due_at: datetime


class RequestIdentity(FrozenModel):
    caller_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    evidence_version: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    plan_revision: int = Field(ge=1)
    trigger: ReviewTrigger


class ReviewerAssignment(FrozenModel):
    slot: ReviewerSlot
    reviewer_type: ReviewerType
    provider: str | None = None
    model: str | None = None
    role_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)


class ReviewerInvocation(FrozenModel):
    session_id: str = Field(min_length=1)
    slot: ReviewerSlot
    stage: ReviewStage
    round: int = Field(ge=1)
    snapshot_hash: str = Field(min_length=1)
    assignment: ReviewerAssignment
    created_at: datetime


class AuditRecord(FrozenModel):
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
