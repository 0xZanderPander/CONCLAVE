import hashlib
from dataclasses import dataclass

from conclave.contracts.validation import validate_review_result
from conclave.domain.enums import (
    ReviewerSlot,
    ReviewStage,
    ReviewState,
    TriggerKind,
)
from conclave.ledger.repository import LedgerRepository, canonical_hash
from conclave.orchestration.state_machine import InvalidTransitionError, validate_transition
from conclave.reviewers.runtime import Assessment, ReviewerCJudgment
from conclave.task_packs.comparison import ComparisonRound, compare_assessments
from conclave.task_packs.models import TaskPack


class AuditVerificationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AuditVerification:
    session_id: str
    path: str
    final_state: ReviewState
    event_count: int
    invocation_count: int
    result_hash: str


_EXPECTED_INVOCATIONS = {
    "a_only": 1,
    "ab_agreement": 2,
    "cross_review_resolved": 4,
    "c_tie_broken": 6,
}

_EXPECTED_STATE_PREFIXES = {
    "a_only": (
        ReviewState.REQUESTED,
        ReviewState.VALIDATED,
        ReviewState.SNAPSHOTTED,
        ReviewState.REVIEWER_A,
        ReviewState.BASELINE_RECORDED,
        ReviewState.REVIEWER_ADJUDICATION,
    ),
    "ab_agreement": (
        ReviewState.REQUESTED,
        ReviewState.VALIDATED,
        ReviewState.SNAPSHOTTED,
        ReviewState.REVIEWER_A,
        ReviewState.BASELINE_RECORDED,
        ReviewState.REVIEWER_B,
        ReviewState.COMPARING,
        ReviewState.REVIEWER_ADJUDICATION,
    ),
    "cross_review_resolved": (
        ReviewState.REQUESTED,
        ReviewState.VALIDATED,
        ReviewState.SNAPSHOTTED,
        ReviewState.REVIEWER_A,
        ReviewState.BASELINE_RECORDED,
        ReviewState.REVIEWER_B,
        ReviewState.COMPARING,
        ReviewState.CROSS_REVIEW,
        ReviewState.REVIEWER_ADJUDICATION,
    ),
    "c_tie_broken": (
        ReviewState.REQUESTED,
        ReviewState.VALIDATED,
        ReviewState.SNAPSHOTTED,
        ReviewState.REVIEWER_A,
        ReviewState.BASELINE_RECORDED,
        ReviewState.REVIEWER_B,
        ReviewState.COMPARING,
        ReviewState.CROSS_REVIEW,
        ReviewState.REVIEWER_C_INDEPENDENT,
        ReviewState.REVIEWER_C_JUDGING,
        ReviewState.REVIEWER_ADJUDICATION,
    ),
}


