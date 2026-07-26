# Conclave MVP Build Roadmap

## Status

Proposed implementation roadmap for an independent Conclave MVP. Conclave is
built and tested with sample ad-performance data and fixtures. Marketing OS is
built separately and does not depend on Conclave.

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

## Phase 1: Foundation and Review Ledger

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

## Phase 2: Sample Ad-Performance Task-Pack Intake

### Build

- authenticated request endpoint
- contract and schema version validation
- evidence-package hashing and immutability
- declared data-classification checks
- freshness, partial-data, tracking-health, and evidence-quality field
  validation
- domain-supplied materiality and allowed-action validation
- local `marketing-ads/v1` sample action ontology and comparator profile
- weighted distance, hard-trigger, and merge-rule validation
- stored fixtures for deterministic tests

### Exit Gate

- The same package always produces the same stored snapshot hash.
- Conclave cannot fetch or enrich live Marketing evidence.
- Invalid, stale, or tracking-unhealthy packages enter explicit non-optimization
  states.
- No fixture contains platform credentials or raw personal content.
- Comparator configuration matches the registered task-pack version.

## Phase 3: Reviewer A and Baseline

### Build

- `ReviewerRuntime`
- first provider adapter
- versioned reviewer-A role and stance
- assessment, claim, recommendation, and experiment output validation
- single-reviewer baseline
- timeout, retry, token, latency, and cost accounting

### Exit Gate

- One eligible snapshot produces one valid reviewer-A assessment.
- Weak evidence can produce `collect_more_data`.
- An experiment includes hypothesis, control, isolated change, success metric,
  minimum evidence, exposure limit, stop conditions, and review time.
- Invalid model output never enters the ledger as a valid assessment.

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
- A-only, scheduled-B, material-A, failed-goal, and audit-sample paths invoke
  exactly the intended reviewer slots.
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

- [ ] Conclave validates its local versioned contract fixtures.
- [ ] Review-plan cadence values are editable through audited future revisions.
- [ ] Open sessions remain pinned to their original plan revision.
- [ ] Duplicate requests cannot create duplicate reviews.
- [ ] A fixture package names one validated, deduplicated plan occurrence.
- [ ] Every review uses a stored, hashed request snapshot.
- [ ] Evidence, context, policy, goal, and quality are distinct.
- [ ] Evidence quality is separate from reviewer confidence.
- [ ] Reviewer A and B assessments are independently formed.
- [ ] Whenever B or C joins, all reviewers use the exact same snapshot.
- [ ] B joins only on its cadence or an approved expansion trigger.
- [ ] Triggered B work does not move its next scheduled audit.
- [ ] Reviewer A's baseline is recorded.
- [ ] Claims reference evidence and alternative explanations.
- [ ] Disagreement is measured and explained.
- [ ] Ad-performance weights total `1.0`, tolerance is explicit, and hard triggers
      bypass weighted agreement.
- [ ] Cross review is one bounded round.
- [ ] Reviewer C appears only after surviving disagreement, assesses blindly,
      then judges A and B.
- [ ] Material results return `caller_decision_required`.
- [ ] Conclave has no platform credential or execution path.
- [ ] Conclave has no authoritative Marketing approval surface.
- [ ] Feedback is linked without becoming trusted domain truth.
- [ ] Panel-value metrics are labeled directional rather than causal proof.
- [ ] Provider, prompt, schema, token, latency, and cost data are auditable.
- [ ] Failures retry without duplicating completed work.

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

## Coding Start Gate

Phase 1 may begin when:

- r4 design documents and changelog are synchronized;
- the local draft contract package is internally valid at `0.2.0`;
- ad-performance weights and hard triggers have golden test vectors;
- one review-plan revision fixture proves editable cadence semantics;
- one fake state-trace suite covers A-only, A/B, cross-review, C, result, and
  feedback paths without any Marketing production access.

## Immediate Next Build: Phase 1A

Start with the deterministic kernel and ledger. Do not add a real model provider
or Marketing connection in this slice.

### Build order

1. Initialize source control and the Python project skeleton.
2. Add Pydantic models for plan revisions, sessions, invocations, snapshots,
   assessments, comparisons, results, feedback references, and audit events.
3. Load and validate the draft `0.2.0` shared schemas and fixtures in tests.
4. Add the first PostgreSQL migration with uniqueness and immutability
   constraints for plan revisions, occurrences, sessions, invocations, and
   snapshot hashes.
5. Implement pure schedule expansion for A/B cadences, future-effective plan
   revisions, collisions, and off-cadence B triggers.
6. Implement the fixed state-transition table with fake reviewer adapters.
7. Replay `design-fixtures/review-plan-revision.json` and
   `design-fixtures/fake-state-traces.json` as deterministic tests.
8. Add structured audit events for every accepted transition and rejected
   duplicate.

### Phase 1A done

- all contract and design fixtures pass in the project test suite;
- a repeated occurrence cannot create a second session;
- an open session cannot change plan revision;
- the fake runtime traverses A-only, A/B, cross-review, and C paths;
- every state transition is reconstructable from the ledger; and
- the code contains no provider credential, Marketing connection, policy
  decision, or execution path.
