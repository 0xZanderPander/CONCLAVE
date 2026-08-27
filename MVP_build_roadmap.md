# Conclave MVP Build Roadmap

## Status

Active implementation roadmap for the independent Conclave MVP. Phases 0
through 7 are complete for the deterministic polling-based MVP, and the
three-provider compatibility gate is complete. Phase 6 feedback intake,
immutable reviewer-evaluation candidates, and directional metrics are verified
locally and on the hosted PostgreSQL project. The 34-case Phase 7 pilot passes
locally with complete result and terminal-state audit reconstruction. Phase 8
is defined as a controlled 24-case real/replay shadow pilot but remains
unauthorized and disabled.

The normal worker now routes from request and recommendation materiality,
scheduled and failed-goal triggers, weighted disagreement, merge compatibility,
and hard triggers. The Phase 1B fixture-path selector remains available only
for deterministic protocol regression tests.

Marketing OS is built separately and does not depend on Conclave.

Progress is controlled by acceptance gates rather than dates.

## MVP Outcome

```text
Sample ad-performance package
        |
Immutable Conclave request snapshot
        |
Reviewer A + single-reviewer baseline
        |
Independent reviewer B
        |
Comparison against tolerance
        |
One bounded cross review when required
        |
Reviewer C tie-breaks surviving disagreement
        |
Structured review result written to a test sink
        |
Simulated caller decision and outcome
        |
Simulated feedback returns to Conclave
```

Conclave has no campaign creation, Meta connection, account or Page discovery,
first-party event collection, spend approval, Telegram approval surface,
campaign launch or change capability, authoritative Marketing decision record,
Marketing outcome store, or Marketing Learning Registry.

## Phase 0: Approve the Local Test Contract

### Conclave Decisions

- select one sample ad-performance subject
- approve local fixture versions of `review-request/v1`, `review-result/v1`,
  and `review-feedback/v1`
- classify every request field as evidence, context, policy, goal, or quality
- approve versioned review-plan creation, revision, activation, pause, resume,
  and rollback semantics
- define reviewer A, B, and C roles, reviewer types, default cadences, and
  stances
- approve the A-routine/B-cadence-or-trigger/C-event-only session rules
- approve ad-performance comparator weights, tolerance `0.25`, hard-conflict
  triggers, and within-tolerance merge behavior
- approve reviewer C's independent-assessment and judging contract
- define conservative auto-resolve conditions
- approve the sample ad-performance recommendation and experiment schemas
- approve domain-supplied materiality indicators
- define model-call cost and timeout limits
- define redaction, retention, and deletion behavior for submitted packages

### Fixtures

- normal review
- weak evidence
- stale or invalid evidence
- tracking-unhealthy evidence
- conflicting reviewers that trigger cross review
- surviving conflict that reaches reviewer C
- non-material agreement that auto-resolves
- experiment recommendation
- duplicate review request
- fixture package satisfying one scheduled plan occurrence
- caller decision and outcome feedback
- plan revision becoming effective without changing an open session
- A-only non-material review
- scheduled B audit sharing A's snapshot
- material A result invoking B off-cadence
- failed-goal feedback forcing B and cross review
- reviewer C selecting A, selecting B, synthesizing, and escalating
- comparator test vectors with expected weighted distances

### Exit Gate

- Conclave validates every local contract and design fixture.
- Draft contract set `0.2.0` is a Conclave test artifact. It creates no
  Marketing OS requirement.
- Two independent classifiers agree on every evidence/context/policy/goal/
  quality field.
- No Conclave field requires a Meta credential, live Marketing query, or
  raw personal content.
- Tracking-unhealthy input cannot be represented as optimization-eligible.

## Phase 1A: Foundation and Review Ledger — Complete

### Build

- Python application and configuration
- PostgreSQL schema and migrations
- fixed review state machine
- reviewer slots A, B, and C
- versioned review plans and immutable plan revisions
- review sessions and per-slot/per-stage reviewer invocations
- immutable request snapshots
- assessments, claims, comparisons, baselines, recommendations, and external
  feedback references
- append-only audit events
- deterministic IDs and idempotency keys
- schedule-deduplication constraints
- health and readiness endpoints
- fake reviewer adapters

