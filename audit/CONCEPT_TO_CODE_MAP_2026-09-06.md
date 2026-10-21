# Conclave Concept-to-Code Map — Working Audit Artifact

> **Status:** PRIMARY PASS COMPLETE — independent review pending.  
> **Audit date:** 2026-09-06 PT.  
> **Repository baseline:** `b91b57330019ff299905bf53698562cf4317ee3d`.  
> **Authority:** evidence and proposed classification only; not product canon.

## Purpose

Map the product currently described in Notion and the self-audit charter to the
implementation that exists at the frozen repository revision. This map
separates working primitives from marketing-specific implementations and from
capabilities that are only proposed.

Classification meanings:

- **BUILT** — present in code or schema at the frozen revision.
- **PARTIAL** — a useful primitive exists, but not with the required generality.
- **MISSING** — no implementation satisfying the concept was found.
- **CONFLICT** — authorities or abstractions disagree materially.

## Executive result

Conclave currently contains a strong, auditable implementation of one
deliberation topology. Its reusable strengths are immutable inputs, revision
pinning, typed outputs, blind first-round call construction, durable execution,
event history, deterministic route verification, provider abstraction and
telemetry. Its non-reusable center is the execution model: seats, stages,
visibility changes, result paths and verification are expressed as A/B/C
control flow rather than as a stored graph.

The current implementation should therefore be treated as a **verified legacy
configuration and conformance oracle**, not discarded as a failed general
kernel and not mistaken for the generalized kernel already being present.

## Concept-to-code map

