# Data and dashboard contract

Status (2026-11-27): **CSV schema and generated dashboard export contract verified; database execution is reported by export metadata but was not independently reconnected during this review.** All exported claim rows and exact numeric values match the pinned CSV source. The claims and quality exports share the pinned source hash and pass their parsers. Direct SQL execution evidence for the 28-query pack is not stored in this repository.

## Source and privacy

- Sole source: Misata Studio, “Hospital encounters, diagnoses and claims” (publisher page: <https://www.misata.studio/datasets/hospital-encounters-claims>).
- Preserve the downloaded source archive and extracted CSVs as immutable raw inputs. Record retrieval date, source URL, license text, archive hash, and actual row counts.
- Keep exports limited to operational and claim analysis. Omit patient names, addresses, and patient identifiers unless the verified contract proves a nonidentifying key is necessary for joins; never export direct identifiers to the public dashboard.

## Verified source grains and keys

The archive contains 39,946 rows and 73 columns across seven tables. Each source primary key is non-null and unique. All 82,311 references across 11 foreign keys resolve. `claims` contains one claim per encounter (4,737 rows); its key is `claim_id`, and it links to `encounters.encounter_id` and `patients.patient_id`. Full per-table schema, dates, and missingness are in `docs/dataset_profile.md`.

Relevant grain-safe paths:

- Claim → encounter → provider: `claims.encounter_id` → `encounters.encounter_id`, then `encounters.provider_id` → `providers.provider_id`.
- Claim → payer: `claims.payer` is copied from `encounters.insurance` in every observed row.
- Claim → one-to-many clinical context: diagnoses, lab results, and prescriptions link through encounter and/or patient keys. Reduce them to encounter-level summaries before combining with claim-level amounts.

## Verified claim fields and labels

- Claim cohort timestamp: `claims.submitted_at`; report trends by submission month and display counts alongside observed denial rates.
- Status values: `paid` (4,122), `denied` (426), `pending` (189). Empty `paid_at` occurs on denied and pending rows; `denied_at` and `denial_reason` are empty on paid and pending rows.
- Financial source columns: `billed_amount`, `allowed_amount`, `paid_amount`, `patient_responsibility`, plus `allowed_ratio`. Amounts are populated at two decimal places; ratio precision is four decimals.
- `paid_amount` is the publisher's payer-payment field. It includes 606,755.02 among claims labeled `self_pay`; preserve the source label and disclose this generated-data behavior where payer totals are interpreted.
- There is no currency column, observation cutoff, remittance ledger, appeal/resubmission history, service-line detail, patient-payment transaction, or charge-adjustment field.
- Do not require claim submission or outcome after discharge. Observed source records include 278 submissions, 12 payments, and 4 denials before discharge; all claim submissions follow encounter admission and all payment/denial timestamps follow submission.

## Source reconciliation baseline

Independent Python `Decimal` checks against the raw CSVs produced these exact all-status totals:

| Measure | Amount |
| --- | ---: |
| Billed | 18,033,949.84 |
| Allowed | 9,172,905.62 |
| Recorded payer payment | 7,938,924.10 |
| Patient responsibility assigned | 7,779,126.53 |

The dashboard may use these as expected reconciliation values only after executed PostgreSQL queries reproduce them. They are not total cash collections: patient responsibility is an assigned amount with no evidence of payment receipt. The observed denial rate is 426 / 4,737 = 8.99%, but monthly rates are snapshot status counts without a cutoff or completion window.

## Join and transformation rules

- `claims` and `encounters` have a one-to-one relationship in the verified source, but preserve each table's own primary key and enforce the foreign key.
- Provider-level claim analysis joins through the encounter. Diagnose-, lab-, and prescription-level analysis must pre-aggregate to encounter or another explicitly stated grain before joining to claim financial measures.
- Preserve source fields and create separately named derived fields with documented formulas. Do not silently impute financial or status values. Assert row counts and exact money totals at each claim-grain join.

## KPI semantics to verify against source fields

- Claim volume: count of unique `claim_id` in the filtered claim cohort.
- Billed amount: sum of `claims.billed_amount`.
- Payer payment: sum of `claims.paid_amount`. Display separately from patient responsibility and do not label it total collected revenue.
- Denial rate: claims with `status = 'denied'` divided by all claims in the defined filtered claim cohort. For monthly analysis, use `submitted_at` and label this an observed cohort rate; status maturity is unknown.
- Payer/provider denial comparisons: show the denied-claim numerator and all-claim denominator for each group alongside the observed rate. Flag groups below 30 claims as small samples; this is a display caution, not an inferential threshold.
- Payment timing by payer: use claims with `status = 'paid'` and a non-null `submission_to_payment_days`; report the paid-claim count and discrete P50/P90 observed durations. Discrete percentiles select an observed duration using the same rank rule as PostgreSQL `percentile_disc`. These are paid-subset descriptions, not cohort-wide turnaround or aging.
- Allowed amount and patient responsibility: separate source-supported sums. Do not infer them from billed minus paid unless a documented reconciliation rule verifies that identity.
- Financial exposure: a clearly named descriptive sum (for example, billed value on denied claims); never describe as confirmed loss or recoverable cash.
- Aging and a total collection rate are unavailable: the source has no observation cutoff, remittance ledger, or patient-payment transactions. Submission-month volume and observed monthly denial rates are supported, but claim maturity by month is unknown. Submission-to-payment time is descriptive for the paid subset only; it is not a cohort-wide turnaround measure.

## PostgreSQL and export

- PostgreSQL is the authoritative execution environment for final analytical results. Store money in exact numeric types and document rounding at presentation/export boundaries.
- The export pipeline reads validated PostgreSQL views and writes JSON consumed by the deployed Streamlit app; production dashboard code must not require PostgreSQL.
- Write `dashboard/data/claims.json` and `dashboard/data/quality.json`. Both top-level objects contain `metadata` and `records` or validation results. `metadata` keys are `schema_version` (`1.0.0`), `generated_at` (UTC ISO 8601), `dataset_name`, `source_sha256`, `source_license`, `record_count`, `record_grain`, and `reconciled_with_postgres` (boolean). The claim export may be written only when PostgreSQL reconciliation is true.
- In `claims.json`, `metadata.record_count` is the number of claim records and `metadata.record_grain = "one row per claim"`. The top-level `records` array contains `claim_id`, `submitted_at`, `payer`, `encounter_type`, `provider_id`, `status`, `billed_amount`, `allowed_amount`, `payer_paid_amount`, `patient_responsibility`, `allowed_ratio`, `paid_at`, `denied_at`, `denial_reason`, and `submission_to_payment_days` (decimal string, null unless paid). Keep exact financial/numeric source values as decimal strings in JSON; omit `patient_id`, patient attributes, provider names/NPI, and all other unnecessary direct identifiers.
- In `quality.json`, `metadata.record_count` is the number of original source rows in scope (39,946), and `metadata.record_grain = "validation run across seven source tables"`. Top-level objects are `original` and `injected_test`; each has `summary`, `rules`, and `issues`. The original summary has `source_rows`, `rules_total`, `rules_passed`, and `issues_total`. The injected-test summary has `source_rows`, `rules_total`, `expected_findings`, `detected_findings`, `missed_findings`, and `tests_passed`; `tests_passed` is an integer count of test rules with all expected findings detected and zero missed findings. Each original rule has `rule_id`, `source_table`, `category`, `severity`, `tested_rows`, `issue_count`, `pass_rate`, and `recommended_action`. `pass_rate` is a decimal-string fraction from 0 to 1, calculated as 1 − `issue_count / tested_rows`; it is null when no rows were tested. Each injected-test rule instead has `rule_id`, `source_table`, `category`, `severity`, `expected_count`, `detected_count`, `missed_count`, `detection_rate`, `result`, and `recommended_action`; `result` is `pass` when `detected_count = expected_count` and `missed_count = 0`, otherwise `fail`. `detection_rate` is a decimal-string fraction from 0 to 1 or null when `expected_count` is 0. Each original issue has `rule_id`, `source_table`, `record_ref`, `issue_category`, `severity`, `resolution_status`, and `recommended_action`. It must not include patient IDs or corrupted test rows. For original claim-level exceptions, `record_ref` may be a `claim_id`; audit issues keyed by other source rows stay in the local audit report unless they can be safely de-identified. Injected-test issue details remain local; JSON exposes expected/detected/missed counts by rule only, with `injected_test.issues` empty.
- Represent timestamps in ISO 8601 and preserve nulls explicitly. Dashboard calculations must retain exact amount semantics and only convert values for chart rendering after aggregation.

## QA result separation

Report issues found in original source data separately from expected detections in deterministic, deliberately corrupted test copies. Keep rule ID, record key, source table, category, severity, result, resolution state, and action in the audit contract; define each rule and denominator in documentation.
