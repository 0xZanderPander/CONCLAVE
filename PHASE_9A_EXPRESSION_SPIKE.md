# Phase 9A — Expression Spike Findings

Revision 2, 2026-08-27. No code changed. Artifact under review:
`councils/marketing-ad-performance.v1.yaml`.

Revised after the Conclave model was clarified: a conclave is an **inactive,
input-triggered adversarial review body** that consumes a rigid input object and
produces an output object. It is **not a task master and does not delegate
work**. Its purpose is research, ideation, refinement, poking holes, and
recommendation — between frontier models.

**Do not begin 9B until the decisions at the end are made.**

## Verdict

The protocol is expressible, and the central question resolves favourably:
**blind isolation survives being written as data.** An empty `hears_from: []`
states the mechanism explicitly. It is more legible as configuration than as
code, where isolation is currently an emergent property of orchestration
ordering rather than a stated fact.

The clarified model also **removes** problems rather than adding them. A
stateless, input-triggered body with no delegation is a much smaller thing to
build than a persistent orchestrator.

## What the clarified model changes

### It contradicts the Notion page — needs a decision

The Notion CONCLAVE page currently carries `Task` and `Worker` as core objects,
a `Council != Worker` section, and `Worker Delegation` in the Council Structure
diagram. All three describe an orchestrator that says "I need this capability"
and has work matched to it.

If Conclave is not a task master, **those do not belong on the Conclave page**.
They describe what a VORAGO persistent project council would need — a different
thing that may *use* conclaves.

This is a product decision, not an implementation detail. Flagged, not resolved.

### It removes scope

Persistent councils, worker pools, capability matching and task delegation are
not deferred Conclave features — they are **not Conclave**. A conclave is a
function: `(config, input object) -> output object`. Stateless between runs.

### Instructions become files, not code

Seat prompts currently live in `reviewers/prompts.py`. Under the clarified model
they are Markdown assets: one shared set every seat receives (setting,
coordination, common goal, definition of done) and one private file per seat.

Note the separation: **Markdown carries the goal; the schema carries the
shape.** The repo's strict structured output stays exactly as it is. An MD file
tells a seat what it is trying to achieve; `assessment.v2` tells it what shape
to return. Both are needed and they are not substitutes.

`prompt_version` on `reviewer_slots` becomes a pointer to a versioned MD file
rather than a code reference. That is a small change with a large payoff —
changing a seat's job stops requiring a deploy.

### It resolves finding 3, against my earlier recommendation

An earlier revision argued that Reviewer C doing a blind assessment and then a
judgment should become a `(seat, stage)` binding, and advised against modelling
it as two seats.

Under the clarified model that was wrong. If a seat is **a role with a job
description**, then C is doing two jobs and should be two seats — `C_ASSESS` and
`C_JUDGE` — staffed by the same model API. That is more consistent with
one-seat-one-MD, and the audit trail becomes clearer rather than muddier: two
named roles rather than one seat with two output schemas.

Revised recommendation: **two seats.** No `(seat, stage)` binding table needed,
and `reviewer_slots` keeps its shape.

## Findings that survive

### 1. Routing is round-scoped

The same pair of seats is isolated in one round and connected in another. A and
B are blind in `independent` and mutually visible in `cross_review`.

Per-seat routing declared at setup — "A hears from nobody, sends to CMP" — works,
but it must be declared **per round**, not once per seat. Minor.

### 2. The conclave is not a DAG — still the structural finding

Cross review is **simultaneous**: A and B exchange positions and respond in one
bounded round. That is `A -> B` and `B -> A` inside a single round. A cycle.

A DAG executor topologically sorts and walks. A conclave executor must resolve
an execution mode per round: `parallel` (no intra-round routing),
`sequential` (ordered), or `simultaneous` (synchronised exchange).

This matters more under the clarified model, not less. "A debates with the other
seats to produce the most refined output" is inherently cyclic. Debate is the
product, and debate is not a DAG.

*Highest-risk item.* Get `simultaneous` wrong and already-verified cross-review
behaviour cannot be reproduced.

### 4. Termination needs guards

"A material result cannot bypass B" is an invariant, not a flow — not routing,
not activation, not an outcome predicate. Folding it into the `auto_resolved`
condition would work mechanically but hides a safety constraint inside a routing
rule, where an unrelated edit can silently weaken it.

