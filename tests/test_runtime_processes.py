from datetime import UTC, datetime, timedelta

from conclave.fixtures import load_design_plan_revisions
from conclave.intake import ReviewIntakeService
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.development import DevelopmentReviewerRuntime
from conclave.runtime.processes import SchedulerProcess, WorkerProcess
from conclave.scheduling.service import SchedulerService
from conclave.scheduling.worker import FixtureWorker
from tests.helpers import create_test_engine, create_test_repository


def test_scheduler_and_worker_once_record_clean_process_lifecycles() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        scheduler = SchedulerService(repository)
        worker = FixtureWorker(
            repository,
            ReviewIntakeService(repository),
            ReviewOrchestrator(repository, DevelopmentReviewerRuntime()),
        )

        SchedulerProcess(
            repository,
            scheduler,
            process_id="scheduler-test",
            interval_seconds=60,
        ).run(once=True)
        WorkerProcess(
            repository,
            worker,
            process_id="worker-test",
            idle_seconds=1,
            lease_seconds=60,
            retry_delay_seconds=1,
            path=FixturePath.A_ONLY,
        ).run(once=True)

        processes = repository.list_processes()
        assert [process.process_id for process in processes] == [
            "scheduler-test",
            "worker-test",
        ]
        assert all(process.status == "stopped" for process in processes)
        assert all(process.stopped_at is not None for process in processes)
    finally:
        engine.dispose()


def test_stale_process_monitor_only_reports_overdue_running_processes() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    now = datetime.now(UTC)
    try:
        repository.register_process(
            process_id="stale-worker",
            process_type="worker",
            now=now - timedelta(minutes=10),
        )
        repository.register_process(
            process_id="healthy-worker",
            process_type="worker",
            now=now,
        )
        repository.register_process(
            process_id="stopped-worker",
            process_type="worker",
            now=now - timedelta(minutes=10),
        )
        repository.stop_process(
            process_id="stopped-worker",
            now=now - timedelta(minutes=9),
        )

        stale = repository.stale_processes(now=now, stale_after_seconds=180)

        assert [process.process_id for process in stale] == ["stale-worker"]
    finally:
        engine.dispose()
