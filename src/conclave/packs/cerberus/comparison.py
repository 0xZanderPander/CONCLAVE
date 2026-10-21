"""Cerberus's deterministic comparator.

Two venture assessments are compared on verdict, rubric scores, risk and
evidence quality. A ``viable`` against a ``not_viable`` is a polarity conflict
and always forces cross review; so does any single rubric score differing by
``extreme_score_gap`` or more. When the pair converges, the merged assessment
is the more cautious of the two on every axis.
"""

from conclave.packs.cerberus.config import (
    VentureComparatorDimension,
    VentureHardTrigger,
    VenturePackConfig,
)
from conclave.packs.cerberus.models import VentureAssessment, VentureScores
from conclave.packs.cerberus.vocabulary import (
    CAUTION_ORDER,
    SCORE_DIMENSIONS,
    VentureVerdict,
)
from conclave.packs.comparison import ComparisonResult

_QUALITY_ORDER = {"insufficient": 0, "weak": 1, "adequate": 2, "strong": 3}
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
_POLARITY = {VentureVerdict.VIABLE: 1, VentureVerdict.NOT_VIABLE: -1}


def _score_gaps(left: VentureScores, right: VentureScores) -> list[int]:
    return [
        abs(getattr(left, name) - getattr(right, name))
        for name in SCORE_DIMENSIONS
    ]


def _merged_scores(left: VentureScores, right: VentureScores) -> VentureScores:
    values = {
        name: min(getattr(left, name), getattr(right, name))
        for name in SCORE_DIMENSIONS
        if name != "risk_exposure"
    }
    values["risk_exposure"] = max(left.risk_exposure, right.risk_exposure)
    return VentureScores(**values)


def _merged_assessment(left: VentureAssessment, right: VentureAssessment) -> VentureAssessment:
    category = min((left.category, right.category), key=lambda value: CAUTION_ORDER[value])
    summary = (
        left.summary
        if left.summary.strip() == right.summary.strip()
        else f"{left.summary.rstrip()} {right.summary.lstrip()}"
    )
    # Feedback is never concatenated: two valid responses could together exceed
    # the caller's word cap and the merged result is not re-validated. The seat
    # whose (more cautious) verdict carries the merge also carries its feedback;
    # on a tie, A's. The other seat's weaknesses and missing evidence are kept.
    cautious = left if CAUTION_ORDER[left.category] <= CAUTION_ORDER[right.category] else right
    feedback = cautious.feedback
    return left.model_copy(
        update={
            "category": category,
            "summary": summary,
            "claims": tuple(dict.fromkeys((*left.claims, *right.claims))),
            "scores": _merged_scores(left.scores, right.scores),
            "strengths": tuple(dict.fromkeys((*left.strengths, *right.strengths))),
            "weaknesses": tuple(dict.fromkeys((*left.weaknesses, *right.weaknesses))),
            "feedback": feedback,
            "material": True,
            "risk": max((left.risk, right.risk), key=lambda value: _RISK_ORDER[value]),
            "confidence": min(left.confidence, right.confidence),
            "evidence_quality": min(
                (left.evidence_quality, right.evidence_quality),
                key=lambda value: _QUALITY_ORDER[value],
            ),
            "missing_evidence": tuple(
                dict.fromkeys((*left.missing_evidence, *right.missing_evidence))
            ),
        }
    )


def compare_venture_assessments(
    left: VentureAssessment,
    right: VentureAssessment,
    config: VenturePackConfig,
) -> ComparisonResult:
    gaps = _score_gaps(left.scores, right.scores)
    distances = {
        VentureComparatorDimension.VERDICT_DISPOSITION: (
            0.0 if left.category == right.category else 1.0
        ),
        VentureComparatorDimension.SCORE_PROFILE: sum(gaps) / (4 * len(gaps)),
        VentureComparatorDimension.RISK_MATERIALITY: (
            abs(_RISK_ORDER[left.risk] - _RISK_ORDER[right.risk]) / 2
        ),
        VentureComparatorDimension.EVIDENCE_SUFFICIENCY_QUALITY: (
            abs(_QUALITY_ORDER[left.evidence_quality] - _QUALITY_ORDER[right.evidence_quality])
            / 3
        ),
    }
    comparator = config.comparator
    weighted = sum(comparator.weights[dimension] * value for dimension, value in distances.items())

    triggers: list[VentureHardTrigger] = []
    if _POLARITY.get(left.category, 0) * _POLARITY.get(right.category, 0) < 0:
        triggers.append(VentureHardTrigger.VERDICT_POLARITY_CONFLICT)
    if max(gaps) >= comparator.extreme_score_gap:
        triggers.append(VentureHardTrigger.EXTREME_SCORE_DIVERGENCE)
    approved = set(comparator.hard_triggers)
    triggers = [trigger for trigger in triggers if trigger in approved]

    merge_compatible = distances[VentureComparatorDimension.VERDICT_DISPOSITION] == 0
    requires_cross_review = bool(
        triggers or weighted > comparator.tolerance or not merge_compatible
    )
    return ComparisonResult(
        dimension_distances={dimension.value: value for dimension, value in distances.items()},
        weighted_distance=weighted,
        distance=1.0 if triggers else weighted,
        tolerance=comparator.tolerance,
        hard_triggers=tuple(trigger.value for trigger in triggers),
        agreements=tuple(
            dimension.value for dimension, distance in distances.items() if distance == 0
        ),
        disagreements=tuple(
            dimension.value for dimension, distance in distances.items() if distance > 0
        ),
        merge_compatible=merge_compatible,
        requires_cross_review=requires_cross_review,
        merged_assessment=(
            None if requires_cross_review else _merged_assessment(left, right)
        ),
    )
