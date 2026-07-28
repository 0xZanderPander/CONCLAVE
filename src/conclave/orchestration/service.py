import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from conclave.domain.enums import (
    ReviewerSlot,
    ReviewStage,
    ReviewState,
    TriggerKind,
)
from conclave.ledger.models import (
    RequestSnapshotRecord,
    ReviewerInvocationRecord,
    ReviewSessionRecord,
)
from conclave.ledger.repository import LedgerRepository
from conclave.orchestration.result_builder import build_review_result
from conclave.plans.models import ReviewPlanRevision, SlotSchedule
from conclave.reviewers.runtime import (
    Assessment,
    AssessmentClaim,
    CrossReviewResponse,
    PeerAssessment,
    PeerCrossReviewResponse,
    ReviewCall,
    ReviewerCJudgment,
    ReviewerProviderExhaustedError,
    ReviewerRuntime,
    ReviewOutput,
    assign_assessment_claim_ids,
)
from conclave.task_packs.comparison import (
    ComparisonResult,
    ComparisonRound,
    compare_assessments,
    comparison_trigger_labels,
    ordered_unique,
)
from conclave.task_packs.models import TaskPack
from conclave.task_packs.registry import (
    TaskPackRegistry,
    default_task_pack_registry,
)


class FixturePath(StrEnum):
    A_ONLY = "a_only"
    AB_AGREEMENT = "ab_agreement"
    CROSS_REVIEW_RESOLVED = "cross_review_resolved"
    C_TIE_BROKEN = "c_tie_broken"


class OrchestrationStateError(RuntimeError):
    pass


