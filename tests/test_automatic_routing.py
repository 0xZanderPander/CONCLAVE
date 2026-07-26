from copy import deepcopy
from datetime import UTC, datetime

import pytest

from conclave.auditing.verification import AuditVerifier
from conclave.contracts.validation import ContractValidationError
from conclave.domain.enums import (
    RecommendationCategory,
    ReviewerSlot,
    ReviewStage,
    ReviewState,
)
from conclave.events.models import DomainEventType
from conclave.fixtures import load_design_plan_revisions, load_request_fixture
from conclave.intake import ReviewIntakeService
from conclave.orchestration.service import ReviewOrchestrator
from conclave.reviewers.runtime import (
    Assessment,
    FakeReviewerRuntime,
    RecommendedAction,
)
from tests.helpers import create_test_engine, create_test_repository


def _collect(*, material: bool = False, summary: str = "Collect more data.") -> Assessment:
    return Assessment(
        category=RecommendationCategory.COLLECT_MORE_DATA,
        summary=summary,
        claims=(summary,),
        material=material,
        risk="low",
        confidence=0.75,
        evidence_quality="adequate",
        expected_goal_impact="uncertain",
        tracking_health="healthy",
        optimization_eligible=True,
        primary_conversion="eligible_giveaway_entry_completed",
    )


def _pause(*, material: bool = True, summary: str = "Pause the weak creative.") -> Assessment:
    return Assessment(
        category=RecommendationCategory.OPERATIONAL_CHANGE,
        summary=summary,
        claims=(summary,),
        actions=(
            RecommendedAction(
                type="pause_creative",
                target_id="cr_b",
                confidence=0.8,
            ),
        ),
        material=material,
        risk="medium",
        confidence=0.8,
        evidence_quality="adequate",
        expected_goal_impact="positive",
        tracking_health="healthy",
        optimization_eligible=True,
        primary_conversion="eligible_giveaway_entry_completed",
    )


def _judgment() -> Assessment:
    return _collect(summary="Reviewer C selected the conservative recommendation.").model_copy(
        update={"tie_break_verdict": "select_b", "selected_slot": "B"}
    )


def _run(
    document: dict,
    responses: dict[tuple[ReviewerSlot, ReviewStage, int], Assessment],
) -> tuple:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    for revision in load_design_plan_revisions():
        repository.add_plan_revision(revision)
    accepted = ReviewIntakeService(repository).accept(document)
    runtime = FakeReviewerRuntime(responses)
    state = ReviewOrchestrator(repository, runtime).run(
        accepted.session_id,
        now=datetime.now(UTC),
    )
    result = repository.get_result(accepted.session_id)
    assert result is not None
    return engine, repository, accepted, runtime, state, result


def test_automatic_route_selects_a_only_for_nonmaterial_scheduled_a() -> None:
    engine, repository, accepted, runtime, state, result = _run(
        load_request_fixture(),
        {(ReviewerSlot.A, ReviewStage.INDEPENDENT, 1): _collect()},
    )
    try:
        assert state == ReviewState.RESULT_RETURNED
        assert result.path == "a_only"
        assert result.document["status"] == "auto_resolved"
        assert len(runtime.calls) == 1
        assert AuditVerifier(repository).verify_session(accepted.session_id).path == "a_only"
    finally:
        engine.dispose()


def test_automatic_route_selects_ab_for_scheduled_b_within_tolerance() -> None:
    document = load_request_fixture("02-weak-evidence.json")
    assessment = _collect().model_copy(
        update={
            "optimization_eligible": False,
            "evidence_quality": "insufficient",
        }
    )
    engine, repository, accepted, runtime, _state, result = _run(
        document,
        {
            (ReviewerSlot.A, ReviewStage.INDEPENDENT, 1): assessment,
            (ReviewerSlot.B, ReviewStage.INDEPENDENT, 1): assessment,
        },
    )
    try:
        assert result.path == "ab_agreement"
        assert result.document["disagreement"]["distance"] == 0
        assert result.document["disagreement"]["triggered_by"] == ["scheduled_b"]
        assert len(runtime.calls) == 2
        events = repository.list_events(accepted.session_id)
        comparisons = [
            event for event in events if event.event_type == DomainEventType.COMPARISON_COMPLETED
        ]
        assert len(comparisons) == 1
        assert not comparisons[0].payload["requires_cross_review"]
    finally:
        engine.dispose()


