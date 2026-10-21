"""The chimera pack: Conclave configured for marketing ad-performance review.

Deployed by Hyperstructure Marketing. Everything here existed before B2 as
engine code; the pack wraps it behind the ``ReviewPack`` boundary without
changing any decision. The 34 Phase 7 fixtures are the oracle for that claim.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from conclave.contracts.validation import validate_review_result
from conclave.domain.enums import ReviewerSlot, ReviewStage
from conclave.packs.base import (
    OutputKind,
    PackConfig,
    ProviderContract,
    RequestEligibility,
    ReviewPack,
)
from conclave.packs.chimera.comparison import compare_assessments
from conclave.packs.chimera.config import TaskPack
from conclave.packs.chimera.contracts import CONTRACTS
from conclave.packs.chimera.models import (
    Assessment,
    CrossReviewResponse,
    ReviewerCJudgment,
)
from conclave.packs.chimera.registry import (
    TaskPackRegistry,
    default_task_pack_registry,
)
from conclave.packs.chimera.vocabulary import RecommendationCategory
from conclave.packs.comparison import ComparisonResult
from conclave.paths import contracts_root

TASK_PACK_REF = "marketing-ads/v1"

_AUTO_RESOLVE_CATEGORIES = {
    RecommendationCategory.OBSERVE,
    RecommendationCategory.COLLECT_MORE_DATA,
}


class ChimeraPack(ReviewPack):
    pack_id = "chimera"
    task_pack_ref = TASK_PACK_REF

    def __init__(self, registry: TaskPackRegistry | None = None) -> None:
        self._registry = registry or default_task_pack_registry()

    # ------------------------------------------------------------------ identity
    @property
    def registry(self) -> TaskPackRegistry:
        return self._registry

    @property
    def config(self) -> TaskPack:
        return self._registry.get(self.task_pack_ref)

    def config_from_document(self, document: dict[str, Any]) -> TaskPack:
        return TaskPack.model_validate(document)

    # --------------------------------------------------------------------- input
    @property
    def request_schema_path(self) -> Path:
        return contracts_root() / "schemas" / "review-request.v1.schema.json"

    def validate_request(self, document: dict[str, Any]) -> RequestEligibility:
        return self._registry.validate_request(document)

    # ------------------------------------------------------------------- outputs
    @property
    def assessment_type(self) -> type[Assessment]:
        return Assessment

    @property
    def cross_review_type(self) -> type[CrossReviewResponse]:
        return CrossReviewResponse

    @property
    def judgment_type(self) -> type[ReviewerCJudgment]:
        return ReviewerCJudgment

    def output_kind(self, stage: ReviewStage, schema_version: str) -> OutputKind:
        if stage == ReviewStage.JUDGING:
            return "judgment"
        if stage == ReviewStage.CROSS_REVIEW and schema_version == "cross-review-v1":
            return "cross_review"
        return "assessment"

    def assigns_claim_ids(self, schema_version: str) -> bool:
        return schema_version in {"assessment-v2", "cross-review-v1", "reviewer-c-judgment-v2"}

    def judgment_consumes_cross_review_responses(self, schema_version: str) -> bool:
        return schema_version == "reviewer-c-judgment-v2"

    def provider_contract(
        self,
        slot: ReviewerSlot,
        stage: ReviewStage,
        schema_version: str,
    ) -> ProviderContract:
        try:
            return CONTRACTS[(slot, stage, schema_version)]
        except KeyError as exc:
            raise LookupError(
                f"the production contract for reviewer {slot.value} during "
                f"{stage.value} with schema {schema_version!r} is not approved"
            ) from exc

    # ------------------------------------------------ normalization + validation
    def normalize_assessment(
        self,
        document: dict[str, Any],
        assessment: BaseModel,
        *,
        config: PackConfig,
    ) -> Assessment:
        assert isinstance(assessment, Assessment)
        assert isinstance(config, TaskPack)
        return self._registry.normalize_assessment(document, assessment, task_pack=config)

    def normalize_judgment(
        self,
        document: dict[str, Any],
        judgment: BaseModel,
        *,
        config: PackConfig,
    ) -> ReviewerCJudgment:
        assert isinstance(judgment, ReviewerCJudgment)
        assert isinstance(config, TaskPack)
        return self._registry.normalize_judgment(document, judgment, task_pack=config)

    def validate_assessment(
        self,
        document: dict[str, Any],
        assessment: BaseModel,
        *,
        config: PackConfig,
        schema_version: str,
    ) -> None:
        assert isinstance(assessment, Assessment)
        assert isinstance(config, TaskPack)
        self._registry.validate_assessment(
            document,
            assessment,
            task_pack=config,
            schema_version=schema_version,
        )

    def validate_judgment(
        self,
        document: dict[str, Any],
        judgment: BaseModel,
        *,
        config: PackConfig,
        schema_version: str,
        available_claim_ids: frozenset[str],
    ) -> None:
        assert isinstance(judgment, ReviewerCJudgment)
        assert isinstance(config, TaskPack)
        self._registry.validate_judgment(
            document,
            judgment,
            task_pack=config,
            schema_version=schema_version,
            available_claim_ids=available_claim_ids,
        )

    def validate_cross_review(
        self,
        document: dict[str, Any],
        response: BaseModel,
        *,
        peer_claim_ids: frozenset[str],
        config: PackConfig,
    ) -> None:
        assert isinstance(response, CrossReviewResponse)
        assert isinstance(config, TaskPack)
        self._registry.validate_cross_review(
            document,
            response,
            peer_claim_ids=peer_claim_ids,
            task_pack=config,
        )

    # ----------------------------------------------------------------- deciding
    def compare(
        self,
        left: BaseModel,
        right: BaseModel,
        *,
        config: PackConfig,
        failed_goal: bool = False,
    ) -> ComparisonResult:
        assert isinstance(left, Assessment) and isinstance(right, Assessment)
        assert isinstance(config, TaskPack)
        return compare_assessments(left, right, config, failed_goal=failed_goal)

    def recommendation_material(self, assessment: BaseModel, *, config: PackConfig) -> bool:
        assert isinstance(assessment, Assessment)
        assert isinstance(config, TaskPack)
        return bool(
            assessment.category in config.material_recommendation_categories
            or assessment.risk in config.material_risk_levels
            or any(
                action.type in config.material_action_types for action in assessment.actions
            )
        )

    def can_auto_resolve(self, final: BaseModel) -> bool:
        assert isinstance(final, Assessment)
        return (
            final.category in _AUTO_RESOLVE_CATEGORIES
            and not final.actions
            and not final.material
            and final.risk == "low"
        )

    # ------------------------------------------------------------------- result
    @property
    def result_schema_path(self) -> Path:
        return contracts_root() / "schemas" / "review-result.v1.schema.json"

    def recommendation_document(self, final: BaseModel) -> dict[str, Any]:
        assert isinstance(final, Assessment)
        return {
            "category": final.category.value,
            "summary": final.summary,
            "actions": [
                action.model_dump(mode="json", exclude_none=False) for action in final.actions
            ],
            "experiment": (
                final.experiment.model_dump(mode="json")
                if final.experiment is not None
                else None
            ),
        }

    def result_extensions(self, final: BaseModel) -> dict[str, Any]:
        assert isinstance(final, Assessment)
        return {"review_after_hours": final.review_after_hours}

    @property
    def result_extension_keys(self) -> tuple[str, ...]:
        return ("review_after_hours",)

    def validate_result(self, document: dict[str, Any], request: dict[str, Any]) -> None:
        validate_review_result(document, request)


def chimera_pack() -> ChimeraPack:
    return ChimeraPack()
