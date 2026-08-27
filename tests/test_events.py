from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from conclave.domain.enums import ReviewStage, ReviewState
from conclave.events.models import (
    DomainEventType,
    EventActor,
    EventActorType,
    PendingDomainEvent,
)
from conclave.events.publishing import (
    EventDispatcher,
    InMemoryEventPublisher,
    NoOpEventPublisher,
)
from conclave.fixtures import load_design_plan_revisions, load_request_fixture
from conclave.intake import ReviewIntakeService
from conclave.ledger.models import AuditEventRecord, ImmutableLedgerRecordError
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.development import DevelopmentReviewerRuntime
from tests.helpers import create_test_engine, create_test_repository


def _completed_review(path: FixturePath = FixturePath.C_TIE_BROKEN) -> tuple:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    for revision in load_design_plan_revisions():
        repository.add_plan_revision(revision)
    accepted = ReviewIntakeService(repository).accept(
        load_request_fixture("04-surviving-reviewer-conflict.json")
    )
    ReviewOrchestrator(repository, DevelopmentReviewerRuntime()).run_fixture_path(
        accepted.session_id,
        path,
        now=datetime.now(UTC),
    )
    return engine, repository, accepted


def test_review_event_envelope_is_typed_stable_ordered_and_cursor_readable() -> None:
    engine, repository, accepted = _completed_review()
    try:
        events = repository.list_events(accepted.session_id)
        repeated = repository.list_events(accepted.session_id)

        assert events == repeated
        assert [event.sequence for event in events] == list(range(1, len(events) + 1))
        assert len({event.event_id for event in events}) == len(events)
        assert all(event.event_id.startswith("evt_") for event in events)
        assert all(event.schema_version == 1 for event in events)
        assert all(event.correlation_id == accepted.session_id for event in events)
        assert events[0].causation_id is None
        assert [event.causation_id for event in events[1:]] == [
            event.event_id for event in events[:-1]
        ]
        assert all(event.summary.endswith(".") for event in events)
        assert all(isinstance(event.event_type, DomainEventType) for event in events)

        submitted = [
            event
            for event in events
            if event.event_type == DomainEventType.REVIEWER_INVOCATION_COMPLETED
        ]
        assert submitted
        assert all(event.actor is not None for event in submitted)
        assert all(
            event.actor.type == EventActorType.REVIEWER for event in submitted if event.actor
        )
        assert all(event.stage in set(ReviewStage) for event in submitted)
        assert all(event.round_number is not None for event in submitted)
        assert all(event.confidence == 0.7 for event in submitted)
        assert all(event.evidence_refs == () for event in submitted)

        cursor = events[5].sequence
        after = repository.list_events(
            accepted.session_id,
            after_sequence=cursor,
            limit=3,
        )
        assert [event.sequence for event in after] == [cursor + 1, cursor + 2, cursor + 3]
    finally:
        engine.dispose()


def test_event_envelope_validation_rejects_round_without_stage() -> None:
    with pytest.raises(ValueError, match="round_number requires"):
        PendingDomainEvent(
            event_type=DomainEventType.STATE_TRANSITIONED,
            stream_type="review_session",
            stream_id="rs_test",
            round_number=1,
            summary="Invalid event.",
        )


def test_domain_events_remain_immutable() -> None:
    engine, repository, accepted = _completed_review(FixturePath.A_ONLY)
    factory = sessionmaker(engine, expire_on_commit=False, class_=Session)
    try:
        with factory() as db:
            record = db.scalar(
                select(AuditEventRecord).where(AuditEventRecord.entity_id == accepted.session_id)
            )
            assert record is not None
            record.summary = "Changed."
            with pytest.raises(ImmutableLedgerRecordError):
                db.commit()
    finally:
        engine.dispose()


def test_state_mutation_rolls_back_when_event_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        document = load_request_fixture()
        accepted = ReviewIntakeService(repository).accept(document)
        before = repository.list_events(accepted.session_id)
        original = repository._persist_event

        def fail_after_event(db: Session, pending: PendingDomainEvent) -> AuditEventRecord:
            original(db, pending)
            raise RuntimeError("forced event failure")

        monkeypatch.setattr(repository, "_persist_event", fail_after_event)
        with pytest.raises(RuntimeError, match="forced event failure"):
            repository.transition_session(
                accepted.session_id,
                ReviewState.REVIEWER_A,
            )

        session = repository.get_session(accepted.session_id)
        assert session is not None
        assert session.current_state == ReviewState.SNAPSHOTTED.value
        assert repository.list_events(accepted.session_id) == before
    finally:
        engine.dispose()


