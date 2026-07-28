from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from conclave.domain.enums import ReviewerSlot, ReviewStage, ReviewState
from conclave.fixtures import load_design_plan_revisions, load_request_fixture
from conclave.intake import ReviewIntakeService
from conclave.ledger.models import ReviewerInvocationRecord
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.development import (
    DevelopmentReviewerProvider,
    DevelopmentReviewerRuntime,
)
from conclave.reviewers.runtime import (
    FakeReviewerRuntime,
    ProviderCallResult,
    ProviderRegistryRuntime,
    ProviderUsage,
    ReviewCall,
)
from tests.helpers import create_test_engine, create_test_repository


def _prepared() -> tuple:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    for revision in load_design_plan_revisions():
        repository.add_plan_revision(revision)
    intake = ReviewIntakeService(repository)
    accepted = intake.accept(load_request_fixture("04-surviving-reviewer-conflict.json"))
    return engine, repository, accepted


def test_c_path_runs_all_stages_and_is_idempotent_after_completion() -> None:
    engine, repository, accepted = _prepared()
    try:
        orchestrator = ReviewOrchestrator(repository, DevelopmentReviewerRuntime())

        result = orchestrator.run_fixture_path(
            accepted.session_id,
            FixturePath.C_TIE_BROKEN,
            now=datetime.now(UTC),
        )
        repeated = orchestrator.run_fixture_path(
            accepted.session_id,
            FixturePath.C_TIE_BROKEN,
            now=datetime.now(UTC),
        )

        assert result == ReviewState.RESULT_RETURNED
        assert repeated == ReviewState.RESULT_RETURNED

        factory = sessionmaker(engine, expire_on_commit=False, class_=Session)
        with factory() as db:
            invocations = list(
                db.scalars(
                    select(ReviewerInvocationRecord)
                    .where(ReviewerInvocationRecord.session_id == accepted.session_id)
                    .order_by(ReviewerInvocationRecord.created_at)
                )
            )
        assert len(invocations) == 6
        assert all(invocation.status == "completed" for invocation in invocations)
        c_stages = [
            invocation.stage
            for invocation in invocations
            if invocation.reviewer_slot == ReviewerSlot.C.value
        ]
        assert c_stages == [ReviewStage.INDEPENDENT.value, ReviewStage.JUDGING.value]
    finally:
        engine.dispose()


def test_reviewer_failure_enters_explicit_failure_state() -> None:
    engine, repository, accepted = _prepared()
    try:
        orchestrator = ReviewOrchestrator(repository, FakeReviewerRuntime({}))

        with pytest.raises(LookupError):
            orchestrator.run_fixture_path(
                accepted.session_id,
                FixturePath.A_ONLY,
                now=datetime.now(UTC),
            )

        session = repository.get_session(accepted.session_id)
        assert session is not None
        assert session.current_state == ReviewState.REVIEWER_A_FAILED.value
    finally:
        engine.dispose()


def test_provider_telemetry_is_persisted_and_projected_into_the_result() -> None:
    class TelemetryProvider:
        def invoke(self, call: ReviewCall) -> ProviderCallResult:
            return ProviderCallResult(
                output=DevelopmentReviewerProvider().invoke(call),
                provider_request_id="req_test",
                provider_response_id="resp_test",
                finish_status="completed",
                usage=ProviderUsage(
                    input_tokens=500,
                    output_tokens=100,
                    reasoning_tokens=25,
                    total_tokens=600,
                    cost_usd=0.01,
                    pricing_version="test-v1",
                ),
            )

    engine, repository, accepted = _prepared()
    try:
        runtime = ProviderRegistryRuntime(
            {"fixture": TelemetryProvider(), "deterministic": TelemetryProvider()}
        )
        ReviewOrchestrator(repository, runtime).run_fixture_path(
            accepted.session_id,
            FixturePath.A_ONLY,
            now=datetime.now(UTC),
        )

        invocation = repository.list_invocations(accepted.session_id)[0]
        attempts = repository.list_provider_attempts(invocation.invocation_id)
        result = repository.get_result(accepted.session_id)
        events = repository.list_events(accepted.session_id)

        assert len(attempts) == 1
        assert attempts[0].provider_response_id == "resp_test"
        assert invocation.total_tokens == 600
        assert result is not None
        reviewer = result.document["panel_metadata"]["reviewers"][0]
        assert reviewer["attempt_count"] == 1
        assert reviewer["reasoning_tokens"] == 25
        assert reviewer["pricing_version"] == "test-v1"
        assert "provider_attempt_completed" in {
            event.event_type.value for event in events
        }
    finally:
        engine.dispose()
