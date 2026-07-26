import json
from datetime import datetime
from functools import lru_cache
from typing import Any

from pydantic import ValidationError

from conclave.contracts.validation import ContractValidationError
from conclave.domain.enums import RecommendationCategory
from conclave.paths import contracts_root
from conclave.reviewers.runtime import Assessment
from conclave.task_packs.models import (
    ComparatorProfile,
    RequestEligibility,
    RequestMateriality,
    TaskPack,
)

_MARKETING_ACTION_DIRECTIONS = {
    "pause_creative": "decrease",
    "retain_creative": "hold",
    "collect_more_data": "observe",
    "diagnose_tracking": "diagnose",
    "freeze_scope": "freeze",
    "propose_experiment": "experiment",
    "budget_increase": "increase",
    "budget_decrease": "decrease",
    "creative_rotation": "change",
    "audience_change": "change",
}

_NON_OPTIMIZATION_ACTIONS = {
    "collect_more_data",
    "diagnose_tracking",
    "freeze_scope",
}


class TaskPackRegistry:
    def __init__(self, task_packs: tuple[TaskPack, ...]) -> None:
        self._task_packs = {task_pack.task_pack_ref: task_pack for task_pack in task_packs}
        if len(self._task_packs) != len(task_packs):
            raise ValueError("task-pack references must be unique")

    def get(self, task_pack_ref: str) -> TaskPack:
        try:
            return self._task_packs[task_pack_ref]
        except KeyError as exc:
            raise ContractValidationError(f"unknown task_pack_ref {task_pack_ref!r}") from exc

    def validate_request(self, document: dict[str, Any]) -> RequestEligibility:
        task_pack = self.get(document["task_pack_ref"])
        self._validate_contract_binding(task_pack, document)
        return self._evaluate_eligibility(task_pack, document)

    def validate_assessment(
        self,
        document: dict[str, Any],
        assessment: Assessment,
    ) -> None:
        task_pack = self.get(document["task_pack_ref"])
        allowed_recommendations = {
            RecommendationCategory(value) for value in document["allowed_recommendations"]
        }
        if assessment.category not in task_pack.allowed_recommendations:
            raise ContractValidationError(
                f"assessment category {assessment.category.value!r} is not registered"
            )
        if assessment.category not in allowed_recommendations:
            raise ContractValidationError(
                f"assessment category {assessment.category.value!r} is not allowed by the request"
            )

        request_actions = set(document["action_ontology"]["allowed_action_types"])
        for action in assessment.actions:
            if action.type not in task_pack.allowed_action_types:
                raise ContractValidationError(
                    f"assessment action {action.type!r} is not registered"
                )
            if action.type not in request_actions:
                raise ContractValidationError(
                    f"assessment action {action.type!r} is not allowed by the request"
                )

        if not document["quality"]["optimization_eligible"]:
            if assessment.category in {
                RecommendationCategory.EXPERIMENT,
                RecommendationCategory.OPERATIONAL_CHANGE,
            }:
                raise ContractValidationError(
                    "optimization-ineligible evidence cannot propose an experiment or change"
                )
            disallowed = {
                action.type
                for action in assessment.actions
                if action.type not in task_pack.non_optimization_action_types
            }
            if disallowed:
                raise ContractValidationError(
                    "optimization-ineligible evidence proposed unsafe actions: "
                    f"{sorted(disallowed)!r}"
                )

        if assessment.category == RecommendationCategory.EXPERIMENT:
            if assessment.experiment is None:
                raise ContractValidationError(
                    "experiment recommendations require an experiment contract"
                )
        elif assessment.experiment is not None:
            raise ContractValidationError(
                "only experiment recommendations may include an experiment contract"
            )

        max_change = (
            document["sections"]
            .get("policy", {})
            .get("change_limits", {})
            .get("max_budget_change_pct")
        )
        if max_change is not None:
            for action in assessment.actions:
                if (
                    action.type in {"budget_increase", "budget_decrease"}
                    and action.magnitude is not None
                    and action.magnitude > max_change
                ):
                    raise ContractValidationError(
                        f"budget change {action.magnitude} exceeds request limit {max_change}"
                    )

    @staticmethod
    def _validate_contract_binding(
        task_pack: TaskPack,
        document: dict[str, Any],
    ) -> None:
        if document["action_ontology"]["profile"] != task_pack.action_profile:
            raise ContractValidationError("action ontology profile does not match task pack")
        request_actions = set(document["action_ontology"]["allowed_action_types"])
        unknown_actions = request_actions - task_pack.allowed_action_types
        if unknown_actions:
            raise ContractValidationError(
                f"request contains unregistered actions: {sorted(unknown_actions)!r}"
            )
        request_recommendations = {
            RecommendationCategory(value) for value in document["allowed_recommendations"]
        }
        unknown_recommendations = request_recommendations - task_pack.allowed_recommendations
        if unknown_recommendations:
            raise ContractValidationError(
                "request contains unregistered recommendation categories: "
                f"{sorted(value.value for value in unknown_recommendations)!r}"
            )
        try:
            supplied_comparator = ComparatorProfile.model_validate(document["comparator"])
        except ValidationError as exc:
            raise ContractValidationError(f"invalid comparator configuration: {exc}") from exc
        if supplied_comparator != task_pack.comparator:
            raise ContractValidationError(
                "request comparator does not match the registered task-pack version"
            )

    @staticmethod
    def _evaluate_eligibility(
        task_pack: TaskPack,
        document: dict[str, Any],
    ) -> RequestEligibility:
        quality = document["quality"]
        freshness = quality["freshness"]
        observed_at = datetime.fromisoformat(freshness["observed_at"].replace("Z", "+00:00"))
        period_start = datetime.fromisoformat(
            freshness["metric_period_start"].replace("Z", "+00:00")
        )
        period_end = datetime.fromisoformat(freshness["metric_period_end"].replace("Z", "+00:00"))
        due_at = datetime.fromisoformat(document["review_trigger"]["due_at"].replace("Z", "+00:00"))
        if period_start > period_end:
            raise ContractValidationError("metric period starts after it ends")
        if period_end > observed_at:
            raise ContractValidationError("metric period ends after evidence was observed")
        if observed_at > due_at:
            raise ContractValidationError("evidence was observed after the review trigger")

        age_hours = (due_at - observed_at).total_seconds() / 3600
        reasons: list[str] = []
        review_eligible = True
        if age_hours > task_pack.max_evidence_age_hours:
            review_eligible = False
            reasons.append("stale_evidence")

        optimization_eligible = bool(quality["optimization_eligible"])
        if quality["tracking_health"] == "unhealthy":
            reasons.append("tracking_unhealthy")
            optimization_eligible = False
        if quality["is_partial"]:
            reasons.append("partial_evidence")
            optimization_eligible = False
        if quality.get("evidence_quality_label") == "insufficient":
            reasons.append("insufficient_evidence")
            optimization_eligible = False
        if optimization_eligible != bool(quality["optimization_eligible"]):
            raise ContractValidationError(
                "quality.optimization_eligible conflicts with task-pack eligibility rules"
            )

        thresholds = document["materiality"]
        required_thresholds = {
            "min_impressions",
            "min_spend_usd",
            "cpa_deviation_material_pct",
        }
        missing_thresholds = required_thresholds - thresholds.keys()
        if missing_thresholds:
            raise ContractValidationError(
                f"materiality is missing thresholds: {sorted(missing_thresholds)!r}"
            )
        if any(
            isinstance(thresholds[name], bool)
            or not isinstance(thresholds[name], int | float)
            or thresholds[name] < 0
            for name in required_thresholds
        ):
            raise ContractValidationError("materiality thresholds must be non-negative numbers")
        try:
            metrics = document["sections"]["evidence"]["metrics"]
        except KeyError as exc:
            raise ContractValidationError(
                "marketing-ads/v1 requires sections.evidence.metrics"
            ) from exc
        for metric_name in ("impressions", "spend_usd"):
            metric_value = metrics.get(metric_name)
            if (
                isinstance(metric_value, bool)
                or not isinstance(metric_value, int | float)
                or metric_value < 0
            ):
                raise ContractValidationError(
                    f"evidence metric {metric_name!r} must be a non-negative number"
                )
        sufficient_volume = (
            metrics["impressions"] >= thresholds["min_impressions"]
            and metrics["spend_usd"] >= thresholds["min_spend_usd"]
        )
        cpa = metrics.get("cpa_usd")
        target_cpa = metrics.get("target_cpa_usd")
        for metric_name, metric_value in (("cpa_usd", cpa), ("target_cpa_usd", target_cpa)):
            if metric_value is not None and (
                isinstance(metric_value, bool)
                or not isinstance(metric_value, int | float)
                or metric_value < 0
            ):
                raise ContractValidationError(
                    f"evidence metric {metric_name!r} must be null or non-negative"
                )
        cpa_deviation = None
        if cpa is not None and target_cpa not in (None, 0):
            cpa_deviation = abs(cpa - target_cpa) / target_cpa
        material = bool(
            sufficient_volume
            and cpa_deviation is not None
            and cpa_deviation >= thresholds["cpa_deviation_material_pct"]
        )
        return RequestEligibility(
            review_eligible=review_eligible,
            optimization_eligible=optimization_eligible,
            reasons=tuple(reasons),
            observed_at=observed_at,
            evidence_age_hours=age_hours,
            materiality=RequestMateriality(
                sufficient_volume=sufficient_volume,
                cpa_deviation=cpa_deviation,
                material=material,
            ),
        )


def _marketing_ads_task_pack() -> TaskPack:
    path = contracts_root() / "profiles" / "marketing-ads.v1.json"
    with path.open(encoding="utf-8") as source:
        raw_profile = json.load(source)
    comparator = ComparatorProfile.model_validate(
        {
            "profile": raw_profile["profile"],
            "tolerance": raw_profile["tolerance"],
            "dimensions": raw_profile["dimensions"],
            "hard_triggers": raw_profile["hard_triggers"],
        }
    )
    return TaskPack(
        task_pack_ref="marketing-ads/v1",
        action_profile="marketing-ads/v1",
        allowed_recommendations=frozenset(RecommendationCategory),
        allowed_action_types=frozenset(_MARKETING_ACTION_DIRECTIONS),
        non_optimization_action_types=frozenset(_NON_OPTIMIZATION_ACTIONS),
        action_directions=_MARKETING_ACTION_DIRECTIONS,
        comparator=comparator,
        max_evidence_age_hours=24,
    )


@lru_cache(maxsize=1)
def default_task_pack_registry() -> TaskPackRegistry:
    return TaskPackRegistry((_marketing_ads_task_pack(),))
