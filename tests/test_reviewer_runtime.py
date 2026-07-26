from datetime import UTC, datetime

import pytest

from conclave.domain.enums import (
    RecommendationCategory,
    ReviewerSlot,
    ReviewStage,
)
from conclave.reviewers.runtime import (
    Assessment,
    FakeReviewerRuntime,
    ReviewCall,
)


def test_fake_runtime_is_explicit_and_deterministic() -> None:
    assessment = Assessment(
        category=RecommendationCategory.COLLECT_MORE_DATA,
        summary="The sample is too small.",
        confidence=0.8,
        evidence_quality="insufficient",
    )
    runtime = FakeReviewerRuntime({(ReviewerSlot.A, ReviewStage.INDEPENDENT, 1): assessment})
    call = ReviewCall(
        session_id="rs_test",
        snapshot_hash="sha256:test",
        slot=ReviewerSlot.A,
        stage=ReviewStage.INDEPENDENT,
        round=1,
        prompt_version="p1",
        schema_version="v1",
        requested_at=datetime.now(UTC),
    )

    assert runtime.review(call) == assessment
    assert runtime.calls == [call]


def test_fake_runtime_never_silently_falls_back() -> None:
    runtime = FakeReviewerRuntime({})
    call = ReviewCall(
        session_id="rs_test",
        snapshot_hash="sha256:test",
        slot=ReviewerSlot.B,
        stage=ReviewStage.INDEPENDENT,
        round=1,
        prompt_version="p1",
        schema_version="v1",
        requested_at=datetime.now(UTC),
    )

    with pytest.raises(LookupError):
        runtime.review(call)
