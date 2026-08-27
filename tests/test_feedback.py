from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from conclave.auditing.verification import AuditVerifier
from conclave.contracts.validation import ContractValidationError
from conclave.feedback import FeedbackIntakeService
from conclave.fixtures import (
    build_feedback_for_session,
    load_design_plan_revisions,
    load_request_fixture,
)
from conclave.intake import ReviewIntakeService
from conclave.ledger.models import ImmutableLedgerRecordError, ReviewFeedbackRecord
from conclave.ledger.repository import LedgerConflictError
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.development import DevelopmentReviewerRuntime
from tests.helpers import create_test_engine, create_test_repository


def _completed_review():
    engine = create_test_engine()
    repository = create_test_repository(engine)
    for revision in load_design_plan_revisions():
        repository.add_plan_revision(revision)
    accepted = ReviewIntakeService(repository).accept(load_request_fixture())
    ReviewOrchestrator(repository, DevelopmentReviewerRuntime()).run_fixture_path(
        accepted.session_id,
        FixturePath.A_ONLY,
        now=datetime.now(UTC),
    )
    return engine, repository, accepted


def test_feedback_intake_is_idempotent_and_auditable() -> None:
    engine, repository, accepted = _completed_review()
    try:
        document = build_feedback_for_session(
            session_id=accepted.session_id,
            evidence_version="ev_2026-07-24T08:00Z_r1",
        )
        intake = FeedbackIntakeService(repository)

        first = intake.accept(
            session_id=accepted.session_id,
            caller_id="hyperstructure-marketing-os",
            document=document,
        )
        second = intake.accept(
            session_id=accepted.session_id,
            caller_id="hyperstructure-marketing-os",
            document=document,
        )

        assert first == second
        assert first.state.value == "feedback_pending"
        feedback = repository.get_feedback(accepted.session_id)
        assert feedback is not None
        assert feedback.feedback_id == first.feedback_id
        assert feedback.decision_ref == "mktg_decision_9f2a1c"
        assert feedback.outcome_classification == "beneficial"
        assert feedback.confounders == ["weekend traffic mix shift"]
        verification = AuditVerifier(repository).verify_session(
            accepted.session_id
        )
        assert verification.final_state.value == "feedback_pending"
        assert verification.feedback_hash == first.feedback_hash

        events = repository.list_events(accepted.session_id)
        feedback_events = [
            event for event in events if event.event_type == "feedback_recorded"
        ]
        assert len(feedback_events) == 1
        assert feedback_events[0].actor is not None
        assert feedback_events[0].actor.id == "hyperstructure-marketing-os"
        assert feedback_events[0].payload["has_decision_ref"] is True
        assert "decision_ref" not in feedback_events[0].payload
        assert "action_ref" not in feedback_events[0].payload
        assert "outcome_ref" not in feedback_events[0].payload
    finally:
        engine.dispose()


def test_feedback_intake_rejects_changed_replay_and_wrong_correlation() -> None:
    engine, repository, accepted = _completed_review()
    try:
        intake = FeedbackIntakeService(repository)
        document = build_feedback_for_session(
            session_id=accepted.session_id,
            evidence_version="ev_2026-07-24T08:00Z_r1",
        )
        intake.accept(
            session_id=accepted.session_id,
            caller_id="hyperstructure-marketing-os",
            document=document,
        )

        changed = {
            **document,
            "decision_summary": {
                **document["decision_summary"],
                "disposition": "modified",
            },
        }
        with pytest.raises(LedgerConflictError, match="immutable"):
            intake.accept(
                session_id=accepted.session_id,
                caller_id="hyperstructure-marketing-os",
                document=changed,
            )

        wrong_session = {
            **document,
            "review_session_id": "rs_wrong",
        }
        with pytest.raises(ContractValidationError, match="review_session_id"):
            intake.accept(
                session_id=accepted.session_id,
                caller_id="hyperstructure-marketing-os",
                document=wrong_session,
            )
    finally:
        engine.dispose()


def test_feedback_requires_a_result_and_is_append_only() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    factory = sessionmaker(engine, expire_on_commit=False, class_=Session)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        accepted = ReviewIntakeService(repository).accept(load_request_fixture())
        document = build_feedback_for_session(
            session_id=accepted.session_id,
            evidence_version="ev_2026-07-24T08:00Z_r1",
        )

        with pytest.raises(LedgerConflictError, match="immutable review result"):
            FeedbackIntakeService(repository).accept(
                session_id=accepted.session_id,
                caller_id="hyperstructure-marketing-os",
                document=document,
            )

        ReviewOrchestrator(
            repository,
            DevelopmentReviewerRuntime(),
        ).run_fixture_path(
            accepted.session_id,
            FixturePath.A_ONLY,
            now=datetime.now(UTC),
        )
        accepted_feedback = FeedbackIntakeService(repository).accept(
            session_id=accepted.session_id,
            caller_id="hyperstructure-marketing-os",
            document=document,
        )

        with factory() as db:
            record = db.get(ReviewFeedbackRecord, accepted_feedback.feedback_id)
            assert record is not None
            record.outcome_classification = "harmful"
            with pytest.raises(ImmutableLedgerRecordError):
                db.commit()
    finally:
        engine.dispose()
