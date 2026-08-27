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
from conclave.reviewers.prompts import (
    REVIEWER_A_CROSS_PROMPT_VERSION,
    REVIEWER_A_CROSS_ROLE_VERSION,
    REVIEWER_B_CROSS_PROMPT_VERSION,
    REVIEWER_B_CROSS_ROLE_VERSION,
    REVIEWER_C_BLIND_PROMPT_VERSION,
    REVIEWER_C_BLIND_ROLE_VERSION,
    REVIEWER_C_JUDGE_PROMPT_VERSION,
    REVIEWER_C_JUDGE_ROLE_VERSION,
)
from conclave.reviewers.runtime import (
    Assessment,
    AssessmentClaim,
    CrossReviewResponse,
    FakeReviewerRuntime,
    PeerClaimReview,
    PermanentReviewerProviderError,
    ProviderRegistryRuntime,
    RecommendedAction,
    ReviewCall,
    ReviewerCJudgment,
    ReviewerExecution,
    ReviewerProviderExhaustedError,
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


def _judgment() -> ReviewerCJudgment:
    return ReviewerCJudgment(
        verdict="select_b",
        selected_slot="B",
        summary="Reviewer C selected the conservative recommendation.",
        confidence=0.75,
        evidence_quality="adequate",
    )


def _select_a_judgment() -> ReviewerCJudgment:
    return ReviewerCJudgment(
        verdict="select_a",
        selected_slot="A",
        summary="Reviewer C selected reviewer A.",
        confidence=0.8,
        evidence_quality="adequate",
    )


def _structured(
    assessment: Assessment,
    *,
    statement: str,
) -> Assessment:
    return assessment.model_copy(
        update={
            "claims": (
                AssessmentClaim(
                    statement=statement,
                    evidence_references=(
                        "sections.evidence.metrics.primary_conversions",
                        "quality.optimization_eligible",
                    ),
                ),
            )
        }
    )


def _phase4b_revision(revision):
    slots = dict(revision.slots)
    slots[ReviewerSlot.A] = slots[ReviewerSlot.A].model_copy(
        update={
            "schema_version": "assessment-v2",
            "cross_review_role_version": REVIEWER_A_CROSS_ROLE_VERSION,
            "cross_review_prompt_version": REVIEWER_A_CROSS_PROMPT_VERSION,
            "cross_review_schema_version": "cross-review-v1",
        }
    )
    slots[ReviewerSlot.B] = slots[ReviewerSlot.B].model_copy(
        update={
            "schema_version": "assessment-v2",
            "cross_review_role_version": REVIEWER_B_CROSS_ROLE_VERSION,
            "cross_review_prompt_version": REVIEWER_B_CROSS_PROMPT_VERSION,
            "cross_review_schema_version": "cross-review-v1",
        }
    )
    slots[ReviewerSlot.C] = slots[ReviewerSlot.C].model_copy(
        update={
            "role_version": REVIEWER_C_BLIND_ROLE_VERSION,
            "prompt_version": REVIEWER_C_BLIND_PROMPT_VERSION,
            "schema_version": "assessment-v2",
            "judging_role_version": REVIEWER_C_JUDGE_ROLE_VERSION,
            "judging_prompt_version": REVIEWER_C_JUDGE_PROMPT_VERSION,
            "judging_schema_version": "reviewer-c-judgment-v2",
        }
    )
    return revision.model_copy(update={"slots": slots})


class Phase4BContractRuntime:
    def __init__(self) -> None:
        self.calls: list[ReviewCall] = []

    def review(self, call: ReviewCall) -> ReviewerExecution:
        self.calls.append(call)
        if call.stage == ReviewStage.JUDGING:
            assert call.own_assessment is not None
            supporting = tuple(
                claim.claim_id
                for response in call.cross_review_responses
                if response.slot == ReviewerSlot.B
                for claim in response.response.assessment.claims
                if isinstance(claim, AssessmentClaim) and claim.claim_id
            )
            rejected = tuple(
                claim.claim_id
                for response in call.cross_review_responses
                if response.slot == ReviewerSlot.A
                for claim in response.response.assessment.claims
                if isinstance(claim, AssessmentClaim) and claim.claim_id
            )
            unresolved = tuple(
                claim.claim_id
                for claim in call.own_assessment.assessment.claims
                if isinstance(claim, AssessmentClaim) and claim.claim_id
            )
            return ReviewerExecution(
                output=ReviewerCJudgment(
                    verdict="select_b",
                    selected_slot="B",
                    summary="Reviewer B is better supported.",
                    confidence=0.76,
                    evidence_quality="adequate",
                    supporting_claim_ids=supporting,
                    rejected_claim_ids=rejected,
                    unresolved_claim_ids=unresolved,
                )
            )
        if call.slot == ReviewerSlot.A:
            assessment = _structured(
                _pause(summary="A supports pausing the weaker creative."),
                statement="Creative B has a higher submitted CPA.",
            )
        else:
            assessment = _structured(
                _collect(summary=f"{call.slot.value} supports collecting more data."),
                statement="The submitted evidence supports continued observation.",
            )
        if call.stage == ReviewStage.CROSS_REVIEW:
            peer_claims = [
                claim
                for peer in call.peer_assessments
                for claim in peer.assessment.claims
                if isinstance(claim, AssessmentClaim) and claim.claim_id
            ]
            return ReviewerExecution(
                output=CrossReviewResponse(
                    disposition="affirm",
                    peer_claim_reviews=tuple(
                        PeerClaimReview(
                            claim_id=claim.claim_id,
                            position="challenge",
                            summary="The peer claim does not change this recommendation.",
                            evidence_references=(
                                "sections.evidence.metrics.primary_conversions",
                            ),
                        )
                        for claim in peer_claims
                    ),
                    assessment=assessment,
                )
            )
        return ReviewerExecution(output=assessment)


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
        assert result.document["disagreement"]["triggered_by"] == [
            "scheduled_b",
            "request_material",
        ]
        assert len(runtime.calls) == 2
        assert runtime.calls[0].snapshot_hash == runtime.calls[1].snapshot_hash
        assert runtime.calls[0].snapshot == runtime.calls[1].snapshot
        assert runtime.calls[0].prior_claims == ()
        assert runtime.calls[1].prior_claims == ()
        assert runtime.calls[0].peer_assessments == ()
        assert runtime.calls[1].peer_assessments == ()
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
            "recommendation_material_a",
            "merge_incompatible",
        }
        assert result.document["disagreement"]["distance"] == 0
        assert [item["distance"] for item in result.document["comparison_history"]] == [
            pytest.approx(0.77),
            0,
        ]
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


