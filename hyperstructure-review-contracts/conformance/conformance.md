# Conformance

How Conclave validates the draft contract against sample fixtures now, and how
a future optional caller could validate it later.

This document creates no Marketing OS requirement. Marketing OS may be built and
operated without Conclave. Two-sided conformance applies only if an optional
future connection is separately approved.

The current contract-set version is `0.3.0`. It is a pre-release contract:
fixtures may be corrected during Phase 0, but every correction must bump
`VERSION` and be recorded in the Conclave documentation audit log. Once the
contract reaches `1.0.0`, shipped fixtures are immutable.

## Validation rules

Conclave proves these rules now. A future caller would prove the same rules
before a live connection:

1. every JSON document parses and every request, result, and feedback fixture
   validates against its named schema;
2. each request's `review_trigger.occurrence_id`, plan reference, and plan
   revision identify one deduplicated review occurrence;
3. every field or subtree under `sections` and `quality` is covered by exactly
   one classification path, except where a more-specific path explicitly
   overrides a parent path;
4. classification paths exist in the payload and cannot classify request
   control fields such as caller identity, the trigger, plan, task pack, or
   comparator;
5. comparator dimension names are unique, match the pinned profile, and their
   weights total exactly `1.0`;
6. recommendation categories occur in the request's
   `allowed_recommendations`, and proposed action types occur in the request's
   `action_ontology.allowed_action_types`;
7. `optimization_eligible=false` forbids spend, publish, audience, creative, or
   other optimization changes;
8. `recommendation.category=experiment` carries the complete embedded
   experiment structure; and
9. a `tie_broken` result includes C's independent invocation before its judging
   invocation, a non-null tie-break record, and
   `status=caller_decision_required`;
10. every automatic result identifies the immutable task-pack content hash,
    includes each decisive comparison round, and states its resolution basis;
    and
11. reviewer C's judgment explicitly selects A or B, or supplies a separately
    valid assessment for synthesis, insufficient evidence, or escalation.

## Current Conclave checks

Conclave must accept, reject, hash, compare, and return the sample fixtures
without contacting Marketing OS or any production system.

1. **Accepts and hashes every request fixture** without fetching or enriching
   it. Same file in → same snapshot hash out.
2. **Rejects out-of-bounds input.** A request carrying a credential, raw
   personal content, or an unclassified field is refused at intake, not
   reviewed.
3. **Emits valid results.** Every result it returns validates against
   `schemas/review-result.v1.schema.json`, uses only categories present in the
   originating request's `allowed_recommendations`, and keeps `confidence`
   separate from `evidence_quality`.
4. **Never carries authority.** No result instructs a platform write, an
   approval, or anything that bypasses caller policy.
5. **Honors reviewer-C ordering.** C never sees A/B content before storing its
   own assessment; its judging invocation may then compare C's assessment with
   A/B's final claims and justifications.
6. **Pins task-pack meaning.** Every new automatic review stores the content
   hash of the exact task-pack document used for eligibility, materiality,
   comparison, and result validation.
7. **Reconstructs the route.** Audit validation recomputes comparison rounds,
   expansion eligibility, C selection, and the published recommendation from
   stored inputs rather than trusting route labels.

## Future caller checks

The following section is dormant. It applies only if a future Marketing OS
ad-performance adapter, or another caller, is approved.

### Optional caller

1. **Produces valid requests.** Its adapter, given an eligible subject,
   emits a `review-request/v1` payload that validates against
   `schemas/review-request.v1.schema.json`.
2. **Round-trips every request fixture.** It can serialize/deserialize each file
   in `fixtures/request/` without loss and without adding fields outside the
   declared `classification` buckets.
3. **Consumes every result fixture.** Given each file in `fixtures/result/`, its
   policy engine reaches the correct terminal state — e.g.
   `03-tracking-problem` must be blocked from any spend/publish action *even
   though reviewers agree*, because `optimization_eligible` was false on the
   matching request.
4. **Honors the boundary.** No request fixture it produces contains a Meta
   credential, a raw Memory Machine message/recording/submission, or any field
   requiring a live Marketing query to interpret.

## Scenario matrix

Each request fixture pairs with the result the panel should produce. Conclave
tests every pair now. A future caller may reuse the pairs later.

| Request fixture              | Expected result category      | Key invariant exercised                                    |
|------------------------------|-------------------------------|------------------------------------------------------------|
| `01-normal-healthy`          | `operational_change`          | Material result returns `caller_decision_required`         |
| `02-weak-evidence`           | `collect_more_data`           | Thin data auto-resolves; no spend change proposed          |
| `03-tracking-unhealthy`      | `tracking_or_data_problem`    | `optimization_eligible=false` blocks optimization even on reviewer agreement |
| `04-surviving-reviewer-conflict` | `operational_change`     | One frozen cross-review round survives; C assesses blindly, then selects A; caller retains authority |

Add new rows as fixtures are added. During the `0.x` draft period, every fixture
edit requires a version bump and audit entry. After `1.0.0`, never edit a shipped
fixture in place: add a new file and row.

## Comparator vectors

`fixtures/comparator/marketing-v1-cases.json` and
`fixtures/comparator/marketing-v1-assessment-pairs.json` are the golden suites
for `profiles/marketing-ads.v1.json`.

- With no hard trigger, expected distance is the sum of
  `dimension_distance * dimension_weight`.
- Distance greater than tolerance triggers cross review.
- Any registered hard trigger forces cross review and reports normalized
  distance `1.0`, regardless of the weighted sum.
- A within-tolerance merge may only occur when recommendation disposition,
  action direction, and target scope match.
- Assessment-pair cases exercise all weighted dimensions, hard triggers,
  merge incompatibility, and conservative timing with complete valid reviewer
  outputs.

## Conclave-only design fixtures

Review-plan cadence is not a Marketing wire contract. Conclave separately tests:

- `design-fixtures/review-plan-revision.json` — future-effective cadence edits,
  open-session pinning, rollback-by-revision, and off-cadence B behavior;
- `design-fixtures/fake-state-traces.json` — A-only, A/B, cross-review, C,
  result, and feedback state paths without production access.

## Suggested future mechanics

- Conclave keeps a validator in its own test suite now.
- If a future connection is approved, each project keeps a validator and runs it
  in CI against the same reviewed package.
- Pin by git submodule or a copied directory stamped with the `VERSION` string;
  CI fails if the local stamp and the submodule `VERSION` diverge.
- The `request_snapshot_hash` in result fixtures is a `PLACEHOLDER_matches_request_NN`
  marker. Conformance replaces it with the real hash Conclave computes for the
  paired request and asserts both repos agree on that hash.

## Changing the contract

1. During independent Conclave development, propose the change here and test it
   against sample fixtures.
2. While `VERSION` is `0.x`, bump the contract-set version and audit every
   semantic or fixture change.
3. After `1.0.0`, additive/backward-compatible changes bump the minor version
   and keep `.v1.` schemas.
4. After `1.0.0`, breaking changes add `.v2.` schemas beside `.v1.` and keep
   both.
5. If a future caller connection exists, both projects move their pin only
   through a deliberate integration change.