### Exit Gate

- Repeating the same request creates exactly one review run.
- Reusing an occurrence ID cannot create a second session.
- A plan edit creates a future revision; it cannot alter an open session.
- A triggered B invocation does not move B's next scheduled audit.
- A fixture moves through every normal and failure state.
- Every transition is reconstructable from the ledger.

## Phase 1B: Durable Fixture Execution and Operations — Complete

### Built

- immutable `review-result/v1` records tied to the request snapshot
- deterministic A-only, A/B agreement, bounded cross-review, and two-stage
  reviewer-C fixture execution
- exact decision-ledger verification for legal transitions, expected path,
  invocation count, shared snapshot, result hash, and result contract
- PostgreSQL work claiming with row locks and `SKIP LOCKED`
- configurable leases, retry delay, maximum attempts, and database pool limits
- dead-letter handling, manual retry, cancellation, and queue status
- persistent scheduler and worker commands with graceful stop
- runtime process start, heartbeat, stop, and stale-process reporting
- common provider registry behind the reviewer interface
- retries for provider errors and malformed structured output
- no silent provider substitution
- local fixture API and operational endpoints
- migration `20260726_0006` applied to the dedicated Conclave Supabase project
- live PostgreSQL tests for all four fixture paths and concurrent work claiming

### Exit Gate

- Every fixture path produces one contract-valid, immutable result.
- Every completed result has a verified decision ledger.
- A and B first-round calls are blind and use one immutable snapshot.
- C assesses the snapshot independently before judging A and B.
- Two simultaneous workers cannot claim the same work item.
- Recoverable work can retry; exhausted or permanent work is dead-lettered.
- An operator can inspect queue/process health, retry dead-letter work, and
  cancel unfinished work.
- Supabase tests leave no synthetic review rows behind.
- Supabase security checks show only expected informational notices for private
  RLS tables with no client policies.

## Phase 1C: Transport-Neutral Domain Events — Complete

### Built

- the existing `audit_events` ledger promoted into the one canonical typed
  domain-event history
- stable public event IDs, per-stream sequences, actors, stage, round, safe
  summaries, evidence references, confidence, correlation, causation, and
  schema version
- centralized event-type registry and validated event construction
- atomic state mutation and event persistence
- concurrency-safe sequence allocation through `event_streams`
- PostgreSQL-backed subscriber delivery state, leasing, failure recording, and
  retry
- at-least-once delivery with consumer deduplication by `event_id`
- in-memory, logging, and no-op publishers behind one transport-neutral
  interface
- read-only, sequence-paginated review-session event API
- migration `20260726_0007`, including legacy audit-event backfill, applied to
  the dedicated Conclave Supabase project
- focused event, rollback, retry, deduplication, API, and PostgreSQL concurrency
  tests

Discord, Telegram, Slack, webhooks, and communication UIs are not implemented.
A future adapter may implement `EventPublisher` and consume committed events
without changing the Conclave review protocol.

### Exit Gate

- State changes and events commit or roll back together.
- Same-stream concurrent appends cannot duplicate a sequence.
- Subscriber failure cannot roll back or corrupt a review.
- Failed delivery is retryable and safe for duplicate-aware consumers.
- Events are readable without a model provider or external service.
- The audit ledger remains the only canonical event history.

## Phase 2: Sample Ad-Performance Task-Pack Intake — Complete

### Built

- contract and schema version validation
- evidence-package hashing and immutability
- declared data-classification checks
- freshness, partial-data, tracking-health, and evidence-quality field
  validation
- separate deterministic request and recommendation materiality
- deployment-editable panel levers for both materiality types
- allowed-action and recommendation validation
- local `marketing-ads/v1` sample action ontology and comparator profile
- immutable task-pack revision hash pinned to every new session
- weighted distance, hard-trigger, and merge-rule validation
- assessment-pair golden fixtures covering every comparator dimension, hard
  triggers, merge compatibility, and conservative timing
- automatic route selection from materiality, weighted A/B distance, hard
  triggers, and failed-goal input
- comparison decisions recorded as typed events with input invocation IDs and
  the pinned task-pack hash
