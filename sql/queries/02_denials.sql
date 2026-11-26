-- Q07. Which recorded denial reasons appear most often?
-- Grain and denominator: one row per recorded reason; all denied claims for the reason share.
-- Limitation: reasons describe source labels. Claim and encounter keys remain unique for the duplicate_claim label.
WITH reasons AS (
    SELECT
        denial_reason,
        count(*) AS denied_count
    FROM rcm360.claim_analytics
    WHERE status = 'denied'
    GROUP BY denial_reason
)
SELECT
    denial_reason,
    denied_count,
    sum(denied_count) OVER () AS all_denied_claim_count,
    round(100.0 * denied_count / NULLIF(sum(denied_count) OVER (), 0), 2) AS share_of_denials_pct
FROM reasons
ORDER BY denied_count DESC, denial_reason;

-- Q08. How does each reason's incidence vary across payers and encounter types?
-- Grain and denominator: one row per payer/type/observed reason; all claims in the payer/type group for incidence.
-- The mix share uses only denied claims in that same payer/type group.
-- Limitation: this comparison describes recorded labels in the snapshot. Small group counts can dominate rates.
WITH cohorts AS (
    SELECT
        payer,
        encounter_type,
        count(*) AS claim_count,
        count(*) FILTER (WHERE status = 'denied') AS denied_count
    FROM rcm360.claim_analytics
    GROUP BY payer, encounter_type
), reason_counts AS (
    SELECT
        payer,
        encounter_type,
        denial_reason,
        count(*) AS reason_denied_count
    FROM rcm360.claim_analytics
    WHERE status = 'denied'
    GROUP BY payer, encounter_type, denial_reason
), reasons AS (
    SELECT DISTINCT denial_reason
    FROM reason_counts
)
SELECT
    cohorts.payer,
    cohorts.encounter_type,
    reasons.denial_reason,
    cohorts.claim_count,
    cohorts.denied_count,
    COALESCE(reason_counts.reason_denied_count, 0) AS reason_denied_count,
    round(
        100.0 * COALESCE(reason_counts.reason_denied_count, 0) / NULLIF(cohorts.claim_count, 0), 2
    ) AS reason_incidence_pct,
    round(
        100.0 * COALESCE(reason_counts.reason_denied_count, 0) / NULLIF(cohorts.denied_count, 0), 2
    ) AS share_of_cohort_denials_pct
FROM cohorts
CROSS JOIN reasons
LEFT JOIN reason_counts
    ON reason_counts.payer = cohorts.payer
    AND reason_counts.encounter_type = cohorts.encounter_type
    AND reason_counts.denial_reason = reasons.denial_reason
ORDER BY cohorts.payer, cohorts.encounter_type, reasons.denial_reason;

-- Q09. What gross billed amount is attached to denied claims by month, payer, and reason?
-- Grain and denominator: one row per observed submission-month/payer/reason group; denied claims only.
-- For billed share, the denominator is billed on all denied claims in that month and payer.
-- Limitation: these are source charges on denied claims. The snapshot has no write-off or recovery events.
WITH groups AS (
    SELECT
        date_trunc('month', submitted_at)::date AS submission_month,
        payer,
        denial_reason,
        count(*) AS denied_count,
        sum(billed_amount) AS denied_billed_amount
    FROM rcm360.claim_analytics
    WHERE status = 'denied'
    GROUP BY submission_month, payer, denial_reason
)
SELECT
    submission_month,
    payer,
    denial_reason,
    denied_count,
    denied_billed_amount,
    round(
        100.0 * denied_billed_amount / NULLIF(
            sum(denied_billed_amount) OVER (PARTITION BY submission_month, payer), 0
        ), 2
    ) AS share_of_payer_month_denied_billed_pct
FROM groups
ORDER BY submission_month, payer, denied_billed_amount DESC, denial_reason;

-- Q10. How concentrated are denied counts and gross denied billed amounts across reasons?
-- Grain and denominator: one row per denial reason; all denied counts and all billed on denied claims, respectively.
-- Limitation: reason-level concentration describes recorded exposure. There is no evidence about potential intervention effects.
-- Rows display in count rank order. Sort by rank_by_billed to read the billed cumulative sequence.
WITH reasons AS (
    SELECT
        denial_reason,
        count(*) AS denied_count,
        sum(billed_amount) AS denied_billed_amount
    FROM rcm360.claim_analytics
    WHERE status = 'denied'
    GROUP BY denial_reason
)
SELECT
    denial_reason,
    denied_count,
    denied_billed_amount,
    row_number() OVER count_order AS rank_by_count,
    row_number() OVER billed_order AS rank_by_billed,
    round(
        100.0 * sum(denied_count) OVER count_order / NULLIF(sum(denied_count) OVER (), 0), 2
    ) AS cumulative_denied_count_pct,
    round(
        100.0 * sum(denied_billed_amount) OVER billed_order / NULLIF(sum(denied_billed_amount) OVER (), 0), 2
    ) AS cumulative_denied_billed_pct
FROM reasons
WINDOW
    count_order AS (
        ORDER BY denied_count DESC, denial_reason
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ),
    billed_order AS (
        ORDER BY denied_billed_amount DESC, denial_reason
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )
ORDER BY rank_by_count;