| Product concept | Status | Repository implementation | Audit interpretation / required change |
|---|---|---|---|
| Configurable Conclave | **PARTIAL** | `ReviewPlanRevisionRecord.configuration`, `ReviewPlanRevision`, pinned task-pack revisions | Configuration is stored and versioned, but topology is absent. Evolve or wrap this into a versioned graph definition. |
| Council configuration | **CONFLICT** | `GLOSSARY.md` maps Council to review plans; roadmap calls Phase 9 Council composability | Notion makes Conclave configuration run-scoped and Council persistent. Settle vocabulary before naming new types. |
| Run/session | **BUILT** | `ReviewSessionRecord`; orchestration resume; scheduler work items | Strong run-durability primitive. Preserve it or require framework parity. |
| Immutable input/evidence snapshot | **BUILT** | `RequestSnapshotRecord`; canonical hash; each invocation stores `snapshot_hash` | Strong Conclave-owned invariant. Generalize from request document to versioned input artifacts without weakening immutability. |
| Seat | **PARTIAL** | `ReviewerSlot`, `ReviewerSlotRecord`, `ReviewerAssignment` | Reviewer type/provider/model and contract versions exist, but the ID is A/B/C and persisted in a one-character field. |
| Arbitrary node | **MISSING** | No generic executor/node registry | Seats are the only executable units and are model-reviewer shaped. Add a typed node/executor contract. |
| Typed ports / input-output schemas | **PARTIAL** | Pydantic review contracts and JSON Schema validation | Strong type discipline, but contracts are selected through a fixed slot/stage registry. Make schema binding configuration-driven. |
| Edge | **MISSING** | No stored edge model | Visibility and order are implied by orchestration code. An absent edge cannot yet be inspected as data. |
| Blind independence | **BUILT for current topology** | Independent-stage context validation; separate A/B calls over one snapshot; blind C call | Preserve as a kernel-enforced visibility invariant, not a prompt convention. Generalization must pass negative disclosure tests. |
| Selective disclosure/publication | **PARTIAL** | Cross-review call construction exposes exactly one peer assessment after comparison | The desired behavior exists once, hardcoded. Add explicit publication/visibility edges and artifact grants. |
| Shared context | **PARTIAL** | Immutable request snapshot | Provides common read-only input, not a writable or multi-artifact workspace. |
| Seat-private context | **PARTIAL** | Stage-specific prompts and call payload filtering | Private call context exists transiently. Prompt bodies live in code; no persistent private artifact scope or access policy exists. |
| Workspace / artifact plane | **MISSING** | No generic artifact, revision, grant or publication records | Introduce immutable artifact revisions, provenance, per-node read/write scope and explicit disclosure events. |
| Fan-out | **PARTIAL** | A and B receive the same snapshot independently, but orchestration invokes them as fixed steps | Semantics exist for one pair; generic parallel graph fan-out is absent. |
| Fan-in / aggregation | **PARTIAL** | `compare_assessments`, result builder, C judgment | Aggregators are marketing-specific functions over fixed assessment schemas. Make aggregation nodes and schemas replaceable. |
| Conditional routing | **PARTIAL** | panel-expansion rules, eligibility, materiality, comparator thresholds and hard triggers | Deterministic and well tested, but conditions route only through four named paths. Promote condition evaluation and edge selection into data. |
| Bounded loop | **PARTIAL** | exactly one A/B cross-review round; one explicit cross-review recovery | No general cycle, iteration counter, invariant, exit predicate or loop budget. |
| Termination | **PARTIAL** | `ReviewState` terminal states and result classification | Hardcoded per protocol. Store termination predicates and output selection in configuration. |
| Failure policy | **PARTIAL** | provider retries, work-item attempts, dead letters, cancellation and one recovery transition | Operational controls are strong but coupled to known stages. Define per-node retry/failure/compensation policy. |
| Checkpoint/resume | **BUILT** | persisted session state, invocations, work items and event stream | Preserve exact-once/idempotency semantics when evaluating framework checkpoints. |
| Human seat | **PARTIAL / nominal** | `ReviewerType.HUMAN` exists | No human executor, request/response lifecycle or resumable human gate was found. |
| Human approval gate | **MISSING** | `caller_decision_required` returns a result | Returning a decision requirement is not a graph suspension. Add typed request, authorized response and resume semantics. |
| Model-provider adapter | **BUILT** | provider-neutral runtime plus OpenAI, Anthropic and Gemini adapters | Strong capability-adapter precedent. Keep provider choice outside graph semantics. |
| Deterministic checker | **PARTIAL / nominal** | reviewer type exists; deterministic comparator and validators are direct services | Make deterministic checks first-class nodes rather than reviewer-shaped exceptions. |
| Tool node / tool use | **MISSING by current policy** | current prompts and provider calls prohibit tools | Define a capability interface and scoped grant model before enabling tools. Caller credentials and external authority remain outside the kernel. |
| Sub-agent execution | **MISSING** | no spawn/message/wait/interrupt/result contract | Candidate capability adapter, not justification for embedding persistent workforce governance in the kernel. |
| Nested graph / sub-Conclave | **MISSING** | no nested run node or child-run relation | Useful for composability; must preserve independent audit boundaries and budgets. |
| Run budgets | **PARTIAL** | provider attempt, token, time and cost limits; Phase 8 safety budgets | Strong provider-call controls, but not a general graph/node/artifact budget envelope. |
| Tool permissions | **MISSING** | no runtime tool grants | Product docs propose per-seat permissions. Specify capability, data, time, side-effect and cost scopes. |
| Append-only execution history | **BUILT** | audit events, event streams and typed outbox | Preserve and extend to node activation, artifact reads/writes, visibility changes, gates and capability calls. |
| Decision reconstruction | **BUILT for four paths** | `AuditVerifier` replays state and recomputes routing | A major differentiator. The generalized verifier must evaluate stored graph/configuration rather than enumerate path names. |
| Agreement / adjudication records | **PARTIAL** | comparator results, peer-claim positions and C judgment | Strong current deliberation semantics; no generic vote, quorum, consensus or signed authorization component. |
| Domain/task pack | **PARTIAL** | immutable `TaskPackRevisionRecord`, marketing-v1 registry and comparator | Revision pinning is reusable. Recommendation categories, comparator dimensions and assessment fields remain marketing-shaped. |
| Prompt/instruction versioning | **PARTIAL** | versions stored per slot; prompt bodies and contract lookup live in code | Bind versioned prompt/instruction artifacts to nodes while keeping untrusted run input separate. |
| Static versus dynamic instructions | **PARTIAL** | prompts explicitly treat snapshots as untrusted data; intake separates request structure | The trust principle exists. A generalized configuration/input schema must make instruction authority mechanically distinct. |
| Result contract | **BUILT for marketing review** | immutable `review-result/v1`, result hash and validation | Add configurable output-selection/schema binding without weakening immutable results. |
| API and caller boundary | **BUILT for current review service** | FastAPI intake, result/event/feedback and operational endpoints | Keep transport separate from graph semantics; future consumers require stable caller-neutral run APIs. |
| Feedback/evaluation loop | **BUILT, directional** | immutable feedback and reviewer-evaluation candidates | Valuable evidence infrastructure. It does not prove causal panel value and is not project memory. |
| Cross-run project memory | **MISSING by current boundary** | no persistent objective/project workspace | Current canon assigns this to a persistent Council/caller. Owner intent requires explicit confirmation of that boundary. |
| Task emission | **MISSING** | result actions are recommendation objects, not executable tasks | A Conclave output schema may describe tasks; scheduling, assignment and execution authority need not belong to the kernel. |
| Resource/worker management | **MISSING by current boundary** | repository “worker” is a queue process, not a delegated executor | Resolve the naming collision. Persistent workforce/resource routing belongs to the Council/caller layer under the current hypothesis. |
| Visual graph authoring | **MISSING** | configuration is code/JSON and operational APIs | Treat as a later control-plane concern after the graph and visibility contracts stabilize. |
| Framework substrate | **UNDECIDED** | custom state machine and scheduler | Compare LangGraph and Microsoft Agent Framework offline; retain Conclave-owned invariants above either runtime. |

