from dataclasses import dataclass
from datetime import datetime

from conclave.domain.enums import ReviewState
from conclave.fixtures import build_request_for_occurrence
from conclave.intake import ReviewIntakeService
from conclave.ledger.repository import LedgerRepository
from conclave.orchestration.service import FixturePath, ReviewOrchestrator


@dataclass(frozen=True, slots=True)
class WorkerResult:
    work_item_id: str
    occurrence_id: str
    session_id: str
    state: ReviewState


class FixtureWorker:
    def __init__(
        self,
        repository: LedgerRepository,
        intake: ReviewIntakeService,
        orchestrator: ReviewOrchestrator,
    ) -> None:
        self._repository = repository
        self._intake = intake
        self._orchestrator = orchestrator

    def run_once(
        self,
        *,
        worker_id: str,
        now: datetime,
        path: FixturePath = FixturePath.A_ONLY,
        lease_seconds: int = 60,
    ) -> WorkerResult | None:
        work_item = self._repository.claim_next_work_item(
            worker_id=worker_id,
            now=now,
            lease_seconds=lease_seconds,
        )
        if work_item is None:
            return None

        try:
            occurrence = self._repository.get_occurrence(work_item.occurrence_id)
            if occurrence is None:
                raise LookupError(
                    f"work item references missing occurrence {work_item.occurrence_id!r}"
                )
            document = build_request_for_occurrence(occurrence)
            intake_result = self._intake.accept(document)
            state = self._orchestrator.run_fixture_path(
                intake_result.session_id,
                path,
                now=now,
            )
            self._repository.complete_work_item(
                work_item_id=work_item.work_item_id,
                worker_id=worker_id,
                now=now,
            )
            return WorkerResult(
                work_item_id=work_item.work_item_id,
                occurrence_id=work_item.occurrence_id,
                session_id=intake_result.session_id,
                state=state,
            )
        except Exception as exc:
            self._repository.fail_work_item(
                work_item_id=work_item.work_item_id,
                worker_id=worker_id,
                now=now,
                error=str(exc),
            )
            raise
