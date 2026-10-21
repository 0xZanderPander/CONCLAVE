"""The cerberus pack: Conclave configured for venture-submission assessment.

Deployed by VORAGO as its idea gate. Three seats blind-assess a founder's
submission against a six-dimension rubric, cross-review, and a judge breaks
surviving disagreement; the caller receives one verdict with written feedback
and owns the decision. No consumer vocabulary crosses into the engine.
"""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, FormatChecker
from pydantic import BaseModel

from conclave.contracts.errors import ContractValidationError
from conclave.domain.enums import ReviewerSlot, ReviewStage
from conclave.packs.base import (
    OutputKind,
    PackConfig,
    ProviderContract,
    RequestEligibility,
    ReviewPack,
)
from conclave.packs.cerberus import rules
from conclave.packs.cerberus.comparison import compare_venture_assessments
from conclave.packs.cerberus.config import TASK_PACK_REF, VenturePackConfig, default_config
from conclave.packs.cerberus.contracts import (
    ASSESSMENT_SCHEMA,
    CONTRACTS,
    CROSS_REVIEW_SCHEMA,
    JUDGMENT_SCHEMA,
)
from conclave.packs.cerberus.models import (
    VentureAssessment,
    VentureCrossReviewResponse,
    VentureJudgment,
)
from conclave.packs.comparison import ComparisonResult

CONTRACTS_ROOT = Path(__file__).resolve().parent / "contracts"


def contracts_root() -> Path:
    return CONTRACTS_ROOT


def load_request_fixture(name: str = "01-idea-stage.json") -> dict[str, Any]:
    path = CONTRACTS_ROOT / "fixtures" / "request" / Path(name).name
    with path.open(encoding="utf-8") as source:
        return json.load(source)


