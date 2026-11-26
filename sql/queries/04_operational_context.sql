-- Q19. How often did submission, payment, and denial occur before discharge by encounter type?
-- Grain and denominator: one row per encounter type; the denominators are all claims for submission
-- and claims with a recorded timestamp for each outcome, respectively.
-- Limitation: event order describes the source. Pre-discharge events are not classified as errors.
WITH events AS (
    SELECT
        claims.encounter_type,
        count(*) AS submitted_count,
        count(*) FILTER (WHERE claims.submitted_at < encounters.discharge_at) AS submitted_before_discharge,
        count(claims.paid_at) AS recorded_payment_count,
        count(*) FILTER (WHERE claims.paid_at < encounters.discharge_at) AS paid_before_discharge,
        count(claims.denied_at) AS recorded_denial_count,
        count(*) FILTER (WHERE claims.denied_at < encounters.discharge_at) AS denied_before_discharge
    FROM rcm360.claim_analytics AS claims
    JOIN rcm360.encounters USING (encounter_id)
    GROUP BY claims.encounter_type
)
SELECT
    encounter_type,
    submitted_count,
    submitted_before_discharge,
    round(100.0 * submitted_before_discharge / NULLIF(submitted_count, 0), 2) AS submitted_before_discharge_pct,
    recorded_payment_count,
    paid_before_discharge,
    round(100.0 * paid_before_discharge / NULLIF(recorded_payment_count, 0), 2) AS paid_before_discharge_pct,
    recorded_denial_count,
    denied_before_discharge,
    round(100.0 * denied_before_discharge / NULLIF(recorded_denial_count, 0), 2) AS denied_before_discharge_pct
FROM events
ORDER BY encounter_type;

-- Q20. How does observed denial status vary by diagnosis category within encounter type?
-- Grain and denominator: one row per category/type group; claims linked to encounters with that category.
-- Limitation: categories overlap across claims, so counts cannot be summed across categories.
-- Presence within a category says nothing about severity or why a claim was denied.
WITH encounter_categories AS (
    SELECT DISTINCT encounter_id, category
    FROM rcm360.diagnoses
), cohorts AS (
    SELECT
        encounter_categories.category,
        claims.encounter_type,
        count(*) AS claim_count,
        count(*) FILTER (WHERE claims.status = 'denied') AS denied_count
    FROM encounter_categories
    JOIN rcm360.claim_analytics AS claims USING (encounter_id)
    GROUP BY encounter_categories.category, claims.encounter_type
)
SELECT
    category,
    encounter_type,
    claim_count,
    denied_count,
    claim_count < 30 AS fewer_than_30_claims,
    round(100.0 * denied_count / NULLIF(claim_count, 0), 2) AS observed_denial_pct
FROM cohorts
ORDER BY category, encounter_type;

-- Q21. How does observed denial status vary with the number of diagnosis records?
-- Grain and denominator: one row per count bucket/type; all linked claims in each mutually exclusive bucket/type.
-- Limitation: a diagnosis occurrence count is a documentation measure. Other case-mix variables are unadjusted.
WITH cohorts AS (
    SELECT
        claims.encounter_type,
        CASE
            WHEN encounters.diagnosis_count = 0 THEN '0'
            WHEN encounters.diagnosis_count = 1 THEN '1'
            WHEN encounters.diagnosis_count = 2 THEN '2'
            ELSE '3+'
        END AS diagnosis_count_bucket,
        claims.status
    FROM rcm360.claim_analytics AS claims
    JOIN rcm360.encounters USING (encounter_id)
)
SELECT
    encounter_type,
    diagnosis_count_bucket,
    count(*) AS claim_count,
    count(*) FILTER (WHERE status = 'denied') AS denied_count,
    round(
        100.0 * count(*) FILTER (WHERE status = 'denied') / NULLIF(count(*), 0), 2
    ) AS observed_denial_pct
FROM cohorts
GROUP BY encounter_type, diagnosis_count_bucket
ORDER BY encounter_type, diagnosis_count_bucket;

-- Q22. How does claim volume and gross billed amount split across recorded lab/prescription coverage patterns?
-- Grain and denominator: one row per encounter type and lab/prescription presence pair; all linked claims in that group.
-- Limitation: child-table coverage reflects what was generated. Claim totals carry no line-level charge attribution.
WITH lab_encounters AS (
    SELECT DISTINCT encounter_id
    FROM rcm360.lab_results
), prescription_encounters AS (
    SELECT DISTINCT encounter_id
    FROM rcm360.prescriptions
)
SELECT
    claims.encounter_type,
    lab_encounters.encounter_id IS NOT NULL AS has_lab_record,
    prescription_encounters.encounter_id IS NOT NULL AS has_prescription_record,
    count(*) AS claim_count,
    sum(claims.billed_amount) AS billed_amount,
    round(avg(claims.billed_amount), 2) AS mean_billed_amount
FROM rcm360.claim_analytics AS claims
LEFT JOIN lab_encounters USING (encounter_id)
LEFT JOIN prescription_encounters USING (encounter_id)
GROUP BY claims.encounter_type, has_lab_record, has_prescription_record
ORDER BY claims.encounter_type, has_lab_record, has_prescription_record;

-- Q23. How does encounter type change the mix of claim volume and billed amount?
-- Grain and denominator: one row per encounter type; all claim rows and all billed dollars, respectively, for shares.
-- Limitation: each claim covers one encounter in this snapshot. Type differences describe the synthetic mix.
WITH cohorts AS (
    SELECT
        encounter_type,
        count(*) AS claim_count,
        sum(billed_amount) AS billed_amount,
        percentile_disc(0.50) WITHIN GROUP (ORDER BY billed_amount) AS p50_billed_amount
    FROM rcm360.claim_analytics
    GROUP BY encounter_type
)
SELECT
    encounter_type,
    claim_count,
    billed_amount,
    p50_billed_amount,
    round(100.0 * claim_count / NULLIF(sum(claim_count) OVER (), 0), 2) AS share_of_claims_pct,
    round(100.0 * billed_amount / NULLIF(sum(billed_amount) OVER (), 0), 2) AS share_of_billed_pct
FROM cohorts
ORDER BY billed_amount DESC, encounter_type;

-- Q24. How much time elapsed from encounter admission to claim submission by encounter type?
-- Grain and denominator: one row per encounter type; each claim linked to its own encounter contributes one duration.
-- Limitation: the timestamp difference includes time in the visit and carries no workflow-specific service target.
WITH offsets AS (
    SELECT
        claims.encounter_type,
        round(extract(epoch FROM (claims.submitted_at - encounters.admit_at))::numeric / 3600, 6)
            AS admission_to_submission_hours
    FROM rcm360.claim_analytics AS claims
    JOIN rcm360.encounters USING (encounter_id)
)
SELECT
    encounter_type,
    count(*) AS claim_count,
    percentile_disc(0.25) WITHIN GROUP (ORDER BY admission_to_submission_hours) AS p25_hours,
    percentile_disc(0.50) WITHIN GROUP (ORDER BY admission_to_submission_hours) AS p50_hours,
    percentile_disc(0.90) WITHIN GROUP (ORDER BY admission_to_submission_hours) AS p90_hours
FROM offsets
GROUP BY encounter_type
ORDER BY encounter_type;
