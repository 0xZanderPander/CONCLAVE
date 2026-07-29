# Conclave

## Status

Active MVP build. Foundation phases 1A and 1B, the transport-neutral event
boundary, Phase 2 task-pack routing, and the approved Phase 3 reviewer-A
provider boundary are implemented and verified with sample data, local tests,
and the dedicated Conclave Supabase project. Phase 4A now adds the production
Reviewer B boundary and the first live same-snapshot A/B comparison.

The normal worker now selects A-only, A/B agreement, cross-review, or reviewer C
from request and recommendation materiality, scheduled and failed-goal
triggers, weighted disagreement, merge compatibility, and hard triggers. The
explicit fixture-path selector remains a regression harness.

Every new session pins an immutable task-pack revision. Automatic reviews can
resume from any legal partial state, and the decision verifier recomputes the
route from stored reviewer outputs rather than trusting recorded labels.

The OpenAI Responses adapter now supports independently versioned A and B
roles for their blind first round. Both use strict structured output, explicit
runtime selection, bounded retries and cost limits, durable provider-attempt
telemetry, and deterministic normalization of materiality and source facts.
The live Reviewer-A gate and live same-snapshot A/B gate passed on 2026-07-28.
Using the same OpenAI model in that A/B gate proves plumbing and isolation; it
does not prove that the panel outperforms one model.

Phase 4B implements `assessment-v2` structured claims, exact snapshot-reference
validation, one typed A/B cross-review response, Reviewer C's blind assessment
and separate judgment, and controlled operator recovery from
`cross_review_failed`. Historical `assessment-v1` records remain readable.
The complete six-call OpenAI Phase 4B acceptance panel passed on 2026-07-28
within its $0.90 aggregate ceiling.
OpenAI supports the complete approved panel contract. An Anthropic Messages
adapter is also available behind the same provider-neutral interface. Anthropic
and Google credentials passed no-generation authentication checks on
2026-07-28. The first single-attempt Anthropic review was rejected with HTTP
400 before generation. Offline diagnosis found that the adapter had sent raw
Pydantic constraints outside Anthropic's supported structured-output subset.
The adapter now transforms the provider-facing schema while retaining
Conclave's full local validation and explicitly applies the configured
reasoning effort. A separately approved corrected one-attempt review then
passed the complete A-only `assessment-v2` path for $0.022018. No automatic
provider retry was used. The bounded OpenAI-A/Claude-B/OpenAI-C mixed panel
then passed all six stages with one attempt each, exactly two Claude calls, and
$0.1731145 total computed cost. Reviewer C selected B while the recommendation
category remained `operational_change`; the result stayed
`caller_decision_required`.

A Google Gemini Interactions adapter is now available behind the same
provider-neutral runtime. It uses `gemini-3.6-flash`, tool-free structured
output, provider-specific schema normalization, explicit thinking levels,
free-tier-aware pricing, and the existing Conclave validation and telemetry
boundaries. After explicit approval of the synthetic prompt/schema egress, its
one-attempt A-only acceptance passed in 2,268 ms with 1,612 input, 299 output,
0 reported thought, and 1,911 total tokens at $0 free-tier cost. Gemini returned
`observe`, low risk, 0.95 confidence, and adequate evidence. This proves
compatibility only; no provider has been assigned a permanent reviewer slot.

Conclave does not depend on Marketing OS, and Marketing OS does not depend on
Conclave.

## Design Documents

- [MVP Build Roadmap](MVP_build_roadmap.md)
- [MVP Project Architecture](MVP_project_architecture.md)
- [Phase 4B Contract Proposal](PHASE_4B_CONTRACT_PROPOSAL.md)
- [Editable MVP Architecture Flowchart](MVP_architecture_flow.mmd)
- [Domain Event Stream and Future Adapter Boundary](EVENT_STREAM.md)
- [Documentation Audit Log](audit/CHANGELOG.md)
- [Draft Future Review Contracts](hyperstructure-review-contracts/README.md)
- [Review-plan Revision Fixture](design-fixtures/review-plan-revision.json)
- [Fake State Traces](design-fixtures/fake-state-traces.json)