def test_cross_review_provider_failure_is_terminal_and_auditable() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        accepted = ReviewIntakeService(repository).accept(
            load_request_fixture("04-surviving-reviewer-conflict.json")
        )
        runtime = FakeReviewerRuntime(
            {
                (ReviewerSlot.A, ReviewStage.INDEPENDENT, 1): _pause(),
                (ReviewerSlot.B, ReviewStage.INDEPENDENT, 1): _collect(),
            }
        )

        with pytest.raises(LookupError, match="no fake reviewer response"):
            ReviewOrchestrator(repository, runtime).run(
                accepted.session_id,
                now=datetime.now(UTC),
            )

        session = repository.get_session(accepted.session_id)
        invocations = repository.list_invocations(accepted.session_id)
        events = repository.audit_events("review_session", accepted.session_id)

        assert session is not None
        assert session.current_state == ReviewState.CROSS_REVIEW_FAILED.value
        assert [(item.reviewer_slot, item.stage, item.status) for item in invocations] == [
            ("A", ReviewStage.INDEPENDENT.value, "completed"),
            ("B", ReviewStage.INDEPENDENT.value, "completed"),
            ("A", ReviewStage.CROSS_REVIEW.value, "failed"),
        ]
        assert not any(item.reviewer_slot == "C" for item in invocations)
        assert [event.event_index for event in events] == list(
            range(1, len(events) + 1)
        )
        transition = next(
            event
            for event in reversed(events)
            if event.event_type == DomainEventType.STATE_TRANSITIONED.value
        )
        assert transition.event_payload == {
            "source": ReviewState.CROSS_REVIEW.value,
            "target": ReviewState.CROSS_REVIEW_FAILED.value,
        }
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


