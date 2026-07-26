import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from conclave.fixtures import load_design_plan_revisions
from conclave.ledger.repository import LedgerRepository

POSTGRES_TEST_URL = os.getenv("CONCLAVE_TEST_DATABASE_URL")


@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="CONCLAVE_TEST_DATABASE_URL is required for the PostgreSQL locking test",
)
def test_postgres_allows_exactly_one_worker_to_claim_a_work_item() -> None:
    assert POSTGRES_TEST_URL is not None
    engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)
    repository = LedgerRepository(sessionmaker(engine, expire_on_commit=False, class_=Session))
    token = uuid4().hex[:12]
    plan_id = f"integration-locking-{token}"
    occurrence_id = f"integration-occurrence-{token}"
    worker_ids = (f"integration-worker-a-{token}", f"integration-worker-b-{token}")
    revision_id = ""
    work_item_id: str | None = None

    try:
        template = load_design_plan_revisions()[0]
        revision = template.model_copy(
            update={
                "plan_id": plan_id,
                "deployment_id": f"integration-deployment-{token}",
            }
        )
        revision_id = f"{plan_id}:r{revision.revision}"
        repository.add_plan_revision(revision)
        due_at = datetime(2000, 1, 1, tzinfo=UTC)
        repository.add_occurrence(
            occurrence_id=occurrence_id,
            plan_id=plan_id,
            plan_revision=revision.revision,
            due_at=due_at,
            trigger_kind="scheduled",
        )
        work_item_id = repository.enqueue_occurrence(
            occurrence_id=occurrence_id,
            due_at=due_at,
        ).work_item_id

        start = Barrier(2)

        def claim(worker_id: str) -> str | None:
            start.wait()
            item = repository.claim_next_work_item(
                worker_id=worker_id,
                now=datetime.now(UTC),
                lease_seconds=60,
            )
            return item.work_item_id if item is not None else None

        with ThreadPoolExecutor(max_workers=2) as executor:
            claimed = tuple(executor.map(claim, worker_ids))

        assert claimed.count(work_item_id) == 1
        assert claimed.count(None) == 1
    finally:
        with engine.begin() as connection:
            if work_item_id is not None:
                connection.execute(
                    text("delete from scheduler_work_items where work_item_id = :id"),
                    {"id": work_item_id},
                )
            connection.execute(
                text("delete from review_occurrences where occurrence_id = :id"),
                {"id": occurrence_id},
            )
            connection.execute(
                text("delete from reviewer_slots where plan_id = :plan_id"),
                {"plan_id": plan_id},
            )
            connection.execute(
                text("delete from review_plan_revisions where plan_id = :plan_id"),
                {"plan_id": plan_id},
            )
            connection.execute(
                text("delete from review_plans where plan_id = :plan_id"),
                {"plan_id": plan_id},
            )
            connection.execute(
                text(
                    "delete from audit_events "
                    "where entity_id = :occurrence_id "
                    "or entity_id = :work_item_id "
                    "or entity_id = :revision_id"
                ),
                {
                    "occurrence_id": occurrence_id,
                    "work_item_id": work_item_id or "",
                    "revision_id": revision_id,
                },
            )
        engine.dispose()
