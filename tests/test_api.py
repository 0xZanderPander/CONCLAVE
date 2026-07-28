import json
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from conclave.api.app import create_app
from conclave.config import Settings
from conclave.fixtures import load_request_fixture
from tests.helpers import create_test_engine


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_local_api_accepts_and_runs_a_fixture_review() -> None:
    engine = create_test_engine()
    app = create_app(
        settings=Settings(database_url="sqlite+pysqlite://"),
        engine=engine,
        seed_design_fixtures=True,
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            assert (await client.get("/health")).json() == {"status": "ok"}
            assert (await client.get("/ready")).json() == {"status": "ready"}

            document = load_request_fixture()
            created = await client.post("/reviews", json=document)
            assert created.status_code == 201
            payload = created.json()
            assert payload["state"] == "snapshotted"
            assert payload["optimization_eligible"]
            assert not payload["material"]
            assert payload["eligibility_reasons"] == []

            repeated = await client.post("/reviews", json=document)
            assert repeated.status_code == 201
            assert repeated.json()["review_session_id"] == payload["review_session_id"]

            retrieved = await client.get(f"/reviews/{payload['review_session_id']}")
            assert retrieved.status_code == 200
            assert retrieved.json()["snapshot_hash"] == payload["snapshot_hash"]

            completed = await client.post(
                f"/reviews/{payload['review_session_id']}/run",
                json={"path": "a_only"},
            )
            assert completed.status_code == 200
            assert completed.json()["state"] == "result_returned"

            result = await client.get(f"/reviews/{payload['review_session_id']}/result")
            audit = await client.get(f"/reviews/{payload['review_session_id']}/audit")
            events = await client.get(
                f"/review-sessions/{payload['review_session_id']}/events",
                params={"after_sequence": 0, "limit": 5},
            )
            operations = await client.get("/operations/status")
            assert result.status_code == 200
            assert result.json()["status"] == "auto_resolved"
            assert audit.status_code == 200
            assert audit.json()["invocation_count"] == 1
            assert events.status_code == 200
            assert len(events.json()["events"]) == 5
            assert events.json()["events"][0]["event_id"].startswith("evt_")
            assert events.json()["events"][0]["sequence"] == 1
            assert events.json()["next_sequence"] == 5
            assert operations.status_code == 200
            assert operations.json()["queue"]["expired_leases"] == 0
            provider_attempts = operations.json()["provider_attempts"]
            assert provider_attempts["counts"] == {"succeeded": 1}
            assert provider_attempts["total_tokens"] == 0
            assert provider_attempts["total_cost_usd"] == 0.0
            assert provider_attempts["average_latency_ms"] >= 0
            assert provider_attempts["last_completed_at"] is not None
            assert operations.json()["stale_process_ids"] == []
    finally:
        engine.dispose()


@pytest.mark.anyio
async def test_local_api_can_run_the_automatic_task_pack_route() -> None:
    engine = create_test_engine()
    app = create_app(
        settings=Settings(database_url="sqlite+pysqlite://"),
        engine=engine,
        seed_design_fixtures=True,
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = await client.post("/reviews", json=load_request_fixture())
            session_id = created.json()["review_session_id"]
            completed = await client.post(f"/reviews/{session_id}/run-auto")
            result = await client.get(f"/reviews/{session_id}/result")

        assert completed.status_code == 200
        assert completed.json()["state"] == "result_returned"
        assert result.status_code == 200
        assert result.json()["disagreement"]["level"] == "none"
        assert len(result.json()["panel_metadata"]["reviewers"]) == 1
    finally:
        engine.dispose()


@pytest.mark.anyio
async def test_operations_api_exposes_controlled_cross_review_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_test_engine()
    app = create_app(
        settings=Settings(database_url="sqlite+pysqlite://"),
        engine=engine,
        seed_design_fixtures=True,
    )
    captured: dict[str, object] = {}

    def recover_cross_review(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            session_id=kwargs["session_id"],
            current_state="cross_review",
        )

    monkeypatch.setattr(
        app.state.repository,
        "recover_cross_review",
        recover_cross_review,
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/operations/reviews/rs_recovery/recover-cross-review",
                json={"reason": "Provider access restored."},
            )

        assert response.status_code == 200
        assert response.json() == {
            "review_session_id": "rs_recovery",
            "state": "cross_review",
        }
        assert captured["operator_id"] == "local-operator"
        assert captured["reason"] == "Provider access restored."
    finally:
        engine.dispose()


@pytest.mark.anyio
async def test_local_api_rejects_an_invalid_contract() -> None:
    engine = create_test_engine()
    app = create_app(
        settings=Settings(database_url="sqlite+pysqlite://"),
        engine=engine,
        seed_design_fixtures=True,
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/reviews", json={"not": "a review request"})
        assert response.status_code == 422
    finally:
        engine.dispose()


@pytest.mark.anyio
async def test_local_scheduler_endpoint_creates_fixture_work() -> None:
    engine = create_test_engine()
    app = create_app(
        settings=Settings(database_url="sqlite+pysqlite://"),
        engine=engine,
        seed_design_fixtures=True,
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/scheduler/tick",
                json={"at": "2026-07-24T16:00:00Z"},
            )
        assert response.status_code == 200
        scheduled = response.json()["scheduled"]
        assert len(scheduled) == 1
        assert scheduled[0]["slots_due"] == ["A", "B"]

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            processed = await client.post(
                "/worker/run-once",
                params={"worker_id": "api-worker", "path": "ab_agreement"},
            )
            empty = await client.post(
                "/worker/run-once",
                params={"worker_id": "api-worker", "path": "ab_agreement"},
            )
        assert processed.status_code == 200
        assert processed.json()["state"] == "result_returned"
        assert empty.json() == {"processed": False}
    finally:
        engine.dispose()


@pytest.mark.anyio
async def test_static_bearer_authenticates_scopes_and_caller_ownership() -> None:
    engine = create_test_engine()
    credentials = json.dumps(
        {
            "fixture-caller": {
                "token": "fixture-secret",
                "scopes": ["reviews:submit", "reviews:read", "events:read"],
            },
            "other-caller": {
                "token": "other-secret",
                "scopes": ["reviews:read"],
            },
        }
    )
    app = create_app(
        settings=Settings(
            environment="test",
            database_url="sqlite+pysqlite://",
            caller_auth_mode="static_bearer",
            caller_credentials_json=credentials,
        ),
        engine=engine,
        seed_design_fixtures=True,
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            document = load_request_fixture()
            document["caller"]["caller_id"] = "fixture-caller"
            unauthenticated = await client.post("/reviews", json=document)
            assert unauthenticated.status_code == 401

            created = await client.post(
                "/reviews",
                json=document,
                headers={"Authorization": "Bearer fixture-secret"},
            )
            assert created.status_code == 201
            session_id = created.json()["review_session_id"]

            forbidden = await client.get(
                f"/reviews/{session_id}",
                headers={"Authorization": "Bearer other-secret"},
            )
            assert forbidden.status_code == 403

            allowed = await client.get(
                f"/reviews/{session_id}",
                headers={"Authorization": "Bearer fixture-secret"},
            )
            assert allowed.status_code == 200

            wrong_scope = await client.post(
                "/scheduler/tick",
                json={"at": "2026-07-24T16:00:00Z"},
                headers={"Authorization": "Bearer fixture-secret"},
            )
            assert wrong_scope.status_code == 403
    finally:
        engine.dispose()
