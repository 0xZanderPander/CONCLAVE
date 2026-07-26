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
from conclave.ledger.models import RequestSnapshotRecord, ReviewSessionRecord
from conclave.ledger.repository import LedgerRepository
from conclave.orchestration.result_builder import build_review_result
from conclave.plans.models import ReviewPlanRevision, SlotSchedule
from conclave.reviewers.runtime import (
    Assessment,
    PeerAssessment,
    ReviewCall,
    ReviewerRuntime,
)
from conclave.task_packs.comparison import (
    ComparisonResult,
    compare_assessments,
    comparison_trigger_labels,
    ordered_unique,
)
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
        session, snapshot, revision = self._load_ready_session(session_id)
        if ReviewState(session.current_state) == ReviewState.RESULT_RETURNED:
            return ReviewState.RESULT_RETURNED
        task_pack = self._task_packs.get(snapshot.content["task_pack_ref"])

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

        expand, expansion_triggers = self._should_invoke_b(
            session_id=session_id,
            snapshot=snapshot.content,
            assessment=a,
            revision=revision,
        )
        if not expand:
            return self._finish(
                session_id,
                FixturePath.A_ONLY,
                snapshot,
                final_assessment=a,
                route_triggers=expansion_triggers,
                auto_resolve_enabled=revision.auto_resolve_enabled,
            )

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
        initial_comparison = compare_assessments(
            a,
            b,
            task_pack,
            failed_goal=(
                snapshot.content["review_trigger"]["kind"] == TriggerKind.FAILED_GOAL.value
            ),
        )
        self._record_comparison(
            session_id,
            initial_comparison,
            stage=ReviewStage.INDEPENDENT,
            round_number=1,
        )
        comparison_triggers = ordered_unique(
            (*expansion_triggers, *comparison_trigger_labels(initial_comparison))
        )
        if not initial_comparison.requires_cross_review:
            final = initial_comparison.merged_assessment or b
            return self._finish(
                session_id,
                FixturePath.AB_AGREEMENT,
                snapshot,
                final_assessment=final,
                comparison=initial_comparison,
                route_triggers=comparison_triggers,
                auto_resolve_enabled=revision.auto_resolve_enabled,
            )

        self._transition(session_id, ReviewState.CROSS_REVIEW)
        cross_a = self._invoke(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.A,
            stage=ReviewStage.CROSS_REVIEW,
            round_number=2,
            assignment=revision.slots[ReviewerSlot.A],
            now=now,
            prior_claims=b.claims,
            snapshot=snapshot.content,
            peer_assessments=(
                PeerAssessment(
                    slot=ReviewerSlot.B,
                    stage=ReviewStage.INDEPENDENT,
                    round=1,
                    assessment=b,
                ),
            ),
        )
        cross_b = self._invoke(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.B,
            stage=ReviewStage.CROSS_REVIEW,
            round_number=2,
            assignment=revision.slots[ReviewerSlot.B],
            now=now,
            prior_claims=a.claims,
            snapshot=snapshot.content,
            peer_assessments=(
                PeerAssessment(
                    slot=ReviewerSlot.A,
                    stage=ReviewStage.INDEPENDENT,
                    round=1,
                    assessment=a,
                ),
            ),
        )
        cross_comparison = compare_assessments(cross_a, cross_b, task_pack)
        self._record_comparison(
            session_id,
            cross_comparison,
            stage=ReviewStage.CROSS_REVIEW,
            round_number=2,
        )
        if not cross_comparison.requires_cross_review:
            final = cross_comparison.merged_assessment or cross_a
            return self._finish(
                session_id,
                FixturePath.CROSS_REVIEW_RESOLVED,
                snapshot,
                final_assessment=final,
                comparison=initial_comparison,
                route_triggers=comparison_triggers,
                auto_resolve_enabled=revision.auto_resolve_enabled,
            )

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
        judgment = self._invoke(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.C,
            stage=ReviewStage.JUDGING,
            round_number=2,
            assignment=revision.slots[ReviewerSlot.C],
            now=now,
            prior_claims=c.claims + cross_a.claims + cross_b.claims,
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
        )
        return self._finish(
            session_id,
            FixturePath.C_TIE_BROKEN,
            snapshot,
            final_assessment=judgment,
            comparison=initial_comparison,
            route_triggers=comparison_triggers,
            auto_resolve_enabled=revision.auto_resolve_enabled,
        )

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
        cross_a = self._invoke(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.A,
            stage=ReviewStage.CROSS_REVIEW,
            round_number=2,
            assignment=revision.slots[ReviewerSlot.A],
            now=now,
            prior_claims=b.claims,
            snapshot=snapshot.content,
            peer_assessments=(
                PeerAssessment(
                    slot=ReviewerSlot.B,
                    stage=ReviewStage.INDEPENDENT,
                    round=1,
                    assessment=b,
                ),
            ),
        )
        cross_b = self._invoke(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.B,
            stage=ReviewStage.CROSS_REVIEW,
            round_number=2,
            assignment=revision.slots[ReviewerSlot.B],
            now=now,
            prior_claims=a.claims,
            snapshot=snapshot.content,
            peer_assessments=(
                PeerAssessment(
                    slot=ReviewerSlot.A,
                    stage=ReviewStage.INDEPENDENT,
                    round=1,
                    assessment=a,
                ),
            ),
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
        self._invoke(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.C,
            stage=ReviewStage.JUDGING,
            round_number=2,
            assignment=revision.slots[ReviewerSlot.C],
            now=now,
            prior_claims=c.claims + cross_a.claims + cross_b.claims,
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
        prior_claims: tuple[str, ...] = (),
        peer_assessments: tuple[PeerAssessment, ...] = (),
    ) -> Assessment:
        provider = assignment.provider or "fixture"
        model = assignment.model or "deterministic"
        invocation = self._repository.record_invocation(
            session_id=session_id,
            slot=slot,
            reviewer_type=assignment.reviewer_type,
            stage=stage,
            round_number=round_number,
            snapshot_hash=snapshot_hash,
            prompt_version=assignment.prompt_version,
            schema_version=assignment.schema_version,
            provider=provider,
            model=model,
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
            role_version=assignment.role_version,
            prompt_version=assignment.prompt_version,
            schema_version=assignment.schema_version,
            snapshot=snapshot,
            prior_claims=prior_claims,
            peer_assessments=peer_assessments,
            requested_at=now,
        )
        try:
            assessment = self._runtime.review(call)
            self._task_packs.validate_assessment(snapshot, assessment)
        except Exception as exc:
            self._repository.fail_invocation(
                invocation_id=invocation.invocation_id,
                error=str(exc),
                completed_at=now,
            )
            failure = {
                ReviewerSlot.A: ReviewState.REVIEWER_A_FAILED,
                ReviewerSlot.B: ReviewState.REVIEWER_B_FAILED,
                ReviewerSlot.C: ReviewState.REVIEWER_C_FAILED,
            }[slot]
            self._transition(session_id, failure)
            raise
        self._repository.complete_invocation(
            invocation_id=invocation.invocation_id,
            assessment_payload=assessment.model_dump(mode="json"),
            completed_at=now,
        )
        return assessment

    def _finish(
        self,
        session_id: str,
        path: FixturePath,
        snapshot: RequestSnapshotRecord,
        *,
        final_assessment: Assessment | None = None,
        comparison: ComparisonResult | None = None,
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
            comparison=comparison,
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

    def _transition(self, session_id: str, target: ReviewState) -> None:
        self._repository.transition_session(session_id, target)

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

    @staticmethod
    def _should_invoke_b(
        *,
        session_id: str,
        snapshot: dict[str, Any],
        assessment: Assessment,
        revision: ReviewPlanRevision,
    ) -> tuple[bool, tuple[str, ...]]:
        kind = TriggerKind(snapshot["review_trigger"]["kind"])
        triggers: list[str] = []
        if kind == TriggerKind.SCHEDULED_B:
            triggers.append("scheduled_b")
        if kind == TriggerKind.FAILED_GOAL and revision.panel_expansion.invoke_b_on_failed_goal:
            triggers.append("failed_goal")
        if assessment.material and revision.panel_expansion.invoke_b_on_a_material:
            triggers.append("material_a")
        sample_rate = revision.panel_expansion.nonmaterial_audit_sample_rate
        if not assessment.material and sample_rate > 0:
            sample = int(hashlib.sha256(session_id.encode()).hexdigest()[:16], 16) / (2**64)
            if sample < sample_rate:
                triggers.append("audit_sample")
        return bool(triggers), ordered_unique(triggers)

    def _record_comparison(
        self,
        session_id: str,
        comparison: ComparisonResult,
        *,
        stage: ReviewStage,
        round_number: int,
    ) -> None:
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
        )