def test_phase4b_contracts_preserve_blind_c1_and_structured_c2_judgment() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(_phase4b_revision(revision))
        accepted = ReviewIntakeService(repository).accept(
            load_request_fixture("04-surviving-reviewer-conflict.json")
        )
        runtime = Phase4BContractRuntime()

        state = ReviewOrchestrator(repository, runtime).run(
            accepted.session_id,
            now=datetime.now(UTC),
        )

        assert state == ReviewState.RESULT_RETURNED
        assert len(runtime.calls) == 6
        cross_calls = [
            call for call in runtime.calls if call.stage == ReviewStage.CROSS_REVIEW
        ]
        assert len(cross_calls) == 2
        assert all(call.own_assessment is not None for call in cross_calls)
        assert all(len(call.peer_assessments) == 1 for call in cross_calls)
        assert all(len(call.comparison_history) == 1 for call in cross_calls)
        c1 = runtime.calls[4]
        assert c1.slot == ReviewerSlot.C
        assert c1.stage == ReviewStage.INDEPENDENT
        assert c1.own_assessment is None
        assert c1.peer_assessments == ()
        assert c1.cross_review_responses == ()
        assert c1.comparison_history == ()
        c2 = runtime.calls[5]
        assert c2.stage == ReviewStage.JUDGING
        assert c2.own_assessment is not None
        assert {item.slot for item in c2.cross_review_responses} == {
            ReviewerSlot.A,
            ReviewerSlot.B,
        }
        assert len(c2.comparison_history) == 2

        invocations = repository.list_invocations(accepted.session_id)
        cross_records = [
            item for item in invocations if item.stage == ReviewStage.CROSS_REVIEW.value
        ]
        assert all(item.schema_version == "cross-review-v1" for item in cross_records)
        assert all(
            item.assessment_payload
            and item.assessment_payload["disposition"] == "affirm"
            and item.assessment_payload["peer_claim_reviews"]
            for item in cross_records
        )
        judgment = next(
            item
            for item in invocations
            if item.stage == ReviewStage.JUDGING.value
        )
        assert judgment.schema_version == "reviewer-c-judgment-v2"
        assert judgment.assessment_payload
        assert judgment.assessment_payload["supporting_claim_ids"]
        assert judgment.assessment_payload["rejected_claim_ids"]
        assert judgment.assessment_payload["unresolved_claim_ids"]
        result = repository.get_result(accepted.session_id)
        assert result is not None
        assert result.path == "c_tie_broken"
        assert result.document["status"] == "caller_decision_required"
        assert AuditVerifier(repository).verify_session(
            accepted.session_id
        ).path == "c_tie_broken"
    finally:
        engine.dispose()


class RecoverableCrossReviewProvider:
    def __init__(self) -> None:
        self.failed = False

    def invoke(self, call: ReviewCall) -> Assessment:
        if (
            call.slot == ReviewerSlot.A
            and call.stage == ReviewStage.CROSS_REVIEW
            and not self.failed
        ):
            self.failed = True
            raise PermanentReviewerProviderError("simulated cross-review failure")
        if call.stage == ReviewStage.INDEPENDENT and call.slot == ReviewerSlot.A:
            return _pause()
        return _collect()


