from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, text

from conclave.api.auth import (
    CallerAuthenticator,
    CallerPrincipal,
    LocalFixtureAuthenticator,
    StaticBearerAuthenticator,
    scope_dependency,
)
from conclave.auditing.verification import AuditVerificationError, AuditVerifier
from conclave.config import Settings
from conclave.contracts.validation import ContractValidationError
from conclave.database import create_database_engine, create_session_factory
from conclave.fixtures import load_design_plan_revisions
from conclave.intake import ReviewIntakeService
from conclave.ledger.repository import (
    LedgerConflictError,
    LedgerRepository,
    ReviewRecoveryError,
    WorkItemClaimError,
    create_schema,
)
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.factory import build_reviewer_runtime
from conclave.reviewers.runtime import ReviewerRuntime
from conclave.scheduling.service import SchedulerService
from conclave.scheduling.worker import FixtureWorker


class RunFixtureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: FixturePath


class SchedulerTickRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    at: datetime


class RetryWorkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    additional_attempts: int = 1


class CancelWorkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str


class RecoverCrossReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str


def create_app(
    *,
    settings: Settings | None = None,
    engine: Engine | None = None,
    initialize_schema: bool = False,
    seed_design_fixtures: bool = False,
    authenticator: CallerAuthenticator | None = None,
    reviewer_runtime: ReviewerRuntime | None = None,
) -> FastAPI:
    settings = settings or Settings.from_environment()
    engine = engine or create_database_engine(settings)
    if initialize_schema:
        create_schema(engine)

    repository = LedgerRepository(create_session_factory(engine))
    if seed_design_fixtures:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)

    intake = ReviewIntakeService(repository)
    scheduler = SchedulerService(
        repository,
        max_attempts=settings.worker_max_attempts,
    )
    orchestrator = ReviewOrchestrator(
        repository,
        reviewer_runtime or build_reviewer_runtime(settings),
    )
    worker = FixtureWorker(repository, intake, orchestrator)
    auditor = AuditVerifier(repository)
    if authenticator is None:
        authenticator = (
            StaticBearerAuthenticator.from_json(settings.caller_credentials_json)
            if settings.caller_auth_mode == "static_bearer"
            and settings.caller_credentials_json is not None
            else LocalFixtureAuthenticator()
        )
    submit_dependency = scope_dependency(authenticator, "reviews:submit")
    read_dependency = scope_dependency(authenticator, "reviews:read")
    events_dependency = scope_dependency(authenticator, "events:read")
    operations_dependency = scope_dependency(authenticator, "operations:manage")

    app = FastAPI(
        title="Conclave",
        version="0.1.0",
        description="Local fixture API for the independent Conclave review kernel.",
    )
    app.state.engine = engine
    app.state.repository = repository
    app.state.intake = intake
    app.state.scheduler = scheduler
    app.state.orchestrator = orchestrator
    app.state.worker = worker
    app.state.auditor = auditor
    app.state.authenticator = authenticator

    def authorize_session(principal: CallerPrincipal, session_id: str) -> None:
        if principal.caller_id is None:
            return
        record = repository.get_session(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="review session not found")
        if record.caller_id != principal.caller_id:
            raise HTTPException(status_code=403, detail="review session belongs to another caller")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        try:
            with engine.connect() as connection:
                connection.execute(text("select 1"))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc
        return {"status": "ready"}

    @app.post("/reviews", status_code=201)
    def create_review(
        document: dict[str, Any],
        principal: Annotated[CallerPrincipal, Depends(submit_dependency)],
    ) -> dict[str, Any]:
        if (
            principal.caller_id is not None
            and document.get("caller", {}).get("caller_id") != principal.caller_id
        ):
            raise HTTPException(
                status_code=403,
                detail="request caller does not match the authenticated principal",
            )
        try:
            result = intake.accept(document)
        except ContractValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except LedgerConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "review_session_id": result.session_id,
            "snapshot_hash": result.snapshot_hash,
            "task_pack_hash": result.task_pack_hash,
            "state": result.state.value,
            "optimization_eligible": result.optimization_eligible,
            "material": result.material,
            "eligibility_reasons": list(result.eligibility_reasons),
        }

    @app.get("/reviews/{session_id}")
    def get_review(
        session_id: str,
        principal: Annotated[CallerPrincipal, Depends(read_dependency)],
    ) -> dict[str, Any]:
        authorize_session(principal, session_id)
        record = repository.get_session(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="review session not found")
        snapshot = repository.get_snapshot(session_id)
        return {
            "review_session_id": record.session_id,
            "occurrence_id": record.occurrence_id,
            "plan_id": record.plan_id,
            "plan_revision": record.plan_revision,
            "evidence_version": record.evidence_version,
            "state": record.current_state,
            "snapshot_hash": snapshot.content_hash if snapshot else None,
        }

    @app.post("/reviews/{session_id}/run")
    def run_review(
        session_id: str,
        request: RunFixtureRequest,
        principal: Annotated[CallerPrincipal, Depends(submit_dependency)],
    ) -> dict[str, str]:
        authorize_session(principal, session_id)
        try:
            state = orchestrator.run_fixture_path(session_id, request.path)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"review_session_id": session_id, "state": state.value}

    @app.post("/reviews/{session_id}/run-auto")
    def run_review_automatically(
        session_id: str,
        principal: Annotated[CallerPrincipal, Depends(submit_dependency)],
    ) -> dict[str, str]:
        authorize_session(principal, session_id)
        try:
            state = orchestrator.run(session_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"review_session_id": session_id, "state": state.value}

    @app.get("/reviews/{session_id}/result")
    def get_review_result(
        session_id: str,
        principal: Annotated[CallerPrincipal, Depends(read_dependency)],
    ) -> dict[str, Any]:
        authorize_session(principal, session_id)
        result = repository.get_result(session_id)
        if result is None:
            raise HTTPException(status_code=404, detail="review result not found")
        return result.document

    @app.get("/reviews/{session_id}/audit")
    def verify_review_audit(
        session_id: str,
        principal: Annotated[CallerPrincipal, Depends(read_dependency)],
    ) -> dict[str, Any]:
        authorize_session(principal, session_id)
        try:
            verification = auditor.verify_session(session_id)
        except AuditVerificationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "review_session_id": verification.session_id,
            "path": verification.path,
            "final_state": verification.final_state.value,
            "event_count": verification.event_count,
            "invocation_count": verification.invocation_count,
            "result_hash": verification.result_hash,
        }

    @app.get("/review-sessions/{session_id}/events")
    def get_review_events(
        session_id: str,
        principal: Annotated[CallerPrincipal, Depends(events_dependency)],
        after_sequence: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> dict[str, Any]:
        authorize_session(principal, session_id)
        if repository.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="review session not found")
        events = repository.list_events(
            session_id,
            after_sequence=after_sequence,
            limit=limit,
        )
        return {
            "stream_id": session_id,
            "after_sequence": after_sequence,
            "next_sequence": (events[-1].sequence if events else after_sequence),
            "events": [event.model_dump(mode="json", by_alias=True) for event in events],
        }

    @app.post("/scheduler/tick")
    def scheduler_tick(
        request: SchedulerTickRequest,
        _principal: Annotated[CallerPrincipal, Depends(operations_dependency)],
    ) -> dict[str, Any]:
        work = scheduler.tick(request.at)
        return {
            "scheduled": [
                {
                    "plan_id": item.plan_id,
                    "plan_revision": item.plan_revision,
                    "occurrence_id": item.occurrence_id,
                    "work_item_id": item.work_item_id,
                    "due_at": item.due_at,
                    "slots_due": sorted(slot.value for slot in item.slots_due),
                }
                for item in work
            ]
        }

    @app.post("/worker/run-once")
    def worker_run_once(
        _principal: Annotated[CallerPrincipal, Depends(operations_dependency)],
        worker_id: str = "local-worker",
        path: FixturePath | None = None,
    ) -> dict[str, Any]:
        result = worker.run_once(
            worker_id=worker_id,
            now=datetime.now(UTC),
            path=path,
            lease_seconds=settings.worker_lease_seconds,
            retry_delay_seconds=settings.worker_retry_delay_seconds,
        )
        if result is None:
            return {"processed": False}
        return {
            "processed": True,
            "work_item_id": result.work_item_id,
            "occurrence_id": result.occurrence_id,
            "review_session_id": result.session_id,
            "state": result.state.value,
        }

    @app.get("/operations/status")
    def operations_status(
        _principal: Annotated[CallerPrincipal, Depends(operations_dependency)],
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        metrics = repository.queue_metrics(now)
        provider_metrics = repository.provider_metrics()
        stale_processes = repository.stale_processes(
            now=now,
            stale_after_seconds=settings.process_stale_after_seconds,
        )
        return {
            "at": now,
            "queue": {
                "counts": metrics.counts,
                "oldest_claimable_at": metrics.oldest_claimable_at,
                "expired_leases": metrics.expired_leases,
            },
            "provider_attempts": {
                "counts": provider_metrics.counts,
                "total_tokens": provider_metrics.total_tokens,
                "total_cost_usd": provider_metrics.total_cost_usd,
                "average_latency_ms": provider_metrics.average_latency_ms,
                "last_completed_at": provider_metrics.last_completed_at,
            },
            "processes": [
                {
                    "process_id": process.process_id,
                    "process_type": process.process_type,
                    "status": process.status,
                    "heartbeat_at": process.heartbeat_at,
                    "metadata": process.process_metadata,
                }
                for process in repository.list_processes()
            ],
            "stale_process_ids": [process.process_id for process in stale_processes],
        }

    @app.post("/operations/work-items/{work_item_id}/retry")
    def retry_work_item(
        work_item_id: str,
        request: RetryWorkRequest,
        _principal: Annotated[CallerPrincipal, Depends(operations_dependency)],
    ) -> dict[str, Any]:
        try:
            item = repository.retry_dead_letter(
                work_item_id=work_item_id,
                now=datetime.now(UTC),
                additional_attempts=request.additional_attempts,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, WorkItemClaimError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"work_item_id": item.work_item_id, "status": item.status}

    @app.post("/operations/work-items/{work_item_id}/cancel")
    def cancel_work_item(
        work_item_id: str,
        request: CancelWorkRequest,
        _principal: Annotated[CallerPrincipal, Depends(operations_dependency)],
    ) -> dict[str, Any]:
        try:
            item = repository.cancel_work_item(
                work_item_id=work_item_id,
                now=datetime.now(UTC),
                reason=request.reason,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WorkItemClaimError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"work_item_id": item.work_item_id, "status": item.status}

    @app.post("/operations/reviews/{session_id}/recover-cross-review")
    def recover_cross_review(
        session_id: str,
        request: RecoverCrossReviewRequest,
        principal: Annotated[
            CallerPrincipal,
            Depends(operations_dependency),
        ],
    ) -> dict[str, Any]:
        try:
            session = repository.recover_cross_review(
                session_id=session_id,
                operator_id=principal.caller_id or "local-operator",
                reason=request.reason,
                recovered_at=datetime.now(UTC),
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, ReviewRecoveryError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "review_session_id": session.session_id,
            "state": session.current_state,
        }

    return app


app = create_app()
