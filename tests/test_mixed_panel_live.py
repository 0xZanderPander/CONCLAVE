import json
import os
from datetime import UTC, datetime
from typing import Any

import pytest

from conclave.domain.enums import ReviewerSlot, ReviewStage, ReviewState
from conclave.fixtures import load_design_plan_revisions, load_request_fixture
from conclave.intake import ReviewIntakeService
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.anthropic import AnthropicMessagesProvider
from conclave.reviewers.openai import OpenAIResponsesProvider
from conclave.reviewers.prompts import (
    REVIEWER_A_CROSS_PROMPT_VERSION,
    REVIEWER_A_CROSS_ROLE_VERSION,
    REVIEWER_A_PROMPT_VERSION,
    REVIEWER_A_ROLE_VERSION,
    REVIEWER_B_CROSS_PROMPT_VERSION,
    REVIEWER_B_CROSS_ROLE_VERSION,
    REVIEWER_B_PROMPT_VERSION,
    REVIEWER_B_ROLE_VERSION,
    REVIEWER_C_BLIND_PROMPT_VERSION,
    REVIEWER_C_BLIND_ROLE_VERSION,
    REVIEWER_C_JUDGE_PROMPT_VERSION,
    REVIEWER_C_JUDGE_ROLE_VERSION,
)
from conclave.reviewers.runtime import ProviderRegistryRuntime
from tests.helpers import create_test_engine, create_test_repository