def test_operator_can_recover_one_failed_cross_review_without_losing_history() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        revisions = load_design_plan_revisions()
        for revision in revisions:
            slots = {
                slot: schedule.model_copy(update={"provider": "recoverable"})
                for slot, schedule in revision.slots.items()
            }
            repository.add_plan_revision(revision.model_copy(update={"slots": slots}))
        accepted = ReviewIntakeService(repository).accept(
            load_request_fixture("04-surviving-reviewer-conflict.json")
        )
        runtime = ProviderRegistryRuntime(
            {"recoverable": RecoverableCrossReviewProvider()},
            max_attempts=1,
        )
        orchestrator = ReviewOrchestrator(repository, runtime)

        with pytest.raises(ReviewerProviderExhaustedError):
            orchestrator.run(accepted.session_id, now=datetime.now(UTC))
        failed_session = repository.get_session(accepted.session_id)
        assert failed_session is not None
        assert failed_session.current_state == ReviewState.CROSS_REVIEW_FAILED.value

        recovered = repository.recover_cross_review(
            session_id=accepted.session_id,
            operator_id="operator_test",
            reason="Provider access restored.",
            recovered_at=datetime.now(UTC),
        )
        assert recovered.current_state == ReviewState.CROSS_REVIEW.value

        state = orchestrator.run(accepted.session_id, now=datetime.now(UTC))
        assert state == ReviewState.RESULT_RETURNED
        cross_a = next(
            item
            for item in repository.list_invocations(accepted.session_id)
            if item.reviewer_slot == ReviewerSlot.A.value
            and item.stage == ReviewStage.CROSS_REVIEW.value
        )
        attempts = repository.list_provider_attempts(cross_a.invocation_id)
        assert [attempt.attempt_number for attempt in attempts] == [1, 2]
        assert [attempt.status for attempt in attempts] == [
            "permanent_failure",
            "succeeded",
        ]
        recovery = next(
            event
            for event in repository.list_events(accepted.session_id)
            if event.event_type == DomainEventType.STATE_TRANSITIONED
            and event.payload.get("source")
            == ReviewState.CROSS_REVIEW_FAILED.value
        )
        assert recovery.actor is not None
        assert recovery.actor.type.value == "operator"
        assert recovery.payload["recovered_invocation_id"] == cross_a.invocation_id
        assert AuditVerifier(repository).verify_session(
            accepted.session_id
        ).path == "cross_review_resolved"
    finally:
        engine.dispose()


def test_reviewer_c_select_a_publishes_a_cross_review_assessment() -> None:
    document = load_request_fixture("04-surviving-reviewer-conflict.json")
    engine, repository, accepted, _runtime, _state, result = _run(
        document,
        {
            (ReviewerSlot.A, ReviewStage.INDEPENDENT, 1): _pause(),
            (ReviewerSlot.B, ReviewStage.INDEPENDENT, 1): _collect(),
            (ReviewerSlot.A, ReviewStage.CROSS_REVIEW, 2): _pause(
                summary="A retained the pause recommendation."
            ),
            (ReviewerSlot.B, ReviewStage.CROSS_REVIEW, 2): _collect(
                summary="B retained the observation recommendation."
            ),
            (ReviewerSlot.C, ReviewStage.INDEPENDENT, 1): _collect(),
            (ReviewerSlot.C, ReviewStage.JUDGING, 2): _select_a_judgment(),
        },
    )
    try:
        assert result.document["panel_metadata"]["tie_breaker"] == {
            "verdict": "select_a",
            "selected_slot": "A",
            "confidence": 0.8,
            "evidence_quality": "adequate",
            "unresolved_claims": [],
        }
        assert result.document["recommendation"]["category"] == "operational_change"
        assert result.document["recommendation"]["summary"] == (
            "A retained the pause recommendation."
        )
        assert (
            AuditVerifier(repository).verify_session(accepted.session_id).path
            == "c_tie_broken"
        )
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
        assert result.document["disagreement"]["hard_triggers"] == []
        assert result.document["comparison_history"][0]["hard_triggers"] == [
            "failed_goal_movement"
        ]
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

        with pytest.raises(
            ContractValidationError,
            match="optimization-ineligible evidence",
        ):
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
