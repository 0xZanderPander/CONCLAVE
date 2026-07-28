from datetime import UTC, datetime

import pytest

from conclave.auditing.verification import AuditVerifier
from conclave.domain.enums import ReviewerSlot, ReviewStage, ReviewState
from conclave.fixtures import load_design_plan_revisions, load_request_fixture
from conclave.intake import ReviewIntakeService
from conclave.orchestration.service import ReviewOrchestrator
from conclave.reviewers.runtime import (
    FakeReviewerRuntime,
    ReviewCall,
    ReviewerExecution,
    ReviewOutput,
)
from tests.helpers import create_test_engine, create_test_repository
from tests.test_automatic_routing import _collect, _judgment, _pause


def _responses() -> dict[tuple[ReviewerSlot, ReviewStage, int], ReviewOutput]:
    return {
        (ReviewerSlot.A, ReviewStage.INDEPENDENT, 1): _pause(),
        (ReviewerSlot.B, ReviewStage.INDEPENDENT, 1): _collect(),
        (ReviewerSlot.A, ReviewStage.CROSS_REVIEW, 2): _pause(),
        (ReviewerSlot.B, ReviewStage.CROSS_REVIEW, 2): _collect(),
        (ReviewerSlot.C, ReviewStage.INDEPENDENT, 1): _collect(),
        (ReviewerSlot.C, ReviewStage.JUDGING, 2): _judgment(),
    }


class CrashOnceRuntime:
    def __init__(
        self,
        responses: dict[tuple[ReviewerSlot, ReviewStage, int], ReviewOutput],
        crash_at: tuple[ReviewerSlot, ReviewStage, int],
    ) -> None:
        self._responses = responses
        self._crash_at = crash_at
        self._crashed = False

    def review(self, call: ReviewCall) -> ReviewerExecution:
        key = (call.slot, call.stage, call.round)
        if key == self._crash_at and not self._crashed:
            self._crashed = True
            raise KeyboardInterrupt("simulated process loss")
        return ReviewerExecution(output=self._responses[key])


@pytest.mark.parametrize("crash_at", tuple(_responses()))
def test_automatic_orchestration_resumes_pending_reviewer_invocations(
    crash_at: tuple[ReviewerSlot, ReviewStage, int],
) -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        accepted = ReviewIntakeService(repository).accept(
            load_request_fixture("04-surviving-reviewer-conflict.json")
        )
        responses = _responses()
        with pytest.raises(KeyboardInterrupt, match="simulated process loss"):
            ReviewOrchestrator(
                repository,
                CrashOnceRuntime(responses, crash_at),
            ).run(accepted.session_id, now=datetime.now(UTC))

        state = ReviewOrchestrator(
            repository,
            FakeReviewerRuntime(responses),
        ).run(accepted.session_id, now=datetime.now(UTC))

        assert state == ReviewState.RESULT_RETURNED
        assert (
            AuditVerifier(repository).verify_session(accepted.session_id).path
            == "c_tie_broken"
        )
    finally:
        engine.dispose()


def test_automatic_orchestration_resumes_after_committed_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        accepted = ReviewIntakeService(repository).accept(
            load_request_fixture("02-weak-evidence.json")
        )
        assessment = _collect().model_copy(
            update={
                "optimization_eligible": False,
                "evidence_quality": "insufficient",
            }
        )
        responses = {
            (ReviewerSlot.A, ReviewStage.INDEPENDENT, 1): assessment,
            (ReviewerSlot.B, ReviewStage.INDEPENDENT, 1): assessment,
        }
        original = repository.record_comparison
        crashed = False

        def crash_after_commit(**kwargs):
            nonlocal crashed
            event = original(**kwargs)
            if not crashed:
                crashed = True
                raise KeyboardInterrupt("comparison committed")
            return event

        monkeypatch.setattr(repository, "record_comparison", crash_after_commit)
        with pytest.raises(KeyboardInterrupt, match="comparison committed"):
            ReviewOrchestrator(
                repository,
                FakeReviewerRuntime(responses),
            ).run(accepted.session_id, now=datetime.now(UTC))
        monkeypatch.setattr(repository, "record_comparison", original)

        state = ReviewOrchestrator(
            repository,
            FakeReviewerRuntime(responses),
        ).run(accepted.session_id, now=datetime.now(UTC))

        assert state == ReviewState.RESULT_RETURNED
        assert (
            AuditVerifier(repository).verify_session(accepted.session_id).path
            == "ab_agreement"
        )
    finally:
        engine.dispose()


def test_automatic_orchestration_resumes_after_result_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        accepted = ReviewIntakeService(repository).accept(load_request_fixture())
        responses = {
            (ReviewerSlot.A, ReviewStage.INDEPENDENT, 1): _collect(),
        }
        original = repository.record_result
        crashed = False

        def crash_after_commit(**kwargs):
            nonlocal crashed
            result = original(**kwargs)
            if not crashed:
                crashed = True
                raise KeyboardInterrupt("result committed")
            return result

        monkeypatch.setattr(repository, "record_result", crash_after_commit)
        with pytest.raises(KeyboardInterrupt, match="result committed"):
            ReviewOrchestrator(
                repository,
                FakeReviewerRuntime(responses),
            ).run(accepted.session_id, now=datetime.now(UTC))
        monkeypatch.setattr(repository, "record_result", original)

        state = ReviewOrchestrator(
            repository,
            FakeReviewerRuntime(responses),
        ).run(accepted.session_id, now=datetime.now(UTC))

        assert state == ReviewState.RESULT_RETURNED
        assert (
            AuditVerifier(repository).verify_session(accepted.session_id).path
            == "a_only"
        )
    finally:
        engine.dispose()
