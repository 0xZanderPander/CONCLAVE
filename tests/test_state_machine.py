import json

import pytest

from conclave.domain.enums import ReviewState
from conclave.orchestration.state_machine import (
    InvalidTransitionError,
    ReviewWorkflow,
)
from conclave.paths import design_fixtures_root


def test_every_documented_fake_trace_is_valid() -> None:
    with (design_fixtures_root() / "fake-state-traces.json").open(encoding="utf-8") as source:
        fixture = json.load(source)

    for trace in fixture["traces"]:
        workflow = ReviewWorkflow()
        final_state = workflow.replay(trace["states"])

        assert final_state == ReviewState(trace["states"][-1]), trace["id"]
        assert len(workflow.changes) == len(trace["states"]) - 1


def test_invalid_stage_skip_is_rejected() -> None:
    workflow = ReviewWorkflow()

    with pytest.raises(InvalidTransitionError):
        workflow.transition(ReviewState.REVIEWER_A)


def test_completed_trace_is_terminal() -> None:
    workflow = ReviewWorkflow()
    workflow.replay(
        [
            "requested",
            "validated",
            "snapshotted",
            "reviewer_a",
            "baseline_recorded",
            "reviewer_adjudication",
            "auto_resolved",
            "result_returned",
            "feedback_pending",
            "evaluated",
        ]
    )

    with pytest.raises(InvalidTransitionError):
        workflow.transition(ReviewState.REQUESTED)


def test_cross_review_failure_is_a_legal_terminal_transition() -> None:
    workflow = ReviewWorkflow()
    workflow.replay(
        [
            "requested",
            "validated",
            "snapshotted",
            "reviewer_a",
            "baseline_recorded",
            "reviewer_b",
            "comparing",
            "cross_review",
            "cross_review_failed",
        ]
    )

    with pytest.raises(InvalidTransitionError):
        workflow.transition(ReviewState.REVIEWER_C_INDEPENDENT)
