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
    AssessmentClaim,
    FakeReviewerRuntime,
    ProviderCallResult,
    ProviderRegistryRuntime,
    ProviderUsage,
    RetryableReviewerProviderError,
    ReviewCall,
    ReviewerCJudgment,
    ReviewerProviderExhaustedError,
    UnknownReviewerProviderError,
    assign_assessment_claim_ids,
)


def test_evidence_references_canonicalize_bracketed_array_indexes() -> None:
    claim = AssessmentClaim(
        statement="Creative B has no purchases.",
        evidence_references=(
            "sections.evidence.creative_breakdown[1].purchases",
        ),
    )

    assert claim.evidence_references == (
        "sections.evidence.creative_breakdown.1.purchases",
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

    assert runtime.review(call).output == assessment
    assert runtime.calls == [call]


def test_assessment_v1_string_claims_remain_readable_and_round_trip() -> None:
    assessment = Assessment.model_validate(
        {
            "category": "collect_more_data",
            "summary": "Legacy assessment.",
            "claims": ["Legacy claim text."],
            "confidence": 0.7,
            "evidence_quality": "weak",
        }
    )

    assert assessment.claims == ("Legacy claim text.",)
    assert assessment.model_dump(mode="json")["claims"] == ["Legacy claim text."]


def test_assessment_v2_claim_ids_are_conclave_issued_and_deterministic() -> None:
    draft = Assessment(
        category=RecommendationCategory.COLLECT_MORE_DATA,
        summary="Wait for more evidence.",
        claims=(
            AssessmentClaim(
                claim_type="inference",
                statement="The sample is too small.",
                evidence_references=(
                    "sections.evidence.metrics.primary_conversions",
                ),
            ),
        ),
        confidence=0.8,
        evidence_quality="weak",
    )

    first = assign_assessment_claim_ids(draft, invocation_id="inv_test")
    second = assign_assessment_claim_ids(draft, invocation_id="inv_test")

    assert first == second
    assert isinstance(first.claims[0], AssessmentClaim)
    assert first.claims[0].claim_id is not None
    assert first.claims[0].claim_id.startswith("clm_")

    with pytest.raises(ValueError, match="assigned by Conclave"):
        assign_assessment_claim_ids(first, invocation_id="inv_test")


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

    assert runtime.review(_call()).output.evidence_quality == "weak"


def test_provider_registry_rejects_unknown_provider() -> None:
    runtime = ProviderRegistryRuntime({})

    with pytest.raises(UnknownReviewerProviderError):
        runtime.review(_call("missing"))


def test_provider_registry_retries_only_a_typed_retryable_failure() -> None:
    class EventuallyAvailableProvider:
        def __init__(self) -> None:
            self.attempts = 0

        def invoke(self, _call: ReviewCall) -> dict:
            self.attempts += 1
            if self.attempts == 1:
                raise RetryableReviewerProviderError("temporary provider failure")
            return {
                "category": "observe",
                "summary": "No material change.",
                "confidence": 0.8,
                "evidence_quality": "strong",
            }

    provider = EventuallyAvailableProvider()
    runtime = ProviderRegistryRuntime({"fake": provider}, max_attempts=2)

    execution = runtime.review(_call())

    assert execution.output.category == RecommendationCategory.OBSERVE
    assert provider.attempts == 2
    assert [attempt.status for attempt in execution.attempts] == [
        "retryable_failure",
        "succeeded",
    ]


def test_provider_registry_reports_exhausted_provider_without_leaking_response() -> None:
    class BrokenProvider:
        def invoke(self, _call: ReviewCall) -> dict:
            return {"provider_secret": "must not enter the contract"}

    runtime = ProviderRegistryRuntime({"fake": BrokenProvider()}, max_attempts=2)

    with pytest.raises(
        ReviewerProviderExhaustedError,
        match="returned invalid output",
    ) as raised:
        runtime.review(_call())
    assert len(raised.value.attempts) == 1
    assert raised.value.attempts[0].status == "invalid_output"
    assert "must not enter" not in str(raised.value)
    assert "must not enter" not in raised.value.attempts[0].error_message


def test_provider_registry_preserves_safe_usage_metadata() -> None:
    assessment = Assessment(
        category=RecommendationCategory.OBSERVE,
        summary="No material change.",
        confidence=0.8,
        evidence_quality="strong",
    )

    class TelemetryProvider:
        def invoke(self, _call: ReviewCall) -> ProviderCallResult:
            return ProviderCallResult(
                output=assessment,
                provider_request_id="req_public",
                provider_response_id="resp_public",
                finish_status="completed",
                usage=ProviderUsage(
                    input_tokens=100,
                    output_tokens=20,
                    reasoning_tokens=5,
                    total_tokens=120,
                    cost_usd=0.001,
                    pricing_version="test-v1",
                ),
            )

    execution = ProviderRegistryRuntime({"fake": TelemetryProvider()}).review(_call())

    assert execution.output == assessment
    assert execution.attempts[0].provider_request_id == "req_public"
    assert execution.attempts[0].usage.total_tokens == 120
    assert execution.attempts[0].usage.pricing_version == "test-v1"


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