class ReviewOrchestrator:
    def __init__(
        self,
        repository: LedgerRepository,
        runtime: ReviewerRuntime,
        task_packs: TaskPackRegistry | None = None,
    ) -> None:
        self._repository = repository
        self._runtime = runtime
        self._task_packs = task_packs or default_task_pack_registry()

    def run(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> ReviewState:
        now = now or datetime.now(UTC)
        for _step in range(24):
            session, snapshot, revision = self._load_session(session_id)
            state = ReviewState(session.current_state)
            if state == ReviewState.RESULT_RETURNED:
                if self._repository.get_result(session_id) is None:
                    raise OrchestrationStateError(
                        "completed session is missing its immutable result"
                    )
                return state
            task_pack = self._task_pack_for_session(session, snapshot)

            if state == ReviewState.SNAPSHOTTED:
                self._transition(session_id, ReviewState.REVIEWER_A)
                continue

            if state == ReviewState.REVIEWER_A:
                self._invoke_assessment(
                    session_id=session_id,
                    snapshot_hash=snapshot.content_hash,
                    slot=ReviewerSlot.A,
                    stage=ReviewStage.INDEPENDENT,
                    round_number=1,
                    assignment=revision.slots[ReviewerSlot.A],
                    now=now,
                    snapshot=snapshot.content,
                )
                self._transition(session_id, ReviewState.BASELINE_RECORDED)
                continue

            if state == ReviewState.BASELINE_RECORDED:
                a = self._completed_assessment(
                    session_id, ReviewerSlot.A, ReviewStage.INDEPENDENT, 1
                )
                expand, _triggers = self._should_invoke_b(
                    session_id=session_id,
                    snapshot=snapshot.content,
                    assessment=a,
                    revision=revision,
                    task_pack=task_pack,
                )
                if expand:
                    self._transition(session_id, ReviewState.REVIEWER_B)
                    continue
                return self._finish_resumably(
                    session_id,
                    snapshot,
                    revision,
                    task_pack,
                )

            if state == ReviewState.REVIEWER_B:
                self._invoke_assessment(
                    session_id=session_id,
                    snapshot_hash=snapshot.content_hash,
                    slot=ReviewerSlot.B,
                    stage=ReviewStage.INDEPENDENT,
                    round_number=1,
                    assignment=revision.slots[ReviewerSlot.B],
                    now=now,
                    snapshot=snapshot.content,
                )
                self._transition(session_id, ReviewState.COMPARING)
                continue

            if state == ReviewState.COMPARING:
                a = self._completed_assessment(
                    session_id, ReviewerSlot.A, ReviewStage.INDEPENDENT, 1
                )
                b = self._completed_assessment(
                    session_id, ReviewerSlot.B, ReviewStage.INDEPENDENT, 1
                )
                comparison = compare_assessments(
                    a,
                    b,
                    task_pack,
                    failed_goal=(
                        snapshot.content["review_trigger"]["kind"]
                        == TriggerKind.FAILED_GOAL.value
                    ),
                )
                self._record_comparison(
                    session_id,
                    comparison,
                    stage=ReviewStage.INDEPENDENT,
                    round_number=1,
                    task_pack=task_pack,
                )
                if comparison.requires_cross_review:
                    self._transition(session_id, ReviewState.CROSS_REVIEW)
                    continue
                return self._finish_resumably(
                    session_id,
                    snapshot,
                    revision,
                    task_pack,
                )

            if state == ReviewState.CROSS_REVIEW:
                a = self._completed_assessment(
                    session_id, ReviewerSlot.A, ReviewStage.INDEPENDENT, 1
                )
                b = self._completed_assessment(
                    session_id, ReviewerSlot.B, ReviewStage.INDEPENDENT, 1
                )
                initial = compare_assessments(
                    a,
                    b,
                    task_pack,
                    failed_goal=(
                        snapshot.content["review_trigger"]["kind"]
                        == TriggerKind.FAILED_GOAL.value
                    ),
                )
                initial_context = ComparisonRound(
                    stage=ReviewStage.INDEPENDENT,
                    round=1,
                    comparison=initial,
                ).public_document()
                cross_a = self._invoke_cross_review(
                    session_id=session_id,
                    snapshot_hash=snapshot.content_hash,
                    slot=ReviewerSlot.A,
                    stage=ReviewStage.CROSS_REVIEW,
                    round_number=2,
                    assignment=revision.slots[ReviewerSlot.A],
                    now=now,
                    prior_claims=b.claims,
                    own_assessment=PeerAssessment(
                        slot=ReviewerSlot.A,
                        stage=ReviewStage.INDEPENDENT,
                        round=1,
                        assessment=a,
                    ),
                    snapshot=snapshot.content,
                    peer_assessments=(
                        PeerAssessment(
                            slot=ReviewerSlot.B,
                            stage=ReviewStage.INDEPENDENT,
                            round=1,
                            assessment=b,
                        ),
                    ),
                    comparison_history=(initial_context,),
                )
                cross_b = self._invoke_cross_review(
                    session_id=session_id,
                    snapshot_hash=snapshot.content_hash,
                    slot=ReviewerSlot.B,
                    stage=ReviewStage.CROSS_REVIEW,
                    round_number=2,
                    assignment=revision.slots[ReviewerSlot.B],
                    now=now,
                    prior_claims=a.claims,
                    own_assessment=PeerAssessment(
                        slot=ReviewerSlot.B,
                        stage=ReviewStage.INDEPENDENT,
                        round=1,
                        assessment=b,
                    ),
                    snapshot=snapshot.content,
                    peer_assessments=(
                        PeerAssessment(
                            slot=ReviewerSlot.A,
                            stage=ReviewStage.INDEPENDENT,
                            round=1,
                            assessment=a,
                        ),
                    ),
                    comparison_history=(initial_context,),
                )
                comparison = compare_assessments(cross_a, cross_b, task_pack)
                self._record_comparison(
                    session_id,
                    comparison,
                    stage=ReviewStage.CROSS_REVIEW,
                    round_number=2,
                    task_pack=task_pack,
                )
                if comparison.requires_cross_review:
                    self._transition(session_id, ReviewState.REVIEWER_C_INDEPENDENT)
                    continue
                return self._finish_resumably(
                    session_id,
                    snapshot,
                    revision,
                    task_pack,
                )

            if state == ReviewState.REVIEWER_C_INDEPENDENT:
                self._invoke_assessment(
                    session_id=session_id,
                    snapshot_hash=snapshot.content_hash,
                    slot=ReviewerSlot.C,
                    stage=ReviewStage.INDEPENDENT,
                    round_number=1,
                    assignment=revision.slots[ReviewerSlot.C],
                    now=now,
                    snapshot=snapshot.content,
                )
                self._transition(session_id, ReviewState.REVIEWER_C_JUDGING)
                continue

            if state == ReviewState.REVIEWER_C_JUDGING:
                a = self._completed_assessment(
                    session_id, ReviewerSlot.A, ReviewStage.CROSS_REVIEW, 2
                )
                b = self._completed_assessment(
                    session_id, ReviewerSlot.B, ReviewStage.CROSS_REVIEW, 2
                )
                c = self._completed_assessment(
                    session_id, ReviewerSlot.C, ReviewStage.INDEPENDENT, 1
                )
                initial_a = self._completed_assessment(
                    session_id, ReviewerSlot.A, ReviewStage.INDEPENDENT, 1
                )
                initial_b = self._completed_assessment(
                    session_id, ReviewerSlot.B, ReviewStage.INDEPENDENT, 1
                )
                initial = compare_assessments(
                    initial_a,
                    initial_b,
                    task_pack,
                    failed_goal=(
                        snapshot.content["review_trigger"]["kind"]
                        == TriggerKind.FAILED_GOAL.value
                    ),
                )
                cross = compare_assessments(a, b, task_pack)
                self._invoke_judgment(
                    session_id=session_id,
                    snapshot_hash=snapshot.content_hash,
                    slot=ReviewerSlot.C,
                    stage=ReviewStage.JUDGING,
                    round_number=2,
                    assignment=revision.slots[ReviewerSlot.C],
                    now=now,
                    prior_claims=c.claims + a.claims + b.claims,
                    own_assessment=PeerAssessment(
                        slot=ReviewerSlot.C,
                        stage=ReviewStage.INDEPENDENT,
                        round=1,
                        assessment=c,
                    ),
                    snapshot=snapshot.content,
                    peer_assessments=(
                        PeerAssessment(
                            slot=ReviewerSlot.C,
                            stage=ReviewStage.INDEPENDENT,
                            round=1,
                            assessment=c,
                        ),
                        PeerAssessment(
                            slot=ReviewerSlot.A,
                            stage=ReviewStage.CROSS_REVIEW,
                            round=2,
                            assessment=a,
                        ),
                        PeerAssessment(
                            slot=ReviewerSlot.B,
                            stage=ReviewStage.CROSS_REVIEW,
                            round=2,
                            assessment=b,
                        ),
                    ),
                    cross_review_responses=self._cross_review_responses_for_judgment(
                        session_id,
                        revision,
                    ),
                    comparison_history=(
                        ComparisonRound(
                            stage=ReviewStage.INDEPENDENT,
                            round=1,
                            comparison=initial,
                        ).public_document(),
                        ComparisonRound(
                            stage=ReviewStage.CROSS_REVIEW,
                            round=2,
                            comparison=cross,
                        ).public_document(),
                    ),
                )
                return self._finish_resumably(
                    session_id,
                    snapshot,
                    revision,
                    task_pack,
                )

            if state in {
                ReviewState.REVIEWER_ADJUDICATION,
                ReviewState.AUTO_RESOLVED,
                ReviewState.CALLER_DECISION_REQUIRED,
            }:
                return self._finish_resumably(
                    session_id,
                    snapshot,
                    revision,
                    task_pack,
                )

            raise OrchestrationStateError(
                f"review session cannot resume from {state.value!r}"
            )
        raise OrchestrationStateError("orchestration exceeded its bounded advance loop")

    def run_fixture_path(
        self,
        session_id: str,
        path: FixturePath,
        *,
        now: datetime | None = None,
    ) -> ReviewState:
        now = now or datetime.now(UTC)
        session, snapshot, revision = self._load_ready_session(session_id)
        if ReviewState(session.current_state) == ReviewState.RESULT_RETURNED:
            return ReviewState.RESULT_RETURNED

        self._transition(session_id, ReviewState.REVIEWER_A)
        a = self._invoke(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.A,
            stage=ReviewStage.INDEPENDENT,
            round_number=1,
            assignment=revision.slots[ReviewerSlot.A],
            now=now,
            snapshot=snapshot.content,
        )
        self._transition(session_id, ReviewState.BASELINE_RECORDED)

        if path == FixturePath.A_ONLY:
            return self._finish(session_id, path, snapshot)

        self._transition(session_id, ReviewState.REVIEWER_B)
        b = self._invoke(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.B,
            stage=ReviewStage.INDEPENDENT,
            round_number=1,
            assignment=revision.slots[ReviewerSlot.B],
            now=now,
            snapshot=snapshot.content,
        )
        self._transition(session_id, ReviewState.COMPARING)

        if path == FixturePath.AB_AGREEMENT:
            return self._finish(session_id, path, snapshot)

        self._transition(session_id, ReviewState.CROSS_REVIEW)
        task_pack = self._task_pack_for_session(session, snapshot)
        initial = compare_assessments(
            a,
            b,
            task_pack,
            failed_goal=(
                snapshot.content["review_trigger"]["kind"]
                == TriggerKind.FAILED_GOAL.value
            ),
        )
        initial_context = ComparisonRound(
            stage=ReviewStage.INDEPENDENT,
            round=1,
            comparison=initial,
        ).public_document()
        cross_a = self._invoke_cross_review(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.A,
            stage=ReviewStage.CROSS_REVIEW,
            round_number=2,
            assignment=revision.slots[ReviewerSlot.A],
            now=now,
            prior_claims=b.claims,
            own_assessment=PeerAssessment(
                slot=ReviewerSlot.A,
                stage=ReviewStage.INDEPENDENT,
                round=1,
                assessment=a,
            ),
            snapshot=snapshot.content,
            peer_assessments=(
                PeerAssessment(
                    slot=ReviewerSlot.B,
                    stage=ReviewStage.INDEPENDENT,
                    round=1,
                    assessment=b,
                ),
            ),
            comparison_history=(initial_context,),
        )
        cross_b = self._invoke_cross_review(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.B,
            stage=ReviewStage.CROSS_REVIEW,
            round_number=2,
            assignment=revision.slots[ReviewerSlot.B],
            now=now,
            prior_claims=a.claims,
            own_assessment=PeerAssessment(
                slot=ReviewerSlot.B,
                stage=ReviewStage.INDEPENDENT,
                round=1,
                assessment=b,
            ),
            snapshot=snapshot.content,
            peer_assessments=(
                PeerAssessment(
                    slot=ReviewerSlot.A,
                    stage=ReviewStage.INDEPENDENT,
                    round=1,
                    assessment=a,
                ),
            ),
            comparison_history=(initial_context,),
        )

        if path == FixturePath.CROSS_REVIEW_RESOLVED:
            return self._finish(session_id, path, snapshot)

        self._transition(session_id, ReviewState.REVIEWER_C_INDEPENDENT)
        c = self._invoke(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.C,
            stage=ReviewStage.INDEPENDENT,
            round_number=1,
            assignment=revision.slots[ReviewerSlot.C],
            now=now,
            snapshot=snapshot.content,
        )
        self._transition(session_id, ReviewState.REVIEWER_C_JUDGING)
        cross = compare_assessments(cross_a, cross_b, task_pack)
        self._invoke_judgment(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.C,
            stage=ReviewStage.JUDGING,
            round_number=2,
            assignment=revision.slots[ReviewerSlot.C],
            now=now,
            prior_claims=c.claims + cross_a.claims + cross_b.claims,
            own_assessment=PeerAssessment(
                slot=ReviewerSlot.C,
                stage=ReviewStage.INDEPENDENT,
                round=1,
                assessment=c,
            ),
            snapshot=snapshot.content,
            peer_assessments=(
                PeerAssessment(
                    slot=ReviewerSlot.C,
                    stage=ReviewStage.INDEPENDENT,
                    round=1,
                    assessment=c,
                ),
                PeerAssessment(
                    slot=ReviewerSlot.A,
                    stage=ReviewStage.CROSS_REVIEW,
                    round=2,
                    assessment=cross_a,
                ),
                PeerAssessment(
                    slot=ReviewerSlot.B,
                    stage=ReviewStage.CROSS_REVIEW,
                    round=2,
                    assessment=cross_b,
                ),
            ),
            cross_review_responses=self._cross_review_responses_for_judgment(
                session_id,
                revision,
            ),
            comparison_history=(
                initial_context,
                ComparisonRound(
                    stage=ReviewStage.CROSS_REVIEW,
                    round=2,
                    comparison=cross,
                ).public_document(),
            ),
        )
        return self._finish(session_id, path, snapshot)

    def _invoke(
        self,
        *,
        session_id: str,
        snapshot_hash: str,
        slot: ReviewerSlot,
        stage: ReviewStage,
        round_number: int,
        assignment: SlotSchedule,
        now: datetime,
        snapshot: dict[str, Any],
        prior_claims: tuple[str | AssessmentClaim, ...] = (),
        own_assessment: PeerAssessment | None = None,
        peer_assessments: tuple[PeerAssessment, ...] = (),
        cross_review_responses: tuple[PeerCrossReviewResponse, ...] = (),
        comparison_history: tuple[dict[str, Any], ...] = (),
    ) -> ReviewOutput:
        provider = assignment.provider or "fixture"
        model = assignment.model or "deterministic"
        role_version, prompt_version, schema_version = assignment.contract_for_stage(
            stage
        )
        invocation = self._repository.record_invocation(
            session_id=session_id,
            slot=slot,
            reviewer_type=assignment.reviewer_type,
            stage=stage,
            round_number=round_number,
            snapshot_hash=snapshot_hash,
            prompt_version=prompt_version,
            schema_version=schema_version,
            provider=provider,
            model=model,
        )
        if invocation.status == "completed":
            if invocation.assessment_payload is None:
                raise OrchestrationStateError(
                    f"completed invocation {invocation.invocation_id!r} has no output"
                )
            if stage == ReviewStage.JUDGING:
                return ReviewerCJudgment.model_validate(invocation.assessment_payload)
            if (
                stage == ReviewStage.CROSS_REVIEW
                and schema_version == "cross-review-v1"
            ):
                return CrossReviewResponse.model_validate(
                    invocation.assessment_payload
                )
            return Assessment.model_validate(invocation.assessment_payload)
        if invocation.status != "pending":
            raise OrchestrationStateError(
                f"invocation {invocation.invocation_id!r} cannot resume from "
                f"{invocation.status!r}"
            )
        call = ReviewCall(
            session_id=session_id,
            snapshot_hash=snapshot_hash,
            slot=slot,
            stage=stage,
            round=round_number,
            reviewer_type=assignment.reviewer_type,
            provider=provider,
            model=model,
            role_version=role_version,
            prompt_version=prompt_version,
            schema_version=schema_version,
            snapshot=snapshot,
            prior_claims=prior_claims,
            own_assessment=own_assessment,
            peer_assessments=peer_assessments,
            cross_review_responses=cross_review_responses,
            comparison_history=comparison_history,
            requested_at=now,
            provider_policy=assignment.provider_policy_for_stage(stage),
            attempt_number=invocation.attempt_count + 1,
        )
        session = self._repository.get_session(session_id)
        snapshot_record = self._repository.get_snapshot(session_id)
        if session is None or snapshot_record is None:
            raise OrchestrationStateError("invocation session or snapshot is unavailable")
        task_pack = self._task_pack_for_session(session, snapshot_record)
        try:
            execution = self._runtime.review(call)
            self._repository.record_provider_attempts(
                invocation_id=invocation.invocation_id,
                attempts=execution.attempts,
            )
            output = execution.output
            if stage == ReviewStage.JUDGING:
                if not isinstance(output, ReviewerCJudgment):
                    raise TypeError("reviewer C judging must return ReviewerCJudgment")
                if (
                    schema_version == "reviewer-c-judgment-v2"
                    and output.resolution_assessment is not None
                ):
                    output = output.model_copy(
                        update={
                            "resolution_assessment": assign_assessment_claim_ids(
                                output.resolution_assessment,
                                invocation_id=invocation.invocation_id,
                            )
                        }
                    )
                output = self._task_packs.normalize_judgment(
                    snapshot,
                    output,
                    task_pack=task_pack,
                )
                self._task_packs.validate_judgment(
                    snapshot,
                    output,
                    task_pack=task_pack,
                    schema_version=schema_version,
                    available_claim_ids=self._available_judgment_claim_ids(call),
                )
            elif stage == ReviewStage.CROSS_REVIEW and schema_version == "cross-review-v1":
                if not isinstance(output, CrossReviewResponse):
                    raise TypeError(
                        "cross-review-v1 returned a non-cross-review response"
                    )
                normalized_assessment = assign_assessment_claim_ids(
                    output.assessment,
                    invocation_id=invocation.invocation_id,
                )
                normalized_assessment = self._task_packs.normalize_assessment(
                    snapshot,
                    normalized_assessment,
                    task_pack=task_pack,
                )
                output = output.model_copy(
                    update={"assessment": normalized_assessment}
                )
                self._task_packs.validate_cross_review(
                    snapshot,
                    output,
                    peer_claim_ids=self._peer_claim_ids(call),
                    task_pack=task_pack,
                )
            else:
                if not isinstance(output, Assessment):
                    raise TypeError("assessment stage returned a reviewer-C judgment")
                if schema_version == "assessment-v2":
                    output = assign_assessment_claim_ids(
                        output,
                        invocation_id=invocation.invocation_id,
                    )
                output = self._task_packs.normalize_assessment(
                    snapshot,
                    output,
                    task_pack=task_pack,
                )
                self._task_packs.validate_assessment(
                    snapshot,
                    output,
                    task_pack=task_pack,
                    schema_version=schema_version,
                )
        except Exception as exc:
            if isinstance(exc, ReviewerProviderExhaustedError):
                self._repository.record_provider_attempts(
                    invocation_id=invocation.invocation_id,
                    attempts=exc.attempts,
                )
            self._repository.fail_invocation(
                invocation_id=invocation.invocation_id,
                error=str(exc),
                completed_at=now,
            )
            failure = (
                ReviewState.CROSS_REVIEW_FAILED
                if stage == ReviewStage.CROSS_REVIEW
                else {
                    ReviewerSlot.A: ReviewState.REVIEWER_A_FAILED,
                    ReviewerSlot.B: ReviewState.REVIEWER_B_FAILED,
                    ReviewerSlot.C: ReviewState.REVIEWER_C_FAILED,
                }[slot]
            )
            self._transition(session_id, failure)
            raise
        self._repository.complete_invocation(
            invocation_id=invocation.invocation_id,
            assessment_payload=output.model_dump(mode="json"),
            completed_at=now,
        )
        return output

    def _invoke_assessment(self, **kwargs: Any) -> Assessment:
        output = self._invoke(**kwargs)
        if not isinstance(output, Assessment):
            raise OrchestrationStateError("assessment invocation returned a judgment")
        return output

    def _invoke_cross_review(self, **kwargs: Any) -> Assessment:
        output = self._invoke(**kwargs)
        if isinstance(output, CrossReviewResponse):
            return output.assessment
        if isinstance(output, Assessment):
            return output
        raise OrchestrationStateError("cross-review invocation returned a judgment")

    def _invoke_judgment(self, **kwargs: Any) -> ReviewerCJudgment:
        output = self._invoke(**kwargs)
        if not isinstance(output, ReviewerCJudgment):
            raise OrchestrationStateError("judging invocation returned an assessment")
        return output

    @staticmethod
    def _peer_claim_ids(call: ReviewCall) -> frozenset[str]:
        return frozenset(
            claim.claim_id
            for peer in call.peer_assessments
            for claim in peer.assessment.claims
            if isinstance(claim, AssessmentClaim) and claim.claim_id is not None
        )

    @staticmethod
    def _available_judgment_claim_ids(call: ReviewCall) -> frozenset[str]:
        assessments = []
        if call.own_assessment is not None:
            assessments.append(call.own_assessment.assessment)
        assessments.extend(
            item.response.assessment for item in call.cross_review_responses
        )
        return frozenset(
            claim.claim_id
            for assessment in assessments
            for claim in assessment.claims
            if isinstance(claim, AssessmentClaim) and claim.claim_id is not None
        )

    def _finish(
        self,
        session_id: str,
        path: FixturePath,
        snapshot: RequestSnapshotRecord,
        *,
        final_assessment: Assessment | None = None,
        comparisons: tuple[ComparisonRound, ...] = (),
        judgment: ReviewerCJudgment | None = None,
        route_triggers: tuple[str, ...] = (),
        auto_resolve_enabled: bool = True,
    ) -> ReviewState:
        self._transition(session_id, ReviewState.REVIEWER_ADJUDICATION)
        session = self._repository.get_session(session_id)
        if session is None:
            raise LookupError(f"unknown review session {session_id!r}")
        document = build_review_result(
            session=session,
            snapshot=snapshot,
            invocations=self._repository.list_invocations(session_id),
            path=path.value,
            final_assessment=final_assessment,
            comparisons=comparisons,
            judgment=judgment,
            route_triggers=route_triggers,
            auto_resolve_enabled=auto_resolve_enabled,
        )
        resolution_state = (
            ReviewState.AUTO_RESOLVED
            if document["status"] == "auto_resolved"
            else ReviewState.CALLER_DECISION_REQUIRED
        )
        self._transition(session_id, resolution_state)
        self._repository.record_result(
            session_id=session_id,
            path=path.value,
            document=document,
        )
        self._transition(session_id, ReviewState.RESULT_RETURNED)
        return ReviewState.RESULT_RETURNED

    def _finish_resumably(
        self,
        session_id: str,
        snapshot: RequestSnapshotRecord,
        revision: ReviewPlanRevision,
        task_pack: TaskPack,
    ) -> ReviewState:
        (
            path,
            final,
            comparisons,
            judgment,
            route_triggers,
        ) = self._derive_outcome(
            session_id=session_id,
            snapshot=snapshot,
            revision=revision,
            task_pack=task_pack,
        )
        session = self._repository.get_session(session_id)
        if session is None:
            raise LookupError(f"unknown review session {session_id!r}")
        state = ReviewState(session.current_state)
        if state not in {
            ReviewState.REVIEWER_ADJUDICATION,
            ReviewState.AUTO_RESOLVED,
            ReviewState.CALLER_DECISION_REQUIRED,
        }:
            self._transition(session_id, ReviewState.REVIEWER_ADJUDICATION)
            state = ReviewState.REVIEWER_ADJUDICATION

        session = self._repository.get_session(session_id)
        if session is None:
            raise LookupError(f"unknown review session {session_id!r}")
        document = build_review_result(
            session=session,
            snapshot=snapshot,
            invocations=self._repository.list_invocations(session_id),
            path=path.value,
            final_assessment=final,
            comparisons=comparisons,
            judgment=judgment,
            route_triggers=route_triggers,
            auto_resolve_enabled=revision.auto_resolve_enabled,
            routing_mode="automatic",
        )
        resolution_state = (
            ReviewState.AUTO_RESOLVED
            if document["status"] == "auto_resolved"
            else ReviewState.CALLER_DECISION_REQUIRED
        )
        if state == ReviewState.REVIEWER_ADJUDICATION:
            self._transition(session_id, resolution_state)
        elif state != resolution_state:
            raise OrchestrationStateError(
                "persisted resolution state disagrees with the reconstructed result"
            )
        self._repository.record_result(
            session_id=session_id,
            path=path.value,
            document=document,
        )
        self._transition(session_id, ReviewState.RESULT_RETURNED)
        return ReviewState.RESULT_RETURNED

    def _derive_outcome(
        self,
        *,
        session_id: str,
        snapshot: RequestSnapshotRecord,
        revision: ReviewPlanRevision,
        task_pack: TaskPack,
    ) -> tuple[
        FixturePath,
        Assessment,
        tuple[ComparisonRound, ...],
        ReviewerCJudgment | None,
        tuple[str, ...],
    ]:
        a = self._completed_assessment(
            session_id, ReviewerSlot.A, ReviewStage.INDEPENDENT, 1
        )
        _expand, expansion_triggers = self._should_invoke_b(
            session_id=session_id,
            snapshot=snapshot.content,
            assessment=a,
            revision=revision,
            task_pack=task_pack,
        )
        b_record = self._find_invocation(
            session_id, ReviewerSlot.B, ReviewStage.INDEPENDENT, 1
        )
        if b_record is None:
            return FixturePath.A_ONLY, a, (), None, expansion_triggers
        b = self._completed_assessment(
            session_id, ReviewerSlot.B, ReviewStage.INDEPENDENT, 1
        )
        initial = compare_assessments(
            a,
            b,
            task_pack,
            failed_goal=(
                snapshot.content["review_trigger"]["kind"]
                == TriggerKind.FAILED_GOAL.value
            ),
        )
        self._record_comparison(
            session_id,
            initial,
            stage=ReviewStage.INDEPENDENT,
            round_number=1,
            task_pack=task_pack,
        )
        comparisons = (
            ComparisonRound(
                stage=ReviewStage.INDEPENDENT,
                round=1,
                comparison=initial,
            ),
        )
        route_triggers = ordered_unique(
            (*expansion_triggers, *comparison_trigger_labels(initial))
        )
        cross_a_record = self._find_invocation(
            session_id, ReviewerSlot.A, ReviewStage.CROSS_REVIEW, 2
        )
        cross_b_record = self._find_invocation(
            session_id, ReviewerSlot.B, ReviewStage.CROSS_REVIEW, 2
        )
        if cross_a_record is None and cross_b_record is None:
            if initial.requires_cross_review:
                raise OrchestrationStateError(
                    "cross review is required but no cross-review assessments exist"
                )
            return (
                FixturePath.AB_AGREEMENT,
                initial.merged_assessment or b,
                comparisons,
                None,
                route_triggers,
            )
        if cross_a_record is None or cross_b_record is None:
            raise OrchestrationStateError("cross review is missing one reviewer assessment")
        cross_a = self._completed_assessment(
            session_id, ReviewerSlot.A, ReviewStage.CROSS_REVIEW, 2
        )
        cross_b = self._completed_assessment(
            session_id, ReviewerSlot.B, ReviewStage.CROSS_REVIEW, 2
        )
        cross = compare_assessments(cross_a, cross_b, task_pack)
        self._record_comparison(
            session_id,
            cross,
            stage=ReviewStage.CROSS_REVIEW,
            round_number=2,
            task_pack=task_pack,
        )
        comparisons = (
            *comparisons,
            ComparisonRound(
                stage=ReviewStage.CROSS_REVIEW,
                round=2,
                comparison=cross,
            ),
        )
        judgment_record = self._find_invocation(
            session_id, ReviewerSlot.C, ReviewStage.JUDGING, 2
        )
        if judgment_record is None:
            if cross.requires_cross_review:
                raise OrchestrationStateError(
                    "reviewer C is required but no judgment exists"
                )
            return (
                FixturePath.CROSS_REVIEW_RESOLVED,
                cross.merged_assessment or cross_a,
                comparisons,
                None,
                route_triggers,
            )
        judgment = self._completed_judgment(session_id)
        if not cross.requires_cross_review:
            raise OrchestrationStateError(
                "reviewer C was invoked after cross review had converged"
            )
        if judgment.selected_slot == ReviewerSlot.A.value:
            final = cross_a
        elif judgment.selected_slot == ReviewerSlot.B.value:
            final = cross_b
        elif judgment.resolution_assessment is not None:
            final = judgment.resolution_assessment
        else:
            raise OrchestrationStateError("reviewer-C judgment has no resolution")
        return (
            FixturePath.C_TIE_BROKEN,
            final,
            comparisons,
            judgment,
            route_triggers,
        )

    def _transition(self, session_id: str, target: ReviewState) -> None:
        self._repository.transition_session(session_id, target)

    def _load_session(
        self,
        session_id: str,
    ) -> tuple[ReviewSessionRecord, RequestSnapshotRecord, ReviewPlanRevision]:
        session = self._repository.get_session(session_id)
        if session is None:
            raise LookupError(f"unknown review session {session_id!r}")
        snapshot = self._repository.get_snapshot(session_id)
        if snapshot is None:
            raise OrchestrationStateError("session has no immutable snapshot")
        state = ReviewState(session.current_state)
        resumable = {
            ReviewState.SNAPSHOTTED,
            ReviewState.REVIEWER_A,
            ReviewState.BASELINE_RECORDED,
            ReviewState.REVIEWER_B,
            ReviewState.COMPARING,
            ReviewState.CROSS_REVIEW,
            ReviewState.REVIEWER_C_INDEPENDENT,
            ReviewState.REVIEWER_C_JUDGING,
            ReviewState.REVIEWER_ADJUDICATION,
            ReviewState.AUTO_RESOLVED,
            ReviewState.CALLER_DECISION_REQUIRED,
            ReviewState.RESULT_RETURNED,
        }
        if state not in resumable:
            raise OrchestrationStateError(
                f"review session cannot run from {state.value!r}"
            )
        return (
            session,
            snapshot,
            self._find_revision(session.plan_id, session.plan_revision),
        )

    def _load_ready_session(
        self,
        session_id: str,
    ) -> tuple[ReviewSessionRecord, RequestSnapshotRecord, ReviewPlanRevision]:
        session = self._repository.get_session(session_id)
        if session is None:
            raise LookupError(f"unknown review session {session_id!r}")
        current = ReviewState(session.current_state)
        if current == ReviewState.RESULT_RETURNED:
            result = self._repository.get_result(session_id)
            snapshot = self._repository.get_snapshot(session_id)
            if result is None or snapshot is None:
                raise OrchestrationStateError("completed session is missing durable records")
            revision = self._find_revision(session.plan_id, session.plan_revision)
            return session, snapshot, revision
        if current != ReviewState.SNAPSHOTTED:
            raise OrchestrationStateError(
                f"orchestration requires snapshotted; found {current.value}"
            )
        snapshot = self._repository.get_snapshot(session_id)
        if snapshot is None:
            raise OrchestrationStateError("session has no immutable snapshot")
        return (
            session,
            snapshot,
            self._find_revision(
                session.plan_id,
                session.plan_revision,
            ),
        )

    def _task_pack_for_session(
        self,
        session: ReviewSessionRecord,
        snapshot: RequestSnapshotRecord,
    ) -> TaskPack:
        if session.task_pack_hash is None:
            return self._task_packs.get(snapshot.content["task_pack_ref"])
        record = self._repository.get_task_pack_revision(session.task_pack_hash)
        if record is None:
            raise OrchestrationStateError("session task-pack revision is unavailable")
        task_pack = TaskPack.model_validate(record.document)
        if task_pack.content_hash != session.task_pack_hash:
            raise OrchestrationStateError("pinned task-pack revision hash is invalid")
        if task_pack.task_pack_ref != snapshot.content["task_pack_ref"]:
            raise OrchestrationStateError("snapshot and pinned task pack do not match")
        return task_pack

    def _find_invocation(
        self,
        session_id: str,
        slot: ReviewerSlot,
        stage: ReviewStage,
        round_number: int,
    ) -> ReviewerInvocationRecord | None:
        return next(
            (
                invocation
                for invocation in self._repository.list_invocations(session_id)
                if invocation.reviewer_slot == slot.value
                and invocation.stage == stage.value
                and invocation.round == round_number
            ),
            None,
        )

    def _completed_assessment(
        self,
        session_id: str,
        slot: ReviewerSlot,
        stage: ReviewStage,
        round_number: int,
    ) -> Assessment:
        record = self._find_invocation(session_id, slot, stage, round_number)
        if record is None or record.status != "completed" or record.assessment_payload is None:
            raise OrchestrationStateError(
                f"missing completed {slot.value} {stage.value} round {round_number} assessment"
            )
        if (
            stage == ReviewStage.CROSS_REVIEW
            and record.schema_version == "cross-review-v1"
        ):
            return CrossReviewResponse.model_validate(
                record.assessment_payload
            ).assessment
        return Assessment.model_validate(record.assessment_payload)

    def _completed_cross_review_response(
        self,
        session_id: str,
        slot: ReviewerSlot,
    ) -> PeerCrossReviewResponse:
        record = self._find_invocation(
            session_id,
            slot,
            ReviewStage.CROSS_REVIEW,
            2,
        )
        if (
            record is None
            or record.status != "completed"
            or record.assessment_payload is None
            or record.schema_version != "cross-review-v1"
        ):
            raise OrchestrationStateError(
                f"missing completed {slot.value} cross-review-v1 response"
            )
        return PeerCrossReviewResponse(
            slot=slot,
            response=CrossReviewResponse.model_validate(
                record.assessment_payload
            ),
        )

    def _cross_review_responses_for_judgment(
        self,
        session_id: str,
        revision: ReviewPlanRevision,
    ) -> tuple[PeerCrossReviewResponse, ...]:
        _role, _prompt, schema = revision.slots[
            ReviewerSlot.C
        ].contract_for_stage(ReviewStage.JUDGING)
        if schema != "reviewer-c-judgment-v2":
            return ()
        return (
            self._completed_cross_review_response(session_id, ReviewerSlot.A),
            self._completed_cross_review_response(session_id, ReviewerSlot.B),
        )

    def _completed_judgment(self, session_id: str) -> ReviewerCJudgment:
        record = self._find_invocation(
            session_id, ReviewerSlot.C, ReviewStage.JUDGING, 2
        )
        if record is None or record.status != "completed" or record.assessment_payload is None:
            raise OrchestrationStateError("missing completed reviewer-C judgment")
        return ReviewerCJudgment.model_validate(record.assessment_payload)

    def _find_revision(
        self,
        plan_id: str,
        revision_number: int,
    ) -> ReviewPlanRevision:
        revision = next(
            (
                candidate
                for candidate in self._repository.list_plan_revisions()
                if candidate.plan_id == plan_id and candidate.revision == revision_number
            ),
            None,
        )
        if revision is None:
            raise OrchestrationStateError("session plan revision is unavailable")
        return revision

    def _should_invoke_b(
        self,
        *,
        session_id: str,
        snapshot: dict[str, Any],
        assessment: Assessment,
        revision: ReviewPlanRevision,
        task_pack: TaskPack,
    ) -> tuple[bool, tuple[str, ...]]:
        kind = TriggerKind(snapshot["review_trigger"]["kind"])
        triggers: list[str] = []
        if kind == TriggerKind.SCHEDULED_B:
            triggers.append("scheduled_b")
        if kind == TriggerKind.FAILED_GOAL and revision.panel_expansion.invoke_b_on_failed_goal:
            triggers.append("failed_goal")
        request_material = self._request_materiality(session_id)
        recommendation_material = bool(
            assessment.category in task_pack.material_recommendation_categories
            or assessment.risk in task_pack.material_risk_levels
            or any(
                action.type in task_pack.material_action_types
                for action in assessment.actions
            )
        )
        if (
            request_material
            and revision.panel_expansion.invoke_b_on_request_material
        ):
            triggers.append("request_material")
        if (
            recommendation_material
            and revision.panel_expansion.invoke_b_on_recommendation_material
        ):
            triggers.append("recommendation_material_a")
        sample_rate = revision.panel_expansion.nonmaterial_audit_sample_rate
        if not request_material and not recommendation_material and sample_rate > 0:
            sample = int(hashlib.sha256(session_id.encode()).hexdigest()[:16], 16) / (2**64)
            if sample < sample_rate:
                triggers.append("audit_sample")
        return bool(triggers), ordered_unique(triggers)

    def _request_materiality(self, session_id: str) -> bool:
        event = next(
            (
                event
                for event in self._repository.list_events(session_id)
                if event.event_type.value == "request_validated"
            ),
            None,
        )
        if event is None:
            raise OrchestrationStateError("request-validation event is unavailable")
        return bool(event.payload["material"])

    def _record_comparison(
        self,
        session_id: str,
        comparison: ComparisonResult,
        *,
        stage: ReviewStage,
        round_number: int,
        task_pack: TaskPack,
    ) -> None:
        left_slot, right_slot = (
            (ReviewerSlot.A, ReviewerSlot.B)
            if stage in {ReviewStage.INDEPENDENT, ReviewStage.CROSS_REVIEW}
            else (ReviewerSlot.A, ReviewerSlot.B)
        )
        left = self._find_invocation(session_id, left_slot, stage, round_number)
        right = self._find_invocation(session_id, right_slot, stage, round_number)
        if left is None or right is None:
            raise OrchestrationStateError("comparison inputs are unavailable")
        self._repository.record_comparison(
            session_id=session_id,
            stage=stage,
            round_number=round_number,
            distance=comparison.distance,
            weighted_distance=comparison.weighted_distance,
            tolerance=comparison.tolerance,
            dimension_distances={
                dimension.value: value
                for dimension, value in comparison.dimension_distances.items()
            },
            hard_triggers=tuple(trigger.value for trigger in comparison.hard_triggers),
            requires_cross_review=comparison.requires_cross_review,
            merge_compatible=comparison.merge_compatible,
            left_invocation_id=left.invocation_id,
            right_invocation_id=right.invocation_id,
            task_pack_hash=task_pack.content_hash,
        )
