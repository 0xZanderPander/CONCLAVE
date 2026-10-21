"""Cerberus pack configuration: pinned, content-hashed, recorded per session."""

import hashlib
import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from conclave.packs.cerberus.vocabulary import VentureVerdict

TASK_PACK_REF = "venture-submission/v1"


class VentureComparatorDimension(StrEnum):
    VERDICT_DISPOSITION = "verdict_disposition"
    SCORE_PROFILE = "score_profile"
    RISK_MATERIALITY = "risk_materiality"
    EVIDENCE_SUFFICIENCY_QUALITY = "evidence_sufficiency_quality"


class VentureHardTrigger(StrEnum):
    VERDICT_POLARITY_CONFLICT = "verdict_polarity_conflict"
    EXTREME_SCORE_DIVERGENCE = "extreme_score_divergence"


class VentureComparator(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: str = Field(min_length=1)
    tolerance: float = Field(ge=0, le=1)
    weights: dict[VentureComparatorDimension, float]
    hard_triggers: tuple[VentureHardTrigger, ...]
    extreme_score_gap: int = Field(ge=1, le=4)

    @model_validator(mode="after")
    def validate_weights(self) -> "VentureComparator":
        if set(self.weights) != set(VentureComparatorDimension):
            raise ValueError("comparator must weight every registered dimension")
        if abs(sum(self.weights.values()) - 1.0) > 1e-12:
            raise ValueError("comparator weights must total 1.0")
        if len(self.hard_triggers) != len(set(self.hard_triggers)):
            raise ValueError("hard triggers must be unique")
        return self


class VenturePackConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_pack_ref: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    allowed_verdicts: frozenset[VentureVerdict]
    comparator: VentureComparator
    min_total_words: int = Field(ge=1)
    max_submission_age_hours: float = Field(gt=0)
    max_feedback_words: int = Field(ge=50)

    @model_validator(mode="after")
    def validate_binding(self) -> "VenturePackConfig":
        if self.comparator.profile != self.task_pack_ref:
            raise ValueError("comparator profile must match task-pack reference")
        if not self.allowed_verdicts:
            raise ValueError("pack must allow at least one verdict")
        return self

    def revision_document(self) -> dict[str, object]:
        return {
            "task_pack_ref": self.task_pack_ref,
            "rubric_version": self.rubric_version,
            "allowed_verdicts": sorted(value.value for value in self.allowed_verdicts),
            "comparator": {
                "profile": self.comparator.profile,
                "tolerance": self.comparator.tolerance,
                "weights": {
                    key.value: value for key, value in sorted(self.comparator.weights.items())
                },
                "hard_triggers": [trigger.value for trigger in self.comparator.hard_triggers],
                "extreme_score_gap": self.comparator.extreme_score_gap,
            },
            "min_total_words": self.min_total_words,
            "max_submission_age_hours": self.max_submission_age_hours,
            "max_feedback_words": self.max_feedback_words,
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


def default_config() -> VenturePackConfig:
    return VenturePackConfig(
        task_pack_ref=TASK_PACK_REF,
        rubric_version="venture-rubric/v1",
        allowed_verdicts=frozenset(VentureVerdict),
        comparator=VentureComparator(
            profile=TASK_PACK_REF,
            tolerance=0.25,
            weights={
                VentureComparatorDimension.VERDICT_DISPOSITION: 0.4,
                VentureComparatorDimension.SCORE_PROFILE: 0.3,
                VentureComparatorDimension.RISK_MATERIALITY: 0.15,
                VentureComparatorDimension.EVIDENCE_SUFFICIENCY_QUALITY: 0.15,
            },
            hard_triggers=(
                VentureHardTrigger.VERDICT_POLARITY_CONFLICT,
                VentureHardTrigger.EXTREME_SCORE_DIVERGENCE,
            ),
            extreme_score_gap=3,
        ),
        min_total_words=40,
        max_submission_age_hours=24 * 90,
        max_feedback_words=600,
    )
