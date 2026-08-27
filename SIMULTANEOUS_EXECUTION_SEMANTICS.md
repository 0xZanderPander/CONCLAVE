# Execution Mode Semantics — `simultaneous`

Decision 7 of the Phase 9B gate. Written 2026-08-27.

Specifies the three round execution modes, with `simultaneous` defined precisely
enough to implement and to verify against the existing cross-review behaviour.

**Why this is the highest-risk item:** cross review is already built and already
verified. `simultaneous` is the mode that reproduces it. Get it wrong and Phase
9D conformance — all 34 fixture cases reproducing identically — cannot pass.

---

## 1. The problem

Cross review is a **simultaneous exchange**: A and B trade positions and respond
in one bounded round. That means both `A -> B` and `B -> A` exist inside a single
round. The routing graph contains a cycle, so there is no topological order to
walk.

A DAG executor cannot express this. Something has to define what "at the same
time" means.

---

## 2. Core semantics — the round is a barrier

The cycle is only apparent. It resolves at the round boundary.

> **In a simultaneous round, every seat reads state as of the end of the
> previous round. No seat's output from this round is visible to any other seat
> in this round.**

So a seat in cross review responds to the other's **position**, not to the
other's **response**. Nobody gets the last word, and nobody reacts to a reaction.
That is exactly what the current implementation does, and it is what makes the
round bounded and meaningful rather than an unstructured chat.

The consequence that makes this implementable: **a simultaneous round has no
intra-round dependencies, so its seats can execute in any order, including fully
in parallel.** The cycle exists in the routing declaration; it never exists in
execution.

---

## 3. The three modes, defined against each other

All three differ on exactly one axis: **what state a seat's `hears_from` resolves
to.**

| Mode | `hears_from` resolves to | Intra-round dependency | Execution |
|---|---|---|---|
| `parallel` | prior rounds only; no intra-round routing declared | none | any order |
| `simultaneous` | **peer outputs as of end of previous round** | none | any order |
| `sequential` | peer outputs **from this round**, in declared order | yes | declared order |

`parallel` and `simultaneous` are executionally identical. They differ only in
whether the config declares routing between seats in the round. Keeping them as
separate named modes is deliberate: it makes the author state intent, and it
makes an accidental empty `hears_from` visible as a config error rather than
silently degrading a debate into isolated assessments.

`sequential` is the only mode that serialises.

**Marketing protocol check:**
- `independent` — A and B hear from nobody -> `parallel`
- `cross_review` — A hears B, B hears A, both at end-of-`independent` state -> `simultaneous`
- `compare` — CMP hears A and B from prior rounds -> `sequential` (single seat, mode immaterial)

---

## 4. Preconditions

A simultaneous round **must not enter** unless every seat named in any
`hears_from` within the round has a completed output from a prior round.

Do not resolve a missing peer to null or to an empty set. Fail the precondition
and do not start the round.

Rationale: the A-only path never reaches cross review, because entry requires
measured disagreement, which requires B. If that invariant is ever violated by a
config change, the failure should be loud at round entry rather than producing a
seat that silently debates nobody.

---

## 5. Failure semantics

**A partial round is a failed round.**

If any participating seat fails, the round outcome is `round_failed` and the
round-level failure policy fires. For cross review that is the Phase 4B
controlled operator recovery path.

Rationale: the round's meaning is "each party responded to the other's
position." If one party did not respond, that exchange did not happen. Accepting
the surviving seat's output alone silently changes what the round asserts — you
would be recording a synchronised exchange that was in fact one-sided.

**But completed outputs are retained, not discarded.**

A seat that completed before the round failed has its output persisted and
marked `orphaned_by_round_failure`. It stays in the audit log. It was real work
and it cost real money.

### Retry and cost recovery

On retry of a failed simultaneous round:

> **Reuse an orphaned output if and only if the seat's input state hash is
> unchanged.**

If the prior-round state that fed the seat has not changed, the seat's response
is still a valid response to that state, and re-running it would bill again for
the same computation. If recovery changed the input state — an operator injected
material, a snapshot was amended — every seat re-runs.

