from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from jsonschema.validators import validator_for
from pydantic import ValidationError

from conclave.pilot.phase8 import (
    PHASE8_ARTIFACT_MODELS,
    Phase8AccessManifest,
    Phase8BaselinePackage,
    Phase8BatchApproval,
    Phase8BatchBudget,
    Phase8CasePackage,
    Phase8CohortCase,
    Phase8CohortManifest,
    Phase8CredentialBinding,
    Phase8EvidenceQuality,
    Phase8PricingVerification,
    Phase8ProhibitedCapabilities,
    Phase8ProviderPolicy,
    Phase8RedactionAttestation,
    Phase8RedactionChecklist,
    Phase8RoutingProfile,
    Phase8SourceProvenance,
    Phase8StageAccess,
    Phase8VersionPins,
    phase8_content_hash,
    validate_phase8_approval_scope,
    validate_phase8_cohort_packages,
)
from conclave.pilot.phase8_contracts import (
    phase8_json_schemas,
    validate_committed_phase8_schemas,
    validate_phase8_artifact,
)

_NOW = datetime(2026, 7, 29, 16, 0, tzinfo=UTC)


def _hash(label: str) -> str:
    return phase8_content_hash({"label": label})


def _case_id(index: int) -> str:
    return f"p8c_{index:016x}"


def _evidence_version(index: int) -> str:
    return f"p8ev_{index:016x}"


def _redaction(case_id: str) -> Phase8RedactionAttestation:
    return Phase8RedactionAttestation.seal(
        contract_version="phase8-redaction-attestation/v1",
        attestation_id=f"redaction-{case_id}",
        case_id=case_id,
        reviewed_at=_NOW,
        reviewer_ids=("redactor_01", "redactor_02"),
        checklist=Phase8RedactionChecklist(
            personal_data_removed=True,
            credentials_and_tokens_removed=True,
            direct_contact_details_removed=True,
            customer_identifiers_removed=True,
            raw_message_content_removed=True,
            unnecessary_free_text_removed=True,
            business_identifiers_opaque=True,
            timestamps_shifted_when_exact_dates_unneeded=True,
            sensitive_values_normalized_when_exact_values_unneeded=True,
            redaction_map_stored_outside_conclave=True,
        ),
    )


def _baseline(index: int) -> Phase8BaselinePackage:
    return Phase8BaselinePackage.seal(
        contract_version="phase8-baseline/v1",
        captured_at=_NOW - timedelta(days=1),
        captured_before_panel_output=True,
        reviewer_kind="single_reviewer",
        assessment={
            "category": "observe" if index < 4 else "collect_more_data",
            "summary": "Synthetic baseline used only to test the Phase 8 contracts.",
        },
    )


def _versions() -> Phase8VersionPins:
    return Phase8VersionPins(
        task_pack_id="marketing-ads",
        task_pack_revision="v1",
        task_pack_hash=_hash("task-pack"),
        plan_id="phase8-pilot-plan",
        plan_revision=1,
        plan_hash=_hash("plan"),
        prompt_bundle_version="phase8-prompts-v1",
        role_bundle_version="phase8-roles-v1",
        schema_bundle_version="phase8-schemas-v1",
    )


def _snapshot(index: int) -> dict[str, Any]:
    return {
        "contract_version": "review-request/v1",
        "idempotency_key": f"opaque-{index:03}",
        "evidence_version": _evidence_version(index),
        "sections": {"evidence": {"metric_bucket": index % 4}},
        "quality": {"evidence_quality_label": "adequate"},
    }


def _provenance(index: int) -> Phase8SourceProvenance:
    return Phase8SourceProvenance(
        source_kind="real_event" if index % 2 == 0 else "historical_replay",
        source_record_ref=f"p8src_{index:016x}",
        source_snapshot_hash=_hash(f"source-{index}"),
        verified_at=_NOW,
        verified_by="source_reviewer_01",
        redacted_snapshot_derived_from_source=True,
        synthetic_data=False,
    )


