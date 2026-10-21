"""Provider contract resolution and context guards.

The approved (seat, stage, schema) tables are pack-owned. The context guard —
what an independent, cross-review or judging call may carry — is the engine's
isolation invariant and applies to every pack.
"""

from typing import TYPE_CHECKING

from conclave.domain.enums import ReviewerSlot, ReviewStage
from conclave.packs.base import ProviderContract
from conclave.reviewers.runtime import ReviewCall

if TYPE_CHECKING:
    from conclave.packs.registry import PackRegistry

__all__ = ["ProviderContract", "provider_contract_for", "validate_provider_context"]


def provider_contract_for(
    call: ReviewCall,
    *,
    packs: "PackRegistry | None" = None,
) -> ProviderContract:
    if packs is None:
        from conclave.packs.registry import default_pack_registry

        packs = default_pack_registry()
    pack = packs.for_call(call)
    contract = pack.provider_contract(call.slot, call.stage, call.schema_version)
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
