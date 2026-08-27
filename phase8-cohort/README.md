# Phase 8 Real/Replay Cohort Workspace

This workspace is intentionally empty of case data. Real or historical replay
packages must be supplied, redacted, and reviewed by the two named human
reviewers before they are placed in a private working directory.

The committed code provides the curation and freeze boundary; it does not
invent, synthesize, or relabel fixture data as pilot evidence.

## Required input

Prepare exactly 24 `phase8-case-package/v1` JSON files:

- 20 distinct provider-eligible real-event or historical-replay cases;
- one stale control;
- one invalid-contract control;
- one exact duplicate-replay control; and
- one unapproved-provider control.

Every package must include explicit source provenance with
`synthetic_data: false`, an opaque source reference, the source snapshot hash,
and a named human verifier. The package must also include its two-person
redaction attestation. Provider-eligible packages require the baseline and
exact version pins.

Use the generated schema at
`phase8-contracts/schemas/phase8-case-package.v1.schema.json` while curating.
Keep the redaction map and any raw source material outside this repository.

## Freeze the cohort

```text
conclave phase8-freeze-cohort \
  --case-packages-dir /private/path/to/phase8-case-packages \
  --output /private/path/to/phase8-cohort-manifest.json \
  --cohort-id phase8-real-replay-001 \
  --revision 1
```

The command validates the declared request-contract status, provenance,
chronology, coverage, duplicate control, and every canonical hash. It refuses
to overwrite an existing manifest.

## Run Gate 0

After the frozen access manifest and exact review-plan revision are available:

```text
conclave phase8-gate0 \
  --cohort-manifest /private/path/to/phase8-cohort-manifest.json \
  --case-packages-dir /private/path/to/phase8-case-packages \
  --access-manifest /private/path/to/phase8-access-manifest.json \
  --plan-revision /private/path/to/phase8-review-plan-revision.json \
  --output-dir /private/path/to/phase8-gate0-evidence
```

Gate 0 produces a sealed JSON report and a human-readable evidence review. It
loads no provider credential, constructs no provider adapter, makes no
external provider attempt, and spends $0. A passing report is not a Gate 1
approval.