def _eligible_case(index: int) -> Phase8CasePackage:
    from conclave.pilot.phase8 import Phase8OutcomePackage

    case_id = _case_id(index)
    snapshot = _snapshot(index)
    outcome = None
    if index < 12:
        outcome = Phase8OutcomePackage.seal(
            contract_version="phase8-outcome/v1",
            decision_ref=f"decision-{index:03}",
            outcome_ref=f"outcome-{index:03}",
            caller_decision="accepted",
            outcome_classification="beneficial",
            outcome_evidence_quality="adequate",
            known_confounders=(),
            evaluated_at=_NOW - timedelta(hours=1),
            attached_only_after_panel_recommendation_frozen=True,
        )
    weak = index < 6
    return Phase8CasePackage.seal(
        contract_version="phase8-case-package/v1",
        case_id=case_id,
        evidence_version=_evidence_version(index),
        case_kind="provider_eligible",
        expected_disposition="provider_call_allowed",
        request_contract_valid=True,
        request_snapshot=snapshot,
        request_snapshot_hash=phase8_content_hash(snapshot),
        source_provenance=_provenance(index),
        baseline=_baseline(index),
        routing_profile=Phase8RoutingProfile(
            expected_route=(
                "c_tie_broken"
                if index < 4
                else ("cross_review_resolved" if index < 8 else "ab_agreement")
            ),
            request_material=index < 6,
            prior_recommendation_material=False,
            prior_reviewers_disagreed=index < 4,
            baseline_observe_or_no_change=index < 4,
            reviewed_by="routing_reviewer_01",
            reviewed_at=_NOW,
        ),
        redaction_attestation=_redaction(case_id),
        evidence_quality=Phase8EvidenceQuality(
            label="weak" if weak else "adequate",
            is_partial=weak,
            tracking_health="degraded" if weak else "healthy",
            known_gaps=("one attribution window",) if weak else (),
        ),
        outcome_package=outcome,
        version_pins=_versions(),
    )


def _control_case(
    index: int,
    control_type: str,
    *,
    original: Phase8CasePackage,
) -> Phase8CasePackage:
    case_id = _case_id(index)
    evidence_version = (
        original.evidence_version
        if control_type == "duplicate_replay"
        else _evidence_version(index)
    )
    snapshot = (
        deepcopy(original.request_snapshot)
        if control_type == "duplicate_replay"
        else _snapshot(index)
    )
    dispositions = {
        "stale_package": "stop_stale",
        "invalid_contract": "stop_invalid_contract",
        "duplicate_replay": "stop_duplicate",
        "unapproved_provider": "stop_unapproved_provider",
    }
    return Phase8CasePackage.seal(
        contract_version="phase8-case-package/v1",
        case_id=case_id,
        evidence_version=evidence_version,
        case_kind="no_call_control",
        control_type=control_type,
        expected_disposition=dispositions[control_type],
        request_contract_valid=control_type != "invalid_contract",
        request_snapshot=snapshot,
        request_snapshot_hash=phase8_content_hash(snapshot),
        source_provenance=(
            original.source_provenance if control_type == "duplicate_replay" else _provenance(index)
        ),
        routing_profile=Phase8RoutingProfile(
            expected_route=None,
            request_material=False,
            prior_recommendation_material=False,
            prior_reviewers_disagreed=False,
            baseline_observe_or_no_change=False,
            reviewed_by="routing_reviewer_01",
            reviewed_at=_NOW,
        ),
        redaction_attestation=_redaction(case_id),
        evidence_quality=Phase8EvidenceQuality(
            label="adequate",
            is_partial=False,
            tracking_health="healthy",
        ),
        duplicate_of_case_id=(original.case_id if control_type == "duplicate_replay" else None),
        requested_provider=("google" if control_type == "unapproved_provider" else None),
    )


