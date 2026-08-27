import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from conclave.fixtures import load_design_plan_revisions, load_request_fixture
from conclave.ledger.repository import canonical_hash
from conclave.pilot.phase8 import (
    Phase8AccessManifest,
    Phase8CasePackage,
    Phase8CohortManifest,
    Phase8VersionPins,
    phase8_content_hash,
)
from conclave.pilot.phase8_runner import (
    Phase8BatchRunner,
    Phase8CohortError,
    freeze_phase8_cohort,
    run_phase8_gate0,
    write_phase8_gate0_evidence,
)
from conclave.pilot.phase8_safety import Phase8AuthorizationError
from conclave.pilot.runner import _pilot_revision
from conclave.pilot.runner import _repository as _memory_repository
from conclave.plans.models import ProviderPolicy, ReviewPlanRevision
from conclave.task_packs.registry import default_task_pack_registry
from tests.test_phase8_foundation import (
    _access_manifest,
    _cohort,
    _control_case,
    _eligible_case,
)
from tests.test_phase8_safety import (
    _AUTH_NOW,
    _authorized_settings,
    _safety_runtime,
    _SuccessfulProvider,
)

_NOW = datetime(2026, 7, 29, 18, 0, tzinfo=UTC)


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _provider_policy(stage: object) -> ProviderPolicy:
    policy = stage.policy
    return ProviderPolicy(
        max_attempts=policy.max_attempts,
        timeout_seconds=policy.timeout_seconds,
        max_input_characters=policy.max_input_characters,
        max_output_tokens=policy.max_output_tokens,
        max_cost_usd=policy.max_cost_usd,
        reasoning_effort=policy.reasoning_effort,
        input_cost_per_million_usd=policy.input_cost_per_million_usd,
        output_cost_per_million_usd=policy.output_cost_per_million_usd,
        pricing_version=stage.pricing_version,
    )


def _frozen_plan(stage_source: Phase8AccessManifest) -> ReviewPlanRevision:
    stages = {stage.stage_id: stage for stage in stage_source.stages}
    base = _pilot_revision(load_design_plan_revisions()[-1])
    slots = dict(base.slots)
    a = stages["reviewer_a_independent"]
    cross_a = stages["reviewer_a_cross_review"]
    slots["A"] = slots["A"].model_copy(
        update={
            "provider": a.provider,
            "model": a.model,
            "role_version": a.role_version,
            "prompt_version": a.prompt_version,
            "schema_version": a.schema_version,
            "cross_review_role_version": cross_a.role_version,
            "cross_review_prompt_version": cross_a.prompt_version,
            "cross_review_schema_version": cross_a.schema_version,
            "provider_policy": _provider_policy(a),
            "cross_review_provider_policy": _provider_policy(cross_a),
        }
    )
    b = stages["reviewer_b_independent"]
    cross_b = stages["reviewer_b_cross_review"]
    slots["B"] = slots["B"].model_copy(
        update={
            "provider": b.provider,
            "model": b.model,
            "role_version": b.role_version,
            "prompt_version": b.prompt_version,
            "schema_version": b.schema_version,
            "cross_review_role_version": cross_b.role_version,
            "cross_review_prompt_version": cross_b.prompt_version,
            "cross_review_schema_version": cross_b.schema_version,
            "provider_policy": _provider_policy(b),
            "cross_review_provider_policy": _provider_policy(cross_b),
        }
    )
    c = stages["reviewer_c_blind_assessment"]
    judge_c = stages["reviewer_c_judgment"]
    slots["C"] = slots["C"].model_copy(
        update={
            "provider": c.provider,
            "model": c.model,
            "role_version": c.role_version,
            "prompt_version": c.prompt_version,
            "schema_version": c.schema_version,
            "judging_role_version": judge_c.role_version,
            "judging_prompt_version": judge_c.prompt_version,
            "judging_schema_version": judge_c.schema_version,
            "provider_policy": _provider_policy(c),
            "judging_provider_policy": _provider_policy(judge_c),
        }
    )
    return base.model_copy(
        update={
            "plan_id": "phase8-pilot-plan",
            "deployment_id": "phase8-pilot-deployment",
            "revision": 1,
            "slots": slots,
        }
    )


def _snapshot(index: int, plan: ReviewPlanRevision, *, stale: bool = False) -> dict:
    document = deepcopy(load_request_fixture("01-normal-healthy.json"))
    due_at = _NOW - timedelta(hours=1)
    observed_at = due_at - (timedelta(hours=25) if stale else timedelta(hours=1))
    document["caller"] = {
        "caller_id": "p8caller_opaque",
        "auth_subject": "p8subject_opaque",
    }
    document["subject"] = {
        "business_campaign_id": f"p8campaign_{index:03}",
        "deployment_id": "phase8-pilot-deployment",
        "conversion_event_id": "p8conversion_opaque",
    }
    document["idempotency_key"] = f"phase8:{index:03}"
    document["evidence_version"] = f"p8ev_{index:016x}"
    document["review_trigger"] = {
        "occurrence_id": f"p8occ_{index:03}",
        "kind": "scheduled_a",
        "due_at": due_at.isoformat().replace("+00:00", "Z"),
    }
    document["review_plan_ref"] = plan.plan_id
    document["review_plan_revision"] = plan.revision
    document["quality"]["freshness"].update(
        {
            "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
            "metric_period_start": (observed_at - timedelta(hours=8))
            .isoformat()
            .replace("+00:00", "Z"),
            "metric_period_end": (observed_at - timedelta(hours=1))
            .isoformat()
            .replace("+00:00", "Z"),
        }
    )
    return document


