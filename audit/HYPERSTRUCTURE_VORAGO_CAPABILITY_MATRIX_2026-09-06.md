# Hyperstructure / VORAGO Capability Matrix — Working Audit Artifact

> **Status:** PRIMARY PROPOSAL COMPLETE — independent review and owner decisions
> pending.  
> **Audit date:** 2026-09-06 PT.  
> **Authority:** use-case test and proposed ownership allocation only; it does
> not change Conclave, Hyperstructure or VORAGO canon.

## Reading rule

The matrix distinguishes four homes:

1. **Conclave governance layer** — the semantics that make deliberation
   trustworthy and auditable.
2. **Graph runtime** — generic execution mechanics that LangGraph, Microsoft
   Agent Framework or the retained runtime may provide.
3. **Capability adapter layer** — models, tools, workspaces, deterministic
   checks, humans and sub-agents invoked under scoped grants.
4. **Council/caller layer** — persistent objectives, domain authority, task and
   resource governance, credentials and external outcomes.

“Council/caller-owned” does not mean Conclave cannot call an adapter during a
run. It means the caller grants the capability and retains the external
authority, credentials, project state and consequences.

## Use-case centers

### Hyperstructure

Hyperstructure is a modular creative/operating system with its own module-owned
Review System. Conclave is an optional external reviewer. The initial Conclave
proof is a bounded Marketing OS review: Hyperstructure supplies a redacted,
structured evidence package and retains data, credentials, decisions,
approvals and actions.

### VORAGO

VORAGO uses a temporary Conclave for independent venture assessment and a
structured founding package. A persistent Project Council then plans, delegates,
uses resources, reviews work and escalates protected decisions. The open design
question is how much run-scoped tooling and sub-agent execution Conclave should
provide as a reusable primitive without absorbing persistent Council authority.

## Capability matrix

