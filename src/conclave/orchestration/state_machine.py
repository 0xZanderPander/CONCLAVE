from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from conclave.domain.enums import ReviewState


class InvalidTransitionError(ValueError):
    pass


_NORMAL_TRANSITIONS: dict[ReviewState, frozenset[ReviewState]] = {
    ReviewState.REQUESTED: frozenset({ReviewState.VALIDATED}),
    ReviewState.VALIDATED: frozenset({ReviewState.SNAPSHOTTED}),
    ReviewState.SNAPSHOTTED: frozenset({ReviewState.REVIEWER_A, ReviewState.AWAITING_EVIDENCE}),
    ReviewState.REVIEWER_A: frozenset({ReviewState.BASELINE_RECORDED}),
    ReviewState.BASELINE_RECORDED: frozenset(
        {ReviewState.REVIEWER_B, ReviewState.REVIEWER_ADJUDICATION}
    ),
    ReviewState.REVIEWER_B: frozenset({ReviewState.COMPARING}),
    ReviewState.COMPARING: frozenset({ReviewState.CROSS_REVIEW, ReviewState.REVIEWER_ADJUDICATION}),
    ReviewState.CROSS_REVIEW: frozenset(
        {ReviewState.REVIEWER_C_INDEPENDENT, ReviewState.REVIEWER_ADJUDICATION}
    ),
    ReviewState.REVIEWER_C_INDEPENDENT: frozenset({ReviewState.REVIEWER_C_JUDGING}),
    ReviewState.REVIEWER_C_JUDGING: frozenset({ReviewState.REVIEWER_ADJUDICATION}),
    ReviewState.REVIEWER_ADJUDICATION: frozenset(
        {ReviewState.AUTO_RESOLVED, ReviewState.CALLER_DECISION_REQUIRED}
    ),
    ReviewState.AUTO_RESOLVED: frozenset({ReviewState.RESULT_RETURNED}),
    ReviewState.CALLER_DECISION_REQUIRED: frozenset({ReviewState.RESULT_RETURNED}),
    ReviewState.RESULT_RETURNED: frozenset({ReviewState.FEEDBACK_PENDING}),
    ReviewState.FEEDBACK_PENDING: frozenset({ReviewState.EVALUATED}),
}

_FAILURE_TRANSITIONS: dict[ReviewState, frozenset[ReviewState]] = {
    ReviewState.REQUESTED: frozenset({ReviewState.INVALID_REQUEST}),
    ReviewState.VALIDATED: frozenset({ReviewState.INVALID_REQUEST}),
    ReviewState.SNAPSHOTTED: frozenset({ReviewState.STALE_OR_INELIGIBLE_EVIDENCE}),
    ReviewState.REVIEWER_A: frozenset({ReviewState.REVIEWER_A_FAILED}),
    ReviewState.REVIEWER_B: frozenset({ReviewState.REVIEWER_B_FAILED}),
    ReviewState.CROSS_REVIEW: frozenset({ReviewState.CROSS_REVIEW_FAILED}),
    ReviewState.REVIEWER_C_INDEPENDENT: frozenset({ReviewState.REVIEWER_C_FAILED}),
    ReviewState.REVIEWER_C_JUDGING: frozenset({ReviewState.REVIEWER_C_FAILED}),
    ReviewState.AUTO_RESOLVED: frozenset({ReviewState.RESULT_DELIVERY_FAILED}),
    ReviewState.CALLER_DECISION_REQUIRED: frozenset({ReviewState.RESULT_DELIVERY_FAILED}),
}

_TERMINAL_STATES = frozenset(
    {
        ReviewState.EVALUATED,
        ReviewState.INVALID_REQUEST,
        ReviewState.STALE_OR_INELIGIBLE_EVIDENCE,
        ReviewState.REVIEWER_A_FAILED,
        ReviewState.REVIEWER_B_FAILED,
        ReviewState.CROSS_REVIEW_FAILED,
        ReviewState.REVIEWER_C_FAILED,
        ReviewState.AWAITING_EVIDENCE,
        ReviewState.RESULT_DELIVERY_FAILED,
        ReviewState.CANCELLED,
    }
)


def allowed_targets(state: ReviewState) -> frozenset[ReviewState]:
    if state in _TERMINAL_STATES:
        return frozenset()
    targets = set(_NORMAL_TRANSITIONS.get(state, frozenset()))
    targets.update(_FAILURE_TRANSITIONS.get(state, frozenset()))
    targets.add(ReviewState.CANCELLED)
    return frozenset(targets)


def validate_transition(source: ReviewState, target: ReviewState) -> None:
    if target not in allowed_targets(source):
        raise InvalidTransitionError(f"transition {source.value} -> {target.value} is not allowed")


def validate_recovery_transition(source: ReviewState, target: ReviewState) -> None:
    if (
        source != ReviewState.CROSS_REVIEW_FAILED
        or target != ReviewState.CROSS_REVIEW
    ):
        raise InvalidTransitionError(
            f"recovery transition {source.value} -> {target.value} is not allowed"
        )


@dataclass(frozen=True, slots=True)
class StateChange:
    source: ReviewState
    target: ReviewState
    occurred_at: datetime


@dataclass(slots=True)
class ReviewWorkflow:
    state: ReviewState = ReviewState.REQUESTED
    changes: list[StateChange] = field(default_factory=list)

    def transition(self, target: ReviewState, *, at: datetime | None = None) -> StateChange:
        validate_transition(self.state, target)
        change = StateChange(
            source=self.state,
            target=target,
            occurred_at=at or datetime.now(UTC),
        )
        self.changes.append(change)
        self.state = target
        return change

    def replay(self, states: Iterable[ReviewState | str]) -> ReviewState:
        sequence = [ReviewState(state) for state in states]
        if not sequence:
            raise ValueError("a state trace cannot be empty")
        if sequence[0] != self.state:
            raise InvalidTransitionError(
                f"trace starts at {sequence[0].value}; workflow is at {self.state.value}"
            )
        for state in sequence[1:]:
            self.transition(state)
        return self.state