- initial and post-cross-review comparison history in structured results
- deterministic conservative merge for within-tolerance agreement
- automatic worker mode with explicit fixture paths retained for tests
- a separate required reviewer-C judgment contract with no inferred verdict
- selected A/B recommendation identity preserved in the final result
- state-driven, idempotent recovery from every legal partial review state
- route-aware audit verification that recomputes comparisons and final choice
- scoped static-bearer authentication for non-local API mode
- golden local tests for A-only, A/B, cross-review resolution, every reviewer-C
  selection behavior, failed-goal routing, and interruption recovery
- automatic scheduled-B routing and decision-ledger verification on the
  dedicated Conclave Supabase project
- migration `20260726_0008` for immutable task-pack revisions

### Exit Gate

- The same package always produces the same stored snapshot hash.
- Every new session pins immutable task-pack semantics by content hash.
- Conclave cannot fetch or enrich live Marketing evidence.
- Malformed input is rejected before a session is created.
- Stale evidence enters `stale_or_ineligible_evidence`.
- Tracking-unhealthy, partial, or insufficient evidence remains reviewable for
  diagnosis but is explicitly blocked from optimization.
- No fixture contains platform credentials or raw personal content.
- Comparator configuration matches the registered task-pack version.
- Reviewer C cannot publish an inferred verdict or a recommendation other than
  the selected or explicitly synthesized assessment.
- Interrupted automatic reviews resume without duplicate durable decisions.
- Non-local API startup fails without configured caller authentication.

## Phase 3: Reviewer A and Baseline

**Status:** complete. The design and limits were approved by Al on 2026-07-27,
and the live reviewer-A acceptance gate passed on 2026-07-28. The normal test
suite still uses deterministic or mocked providers and never calls a live
model unless the dedicated opt-in gate is selected.

### Build

- [x] first production provider adapter behind the existing `ReviewerRuntime`
- [x] versioned reviewer-A role and stance
- [x] provider-specific assessment generation against the existing validated
  assessment, claim, recommendation, and experiment contract
- [x] timeout, retry, token, latency, and cost accounting
- [x] strict structured output, no tools, no provider storage, and no hidden
  fixture fallback
- [x] durable per-attempt telemetry and aggregate invocation metadata
- [x] provider-attempt counts, token use, cost, average latency, and most
  recent completion in the operational status surface
- [x] one live reviewer-A acceptance call in the isolated test environment

### Exit Gate

- [x] One eligible snapshot produces one valid reviewer-A assessment from the
  live provider.
- [x] Mocked weak evidence produces `collect_more_data`.
- [x] An experiment must include hypothesis, control, isolated change, success metric,
  minimum evidence, exposure limit, stop conditions, and review time.
- [x] Invalid model output never enters the ledger as a valid assessment and is
  not retried as though it were a transient provider failure.
- [x] Retryable provider failures are bounded to two attempts.
- [x] Every provider attempt is auditable without storing raw responses or
  private reasoning.

## Phase 4A: Reviewer B and Comparison

**Status:** complete. Reviewer B has its own approved versioned role and
independent prompt. The live same-snapshot A/B acceptance gate passed on
2026-07-28 using OpenAI for both slots. That gate proves routing, isolation,
validation, telemetry, and comparison behavior. It does not prove that a
same-model panel or Conclave as a whole improves decisions.

### Build

- [x] reviewer B on its independent cadence and configured expansion triggers
- [x] blind first-round enforcement
- [x] exact same-snapshot verification
- [x] separate approved role and prompt versions for A and B
- [x] ad-performance weighted claim and recommendation comparator
- [x] fixed disagreement vocabulary
- [x] distance-versus-tolerance calculation plus hard-conflict triggers
- [x] deterministic within-tolerance merge
- [x] readable agreement and disagreement summary
- [x] live same-snapshot A/B acceptance case

### Exit Gate

- [x] Reviewer B cannot see reviewer-A content before storing its own assessment.
- [x] Known category, direction, magnitude, quality, and integrity conflicts are
  detected.
- [x] A-only, scheduled-B, request-material, recommendation-material, failed-goal,
  and audit-sample paths invoke exactly the intended reviewer slots.