class AuditVerifier:
    def __init__(self, repository: LedgerRepository) -> None:
        self._repository = repository

    def verify_session(self, session_id: str) -> AuditVerification:
        session = self._repository.get_session(session_id)
        if session is None:
            raise AuditVerificationError(f"unknown review session {session_id!r}")
        snapshot = self._repository.get_snapshot(session_id)
        if snapshot is None:
            raise AuditVerificationError("review session has no immutable snapshot")
        result = self._repository.get_result(session_id)
        if result is None:
            raise AuditVerificationError("review session has no immutable result")

        events = self._repository.audit_events("review_session", session_id)
        expected_indices = list(range(1, len(events) + 1))
        actual_indices = [event.event_index for event in events]
        if actual_indices != expected_indices:
            raise AuditVerificationError(f"audit indices are not contiguous: {actual_indices!r}")
        if not events or events[0].event_type != "session_created":
            raise AuditVerificationError("audit stream does not start with session_created")

        reconstructed = ReviewState(events[0].event_payload["state"])
        state_trace = [reconstructed]
        result_recorded = False
        for event in events[1:]:
            if event.event_type == "result_recorded":
                if result_recorded:
                    raise AuditVerificationError("result was recorded more than once")
                if event.event_payload["result_hash"] != result.result_hash:
                    raise AuditVerificationError("result hash differs from audit event")
                result_recorded = True
            if event.event_type != "state_transitioned":
                continue
            source = ReviewState(event.event_payload["source"])
            target = ReviewState(event.event_payload["target"])
            if source != reconstructed:
                raise AuditVerificationError(
                    f"transition source {source.value!r} does not match {reconstructed.value!r}"
                )
            try:
                validate_transition(source, target)
            except InvalidTransitionError as exc:
                raise AuditVerificationError(str(exc)) from exc
            if target == ReviewState.RESULT_RETURNED and not result_recorded:
                raise AuditVerificationError("result_returned occurred before result_recorded")
            reconstructed = target
            state_trace.append(target)

        if reconstructed.value != session.current_state:
            raise AuditVerificationError(
                "reconstructed state does not match the persisted session state"
            )
        if reconstructed != ReviewState.RESULT_RETURNED:
            raise AuditVerificationError(f"review session is not complete: {reconstructed.value!r}")
        if canonical_hash(result.document) != result.result_hash:
            raise AuditVerificationError("persisted result hash is invalid")
        validate_review_result(result.document, snapshot.content)

        invocations = self._repository.list_invocations(session_id)
        expected_invocations = _EXPECTED_INVOCATIONS.get(result.path)
        if expected_invocations is None:
            raise AuditVerificationError(f"unknown result path {result.path!r}")
        resolution_state = (
            ReviewState.AUTO_RESOLVED
            if result.document["status"] == "auto_resolved"
            else ReviewState.CALLER_DECISION_REQUIRED
        )
        expected_states = (
            *_EXPECTED_STATE_PREFIXES[result.path],
            resolution_state,
            ReviewState.RESULT_RETURNED,
        )
        if tuple(state_trace) != expected_states:
            raise AuditVerificationError(
                "state trace does not match the persisted decision path: "
                f"{[state.value for state in state_trace]!r}"
            )
        if len(invocations) != expected_invocations:
            raise AuditVerificationError(
                f"expected {expected_invocations} invocations; found {len(invocations)}"
            )
        if any(invocation.status != "completed" for invocation in invocations):
            raise AuditVerificationError("one or more reviewer invocations did not complete")
        if any(invocation.snapshot_hash != snapshot.content_hash for invocation in invocations):
            raise AuditVerificationError("reviewers did not use one immutable snapshot")
        self._verify_decision_route(
            session_id=session_id,
            session=session,
            snapshot=snapshot.content,
            result=result.document,
            result_path=result.path,
            invocations=invocations,
        )

        return AuditVerification(
            session_id=session_id,
            path=result.path,
            final_state=reconstructed,
            event_count=len(events),
            invocation_count=len(invocations),
            result_hash=result.result_hash,
        )

    def _verify_decision_route(
        self,
        *,
        session_id: str,
        session,
        snapshot: dict,
        result: dict,
        result_path: str,
        invocations: list,
    ) -> None:
        if result.get("task_pack_hash") != session.task_pack_hash:
            raise AuditVerificationError("result does not reference the pinned task pack")
        if result["panel_metadata"].get("routing_mode") != "automatic":
            return
        if session.task_pack_hash is None:
            return
        task_pack_record = self._repository.get_task_pack_revision(
            session.task_pack_hash
        )
        if task_pack_record is None:
            raise AuditVerificationError("pinned task-pack revision is unavailable")
        task_pack = TaskPack.model_validate(task_pack_record.document)
        if task_pack.content_hash != session.task_pack_hash:
            raise AuditVerificationError("pinned task-pack hash is invalid")

        def record(slot: ReviewerSlot, stage: ReviewStage, round_number: int):
            match = next(
                (
                    item
                    for item in invocations
                    if item.reviewer_slot == slot.value
                    and item.stage == stage.value
                    and item.round == round_number
                ),
                None,
            )
            if match is None or match.assessment_payload is None:
                raise AuditVerificationError(
                    f"missing {slot.value} {stage.value} round {round_number} output"
                )
            return match

        a_record = record(ReviewerSlot.A, ReviewStage.INDEPENDENT, 1)
        a = Assessment.model_validate(a_record.assessment_payload)
        if result_path == "a_only":
            self._verify_a_only_expansion(session_id, snapshot, a, session)
            final = a
            expected_rounds: tuple[ComparisonRound, ...] = ()
        else:
            b_record = record(ReviewerSlot.B, ReviewStage.INDEPENDENT, 1)
            b = Assessment.model_validate(b_record.assessment_payload)
            initial = compare_assessments(
                a,
                b,
                task_pack,
                failed_goal=(
                    snapshot["review_trigger"]["kind"]
                    == TriggerKind.FAILED_GOAL.value
                ),
            )
            expected_rounds = (
                ComparisonRound(
                    stage=ReviewStage.INDEPENDENT,
                    round=1,
                    comparison=initial,
                ),
            )
            if result_path == "ab_agreement":
                if initial.requires_cross_review:
                    raise AuditVerificationError(
                        "A/B agreement path exceeded comparator tolerance"
                    )
                final = initial.merged_assessment or b
            else:
                if not initial.requires_cross_review:
                    raise AuditVerificationError(
                        "cross review began without a comparator trigger"
                    )
                cross_a_record = record(
                    ReviewerSlot.A, ReviewStage.CROSS_REVIEW, 2
                )
                cross_b_record = record(
                    ReviewerSlot.B, ReviewStage.CROSS_REVIEW, 2
                )
                cross_a = Assessment.model_validate(
                    cross_a_record.assessment_payload
                )
                cross_b = Assessment.model_validate(
                    cross_b_record.assessment_payload
                )
                cross = compare_assessments(cross_a, cross_b, task_pack)
                expected_rounds = (
                    *expected_rounds,
                    ComparisonRound(
                        stage=ReviewStage.CROSS_REVIEW,
                        round=2,
                        comparison=cross,
                    ),
                )
                if result_path == "cross_review_resolved":
                    if cross.requires_cross_review:
                        raise AuditVerificationError(
                            "cross-review result did not converge"
                        )
                    final = cross.merged_assessment or cross_a
                else:
                    if not cross.requires_cross_review:
                        raise AuditVerificationError(
                            "reviewer C ran after cross review converged"
                        )
                    judgment_record = record(
                        ReviewerSlot.C, ReviewStage.JUDGING, 2
                    )
                    judgment = ReviewerCJudgment.model_validate(
                        judgment_record.assessment_payload
                    )
                    if judgment.selected_slot == ReviewerSlot.A.value:
                        final = cross_a
                    elif judgment.selected_slot == ReviewerSlot.B.value:
                        final = cross_b
                    elif judgment.resolution_assessment is not None:
                        final = judgment.resolution_assessment
                    else:
                        raise AuditVerificationError(
                            "reviewer-C judgment has no resolution"
                        )
                    tie_breaker = result["panel_metadata"]["tie_breaker"]
                    if (
                        tie_breaker["verdict"] != judgment.verdict
                        or tie_breaker["selected_slot"] != judgment.selected_slot
                    ):
                        raise AuditVerificationError(
                            "published tie-break metadata differs from reviewer C"
                        )

        expected_history = [
            comparison_round.public_document()
            for comparison_round in expected_rounds
        ]
        if result.get("comparison_history") != expected_history:
            raise AuditVerificationError(
                "result comparison history differs from recomputed comparisons"
            )
        self._verify_comparison_events(
            session_id,
            expected_rounds,
            invocations,
            session.task_pack_hash,
        )
        expected_recommendation = {
            "category": final.category.value,
            "summary": final.summary,
            "actions": [
                action.model_dump(mode="json", exclude_none=False)
                for action in final.actions
            ],
            "experiment": final.experiment,
        }
        if result["recommendation"] != expected_recommendation:
            raise AuditVerificationError(
                "published recommendation differs from the resolved assessment"
            )

    def _verify_comparison_events(
        self,
        session_id: str,
        comparisons: tuple[ComparisonRound, ...],
        invocations: list,
        task_pack_hash: str,
    ) -> None:
        events = [
            event
            for event in self._repository.list_events(session_id)
            if event.event_type.value == "comparison_completed"
        ]
        if len(events) != len(comparisons):
            raise AuditVerificationError(
                "comparison-event count differs from the result history"
            )
        for event, comparison_round in zip(events, comparisons, strict=True):
            expected = comparison_round.public_document()
            left = next(
                item
                for item in invocations
                if item.reviewer_slot == ReviewerSlot.A.value
                and item.stage == comparison_round.stage.value
                and item.round == comparison_round.round
            )
            right = next(
                item
                for item in invocations
                if item.reviewer_slot == ReviewerSlot.B.value
                and item.stage == comparison_round.stage.value
                and item.round == comparison_round.round
            )
            event_expected = {
                "distance": expected["distance"],
                "weighted_distance": expected["weighted_distance"],
                "tolerance": expected["tolerance"],
                "dimension_distances": expected["dimension_distances"],
                "hard_triggers": expected["hard_triggers"],
                "merge_compatible": expected["merge_compatible"],
                "requires_cross_review": expected["requires_cross_review"],
                "left_invocation_id": left.invocation_id,
                "right_invocation_id": right.invocation_id,
                "task_pack_hash": task_pack_hash,
            }
            if event.payload != event_expected:
                raise AuditVerificationError(
                    "comparison event differs from the recomputed decision"
                )

    def _verify_a_only_expansion(
        self,
        session_id: str,
        snapshot: dict,
        assessment: Assessment,
        session,
    ) -> None:
        revision = next(
            (
                candidate
                for candidate in self._repository.list_plan_revisions()
                if candidate.plan_id == session.plan_id
                and candidate.revision == session.plan_revision
            ),
            None,
        )
        if revision is None:
            raise AuditVerificationError("review plan revision is unavailable")
        validation = next(
            (
                event
                for event in self._repository.list_events(session_id)
                if event.event_type.value == "request_validated"
            ),
            None,
        )
        if validation is None:
            raise AuditVerificationError("request-validation event is unavailable")
        kind = TriggerKind(snapshot["review_trigger"]["kind"])
        requires_b = (
            kind == TriggerKind.SCHEDULED_B
            or (
                kind == TriggerKind.FAILED_GOAL
                and revision.panel_expansion.invoke_b_on_failed_goal
            )
            or (
                bool(validation.payload["material"])
                and revision.panel_expansion.invoke_b_on_request_material
            )
            or (
                assessment.material
                and revision.panel_expansion.invoke_b_on_recommendation_material
            )
        )
        sample_rate = revision.panel_expansion.nonmaterial_audit_sample_rate
        if not requires_b and sample_rate > 0:
            sample = int(
                hashlib.sha256(session_id.encode()).hexdigest()[:16],
                16,
            ) / (2**64)
            requires_b = sample < sample_rate
        if requires_b:
            raise AuditVerificationError("A-only path bypassed a reviewer-B trigger")
