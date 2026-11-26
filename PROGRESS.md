# RCM360 progress

Updated: 2026-11-27

## Current phase

Phase 1 — source/schema verification completed; Phase 2 ETL and EDA preparation is beginning. PostgreSQL execution remains blocked on local installation/service setup.

## Completed

- Confirmed the workspace initially contained only `reference UI/rcm_dashboard_indigo.html` (preserved).
- Downloaded and retained the original CC0 archive locally, plus seven byte-identical CSVs. Verified 39,946 rows, 73 columns, seven unique primary keys, 82,311 valid foreign-key references, and no orphans. Full verified profile: `docs/dataset_profile.md`.
- Independently checked exact claim status and finance totals with Python `Decimal`; verified 4,737 claims (4,122 paid, 426 denied, 189 pending), 18,033,949.84 billed, 9,172,905.62 allowed, 7,938,924.10 recorded payer payments, and 7,779,126.53 patient responsibility assigned. PostgreSQL reproduction is still required.
- Verified the reference HTML’s five pages, styling, responsive breakpoints, interactions, and fictional labels in `docs/ui_reference_analysis.md`; source SHA-256 remained unchanged.
- Detected Codex CLI 0.171.0. Official Codex documentation describes project agents as `.codex/agents/*.toml` and the concurrency setting as `[agents].max_concurrent_threads_per_session`.
- Created the repository teamwork skill, project instructions, roadmap, data contract, decision log, agent files, project-scoped Codex config, dependency pins, and Streamlit theme. The skill validator and TOML syntax checks pass.
- Initialized Git, set `origin` to `https://github.com/emam26/RCM360-Healthcare-Analytics.git`, and confirmed GitHub shows the repository empty. Git Credential Manager is configured; GitHub CLI is unavailable. No commits have been created yet.
- Installed the pinned Python 3.11 development dependencies in `.venv`. `pip check` passes. Browser smoke test verified Shadcn select, button, and card rendering and interactions with Streamlit 1.60.0 / Starlette 1.3.1 / Shadcn UI 1.5.0.

## In progress / next

- Commit the verified project bootstrap and source/reference documentation as separate logical commits, then push to origin if authentication succeeds.
- Build reproducible ETL, PostgreSQL schema/load, advanced SQL, QA, and JSON exports against the verified contract.
- Implement the five-page dashboard after the exported JSON schema is settled.
- Obtain PostgreSQL installation/service setup through the user's local system, then execute and reconcile all SQL before declaring analytics complete.

## Blockers

- No `psql`, `postgres`, `pg_ctl`, or `pg_isready` command is installed. Actual PostgreSQL execution cannot be verified until PostgreSQL is installed and a local service/database is available.
- GitHub authentication is not yet tested; push will be attempted after the first verified local commit.

## Evidence discipline

No PostgreSQL query, finished dashboard, full test suite, or deployment has been verified yet. Do not cite the HTML prototype's demonstration numbers as project findings. Deployment has not been requested and must not be performed.
