"""Cerberus request binding, eligibility and reviewer-output validation.

Everything the engine accepts from a model for a venture submission passes
through here. The rules are deterministic and recomputed by Conclave rather
than trusted from the model: verdict in the allowed set, scores present and in
range, structured claims traceable to the immutable snapshot, feedback inside
the configured length, and ``material`` forced to ``True`` so no venture
verdict ever auto-resolves without the panel.
"""

from datetime import datetime
from typing import Any

from conclave.contracts.errors import ContractValidationError
from conclave.packs.base import RequestEligibility, RequestMateriality
from conclave.packs.cerberus.config import VenturePackConfig
from conclave.packs.cerberus.models import (
    VentureAssessment,
    VentureCrossReviewResponse,
    VentureJudgment,
)
from conclave.packs.cerberus.vocabulary import VentureVerdict
from conclave.packs.claims import AssessmentClaim, validate_evidence_references

EVIDENCE_REFERENCE_ROOTS = frozenset({"sections", "quality", "allowed_recommendations"})

_SAFE_FALLBACK_VERDICTS = {
    VentureVerdict.INSUFFICIENT_INFORMATION,
    VentureVerdict.NEEDS_REVISION,
}


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _word_count(text: str) -> int:
    return len(text.split())


def validate_binding(config: VenturePackConfig, document: dict[str, Any]) -> None:
    comparator = document["comparator"]
    if comparator["profile"] != config.comparator.profile:
        raise ContractValidationError("comparator profile does not match task pack")
    if abs(float(comparator["tolerance"]) - config.comparator.tolerance) > 1e-12:
        raise ContractValidationError(
            "request comparator tolerance does not match the registered task-pack version"
        )
    requested = {VentureVerdict(value) for value in document["allowed_recommendations"]}
    unknown = requested - config.allowed_verdicts
    if unknown:
        raise ContractValidationError(
            "request contains unregistered verdicts: "
            f"{sorted(value.value for value in unknown)!r}"
        )
    if document["sections"]["policy"].get("rubric_version") != config.rubric_version:
        raise ContractValidationError("request rubric_version does not match task pack")


def evaluate_eligibility(
    config: VenturePackConfig,
    document: dict[str, Any],
) -> RequestEligibility:
    submitted_at = _timestamp(document["sections"]["context"]["submitted_at"])
    due_at = _timestamp(document["review_trigger"]["due_at"])
    if submitted_at > due_at:
        raise ContractValidationError("submission was recorded after the review trigger")
    age_hours = (due_at - submitted_at).total_seconds() / 3600

    reasons: list[str] = []
    review_eligible = True
    if age_hours > config.max_submission_age_hours:
        review_eligible = False
        reasons.append("stale_submission")

    quality = document["quality"]
    total_words = quality["total_words"]
    if isinstance(total_words, bool) or not isinstance(total_words, int) or total_words < 0:
        raise ContractValidationError("quality.total_words must be a non-negative integer")
    evidence_words = sum(
        _word_count(value)
        for value in document["sections"]["evidence"].values()
        if isinstance(value, str)
    )
    if total_words != evidence_words:
        raise ContractValidationError(
            "quality.total_words conflicts with the submitted evidence word count"
        )
    if total_words < config.min_total_words:
        review_eligible = False
        reasons.append("submission_too_short")
    if quality.get("gate", {}).get("passed") is False:
        review_eligible = False
        reasons.append("gate_rejected")

    # Every venture submission is material: the panel always convenes.
    return RequestEligibility(
        review_eligible=review_eligible,
        optimization_eligible=True,
        reasons=tuple(reasons),
        observed_at=submitted_at,
        evidence_age_hours=age_hours,
        materiality=RequestMateriality(
            sufficient_volume=True,
            cpa_deviation=None,
            material=True,
        ),
    )


def normalize_assessment(assessment: VentureAssessment) -> VentureAssessment:
    return assessment.model_copy(update={"material": True})


def normalize_judgment(judgment: VentureJudgment) -> VentureJudgment:
    if judgment.resolution_assessment is None:
        return judgment
    return judgment.model_copy(
        update={"resolution_assessment": normalize_assessment(judgment.resolution_assessment)}
    )


