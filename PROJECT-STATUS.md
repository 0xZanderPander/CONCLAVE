# PROJECT-STATUS.md

> **Audit state:** RELOCATED AND VERIFIED — 2026-08-20.  
> Canonical root is `/Users/az/Documents/projects/ai/CONCLAVE`. The active Phase 8 working tree, ignored credentials, Git state, and external-satellite boundary were preserved without hosted-system access.

## 1. Audit control

- Review status: COMPLETE — relocation assessment only.
- Reviewing AI: Codex.
- Review date: 2026-08-14.
- Last materially updated: 2026-08-14.
- Evidence inspected: root/nested inventory (excluding exhaustive virtual-environment packages), Git metadata/status/refs/remotes/worktrees, `.gitignore`, runtime/configuration/migrations, primary documentation, Phase 8 documentation/contracts, and nested component READMEs. No network access, credentials, databases, running services, or external accounts were accessed.

## 2. Root validation

- Is this the correct project root? YES. This is the Git top-level and contains the Python manifest, source, migrations, tests, primary README, and project documentation.
- Classification: independent active software project/repository — **Conclave**.
- Should this folder have its own `PROJECT-STATUS.md`? YES.
- Canonical root elsewhere: UNKNOWN. Local Git and documentation support this folder as canonical; copies outside this root were out of scope.
- Duplicate/competing copies: none found inside this root.
- Nested Git repositories/submodules/worktrees: none. One `.git` directory, no submodules, and one worktree only (this root).
- Evidence: `pyproject.toml` names package `conclave-review`; `src/conclave/`, `tests/`, `migrations/`, `README.md`, and Git all converge here.

## 3. Project identity and hierarchy

- Canonical project name: Conclave (`conclave-review` distribution).
- Purpose: composable, auditable decision-review kernel for structured operational recommendations. It stores immutable snapshots, coordinates independent reviewers and bounded disagreement resolution, and records auditable results plus optional outcome-linked evaluation.
- Parent project: NONE established. It is independent from Hyperstructure Marketing OS.
- Affiliations: Hyperstructure Marketing OS is only a possible future caller for optional ad-performance review. Documentation states neither project currently depends on the other; Conclave must not own Marketing credentials, Meta access, campaign actions, approvals, outcomes, or learning. The separate `phase8-meta-intake` tree is logically a restricted Conclave Phase 8 satellite, not Marketing OS, and must remain physically outside this Git repository.
- Category: active Python/FastAPI/PostgreSQL modular-monolith MVP with provider adapters and fixture/test harness.
- Lifecycle state: Phases 1–7 are documented implemented/verified (Phase 7 deterministic fixture pilot complete). Phase 8 controlled real/replay shadow-pilot foundation is in current uncommitted work but explicitly **defined, not authorized, and not enabled**. No real/replay cases, Gate 0 report, approval, runtime state, or provider calls are recorded here.
- Child components (all remain covered by this root; none is an independent repository):
  - `src/conclave/`: application modules — API, ledger, orchestration, reviewer adapters, scheduler/worker, pilot support, task packs, events, and evaluation.
  - `migrations/`: Alembic migrations for the PostgreSQL/Supabase-backed ledger.
  - `tests/`: local/unit/integration and optional live-provider gate tests.
  - `design-fixtures/` and `pilot-results/phase7/`: synthetic fixtures and Phase 7 results.
  - `hyperstructure-review-contracts/`: draft 0.3.0 future Marketing ad-review schemas, profiles, fixtures, and conformance material; expressly Conclave design/test material today, not an approved shared contract.
  - `phase8-contracts/`: untracked generated offline artifact schemas.
  - `phase8-cohort/`: untracked workflow documentation; intentionally has no case data.
  - `audit/`: documentation audit log.
- Separate status documents required: NO for current children. `hyperstructure-review-contracts/` should become an independently versioned repository/artifact only if a live shared caller contract is approved — a future owner decision, not this move. The external `phase8-meta-intake` satellite requires its own restricted status/migration review because it holds raw inventory, staging variants, private maps, and salts outside this repository.
- Owner decisions required: any future contract extraction; migration timing and preservation of the active working tree; and whether/when Phase 8 receives approved private real/replay material. Alex confirmed Conclave belongs in the standalone AI-projects category.

