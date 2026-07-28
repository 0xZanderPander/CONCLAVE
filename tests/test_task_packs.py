import json
from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from conclave.contracts.validation import ContractValidationError
from conclave.domain.enums import RecommendationCategory, ReviewState
from conclave.events.models import DomainEventType
from conclave.fixtures import load_design_plan_revisions, load_request_fixture
from conclave.intake import ReviewIntakeService
from conclave.ledger.repository import (
    LedgerConflictError,
    canonical_hash,
)
from conclave.paths import contracts_root
from conclave.reviewers.runtime import (
    Assessment,
    AssessmentClaim,
    RecommendedAction,
    assign_assessment_claim_ids,
)
from conclave.task_packs.comparison import compare_assessments
from conclave.task_packs.models import ComparatorDimension, HardTrigger
from conclave.task_packs.registry import default_task_pack_registry
from tests.helpers import create_test_engine, create_test_repository


def _assessment(
    *,
    category: RecommendationCategory = RecommendationCategory.COLLECT_MORE_DATA,
    action: RecommendedAction | None = None,
    material: bool = False,
    risk: str = "low",
    evidence_quality: str = "adequate",
    tracking_health: str | None = "healthy",
    optimization_eligible: bool | None = True,
) -> Assessment:
    return Assessment(
        category=category,
        summary="Structured fixture assessment.",
        claims=("fixture claim",),
        actions=(action,) if action else (),
        material=material,
        risk=risk,
        confidence=0.8,
        evidence_quality=evidence_quality,
        expected_goal_impact="uncertain",
        tracking_health=tracking_health,
        optimization_eligible=optimization_eligible,
        primary_conversion="eligible_giveaway_entry_completed",
    )


def test_registered_task_pack_matches_request_and_calculates_materiality() -> None:
    registry = default_task_pack_registry()

    normal = registry.validate_request(load_request_fixture("01-normal-healthy.json"))
    weak = registry.validate_request(load_request_fixture("02-weak-evidence.json"))

    assert normal.review_eligible
    assert normal.optimization_eligible
    assert not normal.materiality.material
    assert weak.review_eligible
    assert not weak.optimization_eligible
    assert weak.materiality.material
    assert set(weak.reasons) == {"partial_evidence", "insufficient_evidence"}


def test_task_pack_normalizes_model_supplied_deterministic_facts() -> None:
    registry = default_task_pack_registry()
    document = load_request_fixture()
    assessment = _assessment(
        category=RecommendationCategory.OPERATIONAL_CHANGE,
        material=False,
        tracking_health="unhealthy",
        optimization_eligible=False,
    ).model_copy(update={"primary_conversion": "model-invented-event"})

    normalized = registry.normalize_assessment(document, assessment)

    assert normalized.material
    assert normalized.tracking_health == document["quality"]["tracking_health"]
    assert (
        normalized.optimization_eligible
        == document["quality"]["optimization_eligible"]
    )
    assert (
        normalized.primary_conversion
        == document["sections"]["goal"]["primary_conversion"]
    )
    registry.validate_assessment(document, normalized)


def test_assessment_v2_validates_structured_claim_snapshot_references() -> None:
    registry = default_task_pack_registry()
    document = load_request_fixture()
    assessment = assign_assessment_claim_ids(
        Assessment(
            category=RecommendationCategory.COLLECT_MORE_DATA,
            summary="Collect more evidence.",
            claims=(
                AssessmentClaim(
                    claim_type="inference",
                    statement="The current conversion sample is limited.",
                    evidence_references=(
                        "sections.evidence.metrics.primary_conversions",
                        "quality.optimization_eligible",
                    ),
                    alternative_explanations=(
                        "Performance may change with more observations.",
                    ),
                ),
            ),
            material=False,
            risk="low",
            confidence=0.75,
            evidence_quality="adequate",
            expected_goal_impact="uncertain",
            tracking_health="healthy",
            optimization_eligible=True,
            primary_conversion="eligible_giveaway_entry_completed",
        ),
        invocation_id="inv_claim_validation",
    )

    registry.validate_assessment(
        document,
        assessment,
        schema_version="assessment-v2",
    )


