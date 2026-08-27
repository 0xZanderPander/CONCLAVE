import json
from copy import deepcopy
from datetime import UTC, timedelta
from pathlib import Path
from typing import Any

from conclave.ledger.models import ReviewOccurrenceRecord
from conclave.ledger.repository import normalize_instant
from conclave.paths import contracts_root, design_fixtures_root
from conclave.plans.models import ReviewPlanRevision


def load_design_plan_revisions() -> tuple[ReviewPlanRevision, ...]:
    path = design_fixtures_root() / "review-plan-revision.json"
    with path.open(encoding="utf-8") as source:
        fixture = json.load(source)
    return tuple(
        ReviewPlanRevision.model_validate(
            {
                "plan_id": fixture["plan_id"],
                "deployment_id": fixture["deployment_id"],
                **item,
            }
        )
        for item in fixture["revisions"]
    )


def load_request_fixture(name: str = "01-normal-healthy.json") -> dict[str, Any]:
    path = contracts_root() / "fixtures" / "request" / Path(name).name
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def load_feedback_fixture(name: str = "01-beneficial.json") -> dict[str, Any]:
    path = contracts_root() / "fixtures" / "feedback" / Path(name).name
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def build_feedback_for_session(
    *,
    session_id: str,
    evidence_version: str,
    template: str = "01-beneficial.json",
) -> dict[str, Any]:
    document = deepcopy(load_feedback_fixture(template))
    document["review_session_id"] = session_id
    document["evidence_version"] = evidence_version
    return document


def build_request_for_occurrence(
    occurrence: ReviewOccurrenceRecord,
    *,
    template: str = "02-weak-evidence.json",
) -> dict[str, Any]:
    document = deepcopy(load_request_fixture(template))
    due_at = normalize_instant(occurrence.due_at).astimezone(UTC)
    document["caller"] = {
        "caller_id": "conclave-fixture-harness",
        "auth_subject": "local-fixture-worker",
    }
    document["idempotency_key"] = f"fixture:{occurrence.occurrence_id}"
    document["evidence_version"] = f"fixture:{occurrence.occurrence_id}:v1"
    document["review_trigger"] = {
        "occurrence_id": occurrence.occurrence_id,
        "kind": occurrence.trigger_kind,
        "due_at": due_at.isoformat().replace("+00:00", "Z"),
    }
    document["review_plan_ref"] = occurrence.plan_id
    document["review_plan_revision"] = occurrence.plan_revision
    freshness = document["quality"]["freshness"]
    freshness["observed_at"] = due_at.isoformat().replace("+00:00", "Z")
    freshness["metric_period_start"] = (
        (due_at - timedelta(hours=12)).isoformat().replace("+00:00", "Z")
    )
    freshness["metric_period_end"] = (
        (due_at - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    )
    return document