## 4. Current working state

- Current work in progress: substantial uncommitted Phase 8 foundation/documentation work: pilot runtime/runner/safety code, tests, artifact schemas, cohort workflow, pilot contract, and related provider/config/CLI/doc changes.
- Known incomplete work: owner-supplied reviewed/redacted real or replay cases; four controls; two-person provenance/redaction attestations; frozen plan/access/pricing/budget manifests; Gate 0; and separately authorized Gates 1/2. This is not a production authorization.
- Known blockers: no relocation blocker remains. Phase 8 remains blocked by missing approved cohort/authorization artifacts, by design. The modified/untracked Phase 8 work is still intentionally local and requires an eventual commit/push/archive decision.
- Relevant plans/handoffs: `MVP_build_roadmap.md` (next build is Phase 8 curation/freeze/Gate 0), `PHASE_8_CONTROLLED_REPLAY_PILOT.md`, `MVP_project_architecture.md`, `EVENT_STREAM.md`, `PHASE_4B_CONTRACT_PROPOSAL.md`, and `audit/CHANGELOG.md`. No handoff document was found.
- AI instructions: no `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `CODEX.md`, workspace file, or handoff/handover file exists inside this root.
- Is another AI session likely actively using this folder? No active file handle, Conclave/Uvicorn/Alembic listener, or launchd entry was observed during relocation. Saved AI/editor contexts still need reconnection to the new root.

## 5. Source control

- Is Git present? YES; repository root is `/Users/az/Documents/projects/ai/CONCLAVE`.
- Current branch: `agent/initial-conclave` at `ee3e8cef7a541766dab7549138b5bdc1ac4a028a` (`Complete Phase 7 deterministic pilot`).
- Remote: `origin` fetch/push `https://github.com/0xZanderPander/CONCLAVE.git`.
- Branch/remotes: local branch tracks `origin/agent/initial-conclave`; `origin/main` also exists. No remote branch is unmerged into current HEAD.
- Unpushed commits: none at review time (0 behind / 0 ahead of upstream); this excludes uncommitted work.
- Uncommitted tracked changes: 11 modified files — roadmap, README, audit log, CLI/config/pilot initialization, and reviewer/runtime implementation files.
- Untracked project work: Phase 8 contracts/workflow/pilot code/tests, plus this status document. Check live `git status` before relocation for the exact list; this content is relocation-critical.
- Worktrees: one only, this root.
- Submodules: none.
- Git risk after relocation: the dirty Phase 8 worktree remains intentionally unchanged and is not remote-backed. It is protected by a complete rollback checkout and verified all-refs Git bundle. Do not clean, reset, or broadly stage it without a dedicated review.

## 6. Runtime and dependencies

