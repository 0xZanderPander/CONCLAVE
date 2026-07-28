# Conclave Documentation Audit Log

A historical record of substantive changes to the Conclave design documents,
design fixtures, and draft integration contracts. One entry per revision.
Newest first.

Each entry records what changed, when, who requested and applied it, and why.
Add a new entry whenever the design contract changes; do not edit past entries.

| Date | Rev | Requested by | Applied by | Summary |
|---|---|---|---|---|
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
