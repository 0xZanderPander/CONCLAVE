"""Cerberus's approved (seat, stage, schema) -> provider contract table."""

from conclave.domain.enums import ReviewerSlot, ReviewStage
from conclave.packs.base import ProviderContract
from conclave.packs.cerberus.models import (
    VentureAssessmentProviderOutput,
    VentureCrossReviewProviderOutput,
    VentureJudgmentProviderOutput,
)
from conclave.packs.cerberus.prompts import (
    ASSESSOR_A_CROSS_INSTRUCTIONS,
    ASSESSOR_A_CROSS_PROMPT_VERSION,
    ASSESSOR_A_CROSS_ROLE_VERSION,
    ASSESSOR_A_INSTRUCTIONS,
    ASSESSOR_A_PROMPT_VERSION,
    ASSESSOR_A_ROLE_VERSION,
    AUDITOR_B_CROSS_INSTRUCTIONS,
    AUDITOR_B_CROSS_PROMPT_VERSION,
    AUDITOR_B_CROSS_ROLE_VERSION,
    AUDITOR_B_INSTRUCTIONS,
    AUDITOR_B_PROMPT_VERSION,
    AUDITOR_B_ROLE_VERSION,
    JUDGE_C_BLIND_INSTRUCTIONS,
    JUDGE_C_BLIND_PROMPT_VERSION,
    JUDGE_C_BLIND_ROLE_VERSION,
    JUDGE_C_JUDGE_INSTRUCTIONS,
    JUDGE_C_JUDGE_PROMPT_VERSION,
    JUDGE_C_JUDGE_ROLE_VERSION,
)

ASSESSMENT_SCHEMA = "venture-assessment-v1"
CROSS_REVIEW_SCHEMA = "venture-cross-review-v1"
JUDGMENT_SCHEMA = "venture-judgment-v1"

CONTRACTS: dict[tuple[ReviewerSlot, ReviewStage, str], ProviderContract] = {
    (ReviewerSlot.A, ReviewStage.INDEPENDENT, ASSESSMENT_SCHEMA): ProviderContract(
        ASSESSOR_A_ROLE_VERSION,
        ASSESSOR_A_PROMPT_VERSION,
        ASSESSMENT_SCHEMA,
        ASSESSOR_A_INSTRUCTIONS,
        VentureAssessmentProviderOutput,
        "conclave_venture_assessment_v1",
    ),
    (ReviewerSlot.B, ReviewStage.INDEPENDENT, ASSESSMENT_SCHEMA): ProviderContract(
        AUDITOR_B_ROLE_VERSION,
        AUDITOR_B_PROMPT_VERSION,
        ASSESSMENT_SCHEMA,
        AUDITOR_B_INSTRUCTIONS,
        VentureAssessmentProviderOutput,
        "conclave_venture_assessment_v1",
    ),
    (ReviewerSlot.A, ReviewStage.CROSS_REVIEW, CROSS_REVIEW_SCHEMA): ProviderContract(
        ASSESSOR_A_CROSS_ROLE_VERSION,
        ASSESSOR_A_CROSS_PROMPT_VERSION,
        CROSS_REVIEW_SCHEMA,
        ASSESSOR_A_CROSS_INSTRUCTIONS,
        VentureCrossReviewProviderOutput,
        "conclave_venture_cross_review_v1",
    ),
    (ReviewerSlot.B, ReviewStage.CROSS_REVIEW, CROSS_REVIEW_SCHEMA): ProviderContract(
        AUDITOR_B_CROSS_ROLE_VERSION,
        AUDITOR_B_CROSS_PROMPT_VERSION,
        CROSS_REVIEW_SCHEMA,
        AUDITOR_B_CROSS_INSTRUCTIONS,
        VentureCrossReviewProviderOutput,
        "conclave_venture_cross_review_v1",
    ),
    (ReviewerSlot.C, ReviewStage.INDEPENDENT, ASSESSMENT_SCHEMA): ProviderContract(
        JUDGE_C_BLIND_ROLE_VERSION,
        JUDGE_C_BLIND_PROMPT_VERSION,
        ASSESSMENT_SCHEMA,
        JUDGE_C_BLIND_INSTRUCTIONS,
        VentureAssessmentProviderOutput,
        "conclave_venture_assessment_v1",
    ),
    (ReviewerSlot.C, ReviewStage.JUDGING, JUDGMENT_SCHEMA): ProviderContract(
        JUDGE_C_JUDGE_ROLE_VERSION,
        JUDGE_C_JUDGE_PROMPT_VERSION,
        JUDGMENT_SCHEMA,
        JUDGE_C_JUDGE_INSTRUCTIONS,
        VentureJudgmentProviderOutput,
        "conclave_venture_judgment_v1",
    ),
}