## 1. North Star

Conclave is a structured decision-review system.

Its purpose is to improve the quality, auditability, and repeatability of
important operational recommendations through independent review, explicit
claims, measured disagreement, bounded challenge, adjudication, and
outcome-linked reviewer evaluation.

Models are replaceable participants. The review process is the product.

The first intended real deployment is optional ad-performance review for
Hyperstructure Marketing OS. That connection may be considered only after
Marketing OS is already working and collecting reliable campaign results.

## 2. Core Review Pattern

```text
Caller evidence package
        |
Immutable Conclave snapshot
        |
Reviewer A assessment and baseline
        |
Reviewer B joins on its cadence or a configured trigger
        |
Blind A/B claims and evidence references
        |
Comparison against configured tolerance
        |
One bounded cross review when required
        |
Reviewer C independently assesses, then judges surviving disagreement
        |
Structured review result
        |
Caller policy and decision
        |
Optional caller outcome feedback
        |
Reviewer-performance evaluation
```

Reviewer A is the routine reviewer. Reviewer B is the independent audit
reviewer and joins on its own cadence, on configured request or recommendation
materiality, when prior outcome feedback says the goal did not move, or through
a configured non-material audit sample. Reviewer C has no cadence and is
invoked only when disagreement survives one bounded cross-review round.

During Conclave development, the caller and evidence package are simulated with
sample ad-performance fixtures. No live Marketing data is required.

Conclave optimizes for:

- better recommendations than one unchallenged reviewer
- explicit knowns, unknowns, and alternative explanations
- restraint when evidence is weak
- visible disagreement rather than false consensus
- repeatable review under the same evidence and contract version
- measurable value compared with reviewer A's baseline

## 3. Project Boundary

### Calling systems own

- canonical domain data
- source-system connectors and credentials
- evidence preparation and deterministic data-quality status
- domain materiality and action or experiment ontology
- consent, legal compliance, and data-use authority
- final policy enforcement
- human decisions and communications
- execution and verification
- outcome metrics and domain learning

### Conclave owns

- review plans and durable review sessions
- immutable copies of submitted request packages
- reviewer and provider routing
- blind first-round independence
- assessments, claims, and evidence references
- comparison and disagreement measurement
- bounded cross review
- reviewer-C tie-breaking
- reviewer adjudication
- structured review results
- review audit history
- optional external decision and outcome references for reviewer evaluation

### Conclave never

- creates campaigns
- authenticates to Meta or another caller production system
- discovers Meta accounts, ad accounts, or Pages
- collects first-party events
- fetches or enriches caller evidence
- owns ad accounts or project data
- defines consent or legal compliance
- enforces final Marketing policy
- approves spend
- launches, pauses, or changes a campaign
- sends authoritative Marketing approval requests
- executes any platform action
- spends money or publishes content
- owns Marketing decisions
- owns campaign outcomes
- owns Marketing learning or the Marketing Learning Registry
- silently substitutes a reviewer or provider
- promotes model output directly into trusted domain knowledge

## 4. Independent MVP and Future Marketing Deployment

The MVP reviews sample ad-performance packages:

```text
Sample ad-performance fixture
        |
Fixture-based review request
        |
Reviewer panel
        |
Structured recommendation
        |
Test result and simulated feedback
```

The MVP proves:

- request idempotency and schedule deduplication
- immutable evidence-package storage
- separation of evidence, context, policy, goal, and quality
- reviewer independence
- structured claims and recommendations
- evidence quality separate from reviewer confidence
- measurable disagreement and bounded challenge
- reviewer-C tie-breaking
- conservative auto-resolution of allowed non-material agreement
- structured caller-decision-required results
- optional decision and outcome feedback linkage
- panel value relative to reviewer A's baseline

The MVP includes no Marketing connection, Meta access, Telegram approval
capture, or automated execution.

