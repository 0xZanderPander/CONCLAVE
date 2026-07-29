import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
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
    ReviewerEvaluationCandidateRecord,
    ReviewFeedbackRecord,
)
from conclave.ledger.repository import LedgerRepository
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.development import DevelopmentReviewerRuntime

POSTGRES_TEST_URL = os.getenv("CONCLAVE_TEST_DATABASE_URL")


def _assert_private_table_shape(
    db: Session,
    *,
    table_name: str,
    expected_columns: dict[str, tuple[str, str]],
    expected_constraints: set[tuple[str, str]],
    expected_indexes: set[str],
) -> None:
    columns = db.execute(
        text(
            "select column_name, data_type, is_nullable "
            "from information_schema.columns "
            "where table_schema = 'public' and table_name = :table_name "
            "order by ordinal_position"
        ),
        {"table_name": table_name},
    )
    assert {
        column_name: (data_type, is_nullable)
        for column_name, data_type, is_nullable in columns
    } == expected_columns
    constraints = db.execute(
        text(
            "select conname, contype from pg_constraint "
            "where conrelid = to_regclass(:table_name)"
        ),
        {"table_name": f"public.{table_name}"},
    )
    assert set(constraints) == expected_constraints
    indexes = db.scalars(
        text(
            "select indexname from pg_indexes "
            "where schemaname = 'public' and tablename = :table_name"
        ),
        {"table_name": table_name},
    )
    assert set(indexes) == expected_indexes
    rls = db.execute(
        text(
            "select relrowsecurity, relforcerowsecurity from pg_class "
            "where oid = to_regclass(:table_name)"
        ),
        {"table_name": f"public.{table_name}"},
    ).one()
    assert rls == (True, False)
    policy_count = db.scalar(
        text(
            "select count(*) from pg_policies "
            "where schemaname = 'public' and tablename = :table_name"
        ),
        {"table_name": table_name},
    )
    assert policy_count == 0
    for role in ("anon", "authenticated", "service_role"):
        for privilege in (
            "select",
            "insert",
            "update",
            "delete",
            "truncate",
            "references",
            "trigger",
        ):
            assert db.scalar(
                text(
                    "select has_table_privilege("
                    ":role, :table_name, :privilege)"
                ),
                {
                    "role": role,
                    "table_name": f"public.{table_name}",
                    "privilege": privilege,
                },
            ) is False


