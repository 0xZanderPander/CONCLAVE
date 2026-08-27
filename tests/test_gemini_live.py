import json
import os
from datetime import UTC, datetime

import pytest

from conclave.domain.enums import ReviewerSlot, ReviewState
from conclave.fixtures import load_design_plan_revisions, load_request_fixture
from conclave.intake import ReviewIntakeService
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.gemini import GeminiInteractionsProvider
from conclave.reviewers.prompts import (
    REVIEWER_A_PROMPT_VERSION,
    REVIEWER_A_ROLE_VERSION,
)
from conclave.reviewers.runtime import ProviderRegistryRuntime
from tests.helpers import create_test_engine, create_test_repository

GOOGLE_API_KEY = os.getenv("CONCLAVE_GOOGLE_API_KEY")


@pytest.mark.skipif(
    not GOOGLE_API_KEY,
    reason="CONCLAVE_GOOGLE_API_KEY is required for the live Gemini gate",
)
def test_live_gemini_reviewer_a_produces_one_auditable_assessment() -> None:
    assert GOOGLE_API_KEY is not None
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            if revision.revision == 4:
                slots = dict(revision.slots)
                slots[ReviewerSlot.A] = slots[ReviewerSlot.A].model_copy(
                    update={
                        "provider": "google",
                        "model": "gemini-3.6-flash",
                        "role_version": REVIEWER_A_ROLE_VERSION,
                        "prompt_version": REVIEWER_A_PROMPT_VERSION,
                        "schema_version": "assessment-v2",
                        "provider_policy": slots[
                            ReviewerSlot.A
                        ].provider_policy.model_copy(
                            update={
                                "max_attempts": 1,
                                "max_output_tokens": 4_000,
                                "max_cost_usd": 0.01,
                                "reasoning_effort": "low",
                                "input_cost_per_million_usd": 0.0,
                                "output_cost_per_million_usd": 0.0,
                                "pricing_version": (
                                    "google-gemini-3.6-flash-free-2026-07-21"
                                ),
                            }
                        ),
                    }
                )
                revision = revision.model_copy(update={"slots": slots})
            repository.add_plan_revision(revision)

        accepted = ReviewIntakeService(repository).accept(load_request_fixture())
        runtime = ProviderRegistryRuntime(
            {
                "google": GeminiInteractionsProvider(
                    api_key=GOOGLE_API_KEY,
                ),
            },
            max_attempts=1,
        )
        state = ReviewOrchestrator(repository, runtime).run_fixture_path(
            accepted.session_id,
            FixturePath.A_ONLY,
            now=datetime.now(UTC),
        )
        invocation = repository.list_invocations(accepted.session_id)[0]
        attempts = repository.list_provider_attempts(invocation.invocation_id)
        result = repository.get_result(accepted.session_id)

        assert state == ReviewState.RESULT_RETURNED
        assert invocation.status == "completed"
        assert invocation.provider == "google"
        assert invocation.model == "gemini-3.6-flash"
        assert len(attempts) == 1
        assert attempts[0].status == "succeeded"
        assert attempts[0].finish_status == "completed"
        assert attempts[0].total_tokens > 0
        assert attempts[0].cost_usd == 0
        assert result is not None
        assert result.path == FixturePath.A_ONLY.value
        assert result.document["baseline"]["changed_by_panel"] is False

        print(
            "GEMINI_ACCEPTANCE_SUMMARY="
            + json.dumps(
                {
                    "route": result.path,
                    "provider": invocation.provider,
                    "model": invocation.model,
                    "structured_output_valid": True,
                    "attempt_count": len(attempts),
                    "latency_ms": attempts[0].latency_ms,
                    "input_tokens": attempts[0].input_tokens,
                    "cached_input_tokens": attempts[0].cached_input_tokens,
                    "output_tokens": attempts[0].output_tokens,
                    "reasoning_tokens": attempts[0].reasoning_tokens,
                    "total_tokens": attempts[0].total_tokens,
                    "cost_usd": attempts[0].cost_usd,
                    "pricing_version": attempts[0].pricing_version,
                    "category": invocation.assessment_payload["category"],
                    "risk": invocation.assessment_payload["risk"],
                    "confidence": invocation.assessment_payload["confidence"],
                    "evidence_quality": invocation.assessment_payload[
                        "evidence_quality"
                    ],
                },
                sort_keys=True,
            )
        )
    finally:
        engine.dispose()
