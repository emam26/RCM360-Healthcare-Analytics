# RCM360 progress

Updated: 2026-11-27

## Current phase

Phases 3 and 7 implementation are in integration review: the initial PostgreSQL schema, loader and view, and the five-page dashboard are implemented. Actual PostgreSQL execution and export reconciliation remain blocked on local PostgreSQL installation/service setup.

## Completed

- Preserved the supplied `reference UI/rcm_dashboard_indigo.html` unchanged.
- Downloaded the original CC0 Misata archive and retained its seven extracted CSVs locally. The source SHA-256 is pinned in the loader; raw files are excluded from Git.
- Verified 39,946 rows across seven tables and 73 columns, unique primary keys, 82,311 valid foreign-key references, and no orphans. The full profile is in `docs/dataset_profile.md`.
- Independently verified with Python Decimal: 4,737 claims (4,122 paid, 426 denied, 189 pending); billed 18,033,949.84; allowed 9,172,905.62; recorded payer payments 7,938,924.10; patient responsibility assigned 7,779,126.53. PostgreSQL reproduction is still required.
- Documented 24 supported business questions and interpretation guardrails in `docs/business_questions.md`.
- Preserved and profiled the five-page HTML reference in `docs/ui_reference_analysis.md`; its SHA-256 remained unchanged during implementation.
- Created the repository teamwork skill, `AGENTS.md`, roadmap, contracts, decisions, specialist configuration, and project-scoped Codex configuration. The Git workflow is documented in both `AGENTS.md` and the teamwork skill; only the orchestrator performs Git operations.
- Connected `main` to the user-authorized GitHub repository. Git Credential Manager authentication and pushes succeeded. The five current commits are pushed to `origin/main`.
- Installed the pinned Python 3.11 development dependencies in `.venv`; `pip check` passes. Browser smoke testing confirmed Streamlit Shadcn select, button, and card rendering and interaction with the pinned Streamlit 1.60.0 / Starlette 1.3.1 / Shadcn UI 1.5.0 combination.
- Implemented seven PostgreSQL source tables, keys, constraints, indexes, an ER diagram, a claim-grain analytics view, and an archive-verifying loader. The nine scoped data unit tests pass. SQL was statically parsed; no PostgreSQL server was contacted.
- Implemented the five-page JSON-backed Streamlit dashboard, indigo theme, filters, claim detail and export interactions, and separate original/injected QA views. Ten dashboard tests pass; compile checks passed; local `/` and `/_stcore/health` requests returned HTTP 200. Tests used isolated fixtures because final JSON exports do not yet exist.

## In progress / next

- Review and integrate the PostgreSQL and dashboard implementations; run the dashboard against real, PostgreSQL-reconciled JSON exports.
- Build the advanced SQL analysis pack, data quality rules, deterministic injected-error tests, and PostgreSQL-to-JSON export pipeline.
- Obtain local PostgreSQL installation/service setup, then execute the schema and loader, reconcile SQL totals, and verify exports against PostgreSQL.
- Complete the EDA, findings, SOP, recruiter-facing documentation, and deployment preparation after analytical outputs are verified.

## Blockers

- No `psql`, `postgres`, `pg_ctl`, or `pg_isready` command is installed. Actual PostgreSQL execution cannot be verified until PostgreSQL is installed and a local service/database is available.

## Evidence discipline

The Python baseline is not a substitute for the required PostgreSQL reconciliation. No final JSON export, SQL finding, complete integration test run, or deployment has been verified. Do not use fictional HTML prototype values as findings. Deployment has not been requested and must not be performed.