def _cohort_packages() -> tuple[Phase8CasePackage, ...]:
    eligible = tuple(_eligible_case(index) for index in range(20))
    controls = tuple(
        _control_case(20 + offset, control_type, original=eligible[0])
        for offset, control_type in enumerate(
            (
                "stale_package",
                "invalid_contract",
                "duplicate_replay",
                "unapproved_provider",
            )
        )
    )
    return (*eligible, *controls)


def _cohort() -> tuple[Phase8CohortManifest, tuple[Phase8CasePackage, ...]]:
    packages = _cohort_packages()
    cohort = Phase8CohortManifest.seal(
        contract_version="phase8-cohort-manifest/v1",
        cohort_id="phase8-cohort-001",
        revision=1,
        frozen_at=_NOW,
        cases=tuple(Phase8CohortCase.from_case_package(case) for case in packages),
    )
    return cohort, packages


def _policy(stage_id: str) -> Phase8ProviderPolicy:
    maximums = {
        "reviewer_a_independent": (30_000, 0.10),
        "reviewer_b_independent": (30_000, 0.10),
        "reviewer_a_cross_review": (45_000, 0.13),
        "reviewer_b_cross_review": (45_000, 0.13),
        "reviewer_c_blind_assessment": (30_000, 0.15),
        "reviewer_c_judgment": (60_000, 0.25),
    }
    maximum_input, maximum_cost = maximums[stage_id]
    return Phase8ProviderPolicy(
        max_attempts=2,
        max_input_characters=maximum_input,
        max_output_tokens=4_000,
        max_cost_usd=maximum_cost,
        timeout_seconds=90,
        retryable_failures_only=True,
        reasoning_effort="medium",
        input_cost_per_million_usd=2.5,
        output_cost_per_million_usd=15,
    )


def _access_manifest(cohort: Phase8CohortManifest) -> Phase8AccessManifest:
    topology = (
        ("reviewer_a_independent", "A", "independent", "openai"),
        ("reviewer_b_independent", "B", "independent", "anthropic"),
        ("reviewer_a_cross_review", "A", "cross_review", "openai"),
        ("reviewer_b_cross_review", "B", "cross_review", "anthropic"),
        ("reviewer_c_blind_assessment", "C", "independent", "openai"),
        ("reviewer_c_judgment", "C", "judging", "openai"),
    )
    endpoints = {
        "openai": "https://api.openai.test/v1",
        "anthropic": "https://api.anthropic.test/v1",
    }
    pricing = {
        "openai": "openai-phase8-test-v1",
        "anthropic": "anthropic-phase8-test-v1",
    }
    stages = tuple(
        Phase8StageAccess(
            stage_id=stage_id,
            slot=slot,
            stage=stage,
            provider=provider,
            base_url=endpoints[provider],
            model=f"{provider}-pinned-model",
            role_version=f"{stage_id}-role-v1",
            prompt_version=f"{stage_id}-prompt-v1",
            schema_version=f"{stage_id}-schema-v1",
            pricing_version=pricing[provider],
            policy=_policy(stage_id),
        )
        for stage_id, slot, stage, provider in topology
    )
    return Phase8AccessManifest.seal(
        contract_version="phase8-provider-access-manifest/v1",
        manifest_id="phase8-access-001",
        cohort_id=cohort.cohort_id,
        cohort_hash=cohort.cohort_hash,
        created_at=_NOW,
        version_pins=_versions(),
        stages=stages,
        endpoint_allowlist=tuple(endpoints.values()),
        credentials=(
            Phase8CredentialBinding(
                provider="openai",
                external_secret_ref="secret-boundary://phase8/openai",
                pilot_specific=True,
                excluded_from_commands_and_reports=True,
                revoke_after_batch=True,
            ),
            Phase8CredentialBinding(
                provider="anthropic",
                external_secret_ref="secret-boundary://phase8/anthropic",
                pilot_specific=True,
                excluded_from_commands_and_reports=True,
                revoke_after_batch=True,
            ),
        ),
        pricing_verifications=tuple(
            Phase8PricingVerification(
                provider=provider,
                pricing_version=pricing[provider],
                source_url=f"https://pricing.test/{provider}",
                source_hash=_hash(f"{provider}-pricing"),
                verified_at=_NOW,
                verified_by="pricing_reviewer_01",
            )
            for provider in ("openai", "anthropic")
        ),
        prohibited=Phase8ProhibitedCapabilities(),
        provider_retention_and_training_disabled_where_supported=True,
        raw_provider_responses_stored=False,
        hidden_reasoning_stored=False,
    )


