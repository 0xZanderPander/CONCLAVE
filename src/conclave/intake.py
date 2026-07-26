from dataclasses import dataclass
from typing import Any

from conclave.contracts.validation import validate_review_request
from conclave.domain.enums import ReviewState
from conclave.domain.models import RequestIdentity, ReviewTrigger
from conclave.ledger.repository import LedgerRepository
from conclave.task_packs.registry import (
    TaskPackRegistry,
    default_task_pack_registry,
)


@dataclass(frozen=True, slots=True)
class IntakeResult:
    session_id: str
    snapshot_hash: str
    state: ReviewState
    optimization_eligible: bool
    material: bool
    eligibility_reasons: tuple[str, ...]


class ReviewIntakeService:
    def __init__(
        self,
        repository: LedgerRepository,
        task_packs: TaskPackRegistry | None = None,
    ) -> None:
        self._repository = repository
        self._task_packs = task_packs or default_task_pack_registry()

    def accept(self, document: dict[str, Any]) -> IntakeResult:
        validate_review_request(document)
        eligibility = self._task_packs.validate_request(document)
        trigger = ReviewTrigger.model_validate(document["review_trigger"])
        identity = RequestIdentity(
            caller_id=document["caller"]["caller_id"],
            idempotency_key=document["idempotency_key"],
            evidence_version=document["evidence_version"],
            plan_id=document["review_plan_ref"],
            plan_revision=document["review_plan_revision"],
            trigger=trigger,
        )

        available = {
            (revision.plan_id, revision.revision)
            for revision in self._repository.list_plan_revisions()
        }
        if (identity.plan_id, identity.plan_revision) not in available:
            raise LookupError(
                f"unknown review plan revision {identity.plan_id!r} r{identity.plan_revision}"
            )

        self._repository.add_occurrence(
            occurrence_id=trigger.occurrence_id,
            plan_id=identity.plan_id,
            plan_revision=identity.plan_revision,
            due_at=trigger.due_at,
            trigger_kind=trigger.kind.value,
        )
        session = self._repository.create_session(identity)
        state = ReviewState(session.current_state)
        if state == ReviewState.REQUESTED:
            session = self._repository.transition_session(
                session.session_id,
                ReviewState.VALIDATED,
            )
            state = ReviewState(session.current_state)

        snapshot = self._repository.store_snapshot(
            session_id=session.session_id,
            content=document,
        )
        self._repository.record_request_validation(
            session_id=session.session_id,
            review_eligible=eligibility.review_eligible,
            optimization_eligible=eligibility.optimization_eligible,
            reasons=eligibility.reasons,
            material=eligibility.materiality.material,
            sufficient_volume=eligibility.materiality.sufficient_volume,
            cpa_deviation=eligibility.materiality.cpa_deviation,
            evidence_age_hours=eligibility.evidence_age_hours,
        )
        if state == ReviewState.VALIDATED:
            session = self._repository.transition_session(
                session.session_id,
                ReviewState.SNAPSHOTTED,
            )
            state = ReviewState(session.current_state)
        if state == ReviewState.SNAPSHOTTED and not eligibility.review_eligible:
            session = self._repository.transition_session(
                session.session_id,
                ReviewState.STALE_OR_INELIGIBLE_EVIDENCE,
            )
            state = ReviewState(session.current_state)

        return IntakeResult(
            session_id=session.session_id,
            snapshot_hash=snapshot.content_hash,
            state=state,
            optimization_eligible=eligibility.optimization_eligible,
            material=eligibility.materiality.material,
            eligibility_reasons=eligibility.reasons,
        )
