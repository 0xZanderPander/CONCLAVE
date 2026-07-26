from dataclasses import dataclass

from conclave.contracts.validation import validate_review_result
from conclave.domain.enums import ReviewState
from conclave.ledger.repository import LedgerRepository, canonical_hash
from conclave.orchestration.state_machine import InvalidTransitionError, validate_transition


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

        return AuditVerification(
            session_id=session_id,
            path=result.path,
            final_state=reconstructed,
            event_count=len(events),
            invocation_count=len(invocations),
            result_hash=result.result_hash,
        )
