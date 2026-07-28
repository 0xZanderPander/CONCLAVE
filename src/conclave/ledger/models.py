from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

POSTGRES_JSON = JSON().with_variant(JSONB(), "postgresql")


def utc_now() -> datetime:
    return datetime.now(UTC)


class ImmutableLedgerRecordError(RuntimeError):
    pass


class PinnedSessionIdentityError(RuntimeError):
    pass


class Base(DeclarativeBase):
    pass


class ReviewPlanRecord(Base):
    __tablename__ = "review_plans"

    plan_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    deployment_id: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ReviewPlanRevisionRecord(Base):
    __tablename__ = "review_plan_revisions"
    __table_args__ = (UniqueConstraint("plan_id", "revision", name="uq_review_plan_revision"),)

    revision_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("review_plans.plan_id"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    plan: Mapped[ReviewPlanRecord] = relationship()


class ReviewerSlotRecord(Base):
    __tablename__ = "reviewer_slots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_revision"],
            ["review_plan_revisions.plan_id", "review_plan_revisions.revision"],
        ),
        UniqueConstraint(
            "plan_id",
            "plan_revision",
            "slot",
            name="uq_reviewer_slot_revision",
        ),
    )

    reviewer_slot_id: Mapped[str] = mapped_column(String(220), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(160), nullable=False)
    plan_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    slot: Mapped[str] = mapped_column(String(1), nullable=False)
    reviewer_type: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(160))
    role_version: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ReviewOccurrenceRecord(Base):
    __tablename__ = "review_occurrences"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_revision"],
            ["review_plan_revisions.plan_id", "review_plan_revisions.revision"],
        ),
        UniqueConstraint(
            "plan_id",
            "plan_revision",
            "due_at",
            "trigger_kind",
            name="uq_review_occurrence_schedule",
        ),
    )

    occurrence_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(160), nullable=False)
    plan_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trigger_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class SchedulerWorkItemRecord(Base):
    __tablename__ = "scheduler_work_items"
    __table_args__ = (
        UniqueConstraint("occurrence_id", name="uq_scheduler_work_item_occurrence"),
        Index(
            "ix_scheduler_work_items_claimable",
            "status",
            "available_at",
            "due_at",
            "work_item_id",
        ),
        Index(
            "ix_scheduler_work_items_lease",
            "status",
            "lease_expires_at",
        ),
    )

    work_item_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    occurrence_id: Mapped[str] = mapped_column(
        ForeignKey("review_occurrences.occurrence_id"), nullable=False
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    claimed_by: Mapped[str | None] = mapped_column(String(160))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ReviewSessionRecord(Base):
    __tablename__ = "review_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_revision"],
            ["review_plan_revisions.plan_id", "review_plan_revisions.revision"],
        ),
        UniqueConstraint(
            "caller_id",
            "occurrence_id",
            "evidence_version",
            "plan_revision",
            name="uq_review_session_identity",
        ),
        Index(
            "ix_review_sessions_plan_revision",
            "plan_id",
            "plan_revision",
        ),
    )

    session_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    caller_id: Mapped[str] = mapped_column(String(160), nullable=False)
    occurrence_id: Mapped[str] = mapped_column(
        ForeignKey("review_occurrences.occurrence_id"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(240), nullable=False)
    evidence_version: Mapped[str] = mapped_column(String(200), nullable=False)
    task_pack_hash: Mapped[str | None] = mapped_column(
        ForeignKey("task_pack_revisions.content_hash"),
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(String(160), nullable=False)
    plan_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    current_state: Mapped[str] = mapped_column(String(50), nullable=False, default="requested")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class RequestSnapshotRecord(Base):
    __tablename__ = "request_snapshots"
    __table_args__ = (UniqueConstraint("session_id", name="uq_request_snapshot_session"),)

    snapshot_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("review_sessions.session_id"), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(71), nullable=False, index=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class TaskPackRevisionRecord(Base):
    __tablename__ = "task_pack_revisions"

    content_hash: Mapped[str] = mapped_column(String(71), primary_key=True)
    task_pack_ref: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    document: Mapped[dict[str, Any]] = mapped_column(POSTGRES_JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ReviewerInvocationRecord(Base):
    __tablename__ = "reviewer_invocations"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "reviewer_slot",
            "stage",
            "round",
            name="uq_reviewer_invocation_stage",
        ),
    )

    invocation_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("review_sessions.session_id"), nullable=False
    )
    reviewer_slot: Mapped[str] = mapped_column(String(1), nullable=False)
    reviewer_type: Mapped[str] = mapped_column(String(40), nullable=False)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(160))
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    assessment_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_request_id: Mapped[str | None] = mapped_column(String(200))
    provider_response_id: Mapped[str | None] = mapped_column(String(200))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    finish_status: Mapped[str | None] = mapped_column(String(80))
    pricing_version: Mapped[str | None] = mapped_column(String(100))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ReviewerProviderAttemptRecord(Base):
    __tablename__ = "reviewer_provider_attempts"
    __table_args__ = (
        UniqueConstraint(
            "invocation_id",
            "attempt_number",
            name="uq_reviewer_provider_attempt",
        ),
    )

    attempt_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    invocation_id: Mapped[str] = mapped_column(
        ForeignKey("reviewer_invocations.invocation_id"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(200))
    provider_response_id: Mapped[str | None] = mapped_column(String(200))
    finish_status: Mapped[str | None] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    pricing_version: Mapped[str | None] = mapped_column(String(100))
    error_type: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReviewResultRecord(Base):
    __tablename__ = "review_results"
    __table_args__ = (UniqueConstraint("session_id", name="uq_review_result_session"),)

    result_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("review_sessions.session_id"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(60), nullable=False)
    result_hash: Mapped[str] = mapped_column(String(71), nullable=False, index=True)
    document: Mapped[dict[str, Any]] = mapped_column(POSTGRES_JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class RuntimeProcessRecord(Base):
    __tablename__ = "runtime_processes"
    __table_args__ = (
        Index(
            "ix_runtime_processes_status_heartbeat",
            "status",
            "heartbeat_at",
        ),
    )

    process_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    process_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    process_metadata: Mapped[dict[str, Any]] = mapped_column(
        POSTGRES_JSON, nullable=False, default=dict
    )


class EventStreamRecord(Base):
    __tablename__ = "event_streams"

    stream_type: Mapped[str] = mapped_column(String(80), primary_key=True)
    stream_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    last_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class AuditEventRecord(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "event_index",
            name="uq_audit_entity_event_index",
        ),
        UniqueConstraint("event_id", name="uq_audit_event_public_id"),
        Index("ix_audit_events_type_occurred", "event_type", "occurred_at"),
    )

    audit_event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(160), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(160))
    event_index: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_type: Mapped[str | None] = mapped_column(String(40))
    actor_id: Mapped[str | None] = mapped_column(String(160))
    stage: Mapped[str | None] = mapped_column(String(40))
    round_number: Mapped[int | None] = mapped_column("round", Integer)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    event_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float | None] = mapped_column(Float)
    correlation_id: Mapped[str] = mapped_column(String(160), nullable=False)
    causation_id: Mapped[str | None] = mapped_column(String(160))
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class EventSubscriptionRecord(Base):
    __tablename__ = "event_subscriptions"

    subscriber_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    stream_type: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class EventDeliveryRecord(Base):
    __tablename__ = "event_deliveries"
    __table_args__ = (
        Index(
            "ix_event_deliveries_claimable",
            "subscriber_id",
            "status",
            "available_at",
            "lease_expires_at",
        ),
        Index("ix_event_deliveries_event_id", "event_id"),
    )

    subscriber_id: Mapped[str] = mapped_column(
        ForeignKey("event_subscriptions.subscriber_id"),
        primary_key=True,
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("audit_events.event_id"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    claimed_by: Mapped[str | None] = mapped_column(String(160))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


def _reject_mutation(_mapper: Any, _connection: Any, target: Any) -> None:
    raise ImmutableLedgerRecordError(
        f"{type(target).__name__} is append-only and cannot be changed"
    )


for immutable_type in (
    ReviewPlanRevisionRecord,
    ReviewerSlotRecord,
    ReviewOccurrenceRecord,
    RequestSnapshotRecord,
    TaskPackRevisionRecord,
    ReviewResultRecord,
    ReviewerProviderAttemptRecord,
    AuditEventRecord,
):
    event.listen(immutable_type, "before_update", _reject_mutation)
    event.listen(immutable_type, "before_delete", _reject_mutation)


@event.listens_for(ReviewSessionRecord, "before_update")
def _protect_session_identity(_mapper: Any, _connection: Any, target: ReviewSessionRecord) -> None:
    state = inspect(target)
    protected = (
        "caller_id",
        "occurrence_id",
        "idempotency_key",
        "evidence_version",
        "task_pack_hash",
        "plan_id",
        "plan_revision",
        "created_at",
    )
    changed = [name for name in protected if state.attrs[name].history.has_changes()]
    if changed:
        raise PinnedSessionIdentityError(
            f"session identity is pinned; cannot change {', '.join(changed)}"
        )


@event.listens_for(SchedulerWorkItemRecord, "before_update")
def _protect_work_item_identity(
    _mapper: Any,
    _connection: Any,
    target: SchedulerWorkItemRecord,
) -> None:
    state = inspect(target)
    protected = ("occurrence_id", "due_at", "created_at")
    changed = [name for name in protected if state.attrs[name].history.has_changes()]
    if changed:
        raise PinnedSessionIdentityError(
            f"work-item identity is pinned; cannot change {', '.join(changed)}"
        )
