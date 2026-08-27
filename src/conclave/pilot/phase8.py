import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, ClassVar, Literal, Self, TypeVar
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

Sha256 = str
Phase8CaseKind = Literal["provider_eligible", "no_call_control"]
Phase8SourceKind = Literal["real_event", "historical_replay"]
Phase8ControlType = Literal[
    "stale_package",
    "invalid_contract",
    "duplicate_replay",
    "unapproved_provider",
]
Phase8Route = Literal[
    "a_only",
    "ab_agreement",
    "cross_review_resolved",
    "c_tie_broken",
]
Phase8Disposition = Literal[
    "provider_call_allowed",
    "stop_stale",
    "stop_invalid_contract",
    "stop_duplicate",
    "stop_unapproved_provider",
]
Phase8StageId = Literal[
    "reviewer_a_independent",
    "reviewer_b_independent",
    "reviewer_a_cross_review",
    "reviewer_b_cross_review",
    "reviewer_c_blind_assessment",
    "reviewer_c_judgment",
]

_SHA256_PATTERN = r"^sha256:[a-f0-9]{64}$"
_CASE_ID_PATTERN = r"^p8c_[a-f0-9]{16}$"
_EVIDENCE_VERSION_PATTERN = r"^p8ev_[a-f0-9]{16}$"
_ZERO_HASH = f"sha256:{'0' * 64}"


