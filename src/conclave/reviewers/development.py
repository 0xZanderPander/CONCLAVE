from conclave.domain.enums import RecommendationCategory
from conclave.reviewers.runtime import (
    Assessment,
    ProviderRegistryRuntime,
    ReviewCall,
)


class DevelopmentReviewerProvider:
    """Deterministic provider used by fixture and process tests."""

    def invoke(self, call: ReviewCall) -> Assessment:
        return Assessment(
            category=RecommendationCategory.COLLECT_MORE_DATA,
            summary=(
                f"Fixture assessment from reviewer {call.slot.value} during {call.stage.value}."
            ),
            claims=(f"{call.slot.value}:{call.stage.value}:fixture_claim",),
            material=False,
            risk="low",
            confidence=0.7,
            evidence_quality="adequate",
        )


class DevelopmentReviewerRuntime(ProviderRegistryRuntime):
    """Local provider registry used by the fixture API and worker process."""

    def __init__(self) -> None:
        provider = DevelopmentReviewerProvider()
        super().__init__({"fixture": provider, "deterministic": provider})
