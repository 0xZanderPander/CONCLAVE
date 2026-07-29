from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from conclave.domain.enums import ReviewStage
from conclave.reviewers.runtime import Assessment, RecommendedAction
from conclave.task_packs.models import (
    ComparatorDimension,
    HardTrigger,
    TaskPack,
)

_QUALITY_ORDER = {
    "insufficient": 0,
    "weak": 1,
    "adequate": 2,
    "strong": 3,
}
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
_URGENCY_ORDER = {"low": 0, "normal": 1, "high": 2}
_IMPACT_ORDER = {"negative": 0, "neutral": 1, "uncertain": 2, "positive": 3}
_MERGE_REQUIRED = {
    ComparatorDimension.RECOMMENDATION_DISPOSITION,
    ComparatorDimension.ACTION_TYPE_DIRECTION,
    ComparatorDimension.TARGET_SCOPE,
}


class ComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    dimension_distances: dict[ComparatorDimension, float]
    weighted_distance: float = Field(ge=0, le=1)
    distance: float = Field(ge=0, le=1)
    tolerance: float = Field(ge=0, le=1)
    hard_triggers: tuple[HardTrigger, ...] = ()
    agreements: tuple[str, ...] = ()
    disagreements: tuple[str, ...] = ()
    merge_compatible: bool
    requires_cross_review: bool
    merged_assessment: Assessment | None = None