Without this rule, every cross-review retry costs a full round. The repo already
hashes request snapshots, so the machinery to compare input state exists.

---

## 6. Order invariance is a conformance property, not an assumption

Because a simultaneous round has no intra-round dependencies, execution order
cannot affect the result.

That is testable, and it should be tested:

> **A simultaneous round must produce byte-identical output when its seats are
> executed in reversed order.**

Add this to the fixture harness. Any cross-round state leak — a seat reading a
peer's current-round output through a shared buffer, an accidental ordering
dependency in the runtime — shows up immediately as a reversed-order mismatch.
This is the cheapest available guard against the single most likely
implementation bug in this mode.

---

## 7. Multi-round simultaneous

Cross review is bounded at one round today. The mode generalises to N rounds for
genuine debate: round k reads round k-1. Each boundary is a barrier.

Two termination mechanisms, and **both are required**:

1. **Semantic** — a done condition, either a predicate evaluated at the round
   barrier or a designated seat's judgment, per the shared instructions.
2. **Mechanical hard bounds** — `max_rounds`, `max_spend`, `max_wall_clock`.
   Enforced by the engine regardless of what the seats think.

Hard bounds are **required fields, not optional**. Agent-judged termination with
no hard bound is how an adversarial system burns money indefinitely: two good
seats can disagree productively forever.

When a hard bound stops a round, the outcome is a distinct terminal state —
`bound_exhausted` — not a success and not a failure. It must be distinguishable
in the audit record and in whatever the caller receives.

---

## 8. Budget reservation happens before the round, not during

Every seat in a simultaneous round bills concurrently. By the time you know the
round's actual cost, it is already spent.

> **Before starting a simultaneous round, reserve the sum of per-seat maximum
> cost against the remaining budget. If the reservation does not fit, do not
> start the round.**

Do not check spend per seat as the round proceeds — in a parallel round there is
no safe point to stop. Reserve up front, reconcile actual against reserved at
the round barrier, and release the difference.

This is what makes the fixed submission fee safe for VORAGO: the fee sets the
budget, the reservation refuses to start a round it cannot afford, and the
conclave returns "insufficient budget to assess at this depth" instead of
overrunning.

---

## 9. Timeouts

A simultaneous round completes only when its slowest seat completes. A per-round
wall-clock bound is required. A seat exceeding it is a seat failure, which by
section 5 makes it a round failure.

---

## 10. What must be recorded for replay

Per simultaneous round:

- round id, mode, and round index within the stage
- the **input state hash** each seat read (this is what makes retry reuse and
  replay verifiable)
- which prior-round outputs were visible to which seat
- each seat's output, with its provider attempt telemetry
- reserved budget, actual cost, released difference
- round outcome: `completed`, `round_failed`, or `bound_exhausted`
- for a failed round: which seats completed, and which outputs are orphaned

Execution order is deliberately **not** recorded, because by section 6 it must
not matter. Recording it would invite a replay that depends on it.

---

## 11. Conformance checklist for 9D

- [ ] `cross_review` expressed as `simultaneous` reproduces all 34 Phase 7 cases identically
- [ ] reversed-order execution of every simultaneous round produces identical output
- [ ] a seat failure mid-round yields `round_failed`, not a partial result
- [ ] a completed seat's output survives round failure as `orphaned_by_round_failure`
- [ ] retry reuses an orphaned output when the input state hash is unchanged
- [ ] retry re-runs all seats when the input state hash has changed
- [ ] a round whose precondition fails does not start
- [ ] a budget reservation that does not fit prevents the round from starting
- [ ] `bound_exhausted` is distinguishable from both success and failure
- [ ] no Phase 7 fixture was modified to achieve any of the above

---

## 12. Open, deliberately

- Whether `parallel` and `simultaneous` stay separate named modes or collapse
  into one with a lint rule. Recommend keeping them separate — the distinction
  is intent, and intent is what configuration is for.
- Per-seat retry policy inside a round (currently: none — the round retries as a
  unit).
- Whether multi-round simultaneous is in Phase 9 scope at all, or whether
  `max_rounds: 1` is the only supported value until debate is actually needed.
  Recommend the latter: build the general shape, ship the bounded case.
