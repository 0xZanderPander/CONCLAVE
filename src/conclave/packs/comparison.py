"""Domain-neutral comparison envelope.

How two assessments are compared is pack-defined (dimensions, weights, hard
triggers, merge rules). What the engine records about a comparison is not:
distance, tolerance, which dimensions agreed, whether cross review is required,
and the merged assessment when the pair converged.
"""

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from conclave.domain.enums import ReviewStage


class ComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    dimension_distances: dict[str, float]
    weighted_distance: float = Field(ge=0, le=1)
    distance: float = Field(ge=0, le=1)
    tolerance: float = Field(ge=0, le=1)
    hard_triggers: tuple[str, ...] = ()
    agreements: tuple[str, ...] = ()
    disagreements: tuple[str, ...] = ()
    merge_compatible: bool
    requires_cross_review: bool
    merged_assessment: Any = None


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
            "dimension_distances": dict(result.dimension_distances),
            "hard_triggers": list(result.hard_triggers),
            "merge_compatible": result.merge_compatible,
            "requires_cross_review": result.requires_cross_review,
            "agreements": list(result.agreements),
            "disagreements": list(result.disagreements),
        }


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
