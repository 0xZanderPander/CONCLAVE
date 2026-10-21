"""Domain-neutral claim primitives shared by every pack.

A claim is one reviewer statement traceable to the immutable request snapshot.
Claim IDs are issued by Conclave after validation, never by the provider.
"""

import hashlib
import re
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssessmentClaim(BaseModel):
    """One review claim with support from the immutable request snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str | None = Field(default=None, pattern=r"^clm_[a-f0-9]{24}$")
    claim_type: Literal[
        "observation",
        "inference",
        "policy_constraint",
        "uncertainty",
    ] = "inference"
    statement: str = Field(min_length=1)
    evidence_references: tuple[str, ...] = ()
    alternative_explanations: tuple[str, ...] = ()

    @field_validator("evidence_references", mode="before")
    @classmethod
    def canonicalize_array_indexes(cls, value: object) -> object:
        if isinstance(value, (list, tuple)):
            return tuple(
                re.sub(r"\[(\d+)\]", r".\1", item) if isinstance(item, str) else item
                for item in value
            )
        return value

    @model_validator(mode="after")
    def validate_unique_references(self) -> "AssessmentClaim":
        if len(self.evidence_references) != len(set(self.evidence_references)):
            raise ValueError("claim evidence references must be unique")
        return self


class PeerClaimReview(BaseModel):
    """A cross reviewer's explicit position on one peer-authored claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(pattern=r"^clm_[a-f0-9]{24}$")
    position: Literal["accept", "challenge", "insufficient_support"]
    summary: str = Field(min_length=1)
    evidence_references: tuple[str, ...] = Field(min_length=1)

    @field_validator("evidence_references", mode="before")
    @classmethod
    def canonicalize_array_indexes(cls, value: object) -> object:
        if isinstance(value, (list, tuple)):
            return tuple(
                re.sub(r"\[(\d+)\]", r".\1", item) if isinstance(item, str) else item
                for item in value
            )
        return value

    @model_validator(mode="after")
    def validate_unique_references(self) -> "PeerClaimReview":
        if len(self.evidence_references) != len(set(self.evidence_references)):
            raise ValueError("peer-claim evidence references must be unique")
        return self


@runtime_checkable
class ClaimBearing(Protocol):
    """Any pack assessment the engine can assign claim IDs to."""

    claims: tuple[str | AssessmentClaim, ...]

    def model_copy(self, *, update: dict) -> "ClaimBearing": ...


def assign_assessment_claim_ids[T: ClaimBearing](
    assessment: T,
    *,
    invocation_id: str,
) -> T:
    """Normalize provider-authored claim drafts into stored structured claims."""

    normalized: list[AssessmentClaim] = []
    for ordinal, claim in enumerate(assessment.claims, start=1):
        if isinstance(claim, str):
            raise ValueError("assessment-v2 claims must be structured")
        if claim.claim_id is not None:
            raise ValueError("assessment-v2 claim IDs are assigned by Conclave")
        digest = hashlib.sha256(f"{invocation_id}|{ordinal}".encode()).hexdigest()[:24]
        normalized.append(claim.model_copy(update={"claim_id": f"clm_{digest}"}))
    return assessment.model_copy(update={"claims": tuple(normalized)})


def public_claim(claim: str | AssessmentClaim) -> dict[str, object]:
    """Caller-facing claim projection used by result and evaluation documents."""

    if isinstance(claim, str):
        return {
            "statement": claim,
            "evidence_references": [],
            "alternative_explanations": [],
        }
    return {
        "statement": claim.statement,
        "evidence_references": list(claim.evidence_references),
        "alternative_explanations": list(claim.alternative_explanations),
    }


def snapshot_path_exists(document: object, reference: str) -> bool:
    """True when a dotted path (``sections.evidence.metrics.cpa_usd``) resolves in the snapshot."""

    from collections.abc import Mapping, Sequence

    if not reference or reference.startswith(".") or reference.endswith("."):
        return False
    current = document
    for segment in reference.split("."):
        if not segment:
            return False
        if isinstance(current, Mapping):
            if segment not in current:
                return False
            current = current[segment]
            continue
        if (
            isinstance(current, Sequence)
            and not isinstance(current, (str, bytes, bytearray))
            and segment.isdigit()
        ):
            index = int(segment)
            if index >= len(current):
                return False
            current = current[index]
            continue
        return False
    return True


def validate_evidence_references(
    document: dict,
    references: tuple[str, ...],
    *,
    label: str,
    allowed_roots: frozenset[str],
) -> None:
    """Every evidence reference must point at an existing path under an allowed root."""

    from conclave.contracts.errors import ContractValidationError

    for reference in references:
        root = reference.split(".", 1)[0]
        if root not in allowed_roots:
            raise ContractValidationError(
                f"{label} evidence reference {reference!r} uses an unsupported root"
            )
        if not snapshot_path_exists(document, reference):
            raise ContractValidationError(
                f"{label} evidence reference {reference!r} does not exist "
                "in the immutable snapshot"
            )
