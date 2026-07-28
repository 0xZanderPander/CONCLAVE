from dataclasses import dataclass

from pydantic import BaseModel

from conclave.domain.enums import ReviewerSlot, ReviewStage
from conclave.reviewers.prompts import (
    REVIEWER_A_CROSS_INSTRUCTIONS,
    REVIEWER_A_CROSS_PROMPT_VERSION,
    REVIEWER_A_CROSS_ROLE_VERSION,
    REVIEWER_A_INSTRUCTIONS,
    REVIEWER_A_PROMPT_VERSION,
    REVIEWER_A_ROLE_VERSION,
    REVIEWER_B_CROSS_INSTRUCTIONS,
    REVIEWER_B_CROSS_PROMPT_VERSION,
    REVIEWER_B_CROSS_ROLE_VERSION,
    REVIEWER_B_INSTRUCTIONS,
    REVIEWER_B_PROMPT_VERSION,
    REVIEWER_B_ROLE_VERSION,
    REVIEWER_C_BLIND_INSTRUCTIONS,
    REVIEWER_C_BLIND_PROMPT_VERSION,
    REVIEWER_C_BLIND_ROLE_VERSION,
    REVIEWER_C_JUDGE_INSTRUCTIONS,
    REVIEWER_C_JUDGE_PROMPT_VERSION,
    REVIEWER_C_JUDGE_ROLE_VERSION,
)
from conclave.reviewers.runtime import (
    Assessment,
    AssessmentV2ProviderOutput,
    CrossReviewV1ProviderOutput,
    ReviewCall,
    ReviewerCJudgmentV2ProviderOutput,
)


@dataclass(frozen=True, slots=True)
class ProviderContract:
    role_version: str
    prompt_version: str
    schema_version: str
    instructions: str
    output_model: type[BaseModel]
    format_name: str


_CONTRACTS = {
    (ReviewerSlot.A, ReviewStage.INDEPENDENT, "assessment-v1"): ProviderContract(
        REVIEWER_A_ROLE_VERSION,
        REVIEWER_A_PROMPT_VERSION,
        "assessment-v1",
        REVIEWER_A_INSTRUCTIONS,
        Assessment,
        "conclave_assessment",
    ),
    (ReviewerSlot.B, ReviewStage.INDEPENDENT, "assessment-v1"): ProviderContract(
        REVIEWER_B_ROLE_VERSION,
        REVIEWER_B_PROMPT_VERSION,
        "assessment-v1",
        REVIEWER_B_INSTRUCTIONS,
        Assessment,
        "conclave_assessment",
    ),
    (ReviewerSlot.A, ReviewStage.INDEPENDENT, "assessment-v2"): ProviderContract(
        REVIEWER_A_ROLE_VERSION,
        REVIEWER_A_PROMPT_VERSION,
        "assessment-v2",
        REVIEWER_A_INSTRUCTIONS,
        AssessmentV2ProviderOutput,
        "conclave_assessment_v2",
    ),
    (ReviewerSlot.B, ReviewStage.INDEPENDENT, "assessment-v2"): ProviderContract(
        REVIEWER_B_ROLE_VERSION,
        REVIEWER_B_PROMPT_VERSION,
        "assessment-v2",
        REVIEWER_B_INSTRUCTIONS,
        AssessmentV2ProviderOutput,
        "conclave_assessment_v2",
    ),
    (ReviewerSlot.A, ReviewStage.CROSS_REVIEW, "cross-review-v1"): ProviderContract(
        REVIEWER_A_CROSS_ROLE_VERSION,
        REVIEWER_A_CROSS_PROMPT_VERSION,
        "cross-review-v1",
        REVIEWER_A_CROSS_INSTRUCTIONS,
        CrossReviewV1ProviderOutput,
        "conclave_cross_review_v1",
    ),
    (ReviewerSlot.B, ReviewStage.CROSS_REVIEW, "cross-review-v1"): ProviderContract(
        REVIEWER_B_CROSS_ROLE_VERSION,
        REVIEWER_B_CROSS_PROMPT_VERSION,
        "cross-review-v1",
        REVIEWER_B_CROSS_INSTRUCTIONS,
        CrossReviewV1ProviderOutput,
        "conclave_cross_review_v1",
    ),
    (ReviewerSlot.C, ReviewStage.INDEPENDENT, "assessment-v2"): ProviderContract(
        REVIEWER_C_BLIND_ROLE_VERSION,
        REVIEWER_C_BLIND_PROMPT_VERSION,
        "assessment-v2",
        REVIEWER_C_BLIND_INSTRUCTIONS,
        AssessmentV2ProviderOutput,
        "conclave_assessment_v2",
    ),
    (ReviewerSlot.C, ReviewStage.JUDGING, "reviewer-c-judgment-v2"): ProviderContract(
        REVIEWER_C_JUDGE_ROLE_VERSION,
        REVIEWER_C_JUDGE_PROMPT_VERSION,
        "reviewer-c-judgment-v2",
        REVIEWER_C_JUDGE_INSTRUCTIONS,
        ReviewerCJudgmentV2ProviderOutput,
        "conclave_reviewer_c_judgment_v2",
    ),
}


def provider_contract_for(call: ReviewCall) -> ProviderContract:
    try:
        contract = _CONTRACTS[(call.slot, call.stage, call.schema_version)]
    except KeyError as exc:
        raise LookupError(
            f"the production contract for reviewer {call.slot.value} during "
            f"{call.stage.value} with schema {call.schema_version!r} is not approved"
        ) from exc
    if (
        call.role_version != contract.role_version
        or call.prompt_version != contract.prompt_version
    ):
        raise LookupError(
            f"reviewer {call.slot.value} role or prompt version is not approved"
        )
    return contract


def validate_provider_context(call: ReviewCall) -> None:
    if call.stage == ReviewStage.INDEPENDENT:
        if (
            call.prior_claims
            or call.own_assessment is not None
            or call.peer_assessments
            or call.cross_review_responses
            or call.comparison_history
        ):
            raise ValueError(
                "an independent reviewer call cannot contain peer-review content"
            )
        return
    if call.stage == ReviewStage.CROSS_REVIEW:
        if call.own_assessment is None:
            raise ValueError("cross review requires the reviewer's own assessment")
        if len(call.peer_assessments) != 1:
            raise ValueError("cross review requires exactly one peer assessment")
        if call.peer_assessments[0].slot == call.slot:
            raise ValueError("cross review peer assessment must use the other slot")
        if call.cross_review_responses:
            raise ValueError("cross review cannot receive completed cross responses")
        if len(call.comparison_history) != 1:
            raise ValueError("cross review requires the initial comparison")
        return
    if call.stage == ReviewStage.JUDGING:
        if call.slot != ReviewerSlot.C:
            raise ValueError("only reviewer C can judge")
        if call.own_assessment is None or call.own_assessment.slot != ReviewerSlot.C:
            raise ValueError("reviewer-C judgment requires C's blind assessment")
        if {item.slot for item in call.cross_review_responses} != {
            ReviewerSlot.A,
            ReviewerSlot.B,
        }:
            raise ValueError("reviewer-C judgment requires A and B cross responses")
        if len(call.comparison_history) != 2:
            raise ValueError("reviewer-C judgment requires both comparison rounds")
