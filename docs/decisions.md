# Architecture decisions

## 2026-11-27 — One historical source, local PostgreSQL, static analytical exports

Use the single selected Misata dataset. Run ETL, relational analysis, validation, and financial reconciliation in local PostgreSQL; export validated JSON for Streamlit Community Cloud. This satisfies real SQL execution while avoiding a persistent hosted database for historical synthetic data.

## 2026-11-27 — Preserve and verify the design prototype

Keep `reference UI/rcm_dashboard_indigo.html` unchanged. Recreate its navigation, KPI/chart hierarchy, operational insights, and claim investigation in Streamlit using the specified indigo colors. Prototype values are not evidence and must not enter analytical output.

## 2026-11-27 — Pin the tested Streamlit/Shadcn host pair

Use `streamlit-shadcn-ui` 1.5.0 with Streamlit 1.60.0 and Starlette 1.3.1. Its PyPI documentation identifies this as the verified host combination and reports intermittent component asset-serving errors with Starlette 1.10. A browser smoke test passed rendering and interacting with select, button, and card components; native Streamlit components remain the fallback if the full dashboard shows asset or interaction failures.

## 2026-11-27 — Explicit specialist ownership and concurrency

Use two specialists at most: data/analytics and dashboard/visualization. Shared contracts and integration stay with the orchestrator. Agent files use documented standalone TOML fields; `.codex/config.toml` caps active spawned threads at two.

## 2026-11-27 — Keep measures semantically distinct

Do not equate payer payments with total collections. Treat denied billed amount as descriptive exposure rather than confirmed loss. Make all additional revenue-cycle measures conditional on source fields and valid observation windows.

## Pending decisions

- PostgreSQL database/schema execution and connection details after the user installs/starts a local PostgreSQL service.
- Final dashboard export shape after the PostgreSQL schema, analysis views, and QA outputs are executed and reconciled.
