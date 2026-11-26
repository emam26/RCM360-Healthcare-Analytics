# PostgreSQL analysis pack

Run these 27 read-only queries after the approved snapshot and claim analytics view are loaded into the rcm360 schema. Each query states its cohort, denominator, and interpretation limit. The results describe the Misata synthetic dataset and depend on the snapshot's available fields. See the [business questions](../../docs/business_questions.md) and [data contract](../../docs/data_contract.md).

From the project root, with the loader already run and DATABASE_URL set, execute the pack in PowerShell.

~~~powershell
Get-ChildItem -LiteralPath sql/queries -Filter '*.sql' |
    Sort-Object Name |
    ForEach-Object {
        psql -X -v ON_ERROR_STOP=1 --dbname $env:DATABASE_URL --file $_.FullName
        if ($LASTEXITCODE -ne 0) {
            throw "Query pack failed in $($_.Name)"
        }
    }
~~~

The catalog maps each query to its output grain. Counts always refer to the cohort shown in that query. Ratios use exact numeric division and display as percentages. The ordered-set aggregates select an observed value for each discrete percentile.

| Query | Analysis | Output grain |
| --- | --- | --- |
| [Q01](01_claim_flow.sql) | Submitted volume | Month, payer, encounter type |
| Q02 | Observed status mix and denial rate | Submission month |
| Q03 | Overall observed denial rate | Snapshot |
| Q04 | Payer denial rate and share of denied claims | Payer |
| Q05 | Provider observed rate and encounter-mix benchmark | Provider |
| Q06 | Counts of pending claims | Month and payer |
| [Q07](02_denials.sql) | Denial reason frequency | Denial reason |
| Q08 | Reason incidence and share within denied subset | Payer, encounter type, reason |
| Q09 | Billed amount attached to denied claims | Month, payer, reason |
| Q10 | Independent count and billed Pareto rankings | Denial reason |
| [Q11](03_financial_analysis.sql) | Billed, allowed, recorded payer payment, and assigned responsibility | Payer and status |
| Q12 | Billed-minus-allowed difference | Payer and encounter type |
| Q13 | Recorded payer payment as share of billed and allowed | Payer and overall |
| Q14 | Stored allowed ratio and amount tolerance | Status |
| Q15 | Billed, allowed, and recorded payment ordering | Status |
| Q16 | Assigned responsibility versus billed-minus-allowed | Status |
| Q17 | Observed paid claim submission-to-payment distribution | Payer and encounter type |
| Q18 | Recorded payments on self-pay claims | Status within self-pay |
| [Q19](04_operational_context.sql) | Recorded claim events before discharge | Encounter type |
| Q20 | Denial rate by documented diagnosis category | Category and encounter type, with overlapping categories |
| Q21 | Denial rate by diagnosis occurrence count | Count bucket and encounter type |
| Q22 | Volume and billed amount by linked lab/prescription presence | Encounter type and presence pair |
| Q23 | Shares of claim volume and billed amount | Encounter type |
| Q24 | Admission-to-submission distribution | Encounter type |
| [Q25](05_reconciliation.sql) | Agreement of claim and encounter fields | Snapshot |
| Q26 | Exact counts and financial amounts across base claims and view | Reconciliation metric |
| Q27 | Child counts and encounter claim coverage | Parent-count check |

Review Q26 before relying on the claim view for totals. The expected values come from the independent [source profile](../../docs/dataset_profile.md). Each matches_snapshot value should be true after an approved load. Q25 and Q27 report complementary mismatch counts. These checks cover the typed snapshot. The project's original-data audit and injected tests are separate.

The pack passed PostgreSQL grammar parsing and local source checks. Live PostgreSQL execution is pending, so this catalog contains no database results.
