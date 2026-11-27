-- Q11. How do the four recorded financial amounts vary by payer and status?
-- Grain and denominator: one row per payer/status group; all claims within each group.
-- Limitation: patient responsibility is assigned. The source does not track patient payment transactions.
SELECT
    payer,
    status,
    count(*) AS claim_count,
    sum(billed_amount) AS billed_amount,
    sum(allowed_amount) AS allowed_amount,
    sum(payer_paid_amount) AS payer_paid_amount,
    sum(patient_responsibility) AS patient_responsibility
FROM rcm360.claim_analytics
GROUP BY payer, status
ORDER BY payer, status;

-- Q12. What is the billed-minus-allowed difference by payer and encounter type?
-- Grain and denominator: one row per payer/type group; all claims in that group.
-- Limitation: the source gives no adjustment ledger to classify this difference.
SELECT
    payer,
    encounter_type,
    count(*) AS claim_count,
    sum(billed_amount - allowed_amount) AS billed_minus_allowed_amount,
    round(avg(billed_amount - allowed_amount), 2) AS mean_billed_minus_allowed_amount
FROM rcm360.claim_analytics
GROUP BY payer, encounter_type
ORDER BY payer, encounter_type;

-- Q13. How large are recorded payer payments relative to billed and allowed amounts in each payer cohort?
-- Grain and denominator: one row per payer, plus an overall row; summed billed and allowed amounts, respectively.
-- Limitation: all observed statuses are included, and payment completeness is unknown.
WITH sums AS (
    SELECT
        CASE WHEN grouping(payer) = 1 THEN 'all_payers' ELSE payer END AS payer_group,
        count(*) AS claim_count,
        sum(billed_amount) AS billed_amount,
        sum(allowed_amount) AS allowed_amount,
        sum(payer_paid_amount) AS payer_paid_amount
    FROM rcm360.claim_analytics
    GROUP BY GROUPING SETS ((payer), ())
)
SELECT
    payer_group,
    claim_count,
    billed_amount,
    allowed_amount,
    payer_paid_amount,
    round(100.0 * payer_paid_amount / NULLIF(billed_amount, 0), 2) AS payer_paid_pct_of_billed,
    round(100.0 * payer_paid_amount / NULLIF(allowed_amount, 0), 2) AS payer_paid_pct_of_allowed
FROM sums
ORDER BY payer_group;

-- Q14. Do allowed amounts and stored ratios agree within half a cent?
-- Grain and denominator: one row per status; every claim is compared at its original grain before aggregation.
-- Limitation: 0.005 is a source precision check on billed times stored ratio versus allowed.
-- It measures distance before rounding, including either half-cent tie direction.
WITH residuals AS (
    SELECT
        status,
        abs(allowed_amount - billed_amount * allowed_ratio) AS absolute_residual
    FROM rcm360.claims
)
SELECT
    status,
    count(*) AS tested_claim_count,
    0.005::numeric AS tolerance_amount,
    max(absolute_residual) AS max_absolute_residual,
    count(*) FILTER (WHERE absolute_residual > 0.005) AS outside_tolerance_claim_count
FROM residuals
GROUP BY status
ORDER BY status;

-- Q15. Do source financial values follow zero <= recorded payment <= allowed <= billed?
-- Grain and denominator: one row per status; every loaded claim in that status.
-- Limitation: this verifies the loaded data. The schema also requires the ordering at insertion.
SELECT
    status,
    count(*) AS tested_claim_count,
    count(*) FILTER (
        WHERE NOT (
            0 <= paid_amount
            AND paid_amount <= allowed_amount
            AND allowed_amount <= billed_amount
            AND billed_amount <> 'NaN'::numeric
        )
    ) AS amount_order_exception_count
FROM rcm360.claims
GROUP BY status
ORDER BY status;

-- Q16. How often does assigned patient responsibility equal billed minus allowed under each status?
-- Grain and denominator: one row per status; each claim contributes one comparison.
-- Limitation: this checks generated field behavior and uses source values as recorded.
SELECT
    status,
    count(*) AS claim_count,
    count(*) FILTER (
        WHERE patient_responsibility = billed_amount - allowed_amount
    ) AS exact_match_count,
    count(*) FILTER (WHERE patient_responsibility = 0) AS zero_responsibility_count,
    sum(patient_responsibility) AS patient_responsibility,
    sum(billed_amount - allowed_amount) AS billed_minus_allowed_amount,
    sum(patient_responsibility - (billed_amount - allowed_amount)) AS responsibility_minus_difference_amount
FROM rcm360.claims
GROUP BY status
ORDER BY status;

-- Q17. What is the submission-to-payment distribution for observed paid claims?
-- Grain and denominator: payer roll-ups and payer/type groups; claims with paid status and recorded duration.
-- The payer roll-up supports the dashboard; the payer/type rows show encounter-type detail.
-- Limitation: results describe the paid subset. Discrete percentiles select observed durations.
SELECT
    payer,
    encounter_type,
    GROUPING(encounter_type) = 1 AS payer_rollup,
    count(*) AS observed_paid_claim_count,
    min(submission_to_payment_days) AS minimum_days,
    percentile_disc(0.25) WITHIN GROUP (ORDER BY submission_to_payment_days) AS p25_days,
    percentile_disc(0.50) WITHIN GROUP (ORDER BY submission_to_payment_days) AS p50_days,
    percentile_disc(0.90) WITHIN GROUP (ORDER BY submission_to_payment_days) AS p90_days,
    max(submission_to_payment_days) AS maximum_days
FROM rcm360.claim_analytics
WHERE status = 'paid' AND submission_to_payment_days IS NOT NULL
GROUP BY GROUPING SETS ((payer), (payer, encounter_type))
ORDER BY payer, payer_rollup DESC, encounter_type;

-- Q18. What payment values does the source record for claims labeled self_pay?
-- Grain and denominator: one row per self_pay status; sum across all payer groups in the same status for share.
-- Limitation: the synthetic labeling is preserved. The data omit who remitted a given payment.
WITH payer_status AS (
    SELECT
        payer,
        status,
        count(*) AS claim_count,
        count(*) FILTER (WHERE payer_paid_amount > 0) AS positive_payment_claim_count,
        sum(payer_paid_amount) AS payer_paid_amount,
        min(payer_paid_amount) AS minimum_payer_paid_amount,
        max(payer_paid_amount) AS maximum_payer_paid_amount
    FROM rcm360.claim_analytics
    GROUP BY payer, status
), status_totals AS (
    SELECT
        payer_status.*,
        sum(payer_paid_amount) OVER (PARTITION BY status) AS all_payer_groups_paid_amount
    FROM payer_status
)
SELECT
    status,
    claim_count,
    positive_payment_claim_count,
    payer_paid_amount,
    minimum_payer_paid_amount,
    maximum_payer_paid_amount,
    all_payer_groups_paid_amount,
    round(
        100.0 * payer_paid_amount / NULLIF(all_payer_groups_paid_amount, 0), 2
    ) AS self_pay_share_of_status_payment_pct
FROM status_totals
WHERE payer = 'self_pay'
ORDER BY status;
