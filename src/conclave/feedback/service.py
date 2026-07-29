from dataclasses import dataclass
from typing import Any

from conclave.contracts.validation import validate_review_feedback
from conclave.domain.enums import ReviewState
from conclave.ledger.repository import LedgerRepository


@dataclass(frozen=True, slots=True)
class FeedbackAcceptance:
    feedback_id: str
    feedback_hash: str
    session_id: str
    state: ReviewState


class FeedbackIntakeService:
    """Validate and durably link one opaque caller-feedback record."""

    def __init__(self, repository: LedgerRepository) -> None:
        self._repository = repository

    def accept(
        self,
        *,
        session_id: str,
        caller_id: str,
        document: dict[str, Any],
    ) -> FeedbackAcceptance:
        session = self._repository.get_session(session_id)
        if session is None:
            raise LookupError(f"unknown review session {session_id!r}")
        validate_review_feedback(
            document,
            session_id=session_id,
            evidence_version=session.evidence_version,
        )
        feedback = self._repository.record_feedback(
            session_id=session_id,
            caller_id=caller_id,
            document=document,
        )
        updated = self._repository.get_session(session_id)
        if updated is None:
            raise RuntimeError("review session disappeared after feedback intake")
        return FeedbackAcceptance(
            feedback_id=feedback.feedback_id,
            feedback_hash=feedback.feedback_hash,
            session_id=session_id,
            state=ReviewState(updated.current_state),
        )