- Primary technologies: Python >=3.12, FastAPI, SQLAlchemy, Alembic, psycopg/PostgreSQL, Pydantic, HTTPX, JSON Schema, pytest, Ruff, uv/Hatchling; JSON schemas/fixtures, Markdown, Mermaid, and SQL migrations.
- Required runtimes: Python >=3.12; PostgreSQL for normal runtime; local SQLite mode exists for tests. Local `.venv` uses Python 3.14.
- Dependency installation method: uv lockfile and Hatchling project configuration; exact owner workflow is UNKNOWN.
- Local databases/services: default configuration targets PostgreSQL at `localhost:5432`; docs record verification against a dedicated Conclave Supabase project. Relocation validation explicitly removed database/provider environment variables and did not contact local or hosted PostgreSQL/Supabase or provider services.
- Generated files/caches: ignored `.venv/` (~100 MB before relocation), `.coverage`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`, and nested `.DS_Store`. The pre-move virtual environment was preserved separately because 17 entrypoints embedded the old root; a fresh environment was recreated from `uv.lock` at the new root with Python 3.14.6 and uv 0.11.28.
- Large media/binaries: no non-environment project files over 1 MB found; local virtual environment is the material local artifact.
- Sibling-folder dependencies: none found. No source/documentation reference to `/Users/az`, `/Users/az/Documents`, `MARKETING_INFRASTRUCTURE`, or `../` was found.

## 7. Deployment and external integrations

- Is the project deployed? A dedicated Conclave Supabase project is documented as having hosted migration/acceptance verification. Any currently live API, scheduler, worker, or production deployment is UNKNOWN.
- Deployment platform: Supabase is documented for the database; application hosting/platform is UNKNOWN. No Docker, Compose, CI workflow, Sites, Vercel, Netlify, Railway, Render, or similar deployment configuration was found.
- Configuration: `alembic.ini` and environment-driven `src/conclave/config.py`; actual deployment/secret configuration is outside the repository or UNKNOWN.
- External systems: PostgreSQL/Supabase; OpenAI Responses; Anthropic Messages; Google Gemini Interactions. Phase 8 provider use is disabled pending approval. Marketing OS/Meta/domain APIs are prohibited from current access.
- Automation: persistent scheduler/worker commands use database leases. Current processes or external schedulers are UNKNOWN; no external job configuration was found.
- Webhooks/callbacks: future transport adapters are documented; no current external webhook configuration found.
- Does anything depend on the former local path? No tracked/untracked source or documentation dependency was found. No Phase 8 external path variable was configured in the relocation process environment. The only confirmed old-root dependencies were generated virtual-environment entrypoints, which were rebuilt and now reference the new root.

## 8. Paths and relocation risks

- Hard-coded absolute paths: none found in active project source/configuration. The former-root reference remains only as historical relocation context in this document.
- Scripts referencing sibling folders: none found.
- IDE/workspace files: none found.
- Sync software involvement: UNKNOWN.
- Aliases/shortcuts/symlinks: no project-content symlinks; only Python launcher symlinks inside ignored `.venv/`.
- Application libraries referencing this folder: UNKNOWN outside the repository.
- Other path-sensitive findings:
  - Alembic `script_location = migrations` and CLI default output paths are relative to the project root.
  - Phase 8 accepts environment paths for private manifests, case packages, runtime state, revocations, and external provider secrets. None was set in the relocation process environment; no external material was ingested.
  - Raw Phase 8 source material/redaction maps are intentionally outside this repository. Do not sweep nearby private artifacts into this project during centralization.

## 9. Sensitive material

- Environment files: ignored `.env` (603 bytes), with names for OpenAI, Anthropic, Google, reviewer-runtime, and test-database configuration. Values were not read or recorded.
- Credential/key locations: ignored `credentials` (83 bytes; four non-empty lines; content not inspected), plus `.env`. Phase 8 design expects external secret paths; locations are UNKNOWN.
- Private/client/legal material: no committed real/replay cohort data. Future source material, redaction maps, approvals, and provider secrets need special handling and are intended to stay outside the repository.
- Special handling: `.env` and `credentials` were preserved byte-for-byte without reading or recording values; both remain mode `0644`, which is an existing local-permission concern for later owner-approved hardening. The complete rollback copy is secret-bearing and must not be treated as a general review bundle. Actual external Phase 8 artifacts/secrets remain outside this repository.
- Secret values: deliberately not recorded.

## 10. Reorganization assessment

- Recommended parent destination: `/Users/az/Documents/projects/ai/CONCLAVE` as a standalone AI harness, confirmed by Alex; do not place it under Marketing OS or Hyperstructure.
- Recommended folder name: `CONCLAVE` (existing repository/GitHub naming).
- Relocation preservation completed:
  1. Preserved all 11 modified files, every untracked Phase 8 artifact/status path, the synchronized tracked branch, all refs/objects, and ignored local state in a checksum-matched rollback checkout; also created and verified an all-refs Git bundle.
  2. Preserved `.env` and `credentials` byte-for-byte without reading values; recorded their existing modes and hashes for move verification.
  3. Preserved the old virtual environment separately and rebuilt the active environment from `uv.lock`, eliminating all old-root entrypoints.
  4. Confirmed no active file handles/listeners/launchd job and no configured external Phase 8 path; kept `phase8-meta-intake` physically outside this repository.
- Validation completed: repository root/`.git` identities preserved; branch `agent/initial-conclave` remains `ee3e8ce`, 0/0 against its locally observed upstream, with the same dirty/untracked inventory and 22 existing dangling objects. Under explicitly offline/test settings, 153 tests passed and 11 live/PostgreSQL tests skipped; Ruff lint passed; Alembic reported head `20260728_0011`; 4 request fixtures, 4 results, 1 feedback record, 5 comparator cases, and 10 offline Phase 8 schemas validated; CLI help loaded. Ruff format still reports the same pre-existing 38-file formatting baseline; no formatting edit was made.
- Rollback: complete checkout at `/Users/az/Documents/project-reorganization-backups/2026-08-20/CONCLAVE-original`; verified Git bundle at `/Users/az/Documents/project-reorganization-backups/2026-08-20/CONCLAVE-all-refs.bundle`; pre-move environment at `/Users/az/Documents/project-reorganization-backups/2026-08-20/CONCLAVE-pre-move-venv`; former root contains only `MOVED.md`.
- Recommendation: **`RELOCATED AND VERIFIED`.** Commit/push/archive decisions, credential-permission hardening, Phase 8 authorization, and formatting cleanup remain separate maintenance tasks.

## 11. Questions and disagreements

- Unanswered questions: live API/scheduler/worker/Supabase/launch-agent/IDE/sync references; current Phase 8 external artifacts and secrets; future shared-contract extraction; and whether another session is modifying the worktree. The central AI category/destination is resolved.
- Assumptions that appear incorrect: treating Conclave as a Marketing OS subproject contradicts its documentation. Treating the draft Hyperstructure contracts as already approved/shared also contradicts it.
- Reasons to reject/modify hierarchy: keep Conclave independent from Marketing OS. Treat Phase 8 Meta Intake as a logical Conclave satellite, but do not relocate its private source/redaction artifacts into this repository. Do not split nested contract/cohort directories during this move; they are active Conclave work.
- Decisions Alex must make: dirty-worktree preservation; secret handling; confirmation of external path dependencies; and any future contract extraction.

## Cross-review

- Cross-review status: COMPLETED — central evidence spot-check passed with relocation blockers.
- Cross-reviewer: Codex
- Cross-review date: 2026-08-14
- Corrections required: No material correction to the report. External deployment/process/path context and the listed owner decisions remain unresolved. Branch, remote, dirty state, and sensitive-file presence were independently confirmed.
- Final migration decision: **MOVED AND VERIFIED** at `/Users/az/Documents/projects/ai/CONCLAVE`.

## Continuing maintenance

Read this document at the beginning of future work sessions. Update it only when the project's material state, risks, dependencies, deployment, ownership, or migration status changes—not after every response.

## Change log

- 2026-08-20 — Codex relocation: refreshed the dirty-tree, secret, runtime, process, and external-path audit; created a checksum-matched 108 MB rollback checkout and verified all-refs bundle; moved the original repository while preserving root/`.git` identities; preserved every tracked/untracked Phase 8 item and ignored credential file; moved the old generated environment into protected rollback storage and rebuilt it from `uv.lock`; passed 153 offline tests, Ruff lint, Alembic-head inspection, fixture/schema validation, and CLI loading at the destination; retained the existing 38-file formatting baseline; confirmed the restricted Meta Intake satellite stayed external; and installed the old-path pointer. No commit, fetch, push, hosted Supabase/PostgreSQL/provider call, Phase 8 execution, credential read, deployment, or implementation edit occurred.

- 2026-08-20 — Alex classified Conclave as a standalone AI project. Proposed destination `/Users/az/Documents/projects/ai/CONCLAVE` recorded; relocation remains blocked by the existing maintenance findings.
- 2026-08-20 — Recorded `phase8-meta-intake` as a restricted external Conclave Phase 8 satellite. It remains a separate physical root and must not be ingested into the Conclave Git repository during reorganization.
- 2026-08-14 — Completed first read-only relocation review. Recorded root validation, component hierarchy, Git state, sensitive-material locations, runtime/integration evidence, path findings, and blockers. No project files were modified other than this document.
