from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError

from conclave.contracts.validation import ContractValidationError
from conclave.domain.enums import ReviewState
from conclave.fixtures import build_request_for_occurrence
from conclave.intake import ReviewIntakeService
from conclave.ledger.repository import LedgerConflictError, LedgerRepository
from conclave.orchestration.service import (
    FixturePath,
    OrchestrationStateError,
    ReviewOrchestrator,
)
from conclave.reviewers.runtime import (
    ReviewerProviderExhaustedError,
    UnknownReviewerProviderError,
)


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
        path: FixturePath | None = None,
        lease_seconds: int = 300,
        retry_delay_seconds: int = 30,
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
            if intake_result.state == ReviewState.STALE_OR_INELIGIBLE_EVIDENCE:
                state = intake_result.state
            elif path is None:
                state = self._orchestrator.run(
                    intake_result.session_id,
                    now=now,
                )
            else:
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
            retryable = not isinstance(
                exc,
                (
                    ContractValidationError,
                    LedgerConflictError,
                    OrchestrationStateError,
                    ReviewerProviderExhaustedError,
                    UnknownReviewerProviderError,
                    ValidationError,
                ),
            )
            self._repository.fail_work_item(
                work_item_id=work_item.work_item_id,
                worker_id=worker_id,
                now=now,
                error=str(exc),
                retryable=retryable,
                retry_delay_seconds=retry_delay_seconds,
            )
            raise
