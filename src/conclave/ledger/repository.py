import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from conclave.domain.enums import ReviewerSlot, ReviewerType, ReviewStage, ReviewState
from conclave.domain.models import RequestIdentity
from conclave.ledger.models import (
    AuditEventRecord,
    Base,
    RequestSnapshotRecord,
    ReviewerInvocationRecord,
    ReviewerSlotRecord,
    ReviewOccurrenceRecord,
    ReviewPlanRecord,
    ReviewPlanRevisionRecord,
    ReviewResultRecord,
    ReviewSessionRecord,
    RuntimeProcessRecord,
    SchedulerWorkItemRecord,
)
from conclave.orchestration.state_machine import validate_transition
from conclave.plans.models import ReviewPlanRevision


class LedgerConflictError(RuntimeError):
    pass


class WorkItemClaimError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class QueueMetrics:
    counts: dict[str, int]
    oldest_claimable_at: datetime | None
    expired_leases: int


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
            self._append_event(
                db,
                entity_type="review_plan_revision",
                entity_id=revision_id,
                event_type="plan_revision_created",
                payload={"content_hash": record.content_hash},
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
            self._append_event(
                db,
                entity_type="review_occurrence",
                entity_id=occurrence_id,
                event_type="occurrence_created",
                payload={"trigger_kind": trigger_kind, "due_at": due_at.isoformat()},
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
            self._append_event(
                db,
                entity_type="scheduler_work_item",
                entity_id=work_item_id,
                event_type="work_item_enqueued",
                payload={"occurrence_id": occurrence_id, "due_at": due_at.isoformat()},
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
            self._append_event(
                db,
                entity_type="scheduler_work_item",
                entity_id=record.work_item_id,
                event_type="work_item_claimed",
                payload={
                    "worker_id": worker_id,
                    "lease_expires_at": record.lease_expires_at.isoformat(),
                    "attempt": record.attempts,
                },
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
            self._append_event(
                db,
                entity_type="scheduler_work_item",
                entity_id=work_item_id,
                event_type="work_item_completed",
                payload={"worker_id": worker_id},
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
            self._append_event(
                db,
                entity_type="scheduler_work_item",
                entity_id=work_item_id,
                event_type=(
                    "work_item_dead_lettered" if dead_lettered else "work_item_retry_scheduled"
                ),
                payload={
                    "worker_id": worker_id,
                    "error": record.last_error,
                    "attempt": record.attempts,
                    "max_attempts": record.max_attempts,
                    "available_at": (None if dead_lettered else record.available_at.isoformat()),
                },
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
            self._append_event(
                db,
                entity_type="scheduler_work_item",
                entity_id=work_item_id,
                event_type="work_item_lease_extended",
                payload={
                    "worker_id": worker_id,
                    "lease_expires_at": record.lease_expires_at.isoformat(),
                },
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
            self._append_event(
                db,
                entity_type="scheduler_work_item",
                entity_id=work_item_id,
                event_type="work_item_manual_retry",
                payload={
                    "additional_attempts": additional_attempts,
                    "max_attempts": record.max_attempts,
                },
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
            self._append_event(
                db,
                entity_type="scheduler_work_item",
                entity_id=work_item_id,
                event_type="work_item_cancelled",
                payload={"reason": record.last_error},
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

    def create_session(self, identity: RequestIdentity) -> ReviewSessionRecord:
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
                return existing
            record = ReviewSessionRecord(
                session_id=session_id,
                caller_id=identity.caller_id,
                occurrence_id=identity.trigger.occurrence_id,
                idempotency_key=identity.idempotency_key,
                evidence_version=identity.evidence_version,
                plan_id=identity.plan_id,
                plan_revision=identity.plan_revision,
                current_state=ReviewState.REQUESTED.value,
            )
            db.add(record)
            self._append_event(
                db,
                entity_type="review_session",
                entity_id=session_id,
                event_type="session_created",
                payload={"state": ReviewState.REQUESTED.value},
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
            self._append_event(
                db,
                entity_type="review_session",
                entity_id=session_id,
                event_type="snapshot_stored",
                payload={"snapshot_id": snapshot_id, "content_hash": content_hash},
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
            self._append_event(
                db,
                entity_type="review_session",
                entity_id=session_id,
                event_type="reviewer_invocation_created",
                payload={
                    "invocation_id": invocation_id,
                    "slot": slot.value,
                    "stage": stage.value,
                    "round": round_number,
                },
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
            self._append_event(
                db,
                entity_type="review_session",
                entity_id=record.session_id,
                event_type="reviewer_invocation_completed",
                payload={"invocation_id": invocation_id},
            )
            db.flush()
            return record

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
            self._append_event(
                db,
                entity_type="review_session",
                entity_id=record.session_id,
                event_type="reviewer_invocation_failed",
                payload={"invocation_id": invocation_id, "error": record.last_error},
            )
            db.flush()
            return record

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
            self._append_event(
                db,
                entity_type="review_session",
                entity_id=session_id,
                event_type="state_transitioned",
                payload={"source": source.value, "target": target.value},
            )
            db.flush()
            return record

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
            self._append_event(
                db,
                entity_type="review_session",
                entity_id=session_id,
                event_type="result_recorded",
                payload={
                    "result_id": result_id,
                    "result_hash": result_hash,
                    "status": document["status"],
                    "path": path,
                },
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
            self._append_event(
                db,
                entity_type="runtime_process",
                entity_id=process_id,
                event_type="process_started",
                payload={"process_type": process_type},
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
            self._append_event(
                db,
                entity_type="runtime_process",
                entity_id=process_id,
                event_type="process_stopped",
                payload={"process_type": record.process_type},
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

    @staticmethod
    def _append_event(
        db: Session,
        *,
        entity_type: str,
        entity_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> AuditEventRecord:
        current = db.scalar(
            select(func.max(AuditEventRecord.event_index)).where(
                AuditEventRecord.entity_type == entity_type,
                AuditEventRecord.entity_id == entity_id,
            )
        )
        record = AuditEventRecord(
            entity_type=entity_type,
            entity_id=entity_id,
            event_index=(current or 0) + 1,
            event_type=event_type,
            event_payload=payload,
        )
        db.add(record)
        return record
