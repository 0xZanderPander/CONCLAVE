import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from conclave.events.models import (
    DomainEventType,
    EventActor,
    EventActorType,
    PendingDomainEvent,
)
from conclave.ledger.repository import LedgerRepository

POSTGRES_TEST_URL = os.getenv("CONCLAVE_TEST_DATABASE_URL")


@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="CONCLAVE_TEST_DATABASE_URL is required for the event concurrency test",
)
def test_postgres_concurrent_appends_allocate_unique_stream_sequences() -> None:
    assert POSTGRES_TEST_URL is not None
    engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)
    repository = LedgerRepository(sessionmaker(engine, expire_on_commit=False, class_=Session))
    stream_id = f"integration-event-stream-{uuid4().hex[:12]}"
    start = Barrier(2)

    def append(position: int) -> tuple[str, int]:
        start.wait()
        event = repository.append_domain_event(
            PendingDomainEvent(
                event_type=DomainEventType.PROCESS_STARTED,
                stream_type="runtime_process",
                stream_id=stream_id,
                actor=EventActor(type=EventActorType.SYSTEM, id=f"writer-{position}"),
                summary=f"Concurrent writer {position} appended an event.",
                occurred_at=datetime.now(UTC),
            )
        )
        return event.event_id, event.sequence

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            appended = tuple(executor.map(append, (1, 2)))

        events = repository.list_events(
            stream_id,
            stream_type="runtime_process",
        )
        assert sorted(sequence for _event_id, sequence in appended) == [1, 2]
        assert len({event_id for event_id, _sequence in appended}) == 2
        assert [event.sequence for event in events] == [1, 2]
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "delete from event_deliveries where event_id in "
                    "(select event_id from audit_events where entity_id = :stream_id)"
                ),
                {"stream_id": stream_id},
            )
            connection.execute(
                text("delete from audit_events where entity_id = :stream_id"),
                {"stream_id": stream_id},
            )
            connection.execute(
                text(
                    "delete from event_streams "
                    "where stream_type = 'runtime_process' and stream_id = :stream_id"
                ),
                {"stream_id": stream_id},
            )
        engine.dispose()


@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="CONCLAVE_TEST_DATABASE_URL is required for the event delivery locking test",
)
def test_postgres_allows_only_one_active_delivery_per_subscriber_stream() -> None:
    assert POSTGRES_TEST_URL is not None
    engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)
    repository = LedgerRepository(sessionmaker(engine, expire_on_commit=False, class_=Session))
    token = uuid4().hex[:12]
    stream_id = f"integration-delivery-stream-{token}"
    subscriber_id = f"integration-subscriber-{token}"
    worker_ids = (f"dispatcher-a-{token}", f"dispatcher-b-{token}")

    try:
        for position in (1, 2):
            repository.append_domain_event(
                PendingDomainEvent(
                    event_type=DomainEventType.PROCESS_STARTED,
                    stream_type="runtime_process",
                    stream_id=stream_id,
                    actor=EventActor(type=EventActorType.SYSTEM, id=f"writer-{position}"),
                    summary=f"Delivery event {position} was committed.",
                    occurred_at=datetime.now(UTC),
                )
            )
        repository.register_event_subscriber(
            subscriber_id=subscriber_id,
            stream_type="runtime_process",
        )
        now = datetime.now(UTC)
        start = Barrier(2)

        def claim(worker_id: str) -> str | None:
            start.wait()
            claimed = repository.claim_next_event_delivery(
                subscriber_id=subscriber_id,
                worker_id=worker_id,
                now=now,
            )
            return claimed[0].event_id if claimed is not None else None

        with ThreadPoolExecutor(max_workers=2) as executor:
            claimed = tuple(executor.map(claim, worker_ids))

        assert sum(event_id is not None for event_id in claimed) == 1
        assert sum(event_id is None for event_id in claimed) == 1
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("delete from event_deliveries where subscriber_id = :subscriber_id"),
                {"subscriber_id": subscriber_id},
            )
            connection.execute(
                text("delete from event_subscriptions where subscriber_id = :subscriber_id"),
                {"subscriber_id": subscriber_id},
            )
            connection.execute(
                text("delete from audit_events where entity_id = :stream_id"),
                {"stream_id": stream_id},
            )
            connection.execute(
                text(
                    "delete from event_streams "
                    "where stream_type = 'runtime_process' and stream_id = :stream_id"
                ),
                {"stream_id": stream_id},
            )
        engine.dispose()
