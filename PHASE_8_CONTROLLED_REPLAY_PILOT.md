# Phase 8 Controlled Real/Replay Pilot

## Status

Defined, not authorized, and not enabled.

This document is the pre-authorization contract for the first controlled use of
real or historically replayed evidence with live model providers. It does not
grant permission to load provider credentials, enable a live runtime, transmit
evidence, or make a model call.

The offline artifact-contract foundation is implemented in
`phase8-contracts/` and `src/conclave/pilot/phase8.py`. It defines immutable
case, cohort, redaction, access, approval, revocation, blinded-rating, and
pilot-report artifacts.

The fail-closed safety boundary is implemented but remains inactive. The
`phase8_pilot` runtime validates the complete hash-linked authorization package
and durable batch state before reading either private external provider secret
or constructing a provider adapter. Every provider attempt then requires an
explicit approved case scope, exact snapshot and contract versions,
blind-context isolation, a durable per-attempt reservation, and available
route, batch, and phase authority. A hard violation writes an immutable
revocation record and permits no automatic restart.

The dedicated Phase 8 runner is implemented. Its offline path validates and
freezes actual real/replay packages, predicts all no-call controls, proves the
pre-construction authorization boundary, performs a zero-attempt local audit,
idempotency, and evaluation dry run, and emits a sealed machine and human Gate
0 evidence report. Its approved-batch path executes only cases already active
inside the fail-closed safety boundary.

No actual real/replay source packages have been supplied or frozen in this
repository, so Gate 0 has not been run or passed. No Gate 0 report, batch
approval, runtime state, provider credential, or provider call has been
created.

Phase 8 is a shadow-review exercise. Conclave returns recommendations for
evaluation only. It does not approve, execute, publish, spend, query Marketing
OS, access Meta, or alter a caller system.

## Decision this pilot supports

The pilot answers one bounded question:

> On reviewed, redacted, outcome-linked cases, does the Conclave panel produce
> recommendations that are reliable, auditable, clear, and at least as useful
> as the captured single-reviewer baseline within approved cost and latency
> limits?

It does not establish causal business impact, production prevalence, permanent
provider ranking, or a permanent reviewer-slot assignment.

## Pilot shape

### Locked cohort

The cohort contains 24 immutable cases:

- 20 provider-eligible real or historical replay cases.
- Four no-call controls: one stale package, one invalid-contract package, one
  duplicate/idempotency replay, and one unapproved-provider configuration.
- At least 12 eligible cases with a recorded caller decision and later outcome.
- At least six materially eligible requests or cases with a prior material
  recommendation.
- At least six partial, weak-evidence, or tracking-unhealthy cases.
- At least four cases selected because prior reviewers disagreed.
- At least four cases whose prior baseline recommended observation or no
  immediate change.

Tags may overlap. Cases are selected before any live panel output is observed.
No case may be added, removed, or relabeled after the cohort hash is approved
without creating a new pilot revision.

### Case requirements

Every eligible case must include:

1. a contract-valid immutable request snapshot;
2. an opaque case ID and evidence version;
3. a captured single-reviewer baseline created before the panel result;
4. a reviewed materiality and expected-routing profile;
5. a redaction attestation;
6. an evidence-quality assessment;
7. a caller decision and outcome package when available;
8. known confounders and outcome-evidence quality;
9. the approved task-pack, plan, prompt, role, schema, pricing, and model
   versions.
10. human-attested real-event or historical-replay provenance with an opaque
    source reference, source snapshot hash, and explicit confirmation that the
    package is not synthetic.

The baseline and outcome package remain hidden from live reviewers. Outcome
information is attached only after the panel recommendation is frozen.

### Data boundary

- Evidence is supplied as a reviewed snapshot; Conclave does not fetch or
  enrich it.
- Remove personal data, credentials, access tokens, direct contact details,
  customer-level identifiers, raw message content, and unnecessary free text.
- Replace business identifiers with stable opaque IDs.
- Shift timestamps consistently when exact dates are not needed.
- Normalize or bucket commercially sensitive values when exact amounts are not
  decision-relevant.
- Keep the redaction map outside Conclave and outside the pilot repository.
- Store no raw provider response, hidden reasoning, or provider credential.
- No Marketing OS or Meta credential may exist in the pilot environment.

## Execution waves

### Gate 0 — offline preflight

Cost: $0. No provider access.

Required before any credential is loaded:

- all 24 cases pass local contract validation;
- all case hashes, baseline hashes, and cohort hash are frozen;
- both human raters approve the redaction checklist;
- the exact plan revision and provider-access manifest are frozen;
- machine-enforced route, batch, total-spend, attempt, token, and wall-time
  guards pass boundary tests;