def phase8_content_hash(value: Any) -> Sha256:
    """Hash a JSON-compatible Phase 8 artifact using Conclave's canonical encoding."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _require_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class Phase8Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


_HashedArtifactT = TypeVar("_HashedArtifactT", bound="Phase8HashedArtifact")


class Phase8HashedArtifact(Phase8Model):
    """Base for immutable artifacts whose declared hash excludes only itself."""

    hash_field: ClassVar[str]

    @model_validator(mode="after")
    def validate_declared_hash(self, info: ValidationInfo) -> Self:
        if info.context and info.context.get("skip_phase8_hash_validation"):
            return self
        declared = getattr(self, self.hash_field)
        payload = self.model_dump(mode="json", exclude={self.hash_field})
        expected = phase8_content_hash(payload)
        if declared != expected:
            raise ValueError(f"{self.hash_field} does not match the canonical artifact content")
        return self

    @classmethod
    def seal(cls: type[_HashedArtifactT], **values: Any) -> _HashedArtifactT:
        """Validate, normalize, hash, and return an immutable artifact."""

        values.pop(cls.hash_field, None)
        draft = cls.model_validate(
            {**values, cls.hash_field: _ZERO_HASH},
            context={"skip_phase8_hash_validation": True},
        )
        normalized = draft.model_dump(mode="json", exclude={cls.hash_field})
        return cls.model_validate(
            {
                **normalized,
                cls.hash_field: phase8_content_hash(normalized),
            }
        )


class Phase8RedactionChecklist(Phase8Model):
    personal_data_removed: Literal[True]
    credentials_and_tokens_removed: Literal[True]
    direct_contact_details_removed: Literal[True]
    customer_identifiers_removed: Literal[True]
    raw_message_content_removed: Literal[True]
    unnecessary_free_text_removed: Literal[True]
    business_identifiers_opaque: Literal[True]
    timestamps_shifted_when_exact_dates_unneeded: Literal[True]
    sensitive_values_normalized_when_exact_values_unneeded: Literal[True]
    redaction_map_stored_outside_conclave: Literal[True]


class Phase8RedactionAttestation(Phase8HashedArtifact):
    hash_field = "attestation_hash"

    contract_version: Literal["phase8-redaction-attestation/v1"]
    attestation_id: str = Field(min_length=1, max_length=100)
    case_id: str = Field(pattern=_CASE_ID_PATTERN)
    reviewed_at: datetime
    reviewer_ids: tuple[str, str]
    checklist: Phase8RedactionChecklist
    attestation_hash: Sha256 = Field(pattern=_SHA256_PATTERN)

    @field_validator("reviewed_at")
    @classmethod
    def reviewed_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "reviewed_at")

    @field_validator("reviewer_ids")
    @classmethod
    def reviewers_are_distinct(cls, value: tuple[str, str]) -> tuple[str, str]:
        if len(set(value)) != 2:
            raise ValueError("redaction requires two distinct human reviewers")
        if any(not reviewer.strip() for reviewer in value):
            raise ValueError("redaction reviewer IDs cannot be blank")
        return value


class Phase8BaselinePackage(Phase8HashedArtifact):
    hash_field = "baseline_hash"

    contract_version: Literal["phase8-baseline/v1"]
    captured_at: datetime
    captured_before_panel_output: Literal[True]
    reviewer_kind: Literal["single_reviewer"]
    assessment: dict[str, Any]
    baseline_hash: Sha256 = Field(pattern=_SHA256_PATTERN)

    @field_validator("captured_at")
    @classmethod
    def captured_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "captured_at")

    @field_validator("assessment")
    @classmethod
    def assessment_is_not_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("the captured baseline assessment cannot be empty")
        return value


class Phase8EvidenceQuality(Phase8Model):
    label: Literal["strong", "adequate", "weak", "insufficient"]
    is_partial: bool
    tracking_health: Literal["healthy", "degraded", "unhealthy", "unknown"]
    known_gaps: tuple[str, ...] = ()

    @model_validator(mode="after")
    def weak_case_is_identifiable(self) -> Self:
        if (
            self.label in {"weak", "insufficient"}
            or self.is_partial
            or self.tracking_health in {"degraded", "unhealthy", "unknown"}
        ):
            return self
        if self.known_gaps:
            raise ValueError("healthy adequate evidence cannot declare unresolved gaps")
        return self

    @property
    def is_weak_partial_or_tracking_unhealthy(self) -> bool:
        return (
            self.label in {"weak", "insufficient"}
            or self.is_partial
            or self.tracking_health in {"degraded", "unhealthy", "unknown"}
        )


class Phase8RoutingProfile(Phase8Model):
    expected_route: Phase8Route | None
    request_material: bool
    prior_recommendation_material: bool
    prior_reviewers_disagreed: bool
    baseline_observe_or_no_change: bool
    reviewed_by: str = Field(min_length=1, max_length=100)
    reviewed_at: datetime

    @field_validator("reviewed_at")
    @classmethod
    def reviewed_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "reviewed_at")

    @property
    def materially_eligible(self) -> bool:
        return self.request_material or self.prior_recommendation_material


class Phase8OutcomePackage(Phase8HashedArtifact):
    hash_field = "outcome_hash"

    contract_version: Literal["phase8-outcome/v1"]
    decision_ref: str = Field(min_length=1, max_length=200)
    outcome_ref: str = Field(min_length=1, max_length=200)
    caller_decision: Literal[
        "accepted",
        "modified",
        "rejected",
        "deferred",
        "no_action",
    ]
    outcome_classification: Literal[
        "beneficial",
        "harmful",
        "no_effect",
        "mixed",
        "inconclusive",
    ]
    outcome_evidence_quality: Literal[
        "strong",
        "adequate",
        "weak",
        "insufficient",
    ]
    known_confounders: tuple[str, ...]
    evaluated_at: datetime
    attached_only_after_panel_recommendation_frozen: Literal[True]
    outcome_hash: Sha256 = Field(pattern=_SHA256_PATTERN)

    @field_validator("evaluated_at")
    @classmethod
    def evaluated_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "evaluated_at")


class Phase8VersionPins(Phase8Model):
    task_pack_id: str = Field(min_length=1, max_length=200)
    task_pack_revision: str = Field(min_length=1, max_length=100)
    task_pack_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    plan_id: str = Field(min_length=1, max_length=200)
    plan_revision: int = Field(ge=1)
    plan_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    prompt_bundle_version: str = Field(min_length=1, max_length=100)
    role_bundle_version: str = Field(min_length=1, max_length=100)
    schema_bundle_version: str = Field(min_length=1, max_length=100)


class Phase8SourceProvenance(Phase8Model):
    """Human-attested proof that a package is real or historically replayed."""

    source_kind: Phase8SourceKind
    source_record_ref: str = Field(pattern=r"^p8src_[a-f0-9]{16}$")
    source_snapshot_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    verified_at: datetime
    verified_by: str = Field(min_length=1, max_length=100)
    redacted_snapshot_derived_from_source: Literal[True]
    synthetic_data: Literal[False]

    @field_validator("verified_at")
    @classmethod
    def verified_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "verified_at")


class Phase8CasePackage(Phase8HashedArtifact):
    hash_field = "case_package_hash"

    contract_version: Literal["phase8-case-package/v1"]
    case_id: str = Field(pattern=_CASE_ID_PATTERN)
    evidence_version: str = Field(pattern=_EVIDENCE_VERSION_PATTERN)
    case_kind: Phase8CaseKind
    control_type: Phase8ControlType | None = None
    expected_disposition: Phase8Disposition
    request_contract_valid: bool
    request_snapshot: dict[str, Any]
    request_snapshot_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    source_provenance: Phase8SourceProvenance
    baseline: Phase8BaselinePackage | None = None
    routing_profile: Phase8RoutingProfile
    redaction_attestation: Phase8RedactionAttestation
    evidence_quality: Phase8EvidenceQuality
    outcome_package: Phase8OutcomePackage | None = None
    version_pins: Phase8VersionPins | None = None
    duplicate_of_case_id: str | None = Field(default=None, pattern=_CASE_ID_PATTERN)
    requested_provider: str | None = Field(default=None, min_length=1, max_length=100)
    case_package_hash: Sha256 = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_case_shape(self) -> Self:
        if phase8_content_hash(self.request_snapshot) != self.request_snapshot_hash:
            raise ValueError("request_snapshot_hash does not match request_snapshot")
        if self.request_snapshot.get("evidence_version") != self.evidence_version:
            raise ValueError("case evidence_version must match the immutable request snapshot")
        if self.redaction_attestation.case_id != self.case_id:
            raise ValueError("redaction attestation belongs to a different case")

        if self.case_kind == "provider_eligible":
            if self.control_type is not None:
                raise ValueError("provider-eligible cases cannot declare a control type")
            if self.expected_disposition != "provider_call_allowed":
                raise ValueError("provider-eligible cases must allow the approved provider call")
            if not self.request_contract_valid:
                raise ValueError("provider-eligible cases require a contract-valid request")
            if self.baseline is None or self.version_pins is None:
                raise ValueError(
                    "provider-eligible cases require a baseline and exact version pins"
                )
            if self.routing_profile.expected_route is None:
                raise ValueError("provider-eligible cases require an expected route")
            if self.duplicate_of_case_id is not None or self.requested_provider is not None:
                raise ValueError("provider-eligible cases cannot declare control-only fields")
            return self

        if self.control_type is None:
            raise ValueError("no-call controls require a control type")
        expected = {
            "stale_package": "stop_stale",
            "invalid_contract": "stop_invalid_contract",
            "duplicate_replay": "stop_duplicate",
            "unapproved_provider": "stop_unapproved_provider",
        }[self.control_type]
        if self.expected_disposition != expected:
            raise ValueError("the control type and expected disposition do not match")
        if self.routing_profile.expected_route is not None:
            raise ValueError("no-call controls cannot declare a provider route")
        if self.control_type == "invalid_contract" and self.request_contract_valid:
            raise ValueError("the invalid-contract control must be marked contract-invalid")
        if self.control_type != "invalid_contract" and not self.request_contract_valid:
            raise ValueError("only the invalid-contract control may be contract-invalid")
        if self.control_type == "duplicate_replay" and self.duplicate_of_case_id is None:
            raise ValueError("the duplicate control must identify its original case")
        if self.control_type != "duplicate_replay" and self.duplicate_of_case_id is not None:
            raise ValueError("only the duplicate control may identify an original case")
        if self.control_type == "unapproved_provider" and self.requested_provider is None:
            raise ValueError("the provider control must name the unapproved provider")
        if self.control_type != "unapproved_provider" and self.requested_provider is not None:
            raise ValueError("only the provider control may request a provider")
        return self

    @property
    def outcome_linked(self) -> bool:
        return self.outcome_package is not None


class Phase8CohortCase(Phase8Model):
    case_id: str = Field(pattern=_CASE_ID_PATTERN)
    evidence_version: str = Field(pattern=_EVIDENCE_VERSION_PATTERN)
    case_kind: Phase8CaseKind
    control_type: Phase8ControlType | None
    case_package_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    request_snapshot_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    baseline_hash: Sha256 | None = Field(default=None, pattern=_SHA256_PATTERN)
    outcome_hash: Sha256 | None = Field(default=None, pattern=_SHA256_PATTERN)
    outcome_linked: bool
    materially_eligible: bool
    weak_partial_or_tracking_unhealthy: bool
    prior_reviewers_disagreed: bool
    baseline_observe_or_no_change: bool

    @model_validator(mode="after")
    def validate_index_entry_shape(self) -> Self:
        if self.outcome_linked != (self.outcome_hash is not None):
            raise ValueError("outcome-linked flag must match the frozen outcome hash")
        if self.case_kind == "provider_eligible":
            if self.control_type is not None or self.baseline_hash is None:
                raise ValueError("eligible cohort entries require a baseline and no control type")
        elif self.control_type is None:
            raise ValueError("no-call cohort entries require a control type")
        return self

    @classmethod
    def from_case_package(cls, case: Phase8CasePackage) -> Self:
        return cls(
            case_id=case.case_id,
            evidence_version=case.evidence_version,
            case_kind=case.case_kind,
            control_type=case.control_type,
            case_package_hash=case.case_package_hash,
            request_snapshot_hash=case.request_snapshot_hash,
            baseline_hash=case.baseline.baseline_hash if case.baseline else None,
            outcome_hash=(case.outcome_package.outcome_hash if case.outcome_package else None),
            outcome_linked=case.outcome_linked,
            materially_eligible=case.routing_profile.materially_eligible,
            weak_partial_or_tracking_unhealthy=(
                case.evidence_quality.is_weak_partial_or_tracking_unhealthy
            ),
            prior_reviewers_disagreed=case.routing_profile.prior_reviewers_disagreed,
            baseline_observe_or_no_change=(case.routing_profile.baseline_observe_or_no_change),
        )


class Phase8CohortManifest(Phase8HashedArtifact):
    hash_field = "cohort_hash"

    contract_version: Literal["phase8-cohort-manifest/v1"]
    cohort_id: str = Field(min_length=1, max_length=100)
    revision: int = Field(ge=1)
    frozen_at: datetime
    cases: tuple[Phase8CohortCase, ...] = Field(min_length=24, max_length=24)
    cohort_hash: Sha256 = Field(pattern=_SHA256_PATTERN)

    @field_validator("frozen_at")
    @classmethod
    def frozen_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "frozen_at")

    @model_validator(mode="after")
    def validate_locked_cohort(self) -> Self:
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Phase 8 case IDs must be unique")
        eligible = [case for case in self.cases if case.case_kind == "provider_eligible"]
        controls = [case for case in self.cases if case.case_kind == "no_call_control"]
        if len(eligible) != 20 or len(controls) != 4:
            raise ValueError("Phase 8 requires exactly 20 eligible cases and four controls")
        control_counts = {
            control_type: sum(case.control_type == control_type for case in controls)
            for control_type in (
                "stale_package",
                "invalid_contract",
                "duplicate_replay",
                "unapproved_provider",
            )
        }
        if any(count != 1 for count in control_counts.values()):
            raise ValueError("Phase 8 requires exactly one control of each required type")

        coverage = {
            "outcome-linked": sum(case.outcome_linked for case in eligible),
            "material": sum(case.materially_eligible for case in eligible),
            "weak/partial/tracking": sum(
                case.weak_partial_or_tracking_unhealthy for case in eligible
            ),
            "prior disagreement": sum(case.prior_reviewers_disagreed for case in eligible),
            "observe/no-change baseline": sum(
                case.baseline_observe_or_no_change for case in eligible
            ),
        }
        required = {
            "outcome-linked": 12,
            "material": 6,
            "weak/partial/tracking": 6,
            "prior disagreement": 4,
            "observe/no-change baseline": 4,
        }
        missing = [
            f"{name} {coverage[name]}/{minimum}"
            for name, minimum in required.items()
            if coverage[name] < minimum
        ]
        if missing:
            raise ValueError(f"Phase 8 cohort coverage is incomplete: {', '.join(missing)}")
        return self


class Phase8ProviderPolicy(Phase8Model):
    max_attempts: int = Field(ge=1, le=2)
    max_input_characters: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1, le=4_000)
    max_cost_usd: float = Field(gt=0)
    timeout_seconds: int = Field(ge=1, le=720)
    retryable_failures_only: Literal[True]
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"]
    input_cost_per_million_usd: float = Field(ge=0)
    output_cost_per_million_usd: float = Field(ge=0)


_STAGE_LIMITS: dict[Phase8StageId, tuple[str, str, int, float]] = {
    "reviewer_a_independent": ("A", "independent", 30_000, 0.10),
    "reviewer_b_independent": ("B", "independent", 30_000, 0.10),
    "reviewer_a_cross_review": ("A", "cross_review", 45_000, 0.13),
    "reviewer_b_cross_review": ("B", "cross_review", 45_000, 0.13),
    "reviewer_c_blind_assessment": ("C", "independent", 30_000, 0.15),
    "reviewer_c_judgment": ("C", "judging", 60_000, 0.25),
}


class Phase8StageAccess(Phase8Model):
    stage_id: Phase8StageId
    slot: Literal["A", "B", "C"]
    stage: Literal["independent", "cross_review", "judging"]
    provider: Literal["openai", "anthropic"]
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    role_version: str = Field(min_length=1, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=100)
    schema_version: str = Field(min_length=1, max_length=100)
    pricing_version: str = Field(min_length=1, max_length=100)
    policy: Phase8ProviderPolicy

    @field_validator("base_url")
    @classmethod
    def base_url_is_https_origin(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("provider base URLs must use an absolute HTTPS URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("provider base URLs cannot contain credentials or parameters")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_stage_ceiling(self) -> Self:
        expected_slot, expected_stage, max_input, max_cost = _STAGE_LIMITS[self.stage_id]
        if self.slot != expected_slot or self.stage != expected_stage:
            raise ValueError("stage_id does not match its reviewer slot and stage")
        if self.policy.max_input_characters > max_input:
            raise ValueError("stage input ceiling exceeds the Phase 8 contract")
        if self.policy.max_cost_usd > max_cost:
            raise ValueError("stage cost ceiling exceeds the Phase 8 contract")
        return self


class Phase8CredentialBinding(Phase8Model):
    provider: Literal["openai", "anthropic"]
    external_secret_ref: str = Field(min_length=1, max_length=200)
    pilot_specific: Literal[True]
    excluded_from_commands_and_reports: Literal[True]
    revoke_after_batch: Literal[True]

    @field_validator("external_secret_ref")
    @classmethod
    def secret_reference_is_not_a_secret(cls, value: str) -> str:
        lowered = value.lower()
        forbidden = ("sk-", "api_key=", "bearer ", "token=")
        if any(marker in lowered for marker in forbidden):
            raise ValueError("credential bindings may contain references, never secrets")
        return value


class Phase8ProhibitedCapabilities(Phase8Model):
    marketing_os: Literal[False] = False
    meta: Literal[False] = False
    domain_apis: Literal[False] = False
    provider_tools: Literal[False] = False
    browsing: Literal[False] = False
    code_execution: Literal[False] = False
    file_access: Literal[False] = False
    remote_storage: Literal[False] = False
    provider_fallback: Literal[False] = False


class Phase8PricingVerification(Phase8Model):
    provider: Literal["openai", "anthropic"]
    pricing_version: str = Field(min_length=1, max_length=100)
    source_url: str = Field(min_length=1, max_length=500)
    source_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    verified_at: datetime
    verified_by: str = Field(min_length=1, max_length=100)

    @field_validator("source_url")
    @classmethod
    def source_url_is_https(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("pricing sources must use absolute HTTPS URLs")
        return value

    @field_validator("verified_at")
    @classmethod
    def verified_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "verified_at")


class Phase8AccessManifest(Phase8HashedArtifact):
    hash_field = "manifest_hash"

    contract_version: Literal["phase8-provider-access-manifest/v1"]
    manifest_id: str = Field(min_length=1, max_length=100)
    cohort_id: str = Field(min_length=1, max_length=100)
    cohort_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    created_at: datetime
    version_pins: Phase8VersionPins
    stages: tuple[Phase8StageAccess, ...] = Field(min_length=6, max_length=6)
    endpoint_allowlist: tuple[str, ...] = Field(min_length=2, max_length=2)
    credentials: tuple[Phase8CredentialBinding, ...] = Field(min_length=2, max_length=2)
    pricing_verifications: tuple[Phase8PricingVerification, ...] = Field(
        min_length=2,
        max_length=2,
    )
    prohibited: Phase8ProhibitedCapabilities
    provider_retention_and_training_disabled_where_supported: Literal[True]
    raw_provider_responses_stored: Literal[False]
    hidden_reasoning_stored: Literal[False]
    manifest_hash: Sha256 = Field(pattern=_SHA256_PATTERN)

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "created_at")

    @field_validator("endpoint_allowlist")
    @classmethod
    def allowlist_urls_are_https(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.rstrip("/") for value in values)
        for value in normalized:
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError("endpoint allowlist entries must be absolute HTTPS URLs")
        if len(set(normalized)) != len(normalized):
            raise ValueError("endpoint allowlist entries must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_pilot_topology(self) -> Self:
        stage_ids = [stage.stage_id for stage in self.stages]
        if set(stage_ids) != set(_STAGE_LIMITS) or len(stage_ids) != len(set(stage_ids)):
            raise ValueError("the access manifest must pin all six Phase 8 stages once")
        expected_providers = {
            "reviewer_a_independent": "openai",
            "reviewer_b_independent": "anthropic",
            "reviewer_a_cross_review": "openai",
            "reviewer_b_cross_review": "anthropic",
            "reviewer_c_blind_assessment": "openai",
            "reviewer_c_judgment": "openai",
        }
        for stage in self.stages:
            if stage.provider != expected_providers[stage.stage_id]:
                raise ValueError("the Phase 8 v1 topology is OpenAI-A/Anthropic-B/OpenAI-C")
        stage_endpoints = {stage.base_url for stage in self.stages}
        if stage_endpoints != set(self.endpoint_allowlist):
            raise ValueError("endpoint allowlist must exactly match pinned stage endpoints")
        credential_providers = [binding.provider for binding in self.credentials]
        if sorted(credential_providers) != ["anthropic", "openai"]:
            raise ValueError("the manifest requires one credential binding per provider")
        pricing_providers = [item.provider for item in self.pricing_verifications]
        if sorted(pricing_providers) != ["anthropic", "openai"]:
            raise ValueError("the manifest requires one pricing verification per provider")
        pricing_by_provider = {
            item.provider: item.pricing_version for item in self.pricing_verifications
        }
        if any(
            stage.pricing_version != pricing_by_provider[stage.provider] for stage in self.stages
        ):
            raise ValueError("stage pricing versions must match provider price verification")
        return self


class Phase8BatchBudget(Phase8Model):
    batch_spend_cap_usd: float = Field(gt=0)
    batch_attempt_cap: int = Field(ge=1, le=160)
    batch_token_cap: int = Field(ge=1, le=1_000_000)
    phase_spend_cap_usd: Literal[15.0]
    phase_attempt_cap: Literal[160]
    phase_token_cap: Literal[1_000_000]
    alert_percentages: tuple[Literal[50], Literal[75]]
    automatic_stop_percentage: Literal[100]
    unused_authority_rolls_forward: Literal[False]


class Phase8BatchApproval(Phase8HashedArtifact):
    hash_field = "approval_hash"

    contract_version: Literal["phase8-batch-approval/v1"]
    approval_id: str = Field(min_length=1, max_length=100)
    gate: Literal["gate_1_canary", "gate_2_completion"]
    batch_id: str = Field(min_length=1, max_length=100)
    cohort_id: str = Field(min_length=1, max_length=100)
    cohort_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    access_manifest_id: str = Field(min_length=1, max_length=100)
    access_manifest_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    gate_0_report_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    prior_gate_review_hash: Sha256 | None = Field(default=None, pattern=_SHA256_PATTERN)
    eligible_case_ids: tuple[str, ...]
    control_case_ids: tuple[str, ...]
    budget: Phase8BatchBudget
    approved_provider_access: Literal[True]
    approved_by: str = Field(min_length=1, max_length=100)
    stop_authority: str = Field(min_length=1, max_length=100)
    issued_at: datetime
    expires_at: datetime
    approval_hash: Sha256 = Field(pattern=_SHA256_PATTERN)

    @field_validator("eligible_case_ids", "control_case_ids")
    @classmethod
    def case_ids_are_opaque(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            if not re.fullmatch(_CASE_ID_PATTERN, value):
                raise ValueError("approval case IDs must be opaque Phase 8 case IDs")
        return values

    @field_validator("issued_at", "expires_at")
    @classmethod
    def timestamps_are_aware(cls, value: datetime, info: ValidationInfo) -> datetime:
        return _require_aware(value, info.field_name)

    @model_validator(mode="after")
    def validate_gate_authority(self) -> Self:
        all_cases = (*self.eligible_case_ids, *self.control_case_ids)
        if len(all_cases) != len(set(all_cases)):
            raise ValueError("a batch approval cannot repeat a case ID")
        if self.expires_at <= self.issued_at:
            raise ValueError("batch approval expiry must be after issuance")
        if self.gate == "gate_1_canary":
            if len(self.eligible_case_ids) != 5 or len(self.control_case_ids) != 4:
                raise ValueError("Gate 1 approves five eligible cases and four controls")
            if self.budget.batch_spend_cap_usd > 5:
                raise ValueError("Gate 1 spend authority cannot exceed $5")
            if self.prior_gate_review_hash is not None:
                raise ValueError("Gate 1 cannot inherit a prior gate review")
        else:
            if len(self.eligible_case_ids) != 15 or self.control_case_ids:
                raise ValueError("Gate 2 approves only the remaining 15 eligible cases")
            if self.budget.batch_spend_cap_usd > 10:
                raise ValueError("Gate 2 spend authority cannot exceed $10")
            if self.prior_gate_review_hash is None:
                raise ValueError("Gate 2 requires the frozen Gate 1 review")
        return self


class Phase8Gate0Checks(Phase8Model):
    all_case_packages_validated: Literal[True]
    case_baseline_and_cohort_hashes_frozen: Literal[True]
    two_person_redaction_review_complete: Literal[True]
    plan_and_provider_access_manifest_frozen: Literal[True]
    route_batch_phase_and_wall_time_guards_passed: Literal[True]
    approval_and_case_allowlist_required_before_provider_construction: Literal[True]
    all_no_call_controls_predicted_to_stop: Literal[True]
    audit_idempotency_and_evaluation_dry_run_passed: Literal[True]
    approval_record_shape_validated: Literal[True]


Phase8Gate0CheckId = Literal[
    "all_case_packages_validated",
    "case_baseline_and_cohort_hashes_frozen",
    "two_person_redaction_review_complete",
    "plan_and_provider_access_manifest_frozen",
    "route_batch_phase_and_wall_time_guards_passed",
    "approval_and_case_allowlist_required_before_provider_construction",
    "all_no_call_controls_predicted_to_stop",
    "audit_idempotency_and_evaluation_dry_run_passed",
    "approval_record_shape_validated",
]


class Phase8Gate0EvidenceItem(Phase8Model):
    check_id: Phase8Gate0CheckId
    passed: Literal[True]
    details: tuple[str, ...] = Field(min_length=1)
    evidence_hashes: tuple[Sha256, ...] = ()


class Phase8Gate0Coverage(Phase8Model):
    total_cases: Literal[24]
    provider_eligible_cases: Literal[20]
    no_call_controls: Literal[4]
    real_event_cases: int = Field(ge=0, le=24)
    historical_replay_cases: int = Field(ge=0, le=24)
    outcome_linked_cases: int = Field(ge=12, le=20)
    materially_eligible_cases: int = Field(ge=6, le=20)
    weak_partial_or_tracking_unhealthy_cases: int = Field(ge=6, le=20)
    prior_disagreement_cases: int = Field(ge=4, le=20)
    observe_or_no_change_baselines: int = Field(ge=4, le=20)

    @model_validator(mode="after")
    def source_counts_cover_cohort(self) -> Self:
        if self.real_event_cases + self.historical_replay_cases != self.total_cases:
            raise ValueError("Gate 0 source counts must cover all 24 cases")
        return self


class Phase8Gate0Report(Phase8HashedArtifact):
    hash_field = "report_hash"

    contract_version: Literal["phase8-gate-0-report/v1"]
    cohort_id: str = Field(min_length=1, max_length=100)
    cohort_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    access_manifest_id: str = Field(min_length=1, max_length=100)
    access_manifest_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    runner_version: Literal["phase8-runner/v1"]
    generated_at: datetime
    checks: Phase8Gate0Checks
    coverage: Phase8Gate0Coverage
    evidence: tuple[Phase8Gate0EvidenceItem, ...] = Field(min_length=9, max_length=9)
    provider_attempt_count: Literal[0]
    provider_spend_usd: Literal[0.0]
    provider_credentials_loaded: Literal[False]
    passed: Literal[True]
    report_hash: Sha256 = Field(pattern=_SHA256_PATTERN)

    @field_validator("generated_at")
    @classmethod
    def generated_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "generated_at")

    @model_validator(mode="after")
    def evidence_matches_checks(self) -> Self:
        expected = set(Phase8Gate0Checks.model_fields)
        observed = [item.check_id for item in self.evidence]
        if len(observed) != len(set(observed)) or set(observed) != expected:
            raise ValueError("Gate 0 evidence must cover every check exactly once")
        return self


class Phase8RevocationRecord(Phase8HashedArtifact):
    hash_field = "revocation_hash"

    contract_version: Literal["phase8-revocation/v1"]
    batch_id: str = Field(min_length=1, max_length=100)
    approval_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    revoked_at: datetime
    revoked_by: str = Field(min_length=1, max_length=100)
    reason: Literal[
        "credential_or_data_exposure",
        "prohibited_access",
        "unapproved_contract_or_provider",
        "context_leakage",
        "invalid_output_accepted",
        "audit_integrity_failure",
        "critical_recommendation_defect",
        "budget_or_time_breach",
        "consecutive_session_failures",
        "cohort_contract_failure",
        "operator_stop",
    ]
    details: str = Field(min_length=1, max_length=1_000)
    automatic_restart_allowed: Literal[False]
    revocation_hash: Sha256 = Field(pattern=_SHA256_PATTERN)

    @field_validator("revoked_at")
    @classmethod
    def revoked_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "revoked_at")


class Phase8BlindCandidate(Phase8Model):
    label: Literal["result_1", "result_2"]
    document_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    document: dict[str, Any]

    @model_validator(mode="after")
    def validate_document_hash(self) -> Self:
        if phase8_content_hash(self.document) != self.document_hash:
            raise ValueError("blind candidate document hash does not match its document")
        return self


class Phase8RaterItem(Phase8Model):
    item_id: str = Field(min_length=1, max_length=100)
    case_id: str = Field(pattern=_CASE_ID_PATTERN)
    candidates: tuple[Phase8BlindCandidate, Phase8BlindCandidate]

    @model_validator(mode="after")
    def candidates_are_blind_and_complete(self) -> Self:
        if {candidate.label for candidate in self.candidates} != {
            "result_1",
            "result_2",
        }:
            raise ValueError("each rater item requires result_1 and result_2")
        return self


class Phase8RaterPacket(Phase8HashedArtifact):
    hash_field = "packet_hash"

    contract_version: Literal["phase8-rater-packet/v1"]
    packet_id: str = Field(min_length=1, max_length=100)
    cohort_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    created_at: datetime
    randomized: Literal[True]
    blinding_key_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    items: tuple[Phase8RaterItem, ...] = Field(min_length=1, max_length=20)
    packet_hash: Sha256 = Field(pattern=_SHA256_PATTERN)

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "created_at")

    @model_validator(mode="after")
    def item_ids_are_unique(self) -> Self:
        item_ids = [item.item_id for item in self.items]
        case_ids = [item.case_id for item in self.items]
        if len(item_ids) != len(set(item_ids)) or len(case_ids) != len(set(case_ids)):
            raise ValueError("rater packet items and cases must be unique")
        return self


class Phase8DimensionScores(Phase8Model):
    evidence_linkage_and_factual_support: int = Field(ge=1, le=5)
    clarity_and_actionability: int = Field(ge=1, le=5)
    uncertainty_quality_and_confounders: int = Field(ge=1, le=5)
    boundedness_authority_and_safety: int = Field(ge=1, le=5)
    usefulness_for_decision: int = Field(ge=1, le=5)


class Phase8CandidateRating(Phase8Model):
    label: Literal["result_1", "result_2"]
    scores: Phase8DimensionScores
    critical_defects: tuple[
        Literal[
            "unsupported_material_action",
            "evidence_mismatch",
            "hidden_authority",
            "unsafe_certainty",
        ],
        ...,
    ] = ()
    material_recommendation: bool
    caller_decision_required_marked: bool


class Phase8RaterItemRating(Phase8Model):
    item_id: str = Field(min_length=1, max_length=100)
    candidates: tuple[Phase8CandidateRating, Phase8CandidateRating]
    usefulness_preference: Literal[
        "result_1",
        "result_2",
        "equal",
        "not_comparable",
    ]
    notes: str = Field(default="", max_length=2_000)

    @model_validator(mode="after")
    def candidate_labels_are_complete(self) -> Self:
        if {candidate.label for candidate in self.candidates} != {
            "result_1",
            "result_2",
        }:
            raise ValueError("each rating requires scores for result_1 and result_2")
        return self


class Phase8RaterSubmission(Phase8HashedArtifact):
    hash_field = "submission_hash"

    contract_version: Literal["phase8-rater-submission/v1"]
    submission_id: str = Field(min_length=1, max_length=100)
    packet_id: str = Field(min_length=1, max_length=100)
    packet_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    rater_id: str = Field(min_length=1, max_length=100)
    submitted_at: datetime
    ratings: tuple[Phase8RaterItemRating, ...] = Field(min_length=1, max_length=20)
    submission_hash: Sha256 = Field(pattern=_SHA256_PATTERN)

    @field_validator("submitted_at")
    @classmethod
    def submitted_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "submitted_at")

    @model_validator(mode="after")
    def ratings_are_unique(self) -> Self:
        item_ids = [rating.item_id for rating in self.ratings]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("a rater submission cannot score an item twice")
        return self


class Phase8MetricOutcome(Phase8Model):
    metric: str = Field(min_length=1, max_length=200)
    numerator: float = Field(ge=0)
    denominator: float = Field(gt=0)
    value: float = Field(ge=0)
    threshold: str = Field(min_length=1, max_length=100)
    passed: bool


class Phase8CaseResult(Phase8Model):
    case_id: str = Field(pattern=_CASE_ID_PATTERN)
    provider_eligible: bool
    provider_call_count: int = Field(ge=0)
    valid_audited_result: bool
    route: Phase8Route | None
    caller_decision_required_marked: bool
    critical_defect_count: int = Field(ge=0)
    attempt_count: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    total_latency_ms: int = Field(ge=0)
    computed_cost_usd: float = Field(ge=0)
    stop_reason: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def no_call_results_are_call_free(self) -> Self:
        if not self.provider_eligible and self.provider_call_count != 0:
            raise ValueError("a no-call control cannot record a provider call")
        if self.valid_audited_result and self.route is None:
            raise ValueError("an audited eligible result requires its final route")
        return self


class Phase8PilotReport(Phase8HashedArtifact):
    hash_field = "report_hash"

    contract_version: Literal["phase8-pilot-report/v1"]
    cohort_id: str = Field(min_length=1, max_length=100)
    cohort_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    access_manifest_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    gate_0_report_hash: Sha256 = Field(pattern=_SHA256_PATTERN)
    gate_1_approval_hash: Sha256 | None = Field(default=None, pattern=_SHA256_PATTERN)
    gate_2_approval_hash: Sha256 | None = Field(default=None, pattern=_SHA256_PATTERN)
    generated_at: datetime
    status: Literal["gate_0_only", "canary_complete", "pilot_complete", "stopped"]
    case_results: tuple[Phase8CaseResult, ...] = Field(max_length=24)
    metrics: tuple[Phase8MetricOutcome, ...]
    hard_guardrail_violations: tuple[str, ...]
    exit_decision: Literal[
        "not_yet_eligible",
        "proceed_to_larger_shadow_pilot",
        "revise_and_repeat",
        "stop",
    ]
    decision_rationale: str = Field(min_length=1, max_length=4_000)
    report_hash: Sha256 = Field(pattern=_SHA256_PATTERN)

    @field_validator("generated_at")
    @classmethod
    def generated_at_is_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "generated_at")

    @model_validator(mode="after")
    def decision_matches_guardrail_state(self) -> Self:
        if self.hard_guardrail_violations and self.exit_decision not in {
            "not_yet_eligible",
            "stop",
        }:
            raise ValueError("hard guardrail violations cannot produce a proceed decision")
        if self.exit_decision == "proceed_to_larger_shadow_pilot" and (
            self.status != "pilot_complete"
            or not self.metrics
            or not all(metric.passed for metric in self.metrics)
        ):
            raise ValueError("proceed requires a complete pilot with every metric passing")
        return self


def validate_phase8_cohort_packages(
    manifest: Phase8CohortManifest,
    packages: Sequence[Phase8CasePackage],
) -> None:
    """Verify the frozen cohort index against its immutable case packages."""

    by_id = {package.case_id: package for package in packages}
    if len(by_id) != len(packages):
        raise ValueError("case packages contain duplicate case IDs")
    manifest_ids = {case.case_id for case in manifest.cases}
    if set(by_id) != manifest_ids:
        raise ValueError("case package IDs do not exactly match the cohort manifest")
    for entry in manifest.cases:
        expected = Phase8CohortCase.from_case_package(by_id[entry.case_id])
        if entry != expected:
            raise ValueError(f"cohort entry does not match case package {entry.case_id}")

    duplicate_controls = [
        package for package in packages if package.control_type == "duplicate_replay"
    ]
    for duplicate in duplicate_controls:
        original = by_id[duplicate.duplicate_of_case_id or ""]
        if duplicate.request_snapshot_hash != original.request_snapshot_hash:
            raise ValueError("duplicate replay control does not reuse the original snapshot")
        if duplicate.source_provenance != original.source_provenance:
            raise ValueError("duplicate replay control does not reuse the original provenance")

    eligible_sources = [
        package.source_provenance.source_record_ref
        for package in packages
        if package.case_kind == "provider_eligible"
    ]
    if len(eligible_sources) != len(set(eligible_sources)):
        raise ValueError("provider-eligible cases must represent distinct source records")


def validate_phase8_approval_scope(
    approval: Phase8BatchApproval,
    cohort: Phase8CohortManifest,
    access_manifest: Phase8AccessManifest,
) -> None:
    """Cross-check an approval against the frozen cohort and access contract."""

    if approval.cohort_id != cohort.cohort_id or approval.cohort_hash != cohort.cohort_hash:
        raise ValueError("approval does not match the frozen cohort")
    if (
        approval.access_manifest_id != access_manifest.manifest_id
        or approval.access_manifest_hash != access_manifest.manifest_hash
    ):
        raise ValueError("approval does not match the frozen access manifest")
    if (
        access_manifest.cohort_id != cohort.cohort_id
        or access_manifest.cohort_hash != cohort.cohort_hash
    ):
        raise ValueError("access manifest does not match the frozen cohort")

    cohort_by_id = {case.case_id: case for case in cohort.cases}
    approved_ids = {*approval.eligible_case_ids, *approval.control_case_ids}
    if not approved_ids <= cohort_by_id.keys():
        raise ValueError("approval contains a case outside the frozen cohort")
    if any(
        cohort_by_id[case_id].case_kind != "provider_eligible"
        for case_id in approval.eligible_case_ids
    ):
        raise ValueError("eligible approval list contains a no-call control")
    if any(
        cohort_by_id[case_id].case_kind != "no_call_control"
        for case_id in approval.control_case_ids
    ):
        raise ValueError("control approval list contains a provider-eligible case")


PHASE8_ARTIFACT_MODELS: Mapping[str, type[BaseModel]] = {
    "phase8-access-manifest": Phase8AccessManifest,
    "phase8-batch-approval": Phase8BatchApproval,
    "phase8-case-package": Phase8CasePackage,
    "phase8-cohort-manifest": Phase8CohortManifest,
    "phase8-gate-0-report": Phase8Gate0Report,
    "phase8-pilot-report": Phase8PilotReport,
    "phase8-rater-packet": Phase8RaterPacket,
    "phase8-rater-submission": Phase8RaterSubmission,
    "phase8-redaction-attestation": Phase8RedactionAttestation,
    "phase8-revocation-record": Phase8RevocationRecord,
}
