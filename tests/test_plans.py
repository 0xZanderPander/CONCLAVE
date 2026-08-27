import json
from datetime import datetime

import pytest

from conclave.domain.enums import ReviewerSlot, ReviewStage
from conclave.paths import design_fixtures_root
from conclave.plans.models import ProviderPolicy, ReviewPlan, ReviewPlanRevision
from conclave.plans.scheduling import effective_revision, is_due, next_due, slots_due


def _load_plan() -> ReviewPlan:
    with (design_fixtures_root() / "review-plan-revision.json").open(encoding="utf-8") as source:
        fixture = json.load(source)

    revisions = []
    for item in fixture["revisions"]:
        revisions.append(
            ReviewPlanRevision.model_validate(
                {
                    "plan_id": fixture["plan_id"],
                    "deployment_id": fixture["deployment_id"],
                    **item,
                }
            )
        )
    return ReviewPlan(
        plan_id=fixture["plan_id"],
        deployment_id=fixture["deployment_id"],
        revisions=tuple(revisions),
    )


def test_future_revision_does_not_change_earlier_sessions() -> None:
    plan = _load_plan()

    before_change = effective_revision(plan, datetime.fromisoformat("2026-07-17T23:59:00+00:00"))
    after_change = effective_revision(plan, datetime.fromisoformat("2026-07-18T00:00:00+00:00"))

    assert before_change.revision == 3
    assert after_change.revision == 4


@pytest.mark.parametrize(
    ("at", "expected"),
    [
        ("2026-07-19T08:00:00+00:00", {ReviewerSlot.A, ReviewerSlot.B}),
        ("2026-07-24T08:00:00+00:00", {ReviewerSlot.A}),
        ("2026-07-24T16:00:00+00:00", {ReviewerSlot.A, ReviewerSlot.B}),
    ],
)
def test_independent_a_b_cadences(at: str, expected: set[ReviewerSlot]) -> None:
    revision = _load_plan().revisions[-1]
    assert slots_due(revision, datetime.fromisoformat(at)) == expected


def test_event_only_c_is_never_due() -> None:
    revision = _load_plan().revisions[-1]
    c_schedule = revision.slots[ReviewerSlot.C]

    assert not is_due(c_schedule, datetime.fromisoformat("2026-07-24T16:00:00+00:00"))
    assert next_due(c_schedule, datetime.fromisoformat("2026-07-24T16:00:00+00:00")) is None


def test_triggered_b_does_not_move_next_scheduled_audit() -> None:
    revision = _load_plan().revisions[-1]
    b_schedule = revision.slots[ReviewerSlot.B]
    off_cadence_trigger = datetime.fromisoformat("2026-07-24T12:00:00+00:00")

    assert next_due(b_schedule, off_cadence_trigger) == datetime.fromisoformat(
        "2026-07-24T16:00:00+00:00"
    )


def test_provider_limits_can_be_tuned_by_review_stage() -> None:
    schedule = _load_plan().revisions[-1].slots[ReviewerSlot.C].model_copy(
        update={
            "judging_provider_policy": ProviderPolicy(
                max_input_characters=60_000,
                max_cost_usd=0.25,
            )
        }
    )

    assert (
        schedule.provider_policy_for_stage(ReviewStage.INDEPENDENT)
        == schedule.provider_policy
    )
    assert (
        schedule.provider_policy_for_stage(ReviewStage.JUDGING).max_input_characters
        == 60_000
    )