def _repackage(
    package: Phase8CasePackage,
    *,
    snapshot: dict,
    versions: Phase8VersionPins | None,
) -> Phase8CasePackage:
    document = package.model_dump(mode="python", exclude={"case_package_hash"})
    document.update(
        {
            "evidence_version": snapshot["evidence_version"],
            "request_snapshot": snapshot,
            "request_snapshot_hash": phase8_content_hash(snapshot),
            "version_pins": versions,
        }
    )
    return Phase8CasePackage.seal(**document)


def _gate0_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    seed_cohort, _ = _cohort()
    stage_source = _access_manifest(seed_cohort)
    plan = _frozen_plan(stage_source)
    task_pack = default_task_pack_registry().get("marketing-ads/v1")
    versions = Phase8VersionPins(
        task_pack_id="marketing-ads",
        task_pack_revision="v1",
        task_pack_hash=task_pack.content_hash,
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        plan_hash=canonical_hash(plan.model_dump(mode="json")),
        prompt_bundle_version="phase8-prompts-v1",
        role_bundle_version="phase8-roles-v1",
        schema_bundle_version="phase8-schemas-v1",
    )
    eligible = tuple(
        _repackage(
            _eligible_case(index),
            snapshot=_snapshot(index, plan),
            versions=versions,
        )
        for index in range(20)
    )
    controls: list[Phase8CasePackage] = []
    for offset, control_type in enumerate(
        ("stale_package", "invalid_contract", "duplicate_replay", "unapproved_provider")
    ):
        index = 20 + offset
        source = _control_case(index, control_type, original=eligible[0])
        snapshot = (
            deepcopy(eligible[0].request_snapshot)
            if control_type == "duplicate_replay"
            else _snapshot(index, plan, stale=control_type == "stale_package")
        )
        if control_type == "invalid_contract":
            del snapshot["caller"]
        controls.append(_repackage(source, snapshot=snapshot, versions=None))
    case_dir = tmp_path / "case-packages"
    for package in (*eligible, *controls):
        _write(case_dir / f"{package.case_id}.json", package.model_dump(mode="json"))
    cohort_path = tmp_path / "cohort.json"
    cohort = freeze_phase8_cohort(
        case_packages_dir=case_dir,
        output_path=cohort_path,
        cohort_id="phase8-real-replay-001",
        revision=1,
        frozen_at=_NOW,
    )
    access_document = stage_source.model_dump(mode="python", exclude={"manifest_hash"})
    access_document.update(
        {
            "cohort_id": cohort.cohort_id,
            "cohort_hash": cohort.cohort_hash,
            "created_at": _NOW,
            "version_pins": versions,
        }
    )
    access = Phase8AccessManifest.seal(**access_document)
    access_path = tmp_path / "access.json"
    plan_path = tmp_path / "plan.json"
    _write(access_path, access.model_dump(mode="json"))
    _write(plan_path, plan.model_dump(mode="json"))
    return cohort_path, case_dir, access_path, plan_path


def test_freeze_refuses_to_overwrite_an_immutable_cohort(tmp_path: Path) -> None:
    cohort_path, case_dir, _, _ = _gate0_inputs(tmp_path)

    with pytest.raises(Phase8CohortError, match="refusing to overwrite"):
        freeze_phase8_cohort(
            case_packages_dir=case_dir,
            output_path=cohort_path,
            cohort_id="phase8-real-replay-001",
            revision=1,
            frozen_at=_NOW,
        )


def test_gate0_seals_credential_free_machine_and_human_evidence(tmp_path: Path) -> None:
    cohort_path, case_dir, access_path, plan_path = _gate0_inputs(tmp_path)

    report = run_phase8_gate0(
        cohort_manifest_path=cohort_path,
        case_packages_dir=case_dir,
        access_manifest_path=access_path,
        plan_revision_path=plan_path,
        generated_at=_NOW + timedelta(minutes=1),
    )

    assert report.passed is True
    assert report.provider_attempt_count == 0
    assert report.provider_spend_usd == 0
    assert report.provider_credentials_loaded is False
    assert len(report.evidence) == 9
    output_dir = tmp_path / "evidence"
    json_path, markdown_path = write_phase8_gate0_evidence(report, output_dir=output_dir)
    assert Phase8CohortManifest.model_validate(_read(cohort_path))
    assert json.loads(json_path.read_text())["report_hash"] == report.report_hash
    assert "NOT PROVIDER AUTHORIZATION" in markdown_path.read_text()


def test_dedicated_batch_runner_stops_provider_control_without_a_call(
    tmp_path: Path,
) -> None:
    settings, _, packages, _ = _authorized_settings(tmp_path, now=_AUTH_NOW)
    provider = _SuccessfulProvider()
    runtime = _safety_runtime(settings, now=_AUTH_NOW, provider=provider)
    engine, repository = _memory_repository()
    try:
        runner = Phase8BatchRunner(repository, runtime)
        control = next(
            package for package in packages if package.control_type == "unapproved_provider"
        )

        result = runner.run_case(control.case_id, now=_AUTH_NOW)

        assert result.observed_disposition == "stop_unapproved_provider"
        assert result.session_id is None
        assert provider.calls == 0
        assert runtime.state_store.read().cases[control.case_id].completed is True

        with pytest.raises(Phase8AuthorizationError, match="one to five"):
            runner.run_group(tuple(f"p8c_{index:016x}" for index in range(6)))
    finally:
        engine.dispose()


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
