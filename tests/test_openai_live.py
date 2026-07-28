import os
from datetime import UTC, datetime

import pytest

from conclave.domain.enums import ReviewerSlot, ReviewState
from conclave.fixtures import load_design_plan_revisions, load_request_fixture
from conclave.intake import ReviewIntakeService
from conclave.orchestration.service import FixturePath, ReviewOrchestrator
from conclave.reviewers.openai import OpenAIResponsesProvider
from conclave.reviewers.prompts import (
    REVIEWER_A_PROMPT_VERSION,
    REVIEWER_A_ROLE_VERSION,
)
from conclave.reviewers.runtime import ProviderRegistryRuntime
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