def _approval(
    cohort: Phase8CohortManifest,
    access: Phase8AccessManifest,
) -> Phase8BatchApproval:
    eligible = tuple(case.case_id for case in cohort.cases if case.case_kind == "provider_eligible")
    controls = tuple(case.case_id for case in cohort.cases if case.case_kind == "no_call_control")
    return Phase8BatchApproval.seal(
        contract_version="phase8-batch-approval/v1",
        approval_id="phase8-gate1-approval-001",
        gate="gate_1_canary",
        batch_id="phase8-gate1-batch-001",
        cohort_id=cohort.cohort_id,
        cohort_hash=cohort.cohort_hash,
        access_manifest_id=access.manifest_id,
        access_manifest_hash=access.manifest_hash,
        gate_0_report_hash=_hash("gate-0-report"),
        eligible_case_ids=eligible[:5],
        control_case_ids=controls,
        budget=Phase8BatchBudget(
            batch_spend_cap_usd=5,
            batch_attempt_cap=60,
            batch_token_cap=350_000,
            phase_spend_cap_usd=15.0,
            phase_attempt_cap=160,
            phase_token_cap=1_000_000,
            alert_percentages=(50, 75),
            automatic_stop_percentage=100,
            unused_authority_rolls_forward=False,
        ),
        approved_provider_access=True,
        approved_by="operator_01",
        stop_authority="operator_02",
        issued_at=_NOW,
        expires_at=_NOW + timedelta(hours=2),
    )


def test_locked_cohort_requires_exact_shape_and_cross_artifact_integrity() -> None:
    cohort, packages = _cohort()

    assert len(cohort.cases) == 24
    assert sum(case.case_kind == "provider_eligible" for case in cohort.cases) == 20
    assert sum(case.outcome_linked for case in cohort.cases) == 12
    assert sum(case.materially_eligible for case in cohort.cases) == 6
    assert sum(case.weak_partial_or_tracking_unhealthy for case in cohort.cases) == 6
    validate_phase8_cohort_packages(cohort, packages)


def test_duplicate_control_must_reuse_the_original_snapshot() -> None:
    cohort, packages = _cohort()
    duplicate_index = next(
        index
        for index, package in enumerate(packages)
        if package.control_type == "duplicate_replay"
    )
    changed_document = packages[duplicate_index].model_dump(
        mode="json",
        exclude={"case_package_hash"},
    )
    changed_snapshot = deepcopy(changed_document["request_snapshot"])
    changed_snapshot["idempotency_key"] = "not-the-original"
    changed_document["request_snapshot"] = changed_snapshot
    changed_document["request_snapshot_hash"] = phase8_content_hash(changed_snapshot)
    changed = Phase8CasePackage.seal(**changed_document)
    changed_packages = (
        *packages[:duplicate_index],
        changed,
        *packages[duplicate_index + 1 :],
    )
    changed_cohort = Phase8CohortManifest.seal(
        contract_version=cohort.contract_version,
        cohort_id=cohort.cohort_id,
        revision=cohort.revision,
        frozen_at=cohort.frozen_at,
        cases=tuple(Phase8CohortCase.from_case_package(case) for case in changed_packages),
    )

    with pytest.raises(ValueError, match="does not reuse the original snapshot"):
        validate_phase8_cohort_packages(changed_cohort, changed_packages)