class ComparisonRound(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: ReviewStage
    round: int = Field(ge=1)
    comparison: ComparisonResult

    def public_document(self) -> dict[str, object]:
        result = self.comparison
        return {
            "stage": self.stage.value,
            "round": self.round,
            "distance": result.distance,
            "weighted_distance": result.weighted_distance,
            "tolerance": result.tolerance,
            "dimension_distances": {
                dimension.value: value
                for dimension, value in result.dimension_distances.items()
            },
            "hard_triggers": [trigger.value for trigger in result.hard_triggers],
            "merge_compatible": result.merge_compatible,
            "requires_cross_review": result.requires_cross_review,
            "agreements": list(result.agreements),
            "disagreements": list(result.disagreements),
        }


def _set_distance(left: set[object], right: set[object]) -> float:
    if left == right:
        return 0.0
    if not left or not right:
        return 1.0
    overlap = len(left & right)
    union = len(left | right)
    return 1.0 - (overlap / union)


def _optional_order_distance(
    left: str | None,
    right: str | None,
    order: dict[str, int],
) -> float:
    if left == right:
        return 0.0
    if left is None or right is None:
        return 0.5
    return abs(order[left] - order[right]) / max(order.values())


def _actions(assessment: Assessment) -> tuple[RecommendedAction, ...]:
    return tuple(sorted(assessment.actions, key=lambda item: (item.target_id, item.type)))


def _directions(
    assessment: Assessment,
    task_pack: TaskPack,
) -> set[tuple[str, str, str]]:
    return {
        (
            action.target_id,
            action.type,
            task_pack.action_directions.get(action.type, "unknown"),
        )
        for action in assessment.actions
    }


def _magnitude_distance(left: Assessment, right: Assessment) -> float:
    left_values = {(action.target_id, action.type): action.magnitude for action in left.actions}
    right_values = {(action.target_id, action.type): action.magnitude for action in right.actions}
    if left_values.keys() != right_values.keys():
        return 1.0 if left_values or right_values else 0.0
    distances: list[float] = []
    for key in left_values:
        left_value = left_values[key]
        right_value = right_values[key]
        if left_value == right_value:
            distances.append(0.0)
        elif left_value is None or right_value is None:
            distances.append(0.5)
        else:
            denominator = max(abs(left_value), abs(right_value), 1e-12)
            distances.append(min(abs(left_value - right_value) / denominator, 1.0))
    return max(distances, default=0.0)


def _timing_distance(left: Assessment, right: Assessment) -> float:
    left_urgency = max(
        (_URGENCY_ORDER[action.urgency] for action in left.actions),
        default=_URGENCY_ORDER["normal"],
    )
    right_urgency = max(
        (_URGENCY_ORDER[action.urgency] for action in right.actions),
        default=_URGENCY_ORDER["normal"],
    )
    urgency_distance = abs(left_urgency - right_urgency) / 2
    if left.review_after_hours == right.review_after_hours:
        review_distance = 0.0
    elif left.review_after_hours is None or right.review_after_hours is None:
        review_distance = 0.5
    else:
        denominator = max(left.review_after_hours, right.review_after_hours, 1e-12)
        review_distance = min(
            abs(left.review_after_hours - right.review_after_hours) / denominator,
            1.0,
        )
    return max(urgency_distance, review_distance)


def _risk_distance(left: Assessment, right: Assessment) -> float:
    risk = abs(_RISK_ORDER[left.risk] - _RISK_ORDER[right.risk]) / 2
    materiality = 0.0 if left.material == right.material else 1.0
    return max(risk, materiality)


def _opposite_direction(
    left: Assessment,
    right: Assessment,
    task_pack: TaskPack,
) -> bool:
    left_by_target = {
        action.target_id: task_pack.action_directions.get(action.type, "unknown")
        for action in left.actions
    }
    right_by_target = {
        action.target_id: task_pack.action_directions.get(action.type, "unknown")
        for action in right.actions
    }
    return any(
        frozenset((direction, right_by_target[target]))
        in {frozenset(pair) for pair in task_pack.opposite_direction_pairs}
        for target, direction in left_by_target.items()
        if target in right_by_target and direction != right_by_target[target]
    )


def _hard_triggers(
    left: Assessment,
    right: Assessment,
    task_pack: TaskPack,
    *,
    failed_goal: bool,
) -> tuple[HardTrigger, ...]:
    triggers: list[HardTrigger] = []
    if (
        left.tracking_health is not None
        and right.tracking_health is not None
        and left.tracking_health != right.tracking_health
    ):
        triggers.append(HardTrigger.TRACKING_HEALTH_CONFLICT)
    if (
        left.primary_conversion is not None
        and right.primary_conversion is not None
        and left.primary_conversion != right.primary_conversion
    ):
        triggers.append(HardTrigger.GOAL_OR_PRIMARY_CONVERSION_CONFLICT)
    if _opposite_direction(left, right, task_pack):
        triggers.append(HardTrigger.OPPOSITE_ACTION_DIRECTION)
    left_targets = {action.target_id for action in left.actions}
    right_targets = {action.target_id for action in right.actions}
    if left_targets and right_targets and not left_targets & right_targets:
        triggers.append(HardTrigger.INCOMPATIBLE_TARGET_SCOPE)
    if (
        left.optimization_eligible is not None
        and right.optimization_eligible is not None
        and left.optimization_eligible != right.optimization_eligible
    ):
        triggers.append(HardTrigger.EVIDENCE_ELIGIBILITY_CONFLICT)
    action_types = {action.type for action in (*left.actions, *right.actions)}
    if action_types - task_pack.allowed_action_types:
        triggers.append(HardTrigger.ACTION_OUTSIDE_ONTOLOGY)
    if failed_goal:
        triggers.append(HardTrigger.FAILED_GOAL_MOVEMENT)
    approved = set(task_pack.comparator.hard_triggers)
    return tuple(trigger for trigger in triggers if trigger in approved)


def _more_conservative_action(
    left: RecommendedAction,
    right: RecommendedAction,
) -> RecommendedAction:
    if left.magnitude is None:
        magnitude = right.magnitude
    elif right.magnitude is None:
        magnitude = left.magnitude
    else:
        magnitude = min(left.magnitude, right.magnitude)
    urgency = max(
        (left.urgency, right.urgency),
        key=lambda value: _URGENCY_ORDER[value],
    )
    return left.model_copy(
        update={
            "magnitude": magnitude,
            "urgency": urgency,
            "confidence": min(left.confidence, right.confidence),
        }
    )


def _merged_assessment(left: Assessment, right: Assessment) -> Assessment:
    right_actions = {(action.target_id, action.type): action for action in right.actions}
    actions = tuple(
        _more_conservative_action(action, right_actions[(action.target_id, action.type)])
        for action in _actions(left)
    )
    risk = max((left.risk, right.risk), key=lambda value: _RISK_ORDER[value])
    evidence_quality = min(
        (left.evidence_quality, right.evidence_quality),
        key=lambda value: _QUALITY_ORDER[value],
    )
    review_times = [
        value for value in (left.review_after_hours, right.review_after_hours) if value is not None
    ]
    summary = (
        left.summary
        if left.summary.strip() == right.summary.strip()
        else f"{left.summary.rstrip()} {right.summary.lstrip()}"
    )
    return left.model_copy(
        update={
            "summary": summary,
            "claims": tuple(dict.fromkeys((*left.claims, *right.claims))),
            "actions": actions,
            "material": left.material or right.material,
            "risk": risk,
            "confidence": min(left.confidence, right.confidence),
            "evidence_quality": evidence_quality,
            "missing_evidence": tuple(
                dict.fromkeys((*left.missing_evidence, *right.missing_evidence))
            ),
            "review_after_hours": min(review_times) if review_times else None,
        }
    )


def compare_assessments(
    left: Assessment,
    right: Assessment,
    task_pack: TaskPack,
    *,
    failed_goal: bool = False,
) -> ComparisonResult:
    left_directions = _directions(left, task_pack)
    right_directions = _directions(right, task_pack)
    left_targets = {action.target_id for action in left.actions}
    right_targets = {action.target_id for action in right.actions}
    distances = {
        ComparatorDimension.RECOMMENDATION_DISPOSITION: (
            0.0 if left.category == right.category else 1.0
        ),
        ComparatorDimension.ACTION_TYPE_DIRECTION: _set_distance(
            set(left_directions),
            set(right_directions),
        ),
        ComparatorDimension.TARGET_SCOPE: _set_distance(
            set(left_targets),
            set(right_targets),
        ),
        ComparatorDimension.EXPECTED_GOAL_IMPACT: _optional_order_distance(
            left.expected_goal_impact,
            right.expected_goal_impact,
            _IMPACT_ORDER,
        ),
        ComparatorDimension.EVIDENCE_SUFFICIENCY_QUALITY: abs(
            _QUALITY_ORDER[left.evidence_quality] - _QUALITY_ORDER[right.evidence_quality]
        )
        / 3,
        ComparatorDimension.MAGNITUDE_EXPOSURE: _magnitude_distance(left, right),
        ComparatorDimension.RISK_MATERIALITY: _risk_distance(left, right),
        ComparatorDimension.URGENCY_TIMING: _timing_distance(left, right),
    }
    weights = task_pack.comparator.weights
    weighted = sum(weights[dimension] * value for dimension, value in distances.items())
    triggers = _hard_triggers(
        left,
        right,
        task_pack,
        failed_goal=failed_goal,
    )
    merge_compatible = all(distances[dimension] == 0 for dimension in _MERGE_REQUIRED)
    requires_cross_review = bool(
        triggers or weighted > task_pack.comparator.tolerance or not merge_compatible
    )
    agreements = tuple(
        dimension.value for dimension, distance in distances.items() if distance == 0
    )
    disagreements = tuple(
        dimension.value for dimension, distance in distances.items() if distance > 0
    )
    merged = None
    if not requires_cross_review:
        merged = _merged_assessment(left, right)
    return ComparisonResult(
        dimension_distances=distances,
        weighted_distance=weighted,
        distance=1.0 if triggers else weighted,
        tolerance=task_pack.comparator.tolerance,
        hard_triggers=triggers,
        agreements=agreements,
        disagreements=disagreements,
        merge_compatible=merge_compatible,
        requires_cross_review=requires_cross_review,
        merged_assessment=merged,
    )


def comparison_trigger_labels(result: ComparisonResult) -> tuple[str, ...]:
    labels: list[str] = []
    if result.hard_triggers:
        labels.append("hard_conflict")
    if not result.merge_compatible and not result.hard_triggers:
        labels.append("merge_incompatible")
    elif result.weighted_distance > result.tolerance and not result.hard_triggers:
        labels.append("weighted_distance")
    return tuple(labels)


def ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
