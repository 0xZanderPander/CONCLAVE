from datetime import UTC, datetime
from enum import StrEnum

from conclave.domain.enums import (
    ReviewerSlot,
    ReviewStage,
    ReviewState,
)
from conclave.ledger.repository import LedgerRepository
from conclave.plans.models import SlotSchedule
from conclave.reviewers.runtime import Assessment, ReviewCall, ReviewerRuntime


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
    ) -> None:
        self._repository = repository
        self._runtime = runtime

    def run_fixture_path(
        self,
        session_id: str,
        path: FixturePath,
        *,
        now: datetime | None = None,
    ) -> ReviewState:
        now = now or datetime.now(UTC)
        session = self._repository.get_session(session_id)
        if session is None:
            raise LookupError(f"unknown review session {session_id!r}")
        current = ReviewState(session.current_state)
        if current == ReviewState.RESULT_RETURNED:
            return current
        if current != ReviewState.SNAPSHOTTED:
            raise OrchestrationStateError(
                f"fixture orchestration requires snapshotted; found {current.value}"
            )

        snapshot = self._repository.get_snapshot(session_id)
        if snapshot is None:
            raise OrchestrationStateError("session has no immutable snapshot")
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
            raise OrchestrationStateError("session plan revision is unavailable")

        self._transition(session_id, ReviewState.REVIEWER_A)
        a = self._invoke(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.A,
            stage=ReviewStage.INDEPENDENT,
            round_number=1,
            assignment=revision.slots[ReviewerSlot.A],
            now=now,
        )
        self._transition(session_id, ReviewState.BASELINE_RECORDED)

        if path == FixturePath.A_ONLY:
            self._transition(session_id, ReviewState.REVIEWER_ADJUDICATION)
            self._transition(session_id, ReviewState.AUTO_RESOLVED)
            self._transition(session_id, ReviewState.RESULT_RETURNED)
            return ReviewState.RESULT_RETURNED

        self._transition(session_id, ReviewState.REVIEWER_B)
        b = self._invoke(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.B,
            stage=ReviewStage.INDEPENDENT,
            round_number=1,
            assignment=revision.slots[ReviewerSlot.B],
            now=now,
        )
        self._transition(session_id, ReviewState.COMPARING)

        if path == FixturePath.AB_AGREEMENT:
            self._transition(session_id, ReviewState.REVIEWER_ADJUDICATION)
            self._transition(session_id, ReviewState.AUTO_RESOLVED)
            self._transition(session_id, ReviewState.RESULT_RETURNED)
            return ReviewState.RESULT_RETURNED

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
        )

        if path == FixturePath.CROSS_REVIEW_RESOLVED:
            self._transition(session_id, ReviewState.REVIEWER_ADJUDICATION)
            self._transition(session_id, ReviewState.CALLER_DECISION_REQUIRED)
            self._transition(session_id, ReviewState.RESULT_RETURNED)
            return ReviewState.RESULT_RETURNED

        self._transition(session_id, ReviewState.REVIEWER_C_INDEPENDENT)
        c = self._invoke(
            session_id=session_id,
            snapshot_hash=snapshot.content_hash,
            slot=ReviewerSlot.C,
            stage=ReviewStage.INDEPENDENT,
            round_number=1,
            assignment=revision.slots[ReviewerSlot.C],
            now=now,
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
        )
        self._transition(session_id, ReviewState.REVIEWER_ADJUDICATION)
        self._transition(session_id, ReviewState.CALLER_DECISION_REQUIRED)
        self._transition(session_id, ReviewState.RESULT_RETURNED)
        return ReviewState.RESULT_RETURNED

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
        prior_claims: tuple[str, ...] = (),
    ) -> Assessment:
        invocation = self._repository.record_invocation(
            session_id=session_id,
            slot=slot,
            reviewer_type=assignment.reviewer_type,
            stage=stage,
            round_number=round_number,
            snapshot_hash=snapshot_hash,
            prompt_version=assignment.prompt_version,
            schema_version=assignment.schema_version,
            provider=assignment.provider or "fixture",
            model=assignment.model or "deterministic",
        )
        call = ReviewCall(
            session_id=session_id,
            snapshot_hash=snapshot_hash,
            slot=slot,
            stage=stage,
            round=round_number,
            prompt_version=assignment.prompt_version,
            schema_version=assignment.schema_version,
            prior_claims=prior_claims,
            requested_at=now,
        )
        try:
            assessment = self._runtime.review(call)
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

    def _transition(self, session_id: str, target: ReviewState) -> None:
        self._repository.transition_session(session_id, target)
