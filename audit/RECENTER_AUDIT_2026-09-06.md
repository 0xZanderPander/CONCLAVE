# Conclave Full Recenter Audit — Working Record

> **Status:** UNDER REVIEW — primary audit pass in progress.  
> **Opened:** 2026-09-06 PT.  
> **Authority:** working audit record only; this document does not change product
> canon, authorize implementation, select a framework, or enable Phase 8.

## 1. Frozen evidence baseline

- Repository: `/Users/az/Documents/projects/ai/CONCLAVE`
- Branch: `agent/initial-conclave`
- Commit: `b91b57330019ff299905bf53698562cf4317ee3d`
- Git state at audit opening: clean; local branch matched its observed upstream.
- Notion product authority: `CONCLAVE`, fetched 2026-09-06; last edited
  `2026-09-05T18:48:00.033Z`.
- Notion audit charter: `CONCLAVE — Self-Audit Charter & Recenter Brief`, fetched
  after the framework-comparison update; last edited
  `2026-09-06T20:25:44.109Z`.
- Notion control protocol: `CONCLAVE — Audit & Change-Control Protocol`, last
  edited `2026-09-06T19:40:39.924Z`.
- Register entries opened: `CC-AUD-001` through `CC-AUD-007`.

If any of these sources changes during the audit, later observations must name
the new revision rather than silently mixing evidence states.

## 2. Safety boundary

This audit is offline and read-only with respect to product behavior and all
external systems. It does not authorize:

- live model-provider calls or spend;
- hosted PostgreSQL or Supabase access;
- Phase 8 activation, case ingestion, or pilot-material access;
- reading `.env`, `credentials`, private redaction maps, or nearby source
  material;
- deployment, external messages, or caller-platform actions;
- adoption or installation of LangGraph or Microsoft Agent Framework.

## 3. Gate 0 verification

| Check | Result | Interpretation |
|---|---:|---|
| Offline test suite | 153 passed, 11 skipped | Current implemented behavior is healthy under the existing tests. Skips remain opt-in integration/live checks. |
| Ruff lint | Passed | No current lint defect. |
| Alembic heads | `20260728_0011` | One observed migration head. No database connection was made. |
| Phase 7 fixture breadth | 34 cases asserted | The conformance oracle exists and currently checks all expected outcomes, audit traces, independence and snapshot consistency. |

These checks validate the current fixed protocol. They do not establish a
general graph runtime, a shared artifact workspace, a second topology, or
causal panel value.

## 4. Current implementation inventory

| Intended primitive | Classification | Current evidence |
|---|---|---|
| Immutable run input | **BUILT** | `RequestSnapshotRecord` stores hashed content; invocation records reference the snapshot hash. |
| Run durability and resume | **BUILT** | Sessions, invocations, work items, leases, retries, recovery and event streams are persisted. |
| Version-pinned configuration | **PARTIAL** | Review-plan and task-pack revisions are immutable and pinned, but topology is not represented as data. |
| Blind first-round review | **BUILT for A/B/C protocol** | Independent provider calls reject peer-review context; prompts and orchestration preserve first-round isolation. |
| Selective disclosure | **PARTIAL, hardcoded** | The one A/B cross-review opening is assembled in code. There is no stored visibility policy or publication edge. |
| Directed graph topology | **MISSING** | No edge record or generic node/port model exists. Legal routing is encoded in `ReviewState` and orchestration branches. |
| Conditional routing | **BUILT for marketing protocol** | Materiality, comparator and trigger rules choose among four fixed result paths. Conditions are not general graph data. |
| Bounded loops | **PARTIAL, single special case** | One fixed cross-review round and one recovery transition exist. There is no generic bounded cycle contract. |
| Arbitrary seats or nodes | **MISSING** | `ReviewerSlot` is A/B/C; plan validation requires exactly those three; database fields are length one. |
| Typed deliberation records | **BUILT for current protocol** | Assessment claims, peer-claim reviews and Reviewer C judgment are strict, versioned Pydantic contracts. |
| Domain-neutral node outputs | **MISSING** | The central output union is assessment/cross-review/C-judgment, with marketing-oriented recommendation and evidence fields. |
| Shared artifact workspace | **MISSING** | The immutable request snapshot is common input, but there is no versioned artifact plane with per-node read/write scopes. |
| Seat-private workspace | **MISSING** | Prompt/context isolation exists at call construction; no persistent private artifact scope exists. |
| Tool-capable nodes | **MISSING by design today** | Current provider prompts and calls prohibit tools and external action. |
| Human gate as a node | **MISSING** | Caller-decision-required is a terminal result classification, not suspend/resume graph participation. |
| Sub-agent lifecycle | **MISSING** | No generic spawn, message, wait, interrupt, budget or result-collection contract exists. |
| Reconstructible decision ledger | **BUILT for four paths** | The verifier replays transitions and recomputes routing, but it explicitly knows A-only, A/B agreement, cross-review-resolved and C-tie-broken. |
| Cross-run project memory | **MISSING / caller-owned in current canon** | Only run and evaluation persistence exists; no persistent Council objective or project workspace exists. |

## 5. Preliminary findings

### CC-AUD-001 — Baseline and scope freeze

`[Codex · 2026-09-06 · AUDIT START · UNDER REVIEW]`

The repository is healthy enough to audit from the frozen commit. The current
tests and audit verifier provide a strong preservation baseline. No reason has
been found to modify existing fixtures or product behavior before the concept
and architecture review is reconciled.

### CC-AUD-002 — Conclave versus Council boundary is unresolved