@pytest.mark.parametrize(
    ("references", "message"),
    [
        ((), "has no evidence references"),
        (("sections.evidence.metrics.not_present",), "does not exist"),
        (("caller.auth_subject",), "unsupported root"),
    ],
)
def test_assessment_v2_rejects_invalid_snapshot_references(
    references: tuple[str, ...],
    message: str,
) -> None:
    registry = default_task_pack_registry()
    document = load_request_fixture()
    assessment = assign_assessment_claim_ids(
        Assessment(
            category=RecommendationCategory.COLLECT_MORE_DATA,
            summary="Collect more evidence.",
            claims=(
                AssessmentClaim(
                    statement="Unsupported claim.",
                    evidence_references=references,
                ),
            ),
            material=False,
            risk="low",
            confidence=0.75,
            evidence_quality="adequate",
            expected_goal_impact="uncertain",
            tracking_health="healthy",
            optimization_eligible=True,
            primary_conversion="eligible_giveaway_entry_completed",
        ),
        invocation_id=f"inv_invalid_{message}",
    )

    with pytest.raises(ContractValidationError, match=message):
        registry.validate_assessment(
            document,
            assessment,
            schema_version="assessment-v2",
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda document: document["comparator"].update({"tolerance": 0.9}),
            "comparator does not match",
        ),
        (
            lambda document: document["action_ontology"]["allowed_action_types"].append(
                "unregistered_action"
            ),
            "unregistered actions",
        ),
        (
            lambda document: document["quality"].update(
                {"tracking_health": "unhealthy", "optimization_eligible": True}
            ),
            "optimization_eligible conflicts",
        ),
        (
            lambda document: document["materiality"].pop("min_spend_usd"),
            "missing thresholds",
        ),
    ],
)
def test_task_pack_rejects_unregistered_or_inconsistent_request_configuration(
    mutation,
    message: str,
) -> None:
    document = load_request_fixture()
    mutation(document)

    with pytest.raises(ContractValidationError, match=message):
        default_task_pack_registry().validate_request(document)


def test_stale_evidence_is_snapshotted_then_enters_explicit_terminal_state() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        document = deepcopy(load_request_fixture())
        due_at = document["review_trigger"]["due_at"]
        observed_at = datetime.fromisoformat(due_at.replace("Z", "+00:00")) - timedelta(hours=25)
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

        accepted = ReviewIntakeService(repository).accept(document)

        assert accepted.state == ReviewState.STALE_OR_INELIGIBLE_EVIDENCE
        assert accepted.eligibility_reasons == ("stale_evidence",)
        assert repository.get_snapshot(accepted.session_id) is not None
        validation_event = next(
            event
            for event in repository.list_events(accepted.session_id)
            if event.event_type == DomainEventType.REQUEST_VALIDATED
        )
        assert not validation_event.payload["review_eligible"]
        assert validation_event.payload["reasons"] == ["stale_evidence"]
    finally:
        engine.dispose()


def test_intake_pins_one_immutable_task_pack_revision() -> None:
    engine = create_test_engine()
    repository = create_test_repository(engine)
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(revision)
        accepted = ReviewIntakeService(repository).accept(load_request_fixture())
        session = repository.get_session(accepted.session_id)
        pinned = repository.get_task_pack_revision(accepted.task_pack_hash)

        assert session is not None
        assert session.task_pack_hash == accepted.task_pack_hash
        assert pinned is not None
        assert pinned.task_pack_ref == "marketing-ads/v1"

        changed = deepcopy(pinned.document)
        changed["max_evidence_age_hours"] = 48
        with pytest.raises(LedgerConflictError, match="cannot be reused"):
            repository.register_task_pack_revision(
                task_pack_ref=pinned.task_pack_ref,
                content_hash=canonical_hash(changed),
                document=changed,
            )
    finally:
        engine.dispose()


