# Hyperstructure Review Contracts

## Status

Draft `0.2.0` future integration design for optional ad-performance review.

This package belongs to Conclave's current design and test work. Conclave uses
it with sample data and fixtures. Marketing OS does not depend on it and does
not need to implement, import, approve, or pin it during Marketing OS
development.

If an optional Marketing connection is approved later, after Marketing OS is
already operating with reliable campaign results, this package can be reviewed
as a starting point. It must not be treated as an already approved shared
contract.

Before any live connection, the future caller and Conclave would approve a
version, place it in an independently versioned repository or artifact, and
test both sides against the same fixtures.

## Why this exists

Conclave needs stable request, result, and feedback shapes for its own tests.
The draft uses `review-request/v1`, `review-result/v1`, and
`review-feedback/v1`.

The package provides executable examples:

- **Schemas** define the shape.
- **Fixtures** are concrete, valid example payloads — one per scenario both
  systems must handle.
- **Conformance** describes current Conclave checks and possible future
  two-sided checks.

## Layout

```text
hyperstructure-review-contracts/
├── README.md
├── VERSION                       # semver of the contract set as a whole
├── schemas/
│   ├── review-request.v1.schema.json
│   ├── review-result.v1.schema.json
│   └── review-feedback.v1.schema.json
├── profiles/
│   └── marketing-ads.v1.json    # weights, tolerance, triggers, merge rule
├── fixtures/
│   ├── request/                  # caller -> Conclave
│   ├── result/                   # Conclave -> caller
│   ├── feedback/                 # caller -> Conclave (opaque refs)
│   └── comparator/               # golden distance and hard-trigger cases
└── conformance/
    └── conformance.md
```

## The one rule

A payload is valid only if it validates against the schema **and** matches the
field classification (evidence / context / policy / goal / quality) declared in
the request. Conclave must be able to store, hash, and reason over any fixture
here **without ever needing a Meta credential, a Marketing production query, or
raw personal content.** Any fixture that would require those is a contract bug,
not a Conclave feature request.

## Using this package now

- **Conclave** uses the schemas and fixtures as local golden tests.
- Conclave registers `marketing-ads/v1` as its first local task pack and
  requires submitted comparator and action-ontology references to match it.
- **Marketing OS has no current work or dependency here.**

If a future connection is approved, both sides may then pin the same reviewed
version and run a two-sided conformance suite.

Provider and model names in fixtures are illustrative audit values, not approved
reviewer assignments.

Review-plan cadence and activation state are always Conclave configuration. A
future caller may name an approved plan and revision in a request; Conclave
still owns audited plan revisions and session scheduling.

## Versioning

- `VERSION` is the semver of the whole contract set.
- Individual contracts carry their own major in the filename (`.v1.`).
- `0.x` versions are explicitly pre-release: every semantic or fixture change
  still bumps `VERSION` and is audited.
- Additive, backward-compatible fields → minor bump.
- Any required-field or semantic change → new major (`.v2.`), both files kept,
  migration noted in `conformance/conformance.md`, once `1.0.0` has shipped.
- Fixtures become immutable at `1.0.0`; a new scenario then gets a new fixture
  file.
