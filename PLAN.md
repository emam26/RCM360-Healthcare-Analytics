# RCM360 roadmap

## Goal

Build a reproducible healthcare revenue-cycle analytics portfolio from the single synthetic Misata dataset, using Python, executed PostgreSQL, validated JSON exports, and an interactive Streamlit/Plotly dashboard styled from the preserved indigo HTML reference.

## Phases and acceptance criteria

0. **Initialize** — project instructions, teamwork workflow, specialist definitions, tool inventory, and reference UI inventory.
1. **Dataset and business contract** — preserve/download source; verify license, table grains, keys, columns, types, missingness, date ranges, and financial semantics; document data dictionary, KPI definitions, limitations, and at least 20 business questions.
2. **ETL and EDA** — reproducible transformations, raw-data preservation, cross-table profiling, justified cleaning, notebook visualizations, and transformation log.
3. **PostgreSQL** — reproducible schema/load, keys and constraints, useful views/indexes, ER diagram, and queries executed against the actual loaded data.
4. **Analysis** — at least 25 distinct, useful SQL analyses with verified findings, methods, implications, recommendations, and limitations; no grain errors.
5. **Data quality** — at least 15 schema-supported rules, quantified denominators, structured audit output, and separately labeled injected-error test data with known expected detections.
6. **Exports** — deterministic, versioned JSON with provenance and sufficient claim-level detail; privacy-minimized; totals reconciled back to PostgreSQL.
7. **Dashboard** — five functional analytical pages, responsive indigo UI, evidence-backed metrics, global filters, drill-down, claim investigation, CSV downloads, and useful empty/error states.
8. **Integration** — targeted and comprehensive tests, independent SQL/Python comparisons, dependency compatibility, and visual review against the HTML reference.
9. **Documentation** — recruiter-facing README, architecture/ER diagrams, data dictionary, KPI and SQL docs, findings, reconciliation, QA/SOP, limitations, reproducible setup, and Commure role mapping.
10. **Deployment preparation** — portable Streamlit Community Cloud setup, public-safe exports, and precise publishing instructions. Mark deployment complete only after it is online and verified.
11. **Career materials** — verified resume bullets, repository description, two-minute explanation/demo, and interview Q&A based on actual project results.

## Final acceptance

The Definition of Done in the user brief is authoritative. Report every incomplete or unverified item explicitly; do not treat deployment or manual environment setup as complete without direct evidence.
