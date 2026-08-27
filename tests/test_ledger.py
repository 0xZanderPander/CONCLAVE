import json
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from conclave.domain.enums import (
    ReviewerSlot,
    ReviewerType,
    ReviewStage,
    ReviewState,
)
from conclave.domain.models import RequestIdentity, ReviewTrigger
from conclave.ledger.models import (
    ImmutableLedgerRecordError,
    PinnedSessionIdentityError,
    ReviewerProviderAttemptRecord,
    ReviewerSlotRecord,
    ReviewPlanRevisionRecord,
    ReviewSessionRecord,
)
from conclave.ledger.repository import (
    LedgerConflictError,
    LedgerRepository,
    create_schema,
)
from conclave.paths import design_fixtures_root
from conclave.plans.models import ReviewPlanRevision
from conclave.reviewers.runtime import ProviderAttempt, ProviderUsage


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    create_schema(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def _revision() -> ReviewPlanRevision:
    with (design_fixtures_root() / "review-plan-revision.json").open(encoding="utf-8") as source:
        fixture = json.load(source)
    item = fixture["revisions"][-1]
    return ReviewPlanRevision.model_validate(
        {
            "plan_id": fixture["plan_id"],
            "deployment_id": fixture["deployment_id"],
            **item,
        }
    )


def _identity(revision: ReviewPlanRevision) -> RequestIdentity:
    return RequestIdentity(
        caller_id="sample-harness",
        idempotency_key="sample-review-1",
        evidence_version="ev-1",
        plan_id=revision.plan_id,
        plan_revision=revision.revision,
        trigger=ReviewTrigger(
            occurrence_id="occ-sample-1",
            kind="scheduled_a",
            due_at=datetime.fromisoformat("2026-07-24T12:00:00+00:00"),
        ),
    )


def _prepare(repository: LedgerRepository) -> tuple[ReviewPlanRevision, RequestIdentity]:
    revision = _revision()
    identity = _identity(revision)
    repository.add_plan_revision(revision)
    repository.add_occurrence(
        occurrence_id=identity.trigger.occurrence_id,
        plan_id=identity.plan_id,
        plan_revision=identity.plan_revision,
        due_at=identity.trigger.due_at,
        trigger_kind=identity.trigger.kind.value,
    )
    return revision, identity


def test_session_and_snapshot_are_idempotent(
    session_factory: sessionmaker[Session],
) -> None:
    repository = LedgerRepository(session_factory)
    _, identity = _prepare(repository)

    first = repository.create_session(identity)
    second = repository.create_session(identity)
    first_snapshot = repository.store_snapshot(
        session_id=first.session_id,
        content={"sample": 1},
    )
    second_snapshot = repository.store_snapshot(
        session_id=first.session_id,
        content={"sample": 1},
    )

    assert first.session_id == second.session_id
    assert first_snapshot.snapshot_id == second_snapshot.snapshot_id

    with pytest.raises(LedgerConflictError):
        repository.store_snapshot(
            session_id=first.session_id,
            content={"sample": 2},
        )


def test_session_transitions_append_ordered_audit_events(
    session_factory: sessionmaker[Session],
) -> None:
    repository = LedgerRepository(session_factory)
    _, identity = _prepare(repository)
    review_session = repository.create_session(identity)

    repository.transition_session(review_session.session_id, ReviewState.VALIDATED)
    repository.transition_session(review_session.session_id, ReviewState.SNAPSHOTTED)

    events = repository.audit_events("review_session", review_session.session_id)
    assert [event.event_index for event in events] == [1, 2, 3]
    assert [event.event_type for event in events] == [
        "session_created",
        "state_transitioned",
        "state_transitioned",
    ]


def test_invocation_identity_is_unique(
    session_factory: sessionmaker[Session],
) -> None:
    repository = LedgerRepository(session_factory)
    _, identity = _prepare(repository)
    review_session = repository.create_session(identity)
    snapshot = repository.store_snapshot(
        session_id=review_session.session_id,
        content={"sample": 1},
    )

    arguments = {
        "session_id": review_session.session_id,
        "slot": ReviewerSlot.A,
        "reviewer_type": ReviewerType.MODEL,
        "stage": ReviewStage.INDEPENDENT,
        "round_number": 1,
        "snapshot_hash": snapshot.content_hash,
        "prompt_version": "p1",
        "schema_version": "v1",
        "provider": "fake",
        "model": "fixture",
    }
    first = repository.record_invocation(**arguments)
    second = repository.record_invocation(**arguments)

    assert first.invocation_id == second.invocation_id

    with pytest.raises(LedgerConflictError):
        repository.record_invocation(**{**arguments, "prompt_version": "p2"})


def test_provider_attempts_are_immutable_and_update_invocation_telemetry(
    session_factory: sessionmaker[Session],
) -> None:
    repository = LedgerRepository(session_factory)
    _, identity = _prepare(repository)
    review_session = repository.create_session(identity)
    snapshot = repository.store_snapshot(
        session_id=review_session.session_id,
        content={"sample": 1},
    )
    invocation = repository.record_invocation(
        session_id=review_session.session_id,
        slot=ReviewerSlot.A,
        reviewer_type=ReviewerType.MODEL,
        stage=ReviewStage.INDEPENDENT,
        round_number=1,
        snapshot_hash=snapshot.content_hash,
        prompt_version="p1",
        schema_version="v1",
        provider="openai",
        model="gpt-test",
    )
    now = datetime.now(UTC)
    attempt = ProviderAttempt(
        attempt_number=1,
        status="succeeded",
        started_at=now,
        completed_at=now,
        latency_ms=125,
        provider_request_id="req_test",
        provider_response_id="resp_test",
        finish_status="completed",
        usage=ProviderUsage(
            input_tokens=100,
            cached_input_tokens=10,
            output_tokens=25,
            reasoning_tokens=5,
            total_tokens=125,
            cost_usd=0.002,
            pricing_version="test-v1",
        ),
    )

    first = repository.record_provider_attempts(
        invocation_id=invocation.invocation_id,
        attempts=(attempt,),
    )
    second = repository.record_provider_attempts(
        invocation_id=invocation.invocation_id,
        attempts=(attempt,),
    )
    stored_invocation = repository.list_invocations(review_session.session_id)[0]

    assert first[0].attempt_id == second[0].attempt_id
    assert stored_invocation.attempt_count == 1
    assert stored_invocation.total_tokens == 125
    assert stored_invocation.cost_usd == 0.002
    assert stored_invocation.provider_response_id == "resp_test"
    metrics = repository.provider_metrics()
    assert metrics.counts == {"succeeded": 1}
    assert metrics.total_tokens == 125
    assert metrics.total_cost_usd == 0.002
    assert metrics.average_latency_ms == 125
    assert metrics.last_completed_at is not None
    assert [event.event_type for event in repository.list_events(review_session.session_id)] == [
        "session_created",
        "snapshot_stored",
        "reviewer_invocation_created",
        "provider_attempt_completed",
    ]

    changed = attempt.model_copy(update={"latency_ms": 126})
    with pytest.raises(LedgerConflictError):
        repository.record_provider_attempts(
            invocation_id=invocation.invocation_id,
            attempts=(changed,),
        )

    with session_factory() as db:
        record = db.get(ReviewerProviderAttemptRecord, first[0].attempt_id)
        assert record is not None
        record.status = "permanent_failure"
        with pytest.raises(ImmutableLedgerRecordError):
            db.commit()


def test_occurrence_id_cannot_be_reused_for_a_new_schedule(
    session_factory: sessionmaker[Session],
) -> None:
    repository = LedgerRepository(session_factory)
    revision, identity = _prepare(repository)

    with pytest.raises(LedgerConflictError):
        repository.add_occurrence(
            occurrence_id=identity.trigger.occurrence_id,
            plan_id=revision.plan_id,
            plan_revision=revision.revision,
            due_at=datetime.fromisoformat("2026-07-24T16:00:00+00:00"),
            trigger_kind="scheduled_b",
        )


def test_plan_revisions_are_immutable(
    session_factory: sessionmaker[Session],
) -> None:
    repository = LedgerRepository(session_factory)
    revision, _ = _prepare(repository)

    with session_factory() as db:
        record = db.scalar(
            select(ReviewPlanRevisionRecord).where(
                ReviewPlanRevisionRecord.plan_id == revision.plan_id,
                ReviewPlanRevisionRecord.revision == revision.revision,
            )
        )
        assert record is not None
        record.paused = True
        with pytest.raises(ImmutableLedgerRecordError):
            db.commit()


def test_existing_plan_revision_cannot_be_redefined(
    session_factory: sessionmaker[Session],
) -> None:
    repository = LedgerRepository(session_factory)
    revision = _revision()
    repository.add_plan_revision(revision)

    with pytest.raises(LedgerConflictError):
        repository.add_plan_revision(revision.model_copy(update={"paused": True}))


def test_plan_revision_persists_exactly_three_versioned_slots(
    session_factory: sessionmaker[Session],
) -> None:
    repository = LedgerRepository(session_factory)
    revision = _revision()
    repository.add_plan_revision(revision)

    with session_factory() as db:
        slots = list(
            db.scalars(
                select(ReviewerSlotRecord)
                .where(
                    ReviewerSlotRecord.plan_id == revision.plan_id,
                    ReviewerSlotRecord.plan_revision == revision.revision,
                )
                .order_by(ReviewerSlotRecord.slot)
            )
        )

    assert [slot.slot for slot in slots] == ["A", "B", "C"]
    assert all(slot.role_version == "role-v1" for slot in slots)


def test_open_session_cannot_change_plan_revision(
    session_factory: sessionmaker[Session],
) -> None:
    repository = LedgerRepository(session_factory)
    _, identity = _prepare(repository)
    review_session = repository.create_session(identity)

    with session_factory() as db:
        record = db.get(ReviewSessionRecord, review_session.session_id)
        assert record is not None
        record.plan_revision = 99
        with pytest.raises(PinnedSessionIdentityError):
            db.commit()