`[Codex · 2026-09-06 · FINDING · UNDER REVIEW]`

The current product page makes the configurable **Conclave** the fundamental
deliberation object and describes a persistent **Council** as a separate
caller-owned upgrade layer. Repository vocabulary then maps `Council` directly
to the current review plan and calls Phase 9 `Council Composability`. That is
more than a naming blemish: it makes it unclear whether configuration belongs
to a Conclave run, a persistent Council, or both.

The owner intent recorded in the audit charter introduces a second unresolved
question: operational Councils need tools, workspaces, delegation and loops,
but it is not yet decided whether those are kernel mechanisms, governed
capability adapters, or caller-owned services.

### CC-AUD-003 — Runtime foundation requires an invariant-led comparison

`[Codex · 2026-09-06 · FINDING · UNDER REVIEW]`

LangGraph and Microsoft Agent Framework remain the two full-runtime candidates.
No framework should own or weaken Conclave's configuration versioning, evidence
provenance, blind independence, selective visibility, agreement records,
authorization records, or decision reconstruction. A deterministic comparison
must be completed before adoption, component reuse, or retention of the custom
runtime can be recommended.

### CC-AUD-004 — Current kernel is a robust vertical protocol, not a graph

`[Codex · 2026-09-06 · FINDING · UNDER REVIEW]`

The specialization is structural:

- `ReviewerSlot` enumerates only A, B and C.
- `ReviewPlanRevision` requires exactly A/B/C with role-specific cadence rules.
- `ReviewState` encodes reviewer identities and the one legal review sequence.
- the orchestration service directly calls A, B and C in fixed stages;
- result construction and audit verification recognize four named paths and
  fixed invocation counts;
- database seat and invocation identifiers are one character long.

This is not presently a defect in the verified marketing protocol. It is the
main replacement boundary for composability work.

### CC-AUD-005 — Domain pack separation is incomplete

`[Codex · 2026-09-06 · FINDING · UNDER REVIEW]`

Task-pack revision pinning is a strong reusable idea, but domain semantics still
leak into shared runtime types. The global `RecommendationCategory`, comparator
dimension registry, assessment schema, provider-contract registry and prompts
are marketing-shaped. A VORAGO design/build/review topology cannot supply a
materially different node output contract without adding more special cases to
the same kernel modules.

The recenter should preserve task packs while separating generic artifact and
node contracts from optional deliberation-pattern contracts and domain packs.

### CC-AUD-006 — Shared context is implemented; shared workspace is not

`[Codex · 2026-09-06 · FINDING · UNDER REVIEW]`

The request snapshot successfully provides immutable shared input. It should
not be described as the complete future workspace primitive. Conclave currently
has no generic artifact identity, version lineage, write authority, private
scope, publication event, visibility query, or mutation policy. Those are
required if nodes can produce work and selectively reveal it without erasing
blind independence.

### CC-AUD-007 — Canon and continuity documents have material drift

`[Codex · 2026-09-06 · FINDING · UNDER REVIEW]`

`PROJECT-STATUS.md` still describes the pre-commit Phase 8 worktree at commit
`ee3e8ce`, says the repository has no `AGENTS.md`, and frames Phase 8 as the next
build. The observed repository is clean at `b91b573`, contains `AGENTS.md` and
`GLOSSARY.md`, and the roadmap now has a Phase 9 composability track. The README
also places “panel value relative to reviewer A's baseline” under what the MVP
proves even though the same README and `AGENTS.md` correctly say causal panel
value has not been demonstrated.

These are audit findings only. Canon and continuity documents should be revised
after the boundary decisions are reviewed and explicitly authorized.

## 6. Working architecture hypothesis

The primary audit will test this separation:

1. **Conclave-owned governance:** versioned configuration, evidence and artifact
   provenance, visibility policy, independent/adversarial review semantics,
   agreement and authorization, deterministic decision verification.
2. **Graph runtime:** nodes, typed ports, edges, conditions, fan-out/fan-in,
   bounded loops, checkpoints, suspend/resume and nested execution.
3. **Capability layer:** models, deterministic checks, tools, workspace backends,
   sub-agents and external adapters under explicit permissions and budgets.
4. **Persistent Council layer:** durable objective and project state, task
   issuance, repeated Conclave runs, worker/resource governance and domain
   authority.

The audit must still determine whether the capability layer is shipped as part
of Conclave, as reusable adapters beside it, or by persistent Council callers.

## 7. Next primary-audit work

- [Concept-to-code map](CONCEPT_TO_CODE_MAP_2026-09-06.md) — primary pass
  complete; independent review pending. Notion working page:
  `https://app.notion.com/p/3d31b84dbae28168b6efe1ae072e9058`.
- [Hyperstructure/VORAGO capability matrix](HYPERSTRUCTURE_VORAGO_CAPABILITY_MATRIX_2026-09-06.md)
  — primary proposal complete; independent review and owner decisions pending.
  Notion working page:
  `https://app.notion.com/p/3d31b84dbae281f3927ddb19fcd6f993`.
- Reconstruct remaining Notion product claims and compare them line-by-line
  with repository authorities.
- Define the second VORAGO-style topology precisely enough for deterministic
  framework implementation; the matrix now freezes its proposed shape.
- Inspect authorization, failure, retry, human-gate and artifact-visibility
  semantics for missing invariants.
- Convert supported preliminary findings into register rows.
- Prepare the blind independent-review evidence packet without including the
  primary conclusions.
- Route product choices to Alex before any canonical or implementation change.
