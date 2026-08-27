# Phase 7 Fixture Pilot Review

**Assessment:** ready to share for the deterministic fixture MVP, with the
synthetic-evidence caveats below.

**As of:** 2026-07-28
**Dataset:** `design-fixtures/phase7-pilot-cases.json`
**Machine-readable results:** `pilot-results/phase7/phase7-pilot-results.json`

## Decision

The local polling MVP passes the Phase 7 fixture gate. Its automatic routing,
terminal failure behavior, retries, controlled cross-review recovery, feedback
linkage, directional evaluation, and audit reconstruction behaved as designed
across 34 deterministic cases. No reliability, audit, or contract blocker
remains from this pilot.

This result supports freezing the deterministic fixture MVP. It does not support
permanent provider assignment or causal claims about panel quality.

## Scope and methodology

- 34 synthetic cases; 31 completed through feedback and evaluation.
- Five materially eligible inputs and 11 material recommendations.
- Six A-only, 12 A/B agreement, seven cross-review-resolved, and six
  reviewer-C tie-break routes.
- Healthy, partial, stale, tracking-unhealthy, failed-goal, disagreement,
  malformed-output, timeout, idempotency, and recovery cases.
- Assessment-v2 claims, cross-review-v1 responses, and reviewer-C-judgment-v2.
- Synthetic telemetry only; no external provider, Marketing OS, or Meta call.

Every completed case used one immutable snapshot, preserved its evidence
version, accepted caller feedback, produced one directional evaluation
candidate, and passed full audit reconstruction. The three intentional terminal
cases passed a separate contiguous-event reconstruction check.

## Results

| Measure | Result |
|---|---:|
| Expected outcomes passed | 34 / 34 |
| Completed and evaluated results | 31 |
| Intentional terminal-safety cases | 3 |
| Full completed-ledger audit checks | 31 / 31 |
| Terminal-ledger audit checks | 3 / 3 |
| Independent-context isolation checks | 34 / 34 |
| Snapshot-consistency checks | 34 / 34 |
| Evidence-traceability checks | 31 / 31 |
| Recommendation-clarity checks | 31 / 31 |
| Idempotency replay checks | 3 / 3 |
| Controlled recovery cases | 1 / 1 |
| Auto-resolved results | 12 |
| Caller-decision-required results | 19 |

## Routing, latency, and synthetic cost

| Route | Cases | Share | Average latency | Average synthetic cost |
|---|---:|---:|---:|---:|
| A only | 6 | 19.4% | 135 ms | $0.00020640 |
| A/B agreement | 12 | 38.7% | 272.5 ms | $0.00041520 |
| Cross review resolved | 7 | 22.6% | 663.6 ms | $0.00084600 |
| Reviewer C tie-break | 6 | 19.4% | 985 ms | $0.00127440 |

Overall completed-result latency was 472.1 ms on average, 265 ms at p50, and
985 ms at p95. Total synthetic cost was $0.02020440. These values validate
aggregation and route scaling; they are not estimates of real provider
performance or spend.

## Directional evaluation

| Indicator | Result |
|---|---:|
| Evaluation candidates | 31 |
| Panel-change rate | 80.6% |
| Caller preferred panel, comparable cases | 56.0% |
| Average additional issue count | 0.26 |
| Cross-review resolution rate | 53.8% |
| Reviewer-C invocation rate | 19.4% |
| Caller override rate | 25.8% |

These rates reflect the authored pilot mix and synthetic feedback profiles.
They verify definitions, denominators, persistence, and aggregation only. They
do not estimate causal panel value or provider quality.

## Manual recommendation review

All 31 completed recommendations were reviewed by route and recommendation
archetype.

- Observation results clearly state why no immediate change is supported.
- Evidence-collection results state the missing decision condition and the next
  measurement window.
- Tracking results separate data repair from performance interpretation and
  name the submitted conversion target.
- Operational changes name the bounded target, preserve caller approval, and
  do not imply execution.
- Experiments isolate one change, state the success metric, define minimum
  evidence, cap exposure, and include stop conditions.
- Cross-review and reviewer-C results clearly identify the decisive stage.

Independent A, B, and blind-C calls contained no prior claims, peer
assessments, cross-review responses, or comparison history. Every joined
reviewer used the same snapshot hash. Agreement cases can intentionally produce
the same recommendation; isolation is established by call context and separate
claim IDs, not by manufacturing textual disagreement.

## Issues found and fixed

1. The first harness run reused scheduled occurrence timestamps, and the
   occurrence ledger correctly rejected the collision. The pilot now assigns
   each case a unique due time while preserving evidence-age semantics.
2. Compatible A/B results concatenated identical summaries. The comparison
   merge now deduplicates exact summaries while preserving both reviewers'
   claims, invocations, and audit history.
3. The completed-session audit verifier intentionally requires a result, so
   stale and failed sessions were initially outside the pilot audit total. The
   runner now reconstructs those terminal event streams separately.

## Caveats

- The case mix and feedback are synthetic and intentionally exercise branches;
  route and preference rates are not production prevalence estimates.
- Latency, token, and cost values are deterministic test telemetry.
- Calibration is not claimed because the pilot has no observed
  counterfactuals.
- Provider compatibility evidence remains separate from outcome-linked
  provider-quality evidence. No permanent reviewer slot should be assigned from
  this pilot alone.
