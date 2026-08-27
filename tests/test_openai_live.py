import os
from datetime import UTC, datetime

import pytest

from conclave.domain.enums import ReviewerSlot, ReviewStage, ReviewState
from conclave.events.models import DomainEventType
from conclave.fixtures import load_design_plan_revisions, load_request_fixture
from conclave.intake import ReviewIntakeService
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
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
from conclave.reviewers.runtime import (
    ProviderRegistryRuntime,
    ReviewerProviderExhaustedError,
)
from tests.helpers import create_test_engine, create_test_repository

OPENAI_API_KEY = os.getenv("CONCLAVE_OPENAI_API_KEY")


@pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="CONCLAVE_OPENAI_API_KEY is required for the live reviewer-A gate",
)
def test_live_reviewer_a_produces_an_auditable_valid_baseline() -> None:
    assert OPENAI_API_KEY is not None
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            if revision.revision == 4:
                slots = dict(revision.slots)
                slots[ReviewerSlot.A] = slots[ReviewerSlot.A].model_copy(
                    update={
                        "provider": "openai",
                        "model": "gpt-5.6-terra",
                        "role_version": REVIEWER_A_ROLE_VERSION,
                        "prompt_version": REVIEWER_A_PROMPT_VERSION,
                    }
                )
                revision = revision.model_copy(update={"slots": slots})
            repository.add_plan_revision(revision)

        accepted = ReviewIntakeService(repository).accept(load_request_fixture())
        runtime = ProviderRegistryRuntime(
            {
                "openai": OpenAIResponsesProvider(api_key=OPENAI_API_KEY),
            },
            max_attempts=2,
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
        assert attempts
        assert attempts[-1].status == "succeeded"
        assert result is not None
        assert (
            result.document["baseline"]["category"]
            == result.document["recommendation"]["category"]
        )
        assert result.document["baseline"]["changed_by_panel"] is False
        assert result.document["panel_metadata"]["reviewers"][0]["attempt_count"] >= 1
    finally:
        engine.dispose()


@pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="CONCLAVE_OPENAI_API_KEY is required for the live reviewer-A/B gate",
)
def test_live_reviewer_a_and_b_are_blind_independent_and_compared() -> None:
    assert OPENAI_API_KEY is not None
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            if revision.revision == 4:
                slots = dict(revision.slots)
                slots[ReviewerSlot.A] = slots[ReviewerSlot.A].model_copy(
                    update={
                        "provider": "openai",
                        "model": "gpt-5.6-terra",
                        "role_version": REVIEWER_A_ROLE_VERSION,
                        "prompt_version": REVIEWER_A_PROMPT_VERSION,
                    }
                )
                slots[ReviewerSlot.B] = slots[ReviewerSlot.B].model_copy(
                    update={
                        "provider": "openai",
                        "model": "gpt-5.6-terra",
                        "role_version": REVIEWER_B_ROLE_VERSION,
                        "prompt_version": REVIEWER_B_PROMPT_VERSION,
                    }
                )
                revision = revision.model_copy(update={"slots": slots})
            repository.add_plan_revision(revision)

        accepted = ReviewIntakeService(repository).accept(
            load_request_fixture("02-weak-evidence.json")
        )
        runtime = ProviderRegistryRuntime(
            {
                "openai": OpenAIResponsesProvider(api_key=OPENAI_API_KEY),
            },
            max_attempts=2,
        )
        failure: ReviewerProviderExhaustedError | None = None
        try:
            state = ReviewOrchestrator(repository, runtime).run(
                accepted.session_id,
                now=datetime.now(UTC),
            )
        except ReviewerProviderExhaustedError as exc:
            failure = exc
            session = repository.get_session(accepted.session_id)
            assert session is not None
            state = ReviewState(session.current_state)

        invocations = repository.list_invocations(accepted.session_id)
        independent = [
            invocation
            for invocation in invocations
            if invocation.stage == ReviewStage.INDEPENDENT.value
            and invocation.round == 1
        ]
        assert [invocation.reviewer_slot for invocation in independent] == ["A", "B"]
        assert all(invocation.status == "completed" for invocation in independent)
        assert independent[0].snapshot_hash == independent[1].snapshot_hash
        assert independent[0].prompt_version == REVIEWER_A_PROMPT_VERSION
        assert independent[1].prompt_version == REVIEWER_B_PROMPT_VERSION
        for invocation in independent:
            attempts = repository.list_provider_attempts(invocation.invocation_id)
            assert attempts
            assert attempts[-1].status == "succeeded"

        comparisons = [
            event
            for event in repository.list_events(accepted.session_id)
            if event.event_type == DomainEventType.COMPARISON_COMPLETED
            and event.stage == ReviewStage.INDEPENDENT
            and event.round_number == 1
        ]
        assert len(comparisons) == 1
        comparison = comparisons[0]
        assert isinstance(comparison.payload["distance"], float)
        assert isinstance(comparison.payload["tolerance"], float)

        if comparison.payload["requires_cross_review"]:
            assert failure is not None
            assert state == ReviewState.CROSS_REVIEW_FAILED
            assert failure.attempts[-1].status == "permanent_failure"
            assert "not approved" in (failure.attempts[-1].error_message or "")
        else:
            assert failure is None
            assert state == ReviewState.RESULT_RETURNED
            assert repository.get_result(accepted.session_id) is not None
    finally:
        engine.dispose()


@pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="CONCLAVE_OPENAI_API_KEY is required for the live Phase 4B gate",
)
def test_live_phase4b_runs_one_bounded_full_panel() -> None:
    assert OPENAI_API_KEY is not None
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            if revision.revision == 4:
                slots = dict(revision.slots)
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
                    }
                )
                slots[ReviewerSlot.B] = slots[ReviewerSlot.B].model_copy(
                    update={
                        "provider": "openai",
                        "model": "gpt-5.6-terra",
                        "role_version": REVIEWER_B_ROLE_VERSION,
                        "prompt_version": REVIEWER_B_PROMPT_VERSION,
                        "schema_version": "assessment-v2",
                        "cross_review_role_version": REVIEWER_B_CROSS_ROLE_VERSION,
                        "cross_review_prompt_version": REVIEWER_B_CROSS_PROMPT_VERSION,
                        "cross_review_schema_version": "cross-review-v1",
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
                        "judging_provider_policy": slots[
                            ReviewerSlot.C
                        ].provider_policy.model_copy(
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
            {"openai": OpenAIResponsesProvider(api_key=OPENAI_API_KEY)},
            max_attempts=2,
        )
        state = ReviewOrchestrator(repository, runtime).run_fixture_path(
            accepted.session_id,
            FixturePath.C_TIE_BROKEN,
            now=datetime.now(UTC),
        )

        invocations = repository.list_invocations(accepted.session_id)
        assert state == ReviewState.RESULT_RETURNED
        assert len(invocations) == 6
        assert all(invocation.status == "completed" for invocation in invocations)
        assert sum(invocation.cost_usd or 0 for invocation in invocations) <= 0.90
        assert [
            (invocation.reviewer_slot, invocation.stage, invocation.round)
            for invocation in invocations
        ] == [
            ("A", ReviewStage.INDEPENDENT.value, 1),
            ("B", ReviewStage.INDEPENDENT.value, 1),
            ("A", ReviewStage.CROSS_REVIEW.value, 2),
            ("B", ReviewStage.CROSS_REVIEW.value, 2),
            ("C", ReviewStage.INDEPENDENT.value, 1),
            ("C", ReviewStage.JUDGING.value, 2),
        ]
        result = repository.get_result(accepted.session_id)
        assert result is not None
        assert result.path == FixturePath.C_TIE_BROKEN.value
        assert result.document["status"] == "caller_decision_required"
    finally:
        engine.dispose()
