-- Q28. How do submitted volume and observed denial rate change from the prior calendar month?
-- Grain and denominator: one row per calendar month from the first through last submission month.
-- Denial rate uses all claims submitted that month. Volume percentage change uses the prior month's count.
-- Empty months carry zero counts and NULL denial rates. Prior metrics are NULL in the first month.
-- Percentage volume change is NULL when the prior volume is zero. Denial-rate change requires claims in both months.
-- The trailing average uses three equally weighted months, including zero-volume months, and is NULL
-- until three months are available. An empty source returns no rows.
-- Limitation: boundary months may be partial. The source provides no observation cutoff,
-- so recent cohorts may have had less time to mature.
WITH monthly AS (
    SELECT
        date_trunc('month', submitted_at)::date AS submission_month,
        count(*) AS claim_count,
        count(*) FILTER (WHERE status = 'denied') AS denied_count
    FROM rcm360.claim_analytics
    GROUP BY submission_month
), bounds AS (
    SELECT
        min(submission_month)::timestamp AS first_month,
        max(submission_month)::timestamp AS last_month
    FROM monthly
), calendar AS (
    SELECT month_start::date AS submission_month
    FROM bounds
    CROSS JOIN LATERAL generate_series(first_month, last_month, interval '1 month') AS months(month_start)
), cohorts AS (
    SELECT
        calendar.submission_month,
        COALESCE(monthly.claim_count, 0) AS claim_count,
        COALESCE(monthly.denied_count, 0) AS denied_count,
        100.0 * monthly.denied_count / NULLIF(monthly.claim_count, 0) AS observed_denial_pct
    FROM calendar
    LEFT JOIN monthly USING (submission_month)
), comparisons AS (
    SELECT
        submission_month,
        claim_count,
        denied_count,
        observed_denial_pct,
        lag(claim_count) OVER month_order AS prior_month_claim_count,
        lag(observed_denial_pct) OVER month_order AS prior_month_observed_denial_pct,
        CASE WHEN count(*) OVER trailing_window = 3
            THEN avg(claim_count) OVER trailing_window
        END AS trailing_three_month_avg_claim_count
    FROM cohorts
    WINDOW
        month_order AS (ORDER BY submission_month),
        trailing_window AS (month_order ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
)
SELECT
    submission_month,
    claim_count,
    denied_count,
    round(observed_denial_pct, 2) AS observed_denial_pct,
    prior_month_claim_count,
    round(prior_month_observed_denial_pct, 2) AS prior_month_observed_denial_pct,
    claim_count - prior_month_claim_count AS claim_count_change,
    round(
        100.0 * (claim_count - prior_month_claim_count) / NULLIF(prior_month_claim_count, 0), 2
    ) AS claim_count_change_pct,
    round(observed_denial_pct - prior_month_observed_denial_pct, 2) AS denial_change_percentage_points,
    round(trailing_three_month_avg_claim_count, 2) AS trailing_three_month_avg_claim_count
FROM comparisons
ORDER BY submission_month;
