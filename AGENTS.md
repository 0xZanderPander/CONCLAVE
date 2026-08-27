# Conclave — Agent Instructions

Canonical instruction file for any AI agent working in this repository
(Claude, Codex, Gemini, or otherwise). `CLAUDE.md` points here. Read this and
`GLOSSARY.md` before making changes.

## What Conclave is

A composable multi-model council harness. It makes several AI agents
deliberate, criticize, compare, and adjudicate a decision instead of accepting
one model's single answer.

The value comes from **independence and topology, not headcount**. Two agents
that can see each other's reasoning converge; two that cannot produce genuinely
independent assessments that can be compared. Blind independence is the
mechanism, not a detail.

## What Conclave is not

- not a general workflow or pipeline builder
- not an agent framework
- not a marketplace or network
- holds no credentials for any calling system
- performs no action in any external platform
- does not own the calling system's domain data, policy, decisions, or outcomes
- does not replace the caller's final human decision

## First use case

Review of marketing spend and campaign results for **Hyperstructure Marketing
OS**. Marketing OS owns campaign data, platform credentials, spend approval, and
every campaign action. Conclave receives a redacted evidence package and returns
a structured recommendation.

This path is close to test-ready and must not be broken by the composability
work. Neither project depends on the other.

## Conclave and VORAGO are separate

VORAGO is a different project that would use a Conclave council as its
idea-assessment gate. It is **one possible consumer, not Conclave's purpose or
roadmap**.

Conclave must remain independently useful and independently correct whether or
not VORAGO is built. **No consumer's requirements may be pushed down into the
Conclave kernel.** Never introduce VORAGO's economic vocabulary — tokens,
emissions, Contribution Mass, SOI, staking, financing — into this repository.

## Current state

Built and verified: Python / FastAPI / PostgreSQL modular monolith; immutable
hashed request snapshots; versioned review plans pinned per session;
provider-neutral reviewer adapters with OpenAI, Anthropic and Google Gemini all
live-verified; resumable state machine; a decision verifier that recomputes
routing from stored reviewer outputs rather than trusting recorded labels;
per-attempt cost, token and latency telemetry; a typed transport-neutral event
outbox; a feedback-to-reviewer-evaluation loop.

**Current constraint:** a fixed three-seat protocol over a single domain.
Reviewer A is routine, Reviewer B is an independent auditor joining on cadence
or trigger, Reviewer C breaks surviving disagreement. Seats, ordering and wiring
are code, not configuration.

**Panel value over a single strong model is not yet demonstrated.** Current
results prove plumbing, isolation and auditability. Panel-value metrics are
directional, not causal. Do not describe panel value as proven.

## Direction

Promote the hardcoded three-seat protocol out of the state machine into a stored
**Council configuration**. Seats, edges, activation conditions and termination
become data. Marketing then runs as one named Council configuration rather than
as the shape the engine is built around.

The **34-case deterministic fixture suite is the conformance oracle**. If the
marketing configuration reproduces all 34 cases identically through the
generalized engine, the generalization did not change marketing behavior.

Do not modify those fixtures to make a refactor pass. If a fixture must change,
that is a design finding and needs an explicit decision.

See `GLOSSARY.md` for the vocabulary mapping and for exactly where the
three-seat assumption lives.

## Hard rules

- **Phase 8 is defined, unauthorized, and disabled.** Do not enable a live
  runtime, ingest real or replay cases, or make provider calls against pilot
  material without explicit written authorization. Gate 0 runs at $0.
- **Never read, print, copy, or commit** `.env` or `credentials`. Both are
  gitignored and must stay that way.
- **No live provider calls without explicit approval**, including "just one
  test". Provider spend is gated and auditable by design.
- Raw Phase 8 source material and redaction maps live outside this repository.
  Do not ingest nearby private artifacts.
- Conclave never authenticates to Meta or any caller production system.

## Document authority

| Question | Authority |
|---|---|
| Product direction and positioning | Notion CONCLAVE page |
| Vocabulary, Notion-to-code mapping | `GLOSSARY.md` |
| Project state, risks, continuity | `PROJECT-STATUS.md` |
| Build sequencing and gates | `MVP_build_roadmap.md` |
| Implementation detail | `MVP_project_architecture.md` |

Notion: https://app.notion.com/p/CONCLAVE-3c81b84dbae2807791d1e02bac9c2964
Repo: https://github.com/0xZanderPander/CONCLAVE

When product state changes materially, update Notion first, then
`PROJECT-STATUS.md`.

## Conventions

- Python >= 3.12. Dependencies via `uv` and `uv.lock`. Hatchling build.
- `pytest` for tests; live-provider tests are gated and skipped by default.
- `ruff` for lint. **A 38-file formatting baseline predates current work — do
  not mass-reformat**, as it buries real diffs.
- `alembic` for migrations; `script_location = migrations`.
- Local SQLite mode exists for tests; PostgreSQL is the normal runtime.
- Progress is controlled by acceptance gates, not dates. Do not add timelines.