After Marketing OS is operating reliably, an optional adapter may submit
redacted campaign-performance snapshots to Conclave for review. Conclave would
return a recommendation only. Marketing OS would remain responsible for every
campaign, platform connection, event, approval, action, outcome, and learning
record.

## 5. Core Concepts

### Subject

The opaque thing being reviewed. For the first task pack this is a sample
ad-performance subject. A future caller may replace sample identifiers with its
own opaque identifiers.

### Review Plan

A versioned configuration containing:

- subject and caller
- reviewer A, B, and C slots, roles, providers, and reviewer types
- independently configurable A and B cadence definitions
- a common schedule epoch, timezone, collision policy, and evidence-delivery
  mode
- material, failed-goal, and audit-sample panel-expansion triggers
- disagreement tolerance
- cross-review and tie-break triggers
- prompt and output-schema versions
- permitted auto-resolve conditions
- cost and timeout limits
- provider retry, input, output, reasoning, and pricing limits

Review-plan timing is deployment configuration, not kernel code. A deployed
plan is edited by creating a new revision with an `effective_at` time. Existing
sessions remain pinned to the revision that created them; future sessions use
the new revision. Rollback is another revision, never an in-place historical
mutation.

The initial ad-performance test profile may use A every four hours and B every
sixteen hours from one epoch. These values are defaults only. When both are due,
they share one session and snapshot. A material result, failed-goal feedback,
or an audit sample may invoke B off-cadence without moving B's next scheduled
audit.

### Request Snapshot

The immutable copy of a caller submission:

```text
Evidence + Context + Policy + Goal + Quality
```

The caller also supplies evidence version, freshness, partial-data status,
tracking health, classification, allowed recommendation schemas, domain
materiality indicators, comparator configuration, plan revision, and the
scheduled or triggered occurrence satisfied by the request.

Conclave validates, hashes, and stores the request before a reviewer call. It
does not query arbitrary caller systems.

### Evidence Quality

Evidence quality describes whether the input can support a decision. Reviewer
confidence describes the reviewer's strength of belief. They remain separate.

```text
Reviewer confidence: high
Evidence quality: low
Reason: only six conversions are present
```

This cannot be presented as strong operational evidence.

### Assessment and Claim

An assessment contains:

- summary
- explicit claims
- recommendation category
- proposed action or experiment, if allowed
- assumptions and alternative explanations
- missing evidence
- evidence-quality interpretation
- risk
- confidence

Claims, not hidden reasoning or model identity, are the primary comparison unit.
Private chain-of-thought is neither required nor stored.

### Recommendation

The first task pack permits:

1. `observe`
2. `collect_more_data`
3. `experiment`
4. `operational_change`
5. `tracking_or_data_problem`
6. `freeze`

The sample ad-performance task pack defines the action and experiment
vocabulary. A future caller would supply and own its own vocabulary. Conclave
only validates reviewer output against it.
`caller_decision_required` is a result status, not a recommendation category.

### Reviewer Adjudication

Reviewer adjudication resolves panel disagreement; it does not make the
caller's operational decision.

- A result may auto-resolve only when the pinned plan allows it, the result is
  non-material and low risk, there is no hard conflict or C invocation, the
  category is `observe` or `collect_more_data`, and no operational action is
  proposed. This applies to an A-only result or A/B agreement within tolerance.
- Material, risky, or unresolved results return `caller_decision_required`.

Reviewer C is a constrained judge rather than a simple third vote:

1. C receives the same immutable snapshot and stores a blind assessment without
   A or B content.
2. C then receives A and B's final claims, justifications, and structured
   disagreement.
3. C returns a separate required judgment: select A, select B, synthesize a
   schema-valid recommendation, declare insufficient evidence, or escalate.
4. Selecting A or B publishes that reviewer's final cross-review assessment.
   Synthesis and safe fallback verdicts must include an explicit valid
   assessment. There is no inferred or default verdict.

C's resolved output is the panel recommendation. It is never an executed
action. Any result that used C is caller-decision-required in the MVP.

A future caller records any authoritative approval, rejection, amendment,
action, and outcome.

