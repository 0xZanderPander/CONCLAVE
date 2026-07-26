from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, text

from conclave.config import Settings
from conclave.contracts.validation import ContractValidationError
from conclave.database import create_database_engine, create_session_factory
from conclave.fixtures import load_design_plan_revisions
from conclave.intake import ReviewIntakeService
from conclave.ledger.repository import LedgerConflictError, LedgerRepository, create_schema
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.development import DevelopmentReviewerRuntime
from conclave.scheduling.service import SchedulerService
from conclave.scheduling.worker import FixtureWorker


class RunFixtureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: FixturePath


class SchedulerTickRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    at: datetime


def create_app(
    *,
    settings: Settings | None = None,
    engine: Engine | None = None,
    initialize_schema: bool = False,
    seed_design_fixtures: bool = False,
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
    scheduler = SchedulerService(repository)
    orchestrator = ReviewOrchestrator(repository, DevelopmentReviewerRuntime())
    worker = FixtureWorker(repository, intake, orchestrator)

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
    def create_review(document: dict[str, Any]) -> dict[str, Any]:
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
            "state": result.state.value,
        }

    @app.get("/reviews/{session_id}")
    def get_review(session_id: str) -> dict[str, Any]:
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
    def run_review(session_id: str, request: RunFixtureRequest) -> dict[str, str]:
        try:
            state = orchestrator.run_fixture_path(session_id, request.path)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"review_session_id": session_id, "state": state.value}

    @app.post("/scheduler/tick")
    def scheduler_tick(request: SchedulerTickRequest) -> dict[str, Any]:
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
        worker_id: str = "local-worker",
        path: FixturePath = FixturePath.A_ONLY,
    ) -> dict[str, Any]:
        result = worker.run_once(
            worker_id=worker_id,
            now=datetime.now(UTC),
            path=path,
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

    return app


app = create_app()