- the live runtime requires a batch approval artifact and rejects cases outside
  its exact allowlist before provider construction;
- local routing predicts that all four controls stop without a provider call;
- a dry run proves audit reconstruction, idempotency, and result evaluation;
- the approval record names the batch, cases, providers, models, versions,
  budgets, expiry, and approving operator.

### Gate 1 — five-case canary

Five provider-eligible cases plus all four no-call controls.

- Requires a separate, explicit approval after Gate 0.
- Human review occurs before any remaining eligible case is released.
- All five eligible sessions must produce a valid audited result or the pilot
  stops. The cumulative 95% reliability threshold is not rounded down for the
  canary.
- All four controls must stop before network access.

### Gate 2 — fifteen-case completion batch

The remaining 15 provider-eligible cases.

- Requires a new explicit approval after the Gate 1 review.
- May not inherit unused authority from Gate 1.
- Runs in groups of at most five cases, with budget and error-rate checks
  between groups.
- Stops immediately when any hard stop condition is met.

## Provider-access manifest

The proposed initial topology reuses the already compatibility-tested mixed
panel. It is pilot-only and is not a permanent slot assignment.

| Slot or stage | Proposed access | State before approval |
|---|---|---|
| Reviewer A independent and cross review | OpenAI, exact approved model pinned in the batch manifest | Disabled |
| Reviewer B independent and cross review | Anthropic, exact approved model pinned in the batch manifest | Disabled |
| Reviewer C blind assessment and judgment | OpenAI, exact approved model pinned in the batch manifest | Disabled |
| Gemini | No Phase 8 access; requires a revised manifest and separate approval | Disabled |
| Marketing OS, Meta, domain APIs, tools, browsing, storage | No access | Prohibited |

Provider controls:

- exact provider, base URL, model, role, prompt, schema, and pricing version are
  pinned before approval;
- no silent provider or model substitution;
- no provider tools, browsing, code execution, file access, or remote storage;
- provider retention or training is disabled where the provider supports that
  control;
- credentials are pilot-specific, loaded from an external secret boundary,
  excluded from command arguments and reports, and removed after the batch;
- network egress is allowlisted to the approved provider endpoints;
- every provider request must map to one approved case and one durable
  invocation;
- any provider, model, endpoint, price, or contract change invalidates the
  approval and returns the pilot to Gate 0.

## Budgets

These are hard authorization ceilings, not expected spend.

### Per-stage preflight ceilings

| Stage | Maximum attempts | Input bound | Output bound | Cost ceiling |
|---|---:|---:|---:|---:|
| A or B independent | 2 | 30,000 characters | 4,000 tokens | $0.10 |
| A or B cross review | 2 | 45,000 characters | 4,000 tokens | $0.13 |
| C blind assessment | 2 | 30,000 characters | 4,000 tokens | $0.15 |
| C judgment | 2 | 60,000 characters | 4,000 tokens | $0.25 |

Only retryable transport or provider failures may use the second attempt.
Invalid structured output, permanent errors, policy errors, and preflight
budget failures stop immediately.
The cost ceiling in this table applies to each provider request; route and
batch ceilings apply to the accumulated computed cost.

### Per-session ceilings

| Route | Maximum computed cost | Maximum wall time |
|---|---:|---:|
| A only | $0.12 | 3 minutes |
| A/B agreement | $0.25 | 5 minutes |
| Cross-review resolved | $0.55 | 8 minutes |
| Reviewer-C tie-break | $0.95 | 12 minutes |

### Batch ceilings

- Gate 1 hard spend cap: $5.
- Gate 2 hard spend cap: $10.
- Entire Phase 8 hard spend cap: $15.
- Entire Phase 8 provider-attempt cap: 160.
- Entire Phase 8 total-token cap: 1,000,000.
- Budget alerts at 50% and 75%; automatic stop at 100%.
- Unused Gate 1 budget or authority does not roll into Gate 2.
- Pricing is revalidated against the provider price sheets before each
  approval. A price change requires a new signed manifest.

## Measurement framework

### Primary decision metrics

| Metric | Definition | Acceptance threshold |
|---|---|---:|
| Audited completion rate | Provider-eligible sessions with one contract-valid result and a fully reconstructed audit ledger / provider-eligible sessions | 100% in Gate 1; at least 95% cumulative |
| Panel non-inferiority | Comparable cases where both blinded raters score the panel at least as useful as the baseline / comparable cases | At least 80% |
| Critical recommendation defect rate | Cases with an unsupported material action, evidence mismatch, hidden authority, or unsafe certainty / reviewed results | 0% |

