-- Q01. How does submitted claim volume vary by month, payer, and encounter type?
-- Grain and denominator: one row per observed submission-month/payer/type cohort; all claims in each cohort.
-- Limitation: groups with zero submissions are absent. The first and last months can be partial.
SELECT
    date_trunc('month', submitted_at)::date AS submission_month,
    payer,
    encounter_type,
    count(*) AS claim_count
FROM rcm360.claim_analytics
GROUP BY submission_month, payer, encounter_type
ORDER BY submission_month, payer, encounter_type;

-- Q02. How does observed claim status mix vary across submission cohorts?
-- Grain and denominator: one row per submission month; all claims submitted that month.
-- Limitation: the source has no observation cutoff. More recent cohorts may have less follow-up.
WITH monthly AS (
    SELECT
        date_trunc('month', submitted_at)::date AS submission_month,
        count(*) AS claim_count,
        count(*) FILTER (WHERE status = 'paid') AS paid_count,
        count(*) FILTER (WHERE status = 'denied') AS denied_count,
        count(*) FILTER (WHERE status = 'pending') AS pending_count
    FROM rcm360.claim_analytics
    GROUP BY submission_month
)
SELECT
    submission_month,
    claim_count,
    paid_count,
    denied_count,
    pending_count,
    round(100.0 * paid_count / NULLIF(claim_count, 0), 2) AS observed_paid_pct,
    round(100.0 * denied_count / NULLIF(claim_count, 0), 2) AS observed_denial_pct,
    round(100.0 * pending_count / NULLIF(claim_count, 0), 2) AS observed_pending_pct
FROM monthly
ORDER BY submission_month;

-- Q03. What is the overall observed denial rate in the verified snapshot?
-- Grain and denominator: one overall row; all claims across all observed statuses.
-- Limitation: the rate reflects one status per claim with no history of first submissions or appeals.
SELECT
    count(*) AS claim_count,
    count(*) FILTER (WHERE status = 'denied') AS denied_count,
    round(
        100.0 * count(*) FILTER (WHERE status = 'denied') / NULLIF(count(*), 0), 2
    ) AS observed_denial_pct
FROM rcm360.claim_analytics;

-- Q04. Which payers have higher observed denial rates, and how much denial volume do they account for?
-- Grain and denominator: one row per payer; payer claims for the rate and all denied claims for burden share.
-- Limitation: payer groups differ in case mix. The fewer-than-30 flag identifies small descriptive cohorts.
WITH payer_counts AS (
    SELECT
        payer,
        count(*) AS claim_count,
        count(*) FILTER (WHERE status = 'denied') AS denied_count
    FROM rcm360.claim_analytics
    GROUP BY payer
)
SELECT
    payer,
    claim_count,
    denied_count,
    claim_count < 30 AS fewer_than_30_claims,
    round(100.0 * denied_count / NULLIF(claim_count, 0), 2) AS observed_denial_pct,
    round(100.0 * denied_count / NULLIF(sum(denied_count) OVER (), 0), 2) AS share_of_all_denials_pct
FROM payer_counts
ORDER BY denied_count::numeric / NULLIF(claim_count, 0) DESC, payer;

-- Q05. How does each provider's observed denial rate compare with a benchmark based on its encounter-type mix?
-- Grain and denominator: one row per provider with claims; all of that provider's claims.
-- Limitation: the internal benchmark uses pooled encounter-type rates, including the provider under review.
-- It accounts for encounter type only. The fewer-than-30 flag identifies small descriptive cohorts.
WITH provider_type AS (
    SELECT
        provider_id,
        encounter_type,
        count(*) AS claim_count,
        count(*) FILTER (WHERE status = 'denied') AS denied_count
    FROM rcm360.claim_analytics
    GROUP BY provider_id, encounter_type
), type_benchmark AS (
    SELECT
        encounter_type,
        sum(denied_count) / NULLIF(sum(claim_count), 0) AS denial_fraction
    FROM provider_type
    GROUP BY encounter_type
), providers AS (
    SELECT
        provider_type.provider_id,
        sum(provider_type.claim_count) AS claim_count,
        sum(provider_type.denied_count) AS denied_count,
        sum(provider_type.claim_count * type_benchmark.denial_fraction) AS benchmark_denial_count
    FROM provider_type
    JOIN type_benchmark USING (encounter_type)
    GROUP BY provider_type.provider_id
)
SELECT
    provider_id,
    claim_count,
    denied_count,
    claim_count < 30 AS fewer_than_30_claims,
    round(100.0 * denied_count / NULLIF(claim_count, 0), 2) AS observed_denial_pct,
    round(100.0 * benchmark_denial_count / NULLIF(claim_count, 0), 2) AS mix_benchmark_denial_pct,
    round(
        100.0 * (denied_count - benchmark_denial_count) / NULLIF(claim_count, 0), 2
    ) AS difference_percentage_points
FROM providers
ORDER BY claim_count DESC, provider_id;

-- Q06. How many claims are pending by payer and submission month?
-- Grain and denominator: one row per observed payer/submission-month group; all claims in that group.
-- Limitation: pending describes an observed status. The source has no due-date or observation cutoff.
SELECT
    date_trunc('month', submitted_at)::date AS submission_month,
    payer,
    count(*) AS claim_count,
    count(*) FILTER (WHERE status = 'pending') AS pending_count
FROM rcm360.claim_analytics
GROUP BY submission_month, payer
ORDER BY submission_month, payer;