Guards should be a distinct primitive and should appear in the decision log when
they fire.

### 5. Activation predicates are domain-coupled

Seat B joins on materiality, goal movement, and audit sampling — all **task-pack
concepts**. A conclave config cannot be validated without the domain pack's
vocabulary.

Either accept domain-typed conclaves (simple, but configs are not portable,
which undercuts the generalisation), or have domain packs publish named abstract
signals that conclaves reference. Recommend the latter.

### 6. Failure behaviour is per-seat and per-round, and hardcoded

`REVIEWER_A_FAILED` etc. become `seat_failed(seat_id)` and
`round_failed(round_id)`. The *response* is also hardcoded and needs to be
configuration: fail closed, skip, substitute, escalate. Cross review keeps its
Phase 4B operator recovery path as a human gate on one round.

### 7. The result seat is path-dependent

On the A-only path the result is A's; after adjudication it is `C_JUDGE`'s. Bind
the result to the terminal outcome, not to the conclave.

## New findings from the clarified model

### 8. "What done means" needs two mechanisms, not one

Shared instructions define done in natural language. That is right for
adversarial refinement — "keep going until the output survives criticism" is not
expressible as a predicate.

But agent-judged termination with no hard bound is how an adversarial system
burns money indefinitely. Two seats can disagree productively forever.

Every conclave therefore needs **both**: a semantic done condition in the shared
MD, and mechanical hard bounds the engine enforces regardless — max total
rounds, max spend, max wall clock. The existing protocol already does this with
`max_rounds: 1`. Generalising must not lose it.

Recommend hard bounds be **required fields**, not optional ones.

### 9. Dynamic mode is an instruction-injection surface

A dynamic conclave takes instructions from the input object. For a trusted
caller like Marketing OS that is fine.

It is not fine where input content originates from an untrusted party. An idea
submitted to a public board must never be able to carry instructions that
reprogram the council assessing it — that is prompt injection with the council's
own configuration as the payload.

Rule: in dynamic mode, the instruction block comes from the **calling system**,
never from user-authored content inside the input. The two must be separate
fields with separate trust levels, and the engine must never merge them.

Worth fixing in the contract now. Retrofitting a trust boundary after a public
surface exists is much harder.

## Revised primitive set

| Primitive | Notes |
|---|---|
| Conclave | stateless; `(config, input) -> output` |
| Input contract | rigid; conclave inactive until one arrives |
| Output contract | one output object per run |
| Shared instructions | MD: setting, coordination, common goal, done |
| Seat | one role, one job, one MD, one model binding, one output contract |
| Round | scopes routing and execution mode |
| Execution mode | parallel / sequential / **simultaneous** |
| Routing | `hears_from` / `sends_to`, declared per round |
| Activation | predicate referencing domain-pack signals |
| Termination outcome | result seat binds to outcome |
| Guard | blocks an outcome; independently audited |
| Hard bounds | required, not optional |
| Failure policy | per seat and per round |

Dropped from the earlier list: Task, Worker, delegation, persistent state.

## Schema changes implied

1. `reviewer_slots.slot` — `String(1)` A/B/C becomes a free identifier.
   Marketing keeps A and B as names; C becomes `C_ASSESS` and `C_JUDGE`.
2. `prompt_version` becomes a pointer to a versioned MD asset.
3. New tables for rounds, routing, guards.
4. `ReviewState` per-reviewer members retire in favour of `(round, seat_id)`.
   `ReviewStage` already provides the general form.
5. No `(seat, stage)` binding table — superseded by splitting C.

## Decisions required before 9B

1. **Notion contradiction.** Task, Worker, and delegation on the Conclave page
   versus "not a task master". Product decision.
2. **`simultaneous` semantics.** What each seat sees, and what a partial failure
   inside a synchronised exchange does. Highest risk.
3. **Finding 5:** domain-typed conclaves, or abstract signals from the pack.
4. **Finding 9:** the trust boundary on dynamic-mode instructions.
5. **The `Worker` collision** in `GLOSSARY.md` — now partly resolved, since if
   Conclave has no Worker concept the repo keeps the word for its scheduler.

## Unchanged

Nothing here required Phase 8 material or changes its authorization gates. The
two tracks remain decoupled. No Phase 7 fixture was examined for modification;
the 9D conformance requirement stands at all 34 cases reproducing identically.
