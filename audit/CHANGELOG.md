# Conclave Documentation Audit Log

A historical record of substantive changes to the Conclave design documents,
design fixtures, and draft integration contracts. One entry per revision.
Newest first.

Each entry records what changed, when, who requested and applied it, and why.
Add a new entry whenever the design contract changes; do not edit past entries.

| Date | Rev | Requested by | Applied by | Summary |
|---|---|---|---|---|
| 2026-07-24 | r5 | Al | Codex | Removed Marketing MVP coupling; made fixture-based Conclave development current and the first Marketing deployment a later optional ad-performance review connection |
| 2026-07-24 | r4 | Al | Codex | Made review timing deployment-editable through immutable plan revisions; defined A/B expansion and two-stage C judging; added Marketing-v1 weights, hard triggers, contract `0.2.0`, and executable design fixtures |
| 2026-07-24 | r3 | Al | Codex | Separated Marketing domain ownership from the Conclave kernel; replaced direct Meta, Telegram, policy, outcome, and learning ownership with versioned request/result/feedback contracts |
| 2026-07-24 | r2 | Al | Conclave assistant (Cowork session) | Three-reviewer panel, cadence-based ping-pong, tolerance-triggered cross review, tie-breaker, baseline, configurable adjudicator, Hermes learning seam, domain contract, testable Phase 0 gate |
| 2026-07-14 | r1 | Al | Al | Initial Marketing-first, read-only MVP design (baseline of these docs) |

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