def test_assessment_validation_enforces_request_ontology_and_eligibility() -> None:
    registry = default_task_pack_registry()
    weak = load_request_fixture("02-weak-evidence.json")
    unsafe = _assessment(
        category=RecommendationCategory.OPERATIONAL_CHANGE,
        action=RecommendedAction(
            type="budget_increase",
            target_id="campaign",
            magnitude=0.1,
            confidence=0.8,
        ),
        optimization_eligible=False,
    )

    with pytest.raises(ContractValidationError, match="optimization-ineligible"):
        registry.validate_assessment(weak, unsafe)


def test_comparator_reproduces_weighted_magnitude_case_and_conservative_merge() -> None:
    task_pack = default_task_pack_registry().get("marketing-ads/v1")
    left = _assessment(
        category=RecommendationCategory.OPERATIONAL_CHANGE,
        action=RecommendedAction(
            type="budget_increase",
            target_id="campaign",
            magnitude=0.1,
            confidence=0.9,
        ),
    )
    right = _assessment(
        category=RecommendationCategory.OPERATIONAL_CHANGE,
        action=RecommendedAction(
            type="budget_increase",
            target_id="campaign",
            magnitude=0.2,
            confidence=0.7,
        ),
    )

    comparison = compare_assessments(left, right, task_pack)

    assert comparison.dimension_distances[ComparatorDimension.MAGNITUDE_EXPOSURE] == pytest.approx(
        0.5
    )
    assert comparison.weighted_distance == pytest.approx(0.04)
    assert not comparison.requires_cross_review
    assert comparison.merged_assessment is not None
    assert comparison.merged_assessment.actions[0].magnitude == 0.1
    assert comparison.merged_assessment.actions[0].confidence == 0.7


def test_comparator_hard_trigger_overrides_weighted_distance() -> None:
    task_pack = default_task_pack_registry().get("marketing-ads/v1")
    left = _assessment(
        category=RecommendationCategory.OPERATIONAL_CHANGE,
        action=RecommendedAction(
            type="budget_increase",
            target_id="campaign",
            magnitude=0.1,
            confidence=0.8,
        ),
    )
    right = _assessment(
        category=RecommendationCategory.OPERATIONAL_CHANGE,
        action=RecommendedAction(
            type="budget_decrease",
            target_id="campaign",
            magnitude=0.1,
            confidence=0.8,
        ),
    )

    comparison = compare_assessments(left, right, task_pack)

    assert comparison.distance == 1
    assert comparison.requires_cross_review
    assert HardTrigger.OPPOSITE_ACTION_DIRECTION in comparison.hard_triggers


def test_assessment_pair_fixtures_reproduce_comparator_decisions() -> None:
    path = (
        contracts_root()
        / "fixtures"
        / "comparator"
        / "marketing-v1-assessment-pairs.json"
    )
    with path.open(encoding="utf-8") as source:
        document = json.load(source)
    task_pack = default_task_pack_registry().get(document["profile"])

    for case in document["cases"]:
        left = Assessment.model_validate({**document["defaults"], **case["left"]})
        right = Assessment.model_validate({**document["defaults"], **case["right"]})
        comparison = compare_assessments(left, right, task_pack)

        assert comparison.weighted_distance == pytest.approx(
            case["expected_weighted_distance"]
        ), case["id"]
        assert {trigger.value for trigger in comparison.hard_triggers} == set(
            case["expected_hard_triggers"]
        ), case["id"]
        assert comparison.requires_cross_review == case["expected_cross_review"], case["id"]
        for dimension, expected in case["expected_dimensions"].items():
            assert comparison.dimension_distances[ComparatorDimension(dimension)] == pytest.approx(
                expected
            ), case["id"]
        if expected_urgency := case.get("expected_merged_urgency"):
            assert comparison.merged_assessment is not None
            assert comparison.merged_assessment.actions[0].urgency == expected_urgency