def test_automatic_route_stops_after_cross_review_when_revisions_converge() -> None:
    document = load_request_fixture("04-surviving-reviewer-conflict.json")
    engine, repository, accepted, runtime, _state, result = _run(
        document,
        {
            (ReviewerSlot.A, ReviewStage.INDEPENDENT, 1): _pause(),
            (ReviewerSlot.B, ReviewStage.INDEPENDENT, 1): _collect(),
            (ReviewerSlot.A, ReviewStage.CROSS_REVIEW, 2): _collect(
                summary="A revised to collect more data."
            ),
            (ReviewerSlot.B, ReviewStage.CROSS_REVIEW, 2): _collect(
                summary="B maintained collect more data."
            ),
        },
    )
    try:
        assert result.path == "cross_review_resolved"
        assert result.document["status"] == "caller_decision_required"
        assert set(result.document["disagreement"]["triggered_by"]) == {
            "scheduled_a",
            "material_a",
            "weighted_distance",
        }
        assert len(runtime.calls) == 4
        comparisons = [
            event
            for event in repository.list_events(accepted.session_id)
            if event.event_type == DomainEventType.COMPARISON_COMPLETED
        ]
        assert [event.payload["requires_cross_review"] for event in comparisons] == [
            True,
            False,
        ]
    finally:
        engine.dispose()


def test_automatic_route_invokes_c_only_when_cross_review_still_disagrees() -> None:
    document = load_request_fixture("04-surviving-reviewer-conflict.json")
    engine, repository, accepted, runtime, _state, result = _run(
        document,
        {
            (ReviewerSlot.A, ReviewStage.INDEPENDENT, 1): _pause(),
            (ReviewerSlot.B, ReviewStage.INDEPENDENT, 1): _collect(),
            (ReviewerSlot.A, ReviewStage.CROSS_REVIEW, 2): _pause(
                summary="A maintained the change."
            ),
            (ReviewerSlot.B, ReviewStage.CROSS_REVIEW, 2): _collect(
                summary="B maintained restraint."
            ),
            (ReviewerSlot.C, ReviewStage.INDEPENDENT, 1): _collect(
                summary="C independently favored restraint."
            ),
            (ReviewerSlot.C, ReviewStage.JUDGING, 2): _judgment(),
        },
    )
    try:
        assert result.path == "c_tie_broken"
        assert result.document["disagreement"]["level"] == "tie_broken"
        assert result.document["panel_metadata"]["tie_breaker"]["selected_slot"] == "B"
        assert len(runtime.calls) == 6
        assert AuditVerifier(repository).verify_session(accepted.session_id).path == "c_tie_broken"
    finally:
        engine.dispose()


def test_failed_goal_forces_one_cross_review_but_not_reviewer_c_after_agreement() -> None:
    document = deepcopy(load_request_fixture())
    document["idempotency_key"] = "failed-goal-auto-route"
    document["evidence_version"] = "failed-goal-v1"
    document["review_trigger"].update(
        {
            "occurrence_id": "occ_failed_goal_auto_route",
            "kind": "failed_goal",
        }
    )
    assessment = _collect()
    engine, repository, _accepted, runtime, _state, result = _run(
        document,
        {
            (ReviewerSlot.A, ReviewStage.INDEPENDENT, 1): assessment,
            (ReviewerSlot.B, ReviewStage.INDEPENDENT, 1): assessment,
            (ReviewerSlot.A, ReviewStage.CROSS_REVIEW, 2): assessment,
            (ReviewerSlot.B, ReviewStage.CROSS_REVIEW, 2): assessment,
        },
    )
    try:
        assert result.path == "cross_review_resolved"
        assert result.document["disagreement"]["hard_triggers"] == ["failed_goal_movement"]
        assert "hard_conflict" in result.document["disagreement"]["triggered_by"]
        assert len(runtime.calls) == 4
    finally:
        engine.dispose()


def test_invalid_task_pack_output_fails_before_completed_assessment_is_stored() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        accepted = ReviewIntakeService(repository).accept(
            load_request_fixture("02-weak-evidence.json")
        )
        unsafe = _pause(material=True)
        orchestrator = ReviewOrchestrator(
            repository,
            FakeReviewerRuntime({(ReviewerSlot.A, ReviewStage.INDEPENDENT, 1): unsafe}),
        )

        with pytest.raises(ContractValidationError, match="optimization-ineligible"):
            orchestrator.run(accepted.session_id, now=datetime.now(UTC))

        session = repository.get_session(accepted.session_id)
        invocations = repository.list_invocations(accepted.session_id)
        assert session is not None
        assert session.current_state == ReviewState.REVIEWER_A_FAILED.value
        assert len(invocations) == 1
        assert invocations[0].status == "failed"
        assert invocations[0].assessment_payload is None
    finally:
        engine.dispose()
