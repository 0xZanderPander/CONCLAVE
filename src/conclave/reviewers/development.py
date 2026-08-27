from conclave.domain.enums import RecommendationCategory
from conclave.reviewers.runtime import (
    Assessment,
    ProviderRegistryRuntime,
    ReviewCall,
    ReviewerCJudgment,
)


class DevelopmentReviewerProvider:
    """Deterministic provider used by fixture and process tests."""

    def invoke(self, call: ReviewCall) -> Assessment | ReviewerCJudgment:
        if call.stage.value == "judging":
            return ReviewerCJudgment(
                verdict="insufficient_evidence",
                summary="Fixture reviewer C requested more evidence.",
                resolution_assessment=Assessment(
                    category=RecommendationCategory.COLLECT_MORE_DATA,
                    summary="Collect more evidence before choosing either recommendation.",
                    claims=("The fixture does not support a decisive tie-break.",),
                    material=False,
                    risk="low",
                    confidence=0.7,
                    evidence_quality="adequate",
                    expected_goal_impact="uncertain",
                    tracking_health=call.snapshot["quality"]["tracking_health"],
                    optimization_eligible=call.snapshot["quality"]["optimization_eligible"],
                    primary_conversion=call.snapshot["sections"]["goal"]["primary_conversion"],
                ),
                confidence=0.7,
                evidence_quality="adequate",
                unresolved_claims=("The fixture does not support a decisive tie-break.",),
            )
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
            expected_goal_impact="uncertain",
            tracking_health=call.snapshot["quality"]["tracking_health"],
            optimization_eligible=call.snapshot["quality"]["optimization_eligible"],
            primary_conversion=call.snapshot["sections"]["goal"]["primary_conversion"],
        )


class DevelopmentReviewerRuntime(ProviderRegistryRuntime):
    """Local provider registry used by the fixture API and worker process."""

    def __init__(self) -> None:
        provider = DevelopmentReviewerProvider()
        super().__init__({"fixture": provider, "deterministic": provider})