def test_case_package_and_hashed_artifacts_reject_tampering() -> None:
    case = _eligible_case(0)
    document = case.model_dump(mode="json")
    document["request_snapshot"]["sections"]["evidence"]["metric_bucket"] = 99

    with pytest.raises(ValidationError, match="request_snapshot_hash"):
        Phase8CasePackage.seal(
            **{key: value for key, value in document.items() if key != "case_package_hash"}
        )

    document = case.model_dump(mode="json")
    document["routing_profile"]["prior_reviewers_disagreed"] = False
    with pytest.raises(ValidationError, match="case_package_hash"):
        Phase8CasePackage.model_validate(document)


def test_redaction_requires_two_distinct_reviewers() -> None:
    document = _redaction(_case_id(0)).model_dump(mode="json")
    document["reviewer_ids"] = ["same-reviewer", "same-reviewer"]

    with pytest.raises(ValidationError, match="two distinct"):
        Phase8RedactionAttestation.model_validate(
            {
                **document,
                "attestation_hash": _hash("changed-attestation"),
            }
        )


def test_access_manifest_pins_the_mixed_panel_and_contract_ceilings() -> None:
    cohort, _ = _cohort()
    access = _access_manifest(cohort)

    assert {stage.provider for stage in access.stages} == {"openai", "anthropic"}
    assert len(access.stages) == 6

    changed_stages = list(access.stages)
    changed_stages[1] = changed_stages[1].model_copy(update={"provider": "openai"})
    document = access.model_dump(mode="json")
    document["stages"] = [stage.model_dump(mode="json") for stage in changed_stages]
    with pytest.raises(ValidationError, match="OpenAI-A/Anthropic-B/OpenAI-C"):
        Phase8AccessManifest.seal(
            **{key: value for key, value in document.items() if key != "manifest_hash"}
        )

    stage = access.stages[0].model_dump(mode="json")
    stage["policy"]["max_cost_usd"] = 0.11
    with pytest.raises(ValidationError, match="cost ceiling"):
        Phase8StageAccess.model_validate(stage)


def test_access_manifest_never_accepts_a_secret_value() -> None:
    with pytest.raises(ValidationError, match="never secrets"):
        Phase8CredentialBinding(
            provider="openai",
            external_secret_ref="sk-test-secret",
            pilot_specific=True,
            excluded_from_commands_and_reports=True,
            revoke_after_batch=True,
        )


def test_gate_1_approval_is_exact_and_cross_checked() -> None:
    cohort, _ = _cohort()
    access = _access_manifest(cohort)
    approval = _approval(cohort, access)

    validate_phase8_approval_scope(approval, cohort, access)
    assert len(approval.eligible_case_ids) == 5
    assert len(approval.control_case_ids) == 4
    assert approval.budget.batch_spend_cap_usd == 5

    changed = approval.model_dump(mode="json")
    changed["budget"]["batch_spend_cap_usd"] = 5.01
    with pytest.raises(ValidationError, match=r"cannot exceed \$5"):
        Phase8BatchApproval.seal(
            **{key: value for key, value in changed.items() if key != "approval_hash"}
        )


def test_committed_json_schemas_are_current_and_validate_real_models() -> None:
    validate_committed_phase8_schemas()
    schemas = phase8_json_schemas()

    assert set(schemas) == set(PHASE8_ARTIFACT_MODELS)
    cohort, _ = _cohort()
    document = cohort.model_dump(mode="json")
    schema = schemas["phase8-cohort-manifest"]
    validator_for(schema)(schema).validate(document)
    validated = validate_phase8_artifact("phase8-cohort-manifest", document)
    assert validated == cohort


def test_phase8_models_are_immutable() -> None:
    cohort, _ = _cohort()

    with pytest.raises(ValidationError, match="frozen"):
        cohort.revision = 2
