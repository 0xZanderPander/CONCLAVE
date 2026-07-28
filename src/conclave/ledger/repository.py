import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, sessionmaker

from conclave.domain.enums import ReviewerSlot, ReviewerType, ReviewStage, ReviewState
from conclave.domain.models import RequestIdentity
from conclave.events.models import (
    DomainEvent,
    DomainEventType,
    EventActor,
    EventActorType,
    PendingDomainEvent,
)
from conclave.ledger.models import (
    AuditEventRecord,
    Base,
    EventDeliveryRecord,
    EventStreamRecord,
    EventSubscriptionRecord,
    RequestSnapshotRecord,
    ReviewerInvocationRecord,
    ReviewerProviderAttemptRecord,
    ReviewerSlotRecord,
    ReviewOccurrenceRecord,
    ReviewPlanRecord,
    ReviewPlanRevisionRecord,
    ReviewResultRecord,
    ReviewSessionRecord,
    RuntimeProcessRecord,
    SchedulerWorkItemRecord,
    TaskPackRevisionRecord,
)
from conclave.orchestration.state_machine import (
    validate_recovery_transition,
    validate_transition,
)
from conclave.plans.models import ReviewPlanRevision
from conclave.reviewers.runtime import ProviderAttempt


class LedgerConflictError(RuntimeError):
    pass


class WorkItemClaimError(RuntimeError):
    pass


class EventDeliveryClaimError(RuntimeError):
    pass


class ReviewRecoveryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class QueueMetrics:
    counts: dict[str, int]
    oldest_claimable_at: datetime | None
    expired_leases: int


@dataclass(frozen=True, slots=True)
class ProviderMetrics:
    counts: dict[str, int]
    total_tokens: int
    total_cost_usd: float
    average_latency_ms: float | None
    last_completed_at: datetime | None


def canonical_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def deterministic_id(prefix: str, *parts: object) -> str:
    encoded = "|".join(str(part) for part in parts).encode()
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:24]}"


