# Misata source profile

## Provenance and verification

- Misata labels the dataset **CC0** and describes it as fully synthetic. The archive `README.md` says it is free to use without attribution and was generated without real data. The archive contains no standalone license file. [Misata dataset page](https://www.misata.studio/datasets/hospital-encounters-claims)
- The download returned HTTP 200 (`application/zip`) and was saved as `data/raw/hospital-encounters-claims.zip` at **2026-11-26T21:22:55.4340125Z**. It is **754,494 bytes** (736.81 KiB). SHA-256 is `ce8d4d2053ebe0bb1d89e6d5de0d370bbc19d04bcc122c351832916b6591897a`, computed locally. [Publisher's CSV archive](https://www.misata.studio/datasets/hospital-encounters-claims.zip)
- `python -m zipfile -t data/raw/hospital-encounters-claims.zip` passed. Python `zipfile` extraction preserved the seven CSV members byte for byte. The archive also contains `INTEGRITY.txt` (1,655 bytes), `README.md` (2,135), `RECIPE.json` (206), and `ANSWERS.sql` (3,591). The page links `ANSWERS.sql` in its examples and omits it from its archive inventory. The original archive retains all four files.
- `RECIPE.json` identifies engine `misata-studio`, pack `healthcare`, the 1,500-patient override, seed `20260921`, and blueprint hash `8c8ef1dcee3cb646d59bf3c82e1e5e91b37fb4a15c21d312c06a74154d81b5c1`.
- Source checks used Python 3.11 `csv.DictReader`, `datetime.fromisoformat`, `decimal.Decimal`, and key lookups over the full CSVs. Each row matched the width of its distinct header fields. These are source profiling results. The project uses executed PostgreSQL for its analytical results and reconciliation.

## Files and record grain

| CSV file | Rows | Columns | Bytes | Record grain | Primary key |
| --- | ---: | ---: | ---: | --- | --- |
| `claims.csv` | 4,737 | 15 | 550,213 | One claim with one observed status | `claim_id` |
| `diagnoses.csv` | 8,427 | 8 | 832,875 | One coded diagnosis occurrence | `diagnosis_id` |
| `encounters.csv` | 4,737 | 11 | 448,373 | One patient encounter | `encounter_id` |
| `lab_results.csv` | 14,946 | 10 | 1,090,897 | One analyte result | `lab_id` |
| `patients.csv` | 1,500 | 13 | 195,817 | One synthetic patient | `patient_id` |
| `prescriptions.csv` | 5,539 | 11 | 475,724 | One prescription linked to a diagnosis | `prescription_id` |
| `providers.csv` | 60 | 5 | 4,052 | One synthetic provider | `provider_id` |
| **Total** | **39,946** | **73** | | | |

All seven primary keys are populated and unique. All table counts match the page and archived README.

| Child table | Foreign keys and targets | Observed child rows per referenced parent |
| --- | --- | --- |
| `claims` | `encounter_id` → `encounters`, `patient_id` → `patients` | 1 per encounter, 1–20 per linked patient |
| `diagnoses` | `encounter_id` → `encounters`, `patient_id` → `patients` | 1–8 per encounter, 1–43 per linked patient |
| `encounters` | `patient_id` → `patients`, `provider_id` → `providers` | 1–20 per linked patient, 1–681 per provider |
| `lab_results` | `encounter_id` → `encounters`, `patient_id` → `patients` | 1–11 per linked encounter, 1–68 per linked patient |
| `prescriptions` | `diagnosis_id` → `diagnoses`, `encounter_id` → `encounters`, `patient_id` → `patients` | 1–5 per linked diagnosis, 1–8 per linked encounter, 1–27 per linked patient |

The 11 foreign keys resolve across **82,311** populated references with zero orphans, matching the publisher. Every encounter has one claim and at least one diagnosis. Labs are present on 4,016 encounters, and prescriptions on 2,944 encounters and 4,035 diagnoses. Of the 1,500 patients, 1,185 have encounters, and all 60 providers have encounters. The source `encounter_count` and `diagnosis_count` match the observed child counts on every row.

Patient IDs on all encounter-linked rows agree with the encounter's patient ID. Prescription patient, encounter and category agree with the linked diagnosis. Encounter patient sex and insurance match the patient, diagnosis `patient_sex` matches the patient, and claim `payer`, `encounter_type` and `billed_amount` match the encounter's `insurance`, `encounter_type` and `total_billed`. The patient and provider dimensions can be joined through the encounter. Reduce diagnoses, labs and prescriptions to one row per relevant encounter or explicitly allocate dollars before joining to claim amounts. There are 41 ICD-10 codes and 270 rows above one occurrence per encounter/code pair.

## Column dictionary and missingness

The types below are interpreted from parsed CSV values. Store IDs, codes, NPI, phone and postal code as text so formatting survives. NPI has 10 digits on all provider rows and is unique in this file. Timestamps have second precision and no timezone offset. All decimal fields parsed as finite exact values.

| Table | Text, identifiers and categories | Date and timestamp fields | Integer fields | Decimal fields and maximum observed scale |
| --- | --- | --- | --- | --- |
| `claims` | `claim_id`, `encounter_id`, `patient_id`, `payer`, `encounter_type`, `status`, `denial_reason` | `submitted_at`, `paid_at`, `denied_at` | | `billed_amount`, `allowed_amount`, `paid_amount`, `patient_responsibility` (2), `allowed_ratio` (4) |
| `diagnoses` | `diagnosis_id`, `encounter_id`, `patient_id`, `patient_sex`, `icd10_code`, `description`, `category` | `diagnosed_at` | | |
| `encounters` | `encounter_id`, `patient_id`, `provider_id`, `patient_sex`, `insurance`, `encounter_type` | `admit_at`, `discharge_at` | `diagnosis_count` | `los_hours` (4), `total_billed` (2) |
| `lab_results` | `lab_id`, `encounter_id`, `patient_id`, `analyte`, `unit`, `flag` | `collected_at` | | `value` (2), `ref_low`, `ref_high` (1) |
| `patients` | `patient_id`, `full_name`, `sex`, `insurance`, `city`, `region`, `country`, `street_address`, `postal_code`, `phone` | `date_of_birth` (date), `registered_at` | `encounter_count` | |
| `prescriptions` | `prescription_id`, `diagnosis_id`, `encounter_id`, `patient_id`, `category`, `drug`, `dose_unit`, `frequency` | `prescribed_at` | `days_supply` | `dose` (1) |
| `providers` | `provider_id`, `provider_name`, `specialty`, `npi`, `facility` | | | |

Only four fields contain empty CSV cells. Each other field is populated throughout, and no field has whitespace-only values.

| Field | Empty cells | Share | Observed condition |
| --- | ---: | ---: | --- |
| `claims.paid_at` | 615 | 12.98% | Every denied or pending claim |
| `claims.denied_at` | 4,311 | 91.01% | Every paid or pending claim |
| `claims.denial_reason` | 4,311 | 91.01% | Every paid or pending claim |
| `patients.phone` | 46 | 3.07% | Empty on 46 patient rows |

Claim `payer` and encounter `insurance` use `commercial`, `medicaid`, `medicare`, `other`, and `self_pay`. Claim and encounter `encounter_type` use `outpatient` (3,101 encounters), `inpatient` (835), and `emergency` (801). Providers have 11 specialty and six facility labels. Lab result units and reference ranges are analyte-specific. All 14,946 source lab flags agree with the supplied lower and upper bounds.

## Observed date ranges

Ranges use the source's timezone-free values. For optional timestamps, endpoints use populated rows.

| Field | Earliest | Latest |
| --- | --- | --- |
| `patients.date_of_birth` | `1931-09-12` | `2025-07-15` |
| `patients.registered_at` | `2024-09-02 15:32:29` | `2026-08-31 16:45:29` |
| `encounters.admit_at` | `2024-09-10 13:06:36` | `2026-08-31 16:46:03` |
| `encounters.discharge_at` | `2024-09-10 14:13:09` | `2026-09-15 23:26:18` |
| `diagnoses.diagnosed_at` | `2024-09-10 13:06:36` | `2026-08-31 16:46:03` |
| `prescriptions.prescribed_at` | `2024-09-10 13:06:36` | `2026-08-31 16:45:55` |
| `lab_results.collected_at` | `2024-09-10 13:14:08` | `2026-09-13 18:15:31` |
| `claims.submitted_at` | `2024-09-14 16:36:42` | `2026-08-31 16:46:55` |
| `claims.paid_at` | `2024-10-09 20:26:07` | `2026-08-30 23:17:57` |
| `claims.denied_at` | `2024-11-17 19:26:46` | `2026-08-30 23:16:30` |

All discharges follow admission. The source `los_hours` medians are 4.4852 hours for emergency, 97.3035 hours (4.05 days) for inpatient and 1.0072 hours for outpatient. Patient registrations are on or after birth, admissions follow registrations, diagnoses and labs fall within the encounter, and prescriptions occur on or after their diagnoses. All submissions occur on or after admission, including two at the same recorded second. All payment and denial timestamps follow submission. A pre-discharge submission occurs in 278 claims across 259 inpatient, 12 outpatient and 7 emergency encounters. Twelve payments and four denials precede inpatient discharge. The publisher's date-order statement establishes no claim submission or outcome rule relative to discharge.

## Claims finance and limits

| Status | Claims | Billed amount | Allowed amount | Recorded payer payment | Patient responsibility |
| --- | ---: | ---: | ---: | ---: | ---: |
| `paid` | 4,122 | 15,718,050.63 | 7,938,924.10 | 7,938,924.10 | 7,779,126.53 |
| `denied` | 426 | 1,495,593.80 | 778,187.90 | 0.00 | 0.00 |
| `pending` | 189 | 820,305.41 | 455,793.62 | 0.00 | 0.00 |
| **All** | **4,737** | **18,033,949.84** | **9,172,905.62** | **7,938,924.10** | **7,779,126.53** |

- `billed_amount` is the claim charge carried over from the encounter. `allowed_amount` is present for all statuses. `paid_amount` is the publisher's payer payment measure and includes 606,755.02 attributed to the generated `self_pay` category. Its total is 44.02% of billed. The publisher's examples report dollars. Each claim carries amounts without a separate currency field.
- All claims satisfy `0 ≤ paid_amount ≤ allowed_amount ≤ billed_amount`. On paid claims, the payment equals allowed and the responsibility equals billed minus allowed. Denied and pending claims use literal zero for payment and responsibility. Source `allowed_amount` differs from the unrounded `billed_amount × allowed_ratio` by at most 0.005. Preserve the source amounts, including `patient_responsibility`, which records an assigned amount and carries no evidence of cash receipt.
- The overall observed denial rate is 426 / 4,737 = **8.99%**. Payer denominators and denied counts are commercial 198 / 2,136, Medicaid 75 / 952, Medicare 103 / 1,111, other 27 / 263, and self-pay 23 / 275. The five denial reasons are `not_medically_necessary` (123), `missing_authorization` (96), `out_of_network` (88), `coding_error` (60), and `duplicate_claim` (59). `duplicate_claim` is a source reason label. The primary and encounter keys are unique across these records.
- Billed on denied claims totals 1,495,593.80. The snapshot contains no appeals, resubmission history, service lines, remittance ledger, patient payment transactions, charge adjustments or observation cutoff. Pending status alone does not establish an overdue balance. A submitted-month denial rate describes each cohort's observed status and may reflect incomplete follow-up in recent months. Submission-to-payment time describes observed paid claims and remains distinct from a collection measure across the whole cohort.
- The publisher's remaining summary checks also reproduce. The 12 busiest providers handled 2,541 of 4,737 encounters (53.64%), and hemoglobin A1c represents 566 of 4,776 outpatient results (11.85%) and 28 of 3,538 emergency results (0.79%). The published patterns describe this synthetic generator and sample. They carry no evidence of real hospital operations, payer performance, or clinical effects.
- Raw records contain synthetic names, addresses, phone numbers, dates of birth and identifiers. Publish only aggregate operational results and the privacy-minimized fields needed for dashboard filtering and reconciliation.