def test_outbox_dispatch_is_ordered_checkpointed_and_duplicate_safe() -> None:
    engine, repository, accepted = _completed_review(FixturePath.A_ONLY)
    try:
        repository.register_event_subscriber(
            subscriber_id="test-projection",
            stream_type="review_session",
        )
        unpublished = repository.list_unpublished_events(subscriber_id="test-projection")
        assert unpublished == repository.list_events(accepted.session_id)

        publisher = InMemoryEventPublisher()
        dispatcher = EventDispatcher(
            repository,
            {"test-projection": publisher},
        )
        while True:
            result = dispatcher.dispatch_once(
                subscriber_id="test-projection",
                worker_id="dispatcher-1",
                now=datetime.now(UTC),
            )
            if result.status == "empty":
                break
            assert result.status == "delivered"

        assert publisher.events == unpublished
        assert repository.list_unpublished_events(subscriber_id="test-projection") == []
        for event in unpublished:
            delivery = repository.get_event_delivery(
                subscriber_id="test-projection",
                event_id=event.event_id,
            )
            assert delivery is not None
            assert delivery.status == "delivered"
            assert delivery.attempts == 1
    finally:
        engine.dispose()


def test_subscriber_failure_retries_without_changing_review_state() -> None:
    class FailsAfterAcceptingOnce:
        def __init__(self) -> None:
            self.publisher = InMemoryEventPublisher()
            self.failed = False

        def publish(self, event) -> None:
            self.publisher.publish(event)
            if not self.failed:
                self.failed = True
                raise RuntimeError("projection unavailable")

    engine, repository, accepted = _completed_review(FixturePath.A_ONLY)
    try:
        repository.register_event_subscriber(
            subscriber_id="flaky-projection",
            stream_type="review_session",
        )
        publisher = FailsAfterAcceptingOnce()
        dispatcher = EventDispatcher(
            repository,
            {"flaky-projection": publisher},
        )
        now = datetime.now(UTC)

        failed = dispatcher.dispatch_once(
            subscriber_id="flaky-projection",
            worker_id="dispatcher-1",
            now=now,
            retry_delay_seconds=0,
        )
        delivered = dispatcher.dispatch_once(
            subscriber_id="flaky-projection",
            worker_id="dispatcher-1",
            now=now,
        )

        assert failed.status == "retry"
        assert delivered.status == "delivered"
        assert failed.event_id == delivered.event_id
        assert len(publisher.publisher.events) == 1
        delivery = repository.get_event_delivery(
            subscriber_id="flaky-projection",
            event_id=delivered.event_id or "",
        )
        assert delivery is not None
        assert delivery.attempts == 2
        session = repository.get_session(accepted.session_id)
        assert session is not None
        assert session.current_state == ReviewState.RESULT_RETURNED.value
    finally:
        engine.dispose()


def test_noop_publisher_is_a_valid_transport_neutral_subscriber() -> None:
    engine, repository, _accepted = _completed_review(FixturePath.A_ONLY)
    try:
        repository.register_event_subscriber(
            subscriber_id="noop",
            stream_type="review_session",
        )
        result = EventDispatcher(
            repository,
            {"noop": NoOpEventPublisher()},
        ).dispatch_once(
            subscriber_id="noop",
            worker_id="dispatcher-1",
            now=datetime.now(UTC),
        )
        assert result.status == "delivered"
    finally:
        engine.dispose()


def test_standalone_domain_event_uses_the_same_canonical_ledger() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        event = repository.append_domain_event(
            PendingDomainEvent(
                event_type=DomainEventType.PROCESS_STARTED,
                stream_type="runtime_process",
                stream_id="projection-test",
                actor=EventActor(type=EventActorType.SYSTEM, id="projection-test"),
                summary="The projection test process started.",
            )
        )
        audit = repository.audit_events("runtime_process", "projection-test")

        assert len(audit) == 1
        assert audit[0].event_id == event.event_id
        assert event.sequence == 1
    finally:
        engine.dispose()