- [x] Weighted comparison fixtures produce the expected distances and hard triggers.
- [x] A provider failure never silently substitutes a reviewer.

Each reviewer slot remains independently configurable by reviewer type,
provider, model, role version, and prompt version. The next evidence-quality
step is a cross-provider A/B evaluation. Provider diversity is a deployment
lever, not a requirement baked into the Conclave kernel.

## Phase 4B: Cross Review and Tie-Breaker

**Status:** complete. Local, hosted PostgreSQL, and bounded live OpenAI
acceptance gates pass.
Automatic routing, typed one-round cross review, blind C assessment, explicit C
judgment, deterministic result selection, caller-decision handling, and
controlled failed-cross-review recovery are covered by local tests.

`assessment-v2`, deterministic claim IDs, exact snapshot-reference validation,
legacy `assessment-v1` reads, structured result and event projection, and the
legal `cross_review_failed` path are implemented. The approved contracts are
recorded in [the Phase 4B contract](PHASE_4B_CONTRACT_PROPOSAL.md).

### Build

- [x] deterministic one-round cross-review route and fixture execution
- [x] preservation of both independent and cross-review rounds
- [x] reviewer C blind assessment for surviving disagreement in fixtures
- [x] reviewer C judging contract with `select_a`, `select_b`, `synthesize`,
  `insufficient_evidence`, and `escalate`
- [x] reviewer adjudication and exact selected-assessment preservation
- [x] auto-resolve only for plan-enabled, non-material, low-risk `observe` or
  `collect_more_data` results with no operational action, hard conflict, or C
  invocation
- [x] caller-decision-required result for material, C, or unresolved cases
- [x] `assessment-v2` structured claims and snapshot-reference validation
- [x] production A/B cross-review response contract and prompts
- [x] production C blind-assessment and judgment prompts
- [x] legal, auditable cross-review provider-failure state
- [x] controlled operator recovery that preserves provider-attempt history
- [x] second provider adapter with deterministic structured-output tests
- [x] stage-specific provider limits for the larger C2 judgment context
- [x] opt-in live Phase 4B acceptance case

### Exit Gate

- [x] Conflict fixtures traverse cross review and reviewer C as expected.
- [x] C stores its independent assessment before receiving A/B content.
- [x] A synthesized C result must validate against the task-pack ontology.
- [x] Agreement fixtures auto-resolve without a caller decision.
- [x] Material results are marked caller-decision-required rather than decided by a
  model.
- [x] Cross review cannot become an unbounded debate.
- [x] Every assessment-v2 claim references real fields in the immutable snapshot.
- [x] A cross-review provider failure preserves prior work and enters a valid
  terminal state.
- [x] An operator can reopen only the failed cross-review invocation without
  erasing prior attempts or starting another discussion round.
- [x] Production provider output passes the complete A/B/cross-review/C path.

## Phase 5: Structured Result Return

**Status:** complete for the polling-based MVP. `review-result/v1`, immutable result storage,
snapshot linkage, automatic result construction, local API retrieval, and
idempotent result persistence exist. Transport callback delivery and its retry
policy are explicitly deferred; polling is the MVP return path.

### Build

- [x] `review-result/v1`
- [x] local result retrieval through polling, with a future callback left behind
  the draft boundary
- Deferred: callback delivery retry and deduplication
- [x] evidence version and snapshot hash linkage
- [x] result categories for observation, more data, experiment, operational change,
  freeze, and tracking/data problems
- [x] result status for caller decision required
- [x] explicit confidence, evidence quality, missing evidence, risk, and
  disagreement fields

### Exit Gate

- [x] The test harness can retrieve one complete, validated result.
- [x] Immutable result persistence cannot create duplicate recommendations.
- [x] The result contains no instruction that bypasses caller policy.
- [x] Conclave sends no Telegram approval and performs no platform write.
- Deferred: optional callback delivery must retry without duplicating a result
  if it is added after the MVP.

## Provider Diversity Gate Before Phase 6

