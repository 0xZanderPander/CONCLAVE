# Conclave Documentation Audit Log

A historical record of substantive changes to the Conclave design documents,
design fixtures, and draft integration contracts. One entry per revision.
Newest first.

Each entry records what changed, when, who requested and applied it, and why.
Add a new entry whenever the design contract changes; do not edit past entries.

| Date | Rev | Requested by | Applied by | Summary |
|---|---|---|---|---|
| 2026-08-01 | r30 | Al | Codex | Added the dedicated Phase 8 cohort and batch runner, explicit real/replay provenance, immutable cohort freeze command, and credential-free machine and human Gate 0 evidence workflow |
| 2026-07-29 | r29 | Al | Codex | Added the fail-closed Phase 8 authorization and safety runtime with pre-construction artifact validation, explicit case scopes, durable per-attempt budget reservations, exact contract isolation, and irreversible active-batch revocation |
| 2026-07-29 | r28 | Al | Codex | Added the offline Phase 8 artifact-contract foundation, immutable hashing and cross-artifact validation, generated JSON Schemas, and contract tests without enabling provider access |
| 2026-07-29 | r27 | Al | Codex | Defined the disabled Phase 8 controlled real/replay pilot, locked cohort, budgets, acceptance thresholds, provider-access manifest, approval waves, and stop conditions |
| 2026-07-28 | r26 | Al | Codex | Added and passed the 34-case deterministic Phase 7 pilot, route and directional metrics, manual clarity review, terminal audit checks, and fixture hardening |
| 2026-07-28 | r25 | Al | Codex | Added immutable Phase 6 reviewer-evaluation candidates, complete baseline/result comparison, directional route metrics, retrieval APIs, and migration 0011 |
| 2026-07-28 | r24 | Al | Codex | Added the Phase 6 immutable feedback foundation, authenticated intake, idempotency, safe events, audit reconstruction, and migration 0010 |
| 2026-07-28 | r23 | Al | Codex | Added the Gemini Interactions adapter and passed its explicitly approved one-attempt free-tier acceptance |
| 2026-07-28 | r22 | Al | Codex | Passed the bounded OpenAI-A/Claude-B/OpenAI-C panel with six one-attempt stages and exactly two Claude calls |
| 2026-07-28 | r21 | Al | Codex | Passed the corrected one-attempt Claude A-only acceptance while keeping mixed-panel egress separately gated |
| 2026-07-28 | r20 | Al | Codex | Stopped after the first Claude HTTP 400, diagnosed Anthropic schema incompatibility, and hardened the adapter without retrying |
| 2026-07-28 | r19 | Al | Codex | Recentered the canonical plan on provider-diversity validation, Phase 6 feedback evaluation, and the Phase 7 fixture pilot |
| 2026-07-28 | r18 | Al | Codex | Passed the complete bounded live OpenAI Phase 4B panel and closed its release gate |
| 2026-07-28 | r17 | Al | Codex | Added the second provider adapter and hardened production evidence paths and stage-specific limits from bounded live testing |
| 2026-07-28 | r16 | Al | Codex | Implemented typed A/B cross review, two-stage C production contracts, and controlled cross-review recovery |
| 2026-07-28 | r15 | Al | Codex | Implemented assessment-v2 compatibility, validated claim provenance, and added the auditable cross_review_failed terminal state |
| 2026-07-28 | r14 | Al | Codex | Reconciled the roadmap with implemented behavior and proposed Phase 4B structured claims, bounded cross review, two-stage C, and explicit failure handling |
| 2026-07-28 | r13 | Al | Codex | Completed Phase 4A with a blind Reviewer-B prompt, strict same-snapshot isolation, and a passing live A/B comparison gate |
| 2026-07-28 | r12 | Al | Codex | Completed the live Phase 3 Reviewer-A gate and made materiality and source facts deterministic rather than model-authoritative |
| 2026-07-27 | r11 | Al | Codex | Added provider-neutral operational metrics while the live Reviewer-A credential remains pending |
| 2026-07-27 | r10 | Al | Codex | Implemented the approved Phase 3 reviewer-A provider boundary, limits, prompt, durable attempt telemetry, migration 0009, and hosted verification |
| 2026-07-26 | r9 | Al | Codex | Completed the accepted Phase 2 hardening: pinned task-pack revisions, explicit C judgments, resumable execution, reconstructive audit checks, and non-local caller authentication |
| 2026-07-26 | r8 | Al | Codex | Started Phase 2 with a registered Marketing-v1 task pack, eligibility validation, weighted comparison, hard triggers, and automatic route selection |
| 2026-07-26 | r7 | Al | Codex | Promoted the audit ledger into a typed transport-neutral event stream and documented the future adapter boundary before Phase 2 |
| 2026-07-26 | r6 | Al | Codex | Recorded Phase 1B implementation and Supabase verification; made automatic comparator routing the explicit Phase 2 boundary |
| 2026-07-24 | r5 | Al | Codex | Removed Marketing MVP coupling; made fixture-based Conclave development current and the first Marketing deployment a later optional ad-performance review connection |
| 2026-07-24 | r4 | Al | Codex | Made review timing deployment-editable through immutable plan revisions; defined A/B expansion and two-stage C judging; added Marketing-v1 weights, hard triggers, contract `0.2.0`, and executable design fixtures |
| 2026-07-24 | r3 | Al | Codex | Separated Marketing domain ownership from the Conclave kernel; replaced direct Meta, Telegram, policy, outcome, and learning ownership with versioned request/result/feedback contracts |
| 2026-07-24 | r2 | Al | Conclave assistant (Cowork session) | Three-reviewer panel, cadence-based ping-pong, tolerance-triggered cross review, tie-breaker, baseline, configurable adjudicator, Hermes learning seam, domain contract, testable Phase 0 gate |
| 2026-07-14 | r1 | Al | Al | Initial Marketing-first, read-only MVP design (baseline of these docs) |

---

## r30 — 2026-08-01

**Requested by:** Al
**Applied by:** Codex
**Scope:** Phase 8 runner, real/replay cohort curation boundary, and Gate 0
evidence

### Implementation

1. Added explicit human-attested `real_event` or `historical_replay`
   provenance to every case package, including an opaque source reference,
   source hash, verifier, and mandatory `synthetic_data: false` declaration.
2. Added an immutable cohort-freeze command that validates exactly 24 package
   files, declared request-contract validity, chronology, coverage, distinct
   eligible sources, duplicate provenance, and every cross-artifact hash.
3. Added a credential-free Gate 0 command that cross-checks the exact plan,
   task pack, provider-access stages and policies, route guards, controls,
   approval shape, and provider pre-construction boundary.
4. Gate 0 now performs a deterministic mechanics-only audit, idempotency, and
   evaluation dry run with zero provider attempts and writes both a sealed JSON
   report and a human-review evidence document.
5. Added an approved-batch runner that operates only on the safety runtime's
   exact allowlist, keeps controls on the local no-call path, scopes every
   eligible provider execution, verifies the result audit, and durably marks
   case completion.

### Boundary

- No real/replay source package was available in the repository, so no cohort
  or Gate 0 artifact was fabricated or marked complete.
- No provider credential was loaded, provider adapter constructed, approval
  written, external provider attempt made, or spend incurred.
- Gate 1 remains disabled pending actual cohort curation, a passing Gate 0
  report, and a separate explicit human approval.

---

## r29 — 2026-07-29

**Requested by:** Al
**Applied by:** Codex
**Scope:** Phase 8 provider-construction and per-attempt safety boundary

### Implementation

1. Added an explicit `phase8_pilot` runtime mode that requires the pilot
   environment, caller authentication, external private secret-file
   references, and every cohort, access, Gate 0, approval, state, and
   revocation path.
2. Provider secrets are read and adapters are constructed only after the
   complete artifact chain, cohort packages, chronology, expiry, versions,
   endpoint allowlist, prior state, and absence of revocation validate.
3. Every review requires an explicit approved opaque case scope. This prevents
   the duplicate/idempotency control—which intentionally shares a snapshot—
   from being mistaken for its provider-eligible source case.
4. Every provider attempt is authorized separately and durably reserved before
   network access, then settled from safe provider telemetry.
