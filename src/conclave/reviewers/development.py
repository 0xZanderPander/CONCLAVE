from conclave.domain.enums import RecommendationCategory
from conclave.reviewers.runtime import Assessment, ReviewCall


class DevelopmentReviewerRuntime:
    """Local deterministic reviewer used by the fixture API."""

    def review(self, call: ReviewCall) -> Assessment:
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
