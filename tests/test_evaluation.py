from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from conclave.auditing.verification import AuditVerifier
from conclave.evaluation.service import ReviewerEvaluationService
from conclave.feedback import FeedbackIntakeService
from conclave.fixtures import (
    build_feedback_for_session,
    load_design_plan_revisions,
    load_request_fixture,
)
from conclave.intake import ReviewIntakeService
from conclave.ledger.models import (
    ImmutableLedgerRecordError,
    ReviewerEvaluationCandidateRecord,
)
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.development import DevelopmentReviewerRuntime
from tests.helpers import create_test_engine, create_test_repository


def _run_review(repository, path: FixturePath, *, suffix: str):
    document = load_request_fixture()
    hour = 8 + sum(ord(character) for character in suffix) % 12
    document["idempotency_key"] = f"evaluation:{suffix}"
    document["evidence_version"] = f"evaluation-evidence-{suffix}"
    document["review_trigger"] = {
        **document["review_trigger"],
        "occurrence_id": f"evaluation-occurrence-{suffix}",
        "due_at": f"2026-07-24T{hour:02d}:00:00Z",
    }
    accepted = ReviewIntakeService(repository).accept(document)
    ReviewOrchestrator(
        repository,
        DevelopmentReviewerRuntime(),
    ).run_fixture_path(
        accepted.session_id,
        path,
        now=datetime.now(UTC),
    )
    return accepted, document


def test_directional_evaluation_is_immutable_idempotent_and_auditable() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    factory = sessionmaker(engine, expire_on_commit=False, class_=Session)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        accepted, request = _run_review(
            repository,
            FixturePath.A_ONLY,
            suffix="a-only",
        )
        feedback = build_feedback_for_session(
            session_id=accepted.session_id,
            evidence_version=request["evidence_version"],
        )
        FeedbackIntakeService(repository).accept(
            session_id=accepted.session_id,
            caller_id=request["caller"]["caller_id"],
            document=feedback,
        )
        service = ReviewerEvaluationService(repository)

        first = service.evaluate(accepted.session_id)
        second = service.evaluate(accepted.session_id)

        assert first == second
        assert first.state.value == "evaluated"
        stored = repository.get_evaluation_candidate(accepted.session_id)
        assert stored is not None
        assert stored.document["interpretation"] == "directional_only"
        assert stored.document["route"] == "a_only"
        assert stored.document["indicators"]["panel_changed"] is False
        assert stored.document["indicators"]["category_changed"] is False
        assert stored.document["indicators"]["reviewer_c_invoked"] is False
        assert stored.document["result_hash"] == stored.result_hash
        assert stored.document["feedback_hash"] == stored.feedback_hash

        verification = AuditVerifier(repository).verify_session(
            accepted.session_id
        )
        assert verification.final_state.value == "evaluated"
        assert verification.evaluation_hash == first.candidate_hash
        events = repository.list_events(accepted.session_id)
        evaluation_events = [
            event
            for event in events
            if event.event_type == "evaluation_candidate_recorded"
        ]
        assert len(evaluation_events) == 1
        assert evaluation_events[0].payload["interpretation"] == "directional_only"
        assert "decision_ref" not in evaluation_events[0].payload
        assert "action_ref" not in evaluation_events[0].payload
        assert "outcome_ref" not in evaluation_events[0].payload

        with factory() as db:
            record = db.get(
                ReviewerEvaluationCandidateRecord,
                first.candidate_id,
            )
            assert record is not None
            record.caller_override = True
            with pytest.raises(ImmutableLedgerRecordError):
                db.commit()
    finally:
        engine.dispose()


def test_directional_metrics_report_panel_indicators_by_route() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        a_only, a_request = _run_review(
            repository,
            FixturePath.A_ONLY,
            suffix="metrics-a",
        )
        c_panel, c_request = _run_review(
            repository,
            FixturePath.C_TIE_BROKEN,
            suffix="metrics-c",
        )
        for accepted, request, preference, relationship in (
            (a_only, a_request, "not_comparable", "accepted_as_is"),
            (c_panel, c_request, "preferred_panel", "accepted_with_changes"),
        ):
            feedback = build_feedback_for_session(
                session_id=accepted.session_id,
                evidence_version=request["evidence_version"],
            )
            feedback["decision_summary"] = {
                **feedback["decision_summary"],
                "panel_preference": preference,
                "relationship_to_panel": relationship,
            }
            FeedbackIntakeService(repository).accept(
                session_id=accepted.session_id,
                caller_id=request["caller"]["caller_id"],
                document=feedback,
            )
            ReviewerEvaluationService(repository).evaluate(accepted.session_id)

        metrics = ReviewerEvaluationService(repository).metrics()
        assert metrics.interpretation == "directional_only"
        assert metrics.candidate_count == 2
        assert metrics.caller_preferred_panel_rate == 1.0
        assert metrics.reviewer_c_invocation_rate == 0.5
        assert metrics.caller_override_rate == 0.5
        assert metrics.cross_review_resolution_rate == 0.0
        assert metrics.panel_change_rate is not None
        assert metrics.average_additional_issue_count is not None
        assert set(metrics.routes) == {"a_only", "c_tie_broken"}
        assert metrics.routes["a_only"].candidate_count == 1
        assert metrics.routes["c_tie_broken"].candidate_count == 1
    finally:
        engine.dispose()
