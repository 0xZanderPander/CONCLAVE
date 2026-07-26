from dataclasses import dataclass
from typing import Any

from conclave.contracts.validation import validate_review_request
from conclave.domain.enums import ReviewState
from conclave.domain.models import RequestIdentity, ReviewTrigger
from conclave.ledger.repository import LedgerRepository


@dataclass(frozen=True, slots=True)
class IntakeResult:
    session_id: str
    snapshot_hash: str
    state: ReviewState


class ReviewIntakeService:
    def __init__(self, repository: LedgerRepository) -> None:
        self._repository = repository

    def accept(self, document: dict[str, Any]) -> IntakeResult:
        validate_review_request(document)
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
        if state == ReviewState.VALIDATED:
            session = self._repository.transition_session(
                session.session_id,
                ReviewState.SNAPSHOTTED,
            )
            state = ReviewState(session.current_state)

        return IntakeResult(
            session_id=session.session_id,
            snapshot_hash=snapshot.content_hash,
            state=state,
        )