class CerberusPack(ReviewPack):
    pack_id = "cerberus"
    task_pack_ref = TASK_PACK_REF

    def __init__(self, config: VenturePackConfig | None = None) -> None:
        self._config = config or default_config()
        with self.result_schema_path.open(encoding="utf-8") as source:
            schema = json.load(source)
        Draft7Validator.check_schema(schema)
        self._result_validator = Draft7Validator(schema, format_checker=FormatChecker())

    # ------------------------------------------------------------------ identity
    @property
    def config(self) -> VenturePackConfig:
        return self._config

    def config_from_document(self, document: dict[str, Any]) -> VenturePackConfig:
        return VenturePackConfig.model_validate(document)

    # --------------------------------------------------------------------- input
    @property
    def request_schema_path(self) -> Path:
        return CONTRACTS_ROOT / "schemas" / "venture-submission.v1.schema.json"

    def validate_request(self, document: dict[str, Any]) -> RequestEligibility:
        rules.validate_binding(self._config, document)
        return rules.evaluate_eligibility(self._config, document)

    # ------------------------------------------------------------------- outputs
    @property
    def assessment_type(self) -> type[VentureAssessment]:
        return VentureAssessment

    @property
    def cross_review_type(self) -> type[VentureCrossReviewResponse]:
        return VentureCrossReviewResponse

    @property
    def judgment_type(self) -> type[VentureJudgment]:
        return VentureJudgment

    def output_kind(self, stage: ReviewStage, schema_version: str) -> OutputKind:
        if stage == ReviewStage.JUDGING:
            return "judgment"
        if stage == ReviewStage.CROSS_REVIEW:
            return "cross_review"
        return "assessment"

    def assigns_claim_ids(self, schema_version: str) -> bool:
        return schema_version in {ASSESSMENT_SCHEMA, CROSS_REVIEW_SCHEMA, JUDGMENT_SCHEMA}

    def judgment_consumes_cross_review_responses(self, schema_version: str) -> bool:
        return schema_version == JUDGMENT_SCHEMA

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
                f"the cerberus contract for seat {slot.value} during {stage.value} "
                f"with schema {schema_version!r} is not approved"
            ) from exc

    # ------------------------------------------------ normalization + validation
    def normalize_assessment(
        self,
        document: dict[str, Any],
        assessment: BaseModel,
        *,
        config: PackConfig,
    ) -> VentureAssessment:
        assert isinstance(assessment, VentureAssessment)
        return rules.normalize_assessment(assessment)

    def normalize_judgment(
        self,
        document: dict[str, Any],
        judgment: BaseModel,
        *,
        config: PackConfig,
    ) -> VentureJudgment:
        assert isinstance(judgment, VentureJudgment)
        return rules.normalize_judgment(judgment)

    def validate_assessment(
        self,
        document: dict[str, Any],
        assessment: BaseModel,
        *,
        config: PackConfig,
        schema_version: str,
    ) -> None:
        assert isinstance(assessment, VentureAssessment)
        assert isinstance(config, VenturePackConfig)
        rules.validate_assessment(config, document, assessment)

    def validate_judgment(
        self,
        document: dict[str, Any],
        judgment: BaseModel,
        *,
        config: PackConfig,
        schema_version: str,
        available_claim_ids: frozenset[str],
    ) -> None:
        assert isinstance(judgment, VentureJudgment)
        assert isinstance(config, VenturePackConfig)
        rules.validate_judgment(
            config, document, judgment, available_claim_ids=available_claim_ids
        )

    def validate_cross_review(
        self,
        document: dict[str, Any],
        response: BaseModel,
        *,
        peer_claim_ids: frozenset[str],
        config: PackConfig,
    ) -> None:
        assert isinstance(response, VentureCrossReviewResponse)
        assert isinstance(config, VenturePackConfig)
        rules.validate_cross_review(config, document, response, peer_claim_ids=peer_claim_ids)

    # ----------------------------------------------------------------- deciding
    def compare(
        self,
        left: BaseModel,
        right: BaseModel,
        *,
        config: PackConfig,
        failed_goal: bool = False,
    ) -> ComparisonResult:
        assert isinstance(left, VentureAssessment) and isinstance(right, VentureAssessment)
        assert isinstance(config, VenturePackConfig)
        return compare_venture_assessments(left, right, config)

    def recommendation_material(self, assessment: BaseModel, *, config: PackConfig) -> bool:
        return True

    def can_auto_resolve(self, final: BaseModel) -> bool:
        # The caller owns every venture decision; nothing resolves without it.
        return False

    # ------------------------------------------------------------------- result
    @property
    def result_contract_version(self) -> str:
        return "venture-verdict/v1"

    @property
    def result_schema_path(self) -> Path:
        return CONTRACTS_ROOT / "schemas" / "venture-verdict.v1.schema.json"

    def recommendation_document(self, final: BaseModel) -> dict[str, Any]:
        assert isinstance(final, VentureAssessment)
        return {
            "category": final.category.value,
            "summary": final.summary,
            "feedback": final.feedback,
            "scores": final.scores.model_dump(mode="json"),
            "strengths": list(final.strengths),
            "weaknesses": list(final.weaknesses),
        }

    def result_extensions(self, final: BaseModel) -> dict[str, Any]:
        return {}

    def validate_result(self, document: dict[str, Any], request: dict[str, Any]) -> None:
        errors = sorted(self._result_validator.iter_errors(document), key=lambda e: list(e.path))
        if errors:
            messages = []
            for error in errors:
                location = ".".join(str(part) for part in error.path) or "$"
                messages.append(f"{location}: {error.message}")
            raise ContractValidationError("\n".join(messages))
        if document["request_idempotency_key"] != request["idempotency_key"]:
            raise ContractValidationError("venture verdict: idempotency correlation does not match")
        if document["occurrence_id"] != request["review_trigger"]["occurrence_id"]:
            raise ContractValidationError("venture verdict: occurrence correlation does not match")
        if document["recommendation"]["category"] not in request["allowed_recommendations"]:
            raise ContractValidationError("venture verdict: category is not allowed")
        if document["status"] == "auto_resolved":
            raise ContractValidationError("venture verdict: a venture verdict cannot auto-resolve")
        if document["disagreement"]["level"] == "tie_broken":
            reviewers = document["panel_metadata"]["reviewers"]
            independent = [
                index
                for index, reviewer in enumerate(reviewers)
                if reviewer["slot"] == "C" and reviewer["stage"] == "independent"
            ]
            judging = [
                index
                for index, reviewer in enumerate(reviewers)
                if reviewer["slot"] == "C" and reviewer["stage"] == "judging"
            ]
            if not independent or not judging or min(independent) >= min(judging):
                raise ContractValidationError("venture verdict: invalid judge ordering")


def cerberus_pack() -> CerberusPack:
    return CerberusPack()
