# Conclave MVP Build Roadmap

## Status

Active implementation roadmap for the independent Conclave MVP. Phases 1A,
1B, the transport-neutral event boundary, and Phase 2 sample task-pack routing
are complete.

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

### Build

- reviewer B on its independent cadence and configured expansion triggers
- blind first-round enforcement
- exact same-snapshot verification
- ad-performance weighted claim and recommendation comparator
- fixed disagreement vocabulary
- distance-versus-tolerance calculation plus hard-conflict triggers
- deterministic within-tolerance merge
- readable agreement and disagreement summary

### Exit Gate

- Reviewer B cannot see reviewer-A content before storing its own assessment.
- Known category, direction, magnitude, quality, and integrity conflicts are
  detected.
- A-only, scheduled-B, request-material, recommendation-material, failed-goal,
  and audit-sample paths invoke exactly the intended reviewer slots.
- Weighted comparison fixtures produce the expected distances and hard triggers.
- A provider failure never silently substitutes a reviewer.

## Phase 4B: Cross Review and Tie-Breaker

### Build

- one bounded justify-or-revise exchange
- preservation of both independent and cross-review rounds
- reviewer C blind assessment for surviving disagreement
- reviewer C judging stage with `select_a`, `select_b`, `synthesize`,
  `insufficient_evidence`, and `escalate`
- reviewer adjudication
- auto-resolve only for plan-enabled, non-material, low-risk `observe` or
  `collect_more_data` results with no operational action, hard conflict, or C
  invocation
- caller-decision-required result for material or unresolved cases

### Exit Gate

- Conflict fixtures traverse cross review and reviewer C as expected.
- C stores its independent assessment before receiving A/B content.
- A synthesized C result must validate against the task-pack ontology.
- Agreement fixtures auto-resolve without a caller decision.
- Material results are marked caller-decision-required rather than decided by a
  model.
- Cross review cannot become an unbounded debate.

## Phase 5: Structured Result Return

### Build

- `review-result/v1`
- local result retrieval, with future callback or polling support left behind
  the draft boundary
- result delivery retry and deduplication
- evidence version and snapshot hash linkage
- result categories for observation, more data, experiment, operational change,
  freeze, and tracking/data problems
- result status for caller decision required
- explicit confidence, evidence quality, missing evidence, risk, and
  disagreement fields

### Exit Gate

- The test harness can retrieve one complete, validated result.
- Delivery retries cannot create duplicate recommendations.
- The result contains no instruction that bypasses caller policy.
- Conclave sends no Telegram approval and performs no platform write.

## Phase 6: External Feedback and Reviewer Evaluation

### Build

- `review-feedback/v1`
- simulated decision, action, and outcome references
- beneficial, harmful, no-effect, mixed, and inconclusive reviewer-result
  classifications
- confounder and evidence-quality fields
- reviewer-evaluation candidates
- single-reviewer versus panel comparison
- panel-delta, caller-preference, issue-catch, cross-review-resolution,
  reviewer-C, override, latency, and cost indicators

### Exit Gate

- A run traces from request through reviewers, result, and external feedback.
- Conclave does not own caller decisions, actions, metrics, outcomes, causal
  interpretation, or learning.
- Conclave cannot promote a reviewer-evaluation candidate into trusted domain
  knowledge.
- Evaluation output describes directional panel-value indicators and does not
  claim causal proof from an unobserved counterfactual.

## Phase 7: Fixture Pilot and Hardening

### Coverage

- at least 30 synthetic or replayed fixture runs
- at least five material result paths
- stale, partial, and tracking-unhealthy requests
- malformed reviewer output
- provider timeout
- disagreement, cross-review, and reviewer-C cases
- auto-resolved agreement
- experiment and `collect_more_data` results
- one complete external feedback record

### Evaluate

- schedule and idempotency reliability
- reviewer independence
- result clarity and usefulness in fixture review
- review latency and cost
- failure recovery
- evidence-version traceability
- audit reconstruction
- panel-delta rate
- caller panel preference when supplied
- additional issue-catch rate
- cross-review resolution and reviewer-C rates
- caller override rate
- latency and cost by A-only, A/B, cross-review, and C path
- calibration only where both baseline and panel predictions are observable

### Exit Gate

- The complete acceptance checklist passes.
- The fixture suite demonstrates clear, auditable recommendations.
- No Conclave component has or requests Meta access.

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
- [ ] B joins only on its cadence or an approved expansion trigger.
- [x] Triggered B schedule calculation does not move its next scheduled audit.
- [x] Reviewer A's baseline is recorded.
- [ ] Claims reference evidence and alternative explanations.
- [ ] Disagreement is measured and explained.
- [x] Ad-performance fixture weights total `1.0`, tolerance is explicit, and
      hard triggers bypass weighted agreement.
- [x] Cross-review fixture execution is one bounded round.
- [x] Reviewer C fixture execution assesses blindly before judging A and B.
- [ ] Runtime routing invokes C only after measured disagreement survives cross
      review.
- [ ] Material results return `caller_decision_required`.
- [x] Conclave has no platform credential or execution path.
- [x] Conclave has no authoritative Marketing approval surface.
- [ ] Feedback is linked without becoming trusted domain truth.
- [ ] Panel-value metrics are labeled directional rather than causal proof.
- [ ] Provider, prompt, schema, token, latency, and cost data are auditable.
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

1. Review and approve the reviewer-B production prompt, independence checks,
   and provider choice for Phase 4A.
2. Implement reviewer B behind the same provider-neutral runtime and telemetry
   boundary.
3. Run one same-snapshot live A/B independence and comparison acceptance case.
4. Keep reviewer C on fixtures until its production prompt and two-stage
   judgment behavior receive separate approval.
