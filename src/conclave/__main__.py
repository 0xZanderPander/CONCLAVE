import argparse
import json
import logging
import os
import signal
import socket
from datetime import UTC, datetime
from threading import Event

from conclave.auditing.verification import AuditVerifier
from conclave.config import Settings
from conclave.contracts.validation import validate_contract_package
from conclave.database import create_database_engine, create_session_factory
from conclave.fixtures import load_design_plan_revisions
from conclave.intake import ReviewIntakeService
from conclave.ledger.repository import LedgerRepository
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.factory import build_reviewer_runtime
from conclave.runtime.processes import SchedulerProcess, WorkerProcess
from conclave.scheduling.service import SchedulerService
from conclave.scheduling.worker import FixtureWorker


def _default_process_id(kind: str) -> str:
    return f"{kind}-{socket.gethostname()}-{os.getpid()}"


def _stop_event() -> Event:
    event = Event()

    def stop(_signum: int, _frame: object) -> None:
        event.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    return event


def _runtime(
    settings: Settings,
) -> tuple[
    LedgerRepository,
    SchedulerService,
    FixtureWorker,
]:
    engine = create_database_engine(settings)
    repository = LedgerRepository(create_session_factory(engine))
    scheduler = SchedulerService(
        repository,
        max_attempts=settings.worker_max_attempts,
    )
    worker = FixtureWorker(
        repository,
        ReviewIntakeService(repository),
        ReviewOrchestrator(repository, build_reviewer_runtime(settings)),
    )
    return repository, scheduler, worker


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Conclave operational commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "validate-fixtures",
        help="Validate the local contracts and fixtures.",
    )
    subparsers.add_parser(
        "seed-fixtures",
        help="Store the versioned development review plans.",
    )

    scheduler = subparsers.add_parser(
        "scheduler",
        help="Run the persistent schedule-expansion process.",
    )
    scheduler.add_argument("--once", action="store_true")
    scheduler.add_argument("--process-id")

    worker = subparsers.add_parser(
        "worker",
        help="Run the persistent fixture worker process.",
    )
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--process-id")
    worker.add_argument(
        "--path",
        choices=["auto", *(path.value for path in FixturePath)],
        default="auto",
        help="Use automatic routing by default; explicit paths are a test harness.",
    )

    subparsers.add_parser("queue-status", help="Show work-queue and process health.")

    retry = subparsers.add_parser("retry-work", help="Retry one dead-letter work item.")
    retry.add_argument("work_item_id")
    retry.add_argument("--additional-attempts", type=int, default=1)

    cancel = subparsers.add_parser("cancel-work", help="Cancel one unfinished work item.")
    cancel.add_argument("work_item_id")
    cancel.add_argument("--reason", required=True)

    audit = subparsers.add_parser("verify-audit", help="Verify one completed review ledger.")
    audit.add_argument("session_id")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "validate-fixtures":
        report = validate_contract_package()
        print(
            "Validated "
            f"{report.request_count} requests, "
            f"{report.result_count} results, "
            f"{report.feedback_count} feedback records, and "
            f"{report.comparator_case_count} comparator cases."
        )
        return

    settings = Settings.from_environment()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    repository, scheduler, worker = _runtime(settings)

    if args.command == "seed-fixtures":
        revisions = load_design_plan_revisions()
        for revision in revisions:
            repository.add_plan_revision(revision)
        print(json.dumps({"seeded_plan_revisions": len(revisions)}))
    elif args.command == "scheduler":
        process = SchedulerProcess(
            repository,
            scheduler,
            process_id=args.process_id or _default_process_id("scheduler"),
            interval_seconds=settings.scheduler_interval_seconds,
        )
        process.run(once=args.once, stop_event=_stop_event())
    elif args.command == "worker":
        process = WorkerProcess(
            repository,
            worker,
            process_id=args.process_id or _default_process_id("worker"),
            idle_seconds=settings.worker_idle_seconds,
            lease_seconds=settings.worker_lease_seconds,
            retry_delay_seconds=settings.worker_retry_delay_seconds,
            path=None if args.path == "auto" else FixturePath(args.path),
        )
        process.run(once=args.once, stop_event=_stop_event())
    elif args.command == "queue-status":
        now = datetime.now(UTC)
        metrics = repository.queue_metrics(now)
        stale_processes = repository.stale_processes(
            now=now,
            stale_after_seconds=settings.process_stale_after_seconds,
        )
        print(
            json.dumps(
                {
                    "at": now.isoformat(),
                    "queue": {
                        "counts": metrics.counts,
                        "oldest_claimable_at": (
                            metrics.oldest_claimable_at.isoformat()
                            if metrics.oldest_claimable_at
                            else None
                        ),
                        "expired_leases": metrics.expired_leases,
                    },
                    "processes": [
                        {
                            "process_id": process.process_id,
                            "process_type": process.process_type,
                            "status": process.status,
                            "heartbeat_at": process.heartbeat_at.isoformat(),
                            "metadata": process.process_metadata,
                        }
                        for process in repository.list_processes()
                    ],
                    "stale_process_ids": [process.process_id for process in stale_processes],
                }
            )
        )
    elif args.command == "retry-work":
        item = repository.retry_dead_letter(
            work_item_id=args.work_item_id,
            now=datetime.now(UTC),
            additional_attempts=args.additional_attempts,
        )
        print(json.dumps({"work_item_id": item.work_item_id, "status": item.status}))
    elif args.command == "cancel-work":
        item = repository.cancel_work_item(
            work_item_id=args.work_item_id,
            now=datetime.now(UTC),
            reason=args.reason,
        )
        print(json.dumps({"work_item_id": item.work_item_id, "status": item.status}))
    elif args.command == "verify-audit":
        verification = AuditVerifier(repository).verify_session(args.session_id)
        print(
            json.dumps(
                {
                    "session_id": verification.session_id,
                    "path": verification.path,
                    "final_state": verification.final_state.value,
                    "event_count": verification.event_count,
                    "invocation_count": verification.invocation_count,
                    "result_hash": verification.result_hash,
                }
            )
        )


if __name__ == "__main__":
    main()