### External Feedback

The MVP uses simulated feedback fixtures. A future caller may return opaque
references to its decision, action, outcome classification, confounders, and
evidence quality. Conclave may use those references to evaluate reviewer
performance. The caller remains authoritative for the underlying records and
all learning.

## 6. Fixed MVP Protocol

1. The Conclave test harness loads an idempotent, versioned sample request
   against an approved review-plan revision.
2. Conclave validates, hashes, and stores the immutable snapshot.
3. Reviewer A assesses every due eligible request and its recommendation becomes
   the single-reviewer baseline.
4. Reviewer B joins when its cadence is due or a configured panel-expansion
   trigger fires. A and B use the exact same snapshot and remain blind in round
   one.
5. A-only non-material results may auto-resolve when the plan explicitly allows
   it. A material result cannot bypass B.
6. When B joins, the configured task-pack comparator measures A/B disagreement
   against tolerance and hard-conflict triggers.
7. One simultaneous, bounded cross-review round runs when required.
8. Reviewer C performs its blind assessment and judging stage if disagreement
   survives.
9. Conclave returns one structured review result.
10. The test harness records a simulated caller decision.
11. The test harness may submit simulated decision and outcome feedback.

A future optional caller connection uses the same boundary, but it is not part
of the independent MVP.

Retries reuse the same snapshot and reviewer assignment. Completed steps are not
repeated unnecessarily.

## 7. Independence Rules

- Whenever B joins, A and B receive the exact same immutable snapshot.
- Neither sees the other's first-round content before storing its own.
- B's approved cadence and triggered invocations are independent of A's
  conclusion; an off-cadence invocation never moves B's next scheduled audit.
- Cross review is one bounded justify-or-revise round.
- Both cross-review responses use the frozen first-round inputs; neither sees the
  other's second-round response until both are stored.
- C appears only after disagreement survives cross review, forms a blind
  assessment first, and only then judges A and B.
- Prompts, schemas, roles, providers, models, and reviewer types are versioned
  and recorded.
- Provider failure never silently reroutes to a different reviewer.
- Auditability comes from claims, evidence references, assumptions,
  disagreements, recommendations, baselines, and feedback references.

## 8. MVP Scope

### Included

- one sample ad-performance fixture stream
- draft request/result/feedback contracts exercised locally
- versioned, deployment-editable review plans
- immutable snapshots
- A routine review plus cadence- and trigger-based B panel expansion
- reviewer A/B independence and two-stage reviewer-C judging
- structured assessments and claims
- fixed disagreement vocabulary
- ad-performance comparator weights, tolerance, and hard-conflict triggers
- one bounded cross-review round
- single-reviewer baseline
- recommendation and experiment schemas
- conservative auto-resolve
- caller-decision-required results
- authenticated, immutable external feedback linkage
- reviewer-performance candidates
- token, latency, cost, prompt, and schema accounting
- append-only audit history
- typed, transport-neutral domain events with retryable subscriber delivery
- stale, invalid, and provider-failure states

### Deferred

- direct access to Meta or another caller system
- live Marketing OS data or integration
- authoritative human-decision or Telegram approval capture
- platform execution
- Marketing policy enforcement
- Marketing outcome or learning ownership
- generalized workflow-protocol builder
- unbounded multi-round debate
- more than three reviewer slots
- multiple domain task packs
- learned reviewer routing
- cross-domain reviewer scoring

## 9. Architecture

Build a modular monolith with:

- one API process
- separate scheduler and worker commands from the same package
- one PostgreSQL review ledger
- one typed domain-event stream built from that same ledger
- provider adapters behind `ReviewerRuntime`
- explicit request, result, and feedback contracts

The MVP does not require Redis, Celery, Kafka, Kubernetes, a vector database,
microservices, or a generalized workflow DSL.

See [MVP Project Architecture](MVP_project_architecture.md) for the state
machine, modules, persistence, APIs, and security requirements.

## 10. Roadmap and Acceptance

Completed foundation:

