"""Chimera's approved (seat, stage, schema) -> provider contract table.

Moved from ``conclave.reviewers.provider_contracts`` in B2.
"""

from conclave.domain.enums import ReviewerSlot, ReviewStage
from conclave.packs.base import ProviderContract
from conclave.packs.chimera.models import (
    Assessment,
    AssessmentV2ProviderOutput,
    CrossReviewV1ProviderOutput,
    ReviewerCJudgmentV2ProviderOutput,
)
from conclave.packs.chimera.prompts import (
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

CONTRACTS: dict[tuple[ReviewerSlot, ReviewStage, str], ProviderContract] = {
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