## Strong primitives to preserve

1. Immutable, hashed inputs and results.
2. Revision pinning so open runs cannot be changed by later configuration.
3. Enforced first-round context isolation.
4. Strict provider outputs with local validation.
5. Provider-neutral execution and no silent substitution.
6. Durable per-attempt telemetry and bounded cost/retry behavior.
7. Append-only typed events.
8. Independent recomputation of routing from stored evidence.
9. The unchanged 34-case marketing suite as a behavior oracle.

## Structural replacement boundaries

1. Replace identity-specific `ReviewState` control flow with graph runtime state
   separate from node identity.
2. Replace the fixed provider-contract dictionary with versioned node/type
   registration and schema binding.
3. Make edge and visibility configuration first-class stored objects.
4. Separate generic artifact envelopes from deliberation-pattern contracts and
   consumer domain packs.
5. Extend the verifier to interpret the pinned graph rather than four route
   names and fixed invocation counts.

## Decisions this map does not make

- whether the graph executor is LangGraph, Microsoft Agent Framework or a
  retained custom runtime;
- whether the capability layer ships inside the Conclave product boundary;
- whether run-scoped tool/sub-agent nodes are required in the first generalized
  release;
- whether persistent Council state is owned by VORAGO or a reusable companion
  product;
- final names for Conclave configuration, Council configuration, task and
  scheduler worker.

## Evidence anchors

- `src/conclave/domain/enums.py:4-47`
- `src/conclave/plans/models.py:24-137`
- `src/conclave/domain/models.py:33-50`
- `src/conclave/ledger/models.py:53-100,170-275,318-533`
- `src/conclave/orchestration/state_machine.py:12-86`
- `src/conclave/orchestration/service.py`
- `src/conclave/reviewers/runtime.py:26-238,259-359`
- `src/conclave/reviewers/provider_contracts.py:35-167`
- `src/conclave/reviewers/prompts.py:1-188`
- `src/conclave/task_packs/models.py:11-157`
- `src/conclave/auditing/verification.py:42-92,95-533`
- `tests/test_phase7_pilot.py:6-46`
- `GLOSSARY.md:13-82`
- `MVP_build_roadmap.md:26-111`

