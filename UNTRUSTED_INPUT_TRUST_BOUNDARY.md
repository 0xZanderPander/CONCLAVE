# Untrusted Input and the Dynamic-Mode Trust Boundary

Decision 9 of the Phase 9B gate. Written 2026-08-27.

Defines how a conclave handles input content authored by someone who wants a
particular outcome from the conclave.

---

## 1. The threat, stated plainly

A dynamic conclave takes instructions from its input object. VORAGO's assessment
conclave receives submissions written by the public. If submission content can
reach the instruction channel, a submitter can reconfigure the council that is
assessing their own idea.

The adversary here is unusually well positioned:

- **strong incentive** — a pass is worth real money
- **unlimited attempts** — resubmission is cheap relative to the payoff
- **full control of a large text field** — the submission is the payload
- **knowledge of the system** — the pipeline is public by design

This is not a theoretical class of attack. It is the expected steady state of
any public submission surface with an automated gate.

## 2. The governing principle

> **You cannot prevent a model from being persuaded. You can prevent persuasion
> from becoming privilege.**

Every defense below follows from this. The goal is not a conclave that can never
be fooled — that is not achievable. The goal is a conclave where a fully
successful injection changes **what a seat says** and never **what the machine
does**.

A compromised seat should be able to produce a wrong assessment. It should not
be able to remove a guard, extend a budget, silence a peer, or rewrite the
termination condition.

---

## 3. Rule one — public conclaves are static, not dynamic

The largest reduction in attack surface is structural rather than defensive.

> **Dynamic mode requires a trusted caller. Any conclave exposed to public
> submission is static.**

A static conclave carries its own instructions. Submitters supply **content**
and never supply instructions, because there is no instruction channel for them
to reach. Dynamic mode exists for trusted callers varying their own review shape
— Marketing OS adjusting its review configuration, for example.

VORAGO's assessment conclave and VC conclave are therefore **static**. This is
not a limitation to work around later; it is the correct configuration.

## 4. Rule two — separate channels, never merged

Where dynamic mode is used, the input object carries two strictly separate
fields:

| Field | Source | Trust |
|---|---|---|
| `instructions` | the calling system only | trusted |
| `content` | whatever the caller passes through | untrusted |

The engine must never concatenate these into a single undifferentiated prompt.
They are assembled with explicit demarcation (section 5) and the boundary is
recorded in the audit log.

A calling system that relays end-user text into `instructions` has broken the
contract. State this explicitly in the contract documentation, because it is the
mistake an integrator will make.

## 5. Rule three — nonce-delimited content envelopes

Untrusted content reaches a seat inside an envelope whose boundary marker is a
**per-run random nonce**, not a fixed string.

A fixed delimiter is guessable and therefore spoofable — an attacker closes the
envelope early and continues outside it. A nonce generated per run cannot be
guessed from outside.

The seat's own instructions — which are trusted Markdown — state that everything
inside the boundary is material to be assessed and never instruction to be
followed. That framing lives in the seat's MD file, not in the assembled prompt,
so it cannot be displaced by content length.

Free-text content fields carry length caps. A cap is a weak defense on its own
but it bounds payload size cheaply.

---

## 6. Rule four — containment between seats, not just at the door

**This is the part that is usually missed.**

Seat A reads untrusted content and emits an assessment. Seat B reads A's
assessment over an edge that the system treats as **trusted**. If A's output
reproduces attacker text verbatim, the injection has laundered itself out of the
untrusted channel and into a trusted one.

The trust boundary is not a perimeter. It propagates with the data.

Three containments:

1. **Structured output limits the vector.** A seat emits `assessment.v2` with
   typed fields, not free prose. Attacker text can still occupy a string field,
   but it cannot restructure the message.
2. **Quote discipline.** Any verbatim quotation of untrusted content appearing
   in a seat's output is **re-wrapped in a fresh nonce envelope** before being
   passed downstream. Quoted content stays marked as quoted content, at every
   hop.
3. **Provenance marking.** A field containing quoted submission text is flagged
   as such in the output contract, so downstream seats and the audit log both
   know which parts of a trusted message originated untrusted.