5. Exact snapshots, blind independent context, provider/model/role/prompt/
   schema/pricing versions, stage order, retry rules, and route shape are
   enforced before an attempt.
6. Attempt, token, spend, latency, route, batch, and whole-pilot counters
   survive process restarts. Pending uncertain attempts block further calls
   until reconciliation.
7. Hard violations create an immutable revocation record and block all later
   provider access without automatic restart. Revocation and batch completion
   also close and detach the provider adapters.
8. Gate 2 cannot start from fresh state, inherit pending work, repeat a Gate 1
   case, or proceed without the exact completed Gate 1 review hash.

### Boundary

- No real/replay cohort, Gate 0 report, approval, runtime state, revocation
  record, credential, or provider call was created.
- The normal fixture runtime remains the default.
- A dedicated Phase 8 execution runner and the actual `$0` Gate 0 evidence
  package are still required before a canary can be considered.

---

## r28 — 2026-07-29

**Requested by:** Al
**Applied by:** Codex
**Scope:** offline Phase 8 artifact-contract foundation

### Implementation

1. Added immutable, strict models for case packages, the locked cohort,
   two-person redaction attestations, exact provider-access and pricing
   manifests, separate batch approvals, revocation records, blinded-rater
   packets and submissions, and final pilot reports.
2. Added canonical self-hashing, request-snapshot hashing, cohort-to-package
   verification, duplicate-control verification, and approval-to-cohort/access
   cross-checks.
3. Encoded the 20-plus-four cohort shape and minimum overlapping coverage
   requirements directly in the cohort contract.
4. Encoded the mixed OpenAI-A/Anthropic-B/OpenAI-C topology and Phase 8
   per-stage ceilings in the access-manifest contract.
5. Generated ten deterministic JSON Schemas and added commands and tests that
   detect schema drift.

### Boundary

- This revision creates definitions and offline validation only.
- It does not create or freeze the real/replay cohort, implement runtime
  authorization guards, create a batch approval, load a credential, or make a
  provider call.
- Phase 8 remains disabled pending later Gate 0 implementation and evidence.

---

## r27 — 2026-07-29

**Requested by:** Al
**Applied by:** Codex
**Scope:** pre-authorization definition for controlled real/replay cases,
budgets, acceptance thresholds, provider access, staged approvals, and hard
stops before any new live model call

### Decision

1. Phase 8 is a 24-case shadow pilot: 20 provider-eligible real/replay cases
   and four no-call controls.
2. Provider access remains disabled through a $0 offline preflight.
3. A five-case canary and 15-case completion batch require separate explicit
   approvals; authority and unused budget do not roll forward.
4. The proposed pilot-only topology reuses the compatibility-tested mixed
   panel, pins every provider/model/contract/pricing version, and prohibits
   silent substitution.
5. The hard spend ceiling is $15, with stage, route, batch, attempt, token, and
   wall-time limits.
6. Hard gates require complete snapshot isolation, audit reconstruction,
   telemetry, caller authority, and data security, plus zero critical defects,
   invalid accepted outputs, duplicates, unauthorized access, or budget
   breaches.
7. Quality is reviewed against a captured single-reviewer baseline by two
   blinded human raters. Outcome-linked metrics remain directional and cannot
   establish causal lift or permanent provider ranking.

### Boundary

- This revision does not load credentials, change runtime configuration,
  enable a provider, transmit evidence, or make a model call.
- Marketing OS, Meta, tools, browsing, storage, execution, approval authority,
  outcome ownership, and learned routing remain outside Conclave.
- Passing Phase 8 permits only consideration of a larger shadow pilot.

## r26 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** deterministic Phase 7 fixture dataset, pilot runner, synthetic
telemetry, feedback/evaluation metrics, manual result review, failure
containment, audit reconstruction, and roadmap closure

### Implementation

1. Added 34 self-describing Phase 7 cases covering healthy, partial, stale,
   tracking-unhealthy, failed-goal, material, disagreement, cross-review,
   reviewer-C, timeout, malformed-output, idempotency, and recovery paths.
2. Added a local assessment-v2 pilot runtime with deterministic attempts,
   latency, token, and cost telemetry. It has no network or provider path.
3. Added a reusable pilot command that runs automatic routing, submits
   synthetic feedback, records directional evaluation candidates, verifies
   completed audits, reconstructs terminal event streams, and writes a
   machine-readable result artifact.
4. Added an explicit manual review of all result archetypes and documented
   the synthetic-evidence boundary.
5. Deduplicated exact compatible-review summaries while preserving both
   reviewers' claims, invocation records, and audit history.

### Verification

- All 34 cases reach their expected outcomes.
- 31 results complete through feedback, evaluation, and full audit
  reconstruction.
- One stale case and two malformed-output cases stop safely and pass terminal
  event-stream reconstruction.
- Four retryable timeouts recover within their bounded attempts, and one
  failed cross review completes through the controlled operator recovery.
- All 34 independent-context, snapshot-consistency, and audit-trace checks
  pass; all 31 completed results pass evidence traceability and clarity checks.
- Ruff passes.
- The complete local suite passes with 127 tests and 11 expected opt-in skips.
- No OpenAI, Anthropic, Gemini, Marketing OS, Meta, or hosted database call was
  made.

### Interpretation boundary

- Route, preference, panel-change, latency, and cost metrics are directional
  fixture evidence.
- Synthetic feedback does not establish causal panel value, provider quality,
  production prevalence, or real cost.
- Permanent reviewer assignment remains deferred until outcome-linked,
  non-synthetic evidence exists.

## r25 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** immutable reviewer-evaluation candidates, baseline/result
fingerprinting, directional indicators, retrieval APIs, event/audit
reconstruction, migration `20260728_0011`, and local/PostgreSQL tests

### Implementation

1. Added one immutable, versioned evaluation candidate per review session,
   linked to the exact result, feedback, evidence, and route.
2. Compared equivalent complete public assessment projections for Reviewer A's
   baseline and the selected final result rather than relying on the existing
   category-only `changed_by_panel` field.
3. Added explicitly directional panel-change, caller-preference, additional
   issue, cross-review-resolution, reviewer-C, caller-override, outcome,
   latency, and cost indicators.
   Caller-preference rate excludes records marked `not_comparable`, while
   cross-review resolution uses only cross-review-invoked candidates as its
   denominator.
4. Added authenticated feedback and evaluation retrieval plus aggregate
   directional metrics with latency and cost grouped by route.
5. Added the safe `evaluation_candidate_recorded` event and reconstructive
   transition from `feedback_pending` to `evaluated`.
6. Added migration `20260728_0011` with an indexed foreign key, source hashes,
   fixed-precision cost, non-negative and route constraints, RLS, and revoked
   Data API roles.

### Verification

- Focused evaluation, API, feedback, and audit tests pass.
- Ruff passes.
- The complete local suite passes with 125 tests and 11 expected opt-in skips.
- A clean SQLite Alembic upgrade reaches `20260728_0011`.
- The PostgreSQL test now covers concurrent feedback and evaluation replay,
  RLS and role checks for both Phase 6 tables, audit reconstruction, and
  explicit zero-row cleanup.
- Current hosted advisors report only expected informational RLS-without-policy
  notices for the private server-only ledger and unused-index notices on the
  low-volume pre-Phase-6 schema; there are no warning or error findings.
- Hosted execution remains open: the Supabase migration ledger still ends at
  0009, and Codex's Supabase action-approval service continues to reject write
  calls with an internal `input[19].namespace` error before project execution.

### Interpretation boundary

- Every metric is labeled `directional_only`.
- Panel change is descriptive comparison, not a causal estimate of panel value.
- Caller feedback remains external evidence rather than trusted domain truth.
- Conclave does not reinterpret caller metrics, own outcomes, or promote a
  candidate into a learning registry.

---

## r24 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** Phase 6 roadmap recentering, feedback contract validation,
authenticated intake, immutable storage, domain events, audit reconstruction,
migration `20260728_0010`, and local/PostgreSQL test coverage

### Implementation

1. Added correlated `review-feedback/v1` validation for the review session and
   immutable evidence version.
