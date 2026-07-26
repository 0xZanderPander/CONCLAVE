import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from conclave.auditing.verification import AuditVerifier
from conclave.fixtures import load_design_plan_revisions
from conclave.intake import ReviewIntakeService
from conclave.ledger.repository import LedgerRepository
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.development import DevelopmentReviewerRuntime
from conclave.scheduling.worker import FixtureWorker

POSTGRES_TEST_URL = os.getenv("CONCLAVE_TEST_DATABASE_URL")

_PATHS = (
    FixturePath.A_ONLY,
    FixturePath.AB_AGREEMENT,
    FixturePath.CROSS_REVIEW_RESOLVED,
    FixturePath.C_TIE_BROKEN,
)

_EXPECTED_INVOCATIONS = {
    FixturePath.A_ONLY: 1,
    FixturePath.AB_AGREEMENT: 2,
    FixturePath.CROSS_REVIEW_RESOLVED: 4,
    FixturePath.C_TIE_BROKEN: 6,
}


@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="CONCLAVE_TEST_DATABASE_URL is required for the PostgreSQL flow test",
)
def test_postgres_runs_and_verifies_every_fixture_decision_path() -> None:
    assert POSTGRES_TEST_URL is not None
    engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)
    repository = LedgerRepository(sessionmaker(engine, expire_on_commit=False, class_=Session))
    token = uuid4().hex[:12]
    plan_id = f"integration-flows-{token}"
    revision_id = ""
    occurrence_ids: list[str] = []

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

        due_base = datetime(2001, 1, 1, tzinfo=UTC)
        for position, path in enumerate(_PATHS):
            occurrence_id = f"integration-flow-{path.value}-{token}"
            due_at = due_base + timedelta(seconds=position)
            repository.add_occurrence(
                occurrence_id=occurrence_id,
                plan_id=plan_id,
                plan_revision=revision.revision,
                due_at=due_at,
                trigger_kind="scheduled_a",
            )
            repository.enqueue_occurrence(
                occurrence_id=occurrence_id,
                due_at=due_at,
            )
            occurrence_ids.append(occurrence_id)

        worker = FixtureWorker(
            repository,
            ReviewIntakeService(repository),
            ReviewOrchestrator(repository, DevelopmentReviewerRuntime()),
        )
        auditor = AuditVerifier(repository)

        for position, path in enumerate(_PATHS):
            result = worker.run_once(
                worker_id=f"integration-worker-{token}",
                now=datetime.now(UTC),
                path=path,
            )
            assert result is not None
            assert result.occurrence_id == occurrence_ids[position]

            verification = auditor.verify_session(result.session_id)
            persisted = repository.get_result(result.session_id)
            work_item = repository.get_work_item(result.work_item_id)

            assert verification.path == path.value
            assert verification.invocation_count == _EXPECTED_INVOCATIONS[path]
            assert persisted is not None
            assert persisted.document["contract_version"] == "review-result/v1"
            assert persisted.document["panel_metadata"]["reviewers"]
            assert work_item is not None
            assert work_item.status == "completed"
            if path == FixturePath.C_TIE_BROKEN:
                assert persisted.document["disagreement"]["level"] == "tie_broken"
                assert persisted.document["panel_metadata"]["tie_breaker"] is not None
    finally:
        with engine.begin() as connection:
            event_scope = (
                "(entity_type = 'review_session' and entity_id in "
                "(select session_id from review_sessions where plan_id = :plan_id)) "
                "or entity_id in "
                "(select work_item_id from scheduler_work_items where occurrence_id in "
                "(select occurrence_id from review_occurrences where plan_id = :plan_id)) "
                "or entity_id in "
                "(select occurrence_id from review_occurrences where plan_id = :plan_id) "
                "or entity_id = :revision_id"
            )
            connection.execute(
                text(
                    "delete from event_deliveries where event_id in "
                    f"(select event_id from audit_events where {event_scope})"
                ),
                {"plan_id": plan_id, "revision_id": revision_id},
            )
            connection.execute(
                text(
                    "delete from event_streams where exists "
                    "(select 1 from audit_events where "
                    "audit_events.entity_type = event_streams.stream_type and "
                    "audit_events.entity_id = event_streams.stream_id and "
                    f"({event_scope}))"
                ),
                {"plan_id": plan_id, "revision_id": revision_id},
            )
            connection.execute(
                text(f"delete from audit_events where {event_scope}"),
                {"plan_id": plan_id, "revision_id": revision_id},
            )
            for table_name in (
                "review_results",
                "reviewer_invocations",
                "request_snapshots",
            ):
                connection.execute(
                    text(
                        f"delete from {table_name} where session_id in "
                        "(select session_id from review_sessions where plan_id = :plan_id)"
                    ),
                    {"plan_id": plan_id},
                )
            connection.execute(
                text("delete from review_sessions where plan_id = :plan_id"),
                {"plan_id": plan_id},
            )
            connection.execute(
                text(
                    "delete from scheduler_work_items where occurrence_id in "
                    "(select occurrence_id from review_occurrences where plan_id = :plan_id)"
                ),
                {"plan_id": plan_id},
            )
            connection.execute(
                text("delete from review_occurrences where plan_id = :plan_id"),
                {"plan_id": plan_id},
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
