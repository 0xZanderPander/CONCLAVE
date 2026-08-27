import hashlib
from datetime import datetime, timedelta

from conclave.domain.enums import ReviewerSlot, TriggerKind
from conclave.domain.models import ReviewTrigger
from conclave.plans.models import ReviewPlan, ReviewPlanRevision, SlotSchedule


class NoEffectivePlanRevisionError(LookupError):
    pass


def effective_revision(plan: ReviewPlan, at: datetime) -> ReviewPlanRevision:
    eligible = [revision for revision in plan.revisions if revision.effective_at <= at]
    if not eligible:
        raise NoEffectivePlanRevisionError(
            f"no revision of {plan.plan_id!r} is effective at {at.isoformat()}"
        )
    return max(eligible, key=lambda revision: (revision.effective_at, revision.revision))


def is_due(schedule: SlotSchedule, at: datetime) -> bool:
    if schedule.cadence == "event_only" or schedule.anchor_at is None:
        return False
    if at < schedule.anchor_at:
        return False
    return (at - schedule.anchor_at) % schedule.cadence == timedelta(0)


def next_due(schedule: SlotSchedule, after: datetime) -> datetime | None:
    if schedule.cadence == "event_only" or schedule.anchor_at is None:
        return None
    if after < schedule.anchor_at:
        return schedule.anchor_at
    elapsed = after - schedule.anchor_at
    completed = elapsed // schedule.cadence
    candidate = schedule.anchor_at + (completed * schedule.cadence)
    if candidate <= after:
        candidate += schedule.cadence
    return candidate


def slots_due(revision: ReviewPlanRevision, at: datetime) -> frozenset[ReviewerSlot]:
    if revision.paused or at < revision.effective_at:
        return frozenset()
    return frozenset(slot for slot, schedule in revision.slots.items() if is_due(schedule, at))


def occurrence_id(
    *,
    plan_id: str,
    revision: int,
    due_at: datetime,
    kind: TriggerKind,
) -> str:
    canonical = f"{plan_id}|{revision}|{kind.value}|{due_at.isoformat()}"
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:20]
    return f"occ_{digest}"


def scheduled_trigger(
    revision: ReviewPlanRevision,
    *,
    due_at: datetime,
    slot: ReviewerSlot,
) -> ReviewTrigger:
    if slot not in {ReviewerSlot.A, ReviewerSlot.B}:
        raise ValueError("only A and B have scheduled triggers")
    if not is_due(revision.slots[slot], due_at):
        raise ValueError(f"slot {slot} is not due at {due_at.isoformat()}")
    kind = TriggerKind.SCHEDULED_A if slot == ReviewerSlot.A else TriggerKind.SCHEDULED_B
    return ReviewTrigger(
        occurrence_id=occurrence_id(
            plan_id=revision.plan_id,
            revision=revision.revision,
            due_at=due_at,
            kind=kind,
        ),
        kind=kind,
        due_at=due_at,
    )
