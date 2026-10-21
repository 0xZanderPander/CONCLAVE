"""Deterministic reviewer provider for fixture mode and process tests.

Serves both packs. In fixture mode every provider name (``fixture``,
``deterministic``, ``openai``, ``anthropic``, ``google``) resolves to this
provider so a plan revision bound to live providers can be exercised end to
end at $0. Fixture mode is selected explicitly by
``CONCLAVE_REVIEWER_RUNTIME_MODE=fixture``; nothing here is reachable from a
live runtime.
"""

from conclave.domain.enums import RecommendationCategory
from conclave.packs.cerberus import TASK_PACK_REF as CERBERUS_TASK_PACK_REF
from conclave.packs.cerberus.models import (
    VentureAssessment,
    VentureCrossReviewResponse,
    VentureJudgment,
    VentureScores,
)
from conclave.packs.claims import AssessmentClaim, PeerClaimReview
from conclave.reviewers.runtime import (
    Assessment,
    ProviderRegistryRuntime,
    ReviewCall,
    ReviewerCJudgment,
)


class DevelopmentReviewerProvider:
    """Deterministic provider used by fixture and process tests."""

    def invoke(self, call: ReviewCall):
        task_pack_ref = call.task_pack_ref or call.snapshot.get("task_pack_ref")
        if task_pack_ref == CERBERUS_TASK_PACK_REF:
            return self._venture(call)
        return self._marketing(call)

    # ------------------------------------------------------------------ chimera
    @staticmethod
    def _marketing(call: ReviewCall) -> Assessment | ReviewerCJudgment:
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

    # ----------------------------------------------------------------- cerberus
    @staticmethod
    def _venture_assessment(call: ReviewCall) -> VentureAssessment:
        return VentureAssessment(
            category="needs_revision",
            summary=(
                f"Fixture venture assessment from seat {call.slot.value} during "
                f"{call.stage.value}: the problem is specific but the market claim is unevidenced."
            ),
            claims=(
                AssessmentClaim(
                    claim_type="observation",
                    statement="The submission names a specific customer and a specific pain.",
                    evidence_references=("sections.evidence.problem",),
                ),
                AssessmentClaim(
                    claim_type="inference",
                    statement="The market size is asserted, not evidenced.",
                    evidence_references=("sections.evidence.market",),
                    alternative_explanations=("The founder may hold data not submitted.",),
                ),
            ),
            scores=VentureScores(
                problem_clarity=4,
                market_opportunity=3,
                differentiation=3,
                feasibility=3,
                team_capability=3,
                risk_exposure=3,
            ),
            strengths=("Clear problem statement.",),
            weaknesses=("Market size is unsupported.",),
            feedback=(
                "Fixture feedback: the problem is well described. Before resubmitting, add "
                "evidence for the market size and name the first ten customers you would call."
            ),
            risk="medium",
            confidence=0.7,
            evidence_quality="adequate",
            missing_evidence=("Market sizing source.",),
        )

    def _venture(self, call: ReviewCall):
        if call.stage.value == "judging":
            available = [
                claim.claim_id
                for source in (
                    [call.own_assessment.assessment] if call.own_assessment else []
                )
                + [item.response.assessment for item in call.cross_review_responses]
                for claim in source.claims
                if isinstance(claim, AssessmentClaim) and claim.claim_id
            ]
            return VentureJudgment(
                verdict="insufficient_evidence",
                summary="Fixture judge: neither position is decisively supported.",
                resolution_assessment=self._venture_assessment(call).model_copy(
                    update={
                        "category": "insufficient_information",
                        "missing_evidence": ("Market sizing source.", "Team detail."),
                    }
                ),
                confidence=0.6,
                evidence_quality="adequate",
                unresolved_claim_ids=tuple(available),
            )
        if call.stage.value == "cross_review":
            peer_ids = [
                claim.claim_id
                for peer in call.peer_assessments
                for claim in peer.assessment.claims
                if isinstance(claim, AssessmentClaim) and claim.claim_id
            ]
            return VentureCrossReviewResponse(
                disposition="affirm",
                peer_claim_reviews=tuple(
                    PeerClaimReview(
                        claim_id=claim_id,
                        position="accept",
                        summary="Fixture cross review accepts the peer claim.",
                        evidence_references=("sections.evidence.problem",),
                    )
                    for claim_id in peer_ids
                ),
                assessment=self._venture_assessment(call),
            )
        return self._venture_assessment(call)


class DevelopmentReviewerRuntime(ProviderRegistryRuntime):
    """Local provider registry used by the fixture API and worker process."""

    PROVIDER_NAMES = ("fixture", "deterministic", "openai", "anthropic", "google")

    def __init__(self) -> None:
        provider = DevelopmentReviewerProvider()
        super().__init__(dict.fromkeys(self.PROVIDER_NAMES, provider))