2. Added one append-only feedback record per completed review session. Exact
   replay is idempotent; a changed replay is rejected.
3. Added authenticated `POST /reviews/{review_session_id}/feedback` intake with
   caller ownership and `feedback:submit` scope checks.
4. Added the safe `feedback_recorded` domain event and transition from
   `result_returned` to `feedback_pending`. Opaque decision, action, and outcome
   reference values remain out of the event stream.
5. Extended audit reconstruction through feedback linkage and its exact
   document hash.
6. Added migration `20260728_0010` for
   `public.review_feedback_records`, including session uniqueness, lookup
   indexes, RLS enablement, and revoked client-role privileges.

### Verification

- Focused feedback, API, validation, idempotency, append-only, and audit tests
  pass locally.
- Ruff passes.
- The complete local suite passes with 123 tests and 11 expected opt-in skips.
- A clean SQLite Alembic upgrade reaches `20260728_0010`.
- The isolated PostgreSQL concurrency test is implemented with synthetic-row
  cleanup but has not run against the hosted project yet.
- The Supabase connector rejected both the read-only state check and migration
  request before SQL execution because its automatic approval service returned
  an internal unknown-parameter error. The hosted migration and PostgreSQL
  verification therefore remain explicitly open.

### Boundary

- Feedback is caller-supplied evaluation evidence, not trusted domain truth.
- Conclave stores opaque external references but does not own caller decisions,
  actions, outcomes, causal interpretation, or learning.
- Reviewer-evaluation candidates and directional panel-value indicators remain
  the next Phase 6 checkpoint.

---

## r23 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** Google Gemini adapter, explicit runtime configuration, mocked and
opt-in live tests, provider comparison, canonical status documents, and audit
history

### Provider basis

- Google's current [Gemini 3.6 Flash model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash)
  identifies `gemini-3.6-flash` as the stable model and lists structured output
  and thinking support.
