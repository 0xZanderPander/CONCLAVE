# Conclave Glossary

Maps the product vocabulary on the Notion CONCLAVE page to the vocabulary in
this repository, and records where the fixed three-seat assumption actually
lives.

Written 2026-08-27, before composability work begins. The Notion page is the
authority on product direction; this file is the authority on what that
direction means in code.

Status values: **BUILT**, **PARTIAL**, **MISSING**, **COLLISION**.

## Mapping

| Notion object | Repo today | Status | Notes |
|---|---|---|---|
| **Council** | `ReviewPlanRecord` + `ReviewPlanRevisionRecord` | PARTIAL | A Council is *configuration*. A review plan revision is already versioned, pinned configuration carrying cadence, tolerance and slot definitions. Council generalizes the review plan revision. |
| **Council run** | `ReviewSessionRecord` | BUILT | Immutable, resumable, pinned to a plan revision. Rename only. |
| **Seat** | `ReviewerSlotRecord` (`reviewer_slots`) | PARTIAL — closer than the docs suggest | Already carries `reviewer_type` (model / deterministic_checker / human), `provider`, `model`, `role_version`, `prompt_version`, `schema_version`, scoped to `plan_id` + `plan_revision`. Blockers: `slot` is `String(1)` constrained to A/B/C, and `ReviewerSlot` is a literal A/B/C enum. |
| **Edge** | nothing | MISSING | Blind independence is an invariant enforced by orchestration control flow, not a stored relation. This is the primary new object. |
| **Shared Context** | `RequestSnapshotRecord` | BUILT | Immutable and hashed. Exactly shared context. |
| **Seat Context** | `reviewers/prompts.py` + `prompt_version` on `reviewer_slots` | PARTIAL | Versioned per role, but prompt bodies live in code rather than data. |
| **Policy** | `ReviewPlanRevisionRecord` + `TaskPackRevisionRecord` | PARTIAL / SPLIT | Cadence and triggers live on the plan; tolerance and comparator weights live on the task pack. Notion treats Policy as one object. |
| **Termination** | `ReviewState` terminal members + `_TERMINAL_STATES` | PARTIAL | Exists, but hardcoded rather than configured. |
| **Task** | — | MISSING | Deferred. Not required for composability. |
| **Worker** | `SchedulerWorkItemRecord`, `scheduling/worker.py` | **COLLISION** | The repo uses "worker" for the queue/scheduler process. Notion's Worker is a delegated executor agent. Same word, unrelated meaning. Must be resolved before either term enters new code. |
| **Decision Log** | ledger + `auditing/verification.py` + event outbox | BUILT | Strong. The decision verifier recomputes routing from stored reviewer outputs rather than trusting recorded labels. |

## Concepts this repo has that Notion does not name

These are real and must not be lost in the generalization.

- **Task Pack** — the domain contract: comparator weights, tolerance, materiality
  ontology, evidence schema. Notion has no domain-pack object, and Policy alone
  does not cover it.
- **Revision pinning** — plan and task-pack revisions are pinned per session, so
  a config change never mutates open work. Council configurations will need
  identical semantics.
- **Baseline** — Reviewer A's recommendation is recorded as the single-reviewer
  baseline. Panel value is measured against it. A generalized Council must
  preserve a designated baseline seat or panel value becomes unmeasurable.
- **Evidence quality vs reviewer confidence** — deliberately separate concepts.

## Where the three-seat assumption actually lives

Roughly 290 literal A/B/C references, concentrated in:

| File | Hits |
|---|---|
| `orchestration/service.py` | 92 |
| `reviewers/provider_contracts.py` | 54 |
| `pilot/runner.py` | 27 |
| `pilot/runtime.py` | 22 |
| `auditing/verification.py` | 22 |
| `reviewers/prompts.py` | 18 |
| `orchestration/state_machine.py` | 16 |
| `ledger/repository.py` | 8 |
| `domain/enums.py` | 8 |
| `pilot/phase8_safety.py` | 6 |
| `plans/models.py` | 4 |
| `plans/scheduling.py` | 2 |
| `scheduling/service.py` | 1 |

**The structural blocker is `ReviewState`.** It enumerates a state per reviewer:
`REVIEWER_A`, `REVIEWER_B`, `REVIEWER_C_INDEPENDENT`, `REVIEWER_C_JUDGING`,
plus `REVIEWER_A_FAILED`, `REVIEWER_B_FAILED`, `REVIEWER_C_FAILED`. A Council
with N seats cannot enumerate one state per seat.

`ReviewStage` (`INDEPENDENT` / `CROSS_REVIEW` / `JUDGING`) is already the general
form. Direction: a state becomes a `(stage, seat_id)` pair rather than a flat
per-seat enum member.

## Naming decisions still required

1. **Worker collision.** Rename the repo's scheduler worker, or rename Notion's
   Worker. Do not let both stand.
2. **Package name.** `conclave-review` bakes in the word being generalized away.
3. **Council vs review plan.** Does Council replace the review plan in code, or
   sit above it as a separate object?
4. **Seat identifier.** `String(1)` A/B/C must become a free identifier, and the
   marketing configuration must keep using A/B/C as its seat names so existing
   fixtures and audit records stay readable.
