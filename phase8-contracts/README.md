# Phase 8 Artifact Contracts

This directory contains the generated JSON Schemas for the offline Phase 8
pilot artifacts. The authoritative Python models live in
`src/conclave/pilot/phase8.py`.

The contracts cover:

- immutable real/replay-provenance case packages and the locked 24-case cohort;
- two-person redaction attestations;
- the exact provider-access and pricing manifest;
- the `$0` Gate 0 evidence report and separate Gate 1 and Gate 2 approvals;
- irreversible active-batch revocation records;
- randomized blinded-rater packets and original rater submissions; and
- the final pilot result and exit-decision report.

These schemas are definitions only. Their existence does not authorize a live
runtime, load a credential, approve a batch, or permit provider access. Until a
later Gate 1 approval is created and independently validated, Phase 8 remains
offline and `CONCLAVE_REVIEWER_RUNTIME_MODE` remains `fixture`.

The schemas are generated deterministically from the Pydantic models and are
checked for drift by the test suite.

The separate cohort curation and Gate 0 workflow is documented in
`phase8-cohort/README.md`.

Validate the committed schema set with:

```text
conclave phase8-validate-contracts
```

Regenerate the schema set after an intentional model change with:

```text
conclave phase8-export-contracts
```