**Status:** complete for provider compatibility. The corrected one-attempt
Claude A-only review passed for $0.022018. The OpenAI-A/Claude-B/OpenAI-C panel
then passed all six one-attempt stages with exactly two Claude calls and
$0.1731145 total computed cost. The Gemini adapter's mocked boundary suite and
separately approved one-attempt free-tier A-only review also passed. The
structured comparison is recorded below; it does not justify permanent
reviewer-slot assignment.

### Build

- [x] Anthropic credential authentication check without a model generation
- [x] Google credential authentication check without a model generation
- [x] Anthropic adapter behind the common reviewer interface
- [x] one low-cost Anthropic independent-review acceptance call
- [x] one bounded mixed panel with OpenAI in A and C and Claude in B
- [x] no more than two Claude calls in that mixed-panel acceptance run
- [x] Gemini adapter behind the common reviewer interface
- [x] mocked Gemini contract, retry, telemetry, and failure tests
- [x] one free-tier Gemini independent-review acceptance call
- [x] comparison of OpenAI, Claude, and Gemini structured outputs before
  permanent reviewer-slot assignment

Passing this gate proves provider compatibility and creates evidence for slot
selection. It does not prove that multiple providers improve decisions.

### First Anthropic attempt — 2026-07-28

- Route: A-only independent review using `claude-sonnet-5`.
- Bound: one provider attempt, low effort, 4,000 output tokens, and a $0.10
  request ceiling using the active introductory pricing.
- Result: permanent HTTP 400 before generation; no structured reviewer output
  or token usage was returned.
- Conclave accounting: zero generated tokens and $0.00 computed model cost.
- End-to-end test wall time: 7.9 seconds. Per-provider latency was not retained
  after the isolated SQLite acceptance harness disposed its failed session.
- Diagnosis: the provider-facing schema contained raw Pydantic constraints
  that Anthropic documents as unsupported for direct structured-output
  requests. The adapter now performs the documented provider-specific schema
  transformation and still validates the response against Conclave's original
  contract.
- Guardrail result: no silent retry, provider substitution, cross review, or
  mixed-panel call occurred.

### Corrected Anthropic acceptance — 2026-07-28

- Authorization: a separate explicit approval superseded the original
  one-attempt stop only for one corrected request.
- Route: A-only independent review using `claude-sonnet-5`.
- Result: one successful provider attempt and one contract-valid
  `assessment-v2`; no raw response or hidden reasoning was stored.
- Telemetry: 44,478 ms provider latency, 5,164 input tokens, 1,169 output
  tokens, 6,333 total tokens, and $0.022018 computed cost under the active
  introductory pricing.
- Guardrail result: no retry, provider substitution, cross review, or mixed
  panel occurred.

### Mixed OpenAI/Claude/OpenAI panel — 2026-07-28

- Route: the bounded `c_tie_broken` acceptance path using the synthetic
  surviving-conflict fixture.
- Calls: six successful structured stages with exactly one attempt each:
  OpenAI A independent, Claude B independent, OpenAI A cross review, Claude B
  cross review, OpenAI C blind assessment, and OpenAI C judgment.
- Claude bound: exactly two calls, as approved; no retry or provider
  substitution occurred.
- Aggregate telemetry: 39,900 tokens, 113,898 ms summed provider latency, and
  $0.1731145 computed cost.
- OpenAI telemetry: four calls, 22,856 tokens, 47,775 ms, and $0.1154025.
- Claude telemetry: two calls, 17,044 tokens, 66,123 ms, and $0.057712.
- Structured comparison: A and B independently recommended
  `operational_change` with adequate evidence. A assessed medium risk at 0.78
  confidence with three claims and one action; B assessed low risk at 0.62
  confidence with six claims and two actions.
- Cross review: A retained medium risk and 0.78 confidence; B retained low risk
  and moved from 0.62 to 0.60 confidence.
- Reviewer C: the blind assessment also recommended `operational_change` with
  adequate evidence, medium risk, 0.80 confidence, five claims, and two
  actions. C then selected B at 0.73 judgment confidence.
- Result: `caller_decision_required`. The category did not change from A's
  baseline, but the selected final assessment did. The current public
  `changed_by_panel` flag compares category only and therefore remained false;
  Phase 6 must not treat it alone as the full panel-change indicator.
