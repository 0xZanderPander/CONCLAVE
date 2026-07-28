import hashlib
import json
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from conclave.domain.enums import RecommendationCategory


class ComparatorDimension(StrEnum):
    RECOMMENDATION_DISPOSITION = "recommendation_disposition"
    ACTION_TYPE_DIRECTION = "action_type_direction"
    TARGET_SCOPE = "target_scope"
    EXPECTED_GOAL_IMPACT = "expected_goal_impact"
    EVIDENCE_SUFFICIENCY_QUALITY = "evidence_sufficiency_quality"
    MAGNITUDE_EXPOSURE = "magnitude_exposure"
    RISK_MATERIALITY = "risk_materiality"
    URGENCY_TIMING = "urgency_timing"


class HardTrigger(StrEnum):
    TRACKING_HEALTH_CONFLICT = "tracking_health_conflict"
    GOAL_OR_PRIMARY_CONVERSION_CONFLICT = "goal_or_primary_conversion_conflict"
    OPPOSITE_ACTION_DIRECTION = "opposite_action_direction"
    INCOMPATIBLE_TARGET_SCOPE = "incompatible_target_scope"
    EVIDENCE_ELIGIBILITY_CONFLICT = "evidence_eligibility_conflict"
    ACTION_OUTSIDE_ONTOLOGY = "action_outside_ontology"
    FAILED_GOAL_MOVEMENT = "failed_goal_movement"


class DimensionWeight(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: ComparatorDimension
    weight: float = Field(ge=0, le=1)


class ComparatorProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: str = Field(min_length=1)
    tolerance: float = Field(ge=0, le=1)
    dimensions: tuple[DimensionWeight, ...]
    hard_triggers: tuple[HardTrigger, ...]

    @model_validator(mode="after")
    def validate_dimensions(self) -> "ComparatorProfile":
        names = [item.name for item in self.dimensions]
        if len(names) != len(set(names)):
            raise ValueError("comparator dimensions must be unique")
        if set(names) != set(ComparatorDimension):
            raise ValueError("comparator must define every registered dimension")
        if abs(sum(item.weight for item in self.dimensions) - 1.0) > 1e-12:
            raise ValueError("comparator weights must total 1.0")
        if len(self.hard_triggers) != len(set(self.hard_triggers)):
            raise ValueError("hard triggers must be unique")
        return self

    @property
    def weights(self) -> dict[ComparatorDimension, float]:
        return {item.name: item.weight for item in self.dimensions}


class RequestMateriality(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sufficient_volume: bool
    cpa_deviation: float | None = Field(default=None, ge=0)
    material: bool


class RequestEligibility(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_eligible: bool
    optimization_eligible: bool
    reasons: tuple[str, ...] = ()
    observed_at: datetime
    evidence_age_hours: float = Field(ge=0)
    materiality: RequestMateriality


class TaskPack(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_pack_ref: str = Field(min_length=1)
    action_profile: str = Field(min_length=1)
    allowed_recommendations: frozenset[RecommendationCategory]
    allowed_action_types: frozenset[str]
    non_optimization_action_types: frozenset[str]
    action_directions: dict[str, str]
    opposite_direction_pairs: tuple[tuple[str, str], ...]
    comparator: ComparatorProfile
    max_evidence_age_hours: float = Field(gt=0)
    required_assessment_fields: frozenset[str]
    material_recommendation_categories: frozenset[RecommendationCategory]
    material_action_types: frozenset[str]
    material_risk_levels: frozenset[str]

    @field_validator("allowed_action_types", "allowed_recommendations")
    @classmethod
    def require_values(cls, value: frozenset[object]) -> frozenset[object]:
        if not value:
            raise ValueError("task-pack ontology cannot be empty")
        return value

    @model_validator(mode="after")
    def validate_action_configuration(self) -> "TaskPack":
        if not self.non_optimization_action_types <= self.allowed_action_types:
            raise ValueError("non-optimization actions must belong to the task-pack ontology")
        if set(self.action_directions) != set(self.allowed_action_types):
            raise ValueError("every task-pack action must define a comparison direction")
        if self.comparator.profile != self.task_pack_ref:
            raise ValueError("comparator profile must match task-pack reference")
        if not self.material_action_types <= self.allowed_action_types:
            raise ValueError("material action types must belong to the task-pack ontology")
        if not self.material_recommendation_categories <= self.allowed_recommendations:
            raise ValueError("material categories must belong to the recommendation ontology")
        if not self.material_risk_levels <= {"low", "medium", "high"}:
            raise ValueError("material risk levels are invalid")
        return self

    def revision_document(self) -> dict[str, object]:
        return {
            "task_pack_ref": self.task_pack_ref,
            "action_profile": self.action_profile,
            "allowed_recommendations": sorted(
                value.value for value in self.allowed_recommendations
            ),
            "allowed_action_types": sorted(self.allowed_action_types),
            "non_optimization_action_types": sorted(
                self.non_optimization_action_types
            ),
            "action_directions": dict(sorted(self.action_directions.items())),
            "opposite_direction_pairs": [
                list(pair) for pair in self.opposite_direction_pairs
            ],
            "comparator": self.comparator.model_dump(mode="json"),
            "max_evidence_age_hours": self.max_evidence_age_hours,
            "required_assessment_fields": sorted(self.required_assessment_fields),
            "material_recommendation_categories": sorted(
                value.value for value in self.material_recommendation_categories
            ),
            "material_action_types": sorted(self.material_action_types),
            "material_risk_levels": sorted(self.material_risk_levels),
        }

    @property
    def content_hash(self) -> str:
        encoded = json.dumps(
            self.revision_document(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
