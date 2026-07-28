from datetime import UTC, datetime

import pytest

from conclave.domain.enums import (
    RecommendationCategory,
    ReviewerSlot,
    ReviewerType,
    ReviewStage,
)
from conclave.reviewers.runtime import (
    Assessment,
    FakeReviewerRuntime,
    ProviderRegistryRuntime,
    ReviewCall,
    ReviewerCJudgment,
    ReviewerProviderExhaustedError,
    UnknownReviewerProviderError,
)


def _call(provider: str = "fake") -> ReviewCall:
    return ReviewCall(
        session_id="rs_test",
        snapshot_hash="sha256:test",
        slot=ReviewerSlot.A,
        stage=ReviewStage.INDEPENDENT,
        round=1,
        reviewer_type=ReviewerType.MODEL,
        provider=provider,
        model="fixture-model",
        role_version="role-v1",
        prompt_version="p1",
        schema_version="v1",
        snapshot={"evidence": "fixture"},
        requested_at=datetime.now(UTC),
    )


def test_fake_runtime_is_explicit_and_deterministic() -> None:
    assessment = Assessment(
        category=RecommendationCategory.COLLECT_MORE_DATA,
        summary="The sample is too small.",
        confidence=0.8,
        evidence_quality="insufficient",
    )
    runtime = FakeReviewerRuntime({(ReviewerSlot.A, ReviewStage.INDEPENDENT, 1): assessment})
    call = _call()

    assert runtime.review(call) == assessment
    assert runtime.calls == [call]


def test_fake_runtime_never_silently_falls_back() -> None:
    runtime = FakeReviewerRuntime({})
    call = _call().model_copy(update={"slot": ReviewerSlot.B})

    with pytest.raises(LookupError):
        runtime.review(call)


def test_provider_registry_validates_structured_output() -> None:
    class MappingProvider:
        def invoke(self, _call: ReviewCall) -> dict:
            return {
                "category": "collect_more_data",
                "summary": "Wait for more evidence.",
                "confidence": 0.7,
                "evidence_quality": "weak",
            }

    runtime = ProviderRegistryRuntime({"fake": MappingProvider()})

    assert runtime.review(_call()).evidence_quality == "weak"


def test_provider_registry_rejects_unknown_provider() -> None:
    runtime = ProviderRegistryRuntime({})

    with pytest.raises(UnknownReviewerProviderError):
        runtime.review(_call("missing"))


def test_provider_registry_retries_then_validates_output() -> None:
    class EventuallyValidProvider:
        def __init__(self) -> None:
            self.attempts = 0

        def invoke(self, _call: ReviewCall) -> dict:
            self.attempts += 1
            if self.attempts == 1:
                return {"summary": "Incomplete response."}
            return {
                "category": "observe",
                "summary": "No material change.",
                "confidence": 0.8,
                "evidence_quality": "strong",
            }

    provider = EventuallyValidProvider()
    runtime = ProviderRegistryRuntime({"fake": provider}, max_attempts=2)

    assert runtime.review(_call()).category == RecommendationCategory.OBSERVE
    assert provider.attempts == 2


def test_provider_registry_reports_exhausted_provider_without_leaking_response() -> None:
    class BrokenProvider:
        def invoke(self, _call: ReviewCall) -> dict:
            return {"provider_secret": "must not enter the contract"}

    runtime = ProviderRegistryRuntime({"fake": BrokenProvider()}, max_attempts=2)

    with pytest.raises(ReviewerProviderExhaustedError, match="after 2 attempts"):
        runtime.review(_call())


def test_reviewer_c_judgment_requires_an_explicit_consistent_verdict() -> None:
    with pytest.raises(ValueError, match="selected_slot=A"):
        ReviewerCJudgment(
            verdict="select_a",
            selected_slot="B",
            summary="Contradictory selection.",
            confidence=0.8,
            evidence_quality="adequate",
        )

    with pytest.raises(ValueError, match="requires a resolution assessment"):
        ReviewerCJudgment(
            verdict="synthesize",
            summary="No synthesis supplied.",
            confidence=0.8,
            evidence_quality="adequate",
        )
