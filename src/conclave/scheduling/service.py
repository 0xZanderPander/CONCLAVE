from dataclasses import dataclass
from datetime import datetime

from conclave.domain.enums import ReviewerSlot
from conclave.ledger.repository import LedgerRepository
from conclave.plans.models import ReviewPlan, ReviewPlanRevision
from conclave.plans.scheduling import (
    NoEffectivePlanRevisionError,
    effective_revision,
    scheduled_trigger,
    slots_due,
)


@dataclass(frozen=True, slots=True)
class ScheduledWork:
    plan_id: str
    plan_revision: int
    occurrence_id: str
    work_item_id: str
    due_at: datetime
    slots_due: frozenset[ReviewerSlot]


class SchedulerService:
    def __init__(self, repository: LedgerRepository) -> None:
        self._repository = repository

    def tick(self, at: datetime) -> tuple[ScheduledWork, ...]:
        grouped: dict[tuple[str, str], list[ReviewPlanRevision]] = {}
        for revision in self._repository.list_plan_revisions():
            grouped.setdefault(
                (revision.plan_id, revision.deployment_id),
                [],
            ).append(revision)

        scheduled: list[ScheduledWork] = []
        for (plan_id, deployment_id), revisions in grouped.items():
            plan = ReviewPlan(
                plan_id=plan_id,
                deployment_id=deployment_id,
                revisions=tuple(revisions),
            )
            try:
                revision = effective_revision(plan, at)
            except NoEffectivePlanRevisionError:
                continue
            due = slots_due(revision, at)
            if not due:
                continue

            trigger_slot = ReviewerSlot.B if ReviewerSlot.B in due else ReviewerSlot.A
            trigger = scheduled_trigger(revision, due_at=at, slot=trigger_slot)
            occurrence = self._repository.add_occurrence(
                occurrence_id=trigger.occurrence_id,
                plan_id=revision.plan_id,
                plan_revision=revision.revision,
                due_at=trigger.due_at,
                trigger_kind=trigger.kind.value,
            )
            work_item = self._repository.enqueue_occurrence(
                occurrence_id=occurrence.occurrence_id,
                due_at=trigger.due_at,
            )
            scheduled.append(
                ScheduledWork(
                    plan_id=revision.plan_id,
                    plan_revision=revision.revision,
                    occurrence_id=occurrence.occurrence_id,
                    work_item_id=work_item.work_item_id,
                    due_at=trigger.due_at,
                    slots_due=due,
                )
            )
        return tuple(scheduled)
