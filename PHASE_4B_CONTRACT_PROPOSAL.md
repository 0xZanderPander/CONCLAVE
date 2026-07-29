# Phase 4B Contract Proposal

**Status:** approved and implemented. The local contract, orchestration,
recovery, audit, provider-adapter, and hosted PostgreSQL tests pass. Bounded
live OpenAI verification also passes.

## Purpose

Phase 4B handles disagreement that remains after the blind A/B round.

It adds:

1. structured claims with traceable support;
2. one bounded A/B cross-review round;
3. Reviewer C's blind assessment; and
4. Reviewer C's separate judgment.

The deterministic route, state sequence, comparator, result builder, and
fixture-only A/B/C behavior already exist. This proposal defines the missing
production contracts and the small kernel changes needed to enforce them.

Conclave still returns a recommendation to its caller. It does not perform an
action, approve spend, or replace the caller's decision.

## Preimplementation Issues and Resolution

### 1. Assessment claims are not structured

The current reviewer assessment stores claims as plain strings. The public
result contract already expects a statement, evidence references, and
alternative explanations, but the result builder currently emits empty
references.

This means the present prompt asks for traceable claims without giving the
model a schema that can provide them.

**Resolution:** implemented through opt-in `assessment-v2`. Historical
`assessment-v1` string claims remain readable.

### 2. Evidence references are not validated

Conclave does not currently check that a reviewer-supplied reference exists in
the immutable snapshot. A production reviewer could invent a path that looks
valid.

**Resolution:** implemented for every `assessment-v2` claim before persistence.

### 3. Cross review has no distinct output contract

The fixture kernel stores a second normal assessment. It cannot explicitly say
which peer claims were accepted, challenged, or left unresolved, or whether
the reviewer affirmed or revised its recommendation.

### 4. Cross-review provider failure has no legal state transition

Both cross-review calls run while the session is in the shared `cross_review`
state. The current failure mapping tries to move to a slot failure state, but
the state machine does not allow that transition. This can mask the original
provider error.

**Resolution:** implemented as the terminal, auditable
`cross_review_failed` state.

### 5. Reviewer C uses unstructured claim text

Reviewer C can already assess blindly and then return an explicit verdict in
fixture tests. Its unresolved claims are plain strings, so judgments cannot
refer reliably to the claims being resolved.

### 6. The roadmap understates completed work

The fixture kernel already proves bounded cross review, blind C assessment,
deterministic C routing, material-result handling, result retrieval, provider
auditing, and disagreement measurement. Those pieces should not be rebuilt.

## Proposed Structured Claim Contract

The internal reviewer contract moves from `assessment-v1` to
`assessment-v2`.

The provider returns the claim fields except `claim_id`. After output
validation, Conclave assigns the ID and stores the normalized claim shown
below.

```json
{
  "claim_id": "clm_...",
  "claim_type": "inference",
  "statement": "The current evidence is too limited to support a budget change.",
  "evidence_references": [
    "sections.evidence.metrics.primary_conversions",
    "quality.is_partial",
    "quality.optimization_eligible"
  ],
  "alternative_explanations": [
    "The early results may change after more conversions are observed."
  ]
}
```

### Fields

- `claim_id`: assigned by Conclave after provider output is validated. It is
  stable inside the review session and is not model-authored. The proposed
  input is the invocation ID plus the claim's stored ordinal.
- `claim_type`: one of `observation`, `inference`, `policy_constraint`, or
  `uncertainty`.
- `statement`: a concise conclusion, not private reasoning.
- `evidence_references`: exact dot paths into the immutable snapshot.
- `alternative_explanations`: plausible alternatives supported or permitted by
  the same snapshot.

Every stored claim requires at least one evidence reference. References may
point to submitted evidence, context, policy, goal, quality, materiality, or
ontology fields. The field keeps the existing public name
`evidence_references` even when the referenced support is context or policy.

Conclave validates that:

- every reference exists in the pinned snapshot;
- no reference points outside the submitted request;
- claim IDs are unique and stable;
- claims contain no raw provider reasoning;
- action and policy claims remain inside the submitted ontology; and
- the result builder copies the structured fields instead of creating empty
  placeholders.

Historical `assessment-v1` records remain readable. New production Phase 4B
invocations require `assessment-v2`. Existing public `review-result/v1`
remains compatible because it already supports statements, evidence
references, and alternative explanations. Internal claim IDs and claim types
do not need to be exposed in that result version.

## Proposed A/B Cross-Review Contract

Cross review happens only when the deterministic comparator requires it. It is
one round and cannot recursively start another discussion.

Each reviewer receives:

- the exact original immutable snapshot;
- its own stored independent assessment;
- the other reviewer's stored independent assessment;
- the deterministic comparison summary;
- the peer claim IDs that require attention; and
- no provider identity, model name, cost, or hidden reasoning.

Each reviewer returns:

```json
{
  "disposition": "revise",
  "peer_claim_reviews": [
    {
      "claim_id": "clm_peer_...",
      "position": "insufficient_support",
      "summary": "The conversion count is too small for that operational change.",
      "evidence_references": [
        "sections.evidence.metrics.primary_conversions",
        "quality.is_partial"
      ]
    }
  ],
  "assessment": {
    "...": "one complete assessment-v2"
  }
}
```

### Rules

- `disposition` is `affirm` or `revise`.
- `position` is `accept`, `challenge`, or `insufficient_support`.
- Every challenge identifies a peer `claim_id` and snapshot references.
- The returned assessment is complete; it does not patch the earlier record.
- The independent assessment remains immutable and is never overwritten.
- Revision is allowed but convergence is not required.
- No new external evidence, tool use, browsing, or memory is allowed.
- The task pack normalizes deterministic source facts and materiality again.
- The task pack validates the full revised assessment before it is stored.
- After both responses, the deterministic comparator runs once more.