| Capability | Hyperstructure requirement | VORAGO requirement | Proposed home | Current Conclave state | Conformance implication |
|---|---|---|---|---|---|
| Versioned graph definition | Express Marketing review as a named topology | Express venture assessment and reusable deliberation/build-review shapes | Conclave governance | **MISSING** topology; plan revisions exist | Both use cases load immutable graph revisions. |
| Arbitrary typed nodes | Reviewers, comparator, verifier, result | Researchers, critics, synthesizer, judge, tool/sub-agent/human nodes | Graph runtime + Conclave type registry | **MISSING** generic node | Second topology must add node types without editing kernel routing. |
| Directed edges | Preserve blind A/B start and later disclosure | Support independent research, critique, synthesis and approval routes | Conclave governance | **MISSING** stored edge | Absence of edge must be inspectable and enforced. |
| Conditional gates | Materiality, evidence quality and disagreement | Viability, confidence, test result, protected action and human escalation | Graph runtime; condition policy pinned by Conclave | **PARTIAL**, marketing-only | Route decisions replay from stored inputs and policy. |
| Fan-out/fan-in | A/B independent review then comparison | Parallel research/work then synthesis/review | Graph runtime | **PARTIAL**, fixed pair | Deterministic parallel test with controlled merge. |
| Bounded iteration | One cross-review round | Strategy critique and failed-work correction loops | Graph runtime + Conclave budgets/termination | **PARTIAL**, one special round | Explicit maximum iterations and fail-closed exhaustion. |
| Checkpoint/resume | Recover review safely | Pause for workers/humans and resume long-running work | Graph runtime + Conclave ledger | **BUILT** for current flow | Crash at each node boundary and reproduce exact continuation. |
| Immutable input snapshot | Freeze submitted performance evidence | Freeze submission, research and authorized repository evidence | Conclave governance/artifact plane | **BUILT** for one request document | Artifact hashes remain stable across every consumer. |
| Shared artifact workspace | Review common evidence and generated comparisons | Share blueprint, work products, tests and review artifacts | Conclave artifact plane or reusable Conclave service | **MISSING** | Nodes see only granted artifact revisions. |
| Private artifact scope | A/B remain blind until disclosure | Independent research/review and protected human material | Conclave governance/artifact plane | **MISSING** persistent scope | Negative tests prove unauthorized artifacts cannot enter prompts/calls. |
| Explicit publication | Open A↔B visibility only after threshold | Publish draft to critics, worker result to reviewers, decision to caller | Conclave governance | **PARTIAL**, hardcoded cross-review | Publication creates a typed, auditable event and new visible revision set. |
| Provenance and lineage | Trace recommendation to evidence and reviewer output | Trace blueprint/work/review to sources, tools and actors | Conclave governance | **BUILT for claims/snapshots**, not generic artifacts | Every output names inputs, actor, schema and configuration revision. |
| Independent review node | Core A/B mechanism | Core venture and work-product mechanism | Deliberation component | **BUILT**, fixed contracts | Reusable component accepts caller-selected schema and visibility grant. |
| Adversarial critic | Challenge material disagreement | Attack assumptions, plans and completed work | Deliberation component | **PARTIAL**, peer cross-review only | Critic can target any versioned artifact, not only a peer assessment. |
| Comparator | Weighted Marketing disagreement | Schema-specific comparison or deterministic test result | Deliberation/deterministic component supplied by domain pack | **BUILT**, marketing-shaped | A second comparator must register without editing global enums. |
| Synthesis | Merge compatible reviews | Produce refined venture package or technical blueprint | Deliberation component | **PARTIAL**, result merging/C synthesis | Synthesis output schema is configuration-bound. |
| Judge/adjudicator | C resolves surviving disagreement | Resolve assessment/design disagreements; escalate when protected | Deliberation component | **BUILT for C**, fixed A/B inputs | Judge accepts configured candidate set and policy, not hardcoded slots. |
| Agreement/quorum | Bounded agreement before recommendation | Structured consensus before blueprint/task release | Conclave governance/deliberation component | **PARTIAL** comparator and judgment | Record who agreed, to which artifact revision and under what rule. |
| Human participation | Marketing owner decides externally | Human may occupy discussion node or protected gate | Human capability adapter + graph suspension | **MISSING** executable gate | Typed request, authorized response, expiry and exact resume. |
| Model access | Multiple independent providers | Different models for strategy, review and execution | Capability adapter | **BUILT** providers | Node config selects adapter; provider identity never determines topology. |
| Deterministic checks | Schema, evidence and policy validation | Tests, lint, schemas, repository checks and acceptance criteria | Capability adapter/node | **PARTIAL**, direct services | Fake deterministic checker participates as a first-class node. |
| Read-only research tools | Optional evidence enrichment remains caller-controlled | Venture research and bounded technical assessment | Capability adapter under caller grant | **MISSING** | Tool use records query/scope/output provenance and cannot exceed grant. |
| Code/file execution | Not needed for bounded Marketing review | Needed for build/test/review Council patterns | Capability adapter under Council grant | **MISSING** | Deterministic fake workspace first; no external action in comparison spike. |
| Sub-agent invocation | Usually unnecessary | Useful for delegated research, implementation and independent review | Capability adapter for run-scoped invocation; Council for persistent workforce | **MISSING** | Spawn/message/wait/result events, budgets and isolation tested with fakes. |
| Capability discovery | Select approved reviewer/tool profiles | Resolve requested skill to eligible worker/service | Interface in Conclave; registry and matching in Council/caller | **MISSING** | Conclave requests a capability without owning the external supply network. |
| Credentials/secrets | Hyperstructure retains all production credentials | VORAGO/caller retains resource and repository grants | Council/caller; short-lived scoped delegation to adapter | **OUTSIDE by rule** | Kernel stores references/receipts, never standing consumer credentials. |
| Side-effect authority | Conclave recommends only | Council may authorize work; protected actions may require a human | Council/caller policy; adapter enforces grant | **OUTSIDE by rule** | No node can infer authority from having a tool. |
| Per-run budget | Bound model review cost/time | Bound research, tools, workers and correction loops | Conclave governance with caller-supplied ceilings | **PARTIAL**, provider/Phase 8 controls | Aggregate and per-node budgets survive resume and fail closed. |
| Persistent project memory | Hyperstructure owns Universe/module knowledge | Council requires long-lived founding context and project state | Council/caller | **MISSING by design** | Second Conclave spike passes a state snapshot in; it does not create a project database. |
| Task emission | Recommendation may contain proposed actions | Council needs typed work tasks | Output schema may describe tasks; Council owns persistence/dispatch | **MISSING** executable task | Conclave can return a task artifact without scheduling it. |
| Task scheduling/assignment | Hyperstructure owns execution | Council owns assignment and follow-through | Council/caller | **OUTSIDE** | Keep separate from Conclave run scheduler terminology. |
| Worker/resource matching | Not a Conclave concern | Required by persistent Council | Council/caller | **OUTSIDE** | Capability request/receipt boundary is tested; matching algorithm is not. |
| Final decision authority | Hyperstructure/human retains it | Project governance/human retains protected decisions | Council/caller | **OUTSIDE by rule** | Conclave output is advisory or delegated only within explicit grant. |
| External action | Hyperstructure executes campaigns/content | Council/tool workers may modify project artifacts under authority | Capability adapter + Council/caller authorization | **OUTSIDE current Conclave** | Any future execution must be explicit, revocable, bounded and separately audited. |
| Audit/event history | Reconstruct recommendation and delivery | Reconstruct deliberation, delegation, work and gates | Conclave for run; Council for cross-run lifecycle | **BUILT for current run** | Correlation links Conclave run events to caller/Council events without merging ledgers. |
| Outcome feedback | Compare recommendations with later results | Evaluate assessment and work quality | Caller supplies; Conclave stores run-linked evaluation | **BUILT, directional** | Claims remain directional until causal design supports more. |
| Consumer domain policy | Marketing ontology, evidence quality and thresholds | Venture assessment schemas and Council authority rules | Consumer-owned versioned domain pack | **PARTIAL**, marketing embedded | Install two packs without consumer vocabulary entering shared kernel types. |
| Visual builder | Helpful for configuring review flows later | Helpful for Council/project operators later | Control-plane product above stored graph schema | **MISSING / DEFERRED** | Do not build UI before configuration and validation contracts stabilize. |

