-- rule ENCOUNTER_PATIENT_AGREEMENT
SELECT
    e.audit_row_id,
    e.encounter_id AS record_ref,
    e.patient_sex IS DISTINCT FROM p.sex OR e.insurance IS DISTINCT FROM p.insurance AS failed
FROM pg_temp.qa_encounters AS e
JOIN pg_temp.qa_patients AS p USING (patient_id);

-- rule CLAIM_ENCOUNTER_AGREEMENT
SELECT
    c.audit_row_id,
    c.claim_id AS record_ref,
    c.patient_id IS DISTINCT FROM e.patient_id
        OR c.payer IS DISTINCT FROM e.insurance
        OR c.encounter_type IS DISTINCT FROM e.encounter_type
        OR c.billed_amount IS DISTINCT FROM e.total_billed AS failed
FROM pg_temp.qa_claims AS c
JOIN pg_temp.qa_encounters AS e USING (encounter_id);

-- rule PRESCRIPTION_DIAGNOSIS_AGREEMENT
SELECT
    p.audit_row_id,
    p.prescription_id AS record_ref,
    p.encounter_id IS DISTINCT FROM d.encounter_id
        OR p.patient_id IS DISTINCT FROM d.patient_id
        OR p.category IS DISTINCT FROM d.category AS failed
FROM pg_temp.qa_prescriptions AS p
JOIN pg_temp.qa_diagnoses AS d USING (diagnosis_id);

-- rule ENCOUNTER_DISCHARGE_ORDER
SELECT
    audit_row_id,
    encounter_id AS record_ref,
    (admit_at < discharge_at) IS NOT TRUE AS failed
FROM pg_temp.qa_encounters;

-- rule CLAIM_SUBMISSION_ORDER
SELECT
    c.audit_row_id,
    c.claim_id AS record_ref,
    (c.submitted_at >= e.admit_at) IS NOT TRUE AS failed
FROM pg_temp.qa_claims AS c
JOIN pg_temp.qa_encounters AS e USING (encounter_id);

-- rule PRESCRIPTION_DIAGNOSIS_ORDER
SELECT
    p.audit_row_id,
    p.prescription_id AS record_ref,
    (p.prescribed_at >= d.diagnosed_at) IS NOT TRUE AS failed
FROM pg_temp.qa_prescriptions AS p
JOIN pg_temp.qa_diagnoses AS d USING (diagnosis_id);

-- rule CLAIM_OUTCOME_ORDER
SELECT
    audit_row_id,
    claim_id AS record_ref,
    (paid_at IS NULL OR paid_at >= submitted_at) IS NOT TRUE
        OR (denied_at IS NULL OR denied_at >= submitted_at) IS NOT TRUE AS failed
FROM pg_temp.qa_claims
WHERE paid_at IS NOT NULL OR denied_at IS NOT NULL;

-- rule CLAIM_STATUS_DOMAIN
SELECT
    audit_row_id,
    claim_id AS record_ref,
    (status IN ('paid', 'denied', 'pending')) IS NOT TRUE AS failed
FROM pg_temp.qa_claims;

-- rule CLAIM_STATUS_FIELDS
SELECT
    audit_row_id,
    claim_id AS record_ref,
    (status = 'paid') IS DISTINCT FROM (paid_at IS NOT NULL)
        OR (status = 'denied') IS DISTINCT FROM (denied_at IS NOT NULL)
        OR (status = 'denied') IS DISTINCT FROM (denial_reason IS NOT NULL)
        OR COALESCE(btrim(denial_reason) = '', false) AS failed
FROM pg_temp.qa_claims
WHERE status IN ('paid', 'denied', 'pending');

-- rule CLAIM_AMOUNT_ORDER
SELECT
    audit_row_id,
    claim_id AS record_ref,
    (
        0 <= paid_amount
        AND paid_amount <= allowed_amount
        AND allowed_amount <= billed_amount
        AND billed_amount <> 'NaN'::numeric
        AND patient_responsibility BETWEEN 0 AND billed_amount
    ) IS NOT TRUE AS failed
FROM pg_temp.qa_claims;

-- rule CLAIM_ALLOWED_RATIO
SELECT
    audit_row_id,
    claim_id AS record_ref,
    (
        allowed_ratio BETWEEN 0 AND 1
        AND abs(allowed_amount - billed_amount * allowed_ratio) <= 0.005
    ) IS NOT TRUE AS failed
FROM pg_temp.qa_claims
WHERE billed_amount > 0 AND billed_amount <> 'NaN'::numeric;

-- rule CLAIM_STATUS_AMOUNTS
SELECT
    audit_row_id,
    claim_id AS record_ref,
    CASE
        WHEN status = 'paid' THEN paid_amount IS DISTINCT FROM allowed_amount
            OR patient_responsibility IS DISTINCT FROM billed_amount - allowed_amount
        ELSE paid_amount IS DISTINCT FROM 0 OR patient_responsibility IS DISTINCT FROM 0
    END AS failed
FROM pg_temp.qa_claims
WHERE status IN ('paid', 'denied', 'pending');

-- rule LAB_FLAG_AGREEMENT
SELECT
    audit_row_id,
    lab_id AS record_ref,
    flag IS DISTINCT FROM CASE
        WHEN value < ref_low THEN 'low'
        WHEN value > ref_high THEN 'high'
        ELSE 'normal'
    END AS failed
FROM pg_temp.qa_lab_results
WHERE ref_low <= ref_high AND ref_high <> 'NaN'::numeric
    AND value IS NOT NULL AND value <> 'NaN'::numeric;

-- rule ENCOUNTER_CLAIM_COVERAGE
WITH claim_counts AS (
    SELECT encounter_id, count(*) AS claim_count
    FROM pg_temp.qa_claims
    GROUP BY encounter_id
)
SELECT
    e.audit_row_id,
    e.encounter_id AS record_ref,
    COALESCE(claim_counts.claim_count, 0) <> 1 AS failed
FROM pg_temp.qa_encounters AS e
LEFT JOIN claim_counts USING (encounter_id);