- Interpretation: this proves transport and contract compatibility only. It is
  not evidence that Claude is a better B, that the panel improved the
  recommendation, or that any observed difference is causal.

### Gemini free-tier acceptance — 2026-07-28

- Authorization: Al explicitly approved one request containing only Conclave's
  synthetic fixture and reviewer prompt/schema after being told that Google may
  use free-tier content to improve its products.
- Route: A-only independent review using stable `gemini-3.6-flash` through the
  current Interactions API.
- Bound: one provider attempt, low thinking, 4,000 output tokens, a $0.01
  Conclave ceiling, and free-tier pricing pinned at $0.
- Result: one successful provider attempt and one contract-valid
  `assessment-v2`; no tool, retry, fallback, provider substitution, raw
  response storage, or thought summary was used.
- Output: `observe`, low risk, 0.95 confidence, adequate evidence.
- Telemetry: 2,268 ms provider latency, 1,612 input tokens, 299 output tokens,
  0 reported thought tokens, 1,911 total tokens, and $0 computed free-tier
  cost.

### Three-provider structured comparison

| Evidence available | Structured result | What it establishes |
|---|---|---|
| OpenAI A on the surviving-conflict fixture | `operational_change`, adequate evidence, medium risk, 0.78 confidence, three claims, one action | Complete panel-contract compatibility |
| Claude B on that same fixture | `operational_change`, adequate evidence, low risk, 0.62 confidence, six claims, two actions | Cross-provider compatibility and a materially different structured assessment |
| Gemini A on the base A-only fixture | `observe`, adequate evidence, low risk, 0.95 confidence | Gemini contract and transport compatibility |

The Gemini run used a different fixture from the surviving-conflict panel, and
OpenAI and Claude occupied different reviewer roles. The values therefore
cannot be treated as an apples-to-apples quality ranking. No permanent slot is
assigned; Phase 6 outcome-linked evaluation is the next decision-quality gate.

## Phase 6: External Feedback and Reviewer Evaluation

**Status:** complete and hosted verified. Authenticated feedback intake produces
one immutable, versioned reviewer-evaluation candidate, compares the complete
published Reviewer-A baseline with the complete selected result, and exposes
explicitly directional metrics. Hosted migrations `20260728_0010` and
`20260728_0011`, concurrent feedback/evaluation replay, complete table shape,
RLS, policy, privilege, audit reconstruction, and zero-row cleanup checks pass.
Hosted security and performance advisors report no warning or error findings.

### Build

- [x] validated `review-feedback/v1` schema and fixture
- [x] authenticated feedback API and durable session linkage
- [x] one immutable, idempotent feedback record per review session
- [x] safe `feedback_recorded` event without copied opaque references
- [x] simulated decision, action, and outcome references in the ledger
- [x] beneficial, harmful, no-effect, mixed, and inconclusive reviewer-result
  classifications
- [x] confounder and evidence-quality persistence
- [x] hosted migrations `20260728_0010` and `20260728_0011` plus PostgreSQL
  concurrency verification
- [x] immutable, versioned reviewer-evaluation candidates
- [x] complete published single-reviewer versus selected-result comparison
- [x] panel-change, caller-preference, issue-catch, cross-review-resolution,
  reviewer-C, override, latency, and cost indicators
- [x] authenticated feedback/evaluation retrieval and aggregate directional
  metrics by route

### Exit Gate

- A run traces from request through reviewers, result, and external feedback.
- Conclave does not own caller decisions, actions, metrics, outcomes, causal
  interpretation, or learning.
- Conclave cannot promote a reviewer-evaluation candidate into trusted domain
  knowledge.
- Evaluation output describes directional panel-value indicators and does not
  claim causal proof from an unobserved counterfactual.

## Phase 7: Fixture Pilot and Hardening

**Status:** complete for the deterministic local pilot. All 34 expected
outcomes pass: 31 runs complete through feedback and evaluation, while stale
evidence and two malformed-output cases stop in their explicit terminal states.
The pilot verifies retries, one controlled cross-review recovery, idempotency,
same-snapshot reviewer isolation, evidence traceability, result clarity, route
metrics, and all 34 audit traces. See
[`PHASE_7_PILOT_REVIEW.md`](pilot-results/phase7/PHASE_7_PILOT_REVIEW.md).