## Proposed minimum shared Conclave boundary

The smallest boundary that supports both references without becoming a generic
automation product is:

1. versioned graph configuration and validation;
2. run-scoped durable execution with conditions, fan-out/fan-in and bounded
   loops;
3. a governed artifact plane with private/shared scopes and explicit
   publication;
4. reusable deliberation components;
5. capability interfaces for models, tools, deterministic checks, humans and
   optional run-scoped sub-agents;
6. caller-supplied permissions and budgets enforced by Conclave;
7. append-only events and configuration-based decision reconstruction.

Persistent project memory, task queues, worker/resource matching, consumer
credentials, consumer policy and final external authority remain outside that
minimum boundary.

## Deterministic comparison shapes

### Shape H — preserved Hyperstructure Marketing review

```text
immutable evidence
    -> A independent baseline
    -> conditional B independent audit
    -> compare
    -> optional one-round A/B disclosure and challenge
    -> optional blind C assessment and judgment
    -> immutable recommendation
```

Acceptance: reproduce all 34 existing cases, terminal states, results and audit
reconstruction without changing fixtures.

### Shape V — run-scoped VORAGO build/review proof

```text
objective + approved project-context snapshot
    -> two independent design nodes
    -> controlled cross-critique
    -> agreement gate
    -> blueprint/task-artifact node
    -> parallel fake worker/sub-agent nodes in isolated workspaces
    -> deterministic check + independent review
    -> bounded correction loop on failure
    -> human gate for protected completion
    -> signed result package returned to persistent Council
```

This shape proves reusable mechanisms. It must use fake tools, fake sub-agents
and local artifacts during the framework comparison. It does not authorize a
live provider, repository mutation outside a disposable test workspace, or
VORAGO project execution.

## Owner decisions exposed by the matrix

1. Does Conclave ship the governed artifact plane, or only specify an interface
   to a companion workspace service?
2. Are run-scoped tool and sub-agent nodes required core capabilities, or
   optional adapters shipped separately?
3. Does “stateless Conclave” mean no cross-run project memory while retaining
   durable run state, or a stricter no-persistence product promise?
4. Is a Council always consumer-owned, or may Conclave offer a reusable Council
   product above the same kernel without placing Council state in the kernel?
5. Which names replace the current collision between a queue worker and a
   delegated worker/agent?

## Notion evidence sources

- `CONCLAVE` — product thesis, configurable Conclave, current state and Council
  boundary; last edited 2026-09-05.
- `CONCLAVE — Self-Audit Charter & Recenter Brief` — owner intent and audit
  hypothesis; last edited 2026-09-06.
- `CONCLAVE — Build Plan · SOURCE OF TRUTH` — current build sequence and
  explicit non-goals; last edited 2026-08-28.
- `Hyperstructure` — module-owned Review System and optional Conclave boundary;
  last edited 2026-08-27.
- `VORAGO — Decentralized AI Venture Board` — temporary assessment Conclave,
  structured founding package, persistent Council and tool/resource needs;
  last edited 2026-09-04.
- `VORAGO — Build Plan` — persistent Council responsibilities, capability
  adapters, security boundaries and framework spike; last edited 2026-09-04.
- `Council Runtime Substrate — Research Proposal` — LangGraph/MAF comparison and
  persistent Council hypothesis; last edited 2026-09-01.