- The [Interactions API](https://ai.google.dev/api/interactions-api-v1) defines
  the request, response, status, and token-usage fields used by the adapter.
- The [structured-output guide](https://ai.google.dev/gemini-api/docs/structured-output)
  defines the supported JSON Schema subset.
- The [pricing page](https://ai.google.dev/gemini-api/docs/pricing) defines
  current paid rates, the free tier, and its data-use distinction.

### Implementation

1. Added explicit `gemini` runtime selection with
   `CONCLAVE_GOOGLE_API_KEY` and `CONCLAVE_GOOGLE_BASE_URL`; missing
   configuration fails instead of falling back.
2. Added a stateless Google Interactions adapter for stable
   `gemini-3.6-flash`. It requests schema-shaped JSON, exposes no tools, sets
   `store=false`, suppresses thought summaries, and maps the existing Conclave
   reasoning policy onto Gemini's supported thinking levels.
3. Added provider-facing JSON Schema normalization for Google's documented
   subset while preserving full local Pydantic, evidence-reference, task-pack,
   and orchestration validation.
4. Added safe request/response identifiers and input, cached, output, thought,
   total-token, latency, cost, finish-status, and pricing-version telemetry.
   Raw provider responses and hidden reasoning remain unstored.

### Acceptance result

1. The mocked suite covers independent structured assessment, explicit
   no-tools behavior, thinking-level mapping, retryable 429, permanent 400,
   telemetry, preflight budget rejection, and contract rejection before
   network access.
2. Al explicitly approved sending the synthetic fixture and reviewer
   prompt/schema to Google's free-tier API after being informed that Google may
   use free-tier content to improve its products.
3. The A-only `assessment-v2` acceptance called
   `gemini-3.6-flash` exactly once. It passed without retry, fallback, provider
   substitution, cross review, tool use, or raw-response storage.
4. Gemini returned `observe`, adequate evidence, low risk, and 0.95 confidence.
5. Safe telemetry recorded 2,268 ms provider latency, 1,612 input tokens,
   299 output tokens, 0 reported thought tokens, 1,911 total tokens, and
   $0 computed free-tier cost.

### Interpretation

- Gemini now satisfies the same provider-contract and accounting boundary as
  the OpenAI and Anthropic adapters.
- The available three-provider outputs are not a controlled quality benchmark:
  the Gemini acceptance used the base A-only fixture, while the most detailed
  OpenAI/Claude comparison used the surviving-conflict fixture and different
  A/B roles.
- No permanent reviewer slot is assigned. Phase 6 outcome-linked evaluation is
  the next major gate.
- No persistence schema changed, so no new PostgreSQL verification was
  required.

---

## r22 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** bounded mixed-provider live acceptance, provider comparison,
canonical status documents, local and PostgreSQL verification, and audit
history

### Acceptance result

1. The approved `c_tie_broken` synthetic-fixture route completed all six
   production stages with one provider attempt each.
2. A independent, A cross review, C blind assessment, and C judgment used
   OpenAI `gpt-5.6-terra`.
3. B independent and B cross review used Anthropic `claude-sonnet-5`.
4. Claude was called exactly twice. No retry, fallback, provider substitution,
   or extra discussion round occurred.
5. Every response passed the stage-specific structured contract, claim and
   evidence validation, deterministic task-pack normalization, result
   construction, and caller-decision boundary.
6. Aggregate telemetry was 39,900 tokens, 113,898 ms summed provider latency,
   and $0.1731145 computed cost. OpenAI accounted for 22,856 tokens,
   47,775 ms, and $0.1154025; Claude accounted for 17,044 tokens, 66,123 ms,
   and $0.057712.

### Structured comparison

1. A and B independently selected `operational_change` and adequate evidence.
   A reported medium risk, 0.78 confidence, three claims, and one action. B
   reported low risk, 0.62 confidence, six claims, and two actions.
2. After cross review, A retained medium risk and 0.78 confidence. B retained
   low risk and moved to 0.60 confidence.
3. C's blind assessment also selected `operational_change`, adequate evidence,
   medium risk, and 0.80 confidence with five claims and two actions.
4. C's judgment selected B at 0.73 confidence. The final result remained
   `caller_decision_required`.
5. A's category and the final category matched, so the existing
   category-only `changed_by_panel` field remained false even though the final
   selected assessment changed from A to B. Phase 6 must compare complete
   assessments for panel-change reporting.

### Interpretation

- The run proves bounded cross-provider compatibility for the approved
  Conclave contracts.
- It does not prove that Claude should permanently occupy B, that the panel
  improved the recommendation, or that any difference is causal.
- Gemini compatibility and the three-provider comparison remain open.

### Verification

- Ruff passes.
- The complete local suite passes with 113 tests and 9 expected opt-in skips.
- All four isolated PostgreSQL event-stream, full-flow, and worker-locking
  integration cases pass and clean up their synthetic rows.

### Guardrails preserved

- Reviewer A and B were blind in their first round and shared one immutable
  snapshot.
- Cross review remained one bounded round.
- C1 remained blind and C2 received only approved structured context.
- No raw response, hidden reasoning, credential, campaign authority, approval,
  execution, or Marketing OS connection was stored or added.

---

## r21 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** corrected Anthropic live acceptance, mixed-panel acceptance harness,
canonical status documents, and audit history

### What changed

1. Al separately authorized exactly one corrected Anthropic attempt after the
   stopped HTTP 400 and schema hardening.
2. `claude-sonnet-5` returned a contract-valid `assessment-v2` in one attempt
   on the A-only synthetic-fixture route.
3. Safe telemetry recorded 44,478 ms provider latency, 5,164 input tokens,
   1,169 output tokens, 6,333 total tokens, and $0.022018 computed cost under
   the active introductory pricing.
4. The acceptance stored no raw provider response or hidden reasoning and
   performed no retry, substitution, cross review, or provider expansion.
5. A mixed-panel harness now statically assigns OpenAI to A/C and Anthropic to
   B, permits one attempt per stage, caps Claude at its independent and single
   cross-review calls, and has an aggregate $0.93 ceiling.
6. The mixed panel was not executed because multi-provider egress requires
   separate explicit approval.

### Remaining gate

- The bounded mixed panel remains pending.
- Passing Claude compatibility is not evidence of reviewer quality or panel
  value and does not assign Claude a permanent slot.
- Gemini adapter and free-tier acceptance remain pending.
- No commit or push occurs until the complete checkpoint is green.

---

## r20 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** Anthropic adapter, opt-in live acceptance harness, provider tests,
`README.md`, `MVP_project_architecture.md`, `MVP_build_roadmap.md`,
`PHASE_4B_CONTRACT_PROPOSAL.md`, and `audit/CHANGELOG.md`

### What happened

1. Official Anthropic documentation confirmed `claude-sonnet-5`, current
   structured-output support, low-effort request control, and the active
   introductory pricing.
2. The first live A-only acceptance used exactly one provider attempt, low
   effort, a 4,000-token output bound, and a $0.10 request ceiling.
3. Anthropic rejected the request with permanent HTTP 400 before generation.
   The mixed panel was not started and the request was not retried.
4. The provider returned no generated-token usage. Conclave computed $0.00
   model cost for the failed request. The isolated test completed in 7.9
   seconds end to end; its per-provider latency record was not retained after
   the ephemeral SQLite harness disposed the failed session.

### Diagnosis and hardening

1. The raw Pydantic schema contained constraints such as `minimum`,
   `maximum`, and `minLength` that Anthropic documents as unsupported in raw
   structured-output schemas.
2. The Anthropic adapter now transforms the provider-facing schema using the
   documented supported subset: recursive definitions and unions remain,
   unsupported constraints move into descriptions, and every object forbids
   additional properties.
3. Conclave still validates any returned document against the complete
   original Pydantic and task-pack contracts.
4. The adapter now honors pinned reasoning effort, including explicit
   thinking disablement when policy selects `none`.

### Verification and remaining risk

- Ruff passes.
- The complete local suite passes with 113 tests and 8 expected opt-in skips.
- No PostgreSQL persistence changed, so no new hosted persistence run was
  required for this failed provider checkpoint.
- The exact provider error message was intentionally not persisted; the
  unsupported raw schema is a concrete compatibility defect and the most
  likely cause of the HTTP 400, but a later separately approved acceptance is
  required to confirm the fix.
- Checkpoint 1 is not green. No commit, push, mixed panel, or provider-slot
  assignment is authorized from this result.

### Not changed

- One bounded cross-review round, reviewer independence, C1 blindness, the
  caller-decision boundary, and no-chain-of-thought storage remain intact.
- Marketing OS, Meta, campaign execution, approval, and spend authority remain
  out of scope.

---

## r19 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_project_architecture.md`,
`MVP_build_roadmap.md`, `PHASE_4B_CONTRACT_PROPOSAL.md`,
`audit/CHANGELOG.md`

### Why

Phase 4B is complete and both additional provider credentials now authenticate.
The canonical plan needed to separate provider compatibility testing from the
next major product phase: outcome-linked reviewer evaluation.

### What changed

1. Closed the Phase 4B release gate.
2. Added a provider-diversity gate: one low-cost Claude review, one mixed panel
   with no more than two Claude calls, a Gemini adapter, one free-tier Gemini
   review, and structured provider comparison before permanent slot assignment.
3. Recorded that Anthropic and Google credentials passed no-generation
   authentication checks, without claiming live reviewer compatibility.
4. Made Phase 6 durable feedback linkage and directional panel-value evaluation
   the next major implementation phase.
5. Kept Phase 7 as a minimum 30-case synthetic or replayed pilot with no live
   Marketing dependency.

### Not changed

- Provider availability does not determine a permanent reviewer assignment.
- Conclave does not own caller decisions, outcomes, causal interpretation, or
  domain learning.
- Marketing OS integration remains optional and deferred.

---

## r18 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_build_roadmap.md`,
`PHASE_4B_CONTRACT_PROPOSAL.md`, `audit/CHANGELOG.md`

### What changed

1. The complete live Phase 4B acceptance path passed using OpenAI for all six
   bounded calls: A independent, B independent, A cross review, B cross review,
   C blind assessment, and C judgment.
2. Every production response passed the structured contract, canonical evidence
   validation, deterministic normalization, result construction, and
   caller-decision boundary.
3. The run stayed inside the test's $0.90 aggregate cost ceiling.
4. Phase 4B is now marked complete. Genuine perspective-diversity evaluation
   remains separate and requires another provider credential.

### Not changed

- Passing a same-provider panel proves the production plumbing and contracts; it
  does not prove that the panel outperforms one model.
- Conclave still does not execute or own the caller's decision.

---

## r17 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** provider adapters, reviewer prompts, evidence references, plan
policies, architecture, roadmap, tests, and audit log

### What changed

1. Added an Anthropic Messages adapter behind the same approved, typed reviewer
   contracts as OpenAI. Runtime selection remains explicit and never falls
   back silently.
2. Added `anthropic` and `multi_provider` runtime modes. Multi-provider startup
   requires both credentials.
3. Tightened every Phase 4B production prompt to use canonical evidence roots
   and never prefix paths with `snapshot`.
4. Canonicalized bracketed numeric array references to the stored dotted form
   while preserving strict snapshot-existence validation.
5. Added optional cross-review and judging provider policies per slot so a
   deployment can tune bounded stage limits without weakening other calls.

### Verification

- Ruff and the full local suite pass.
- Mocked Anthropic success, telemetry, retry, and failure tests pass.
- All four hosted PostgreSQL integration tests pass against the Supabase
  Session Pooler.
- Bounded OpenAI attempts progressed through A/B and cross review, then exposed
  and hardened two real contract boundaries: provider-authored path syntax and
  C2's larger input size. The final complete live gate remains pending.

### Not changed

- The A/B/C protocol, one-round cross-review limit, caller decision boundary,
  immutable ledger, and no-execution rule.
- No Anthropic live evaluation is claimed before a separate credential is
  configured.

---

## r16 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** stage-specific reviewer contracts, production prompts, orchestration,
provider validation, audit reconstruction, recovery controls, architecture,
roadmap, tests, and audit log

### What changed

1. A and B cross review now returns `affirm` or `revise`, an explicit position
   on every peer claim, and one complete structured assessment.
2. Reviewer C now has separate approved contracts for its blind assessment and
   later judgment.
3. C's judgment classifies all submitted claim IDs as supporting, rejected, or
   unresolved. Selecting A or B preserves that exact final assessment.
4. Reviewer slot plans may pin different role, prompt, and schema versions for
   independent review, cross review, and judgment.
5. Production provider calls reject peer content in blind rounds and require
   the approved context for cross review and judgment.
6. Operators may recover `cross_review_failed` only when exactly one
   cross-review invocation failed. Recovery keeps prior assessments and
   provider attempts, records the operator and reason, and resumes the same
   bounded round.
7. Attempt numbering and aggregate provider telemetry remain continuous across
   recovery.

### Verification

- The local suite covers the complete structured A/B/cross-review/C path,
  Reviewer C blindness, claim classification, exact schema identities,
  recovery, attempt preservation, result construction, and audit replay.
- Ruff and the complete local suite pass.
- The hosted PostgreSQL concurrency and full-flow suite passes through the
  Supabase Session Pooler.

### Still pending

- One bounded OpenAI full-conflict test.
- A second provider adapter and later credentialed cross-provider evaluation.

---

## r15 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** reviewer assessment models, task-pack validation, orchestration,
state machine, result and event projection, design traces, Phase 4B documents,
README, architecture, roadmap, tests, and audit log

### What changed

1. `assessment-v2` supports structured claims containing a type, statement,
   exact snapshot references, and alternative explanations.
2. Conclave assigns stable claim IDs from the invocation identity and stored
   claim ordinal. Provider-authored claim IDs are rejected.
3. Historical `assessment-v1` string claims remain readable and round-trip
   unchanged.
4. Every v2 reference must use an approved request root and resolve to an exact
   path in the immutable snapshot.
5. Structured claims project into `review-result/v1` and reviewer-completion
   event evidence references without exposing internal claim IDs.
6. Cross-review provider or contract failures now enter
   `cross_review_failed`, preserve completed A/B work, record the failed
   invocation and state transition, and never continue to Reviewer C.

### Verification

- Legacy assessment compatibility, deterministic claim IDs, valid and invalid
  reference paths, result/event projection, legal state transitions, terminal
  behavior, and cross-review audit continuity have dedicated tests.
- Ruff and the complete local suite pass.
- No database migration was required because review states and assessment
  payloads are stored as versioned strings and JSON.
- Supabase MCP confirms the isolated project is healthy, remains at Alembic
  `20260727_0009`, stores session state as character data, and stores
  assessments as JSON.
- The four direct PostgreSQL pytest cases were attempted but could not connect
  with the saved local credential note or the inferred pooler route. They
  remain unverified for this revision rather than being reported as passing.

### Still pending

- Production A/B cross-review response models and prompts.
- Production Reviewer C blind-assessment and judgment prompts.
- A bounded live Phase 4B conflict test.
- Terminal reviewer-session operator recovery.
- A second provider adapter and cross-provider evaluation.

---

## r14 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_project_architecture.md`,
`MVP_build_roadmap.md`, `PHASE_4B_CONTRACT_PROPOSAL.md`, and
`audit/CHANGELOG.md`

### Why

Al asked to recenter the documentation, identify remaining issues, and prepare
the Phase 4B contract proposal before implementation.

### What changed

1. The roadmap now separates the completed fixture kernel from the unapproved
   production Phase 4B provider contracts.
2. Existing automatic C routing, bounded cross review, material-result
   handling, disagreement measurement, result retrieval, and provider auditing
   are marked as implemented rather than scheduled for rebuilding.
3. The proposal introduces `assessment-v2` structured claims with
   Conclave-issued IDs, exact snapshot references, and alternative
   explanations.
4. The proposal defines one full-assessment A/B affirm-or-revise round,
   Reviewer C's blind assessment, and Reviewer C's separate explicit judgment.
5. The proposal identifies the missing legal failure transition from the
   shared cross-review state and recommends `cross_review_failed`.
6. Phase 5 is recorded as partially complete. Phase 6 is recorded as a
   validated contract fixture without ingestion or evaluation implementation.
7. The docs now distinguish queue retry from terminal reviewer-session
   recovery, which is not implemented.

### Decisions still required

- Approve the structured claim fields and deterministic claim IDs.
- Approve exact snapshot-path reference validation.
- Approve the A/B cross-review response contract.
- Approve C's two production contracts.
- Approve `cross_review_failed`.
- Approve an initial same-provider live Phase 4B plumbing test before adding a
  second provider.

### Not changed

- No reviewer model, prompt, schema, state, or database code changed.
- No live provider call was made.
- The Marketing boundary and caller authority are unchanged.
- Conclave still returns recommendations and never performs actions.

---

## r13 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_project_architecture.md`,
`MVP_build_roadmap.md`, `audit/CHANGELOG.md`, OpenAI reviewer prompts and
adapter, and reviewer-routing and live-provider tests

### Why

Al approved using OpenAI for the Reviewer-B acceptance test while identifying
independent perspectives from different agents or providers as the likely
stronger production design.

### What changed

1. Reviewer B now has a separate approved role version and independent-audit
   prompt.
2. The OpenAI adapter routes A and B through their own approved prompt
   versions and supports only the blind independent stage.
3. Independent provider calls containing prior claims or peer assessments are
   rejected before any network request.
4. Tests prove A and B receive the exact same immutable snapshot with empty
   peer context before comparison.
5. The existing deterministic comparator records the A/B distance, tolerance,
   hard triggers, and whether cross review is required.
6. Reviewer slots remain independently configurable by provider, model,
   reviewer type, role, and prompt. A second provider can be added without
   changing the kernel.

### Verification

- The opt-in live A/B gate passed with two successful independent OpenAI
  assessments and one durable comparison.
- Any required cross-review call is rejected locally because Phase 4B prompts
  are not yet approved.
- Ruff passed.
- The full non-live suite passed with 92 tests; six opt-in live or PostgreSQL
  tests were skipped.

### Not changed

- No second model provider was added.
- The same-provider live gate is not treated as evidence that a panel
  outperforms one model.
- Cross review and Reviewer C remain fixture-only until their prompts receive
  separate review and approval.
- The Marketing boundary and deterministic A/B/C protocol are unchanged.
- Conclave still performs no caller or campaign action.

---

## r12 — 2026-07-28

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_project_architecture.md`,
`MVP_build_roadmap.md`, `audit/CHANGELOG.md`, `.gitignore`, reviewer prompt,
task-pack registry, orchestration, event projection, and tests

### Why

Al added an isolated OpenAI API key and authorized testing within a $10
dashboard budget. The first live assessment was structurally valid but exposed
an important boundary issue: the model labeled an experiment non-material even
though the pinned task pack defines experiments as material.

### What changed

1. Conclave now deterministically replaces model-supplied materiality,
   tracking health, optimization eligibility, and primary conversion before
   task-pack validation and persistence.
2. The model remains responsible for its recommendation, claims, confidence,
   evidence-quality judgment, risk, actions, and experiment proposal. It is not
   authoritative for source facts or routing policy.
3. Reviewer-A prompt `marketing-assessment-p2` states the materiality rule and
   the deterministic normalization boundary.
4. Reviewer completion events identify the fields controlled by Conclave.
5. `.env` editor swap files are ignored so a temporary editor artifact cannot
   be accidentally committed with a credential.

### Verification

- The first live call proved API access and strict structured output, then was
  correctly rejected for conflicting materiality.
- After deterministic normalization, a second live review passed the provider,
  task-pack, orchestration, baseline, telemetry, and ledger stages; its test
  then exposed an unrelated stale baseline assertion.
- The final bounded live reviewer-A gate passed cleanly after correcting that
  assertion.
- Ruff passed, and the full non-live regression suite passed with 90 tests;
  only the four opt-in PostgreSQL tests and the live-provider gate were skipped.
- No API key or raw provider response was printed, read into the ledger, or
  committed.

### Not changed

- Reviewer B and C production prompts remain unimplemented and unapproved.
- The A/B/C protocol and Marketing boundary are unchanged.
- Conclave remains a recommendation-review module and performs no caller
  action.

---

## r11 — 2026-07-27

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_project_architecture.md`,
`MVP_build_roadmap.md`, `audit/CHANGELOG.md`, ledger repository, API, CLI, and
tests

### Why

The live Reviewer-A acceptance gate is waiting for an OpenAI API key. Work can
continue safely on provider-neutral operational scaffolding without changing
reviewer prompts, provider behavior, or the fixed A/B/C protocol.

### What changed

1. The ledger now summarizes provider-attempt counts by status, total tokens,
   total estimated cost, average latency, and the most recent completion time.
2. `GET /operations/status` and the `queue-status` CLI output expose the same
   safe aggregate view.
3. The summary is built only from the durable attempt ledger. It does not
   expose credentials, submitted evidence, raw provider responses, or
   assessment content.

### Not changed

- No live provider call was made.
- Reviewer B and C production prompts remain unimplemented and unapproved.
- No `.env` file or credential was created, read, or committed.
- The review protocol, task-pack routing, and Marketing boundary are unchanged.

---

## r10 — 2026-07-27

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_project_architecture.md`,
`MVP_build_roadmap.md`, `MVP_architecture_flow.mmd`, `EVENT_STREAM.md`,
`audit/CHANGELOG.md`, result contract schema, Phase 3 source, migration, and
tests

### Why

Al approved the Phase 3 review and asked Conclave to begin the first real
reviewer-provider implementation without changing the fixed A/B/C protocol.
The provider boundary needed explicit production configuration, safe prompt
isolation, bounded operational limits, and auditable accounting before any live
reviewer-A acceptance run.

### What changed

1. The first production provider adapter uses the OpenAI Responses API for
   reviewer A. It is stateless, tool-free, uses strict structured output, and
   treats the submitted snapshot as untrusted evidence rather than
   instructions.
2. Runtime selection is explicit. Development and test may use deterministic
   fixtures; non-local deployments cannot start with the fixture runtime.
   Missing providers never fall back silently.
3. The initial approved provider policy allows two attempts, 90 seconds per
   attempt, 30,000 input characters, 4,000 output tokens, a $0.15 cost ceiling,
   medium reasoning effort, and versioned pricing inputs.
4. Only typed transient provider failures retry. Invalid contract output,
   permanent provider errors, and budget failures stop immediately.
5. Reviewer invocations now store aggregate token, reasoning-token, latency,
   cost, request/response, finish-status, and pricing metadata. Immutable
   per-attempt records preserve retries and safe error categories.
6. `provider_attempt_completed` events expose safe accounting facts through the
   existing transport-neutral ledger. Raw provider responses, snapshots,
   credentials, and hidden reasoning are not copied into events.
7. Migration `20260727_0009` adds `reviewer_provider_attempts` and aggregate
   telemetry columns to `reviewer_invocations`.
8. The optional result metadata contract accepts the new audit fields without
   breaking existing result fixtures.
9. A future Hermes reviewer remains a separate adapter and must use a
   dedicated blank-slate profile with no tools, memory, skills, browsing, or
   unrelated context.

### Verification

- Ruff passed.
- The complete local suite passed: 89 tests, with the four opt-in PostgreSQL
  cases and one opt-in live-provider case skipped.
- A clean SQLite database upgraded through the entire Alembic chain to
  `20260727_0009`.
- Migration `0009` was applied to the dedicated Conclave Supabase project.
  Supabase migration history and Alembic both report the new revision.
- All four PostgreSQL integration checks passed: full fixture flows with
  provider telemetry, concurrent event ordering, subscriber-delivery locking,
  and worker-claim locking.
- Supabase security and performance advisors report informational notices only.
  RLS intentionally has no client policies because Conclave tables are private
  to the server process.
- No live OpenAI call was made because no API key is configured. The one-call
  reviewer-A live acceptance gate remains open.

### Not changed

- The A/B, one-round cross-review, and two-stage reviewer-C protocol is
  unchanged.
- Reviewer B and C do not yet have approved production prompts.
- Conclave remains a recommendation-review module, not an execution engine.
- Marketing OS remains independent, and any later Marketing connection remains
  optional ad-performance review only.
- Discord, Telegram, Slack, and other presentation adapters remain deferred
  consumers of the same event stream.

---

## r9 — 2026-07-26

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_project_architecture.md`,
`MVP_build_roadmap.md`, `MVP_architecture_flow.mmd`,
`hyperstructure-review-contracts/`, `audit/CHANGELOG.md`, Phase 2 source,
migration, and tests

### Why

The Phase 2 acceptance review found several places where a recorded route could
be technically complete but not fully reconstructable. Reviewer C's verdict
was overloaded onto a normal assessment, task-pack meaning was loaded from
mutable application registration, a crash could repeat completed model work,
and non-local caller authentication remained deferred.

### What changed

1. Every new session pins the full task-pack document by a deterministic
   content hash. The stored revision supplies action ontology, eligibility,
   materiality, comparator, and merge semantics for the life of that session.
2. Request materiality and reviewer recommendation materiality are separate
   deterministic panel-expansion inputs with separate review-plan levers.
3. The Marketing-v1 task pack now owns action directions, opposite action
   pairs, required assessment fields, material recommendation rules, and
   maximum evidence age.
4. Comparator golden fixtures now contain full assessment pairs and cover all
   weighted dimensions, hard triggers, merge incompatibility, and conservative
   timing.
5. Reviewer C now returns a separate required judgment. Selecting A or B
   preserves that exact final assessment; synthesis and safe fallback require
   an explicit task-pack-valid assessment.
6. Automatic orchestration is state-driven and resumable from every legal
   partial state. Completed invocations, comparisons, results, and transitions
   are reused instead of repeated.
7. Results preserve both initial and post-cross-review comparisons, identify
   the decisive resolution basis, and store the task-pack hash.
8. The decision verifier recomputes materiality, comparison rounds, route
   eligibility, reviewer-C use, and the published recommendation from stored
   inputs.
9. Non-local API mode now fails startup without configured credentials.
   Scoped bearer authentication and caller ownership checks protect review,
   event, audit, and operational endpoints.
10. Migration `20260726_0008` adds immutable `task_pack_revisions` and pins new
    `review_sessions` to them.

### Verification

- Ruff passed.
- The complete local suite passed: 79 tests, with only the four
  PostgreSQL-only cases skipped.
- All four PostgreSQL-only cases passed against the dedicated Conclave
  Supabase project: full fixture flows, concurrent event ordering,
  subscriber-delivery locking, and worker-claim locking.
- Supabase migration history and Alembic both report revision
  `20260726_0008`; hosted test rows were removed after verification.
- Supabase security and performance advisors report informational notices only.
  RLS intentionally has no client policies because Conclave tables are private
  to the server process, and the unused-index notices are expected for a new
  test database.

### Not changed

- The A/B, one-round cross-review, and two-stage C protocol remains fixed.
- Conclave remains a recommendation-review module, not an execution or
  generalized workflow engine.
- Conclave has no Marketing data connector, platform credentials, campaign
  control, spend authority, outcome ownership, or Marketing learning
  ownership.
- Discord, Telegram, Slack, and other presentation adapters remain deferred
  consumers of the transport-neutral event stream.

---

## r8 — 2026-07-26

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_project_architecture.md`,
`MVP_build_roadmap.md`, `MVP_architecture_flow.mmd`, `EVENT_STREAM.md`,
`hyperstructure-review-contracts/README.md`, `audit/CHANGELOG.md`, Phase 2
source and tests

### Why

Phase 1 proved each fixed review path manually. Phase 2 must select those same
paths from a registered task-pack contract and recorded reviewer output without
turning Conclave into a general workflow builder or coupling it to Marketing
OS.

### What changed

1. `marketing-ads/v1` is the first registered local task pack, with a bounded
   action ontology, eligibility rules, materiality calculation, comparator
   weights, tolerance, hard triggers, and conservative merge behavior.
2. Intake now checks task-pack identity, comparator equality, ontology,
   freshness ordering and age, partial data, tracking health, evidence quality,
   optimization eligibility, metrics, and materiality thresholds.
3. Stale evidence is still stored as an immutable snapshot, then enters
   `stale_or_ineligible_evidence`.
4. Reviewer output is checked against the request ontology, evidence
   eligibility, experiment rules, and budget-change policy before it is stored
   as a completed assessment.
5. The comparator measures all eight approved dimensions and applies hard
   triggers before weighted tolerance.
6. The normal orchestrator automatically expands to B, cross review, or C from
   scheduled-B, material-A, failed-goal, audit-sample, weighted-distance, and
   hard-conflict facts.
7. Failed-goal input forces the bounded cross-review round but does not force C
   after A and B converge.
8. Comparison results are appended to the canonical typed event stream.
9. Manual path selection remains available only as a deterministic regression
   harness.
10. Automatic scheduled-B routing and its decision ledger passed against the
    dedicated Conclave Supabase project; synthetic rows were removed afterward.

### Deferrals adjusted

- Automatic panel routing moved into active Phase 2 implementation.
- Caller authentication remains required before any non-local request endpoint.
- Real model-provider selection remains after the Phase 2 acceptance review.

### Not changed

- The fixed A/B/cross-review/C protocol and one-round cross-review bound remain.
- Conclave has no Marketing data connector, Meta credential, campaign control,
  approval authority, outcome ownership, or Marketing learning ownership.
- Discord and other communication adapters remain outside this phase.

---

## r7 — 2026-07-26

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_project_architecture.md`,
`MVP_build_roadmap.md`, `MVP_architecture_flow.mmd`, `EVENT_STREAM.md`,
`audit/CHANGELOG.md`, event source, migration, API, and tests

### Why

Future visualizations and communication adapters need a reliable way to observe
Conclave without entering the review protocol. The existing append-only audit
ledger was the correct starting point, but it needed typed envelopes, safe
summaries, concurrency-safe ordering, and retryable subscriber delivery before
it could serve as that boundary.

### What changed

1. `audit_events` remains the one canonical history and now stores a stable
   public event envelope.
2. Typed event definitions replace arbitrary event-name strings in repository
   operations.
3. `event_streams` atomically allocates per-stream sequence numbers and removes
   the prior `max + 1` concurrency risk.
4. `event_subscriptions` and `event_deliveries` provide PostgreSQL-backed
   delivery leases, checkpoints, error recording, and retry.
5. Subscriber delivery happens after the domain transaction commits. Subscriber
   failure cannot roll back or corrupt Conclave review state.
6. The event API supports read-only polling by review-session sequence.
7. Event payloads use references and safe projections rather than full
   snapshots, ORM records, assessment bodies, or hidden reasoning.
8. A future Discord, Telegram, Slack, logging, or web adapter implements the
   same `EventPublisher.publish(DomainEvent)` boundary and deduplicates by
   `event_id`.
9. Migration `20260726_0007`, full review flows, same-stream sequence
   concurrency, and multi-worker delivery locking passed against the dedicated
   Conclave Supabase project.
10. Phase 2 task-pack intake and automatic route selection remain the immediate
    next build.

### Deferrals adjusted

- The transport-neutral boundary moved ahead of Phase 2 and is complete.
- Discord, Telegram, Slack, webhooks, chat bots, push UI, and human approval
  capture remain unimplemented and deferred.

### Not changed

- The A/B/cross-review/C protocol and deterministic fixture paths are unchanged.
- Conclave remains a decision-review system, not a communication or execution
  engine.
- Marketing OS remains independent. Any later Marketing connection is optional
  ad-performance review only.

---

## r6 — 2026-07-26

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_project_architecture.md`,
`MVP_build_roadmap.md`, `MVP_architecture_flow.mmd`,
`audit/CHANGELOG.md`, Phase 1B source, migration, and tests

### Why

Phase 1B moved from design into working code. The documents still called the
project proposed, described modules and endpoints that did not exist, and did
not clearly separate deterministic fixture-path execution from future automatic
comparator routing.

### What changed

1. The status now records Phase 1A and 1B as complete and makes Phase 2
   task-pack intake and automatic comparator routing the next build.
2. Migration `20260726_0006` adds immutable results, work retry and dead-letter
   fields, queue indexes, and runtime-process health records.
3. Persistent scheduler and worker commands now use database leases, retries,
   dead-letter recovery, cancellation, heartbeats, and stale-process reporting.
4. Reviewer calls now pass through a common provider registry. Provider errors
   and malformed output retry within a fixed limit, and there is no silent
   provider substitution.
5. A-only, A/B agreement, cross-review, and reviewer-C fixture paths now create
   one contract-valid, immutable result.
6. The audit verifier now checks contiguous event order, legal transitions,
   exact path shape, invocation count, shared snapshot, result ordering, result
   hash, and result contract.
7. All four fixture paths and concurrent work claiming passed against the
   dedicated Conclave Supabase database. Synthetic integration rows were
   removed after the run.
8. The architecture document now matches the real package layout, current
   tables, local endpoints, work queue, process health, and decision verifier.
9. The flowchart now shows the persistent worker, leased queue, operational
   controls, audit verifier, and the Phase 2 comparator boundary.

### Deferrals adjusted

- Automatic selection of A-only, A/B, cross-review, or C from materiality,
  weighted disagreement, hard triggers, and failed-goal input is Phase 2.
- Real model providers, provider-specific timeout and cost limits, caller
  authentication, external result delivery, feedback, and reviewer evaluation
  remain later-phase work.
- Before real provider calls, the worker lease must be longer than the bounded
  provider retry window or must be renewed during the call.

### Not changed

- Conclave remains an independent structured decision-review system.
- Marketing OS remains separate and has no Conclave dependency.
- Any future Marketing connection remains optional ad-performance review only.
- Conclave has no platform credential, campaign control, spend authority,
  Marketing decision authority, outcome ownership, or Marketing learning
  ownership.

---

## r5 — 2026-07-24

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_project_architecture.md`,
`MVP_build_roadmap.md`, `MVP_architecture_flow.mmd`,
`hyperstructure-review-contracts/README.md`,
`hyperstructure-review-contracts/conformance/conformance.md`,
`hyperstructure-review-contracts/schemas/*.json` (descriptions only)

### Why

Marketing OS is being built first and does not depend on Conclave. The active
r4 documents still described a near-term integration, live Marketing evidence
delivery, and joint contract approval. That created unnecessary ownership and
schedule conflicts between the two projects.

### What changed

1. The Conclave MVP is now independent and uses sample ad-performance data,
   local contracts, simulated feedback, and deterministic fixtures.
2. Marketing OS has no Conclave dependency and no current contract, adapter,
   evidence-delivery, test, approval, or version-pinning work.
3. The first intended real Conclave deployment remains Marketing OS, but only
   as a later optional ad-performance review connection after Marketing OS is
   already operating and collecting reliable campaign results.
4. The architecture flow now begins with sample fixtures and ends at a test
   result sink. A dashed Marketing adapter shows the optional future boundary.
5. Draft review contracts are Conclave test artifacts. They are starting points
   for possible future integration review and do not block Marketing OS.
6. The roadmap replaces joint integration gates and a live shadow pilot with
   local contract approval, fixture replay, simulated feedback, and a fixture
   pilot.
7. The ownership boundary is explicit: Conclave never creates campaigns,
   connects to Meta, discovers accounts or Pages, collects first-party events,
   approves spend, launches or changes campaigns, owns Marketing decisions,
   owns campaign outcomes, or owns Marketing learning.
8. A future Marketing adapter may submit a complete redacted performance
   snapshot and receive a recommendation. It never gives Conclave operational
   authority.

### Deferrals adjusted

- Live Marketing OS integration is outside the Conclave MVP.
- Any Marketing adapter, two-sided contract pin, or live campaign-performance
  review is deferred until Marketing OS is already reliable and a separate
  integration decision is made.

### Not changed

- Marketing OS remains the first intended real Conclave deployment.
- Conclave remains a composable structured decision-review system.
- Versioned review plans, A/B independence, one bounded cross-review round,
  two-stage C judging, immutable snapshots, and the PostgreSQL ledger remain.
- The ad-performance fixtures and comparator remain useful for independent
  Conclave testing.

---

## r4 — 2026-07-24

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_project_architecture.md`,
`MVP_build_roadmap.md`, `MVP_architecture_flow.mmd`, `design-fixtures/`,
`hyperstructure-review-contracts/`

### Why

The r3 boundary was correct, but the operational protocol still needed precise
deployment levers. Cadence had to be editable after deployment without changing
open reviews; reviewer C needed to form an independent view before judging A
and B; and the Marketing pilot needed an explicit, testable comparison profile.
The draft contracts also needed to exercise these choices before coding.

### What changed

1. Review timing is now Conclave-owned, deployment-specific configuration.
   Edits create future-effective, immutable plan revisions; open sessions stay
   pinned, and rollback creates another revision.
2. The Marketing defaults are A every four hours and B every sixteen hours from
   a common epoch, but neither value is hard-coded. C remains event-only.
3. A runs routinely. B joins on its own cadence, a material A result,
   failed-goal feedback, or a configured non-material audit sample. Triggered B
   work uses A's frozen snapshot and does not move B's next audit.
4. A/B first-round independence and one simultaneous, frozen cross-review round
   are explicit.
5. C is a two-stage judge: it first stores a blind assessment of the same
   evidence, then evaluates A/B's final claims and justifications. Its allowed
   verdicts are `select_a`, `select_b`, `synthesize`,
   `insufficient_evidence`, and `escalate`. C returns a panel recommendation,
   never an operational action; every C path requires a caller decision in the
   MVP.
   Auto-resolution is limited to plan-enabled, non-material, low-risk
   `observe` or `collect_more_data` results without actions, hard conflicts, or
   C.
6. Marketing-v1 comparison now has normalized weights, tolerance `0.25`, seven
   hard-conflict triggers, deterministic conservative merge rules, and golden
   distance vectors.
7. Requests now carry a deduplicated plan occurrence plus plan revision.
   Recommendation categories were corrected so
   `caller_decision_required` is only a result status.
8. Draft shared contracts advanced to `0.2.0`; schemas and fixtures now cover
   evidence eligibility, action ontology, comparator configuration, reviewer
   metadata, external decision summaries, and the full C path.
9. Conclave-only design fixtures now prove plan revision semantics and A-only,
   A/B, cross-review, C, result, and feedback state paths.
10. Panel evaluation is framed as directional evidence—panel delta, caller
    preference, issue catch, resolution, override, latency, cost, and observable
    calibration—not causal proof that a panel beats reviewer A.
11. The Hermes relationship is explicit: Conclave remains an independent
    kernel; Hermes may connect through an adapter as a reviewer, caller, or
    supervised pipeline.
12. The roadmap now starts implementation with a provider-free Phase 1A:
    contract models, ledger constraints, schedule expansion, fixed state
    transitions, fake reviewers, and fixture replay.

### Deferrals adjusted

- A generalized workflow DSL, multiple domain task packs, learned routing, more
  than three reviewer slots, and unbounded debate remain deferred.
- Contract extraction into an independently versioned repository or artifact
  is required before either application ships, but does not block local
  Conclave foundation work.
- Direct Meta access, Telegram approval, Marketing policy enforcement,
  execution, outcome ownership, and learning remain outside Conclave.

### Not changed

- Marketing is the first customer and optimization target.
- Conclave is a structured decision-review system, not an AI engine.
- The MVP is a modular monolith with PostgreSQL and no production Marketing
  access.
- Marketing remains authoritative for domain data, policy, decisions, actions,
  outcomes, and knowledge.

---

## r3 — 2026-07-24

**Requested by:** Al
**Applied by:** Codex
**Scope:** `README.md`, `MVP_project_architecture.md`,
`MVP_build_roadmap.md`, `MVP_architecture_flow.mmd`

### Why

Conclave is being built as its own project alongside Hyperstructure Marketing
OS. The prior design coupled the review kernel to Meta ingestion, Marketing
materiality and comparison code, Telegram approvals, outcome interpretation,
and Marketing knowledge. The boundary was revised so each project can evolve
independently through stable contracts.

### What changed

1. Marketing now owns platform connectors, evidence preparation, deterministic
   quality and tracking health, domain materiality, action and experiment
   ontology, policy, approval, execution, outcomes, and learning.
2. Conclave owns review sessions, reviewer routing and independence,
   comparison, disagreement, bounded cross review, reviewer-C tie-breaking,
   reviewer adjudication, and structured review output.
3. Direct Meta and Telegram adapters were removed from the Conclave
   architecture and roadmap.
4. `review-request/v1`, `review-result/v1`, and `review-feedback/v1` became the
   integration seams.
5. Decision and outcome records in Conclave became opaque external references
   used only for reviewer-performance evaluation.
6. The architecture flow now begins and ends at the Marketing OS boundary.

### Deferrals adjusted

- All platform access, authoritative Marketing approvals, execution, Marketing
  outcome ownership, and Marketing learning promotion are explicitly outside
  Conclave.

### Not changed

- Modular-monolith architecture and PostgreSQL review ledger.
- Reviewer A/B independence, one bounded cross-review round, and reviewer C as
  tie-breaker.
- Single-reviewer baseline, structured claims, no silent provider fallback,
  and immutable review snapshots.

---

## r2 — 2026-07-24

**Requested by:** Al
**Applied by:** Conclave assistant, in a Cowork working session, on Al's
instruction
**Scope:** `README.md`, `MVP_project_architecture.md`, `MVP_build_roadmap.md`,
`MVP_architecture_flow.mmd`

### Why

The r1 design used two reviewers (primary + secondary) with a human adjudicator.
Two reviewers can disagree but cannot resolve, and the design did not measure
whether review added value over a single model. Al directed a move to a
three-position reviewer panel and a set of related improvements so the system
can audit itself with less human involvement, use any AI (or non-model checker)
behind a common rail, and stay composable toward future domains such as Memory
Machine content review.

### What changed

1. **Three reviewer positions.** Reviewers A (primary) and B (secondary)
   ping-pong; reviewer C is a tie-breaker invoked only for surviving
   disagreement. Reviewers are modeled as configurable slots with a
   `reviewer_type`, so each can be a different model, the same model, or a
   non-model deterministic checker.
   - README: §2, §5.2, §5.14, §8, §9 flow/modules/persistence/state machine.
   - Architecture: decision list, flow, Reviewer Runtime, persistence,
     principles, approval table.
   - Roadmap: Phase 1, Phase 3, Phase 4a/4b.

2. **Independent assessment framed by a shared goal, then tolerance.** Each
   reviewer answers the same pipeline question (change / leave running /
   experiment / collect more / freeze / escalate) framed by the goal. A–B
   distance is mapped to a fixed disagreement vocabulary and compared to a
   configured tolerance.
   - README: §5.6, §5.13, §6 Steps 3–5.
   - Architecture: Marketing Comparator.
   - Roadmap: Phase 4a.

3. **Cross review.** One bounded justify-or-revise exchange triggered when
   distance exceeds tolerance, or when a prior recorded change did not move the
   campaign toward its goal. Not an open debate loop; both rounds preserved.
   - README: §5.8, §5.13, §6 Step 6.
   - Architecture: Cross Review component.
   - Roadmap: Phase 4b.

4. **Tie-breaker cadence-independent secondary.** Reviewer B runs on its own
   cadence (e.g. 16h vs A's 4h) so A cannot suppress review; a random sample of
   non-material runs is still cross-checked.
   - README: §6 Steps 1 & 4, §7.
   - Architecture: Scheduler responsibilities, Independence.
   - Roadmap: Phase 4a.

5. **Single-reviewer baseline.** Every review records what reviewer A alone
   would have recommended, so the pilot can measure whether the panel changed
   the decision and whether that led to better outcomes.
   - README: §5.15, §6 Step 3, §10 Phase 7, §11.
   - Architecture: persistence (`baselines`), Independence.
   - Roadmap: Phase 3, Phase 7 value metric.

6. **Configurable adjudicator with auto-resolve.** Adjudication is a role, not a
   person. On agreement within tolerance and non-material results, the run
   auto-resolves without paging a human (logged and overridable). Material or
   tie-broken results page Alex.
   - README: §5.10, §6 Step 8.
   - Architecture: Adjudicator component, principles, approval table.
   - Roadmap: Phase 4b.

7. **Hermes as a learning assistant.** Named as a post-MVP seam: Hermes reads
   candidate findings and the audit ledger and proposes documented context,
   draft skills, and improved prompts, all staying candidate until human
   approval. Also usable as a reviewer slot.
   - README: §12, §13.
   - Architecture: Reviewer Runtime note.

8. **Domain contract.** `domains/base.py` names the functions every domain
   implements (`build_snapshot`, `quality_checks`, `materiality_rules`,
   `comparison_rules`, schemas, prompts). Marketing is the first
   implementation; a second domain is a drop-in, not a re-architecture.
   - README: §9.4, §14.
   - Architecture: Domain Contract component, module tree.

9. **Testable Phase 0 gate.** The fixture gate now requires two independent
   classifiers to label every snapshot field as evidence/context/policy/goal/
   quality and match, replacing the fuzzy "no ambiguous fields."
   - README: §10 Phase 0.
   - Roadmap: Phase 0.

### Deferrals adjusted

- One bounded cross-review round is now in scope; unbounded multi-round debate
  remains deferred.
- Reviewer C tie-breaking is in scope; model adjudication of final material
  decisions remains deferred.
- More than three reviewer slots remains deferred.

### Not changed

- Read-only Meta access and the full "never write / never spend" boundary.
- Modular monolith, PostgreSQL ledger, FastAPI/Pydantic stack.
- Evidence-vs-confidence separation and the immutable snapshot model.

---

## r1 — 2026-07-14

**Requested by / Applied by:** Al

Initial proposed design: Marketing-first, read-only MVP with one primary and one
blind secondary reviewer, materiality gating, Marketing comparator, Telegram
decision loop, outcome recording, and candidate findings. This is the baseline
against which r2 is recorded.

---

## Entry template (copy for the next revision)

```
## rN — YYYY-MM-DD

**Requested by:** <name>
**Applied by:** <name / session>
**Scope:** <files touched>

### Why
<reason for the change>

### What changed
<numbered list, each pointing to the doc and section it applies to>

### Deferrals adjusted
<what moved into or out of scope>

### Not changed
<key invariants preserved>
```