1. local request, result, feedback, comparator, plan, and trace fixtures
2. PostgreSQL ledger, immutable plan revisions and snapshots, idempotent
   scheduling, and fixed state transitions
3. persistent scheduler and worker commands with leases, retries, dead-letter
   recovery, cancellation, heartbeats, and stale-process reporting
4. common reviewer-provider interface with strict structured-output validation
   and no silent provider substitution
5. deterministic A-only, A/B, cross-review, and two-stage C fixture paths
6. one immutable `review-result/v1` record per completed fixture run
7. audit verification of legal transitions, exact path, invocation count,
   snapshot identity, result hash, and result contract
8. PostgreSQL integration tests against the dedicated Conclave Supabase project
9. typed event envelopes, concurrency-safe stream ordering, subscriber
   checkpoints, retry, deduplication, and a read-only event API
10. registered `marketing-ads/v1` task-pack validation, deterministic
    eligibility and materiality checks, weighted comparison, hard triggers,
    conservative merge, and automatic panel routing
11. explicit fixture, OpenAI, Anthropic, Gemini, or multi-provider runtime
    selection
    with no production fixture fallback
12. a stateless, tool-free OpenAI Responses adapter for blind, independently
    prompted reviewers A and B with strict structured output and
    prompt-injection boundaries
13. durable provider attempts, request/response IDs, token usage, latency,
    cost, finish status, and pricing-version metadata through migration `0009`
14. provider-attempt health and accounting summaries in the existing
    operational status API and CLI output
15. exact same-snapshot A/B enforcement, empty peer context in the independent
    round, slot-specific prompt approval, and a passing live comparison gate
16. assessment-v2 structured claim provenance, legacy assessment-v1 reads,
    structured result and event projection, and explicit cross-review failure
17. typed A/B affirm-or-revise responses with explicit peer-claim positions
18. separate production contracts for C's blind assessment and tie-break
    judgment
19. an operator-only, audited recovery operation that retries only the failed
    cross-review invocation and preserves earlier attempts
20. a fixture-tested Anthropic Messages adapter plus stage-specific provider
    limits for larger bounded review contexts
21. a fixture-tested Google Gemini Interactions adapter with explicit
    configuration, tool-free structured output, safe thought-token telemetry,
    and one successful free-tier acceptance attempt

Next:

1. verify Phase 6 migrations `0010` and `0011`, concurrent feedback/evaluation,
   cleanup, and advisors on PostgreSQL
2. run the 30-case Phase 7 fixture pilot using the implemented directional
   evaluation metrics
3. use outcome-linked evidence, rather than one-off acceptance outputs, before
   assigning permanent reviewer positions

Non-local API mode requires explicit bearer authentication and caller scopes.
Local fixture mode remains available only in development and test.

See [MVP Build Roadmap](MVP_build_roadmap.md) for acceptance gates and the full
checklist.

## 11. Hermes Relationship

For the MVP, Conclave should remain an independent review kernel rather than a
Hermes mod. Hermes can integrate through a thin adapter that implements
`ReviewerRuntime`, submits proposed actions for review, or places Conclave
around a Hermes-operated pipeline as an oversight layer. This keeps the review
process usable when Hermes is absent and makes Hermes one replaceable
participant or caller.

Hermes does not own Conclave's snapshots, scheduling, reviewer state, or ledger.

Any Hermes-generated prompt improvement or reviewer strategy remains a
candidate until explicitly approved.

A future Hermes reviewer adapter must run under a dedicated blank-slate
profile: no tools, memory, skills, browsing, or unrelated session context.
Hermes is not used by the Phase 3 reviewer-A adapter.

## 12. Future Domains

After the independent kernel is proven, the first intended deployment is an
optional Marketing OS ad-performance reviewer. Other future callers may include
software review, Memory Machine classification, ingestion quality, moderation,
research, creative direction, operational planning, and agent oversight.

Each caller supplies its own evidence adapter, data-quality status, materiality,
ontology, policy context, outcome authority, and learning process. Conclave
generalizes only review concepts proven across real callers.
