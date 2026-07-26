from datetime import UTC, datetime, timedelta

import pytest

from conclave.fixtures import load_design_plan_revisions
from conclave.ledger.repository import WorkItemClaimError
from conclave.scheduling.service import SchedulerService
from tests.helpers import create_test_engine, create_test_repository


def test_scheduler_tick_is_idempotent_and_collides_a_b_into_one_work_item() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        scheduler = SchedulerService(repository)
        at = datetime.fromisoformat("2026-07-24T16:00:00+00:00")

        first = scheduler.tick(at)
        second = scheduler.tick(at)

        assert len(first) == 1
        assert len(second) == 1
        assert first[0].occurrence_id == second[0].occurrence_id
        assert first[0].work_item_id == second[0].work_item_id
        assert {slot.value for slot in first[0].slots_due} == {"A", "B"}
    finally:
        engine.dispose()


def test_database_lease_allows_only_one_active_worker_and_can_expire() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        work = SchedulerService(repository).tick(
            datetime.fromisoformat("2026-07-24T16:00:00+00:00")
        )[0]
        now = datetime.now(UTC)

        first = repository.claim_next_work_item(
            worker_id="worker-1",
            now=now,
            lease_seconds=30,
        )
        blocked = repository.claim_next_work_item(
            worker_id="worker-2",
            now=now,
            lease_seconds=30,
        )
        reclaimed = repository.claim_next_work_item(
            worker_id="worker-2",
            now=now + timedelta(seconds=31),
            lease_seconds=30,
        )

        assert first is not None
        assert first.work_item_id == work.work_item_id
        assert blocked is None
        assert reclaimed is not None
        assert reclaimed.work_item_id == work.work_item_id
        assert reclaimed.attempts == 2

        with pytest.raises(WorkItemClaimError):
            repository.complete_work_item(
                work_item_id=work.work_item_id,
                worker_id="worker-1",
                now=now + timedelta(seconds=32),
            )

        completed = repository.complete_work_item(
            work_item_id=work.work_item_id,
            worker_id="worker-2",
            now=now + timedelta(seconds=32),
        )
        assert completed.status == "completed"
        assert (
            repository.claim_next_work_item(
                worker_id="worker-3",
                now=now + timedelta(seconds=33),
            )
            is None
        )
    finally:
        engine.dispose()