---

## 7. Rule five — the capability floor

An explicit list of things that **no input content can influence at any depth**,
whether directly, through a seat's output, or through any chain of seats:

- seat definitions, model bindings, providers
- seat instructions and shared instructions
- routing — `hears_from`, `sends_to`, round membership
- execution mode
- hard bounds — `max_rounds`, `max_spend`, `max_wall_clock`
- guards
- termination outcomes and the result seat
- the output contract itself

These are read from the pinned conclave configuration revision and are never
resolved from runtime data. Enforced at the config layer, not by asking a model
to decline.

This list is the actual security guarantee. Everything above it is
defense-in-depth that reduces the odds of a wrong assessment; this is the part
that holds even when the odds lose.

---

## 8. The prelim gate is the most exposed component, and that is fine

The gate reads raw submissions before anything else. It is the first thing an
attacker meets and the easiest thing to influence.

Two properties make that acceptable:

- **Its failure mode is permissive by design.** We already decided the gate
  should lean toward passing, because a false negative costs more than a false
  positive. So a compromised gate does what an uncompromised permissive gate
  already does — pass something through to a conclave that will assess it
  properly. The exposure sits on the component where it matters least.
- **Its output is a typed verdict**, not a prose handoff: pass or reject, plus a
  reason string that is treated as untrusted content downstream. The gate cannot
  hand instructions to the conclave because it has no channel to do so.

The gate must never be able to modify conclave configuration. It selects which
conclave receives the submission; it does not configure it.

## 9. The panel is itself a defense

Worth naming, because it is a real structural property rather than a hope.

Fooling one model is straightforward. Fooling three models from **different
providers** with the same payload, in a single pass, is materially harder.

Partial success is not silent. A seat that has been influenced diverges from its
peers, and divergence is exactly what the comparator measures. An injection that
moves one seat and not the others surfaces as measured disagreement, routes into
cross review, and then to adjudication.

Provider diversity therefore is not only a quality argument — it is an
injection-resistance argument. It is a reason to keep seats on genuinely
different models rather than the same model with different prompts.

## 10. Detection and economics

**Flag, do not block.** A cheap heuristic pass over submissions marks
instruction-shaped content — imperative reframing, role assertions,
delimiter-like sequences, unusual formatting density. The flag travels with the
content to the seats and into the audit record. It does not reject: heuristics
have false positives, and rejecting a legitimate submission is the expensive
error.

**The fee does defensive work.** Iterative injection requires resubmission, and
resubmission costs the submission fee. Combined with rate limiting per account,
this makes payload iteration expensive in a way that a free submission surface
never can be. Worth recognising that the economics were already doing security
work before anyone designed for it.

## 11. What the audit record must carry

- the nonce used for each content envelope
- which content was delivered to which seat, and in which round
- the injection heuristic flag and its score
- whether quote re-wrapping fired, and on which fields
- provenance marks on any output field carrying quoted untrusted text
- the pinned conclave configuration revision, proving no runtime reconfiguration

An injection attempt should be fully reconstructable after the fact. Assume the
first successful one will be found by someone else and reported.

---

## 12. Conformance checklist

- [ ] a conclave exposed to public submission cannot be configured as dynamic
- [ ] `instructions` and `content` are separate contract fields, never concatenated
- [ ] content envelopes use a per-run nonce, not a fixed delimiter
- [ ] seat framing lives in the seat's MD, not in assembled runtime text
- [ ] verbatim quoted content is re-wrapped at every downstream hop
- [ ] output fields carrying quoted untrusted text are provenance-marked
- [ ] no item on the capability floor resolves from runtime data
- [ ] the prelim gate emits a typed verdict and cannot select or alter configuration
- [ ] the injection heuristic flags and never blocks
- [ ] the audit record reconstructs a full injection attempt

## 13. Open

- Whether the injection heuristic is a rule set, a small classifier, or a cheap
  model call. Recommend starting with a rule set — it is auditable and free.
- Whether a flagged submission should route to a different conclave
  configuration with tighter bounds, rather than the standard one.
- Length caps per content field, to be set from real submission distributions
  rather than guessed.
