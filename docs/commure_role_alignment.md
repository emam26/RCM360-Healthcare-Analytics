# Project evidence for the Commure Data Operations Analyst role

This is an evidence map, not a claim that a portfolio project is equivalent to employment experience. It is based on the [Commure Data Operations Analyst (Bangladesh) posting](https://jobs.ashbyhq.com/Commure/4f984c29-f4f8-465b-a20e-b9c9e81a8e1c/) as reviewed on 2026-11-27. Project evidence remains provisional until live PostgreSQL execution, exports, and final integration review are complete.

| Posting area | RCM360 artifact or planned evidence | Current evidence limit |
| --- | --- | --- |
| QA and documentation | Source profiling, schema constraints, data-load tests, planned original-data QA rules, injected-error checks, and SOP | The schema and unit tests exist; the QA rules and SOP are not complete, and database checks have not run on PostgreSQL. |
| Process adherence | SHA-256-pinned source, byte-checked archive members, typed loader, transaction-scoped snapshot comparison, and documented rerun/mismatch behavior | Unit tests cover parser and mocked loader behavior. Live load, idempotent rerun, and rollback still require PostgreSQL. |
| SQL and discrepancy analysis | 27 documented read-only analyses across claims, denials, financial semantics, operations, and reconciliation | The query pack passed static parsing and independent source-baseline checks; its SQL has not yet executed against PostgreSQL. |
| Attention to detail and data integrity | Verified keys and relationships, exact Python Decimal baselines, source/encounter comparison queries, and reconciliation checks | These demonstrate project methods. The PostgreSQL confirmation of the financial totals remains pending. |
| Instruction creation | Business question catalog, SQL query catalog, planned data-quality SOP, and reproducible setup guidance | The business and query catalogs exist; the SOP and final setup guide are pending. |
| Clear communication | Five-page executive and operational dashboard, data contract, limitations, and planned findings report | Dashboard tests use isolated fixtures. The dashboard has not yet displayed a PostgreSQL-reconciled export or been visually reviewed with final data. |
| Cross-team collaboration | Explicit shared data contract, bounded ownership, and documented integration handoffs | These show an approach to collaboration in a project; they do not evidence work with Commure's Product, Engineering, Sales, or Account Management teams. |
| Ownership and adaptability | Incremental implementation, tests, failure-safe source loading, and visible tracking of blockers | Portfolio artifacts can demonstrate decisions and follow-through, but cannot establish prior workplace performance. |

The posting also lists a relevant bachelor's degree or equivalent experience and a 10:00 p.m.–7:00 a.m. Bangladesh Standard Time, Monday–Friday schedule. RCM360 cannot verify either requirement; represent education, work history, and schedule availability truthfully in application materials.

Do not claim quantified efficiency gains, recovered revenue, avoided losses, production healthcare experience, or real payer/provider behavior from this synthetic portfolio. Resume bullets and interview answers should use only results reproduced from the final PostgreSQL-backed analysis.