### Coverage

- [x] at least 30 synthetic or replayed fixture runs
- [x] at least five material result paths
- [x] stale, partial, and tracking-unhealthy requests
- [x] malformed reviewer output
- [x] provider timeout
- [x] disagreement, cross-review, and reviewer-C cases
- [x] auto-resolved agreement
- [x] experiment and `collect_more_data` results
- [x] complete external feedback records across all 31 completed cases

### Evaluate

- [x] schedule and idempotency reliability
- [x] reviewer independence
- [x] result clarity and usefulness in fixture review
- [x] synthetic review latency and cost aggregation
- [x] failure recovery and safe terminal containment
- [x] evidence-version traceability
- [x] completed and terminal-state audit reconstruction
- [x] directional panel-change rate
- [x] caller panel preference when supplied
- [x] additional issue-catch rate
- [x] cross-review resolution and reviewer-C rates
- [x] caller override rate
- [x] latency and cost by A-only, A/B, cross-review, and C path
- Deferred: calibration until both baseline and panel predictions are
  observable against non-synthetic outcomes.

### Exit Gate

- [x] The complete local acceptance checklist passes.
- [x] The fixture suite demonstrates clear, auditable recommendations.
- [x] No Conclave component has or requests Meta access.

## Phase 8: Controlled Real/Replay Shadow Pilot

**Status:** defined, not authorized, and not enabled. The complete
pre-authorization contract is
[`PHASE_8_CONTROLLED_REPLAY_PILOT.md`](PHASE_8_CONTROLLED_REPLAY_PILOT.md).

### Cohort and execution

- [x] define immutable Phase 8 case, cohort, redaction, access, approval,
  revocation, blinded-rating, and pilot-report artifact contracts
- [x] generate and drift-check the offline Phase 8 JSON Schemas
- [x] require a hash-linked, unexpired Gate 0 report and batch approval before
  either external pilot secret is read or provider adapter is constructed
- [x] require an explicit approved case scope and exact snapshot, provider,
  model, role, prompt, schema, pricing, and stage policy for every attempt
- [x] durably reserve and settle every attempt against route, batch, and whole
  pilot attempt, token, spend, and wall-time ceilings
- [x] persist a fail-closed revocation record on unauthorized access, context
  leakage, budget breach, audit-integrity failure, repeated invalid output, or
  consecutive failed sessions
- [x] implement a dedicated Phase 8 runner with separate credential-free
  cohort/Gate 0 and approved-batch execution paths
- [x] require explicit human-attested real-event or historical-replay source
  provenance and reject synthetic cohort packages
- [x] generate a sealed machine-readable and human-reviewable Gate 0 evidence
  report only after every offline check passes
- [ ] freeze 20 provider-eligible, redacted real/replay cases and four no-call
  controls
- [ ] include at least 12 outcome-linked cases, six material cases, six
  weak/partial/tracking cases, four prior-disagreement cases, and four
  observe/no-change baselines
- [ ] capture every baseline before panel output and keep outcomes hidden until
  the recommendation is frozen
- [ ] pass the $0 Gate 0 contract, redaction, hash, routing, audit, and access
  preflight
- [ ] obtain separate explicit approval for the five-case canary
- [ ] review the canary before separately approving the 15-case completion
  batch

### Budgets and access

- [ ] keep all provider access disabled until a batch-specific approval names
  exact cases, providers, models, contracts, prices, budgets, operator, and
  expiry
- [ ] enforce at most two attempts per stage, stage-specific input/output and
  cost limits, route-specific cost and wall-time limits, a $5 canary cap, a
  $10 completion-batch cap, and a $15 total cap
- [ ] allow only the pinned pilot topology; prohibit provider substitution,
  tools, browsing, storage, Marketing OS, Meta, and domain APIs
- [ ] load only pilot-specific credentials through an external secret boundary
  and revoke them after the approved batch

### Acceptance

- [ ] 100% audited completion in the canary and at least 95% cumulative
  provider-eligible completion
- [ ] 100% snapshot consistency, reviewer independence, legal route
  reconstruction, telemetry completeness, and caller-decision marking for
  material results