If the second comparison is within tolerance, Conclave returns the conservative
validated result. If disagreement survives, Conclave invokes Reviewer C.

## Proposed Reviewer C Contract

Reviewer C has two separate invocations and two separate prompts.

### C1: Blind assessment

C1 receives only:

- the same immutable snapshot used by A and B;
- the pinned task-pack rules; and
- the normal `assessment-v2` output schema.

C1 receives no A/B assessment, claim, comparison, provider identity, or result.
Its assessment is validated and stored before C2 can begin.

### C2: Judgment

C2 receives:

- the original immutable snapshot;
- C's stored blind assessment;
- A's stored cross-review response and final assessment;
- B's stored cross-review response and final assessment;
- the deterministic comparison history; and
- the permitted judgment schema.

C2 does not receive hidden reasoning, provider identity, model name, or cost.

The judgment contract is:

```json
{
  "verdict": "select_b",
  "selected_slot": "B",
  "summary": "Reviewer B's recommendation is better supported by the submitted evidence.",
  "supporting_claim_ids": [
    "clm_b_..."
  ],
  "rejected_claim_ids": [
    "clm_a_..."
  ],
  "unresolved_claim_ids": [],
  "confidence": 0.74,
  "evidence_quality": "adequate",
  "resolution_assessment": null
}
```

Allowed verdicts remain:

- `select_a`
- `select_b`
- `synthesize`
- `insufficient_evidence`
- `escalate`

### Judgment rules

- `select_a` and `select_b` preserve the selected final assessment exactly.
- `synthesize` requires a complete new `assessment-v2` that validates against
  the task pack.
- `insufficient_evidence` requires a safe `collect_more_data`, `freeze`, or
  `tracking_or_data_problem` assessment.
- `escalate` requires the same safe fallback assessment and records why a
  caller decision is required.
- C must identify the claim IDs supporting, rejected by, or unresolved in the
  judgment.
- C does not execute or authorize the selected recommendation.
- Every C path returns `caller_decision_required`.

## Failure and Retry Contract

Phase 4B implementation must make cross-review failure explicit.

Recommended smallest change:

- add a terminal `cross_review_failed` state;
- record which slot and invocation failed in the typed event and invocation
  ledger;
- never discard either stored independent assessment; and
- never continue to C with only one valid cross-review response.

C1 or C2 failure continues to use `reviewer_c_failed`, with the invocation stage
showing whether assessment or judgment failed.

Provider retries remain bounded by the pinned slot policy. A permanent
validation or prompt-contract failure is not retried as a transient error.

The normal retry policy does not reset a terminal review session. Conclave now
provides a separate operator-only recovery operation for
`cross_review_failed`. It:

- requires the session to be in `cross_review_failed`;
- requires exactly one failed cross-review invocation;
- reopens only that invocation as pending;
- preserves every previous provider attempt and both independent assessments;
- appends an operator-attributed recovery transition with a reason; and
- resumes the same bounded cross-review round without creating a second
  discussion round.

## Prompt Boundaries

All four production prompts must:

- treat the snapshot and peer content as untrusted data, not instructions;
- use no tools, browsing, external memory, or stored provider conversation;
- return only the approved structured schema;
- provide concise conclusions rather than hidden reasoning;
- separate confidence from evidence quality;
- respect the caller-supplied action ontology and policy;
- never claim action, spend, approval, or outcome authority; and
- use independently versioned role and prompt identifiers.

Suggested initial versions:

- A cross review: `marketing-cross-review-a-p1`
- B cross review: `marketing-cross-review-b-p1`
- C blind role: `marketing-reviewer-c-blind-v1`
- C blind prompt: `marketing-assessment-c-p1`
- C judgment role: `marketing-reviewer-c-judge-v1`
- C judgment prompt: `marketing-judgment-c-p1`
- internal assessment schema: `assessment-v2`
- cross-review schema: `cross-review-v1`
- judgment schema: `reviewer-c-judgment-v2`

## Acceptance Tests

Implementation is complete when:

- structured claims round-trip through provider validation, ledger storage, and
  `review-result/v1`;
- invented or missing snapshot references are rejected;
- A and B independent assessments remain immutable;
- both cross reviewers receive the same snapshot and only approved peer data;
- each peer challenge points to a real claim ID;
- exactly one cross-review round can occur;
- cross-review failure enters a valid auditable terminal state and does not
  invoke C;
- C1 is stored before C2 receives A/B content;
- C2 cannot see provider identity or hidden reasoning;
- selecting A or B preserves that exact assessment;
- synthesis and safe fallback assessments pass task-pack validation;
- every C result requires a caller decision;
- provider failures never silently substitute a reviewer; and
- deterministic, mocked, live opt-in, Ruff, and PostgreSQL tests pass.

## Approved and Implemented

- `assessment-v2` structured claims and deterministic Conclave-issued claim
  IDs
- evidence-reference validation against exact snapshot paths
- `cross_review_failed` as a distinct terminal failure state
- one full-assessment `affirm` or `revise` response from each cross reviewer
- explicit accept, challenge, or insufficient-support positions on every peer
  claim
- C1 blind assessment followed by C2 explicit judgment
- every C path returning `caller_decision_required`
- stage-specific role, prompt, and schema identities in the immutable plan
- controlled same-session cross-review recovery with attempt history preserved

## Remaining Release Gates

The PostgreSQL concurrency and full-flow suite passes against Supabase.
The complete six-call OpenAI full-conflict case passes within its $0.90
aggregate ceiling.

1. configure the implemented Anthropic Messages adapter with a separate
   credential; and
2. run a cross-provider case only after that credential is configured.