def _validate_structured_claims(document: dict[str, Any], assessment: VentureAssessment) -> None:
    if not assessment.claims:
        raise ContractValidationError("venture assessment requires at least one structured claim")
    for claim in assessment.claims:
        if not isinstance(claim, AssessmentClaim):
            raise ContractValidationError("venture assessment claims must be structured")
        if claim.claim_id is None:
            raise ContractValidationError(
                "venture assessment claim is missing its Conclave-issued ID"
            )
        if not claim.evidence_references:
            raise ContractValidationError(
                f"venture assessment claim {claim.claim_id!r} has no evidence references"
            )
        validate_evidence_references(
            document,
            claim.evidence_references,
            label=f"claim {claim.claim_id!r}",
            allowed_roots=EVIDENCE_REFERENCE_ROOTS,
        )


def validate_assessment(
    config: VenturePackConfig,
    document: dict[str, Any],
    assessment: VentureAssessment,
) -> None:
    _validate_structured_claims(document, assessment)
    if assessment.category not in config.allowed_verdicts:
        raise ContractValidationError(
            f"verdict {assessment.category.value!r} is not registered"
        )
    allowed = {VentureVerdict(value) for value in document["allowed_recommendations"]}
    if assessment.category not in allowed:
        raise ContractValidationError(
            f"verdict {assessment.category.value!r} is not allowed by the request"
        )
    if not assessment.material:
        raise ContractValidationError("venture assessments are always material")
    if _word_count(assessment.feedback) > config.max_feedback_words:
        raise ContractValidationError(
            f"feedback exceeds {config.max_feedback_words} words"
        )
    if assessment.category == VentureVerdict.VIABLE and assessment.evidence_quality in {
        "insufficient",
    }:
        raise ContractValidationError(
            "a viable verdict cannot rest on insufficient evidence"
        )
    if assessment.category == VentureVerdict.INSUFFICIENT_INFORMATION and not (
        assessment.missing_evidence
    ):
        raise ContractValidationError(
            "insufficient_information must name the missing evidence"
        )


def validate_judgment(
    config: VenturePackConfig,
    document: dict[str, Any],
    judgment: VentureJudgment,
    *,
    available_claim_ids: frozenset[str],
) -> None:
    classified = (
        *judgment.supporting_claim_ids,
        *judgment.rejected_claim_ids,
        *judgment.unresolved_claim_ids,
    )
    if not classified:
        raise ContractValidationError("venture judgment must classify submitted claims")
    unknown = set(classified) - available_claim_ids
    if unknown:
        raise ContractValidationError(
            f"judge classified unknown claim IDs: {sorted(unknown)!r}"
        )
    omitted = available_claim_ids - set(classified)
    if omitted:
        raise ContractValidationError(f"judge omitted claim IDs: {sorted(omitted)!r}")
    if judgment.resolution_assessment is not None:
        validate_assessment(config, document, judgment.resolution_assessment)
    if judgment.verdict in {"insufficient_evidence", "escalate"}:
        assessment = judgment.resolution_assessment
        if assessment is None:
            raise ContractValidationError(f"{judgment.verdict} requires a resolution assessment")
        if assessment.category not in _SAFE_FALLBACK_VERDICTS:
            raise ContractValidationError(
                f"{judgment.verdict} requires a cautious fallback verdict"
            )


def validate_cross_review(
    config: VenturePackConfig,
    document: dict[str, Any],
    response: VentureCrossReviewResponse,
    *,
    peer_claim_ids: frozenset[str],
) -> None:
    reviewed = {review.claim_id for review in response.peer_claim_reviews}
    unknown = reviewed - peer_claim_ids
    if unknown:
        raise ContractValidationError(
            f"cross review classified unknown peer claim IDs: {sorted(unknown)!r}"
        )
    omitted = peer_claim_ids - reviewed
    if omitted:
        raise ContractValidationError(
            f"cross review omitted peer claim IDs: {sorted(omitted)!r}"
        )
    for review in response.peer_claim_reviews:
        validate_evidence_references(
            document,
            review.evidence_references,
            label=f"peer claim {review.claim_id!r}",
            allowed_roots=EVIDENCE_REFERENCE_ROOTS,
        )
    validate_assessment(config, document, response.assessment)
