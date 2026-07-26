import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, FormatChecker

from conclave.paths import contracts_root


class ContractValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ContractValidationReport:
    request_count: int
    result_count: int
    feedback_count: int
    comparator_case_count: int


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _validate_json(schema_path: Path, fixture_paths: list[Path]) -> None:
    schema = _load(schema_path)
    Draft7Validator.check_schema(schema)
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for fixture_path in fixture_paths:
        fixture = _load(fixture_path)
        for error in sorted(validator.iter_errors(fixture), key=lambda item: list(item.path)):
            location = ".".join(str(part) for part in error.path) or "$"
            errors.append(f"{fixture_path.name}:{location}: {error.message}")
    if errors:
        raise ContractValidationError("\n".join(errors))


def validate_review_request(
    document: dict[str, Any],
    root: Path | None = None,
) -> None:
    root = root or contracts_root()
    schema = _load(root / "schemas" / "review-request.v1.schema.json")
    Draft7Validator.check_schema(schema)
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    if errors:
        messages = []
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "$"
            messages.append(f"{location}: {error.message}")
        raise ContractValidationError("\n".join(messages))
    _validate_classification(document, "review request")


def validate_review_result(
    document: dict[str, Any],
    request: dict[str, Any],
    root: Path | None = None,
) -> None:
    root = root or contracts_root()
    schema = _load(root / "schemas" / "review-result.v1.schema.json")
    Draft7Validator.check_schema(schema)
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    if errors:
        messages = []
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "$"
            messages.append(f"{location}: {error.message}")
        raise ContractValidationError("\n".join(messages))
    _validate_request_result_pair(request, document, "review result")


def _leaf_paths(value: Any, path: str) -> list[str]:
    if isinstance(value, dict):
        return [
            leaf for key, child in value.items() for leaf in _leaf_paths(child, f"{path}.{key}")
        ]
    if isinstance(value, list):
        if not value:
            return [path]
        return [leaf for child in value for leaf in _leaf_paths(child, path)]
    return [path]


def _validate_classification(request: dict[str, Any], name: str) -> None:
    classified = [
        (bucket, declared_path)
        for bucket, paths in request["classification"].items()
        for declared_path in paths
    ]
    leaves = _leaf_paths(request["sections"], "sections")
    leaves.extend(_leaf_paths(request["quality"], "quality"))

    errors: list[str] = []
    for leaf in leaves:
        matches = [
            bucket
            for bucket, declared_path in classified
            if leaf == declared_path or leaf.startswith(f"{declared_path}.")
        ]
        if not matches:
            errors.append(f"{name}: unclassified field {leaf}")
        if len(set(matches)) > 1:
            errors.append(f"{name}: conflicting classification for {leaf}: {matches}")
    if errors:
        raise ContractValidationError("\n".join(errors))


def _validate_request_result_pair(
    request: dict[str, Any],
    result: dict[str, Any],
    name: str,
) -> None:
    if result["request_idempotency_key"] != request["idempotency_key"]:
        raise ContractValidationError(f"{name}: idempotency correlation does not match")
    if result["occurrence_id"] != request["review_trigger"]["occurrence_id"]:
        raise ContractValidationError(f"{name}: occurrence correlation does not match")

    recommendation = result["recommendation"]
    if recommendation["category"] not in request["allowed_recommendations"]:
        raise ContractValidationError(f"{name}: recommendation category is not allowed")

    allowed_actions = set(request["action_ontology"]["allowed_action_types"])
    for action in recommendation["actions"]:
        if action["type"] not in allowed_actions:
            raise ContractValidationError(f"{name}: action {action['type']!r} is not allowed")

    if (
        not request["quality"]["optimization_eligible"]
        and recommendation["category"] == "operational_change"
    ):
        raise ContractValidationError(f"{name}: ineligible evidence proposed optimization")

    if result["status"] == "auto_resolved":
        safe_category = recommendation["category"] in {"observe", "collect_more_data"}
        safe = (
            safe_category
            and not recommendation["actions"]
            and result.get("risk") == "low"
            and result["panel_metadata"]["tie_breaker"] is None
        )
        if not safe:
            raise ContractValidationError(f"{name}: unsafe auto-resolution")

    if result["disagreement"]["level"] == "tie_broken":
        reviewers = result["panel_metadata"]["reviewers"]
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
        if (
            not independent
            or not judging
            or min(independent) >= min(judging)
            or result["status"] != "caller_decision_required"
        ):
            raise ContractValidationError(f"{name}: invalid reviewer-C ordering")


def _validate_comparator(root: Path) -> int:
    profile = _load(root / "profiles" / "marketing-ads.v1.json")
    weights = {item["name"]: item["weight"] for item in profile["dimensions"]}
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-12):
        raise ContractValidationError("comparator weights must total 1.0")

    cases = _load(root / "fixtures" / "comparator" / "marketing-v1-cases.json")["cases"]
    for case in cases:
        weighted = sum(
            weights[dimension] * distance
            for dimension, distance in case["dimension_distances"].items()
        )
        actual = 1.0 if case["hard_triggers"] else weighted
        expected_cross_review = bool(case["hard_triggers"]) or weighted > profile["tolerance"]
        if not math.isclose(actual, case["expected_distance"], abs_tol=1e-12):
            raise ContractValidationError(f"comparator case {case['id']} distance mismatch")
        if expected_cross_review != case["expected_cross_review"]:
            raise ContractValidationError(f"comparator case {case['id']} cross-review mismatch")
    return len(cases)


def validate_contract_package(root: Path | None = None) -> ContractValidationReport:
    root = root or contracts_root()
    schema_root = root / "schemas"
    fixture_root = root / "fixtures"
    request_paths = sorted((fixture_root / "request").glob("*.json"))
    result_paths = sorted((fixture_root / "result").glob("*.json"))
    feedback_paths = sorted((fixture_root / "feedback").glob("*.json"))

    _validate_json(schema_root / "review-request.v1.schema.json", request_paths)
    _validate_json(schema_root / "review-result.v1.schema.json", result_paths)
    _validate_json(schema_root / "review-feedback.v1.schema.json", feedback_paths)

    requests = {path.name[:2]: _load(path) for path in request_paths}
    results = {path.name[:2]: _load(path) for path in result_paths}
    if requests.keys() != results.keys():
        raise ContractValidationError("request and result fixture IDs do not match")

    for fixture_id, request in requests.items():
        _validate_classification(request, f"request {fixture_id}")
        _validate_request_result_pair(
            request,
            results[fixture_id],
            f"fixture pair {fixture_id}",
        )

    comparator_count = _validate_comparator(root)
    return ContractValidationReport(
        request_count=len(request_paths),
        result_count=len(result_paths),
        feedback_count=len(feedback_paths),
        comparator_case_count=comparator_count,
    )
