import logging
from datetime import UTC, datetime
from threading import Event

from conclave.ledger.repository import LedgerRepository
from conclave.orchestration.service import FixturePath
from conclave.scheduling.service import SchedulerService
from conclave.scheduling.worker import FixtureWorker

logger = logging.getLogger(__name__)


class SchedulerProcess:
    def __init__(
        self,
        repository: LedgerRepository,
        scheduler: SchedulerService,
        *,
        process_id: str,
        interval_seconds: int,
    ) -> None:
        self._repository = repository
        self._scheduler = scheduler
        self._process_id = process_id
        self._interval_seconds = interval_seconds

    def run(self, *, once: bool = False, stop_event: Event | None = None) -> None:
        stop_event = stop_event or Event()
        self._repository.register_process(
            process_id=self._process_id,
            process_type="scheduler",
            now=datetime.now(UTC),
            metadata={"interval_seconds": self._interval_seconds},
        )
        try:
            while not stop_event.is_set():
                now = datetime.now(UTC)
                scheduled = self._scheduler.tick(now)
                self._repository.heartbeat_process(
                    process_id=self._process_id,
                    now=datetime.now(UTC),
                    metadata={
                        "interval_seconds": self._interval_seconds,
                        "last_tick_at": now.isoformat(),
                        "scheduled_count": len(scheduled),
                    },
                )
                logger.info(
                    "scheduler tick complete",
                    extra={"scheduled_count": len(scheduled)},
                )
                if once:
                    break
                stop_event.wait(self._interval_seconds)
        finally:
            self._repository.stop_process(
                process_id=self._process_id,
                now=datetime.now(UTC),
            )


class WorkerProcess:
    def __init__(
        self,
        repository: LedgerRepository,
        worker: FixtureWorker,
        *,
        process_id: str,
        idle_seconds: int,
        lease_seconds: int,
        retry_delay_seconds: int,
        path: FixturePath | None,
    ) -> None:
        self._repository = repository
        self._worker = worker
        self._process_id = process_id
        self._idle_seconds = idle_seconds
        self._lease_seconds = lease_seconds
        self._retry_delay_seconds = retry_delay_seconds
        self._path = path

    def run(self, *, once: bool = False, stop_event: Event | None = None) -> None:
        stop_event = stop_event or Event()
        processed_count = 0
        failure_count = 0
        self._repository.register_process(
            process_id=self._process_id,
            process_type="worker",
            now=datetime.now(UTC),
            metadata={"path": self._path.value if self._path else "auto"},
        )
        try:
            while not stop_event.is_set():
                now = datetime.now(UTC)
                try:
                    result = self._worker.run_once(
                        worker_id=self._process_id,
                        now=now,
                        path=self._path,
                        lease_seconds=self._lease_seconds,
                        retry_delay_seconds=self._retry_delay_seconds,
                    )
                except Exception:
                    failure_count += 1
                    logger.exception("worker item failed")
                    result = None
                if result is not None:
                    processed_count += 1
                self._repository.heartbeat_process(
                    process_id=self._process_id,
                    now=datetime.now(UTC),
                    metadata={
                        "path": self._path.value if self._path else "auto",
                        "last_poll_at": now.isoformat(),
                        "processed_count": processed_count,
                        "failure_count": failure_count,
                    },
                )
                if once:
                    break
                if result is None:
                    stop_event.wait(self._idle_seconds)
        finally:
            self._repository.stop_process(
                process_id=self._process_id,
                now=datetime.now(UTC),
            )
