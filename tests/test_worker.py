from datetime import UTC, datetime

import pytest

from conclave.domain.enums import ReviewState
from conclave.fixtures import load_design_plan_revisions
from conclave.intake import ReviewIntakeService
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.development import DevelopmentReviewerRuntime
from conclave.reviewers.runtime import ProviderRegistryRuntime, ReviewCall
from conclave.scheduling.service import SchedulerService
from conclave.scheduling.worker import FixtureWorker
from tests.helpers import create_test_engine, create_test_repository


def test_worker_claims_builds_and_completes_a_fixture_review() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        scheduled_at = datetime.fromisoformat("2026-07-24T16:00:00+00:00")
        scheduled = SchedulerService(repository).tick(scheduled_at)[0]
        worker = FixtureWorker(
            repository,
            ReviewIntakeService(repository),
            ReviewOrchestrator(repository, DevelopmentReviewerRuntime()),
        )

        result = worker.run_once(
            worker_id="worker-1",
            now=datetime.now(UTC),
            path=FixturePath.A_ONLY,
        )
        empty = worker.run_once(
            worker_id="worker-1",
            now=datetime.now(UTC),
            path=FixturePath.A_ONLY,
        )

        assert result is not None
        assert result.work_item_id == scheduled.work_item_id
        assert result.state == ReviewState.RESULT_RETURNED
        assert empty is None
        work_item = repository.get_work_item(scheduled.work_item_id)
        assert work_item is not None
        assert work_item.status == "completed"
        session = repository.find_session_by_occurrence(scheduled.occurrence_id)
        assert session is not None
        assert session.current_state == ReviewState.RESULT_RETURNED.value
    finally:
        engine.dispose()


def test_worker_dead_letters_a_permanently_invalid_reviewer_response() -> None:
    class InvalidProvider:
        def invoke(self, _call: ReviewCall) -> dict:
            return {"summary": "Missing required contract fields."}

    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        scheduled = SchedulerService(repository, max_attempts=3).tick(
            datetime.fromisoformat("2026-07-24T16:00:00+00:00")
        )[0]
        runtime = ProviderRegistryRuntime(
            {
                "fixture": InvalidProvider(),
                "deterministic": InvalidProvider(),
            },
            max_attempts=2,
        )
        worker = FixtureWorker(
            repository,
            ReviewIntakeService(repository),
            ReviewOrchestrator(repository, runtime),
        )

        with pytest.raises(RuntimeError, match="returned invalid output"):
            worker.run_once(
                worker_id="worker-invalid",
                now=datetime.now(UTC),
                path=FixturePath.A_ONLY,
            )

        work_item = repository.get_work_item(scheduled.work_item_id)
        assert work_item is not None
        assert work_item.status == "dead_letter"
        assert work_item.attempts == 1
        assert work_item.dead_lettered_at is not None
    finally:
        engine.dispose()
