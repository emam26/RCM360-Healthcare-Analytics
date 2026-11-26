# PostgreSQL quality audit

Run the audit after loading the approved Misata snapshot. Set DATABASE_URL and run the command from the project root.

~~~powershell
python -m src.validation.audit
~~~

The command reports original data and injected tests in separately labeled JSON objects. It exits nonzero on an original issue, an incomplete injection test, or an execution error. The command uses a read-write transaction with permission to create temporary tables. It reads the seven source tables and rolls back all temporary tables before returning.

## Tested grain and rules

Each rule tests source rows from one table. A row can contribute at most one issue to a rule. The original summary counts issues across rules, so a row can contribute to several rules. The original pass rate uses the eligible row count for that rule. A zero-row denominator yields a null pass rate. Summary source_rows is the row count across the seven original source tables.

| Rule family | Checks | Tested records | Injected case per rule |
| --- | ---: | --- | --- |
| PK_ followed by the source table | 7 | Every row of each table. Check for missing, whitespace-only, or repeated primary keys. Count every duplicate participant. | Copy the first key onto the second row, clear the third, and set the fourth to a space. Expect four findings including the duplicate peer. |
| FK_ followed by the source table and foreign key | 11 | Every row of each child table. Each foreign key must reach its parent table. The mappings follow the typed schema and data contract. | Use an absent parent key on the first row and clear the second. Expect two findings. |

| Rule | Eligible rows | Tested condition | Injected case |
| --- | --- | --- | --- |
| ENCOUNTER_PATIENT_AGREEMENT | Encounters with a linked patient | Encounter sex and insurance match the patient | Change encounter insurance |
| CLAIM_ENCOUNTER_AGREEMENT | Claims with a linked encounter | Patient, payer/insurance, type and billed fields match | Change claim payer |
| PRESCRIPTION_DIAGNOSIS_AGREEMENT | Prescriptions with a linked diagnosis | Encounter, patient and category match the diagnosis | Change prescription category |
| ENCOUNTER_DISCHARGE_ORDER | All encounters | Discharge follows admission | Move discharge one second before admission |
| CLAIM_SUBMISSION_ORDER | Claims with a linked encounter | Submission is on or after admission | Move submission one second before admission |
| PRESCRIPTION_DIAGNOSIS_ORDER | Prescriptions with a linked diagnosis | Prescription is on or after diagnosis | Move prescription one second before diagnosis |
| CLAIM_OUTCOME_ORDER | Claims with a payment or denial timestamp | Each populated outcome is on or after submission | Move a payment one second before submission |
| CLAIM_STATUS_DOMAIN | All claims | Status is paid, denied, or pending | Set an unrecognized status |
| CLAIM_STATUS_FIELDS | Claims with a recognized status | Payment date belongs to paid claims. Denial date and nonblank reason belong to denied claims. | Clear a denied claim's reason |
| CLAIM_AMOUNT_ORDER | All claims | Zero ≤ payment ≤ allowed ≤ billed, with finite amounts and zero ≤ responsibility ≤ billed | Increase payment to one cent above allowed |
| CLAIM_ALLOWED_RATIO | Claims with positive, finite billed amount | Ratio is from 0 to 1, and the allowed amount differs from billed times ratio by at most 0.005 | Move the ratio to the farther endpoint |
| CLAIM_STATUS_AMOUNTS | Claims with a recognized status | Paid claims carry payment equal to allowed and responsibility equal to billed minus allowed. Other statuses carry zero for both fields. | Assign a cent of responsibility to a pending claim |
| LAB_FLAG_AGREEMENT | Lab results with a finite value and an ordered finite reference interval | Flag matches the source value relative to the supplied bounds | Change a flag to the opposite category |
| ENCOUNTER_CLAIM_COVERAGE | All encounters | Each encounter has one claim in the verified snapshot | Remove one linked claim from the temporary copy |

Relationship checks that require a parent use linked records. The corresponding FK check measures missing parent links over every child record. Source behavior supports the half-cent tolerance, optional status fields, and status-dependent amount identities. Pre-discharge claim events and self-pay payments are valid observed source behavior. Phone is optional. Lab flag evaluation uses the supplied interval for that row.

## Isolation and detection accounting

Temporary tables copy the original PostgreSQL values without constraints and add a stable row number ordered by the source key with C collation. The audit records all original evaluations before seeding any defects. It then applies each mutation inside its own savepoint, evaluates the same rule, and rolls back the mutation. This controls for side effects on unrelated rules while preserving the original and test results separately.

Expected findings are record-level identities obtained from the mutation target and any documented duplicate peer. New findings exclude issue identities already present in the original evaluation. Detected count includes any unexpected new finding, and missed count measures expected identities that were absent. Detection rate divides correctly found expected identities by expected count. A case passes only when detected and expected counts match and no expected identity is missed. The tests seed 64 expected findings across 32 rules by design. Live detections depend on running the audit against PostgreSQL.

The Python function run_quality returns local results, including source references and injected case outcomes for investigation. public_results keeps original claim-level issue references and suppresses all injected issue details. The CLI prints that public-safe projection. The export layer adds the metadata from the [data contract](../../docs/data_contract.md).