@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="CONCLAVE_TEST_DATABASE_URL is required for the PostgreSQL feedback test",
)
def test_postgres_feedback_is_private_atomic_and_idempotent() -> None:
    assert POSTGRES_TEST_URL is not None
    engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)
    factory = sessionmaker(engine, expire_on_commit=False, class_=Session)
    repository = LedgerRepository(factory)
    token = uuid4().hex[:12]
    plan_id = f"integration-feedback-{token}"
    occurrence_id = f"integration-feedback-occurrence-{token}"
    revision_id = ""
    session_id = ""

    try:
        template = load_design_plan_revisions()[0]
        revision = template.model_copy(
            update={
                "plan_id": plan_id,
                "deployment_id": f"integration-feedback-deployment-{token}",
            }
        )
        revision_id = f"{plan_id}:r{revision.revision}"
        repository.add_plan_revision(revision)

        document = load_request_fixture()
        document["caller"]["caller_id"] = f"integration-feedback-caller-{token}"
        document["idempotency_key"] = f"integration-feedback:{token}"
        document["evidence_version"] = f"integration-feedback-evidence-{token}"
        document["review_plan_ref"] = plan_id
        document["review_plan_revision"] = revision.revision
        document["review_trigger"] = {
            "occurrence_id": occurrence_id,
            "kind": "manual",
            "due_at": "2026-07-24T08:00:00Z",
        }
        accepted = ReviewIntakeService(repository).accept(document)
        session_id = accepted.session_id
        ReviewOrchestrator(
            repository,
            DevelopmentReviewerRuntime(),
        ).run_fixture_path(
            session_id,
            FixturePath.A_ONLY,
            now=datetime.now(UTC),
        )
        feedback_document = build_feedback_for_session(
            session_id=session_id,
            evidence_version=document["evidence_version"],
        )

        def submit_feedback():
            return FeedbackIntakeService(repository).accept(
                session_id=session_id,
                caller_id=document["caller"]["caller_id"],
                document=feedback_document,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            first, second = list(executor.map(lambda _index: submit_feedback(), range(2)))

        assert first.feedback_id == second.feedback_id
        assert first.feedback_hash == second.feedback_hash
        assert first.state.value == "feedback_pending"
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_evaluation, second_evaluation = list(
                executor.map(
                    lambda _index: ReviewerEvaluationService(
                        repository
                    ).evaluate(session_id),
                    range(2),
                )
            )
        assert first_evaluation == second_evaluation
        assert first_evaluation.state.value == "evaluated"
        with factory() as db:
            _assert_private_table_shape(
                db,
                table_name="review_feedback_records",
                expected_columns={
                    "feedback_id": ("character varying", "NO"),
                    "session_id": ("character varying", "NO"),
                    "contract_version": ("character varying", "NO"),
                    "evidence_version": ("character varying", "NO"),
                    "feedback_hash": ("character varying", "NO"),
                    "decision_ref": ("character varying", "NO"),
                    "decision_disposition": ("character varying", "NO"),
                    "relationship_to_panel": ("character varying", "NO"),
                    "panel_preference": ("character varying", "NO"),
                    "action_ref": ("character varying", "YES"),
                    "outcome_ref": ("character varying", "YES"),
                    "outcome_classification": ("character varying", "NO"),
                    "action_executed": ("boolean", "NO"),
                    "confounders": ("jsonb", "NO"),
                    "outcome_evidence_quality": ("character varying", "YES"),
                    "outcome_evaluated_at": (
                        "timestamp with time zone",
                        "YES",
                    ),
                    "document": ("jsonb", "NO"),
                    "created_at": ("timestamp with time zone", "NO"),
                },
                expected_constraints={
                    ("review_feedback_records_pkey", "p"),
                    ("review_feedback_records_session_id_fkey", "f"),
                    ("uq_review_feedback_session", "u"),
                },
                expected_indexes={
                    "review_feedback_records_pkey",
                    "uq_review_feedback_session",
                    "ix_review_feedback_records_session_id",
                    "ix_review_feedback_records_feedback_hash",
                },
            )
            _assert_private_table_shape(
                db,
                table_name="reviewer_evaluation_candidates",
                expected_columns={
                    "candidate_id": ("character varying", "NO"),
                    "session_id": ("character varying", "NO"),
                    "contract_version": ("character varying", "NO"),
                    "candidate_hash": ("character varying", "NO"),
                    "result_hash": ("character varying", "NO"),
                    "feedback_hash": ("character varying", "NO"),
                    "route": ("character varying", "NO"),
                    "panel_changed": ("boolean", "NO"),
                    "category_changed": ("boolean", "NO"),
                    "caller_preference": ("character varying", "NO"),
                    "additional_issue_count": ("integer", "NO"),
                    "cross_review_invoked": ("boolean", "NO"),
                    "cross_review_resolved": ("boolean", "NO"),
                    "reviewer_c_invoked": ("boolean", "NO"),
                    "caller_override": ("boolean", "NO"),
                    "total_latency_ms": ("integer", "NO"),
                    "total_cost_usd": ("numeric", "NO"),
                    "outcome_classification": ("character varying", "NO"),
                    "outcome_evidence_quality": ("character varying", "YES"),
                    "confounder_count": ("integer", "NO"),
                    "document": ("jsonb", "NO"),
                    "created_at": ("timestamp with time zone", "NO"),
                },
                expected_constraints={
                    ("reviewer_evaluation_candidates_pkey", "p"),
                    ("reviewer_evaluation_candidates_session_id_fkey", "f"),
                    ("uq_reviewer_evaluation_candidate_session", "u"),
                    ("ck_reviewer_evaluation_additional_issue_count", "c"),
                    ("ck_reviewer_evaluation_total_latency", "c"),
                    ("ck_reviewer_evaluation_total_cost", "c"),
                    ("ck_reviewer_evaluation_confounder_count", "c"),
                    ("ck_reviewer_evaluation_route", "c"),
                },
                expected_indexes={
                    "reviewer_evaluation_candidates_pkey",
                    "uq_reviewer_evaluation_candidate_session",
                    "ix_reviewer_evaluation_candidates_candidate_hash",
                    "ix_reviewer_evaluation_candidates_route_created",
                },
            )
            assert db.scalar(select(func.count()).select_from(ReviewFeedbackRecord)) >= 1
            stored = db.scalar(
                select(ReviewFeedbackRecord).where(
                    ReviewFeedbackRecord.session_id == session_id
                )
            )
            assert stored is not None
            assert stored.feedback_hash == first.feedback_hash
            evaluation = db.scalar(
                select(ReviewerEvaluationCandidateRecord).where(
                    ReviewerEvaluationCandidateRecord.session_id == session_id
                )
            )
            assert evaluation is not None
            assert evaluation.candidate_hash == first_evaluation.candidate_hash
        verification = AuditVerifier(repository).verify_session(session_id)
        assert verification.final_state.value == "evaluated"
        assert verification.feedback_hash == first.feedback_hash
        assert verification.evaluation_hash == first_evaluation.candidate_hash
        feedback_events = [
            event
            for event in repository.list_events(session_id)
            if event.event_type == "feedback_recorded"
        ]
        assert len(feedback_events) == 1
    finally:
        with engine.begin() as connection:
            streams = [
                ("review_occurrence", occurrence_id),
                ("review_plan_revision", revision_id),
            ]
            if session_id:
                streams.insert(0, ("review_session", session_id))
            for stream_type, stream_id in streams:
                connection.execute(
                    text(
                        "delete from event_deliveries where event_id in "
                        "(select event_id from audit_events "
                        "where entity_type = :stream_type and entity_id = :stream_id)"
                    ),
                    {"stream_type": stream_type, "stream_id": stream_id},
                )
                connection.execute(
                    text(
                        "delete from audit_events "
                        "where entity_type = :stream_type and entity_id = :stream_id"
                    ),
                    {"stream_type": stream_type, "stream_id": stream_id},
                )
                connection.execute(
                    text(
                        "delete from event_streams "
                        "where stream_type = :stream_type and stream_id = :stream_id"
                    ),
                    {"stream_type": stream_type, "stream_id": stream_id},
                )
            if session_id:
                connection.execute(
                    text(
                        "delete from reviewer_provider_attempts "
                        "where invocation_id in "
                        "(select invocation_id from reviewer_invocations "
                        "where session_id = :session_id)"
                    ),
                    {"session_id": session_id},
                )
                for table_name in (
                    "reviewer_evaluation_candidates",
                    "review_feedback_records",
                    "review_results",
                    "reviewer_invocations",
                    "request_snapshots",
                ):
                    connection.execute(
                        text(
                            f"delete from {table_name} where session_id = :session_id"
                        ),
                        {"session_id": session_id},
                    )
                connection.execute(
                    text("delete from review_sessions where session_id = :session_id"),
                    {"session_id": session_id},
                )
                for table_name in (
                    "reviewer_evaluation_candidates",
                    "review_feedback_records",
                ):
                    assert (
                        connection.scalar(
                            text(
                                f"select count(*) from {table_name} "
                                "where session_id = :session_id"
                            ),
                            {"session_id": session_id},
                        )
                        == 0
                    )
            connection.execute(
                text(
                    "delete from review_occurrences where occurrence_id = :occurrence_id"
                ),
                {"occurrence_id": occurrence_id},
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
        engine.dispose()