- [ ] zero critical recommendation defects, invalid accepted outputs, duplicate
  results, unauthorized access, provider substitution, or budget breaches
- [ ] panel results score at least 4.0/5.0 and are at least as useful as the
  baseline in at least 80% of comparable cases under blinded human review
- [ ] average cost at most $0.25 per eligible case and p95 case cost at most
  $0.75, with route-specific latency ceilings

Passing Phase 8 permits only a larger shadow pilot. It does not authorize
production routing, execution, causal claims, learned routing, or permanent
provider-slot assignment.

## MVP Acceptance Checklist

- [x] Conclave validates its local versioned contract fixtures.
- [x] Review-plan cadence values are editable through audited future revisions.
- [x] Open sessions remain pinned to their original plan revision.
- [x] Duplicate requests cannot create duplicate reviews.
- [x] A fixture package names one validated, deduplicated plan occurrence.
- [x] Every review uses a stored, hashed request snapshot.
- [x] Evidence, context, policy, goal, and quality are distinct in the request
      contract.
- [x] Evidence quality is separate from reviewer confidence.
- [x] Reviewer A and B fixture assessments are independently formed.
- [x] Whenever B or C joins, all reviewers use the exact same snapshot.
- [x] B joins only on its cadence or an approved expansion trigger.
- [x] Triggered B schedule calculation does not move its next scheduled audit.
- [x] Reviewer A's baseline is recorded.
- [x] Assessment-v2 claims reference validated evidence and alternative explanations.
- [x] Disagreement is measured and explained.
- [x] Ad-performance fixture weights total `1.0`, tolerance is explicit, and
      hard triggers bypass weighted agreement.
- [x] Cross-review fixture execution is one bounded round.
- [x] Reviewer C fixture execution assesses blindly before judging A and B.
- [x] Runtime routing invokes C only after measured disagreement survives cross
      review.
- [x] Material results return `caller_decision_required`.
- [x] Conclave has no platform credential or execution path.
- [x] Conclave has no authoritative Marketing approval surface.
- [x] Feedback is linked without becoming trusted domain truth.
- [x] Panel-value metrics are labeled directional rather than causal proof.
- [x] Provider, prompt, schema, token, latency, and cost data are auditable.
- [x] Queue failures retry without duplicating completed work.
- [x] Completed fixture results and their decision ledgers validate on
      PostgreSQL.
- [x] Committed lifecycle operations emit typed transport-neutral events.
- [x] Event delivery retries without changing committed review state.
- [x] Consumers can poll by stream sequence and deduplicate by event ID.

## Explicitly Deferred

- direct Meta or other domain-system access
- live Marketing OS integration or campaign data
- Telegram approval capture
- platform execution
- Marketing policy enforcement
- Marketing outcome ownership
- Marketing learning promotion
- generalized workflow-protocol builder
- unbounded multi-round debate
- more than three reviewer slots
- multiple domain task packs
- learned reviewer routing
- cross-domain reviewer scoring

## Optional Future Marketing Deployment

This phase is not part of the independent MVP and does not block Marketing OS.
It may begin only after Marketing OS is already working and collecting reliable
campaign results.

Its scope is limited to optional ad-performance review:

- Marketing OS may submit a complete, redacted performance snapshot.
- Conclave may return a structured recommendation.
- Marketing OS remains responsible for campaigns, Meta, accounts and Pages,
  first-party events, spend approval, every campaign action, decisions,
  outcomes, and learning.
- Conclave receives no Meta credential and performs no platform action.
- The draft future contracts must be reviewed again before any live connection.

## Immediate Next Build

1. Supply and curate the 20 actual real/replay source cases; do not substitute
   deterministic fixtures for pilot evidence.
2. Build the four controls from the reviewed cohort, then complete the two
   human redaction and source-provenance attestations.
3. Freeze the 24 packages with `phase8-freeze-cohort`.
4. Freeze and review the exact plan, access, pricing, and budget manifest.
5. Run `phase8-gate0` locally at $0 and review both evidence outputs.
6. Do not enable a live runtime until the five-case canary receives a separate,
   explicit approval.
