-- Q25. Do claim payer, type, and billed amount match the corresponding encounter fields?
-- Grain and denominator: one overall row; every claim is compared to at most one encounter.
-- Limitation: mismatch counts identify recorded differences. Field-specific counts may overlap.
SELECT
    count(*) AS tested_claim_count,
    count(encounters.encounter_id) AS linked_claim_count,
    count(*) FILTER (WHERE encounters.encounter_id IS NULL) AS missing_encounter_count,
    count(*) FILTER (
        WHERE encounters.encounter_id IS NOT NULL AND claims.payer IS DISTINCT FROM encounters.insurance
    ) AS payer_mismatch_count,
    count(*) FILTER (
        WHERE encounters.encounter_id IS NOT NULL AND claims.encounter_type IS DISTINCT FROM encounters.encounter_type
    ) AS encounter_type_mismatch_count,
    count(*) FILTER (
        WHERE encounters.encounter_id IS NOT NULL AND claims.billed_amount IS DISTINCT FROM encounters.total_billed
    ) AS billed_amount_mismatch_count
FROM rcm360.claims
LEFT JOIN rcm360.encounters USING (encounter_id);

-- Q26. Do base claims and the claim view reproduce the independently profiled counts and exact amounts?
-- Grain and denominator: one row per reconciliation metric across the verified snapshot; all claims.
-- Limitation: expected values belong to the pinned source archive. Aggregate agreement complements record-level checks.
WITH base AS (
    SELECT
        count(*) AS claim_count,
        count(DISTINCT claim_id) AS distinct_claim_count,
        count(*) FILTER (WHERE status = 'paid') AS paid_count,
        count(*) FILTER (WHERE status = 'denied') AS denied_count,
        count(*) FILTER (WHERE status = 'pending') AS pending_count,
        sum(billed_amount) AS billed_amount,
        sum(allowed_amount) AS allowed_amount,
        sum(paid_amount) AS payer_paid_amount,
        sum(patient_responsibility) AS patient_responsibility,
        sum(billed_amount) FILTER (WHERE status = 'denied') AS denied_billed_amount
    FROM rcm360.claims
), analytics AS (
    SELECT
        count(*) AS claim_count,
        count(DISTINCT claim_id) AS distinct_claim_count,
        count(*) FILTER (WHERE status = 'paid') AS paid_count,
        count(*) FILTER (WHERE status = 'denied') AS denied_count,
        count(*) FILTER (WHERE status = 'pending') AS pending_count,
        sum(billed_amount) AS billed_amount,
        sum(allowed_amount) AS allowed_amount,
        sum(payer_paid_amount) AS payer_paid_amount,
        sum(patient_responsibility) AS patient_responsibility,
        sum(billed_amount) FILTER (WHERE status = 'denied') AS denied_billed_amount
    FROM rcm360.claim_analytics
)
SELECT
    measures.metric,
    measures.expected_value,
    measures.base_value,
    measures.view_value,
    measures.base_value IS NOT DISTINCT FROM measures.expected_value
        AND measures.view_value IS NOT DISTINCT FROM measures.expected_value AS matches_snapshot
FROM base
CROSS JOIN analytics
CROSS JOIN LATERAL (
    VALUES
        ('claim_count', 4737::numeric, base.claim_count, analytics.claim_count),
        ('distinct_claim_count', 4737, base.distinct_claim_count, analytics.distinct_claim_count),
        ('paid_count', 4122, base.paid_count, analytics.paid_count),
        ('denied_count', 426, base.denied_count, analytics.denied_count),
        ('pending_count', 189, base.pending_count, analytics.pending_count),
        ('billed_amount', 18033949.84, base.billed_amount, analytics.billed_amount),
        ('allowed_amount', 9172905.62, base.allowed_amount, analytics.allowed_amount),
        ('payer_paid_amount', 7938924.10, base.payer_paid_amount, analytics.payer_paid_amount),
        ('patient_responsibility', 7779126.53, base.patient_responsibility, analytics.patient_responsibility),
        ('denied_billed_amount', 1495593.80, base.denied_billed_amount, analytics.denied_billed_amount)
) AS measures(metric, expected_value, base_value, view_value)
ORDER BY measures.metric;

-- Q27. Do observed child counts agree with the source parent counts and one-claim-per-encounter snapshot?
-- Grain and denominator: one row per coverage check; every patient or encounter in the respective check.
-- Limitation: zero child encounters is valid for a patient. The claim-coverage rule describes this dataset version.
WITH encounters_per_patient AS (
    SELECT patient_id, count(*) AS row_count
    FROM rcm360.encounters
    GROUP BY patient_id
), diagnoses_per_encounter AS (
    SELECT encounter_id, count(*) AS row_count
    FROM rcm360.diagnoses
    GROUP BY encounter_id
), claims_per_encounter AS (
    SELECT encounter_id, count(*) AS row_count
    FROM rcm360.claims
    GROUP BY encounter_id
), coverage AS (
    SELECT
        'patient_encounter_count' AS check_name,
        count(*) AS tested_parent_count,
        count(*) FILTER (
            WHERE patients.encounter_count <> COALESCE(encounters_per_patient.row_count, 0)
        ) AS mismatch_count
    FROM rcm360.patients
    LEFT JOIN encounters_per_patient USING (patient_id)

    UNION ALL

    SELECT
        'encounter_diagnosis_count',
        count(*),
        count(*) FILTER (
            WHERE encounters.diagnosis_count <> COALESCE(diagnoses_per_encounter.row_count, 0)
        )
    FROM rcm360.encounters
    LEFT JOIN diagnoses_per_encounter USING (encounter_id)

    UNION ALL

    SELECT
        'encounter_claim_coverage',
        count(*),
        count(*) FILTER (WHERE COALESCE(claims_per_encounter.row_count, 0) <> 1)
    FROM rcm360.encounters
    LEFT JOIN claims_per_encounter USING (encounter_id)
)
SELECT check_name, tested_parent_count, mismatch_count
FROM coverage
ORDER BY check_name;
