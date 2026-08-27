from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from conclave.domain.enums import ReviewStage


class DomainEventType(StrEnum):
    PLAN_REVISION_CREATED = "plan_revision_created"
    OCCURRENCE_CREATED = "occurrence_created"
    WORK_ITEM_ENQUEUED = "work_item_enqueued"
    WORK_ITEM_CLAIMED = "work_item_claimed"
    WORK_ITEM_COMPLETED = "work_item_completed"
    WORK_ITEM_RETRY_SCHEDULED = "work_item_retry_scheduled"
    WORK_ITEM_DEAD_LETTERED = "work_item_dead_lettered"
    WORK_ITEM_LEASE_EXTENDED = "work_item_lease_extended"
    WORK_ITEM_MANUAL_RETRY = "work_item_manual_retry"
    WORK_ITEM_CANCELLED = "work_item_cancelled"
    SESSION_CREATED = "session_created"
    SNAPSHOT_STORED = "snapshot_stored"
    REQUEST_VALIDATED = "request_validated"
    REVIEWER_INVOCATION_CREATED = "reviewer_invocation_created"
    REVIEWER_INVOCATION_COMPLETED = "reviewer_invocation_completed"
    REVIEWER_INVOCATION_FAILED = "reviewer_invocation_failed"
    PROVIDER_ATTEMPT_COMPLETED = "provider_attempt_completed"
    COMPARISON_COMPLETED = "comparison_completed"
    STATE_TRANSITIONED = "state_transitioned"
    RESULT_RECORDED = "result_recorded"
    FEEDBACK_RECORDED = "feedback_recorded"
    EVALUATION_CANDIDATE_RECORDED = "evaluation_candidate_recorded"
    PROCESS_STARTED = "process_started"
    PROCESS_STOPPED = "process_stopped"


class EventActorType(StrEnum):
    SYSTEM = "system"
    CALLER = "caller"
    REVIEWER = "reviewer"
    SCHEDULER = "scheduler"
    WORKER = "worker"
    OPERATOR = "operator"


class EventActor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: EventActorType
    id: str = Field(min_length=1)


class PendingDomainEvent(BaseModel):
    """A validated event before durable identity and sequence are assigned."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: DomainEventType
    stream_type: str = Field(min_length=1)
    stream_id: str = Field(min_length=1)
    session_id: str | None = None
    actor: EventActor | None = None
    stage: ReviewStage | None = None
    round_number: int | None = Field(default=None, ge=1)
    summary: str = Field(min_length=1, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1)
    correlation_id: str | None = None
    causation_id: str | None = None
    schema_version: int = Field(default=1, ge=1)
    occurred_at: datetime | None = None

    @model_validator(mode="after")
    def validate_review_metadata(self) -> "PendingDomainEvent":
        if self.round_number is not None and self.stage is None:
            raise ValueError("round_number requires a review stage")
        return self


class DomainEvent(BaseModel):
    """Stable public envelope read by transport-neutral consumers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(pattern=r"^evt_[A-Za-z0-9_-]+$")
    stream_type: str = Field(min_length=1)
    stream_id: str = Field(min_length=1)
    session_id: str | None = None
    sequence: int = Field(ge=1)
    occurred_at: datetime
    event_type: DomainEventType
    actor: EventActor | None = None
    stage: ReviewStage | None = None
    round_number: int | None = Field(default=None, ge=1, serialization_alias="round")
    summary: str = Field(min_length=1, max_length=500)
    evidence_refs: tuple[str, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str
    causation_id: str | None = None
    schema_version: int = Field(ge=1)