OPENAI_API_KEY = os.getenv("CONCLAVE_OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("CONCLAVE_ANTHROPIC_API_KEY")


def _safe_output_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    assessment = payload.get("assessment", payload)
    if "verdict" in payload:
        return {
            "verdict": payload["verdict"],
            "selected_slot": payload.get("selected_slot"),
            "confidence": payload.get("confidence"),
            "evidence_quality": payload.get("evidence_quality"),
        }
    return {
        "category": assessment.get("category"),
        "risk": assessment.get("risk"),
        "confidence": assessment.get("confidence"),
        "evidence_quality": assessment.get("evidence_quality"),
        "action_types": [
            action.get("type")
            for action in assessment.get("actions", [])
            if isinstance(action, dict)
        ],
        "claim_count": len(assessment.get("claims", [])),
    }


@pytest.mark.skipif(
    not OPENAI_API_KEY or not ANTHROPIC_API_KEY,
    reason="OpenAI and Anthropic keys are required for the live mixed-panel gate",
)
def test_live_mixed_panel_runs_one_bounded_cross_provider_path() -> None:
    assert OPENAI_API_KEY is not None
    assert ANTHROPIC_API_KEY is not None
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            if revision.revision == 4:
                slots = dict(revision.slots)
                one_attempt = slots[ReviewerSlot.A].provider_policy.model_copy(
                    update={"max_attempts": 1}
                )
                anthropic_policy = slots[
                    ReviewerSlot.B
                ].provider_policy.model_copy(
                    update={
                        "max_attempts": 1,
                        "max_cost_usd": 0.10,
                        "reasoning_effort": "low",
                        "input_cost_per_million_usd": 2.0,
                        "output_cost_per_million_usd": 10.0,
                        "pricing_version": "anthropic-sonnet-5-intro-2026-06-30",
                    }
                )
                anthropic_cross_policy = anthropic_policy.model_copy(
                    update={
                        "max_input_characters": 45_000,
                        "max_cost_usd": 0.13,
                    }
                )
                slots[ReviewerSlot.A] = slots[ReviewerSlot.A].model_copy(
                    update={
                        "provider": "openai",
                        "model": "gpt-5.6-terra",
                        "role_version": REVIEWER_A_ROLE_VERSION,
                        "prompt_version": REVIEWER_A_PROMPT_VERSION,
                        "schema_version": "assessment-v2",
                        "cross_review_role_version": REVIEWER_A_CROSS_ROLE_VERSION,
                        "cross_review_prompt_version": REVIEWER_A_CROSS_PROMPT_VERSION,
                        "cross_review_schema_version": "cross-review-v1",
                        "provider_policy": one_attempt,
                        "cross_review_provider_policy": one_attempt,
                    }
                )
                slots[ReviewerSlot.B] = slots[ReviewerSlot.B].model_copy(
                    update={
                        "provider": "anthropic",
                        "model": "claude-sonnet-5",
                        "role_version": REVIEWER_B_ROLE_VERSION,
                        "prompt_version": REVIEWER_B_PROMPT_VERSION,
                        "schema_version": "assessment-v2",
                        "cross_review_role_version": REVIEWER_B_CROSS_ROLE_VERSION,
                        "cross_review_prompt_version": REVIEWER_B_CROSS_PROMPT_VERSION,
                        "cross_review_schema_version": "cross-review-v1",
                        "provider_policy": anthropic_policy,
                        "cross_review_provider_policy": anthropic_cross_policy,
                    }
                )
                slots[ReviewerSlot.C] = slots[ReviewerSlot.C].model_copy(
                    update={
                        "provider": "openai",
                        "model": "gpt-5.6-terra",
                        "role_version": REVIEWER_C_BLIND_ROLE_VERSION,
                        "prompt_version": REVIEWER_C_BLIND_PROMPT_VERSION,
                        "schema_version": "assessment-v2",
                        "judging_role_version": REVIEWER_C_JUDGE_ROLE_VERSION,
                        "judging_prompt_version": REVIEWER_C_JUDGE_PROMPT_VERSION,
                        "judging_schema_version": "reviewer-c-judgment-v2",
                        "provider_policy": one_attempt,
                        "judging_provider_policy": one_attempt.model_copy(
                            update={
                                "max_input_characters": 60_000,
                                "max_cost_usd": 0.25,
                            }
                        ),
                    }
                )
                revision = revision.model_copy(update={"slots": slots})
            repository.add_plan_revision(revision)

        accepted = ReviewIntakeService(repository).accept(
            load_request_fixture("04-surviving-reviewer-conflict.json")
        )
        runtime = ProviderRegistryRuntime(
            {
                "openai": OpenAIResponsesProvider(api_key=OPENAI_API_KEY),
                "anthropic": AnthropicMessagesProvider(api_key=ANTHROPIC_API_KEY),
            },
            max_attempts=1,
        )
        state = ReviewOrchestrator(repository, runtime).run_fixture_path(
            accepted.session_id,
            FixturePath.C_TIE_BROKEN,
            now=datetime.now(UTC),
        )

        invocations = repository.list_invocations(accepted.session_id)
        result = repository.get_result(accepted.session_id)
        anthropic_invocations = [
            invocation
            for invocation in invocations
            if invocation.provider == "anthropic"
        ]
        assert state == ReviewState.RESULT_RETURNED
        assert len(invocations) == 6
        assert all(invocation.status == "completed" for invocation in invocations)
        assert [
            (invocation.reviewer_slot, invocation.provider, invocation.stage)
            for invocation in anthropic_invocations
        ] == [
            ("B", "anthropic", ReviewStage.INDEPENDENT.value),
            ("B", "anthropic", ReviewStage.CROSS_REVIEW.value),
        ]
        assert sum(invocation.attempt_count for invocation in anthropic_invocations) == 2
        assert all(invocation.attempt_count == 1 for invocation in invocations)
        assert result is not None
        assert result.path == FixturePath.C_TIE_BROKEN.value
        assert sum(invocation.cost_usd or 0 for invocation in invocations) <= 0.93

        telemetry = []
        for invocation in invocations:
            attempts = repository.list_provider_attempts(invocation.invocation_id)
            assert len(attempts) == 1
            assert attempts[0].status == "succeeded"
            telemetry.append(
                {
                    "slot": invocation.reviewer_slot,
                    "stage": invocation.stage,
                    "round": invocation.round,
                    "provider": invocation.provider,
                    "model": invocation.model,
                    "latency_ms": attempts[0].latency_ms,
                    "input_tokens": attempts[0].input_tokens,
                    "output_tokens": attempts[0].output_tokens,
                    "total_tokens": attempts[0].total_tokens,
                    "cost_usd": attempts[0].cost_usd,
                    "structured_output_valid": True,
                    "output": _safe_output_summary(invocation.assessment_payload),
                }
            )

        print(
            "MIXED_PANEL_ACCEPTANCE_SUMMARY="
            + json.dumps(
                {
                    "route": result.path,
                    "status": result.document["status"],
                    "baseline_category": result.document["baseline"]["category"],
                    "final_category": result.document["recommendation"]["category"],
                    "changed_by_panel": result.document["baseline"][
                        "changed_by_panel"
                    ],
                    "total_cost_usd": sum(
                        invocation.cost_usd or 0 for invocation in invocations
                    ),
                    "anthropic_call_count": len(anthropic_invocations),
                    "invocations": telemetry,
                },
                sort_keys=True,
            )
        )
    finally:
        engine.dispose()