### Reliability and contract guardrails

| Guardrail | Threshold |
|---|---:|
| Immutable snapshot consistency across joined reviewers | 100% |
| Blind independent-context isolation | 100% |
| Legal route and state-transition reconstruction | 100% |
| Duplicate durable results or feedback records | 0 |
| Invalid output accepted into a valid assessment | 0 |
| Provider substitution or unapproved provider access | 0 |
| Complete provider-attempt, token, latency, cost, prompt, schema, and pricing telemetry | 100% |
| First-attempt structured-output success | At least 90% |
| Structured-output success within allowed attempts | At least 95% |
| No-call controls that reach a provider | 0 of 4 |

### Quality review

Two human raters independently review baseline and panel results in randomized,
blinded order. They score each result from 1 to 5 on:

1. evidence linkage and factual support;
2. recommendation clarity and actionability;
3. uncertainty, evidence-quality, and confounder handling;
4. boundedness, caller authority, and safety;
5. usefulness for the stated decision.

Acceptance requires:

- average panel score of at least 4.0;
- no panel dimension below 3.0 on any material recommendation;
- panel rated at least as useful as baseline in at least 80% of comparable
  cases;
- panel strictly preferred in at least 50% of cases with a decisive
  preference;
- zero critical recommendation defects;
- 100% of material recommendations clearly marked
  `caller_decision_required`.

Rater disagreements are recorded, not silently averaged away. A third reviewer
may adjudicate the rubric, but the original ratings remain in the audit
artifact.

### Outcome-linked directional metrics

For the at least 12 cases with later outcomes, report:

- panel-change rate;
- caller panel preference;
- additional issue-catch count;
- caller override rate;
- outcome classification and evidence quality;
- confounder count;
- latency and cost by route.

These are diagnostics, not causal exit gates. Phase 8 is too small and too
selected to estimate business lift or rank providers.

### Latency and cost guardrails

- Route-specific p95 wall time must remain within the per-session ceilings.
- Average computed cost must be at most $0.25 per provider-eligible case.
- Cumulative p95 computed case cost must be at most $0.75.
- No case, batch, attempt, token, or aggregate ceiling may be exceeded.
- A result produced after a breached ceiling does not count as an accepted
  pilot result.

## Immediate stop conditions

Stop the active batch and revoke its authorization on any of the following:

- credential, personal-data, raw-response, or hidden-reasoning exposure;
- any Marketing OS, Meta, domain API, tool, browsing, or storage access;
- unapproved provider, model, endpoint, prompt, role, schema, or pricing
  version;
- silent provider substitution;
- cross-snapshot contamination or independent-round context leakage;
- invalid provider output stored as a valid assessment;
- duplicate durable result, broken audit sequence, or unverifiable final route;
- an unsupported material action or recommendation that implies execution
  authority;
- any hard cost, token, attempt, or wall-time ceiling breach;
- two consecutive provider-eligible sessions without a valid result;
- more than one contract or audit failure in the cohort.

There is no automatic restart. Resumption requires diagnosis, a revised pilot
manifest, a new cohort or version when results could be biased, and explicit
approval.

## Exit decision

### Proceed to a larger shadow pilot

Allowed only when every hard guardrail and acceptance threshold passes. The
next stage remains shadow-only and may expand the sample; it does not authorize
production routing or permanent provider assignment.

### Revise and repeat

Use when security and audit guardrails pass but a reliability, clarity,
latency, cost, or non-inferiority threshold misses. Revise one controlled
variable, version the plan, and rerun with a newly approved cohort.

### Stop

Required after any security, authority, data-boundary, audit-integrity, or
critical-recommendation defect.

## Authorization checklist

Before any live call, the approving record must confirm:

- [ ] Gate 0 passed with $0 provider spend.
- [ ] The cohort manifest and every case hash are frozen.
- [ ] Redaction was reviewed by two people.
- [ ] Baselines were captured before panel outputs.
- [ ] Provider/model assignments and every contract version are pinned.
- [ ] Current pricing was verified and the budget manifest was signed.
- [ ] Pilot-only credentials and endpoint allowlists are ready.
- [ ] Marketing OS, Meta, tools, browsing, storage, and fallback remain
      unavailable.
- [ ] The exact Gate 1 or Gate 2 case IDs are approved.
- [ ] The approval has an operator, timestamp, and expiry.
- [ ] Stop authority and credential revocation are assigned.

Until every item is complete and the user explicitly authorizes the named
batch, `CONCLAVE_REVIEWER_RUNTIME_MODE` remains `fixture` and no provider
credential is loaded.
