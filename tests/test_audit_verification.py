import json
from datetime import UTC, datetime

import pytest

from conclave.auditing.verification import AuditVerifier
from conclave.fixtures import load_design_plan_revisions, load_request_fixture
from conclave.intake import ReviewIntakeService
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.paths import design_fixtures_root
from conclave.reviewers.development import DevelopmentReviewerRuntime
from tests.helpers import create_test_engine, create_test_repository


def _expected_states() -> dict[str, list[str]]:
    with (design_fixtures_root() / "fake-state-traces.json").open(encoding="utf-8") as source:
        traces = json.load(source)["traces"]
    return {
        "a_only": traces[0]["states"],
        "ab_agreement": traces[1]["states"],
        "cross_review_resolved": traces[2]["states"],
        "c_tie_broken": traces[3]["states"][:-2],
    }


@pytest.mark.parametrize(
    ("path", "expected_invocations"),
    [
        (FixturePath.A_ONLY, 1),
        (FixturePath.AB_AGREEMENT, 2),
        (FixturePath.CROSS_REVIEW_RESOLVED, 4),
        (FixturePath.C_TIE_BROKEN, 6),
    ],
)
def test_every_fixture_path_produces_a_verifiable_decision_ledger(
    path: FixturePath,
    expected_invocations: int,
) -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        accepted = ReviewIntakeService(repository).accept(
            load_request_fixture("04-surviving-reviewer-conflict.json")
        )

        ReviewOrchestrator(repository, DevelopmentReviewerRuntime()).run_fixture_path(
            accepted.session_id,
            path,
            now=datetime.now(UTC),
        )

        verification = AuditVerifier(repository).verify_session(accepted.session_id)
        result = repository.get_result(accepted.session_id)
        events = repository.audit_events("review_session", accepted.session_id)
        states = [events[0].event_payload["state"]] + [
            event.event_payload["target"]
            for event in events
            if event.event_type == "state_transitioned"
        ]

        assert verification.path == path.value
        assert verification.invocation_count == expected_invocations
        assert result is not None
        assert result.document["request_snapshot_hash"] == accepted.snapshot_hash
        assert states == _expected_states()[path.value]
    finally:
        engine.dispose()
