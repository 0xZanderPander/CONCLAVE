"""The pack boundary.

Conclave is one engine deployed in several configurations. Everything that is
*domain-shaped* — what a reviewer may hand back, how two reviewers' answers are
compared, what counts as material, which categories exist, the seat prompts,
the input contract and the result contract — lives in a pack. Everything that
is not — the three-seat protocol, blind isolation, the ledger, the state
machine, provider adapters, the audit verifier, cost telemetry — lives in the
engine and calls through this interface.

Packs today:

- ``chimera`` — marketing ad-performance review (Hyperstructure Marketing).
- ``cerberus`` — venture-submission assessment (VORAGO).

A pack never learns about its caller. No consumer vocabulary crosses into the
engine through this boundary.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from conclave.domain.enums import ReviewerSlot, ReviewStage
from conclave.packs.comparison import ComparisonResult

OutputKind = Literal["assessment", "cross_review", "judgment"]


@runtime_checkable
class PackConfig(Protocol):
    """Pinned, content-hashed pack configuration.

    The hash is recorded on every session so a later configuration change
    never mutates open work. Chimera's ``TaskPack`` is one implementation.
    """

    @property
    def task_pack_ref(self) -> str: ...

    @property
    def content_hash(self) -> str: ...

    def revision_document(self) -> dict[str, object]: ...


class RequestMateriality(BaseModel):
    """Deterministic request-level materiality computed at intake.

    ``sufficient_volume`` and ``cpa_deviation`` are recorded in the
    ``request_validated`` ledger event for every pack; a pack without a volume
    or deviation concept reports ``True`` and ``None``.
    """

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


@dataclass(frozen=True, slots=True)
class ProviderContract:
    """What a model provider is allowed to be asked for one seat and stage."""

    role_version: str
    prompt_version: str
    schema_version: str
    instructions: str
    output_model: type[BaseModel]
    format_name: str


class ReviewPack(ABC):
    """One deployable configuration of the Conclave engine."""

    # ------------------------------------------------------------------ identity
    pack_id: str
    task_pack_ref: str

    @property
    @abstractmethod
    def config(self) -> PackConfig:
        """The current registered configuration for this pack."""

    @abstractmethod
    def config_from_document(self, document: dict[str, Any]) -> PackConfig:
        """Rehydrate a pinned configuration from its ledger revision document."""

    # --------------------------------------------------------------------- input
    @property
    @abstractmethod
    def request_schema_path(self) -> Path:
        """JSON schema the input object must satisfy before anything else runs."""

    @abstractmethod
    def validate_request(self, document: dict[str, Any]) -> RequestEligibility:
        """Pack-level checks after the schema passes: binding, eligibility, materiality."""

    # ------------------------------------------------------------------- outputs
    @property
    @abstractmethod
    def assessment_type(self) -> type[BaseModel]: ...

    @property
    @abstractmethod
    def cross_review_type(self) -> type[BaseModel]: ...

    @property
    @abstractmethod
    def judgment_type(self) -> type[BaseModel]: ...

    @abstractmethod
    def output_kind(self, stage: ReviewStage, schema_version: str) -> OutputKind:
        """Which output shape a seat returns for this stage and schema version."""

    def parse_output(
        self,
        stage: ReviewStage,
        schema_version: str,
        payload: Any,
    ) -> BaseModel:
        kind = self.output_kind(stage, schema_version)
        if kind == "judgment":
            return self.judgment_type.model_validate(payload)
        if kind == "cross_review":
            return self.cross_review_type.model_validate(payload)
        return self.assessment_type.model_validate(payload)

    def assessment_from_output(self, output: BaseModel) -> BaseModel:
        """The assessment carried by an assessment or cross-review output."""

        if isinstance(output, self.cross_review_type):
            return output.assessment  # type: ignore[attr-defined]
        if isinstance(output, self.assessment_type):
            return output
        raise TypeError("output does not carry an assessment")

    @abstractmethod
    def assigns_claim_ids(self, schema_version: str) -> bool:
        """Whether this schema version carries structured claims Conclave must ID."""

    @abstractmethod
    def judgment_consumes_cross_review_responses(self, schema_version: str) -> bool:
        """Whether the judge seat receives A and B's full cross-review responses."""

    @abstractmethod
    def provider_contract(
        self,
        slot: ReviewerSlot,
        stage: ReviewStage,
        schema_version: str,
    ) -> ProviderContract:
        """Approved instructions and output model for a seat at a stage."""

    # ------------------------------------------------ normalization + validation
    @abstractmethod
    def normalize_assessment(
        self,
        document: dict[str, Any],
        assessment: BaseModel,
        *,
        config: PackConfig,
    ) -> BaseModel: ...

    @abstractmethod
    def normalize_judgment(
        self,
        document: dict[str, Any],
        judgment: BaseModel,
        *,
        config: PackConfig,
    ) -> BaseModel: ...

    @abstractmethod
    def validate_assessment(
        self,
        document: dict[str, Any],
        assessment: BaseModel,
        *,
        config: PackConfig,
        schema_version: str,
    ) -> None: ...

    @abstractmethod
    def validate_judgment(
        self,
        document: dict[str, Any],
        judgment: BaseModel,
        *,
        config: PackConfig,
        schema_version: str,
        available_claim_ids: frozenset[str],
    ) -> None: ...

    @abstractmethod
    def validate_cross_review(
        self,
        document: dict[str, Any],
        response: BaseModel,
        *,
        peer_claim_ids: frozenset[str],
        config: PackConfig,
    ) -> None: ...

    # ----------------------------------------------------------------- deciding
    @abstractmethod
    def compare(
        self,
        left: BaseModel,
        right: BaseModel,
        *,
        config: PackConfig,
        failed_goal: bool = False,
    ) -> ComparisonResult: ...

    @abstractmethod
    def recommendation_material(self, assessment: BaseModel, *, config: PackConfig) -> bool:
        """Whether a seat's recommendation is material under this pack's rules."""

    @abstractmethod
    def can_auto_resolve(self, final: BaseModel) -> bool:
        """Domain half of the auto-resolve rule; the engine adds path and panel checks."""

    # ------------------------------------------------------------------- result
    @property
    @abstractmethod
    def result_contract_version(self) -> str:
        """``contract_version`` stamped on every result document of this pack."""

    @property
    @abstractmethod
    def result_schema_path(self) -> Path: ...

    @abstractmethod
    def recommendation_document(self, final: BaseModel) -> dict[str, Any]:
        """The ``recommendation`` block of the result document."""

    @abstractmethod
    def result_extensions(self, final: BaseModel) -> dict[str, Any]:
        """Pack-specific top-level result fields appended after the engine envelope."""

    @abstractmethod
    def validate_result(self, document: dict[str, Any], request: dict[str, Any]) -> None:
        """Schema plus pack-level request/result pairing rules."""

    def assessment_projection(self, assessment: BaseModel) -> dict[str, Any]:
        """Baseline projection the evaluation loop fingerprints against the result."""

        from conclave.packs.claims import public_claim

        projection: dict[str, Any] = {
            "recommendation": self.recommendation_document(assessment),
            "claims": [public_claim(claim) for claim in assessment.claims],  # type: ignore[attr-defined]
            "confidence": assessment.confidence,  # type: ignore[attr-defined]
            "evidence_quality": assessment.evidence_quality,  # type: ignore[attr-defined]
            "risk": assessment.risk,  # type: ignore[attr-defined]
            "missing_evidence": list(assessment.missing_evidence),  # type: ignore[attr-defined]
        }
        projection.update(self.result_extensions(assessment))
        return projection

    def result_projection(self, result: dict[str, Any]) -> dict[str, Any]:
        """Final-result projection matching ``assessment_projection``'s shape."""

        projection: dict[str, Any] = {
            "recommendation": result["recommendation"],
            "claims": result["claims"],
            "confidence": result["confidence"],
            "evidence_quality": result["evidence_quality"],
            "risk": result["risk"],
            "missing_evidence": result.get("missing_evidence", []),
        }
        for key in self.result_extension_keys:
            projection[key] = result.get(key)
        return projection

    @property
    def result_extension_keys(self) -> tuple[str, ...]:
        return ()