def normalize_instant(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def same_instant(left: datetime, right: datetime) -> bool:
    return normalize_instant(left) == normalize_instant(right)


def state_transition_summary(target: ReviewState) -> str:
    summaries = {
        ReviewState.VALIDATED: "The review request was validated.",
        ReviewState.SNAPSHOTTED: "The immutable review snapshot is ready.",
        ReviewState.REVIEWER_A: "Reviewer A review started.",
        ReviewState.BASELINE_RECORDED: "The single-reviewer baseline was recorded.",
        ReviewState.REVIEWER_B: "Reviewer B independent review started.",
        ReviewState.COMPARING: "The reviewer assessments are ready for comparison.",
        ReviewState.CROSS_REVIEW: "Cross review started.",
        ReviewState.REVIEWER_C_INDEPENDENT: "Reviewer C independent assessment started.",
        ReviewState.REVIEWER_C_JUDGING: "Reviewer C judgment started.",
        ReviewState.REVIEWER_ADJUDICATION: "Reviewer adjudication started.",
        ReviewState.AUTO_RESOLVED: "The review was auto-resolved.",
        ReviewState.CALLER_DECISION_REQUIRED: "The review requires a caller decision.",
        ReviewState.RESULT_RETURNED: "The structured review result is available.",
        ReviewState.FEEDBACK_PENDING: "The review is awaiting optional caller feedback.",
        ReviewState.EVALUATED: "Reviewer performance evaluation completed.",
        ReviewState.INVALID_REQUEST: "The review request was rejected as invalid.",
        ReviewState.STALE_OR_INELIGIBLE_EVIDENCE: (
            "The review stopped because the evidence was stale or ineligible."
        ),
        ReviewState.REVIEWER_A_FAILED: "Reviewer A failed.",
        ReviewState.REVIEWER_B_FAILED: "Reviewer B failed.",
        ReviewState.CROSS_REVIEW_FAILED: "Cross review failed.",
        ReviewState.REVIEWER_C_FAILED: "Reviewer C failed.",
        ReviewState.AWAITING_EVIDENCE: "The review is waiting for more evidence.",
        ReviewState.RESULT_DELIVERY_FAILED: "Review-result delivery failed.",
        ReviewState.CANCELLED: "The review session was cancelled.",
    }
    return summaries[target]


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


class LedgerRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def add_plan_revision(self, revision: ReviewPlanRevision) -> ReviewPlanRevisionRecord:
        payload = revision.model_dump(mode="json")
        revision_id = f"{revision.plan_id}:r{revision.revision}"
        with self._sessions.begin() as db:
            plan = db.get(ReviewPlanRecord, revision.plan_id)
            if plan is None:
                db.add(
                    ReviewPlanRecord(
                        plan_id=revision.plan_id,
                        deployment_id=revision.deployment_id,
                    )
                )
            elif plan.deployment_id != revision.deployment_id:
                raise LedgerConflictError("plan deployment_id cannot change")

            existing = db.get(ReviewPlanRevisionRecord, revision_id)
            if existing is not None:
                if existing.content_hash != canonical_hash(payload):
                    raise LedgerConflictError("plan revision already exists with different content")
                return existing

            record = ReviewPlanRevisionRecord(
                revision_id=revision_id,
                plan_id=revision.plan_id,
                revision=revision.revision,
                effective_at=revision.effective_at,
                content_hash=canonical_hash(payload),
                configuration=payload,
                paused=revision.paused,
            )
            db.add(record)
            for slot, assignment in revision.slots.items():
                db.add(
                    ReviewerSlotRecord(
                        reviewer_slot_id=f"{revision_id}:{slot.value}",
                        plan_id=revision.plan_id,
                        plan_revision=revision.revision,
                        slot=slot.value,
                        reviewer_type=assignment.reviewer_type.value,
                        provider=assignment.provider,
                        model=assignment.model,
                        role_version=assignment.role_version,
                        prompt_version=assignment.prompt_version,
                        schema_version=assignment.schema_version,
                    )
                )
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.PLAN_REVISION_CREATED,
                    stream_type="review_plan_revision",
                    stream_id=revision_id,
                    actor=EventActor(type=EventActorType.SYSTEM, id="conclave"),
                    summary=f"Review plan revision {revision.revision} was created.",
                    payload={
                        "plan_id": revision.plan_id,
                        "revision": revision.revision,
                        "content_hash": record.content_hash,
                    },
                ),
            )
            db.flush()
            return record

    def add_occurrence(
        self,
        *,
        occurrence_id: str,
        plan_id: str,
        plan_revision: int,
        due_at: datetime,
        trigger_kind: str,
    ) -> ReviewOccurrenceRecord:
        with self._sessions.begin() as db:
            existing = db.get(ReviewOccurrenceRecord, occurrence_id)
            if existing is not None:
                if (
                    existing.plan_id != plan_id
                    or existing.plan_revision != plan_revision
                    or not same_instant(existing.due_at, due_at)
                    or existing.trigger_kind != trigger_kind
                ):
                    raise LedgerConflictError(
                        "occurrence ID already exists with different schedule data"
                    )
                return existing
            record = ReviewOccurrenceRecord(
                occurrence_id=occurrence_id,
                plan_id=plan_id,
                plan_revision=plan_revision,
                due_at=due_at,
                trigger_kind=trigger_kind,
            )
            db.add(record)
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.OCCURRENCE_CREATED,
                    stream_type="review_occurrence",
                    stream_id=occurrence_id,
                    actor=EventActor(type=EventActorType.SCHEDULER, id="conclave"),
                    summary="A review occurrence was scheduled.",
                    payload={
                        "plan_id": plan_id,
                        "plan_revision": plan_revision,
                        "trigger_kind": trigger_kind,
                        "due_at": due_at.isoformat(),
                    },
                ),
            )
            try:
                db.flush()
            except IntegrityError as exc:
                raise LedgerConflictError(
                    "review occurrence conflicts with an existing schedule"
                ) from exc
            return record

    def enqueue_occurrence(
        self,
        *,
        occurrence_id: str,
        due_at: datetime,
        max_attempts: int = 3,
    ) -> SchedulerWorkItemRecord:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        work_item_id = deterministic_id("work", occurrence_id)
        with self._sessions.begin() as db:
            existing = db.get(SchedulerWorkItemRecord, work_item_id)
            if existing is not None:
                if existing.occurrence_id != occurrence_id or not same_instant(
                    existing.due_at, due_at
                ):
                    raise LedgerConflictError(
                        "work-item ID already exists with different occurrence data"
                    )
                return existing
            record = SchedulerWorkItemRecord(
                work_item_id=work_item_id,
                occurrence_id=occurrence_id,
                due_at=due_at,
                available_at=due_at,
                status="pending",
                max_attempts=max_attempts,
            )
            db.add(record)
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.WORK_ITEM_ENQUEUED,
                    stream_type="scheduler_work_item",
                    stream_id=work_item_id,
                    actor=EventActor(type=EventActorType.SCHEDULER, id="conclave"),
                    summary="Scheduled review work was added to the queue.",
                    payload={
                        "occurrence_id": occurrence_id,
                        "due_at": due_at.isoformat(),
                        "max_attempts": max_attempts,
                    },
                ),
            )
            db.flush()
            return record

    def claim_next_work_item(
        self,
        *,
        worker_id: str,
        now: datetime,
        lease_seconds: int = 60,
    ) -> SchedulerWorkItemRecord | None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        with self._sessions.begin() as db:
            record = db.scalar(
                select(SchedulerWorkItemRecord)
                .where(
                    or_(
                        (
                            SchedulerWorkItemRecord.status.in_(("pending", "retry"))
                            & (SchedulerWorkItemRecord.available_at <= now)
                        ),
                        (
                            (SchedulerWorkItemRecord.status == "claimed")
                            & (SchedulerWorkItemRecord.lease_expires_at <= now)
                        ),
                    )
                )
                .order_by(
                    SchedulerWorkItemRecord.due_at,
                    SchedulerWorkItemRecord.work_item_id,
                )
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if record is None:
                return None
            record.status = "claimed"
            record.claimed_by = worker_id
            record.claimed_at = now
            record.lease_expires_at = now + timedelta(seconds=lease_seconds)
            record.attempts += 1
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.WORK_ITEM_CLAIMED,
                    stream_type="scheduler_work_item",
                    stream_id=record.work_item_id,
                    actor=EventActor(type=EventActorType.WORKER, id=worker_id),
                    summary=f"Worker {worker_id} claimed scheduled review work.",
                    payload={
                        "worker_id": worker_id,
                        "lease_expires_at": record.lease_expires_at.isoformat(),
                        "attempt": record.attempts,
                    },
                    occurred_at=now,
                ),
            )
            db.flush()
            return record

    def complete_work_item(
        self,
        *,
        work_item_id: str,
        worker_id: str,
        now: datetime,
    ) -> SchedulerWorkItemRecord:
        with self._sessions.begin() as db:
            record = db.scalar(
                select(SchedulerWorkItemRecord)
                .where(SchedulerWorkItemRecord.work_item_id == work_item_id)
                .with_for_update()
            )
            if record is None:
                raise LookupError(f"unknown scheduler work item {work_item_id!r}")
            if record.status != "claimed" or record.claimed_by != worker_id:
                raise WorkItemClaimError("only the active lease holder may complete work")
            if record.lease_expires_at is not None and normalize_instant(
                record.lease_expires_at
            ) < normalize_instant(now):
                raise WorkItemClaimError("work-item lease has expired")
            record.status = "completed"
            record.completed_at = now
            record.lease_expires_at = None
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.WORK_ITEM_COMPLETED,
                    stream_type="scheduler_work_item",
                    stream_id=work_item_id,
                    actor=EventActor(type=EventActorType.WORKER, id=worker_id),
                    summary="Scheduled review work completed.",
                    payload={"worker_id": worker_id},
                    occurred_at=now,
                ),
            )
            db.flush()
            return record

    def fail_work_item(
        self,
        *,
        work_item_id: str,
        worker_id: str,
        now: datetime,
        error: str,
        retryable: bool = True,
        retry_delay_seconds: int = 30,
    ) -> SchedulerWorkItemRecord:
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        with self._sessions.begin() as db:
            record = db.scalar(
                select(SchedulerWorkItemRecord)
                .where(SchedulerWorkItemRecord.work_item_id == work_item_id)
                .with_for_update()
            )
            if record is None:
                raise LookupError(f"unknown scheduler work item {work_item_id!r}")
            if record.status != "claimed" or record.claimed_by != worker_id:
                raise WorkItemClaimError("only the active lease holder may fail work")
            dead_lettered = not retryable or record.attempts >= record.max_attempts
            record.status = "dead_letter" if dead_lettered else "retry"
            record.completed_at = now if dead_lettered else None
            record.dead_lettered_at = now if dead_lettered else None
            record.available_at = now + timedelta(seconds=retry_delay_seconds)
            record.lease_expires_at = None
            record.last_error = error[:1000]
            record.claimed_by = None
            record.claimed_at = None
            event_type = (
                DomainEventType.WORK_ITEM_DEAD_LETTERED
                if dead_lettered
                else DomainEventType.WORK_ITEM_RETRY_SCHEDULED
            )
            summary = (
                "Scheduled review work was moved to the dead-letter queue."
                if dead_lettered
                else "Scheduled review work will be retried."
            )
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=event_type,
                    stream_type="scheduler_work_item",
                    stream_id=work_item_id,
                    actor=EventActor(type=EventActorType.WORKER, id=worker_id),
                    summary=summary,
                    payload={
                        "worker_id": worker_id,
                        "error": record.last_error,
                        "attempt": record.attempts,
                        "max_attempts": record.max_attempts,
                        "available_at": (
                            None if dead_lettered else record.available_at.isoformat()
                        ),
                    },
                    occurred_at=now,
                ),
            )
            db.flush()
            return record

    def extend_work_item_lease(
        self,
        *,
        work_item_id: str,
        worker_id: str,
        now: datetime,
        lease_seconds: int,
    ) -> SchedulerWorkItemRecord:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        with self._sessions.begin() as db:
            record = db.scalar(
                select(SchedulerWorkItemRecord)
                .where(SchedulerWorkItemRecord.work_item_id == work_item_id)
                .with_for_update()
            )
            if record is None:
                raise LookupError(f"unknown scheduler work item {work_item_id!r}")
            if record.status != "claimed" or record.claimed_by != worker_id:
                raise WorkItemClaimError("only the active lease holder may extend work")
            record.lease_expires_at = now + timedelta(seconds=lease_seconds)
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.WORK_ITEM_LEASE_EXTENDED,
                    stream_type="scheduler_work_item",
                    stream_id=work_item_id,
                    actor=EventActor(type=EventActorType.WORKER, id=worker_id),
                    summary="The scheduled-work lease was extended.",
                    payload={
                        "worker_id": worker_id,
                        "lease_expires_at": record.lease_expires_at.isoformat(),
                    },
                    occurred_at=now,
                ),
            )
            db.flush()
            return record

    def retry_dead_letter(
        self,
        *,
        work_item_id: str,
        now: datetime,
        additional_attempts: int = 1,
    ) -> SchedulerWorkItemRecord:
        if additional_attempts <= 0:
            raise ValueError("additional_attempts must be positive")
        with self._sessions.begin() as db:
            record = db.scalar(
                select(SchedulerWorkItemRecord)
                .where(SchedulerWorkItemRecord.work_item_id == work_item_id)
                .with_for_update()
            )
            if record is None:
                raise LookupError(f"unknown scheduler work item {work_item_id!r}")
            if record.status != "dead_letter":
                raise WorkItemClaimError("only dead-letter work may be retried manually")
            record.status = "retry"
            record.max_attempts += additional_attempts
            record.available_at = now
            record.completed_at = None
            record.dead_lettered_at = None
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.WORK_ITEM_MANUAL_RETRY,
                    stream_type="scheduler_work_item",
                    stream_id=work_item_id,
                    actor=EventActor(type=EventActorType.OPERATOR, id="operator"),
                    summary="An operator returned dead-letter work to the retry queue.",
                    payload={
                        "additional_attempts": additional_attempts,
                        "max_attempts": record.max_attempts,
                    },
                    occurred_at=now,
                ),
            )
            db.flush()
            return record

    def cancel_work_item(
        self,
        *,
        work_item_id: str,
        now: datetime,
        reason: str,
    ) -> SchedulerWorkItemRecord:
        with self._sessions.begin() as db:
            record = db.scalar(
                select(SchedulerWorkItemRecord)
                .where(SchedulerWorkItemRecord.work_item_id == work_item_id)
                .with_for_update()
            )
            if record is None:
                raise LookupError(f"unknown scheduler work item {work_item_id!r}")
            if record.status in {"completed", "cancelled"}:
                raise WorkItemClaimError(f"cannot cancel work in state {record.status!r}")
            record.status = "cancelled"
            record.completed_at = now
            record.lease_expires_at = None
            record.claimed_by = None
            record.claimed_at = None
            record.last_error = reason[:1000]
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.WORK_ITEM_CANCELLED,
                    stream_type="scheduler_work_item",
                    stream_id=work_item_id,
                    actor=EventActor(type=EventActorType.OPERATOR, id="operator"),
                    summary="An operator cancelled unfinished review work.",
                    payload={"reason": record.last_error},
                    occurred_at=now,
                ),
            )
            db.flush()
            return record

    def queue_metrics(self, now: datetime) -> QueueMetrics:
        with self._sessions() as db:
            rows = db.execute(
                select(
                    SchedulerWorkItemRecord.status,
                    func.count(SchedulerWorkItemRecord.work_item_id),
                ).group_by(SchedulerWorkItemRecord.status)
            )
            counts = {status: count for status, count in rows}
            oldest = db.scalar(
                select(func.min(SchedulerWorkItemRecord.available_at)).where(
                    SchedulerWorkItemRecord.status.in_(("pending", "retry")),
                    SchedulerWorkItemRecord.available_at <= now,
                )
            )
            expired = db.scalar(
                select(func.count(SchedulerWorkItemRecord.work_item_id)).where(
                    SchedulerWorkItemRecord.status == "claimed",
                    SchedulerWorkItemRecord.lease_expires_at <= now,
                )
            )
            return QueueMetrics(
                counts=counts,
                oldest_claimable_at=oldest,
                expired_leases=expired or 0,
            )

    def provider_metrics(self) -> ProviderMetrics:
        with self._sessions() as db:
            rows = db.execute(
                select(
                    ReviewerProviderAttemptRecord.status,
                    func.count(ReviewerProviderAttemptRecord.attempt_id),
                ).group_by(ReviewerProviderAttemptRecord.status)
            )
            counts = {status: count for status, count in rows}
            aggregate = db.execute(
                select(
                    func.sum(ReviewerProviderAttemptRecord.total_tokens),
                    func.sum(ReviewerProviderAttemptRecord.cost_usd),
                    func.avg(ReviewerProviderAttemptRecord.latency_ms),
                    func.max(ReviewerProviderAttemptRecord.completed_at),
                )
            ).one()
            return ProviderMetrics(
                counts=counts,
                total_tokens=int(aggregate[0] or 0),
                total_cost_usd=float(aggregate[1] or 0),
                average_latency_ms=(
                    float(aggregate[2]) if aggregate[2] is not None else None
                ),
                last_completed_at=aggregate[3],
            )

    def list_plan_revisions(self) -> list[ReviewPlanRevision]:
        with self._sessions() as db:
            records = list(
                db.scalars(
                    select(ReviewPlanRevisionRecord).order_by(
                        ReviewPlanRevisionRecord.plan_id,
                        ReviewPlanRevisionRecord.revision,
                    )
                )
            )
            return [ReviewPlanRevision.model_validate(record.configuration) for record in records]

    def get_work_item(self, work_item_id: str) -> SchedulerWorkItemRecord | None:
        with self._sessions() as db:
            return db.get(SchedulerWorkItemRecord, work_item_id)

    def get_occurrence(self, occurrence_id: str) -> ReviewOccurrenceRecord | None:
        with self._sessions() as db:
            return db.get(ReviewOccurrenceRecord, occurrence_id)

    def find_session_by_occurrence(
        self,
        occurrence_id: str,
    ) -> ReviewSessionRecord | None:
        with self._sessions() as db:
            return db.scalar(
                select(ReviewSessionRecord).where(
                    ReviewSessionRecord.occurrence_id == occurrence_id
                )
            )

    def register_task_pack_revision(
        self,
        *,
        task_pack_ref: str,
        content_hash: str,
        document: dict[str, Any],
    ) -> TaskPackRevisionRecord:
        if canonical_hash(document) != content_hash:
            raise LedgerConflictError("task-pack content hash is invalid")
        with self._sessions.begin() as db:
            by_ref = db.scalar(
                select(TaskPackRevisionRecord).where(
                    TaskPackRevisionRecord.task_pack_ref == task_pack_ref
                )
            )
            if by_ref is not None:
                if by_ref.content_hash != content_hash or by_ref.document != document:
                    raise LedgerConflictError(
                        "task-pack reference cannot be reused with different content"
                    )
                return by_ref
            by_hash = db.get(TaskPackRevisionRecord, content_hash)
            if by_hash is not None:
                if by_hash.task_pack_ref != task_pack_ref or by_hash.document != document:
                    raise LedgerConflictError(
                        "task-pack hash cannot be reused with different content"
                    )
                return by_hash
            record = TaskPackRevisionRecord(
                content_hash=content_hash,
                task_pack_ref=task_pack_ref,
                document=document,
            )
            db.add(record)
            db.flush()
            return record

    def get_task_pack_revision(
        self,
        content_hash: str,
    ) -> TaskPackRevisionRecord | None:
        with self._sessions() as db:
            return db.get(TaskPackRevisionRecord, content_hash)

    def create_session(
        self,
        identity: RequestIdentity,
        *,
        task_pack_hash: str | None = None,
    ) -> ReviewSessionRecord:
        session_id = deterministic_id(
            "rs",
            identity.caller_id,
            identity.trigger.occurrence_id,
            identity.evidence_version,
            identity.plan_revision,
        )
        with self._sessions.begin() as db:
            existing = db.get(ReviewSessionRecord, session_id)
            if existing is not None:
                if existing.idempotency_key != identity.idempotency_key:
                    raise LedgerConflictError("session identity reused with a new idempotency key")
                if task_pack_hash is not None and existing.task_pack_hash != task_pack_hash:
                    raise LedgerConflictError(
                        "session identity reused with a new task-pack revision"
                    )
                return existing
            record = ReviewSessionRecord(
                session_id=session_id,
                caller_id=identity.caller_id,
                occurrence_id=identity.trigger.occurrence_id,
                idempotency_key=identity.idempotency_key,
                evidence_version=identity.evidence_version,
                task_pack_hash=task_pack_hash,
                plan_id=identity.plan_id,
                plan_revision=identity.plan_revision,
                current_state=ReviewState.REQUESTED.value,
            )
            db.add(record)
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.SESSION_CREATED,
                    stream_type="review_session",
                    stream_id=session_id,
                    session_id=session_id,
                    actor=EventActor(type=EventActorType.CALLER, id=identity.caller_id),
                    summary="A review session was requested.",
                    payload={
                        "state": ReviewState.REQUESTED.value,
                        "occurrence_id": identity.trigger.occurrence_id,
                        "plan_id": identity.plan_id,
                        "plan_revision": identity.plan_revision,
                        "evidence_version": identity.evidence_version,
                        "task_pack_hash": task_pack_hash,
                    },
                    correlation_id=session_id,
                ),
            )
            try:
                db.flush()
            except IntegrityError as exc:
                raise LedgerConflictError("review session violates idempotency") from exc
            return record

    def store_snapshot(
        self,
        *,
        session_id: str,
        content: dict[str, Any],
    ) -> RequestSnapshotRecord:
        content_hash = canonical_hash(content)
        snapshot_id = deterministic_id("snap", session_id, content_hash)
        with self._sessions.begin() as db:
            existing = db.scalar(
                select(RequestSnapshotRecord).where(RequestSnapshotRecord.session_id == session_id)
            )
            if existing is not None:
                if existing.content_hash != content_hash:
                    raise LedgerConflictError("session snapshot is immutable")
                return existing
            record = RequestSnapshotRecord(
                snapshot_id=snapshot_id,
                session_id=session_id,
                content_hash=content_hash,
                content=content,
            )
            db.add(record)
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.SNAPSHOT_STORED,
                    stream_type="review_session",
                    stream_id=session_id,
                    session_id=session_id,
                    actor=EventActor(type=EventActorType.SYSTEM, id="conclave"),
                    summary="The immutable request snapshot was stored.",
                    payload={
                        "snapshot_id": snapshot_id,
                        "content_hash": content_hash,
                    },
                    correlation_id=session_id,
                ),
            )
            db.flush()
            return record

    def record_invocation(
        self,
        *,
        session_id: str,
        slot: ReviewerSlot,
        reviewer_type: ReviewerType,
        stage: ReviewStage,
        round_number: int,
        snapshot_hash: str,
        prompt_version: str,
        schema_version: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> ReviewerInvocationRecord:
        invocation_id = deterministic_id("inv", session_id, slot.value, stage.value, round_number)
        with self._sessions.begin() as db:
            existing = db.get(ReviewerInvocationRecord, invocation_id)
            if existing is not None:
                expected = (
                    reviewer_type.value,
                    snapshot_hash,
                    provider,
                    model,
                    prompt_version,
                    schema_version,
                )
                actual = (
                    existing.reviewer_type,
                    existing.snapshot_hash,
                    existing.provider,
                    existing.model,
                    existing.prompt_version,
                    existing.schema_version,
                )
                if actual != expected:
                    raise LedgerConflictError(
                        "reviewer invocation identity cannot be reused with new inputs"
                    )
                return existing
            record = ReviewerInvocationRecord(
                invocation_id=invocation_id,
                session_id=session_id,
                reviewer_slot=slot.value,
                reviewer_type=reviewer_type.value,
                stage=stage.value,
                round=round_number,
                snapshot_hash=snapshot_hash,
                provider=provider,
                model=model,
                prompt_version=prompt_version,
                schema_version=schema_version,
            )
            db.add(record)
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.REVIEWER_INVOCATION_CREATED,
                    stream_type="review_session",
                    stream_id=session_id,
                    session_id=session_id,
                    actor=EventActor(type=EventActorType.SYSTEM, id="conclave"),
                    stage=stage,
                    round_number=round_number,
                    summary=(
                        f"Reviewer {slot.value} was assigned a "
                        f"{stage.value.replace('_', '-')} assessment."
                    ),
                    payload={
                        "invocation_id": invocation_id,
                        "slot": slot.value,
                        "reviewer_type": reviewer_type.value,
                        "provider": provider,
                        "model": model,
                    },
                    correlation_id=session_id,
                ),
            )
            db.flush()
            return record

    def complete_invocation(
        self,
        *,
        invocation_id: str,
        assessment_payload: dict[str, Any],
        completed_at: datetime,
    ) -> ReviewerInvocationRecord:
        with self._sessions.begin() as db:
            record = db.scalar(
                select(ReviewerInvocationRecord)
                .where(ReviewerInvocationRecord.invocation_id == invocation_id)
                .with_for_update()
            )
            if record is None:
                raise LookupError(f"unknown reviewer invocation {invocation_id!r}")
            if record.status == "completed":
                if record.assessment_payload != assessment_payload:
                    raise LedgerConflictError("completed invocation cannot accept a new assessment")
                return record
            if record.status != "pending":
                raise LedgerConflictError(f"cannot complete invocation in state {record.status!r}")
            record.status = "completed"
            record.assessment_payload = assessment_payload
            record.completed_at = completed_at
            if record.stage == ReviewStage.JUDGING.value:
                summary = f"Reviewer {record.reviewer_slot} submitted a tie-break judgment."
            elif record.stage == ReviewStage.CROSS_REVIEW.value:
                summary = f"Reviewer {record.reviewer_slot} submitted a cross-review assessment."
            else:
                summary = f"Reviewer {record.reviewer_slot} submitted an independent assessment."
            assessment_document = (
                assessment_payload.get("assessment", {})
                if record.stage == ReviewStage.CROSS_REVIEW.value
                and record.schema_version == "cross-review-v1"
                else assessment_payload
            )
            claim_evidence_refs = tuple(
                dict.fromkeys(
                    reference
                    for claim in assessment_document.get("claims", [])
                    if isinstance(claim, dict)
                    for reference in claim.get("evidence_references", [])
                    if isinstance(reference, str)
                )
            )
            peer_review_evidence_refs = tuple(
                dict.fromkeys(
                    reference
                    for review in assessment_payload.get("peer_claim_reviews", [])
                    if isinstance(review, dict)
                    for reference in review.get("evidence_references", [])
                    if isinstance(reference, str)
                )
            )
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.REVIEWER_INVOCATION_COMPLETED,
                    stream_type="review_session",
                    stream_id=record.session_id,
                    session_id=record.session_id,
                    actor=EventActor(
                        type=EventActorType.REVIEWER,
                        id=record.reviewer_slot,
                    ),
                    stage=ReviewStage(record.stage),
                    round_number=record.round,
                    summary=summary,
                    payload={
                        "invocation_id": invocation_id,
                        "category": assessment_document.get("category"),
                        "material": assessment_document.get("material"),
                        "risk": assessment_document.get("risk"),
                        "assessment_schema_version": record.schema_version,
                        "claim_count": len(assessment_document.get("claims", [])),
                        "cross_review_disposition": assessment_payload.get(
                            "disposition"
                        ),
                        "peer_claim_review_count": len(
                            assessment_payload.get("peer_claim_reviews", [])
                        ),
                        "deterministic_fields": [
                            "material",
                            "tracking_health",
                            "optimization_eligible",
                            "primary_conversion",
                        ],
                    },
                    evidence_refs=tuple(
                        dict.fromkeys(
                            (*claim_evidence_refs, *peer_review_evidence_refs)
                        )
                    ),
                    confidence=assessment_document.get("confidence"),
                    correlation_id=record.session_id,
                    occurred_at=completed_at,
                ),
            )
            db.flush()
            return record

    def record_provider_attempts(
        self,
        *,
        invocation_id: str,
        attempts: tuple[ProviderAttempt, ...],
    ) -> tuple[ReviewerProviderAttemptRecord, ...]:
        if not attempts:
            return ()
        with self._sessions.begin() as db:
            invocation = db.scalar(
                select(ReviewerInvocationRecord)
                .where(ReviewerInvocationRecord.invocation_id == invocation_id)
                .with_for_update()
            )
            if invocation is None:
                raise LookupError(f"unknown reviewer invocation {invocation_id!r}")
            records: list[ReviewerProviderAttemptRecord] = []
            for attempt in attempts:
                attempt_id = deterministic_id(
                    "pat",
                    invocation_id,
                    attempt.attempt_number,
                )
                expected = {
                    "status": attempt.status,
                    "provider_request_id": attempt.provider_request_id,
                    "provider_response_id": attempt.provider_response_id,
                    "finish_status": attempt.finish_status,
                    "input_tokens": attempt.usage.input_tokens,
                    "cached_input_tokens": attempt.usage.cached_input_tokens,
                    "output_tokens": attempt.usage.output_tokens,
                    "reasoning_tokens": attempt.usage.reasoning_tokens,
                    "total_tokens": attempt.usage.total_tokens,
                    "latency_ms": attempt.latency_ms,
                    "cost_usd": attempt.usage.cost_usd,
                    "pricing_version": attempt.usage.pricing_version,
                    "error_type": attempt.error_type,
                    "error_message": attempt.error_message,
                    "started_at": attempt.started_at,
                    "completed_at": attempt.completed_at,
                }
                existing = db.get(ReviewerProviderAttemptRecord, attempt_id)
                if existing is not None:
                    scalar_fields = {
                        key
                        for key in expected
                        if key not in {"started_at", "completed_at"}
                    }
                    scalar_mismatch = any(
                        getattr(existing, key) != expected[key]
                        for key in scalar_fields
                    )
                    instant_mismatch = not same_instant(
                        existing.started_at,
                        attempt.started_at,
                    ) or not same_instant(
                        existing.completed_at,
                        attempt.completed_at,
                    )
                    if scalar_mismatch or instant_mismatch:
                        raise LedgerConflictError(
                            "provider attempt identity cannot be reused with new data"
                        )
                    records.append(existing)
                    continue
                record = ReviewerProviderAttemptRecord(
                    attempt_id=attempt_id,
                    invocation_id=invocation_id,
                    attempt_number=attempt.attempt_number,
                    **expected,
                )
                db.add(record)
                records.append(record)
                self._persist_event(
                    db,
                    PendingDomainEvent(
                        event_type=DomainEventType.PROVIDER_ATTEMPT_COMPLETED,
                        stream_type="review_session",
                        stream_id=invocation.session_id,
                        session_id=invocation.session_id,
                        actor=EventActor(
                            type=EventActorType.REVIEWER,
                            id=invocation.reviewer_slot,
                        ),
                        stage=ReviewStage(invocation.stage),
                        round_number=invocation.round,
                        summary=(
                            f"Reviewer {invocation.reviewer_slot} provider attempt "
                            f"{attempt.attempt_number} ended with "
                            f"{attempt.status.replace('_', ' ')}."
                        ),
                        payload={
                            "invocation_id": invocation_id,
                            "attempt_number": attempt.attempt_number,
                            "status": attempt.status,
                            "provider_request_id": attempt.provider_request_id,
                            "provider_response_id": attempt.provider_response_id,
                            "finish_status": attempt.finish_status,
                            "input_tokens": attempt.usage.input_tokens,
                            "output_tokens": attempt.usage.output_tokens,
                            "total_tokens": attempt.usage.total_tokens,
                            "latency_ms": attempt.latency_ms,
                            "cost_usd": attempt.usage.cost_usd,
                            "pricing_version": attempt.usage.pricing_version,
                            "error_type": attempt.error_type,
                        },
                        correlation_id=invocation.session_id,
                        occurred_at=attempt.completed_at,
                    ),
                )

            db.flush()
            ordered = list(
                db.scalars(
                    select(ReviewerProviderAttemptRecord)
                    .where(
                        ReviewerProviderAttemptRecord.invocation_id
                        == invocation_id
                    )
                    .order_by(ReviewerProviderAttemptRecord.attempt_number)
                )
            )
            last = ordered[-1]
            invocation.attempt_count = len(ordered)
            invocation.provider_request_id = last.provider_request_id
            invocation.provider_response_id = last.provider_response_id
            invocation.input_tokens = sum(item.input_tokens for item in ordered)
            invocation.cached_input_tokens = sum(
                item.cached_input_tokens for item in ordered
            )
            invocation.output_tokens = sum(item.output_tokens for item in ordered)
            invocation.reasoning_tokens = sum(
                item.reasoning_tokens for item in ordered
            )
            invocation.total_tokens = sum(item.total_tokens for item in ordered)
            invocation.latency_ms = sum(item.latency_ms for item in ordered)
            invocation.cost_usd = sum(item.cost_usd for item in ordered)
            invocation.finish_status = last.finish_status
            invocation.pricing_version = last.pricing_version
            db.flush()
            return tuple(ordered)

    def list_provider_attempts(
        self,
        invocation_id: str,
    ) -> tuple[ReviewerProviderAttemptRecord, ...]:
        with self._sessions() as db:
            return tuple(
                db.scalars(
                    select(ReviewerProviderAttemptRecord)
                    .where(
                        ReviewerProviderAttemptRecord.invocation_id == invocation_id
                    )
                    .order_by(ReviewerProviderAttemptRecord.attempt_number)
                )
            )

    def fail_invocation(
        self,
        *,
        invocation_id: str,
        error: str,
        completed_at: datetime,
    ) -> ReviewerInvocationRecord:
        with self._sessions.begin() as db:
            record = db.scalar(
                select(ReviewerInvocationRecord)
                .where(ReviewerInvocationRecord.invocation_id == invocation_id)
                .with_for_update()
            )
            if record is None:
                raise LookupError(f"unknown reviewer invocation {invocation_id!r}")
            if record.status != "pending":
                raise LedgerConflictError(f"cannot fail invocation in state {record.status!r}")
            record.status = "failed"
            record.last_error = error[:1000]
            record.completed_at = completed_at
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.REVIEWER_INVOCATION_FAILED,
                    stream_type="review_session",
                    stream_id=record.session_id,
                    session_id=record.session_id,
                    actor=EventActor(
                        type=EventActorType.REVIEWER,
                        id=record.reviewer_slot,
                    ),
                    stage=ReviewStage(record.stage),
                    round_number=record.round,
                    summary=f"Reviewer {record.reviewer_slot} failed to submit an assessment.",
                    payload={
                        "invocation_id": invocation_id,
                        "error": record.last_error,
                    },
                    correlation_id=record.session_id,
                    occurred_at=completed_at,
                ),
            )
            db.flush()
            return record

    def recover_cross_review(
        self,
        *,
        session_id: str,
        operator_id: str,
        reason: str,
        recovered_at: datetime,
    ) -> ReviewSessionRecord:
        if not operator_id.strip():
            raise ValueError("operator_id cannot be empty")
        if not reason.strip():
            raise ValueError("recovery reason cannot be empty")
        with self._sessions.begin() as db:
            session = db.scalar(
                select(ReviewSessionRecord)
                .where(ReviewSessionRecord.session_id == session_id)
                .with_for_update()
            )
            if session is None:
                raise LookupError(f"unknown review session {session_id!r}")
            source = ReviewState(session.current_state)
            try:
                validate_recovery_transition(source, ReviewState.CROSS_REVIEW)
            except ValueError as exc:
                raise ReviewRecoveryError(
                    f"review session cannot recover from {source.value!r}"
                ) from exc
            failed = list(
                db.scalars(
                    select(ReviewerInvocationRecord)
                    .where(
                        ReviewerInvocationRecord.session_id == session_id,
                        ReviewerInvocationRecord.stage
                        == ReviewStage.CROSS_REVIEW.value,
                        ReviewerInvocationRecord.status == "failed",
                    )
                    .with_for_update()
                )
            )
            if len(failed) != 1:
                raise ReviewRecoveryError(
                    "cross-review recovery requires exactly one failed invocation"
                )
            invocation = failed[0]
            invocation.status = "pending"
            invocation.last_error = None
            invocation.completed_at = None
            session.current_state = ReviewState.CROSS_REVIEW.value
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.STATE_TRANSITIONED,
                    stream_type="review_session",
                    stream_id=session_id,
                    session_id=session_id,
                    actor=EventActor(
                        type=EventActorType.OPERATOR,
                        id=operator_id,
                    ),
                    stage=ReviewStage.CROSS_REVIEW,
                    round_number=invocation.round,
                    summary=(
                        "An operator reopened cross review after a failed "
                        f"Reviewer {invocation.reviewer_slot} invocation."
                    ),
                    payload={
                        "source": source.value,
                        "target": ReviewState.CROSS_REVIEW.value,
                        "recovered_invocation_id": invocation.invocation_id,
                        "recovered_slot": invocation.reviewer_slot,
                        "reason": reason[:500],
                    },
                    correlation_id=session_id,
                    occurred_at=recovered_at,
                ),
            )
            db.flush()
            return session

    def transition_session(
        self,
        session_id: str,
        target: ReviewState,
    ) -> ReviewSessionRecord:
        with self._sessions.begin() as db:
            record = db.scalar(
                select(ReviewSessionRecord)
                .where(ReviewSessionRecord.session_id == session_id)
                .with_for_update()
            )
            if record is None:
                raise LookupError(f"unknown review session {session_id!r}")
            source = ReviewState(record.current_state)
            validate_transition(source, target)
            record.current_state = target.value
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.STATE_TRANSITIONED,
                    stream_type="review_session",
                    stream_id=session_id,
                    session_id=session_id,
                    actor=EventActor(type=EventActorType.SYSTEM, id="conclave"),
                    summary=state_transition_summary(target),
                    payload={"source": source.value, "target": target.value},
                    correlation_id=session_id,
                ),
            )
            db.flush()
            return record

    def record_request_validation(
        self,
        *,
        session_id: str,
        review_eligible: bool,
        optimization_eligible: bool,
        reasons: tuple[str, ...],
        material: bool,
        sufficient_volume: bool,
        cpa_deviation: float | None,
        evidence_age_hours: float,
    ) -> DomainEvent:
        payload = {
            "review_eligible": review_eligible,
            "optimization_eligible": optimization_eligible,
            "reasons": list(reasons),
            "material": material,
            "sufficient_volume": sufficient_volume,
            "cpa_deviation": cpa_deviation,
            "evidence_age_hours": evidence_age_hours,
        }
        with self._sessions.begin() as db:
            existing = db.scalar(
                select(AuditEventRecord).where(
                    AuditEventRecord.entity_type == "review_session",
                    AuditEventRecord.entity_id == session_id,
                    AuditEventRecord.event_type == DomainEventType.REQUEST_VALIDATED.value,
                )
            )
            if existing is not None:
                if existing.event_payload != payload:
                    raise LedgerConflictError(
                        "request validation is immutable for a review session"
                    )
                return self._to_domain_event(existing)
            record = self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.REQUEST_VALIDATED,
                    stream_type="review_session",
                    stream_id=session_id,
                    session_id=session_id,
                    actor=EventActor(type=EventActorType.SYSTEM, id="conclave"),
                    summary=(
                        "The request passed task-pack validation."
                        if review_eligible
                        else "The request is not eligible for reviewer execution."
                    ),
                    payload=payload,
                    correlation_id=session_id,
                ),
            )
            db.flush()
            return self._to_domain_event(record)

    def record_comparison(
        self,
        *,
        session_id: str,
        stage: ReviewStage,
        round_number: int,
        distance: float,
        weighted_distance: float,
        tolerance: float,
        dimension_distances: dict[str, float],
        hard_triggers: tuple[str, ...],
        requires_cross_review: bool,
        merge_compatible: bool,
        left_invocation_id: str,
        right_invocation_id: str,
        task_pack_hash: str,
    ) -> DomainEvent:
        summary = (
            "Reviewer comparison requires bounded cross review."
            if requires_cross_review
            else "Reviewer comparison completed within tolerance."
        )
        payload = {
            "distance": distance,
            "weighted_distance": weighted_distance,
            "tolerance": tolerance,
            "dimension_distances": dimension_distances,
            "hard_triggers": list(hard_triggers),
            "merge_compatible": merge_compatible,
            "requires_cross_review": requires_cross_review,
            "left_invocation_id": left_invocation_id,
            "right_invocation_id": right_invocation_id,
            "task_pack_hash": task_pack_hash,
        }
        with self._sessions.begin() as db:
            existing = db.scalar(
                select(AuditEventRecord).where(
                    AuditEventRecord.entity_type == "review_session",
                    AuditEventRecord.entity_id == session_id,
                    AuditEventRecord.event_type == DomainEventType.COMPARISON_COMPLETED.value,
                    AuditEventRecord.stage == stage.value,
                    AuditEventRecord.round_number == round_number,
                )
            )
            if existing is not None:
                if existing.event_payload != payload:
                    raise LedgerConflictError(
                        "comparison is immutable for a review stage and round"
                    )
                return self._to_domain_event(existing)
            record = self._persist_event(
                db,
                PendingDomainEvent(
                event_type=DomainEventType.COMPARISON_COMPLETED,
                stream_type="review_session",
                stream_id=session_id,
                session_id=session_id,
                actor=EventActor(type=EventActorType.SYSTEM, id="conclave"),
                stage=stage,
                round_number=round_number,
                summary=summary,
                payload=payload,
                correlation_id=session_id,
                ),
            )
            db.flush()
            return self._to_domain_event(record)

    def get_session(self, session_id: str) -> ReviewSessionRecord | None:
        with self._sessions() as db:
            return db.get(ReviewSessionRecord, session_id)

    def get_snapshot(self, session_id: str) -> RequestSnapshotRecord | None:
        with self._sessions() as db:
            return db.scalar(
                select(RequestSnapshotRecord).where(RequestSnapshotRecord.session_id == session_id)
            )

    def list_invocations(self, session_id: str) -> list[ReviewerInvocationRecord]:
        with self._sessions() as db:
            return list(
                db.scalars(
                    select(ReviewerInvocationRecord)
                    .where(ReviewerInvocationRecord.session_id == session_id)
                    .order_by(
                        ReviewerInvocationRecord.created_at,
                        ReviewerInvocationRecord.invocation_id,
                    )
                )
            )

    def record_result(
        self,
        *,
        session_id: str,
        path: str,
        document: dict[str, Any],
    ) -> ReviewResultRecord:
        result_hash = canonical_hash(document)
        result_id = deterministic_id("result", session_id)
        with self._sessions.begin() as db:
            existing = db.scalar(
                select(ReviewResultRecord).where(ReviewResultRecord.session_id == session_id)
            )
            if existing is not None:
                if existing.result_hash != result_hash or existing.path != path:
                    raise LedgerConflictError("review result is immutable")
                return existing
            record = ReviewResultRecord(
                result_id=result_id,
                session_id=session_id,
                path=path,
                status=document["status"],
                contract_version=document["contract_version"],
                result_hash=result_hash,
                document=document,
            )
            db.add(record)
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.RESULT_RECORDED,
                    stream_type="review_session",
                    stream_id=session_id,
                    session_id=session_id,
                    actor=EventActor(type=EventActorType.SYSTEM, id="conclave"),
                    summary="The structured review result was created.",
                    payload={
                        "result_id": result_id,
                        "result_hash": result_hash,
                        "status": document["status"],
                        "path": path,
                        "category": document["recommendation"]["category"],
                    },
                    confidence=document.get("confidence"),
                    correlation_id=session_id,
                ),
            )
            db.flush()
            return record

    def get_result(self, session_id: str) -> ReviewResultRecord | None:
        with self._sessions() as db:
            return db.scalar(
                select(ReviewResultRecord).where(ReviewResultRecord.session_id == session_id)
            )

    def register_process(
        self,
        *,
        process_id: str,
        process_type: str,
        now: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeProcessRecord:
        with self._sessions.begin() as db:
            record = db.scalar(
                select(RuntimeProcessRecord)
                .where(RuntimeProcessRecord.process_id == process_id)
                .with_for_update()
            )
            if record is None:
                record = RuntimeProcessRecord(
                    process_id=process_id,
                    process_type=process_type,
                    status="running",
                    started_at=now,
                    heartbeat_at=now,
                    process_metadata=metadata or {},
                )
                db.add(record)
            else:
                record.process_type = process_type
                record.status = "running"
                record.started_at = now
                record.heartbeat_at = now
                record.stopped_at = None
                record.process_metadata = metadata or {}
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.PROCESS_STARTED,
                    stream_type="runtime_process",
                    stream_id=process_id,
                    actor=EventActor(type=EventActorType.SYSTEM, id=process_id),
                    summary=f"The Conclave {process_type} process started.",
                    payload={"process_type": process_type},
                    occurred_at=now,
                ),
            )
            db.flush()
            return record

    def heartbeat_process(
        self,
        *,
        process_id: str,
        now: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeProcessRecord:
        with self._sessions.begin() as db:
            record = db.scalar(
                select(RuntimeProcessRecord)
                .where(RuntimeProcessRecord.process_id == process_id)
                .with_for_update()
            )
            if record is None:
                raise LookupError(f"unknown runtime process {process_id!r}")
            if record.status != "running":
                raise RuntimeError(f"cannot heartbeat process in state {record.status!r}")
            record.heartbeat_at = now
            if metadata is not None:
                record.process_metadata = metadata
            db.flush()
            return record

    def stop_process(
        self,
        *,
        process_id: str,
        now: datetime,
    ) -> RuntimeProcessRecord:
        with self._sessions.begin() as db:
            record = db.scalar(
                select(RuntimeProcessRecord)
                .where(RuntimeProcessRecord.process_id == process_id)
                .with_for_update()
            )
            if record is None:
                raise LookupError(f"unknown runtime process {process_id!r}")
            record.status = "stopped"
            record.heartbeat_at = now
            record.stopped_at = now
            self._persist_event(
                db,
                PendingDomainEvent(
                    event_type=DomainEventType.PROCESS_STOPPED,
                    stream_type="runtime_process",
                    stream_id=process_id,
                    actor=EventActor(type=EventActorType.SYSTEM, id=process_id),
                    summary=f"The Conclave {record.process_type} process stopped.",
                    payload={"process_type": record.process_type},
                    occurred_at=now,
                ),
            )
            db.flush()
            return record

    def list_processes(self) -> list[RuntimeProcessRecord]:
        with self._sessions() as db:
            return list(
                db.scalars(
                    select(RuntimeProcessRecord).order_by(
                        RuntimeProcessRecord.process_type,
                        RuntimeProcessRecord.process_id,
                    )
                )
            )

    def stale_processes(
        self,
        *,
        now: datetime,
        stale_after_seconds: int,
    ) -> list[RuntimeProcessRecord]:
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        threshold = now - timedelta(seconds=stale_after_seconds)
        with self._sessions() as db:
            return list(
                db.scalars(
                    select(RuntimeProcessRecord)
                    .where(
                        RuntimeProcessRecord.status == "running",
                        RuntimeProcessRecord.heartbeat_at < threshold,
                    )
                    .order_by(RuntimeProcessRecord.heartbeat_at, RuntimeProcessRecord.process_id)
                )
            )

    def audit_events(self, entity_type: str, entity_id: str) -> list[AuditEventRecord]:
        with self._sessions() as db:
            return list(
                db.scalars(
                    select(AuditEventRecord)
                    .where(
                        AuditEventRecord.entity_type == entity_type,
                        AuditEventRecord.entity_id == entity_id,
                    )
                    .order_by(AuditEventRecord.event_index)
                )
            )

    def append_domain_event(self, event: PendingDomainEvent) -> DomainEvent:
        """Append a standalone typed event for a domain service."""
        with self._sessions.begin() as db:
            record = self._persist_event(db, event)
            db.flush()
            return self._to_domain_event(record)

    def list_events(
        self,
        stream_id: str,
        *,
        stream_type: str = "review_session",
        after_sequence: int = 0,
        limit: int = 100,
    ) -> list[DomainEvent]:
        if after_sequence < 0:
            raise ValueError("after_sequence cannot be negative")
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        with self._sessions() as db:
            records = list(
                db.scalars(
                    select(AuditEventRecord)
                    .where(
                        AuditEventRecord.entity_type == stream_type,
                        AuditEventRecord.entity_id == stream_id,
                        AuditEventRecord.event_index > after_sequence,
                    )
                    .order_by(AuditEventRecord.event_index)
                    .limit(limit)
                )
            )
            return [self._to_domain_event(record) for record in records]

    def register_event_subscriber(
        self,
        *,
        subscriber_id: str,
        stream_type: str | None = None,
    ) -> EventSubscriptionRecord:
        with self._sessions.begin() as db:
            existing = db.get(EventSubscriptionRecord, subscriber_id)
            if existing is not None:
                if existing.stream_type != stream_type:
                    raise LedgerConflictError(
                        "subscriber stream filter cannot change after registration"
                    )
                return existing
            record = EventSubscriptionRecord(
                subscriber_id=subscriber_id,
                stream_type=stream_type,
                status="active",
            )
            db.add(record)
            db.flush()
            return record

    def list_unpublished_events(
        self,
        *,
        subscriber_id: str,
        limit: int = 100,
    ) -> list[DomainEvent]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        with self._sessions.begin() as db:
            subscription = db.get(EventSubscriptionRecord, subscriber_id)
            if subscription is None:
                raise LookupError(f"unknown event subscriber {subscriber_id!r}")
            self._backfill_event_deliveries(db, subscription)
            records = list(
                db.scalars(
                    select(AuditEventRecord)
                    .join(
                        EventDeliveryRecord,
                        EventDeliveryRecord.event_id == AuditEventRecord.event_id,
                    )
                    .where(
                        EventDeliveryRecord.subscriber_id == subscriber_id,
                        EventDeliveryRecord.status != "delivered",
                    )
                    .order_by(AuditEventRecord.audit_event_id)
                    .limit(limit)
                )
            )
            return [self._to_domain_event(record) for record in records]

    def claim_next_event_delivery(
        self,
        *,
        subscriber_id: str,
        worker_id: str,
        now: datetime,
        lease_seconds: int = 60,
    ) -> tuple[DomainEvent, EventDeliveryRecord] | None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        with self._sessions.begin() as db:
            subscription = db.get(EventSubscriptionRecord, subscriber_id)
            if subscription is None:
                raise LookupError(f"unknown event subscriber {subscriber_id!r}")
            if subscription.status != "active":
                return None
            self._backfill_event_deliveries(db, subscription, available_at=now)

            earlier_delivery = aliased(EventDeliveryRecord)
            earlier_event = aliased(AuditEventRecord)
            earlier_undelivered = (
                select(1)
                .select_from(earlier_delivery)
                .join(earlier_event, earlier_event.event_id == earlier_delivery.event_id)
                .where(
                    earlier_delivery.subscriber_id == subscriber_id,
                    earlier_delivery.status != "delivered",
                    earlier_event.entity_type == AuditEventRecord.entity_type,
                    earlier_event.entity_id == AuditEventRecord.entity_id,
                    earlier_event.event_index < AuditEventRecord.event_index,
                )
            )
            row = db.execute(
                select(EventDeliveryRecord, AuditEventRecord)
                .join(
                    AuditEventRecord,
                    AuditEventRecord.event_id == EventDeliveryRecord.event_id,
                )
                .where(
                    EventDeliveryRecord.subscriber_id == subscriber_id,
                    or_(
                        (
                            EventDeliveryRecord.status.in_(("pending", "retry"))
                            & (EventDeliveryRecord.available_at <= now)
                        ),
                        (
                            (EventDeliveryRecord.status == "claimed")
                            & (EventDeliveryRecord.lease_expires_at <= now)
                        ),
                    ),
                    ~exists(earlier_undelivered),
                )
                .order_by(AuditEventRecord.audit_event_id)
                .limit(1)
                .with_for_update(skip_locked=True, of=EventDeliveryRecord)
            ).first()
            if row is None:
                return None
            delivery, event_record = row
            delivery.status = "claimed"
            delivery.claimed_by = worker_id
            delivery.claimed_at = now
            delivery.lease_expires_at = now + timedelta(seconds=lease_seconds)
            delivery.attempts += 1
            db.flush()
            return self._to_domain_event(event_record), delivery

    def complete_event_delivery(
        self,
        *,
        subscriber_id: str,
        event_id: str,
        worker_id: str,
        now: datetime,
    ) -> EventDeliveryRecord:
        with self._sessions.begin() as db:
            record = db.scalar(
                select(EventDeliveryRecord)
                .where(
                    EventDeliveryRecord.subscriber_id == subscriber_id,
                    EventDeliveryRecord.event_id == event_id,
                )
                .with_for_update()
            )
            if record is None:
                raise LookupError(f"unknown event delivery {subscriber_id!r}/{event_id!r}")
            if record.status != "claimed" or record.claimed_by != worker_id:
                raise EventDeliveryClaimError(
                    "only the active event-delivery lease holder may complete delivery"
                )
            if record.lease_expires_at is not None and normalize_instant(
                record.lease_expires_at
            ) < normalize_instant(now):
                raise EventDeliveryClaimError("event-delivery lease has expired")
            record.status = "delivered"
            record.delivered_at = now
            record.claimed_by = None
            record.claimed_at = None
            record.lease_expires_at = None
            record.last_error = None
            db.flush()
            return record

    def fail_event_delivery(
        self,
        *,
        subscriber_id: str,
        event_id: str,
        worker_id: str,
        now: datetime,
        error: str,
        retry_delay_seconds: int = 30,
    ) -> EventDeliveryRecord:
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        with self._sessions.begin() as db:
            record = db.scalar(
                select(EventDeliveryRecord)
                .where(
                    EventDeliveryRecord.subscriber_id == subscriber_id,
                    EventDeliveryRecord.event_id == event_id,
                )
                .with_for_update()
            )
            if record is None:
                raise LookupError(f"unknown event delivery {subscriber_id!r}/{event_id!r}")
            if record.status != "claimed" or record.claimed_by != worker_id:
                raise EventDeliveryClaimError(
                    "only the active event-delivery lease holder may fail delivery"
                )
            record.status = "retry"
            record.available_at = now + timedelta(seconds=retry_delay_seconds)
            record.claimed_by = None
            record.claimed_at = None
            record.lease_expires_at = None
            record.last_error = error[:1000]
            db.flush()
            return record

    def get_event_delivery(
        self,
        *,
        subscriber_id: str,
        event_id: str,
    ) -> EventDeliveryRecord | None:
        with self._sessions() as db:
            return db.get(
                EventDeliveryRecord,
                {"subscriber_id": subscriber_id, "event_id": event_id},
            )

    def _backfill_event_deliveries(
        self,
        db: Session,
        subscription: EventSubscriptionRecord,
        *,
        available_at: datetime | None = None,
    ) -> None:
        query = select(AuditEventRecord.event_id)
        if subscription.stream_type is not None:
            query = query.where(AuditEventRecord.entity_type == subscription.stream_type)
        event_ids = list(db.scalars(query))
        if not event_ids:
            return
        now = available_at or datetime.now(UTC)
        values = [
            {
                "subscriber_id": subscription.subscriber_id,
                "event_id": event_id,
                "status": "pending",
                "attempts": 0,
                "available_at": now,
                "created_at": now,
                "updated_at": now,
            }
            for event_id in event_ids
        ]
        table = EventDeliveryRecord.__table__
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            statement = postgresql_insert(table).values(values).on_conflict_do_nothing()
        elif dialect == "sqlite":
            statement = sqlite_insert(table).values(values).on_conflict_do_nothing()
        else:
            existing = {
                event_id
                for event_id in db.scalars(
                    select(EventDeliveryRecord.event_id).where(
                        EventDeliveryRecord.subscriber_id == subscription.subscriber_id
                    )
                )
            }
            db.add_all(
                EventDeliveryRecord(**value)
                for value in values
                if value["event_id"] not in existing
            )
            return
        db.execute(statement)

    def _persist_event(
        self,
        db: Session,
        pending: PendingDomainEvent,
    ) -> AuditEventRecord:
        occurred_at = pending.occurred_at or datetime.now(UTC)
        sequence = self._next_event_sequence(
            db,
            stream_type=pending.stream_type,
            stream_id=pending.stream_id,
            now=occurred_at,
        )
        previous_event_id = db.scalar(
            select(AuditEventRecord.event_id).where(
                AuditEventRecord.entity_type == pending.stream_type,
                AuditEventRecord.entity_id == pending.stream_id,
                AuditEventRecord.event_index == sequence - 1,
            )
        )
        event_id = deterministic_id(
            "evt",
            pending.stream_type,
            pending.stream_id,
            sequence,
            pending.event_type.value,
        )
        record = AuditEventRecord(
            event_id=event_id,
            entity_type=pending.stream_type,
            entity_id=pending.stream_id,
            session_id=pending.session_id,
            event_index=sequence,
            event_type=pending.event_type.value,
            actor_type=pending.actor.type.value if pending.actor else None,
            actor_id=pending.actor.id if pending.actor else None,
            stage=pending.stage.value if pending.stage else None,
            round_number=pending.round_number,
            summary=pending.summary,
            event_payload=pending.payload,
            evidence_refs=list(pending.evidence_refs),
            confidence=pending.confidence,
            correlation_id=(pending.correlation_id or pending.session_id or pending.stream_id),
            causation_id=pending.causation_id or previous_event_id,
            schema_version=pending.schema_version,
            occurred_at=occurred_at,
        )
        db.add(record)
        return record

    @staticmethod
    def _next_event_sequence(
        db: Session,
        *,
        stream_type: str,
        stream_id: str,
        now: datetime,
    ) -> int:
        table = EventStreamRecord.__table__
        values = {
            "stream_type": stream_type,
            "stream_id": stream_id,
            "last_sequence": 0,
            "created_at": now,
            "updated_at": now,
        }
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            db.execute(
                postgresql_insert(table)
                .values(values)
                .on_conflict_do_nothing(index_elements=["stream_type", "stream_id"])
            )
        elif dialect == "sqlite":
            db.execute(
                sqlite_insert(table)
                .values(values)
                .on_conflict_do_nothing(index_elements=["stream_type", "stream_id"])
            )
        else:
            record = db.get(
                EventStreamRecord,
                {"stream_type": stream_type, "stream_id": stream_id},
            )
            if record is None:
                db.add(EventStreamRecord(**values))
                db.flush()
        sequence = db.scalar(
            update(EventStreamRecord)
            .where(
                EventStreamRecord.stream_type == stream_type,
                EventStreamRecord.stream_id == stream_id,
            )
            .values(
                last_sequence=EventStreamRecord.last_sequence + 1,
                updated_at=now,
            )
            .returning(EventStreamRecord.last_sequence)
        )
        if sequence is None:
            raise RuntimeError("failed to allocate an event-stream sequence")
        return sequence

    @staticmethod
    def _to_domain_event(record: AuditEventRecord) -> DomainEvent:
        actor = None
        if record.actor_type is not None and record.actor_id is not None:
            actor = EventActor(
                type=EventActorType(record.actor_type),
                id=record.actor_id,
            )
        return DomainEvent(
            event_id=record.event_id,
            stream_type=record.entity_type,
            stream_id=record.entity_id,
            session_id=record.session_id,
            sequence=record.event_index,
            occurred_at=record.occurred_at,
            event_type=DomainEventType(record.event_type),
            actor=actor,
            stage=ReviewStage(record.stage) if record.stage else None,
            round_number=record.round_number,
            summary=record.summary,
            evidence_refs=tuple(record.evidence_refs),
            confidence=record.confidence,
            payload=record.event_payload,
            correlation_id=record.correlation_id,
            causation_id=record.causation_id,
            schema_version=record.schema_version,
        )
