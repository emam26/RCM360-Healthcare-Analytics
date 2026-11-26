-- A claim's unique encounter supplies one provider ID. The join preserves
-- claim grain; clinical child tables require pre-aggregation before joining.
CREATE OR REPLACE VIEW rcm360.claim_analytics AS
SELECT
    claims.claim_id,
    claims.encounter_id,
    claims.submitted_at,
    claims.payer,
    claims.encounter_type,
    encounters.provider_id,
    claims.status,
    claims.billed_amount,
    claims.allowed_amount,
    claims.paid_amount AS payer_paid_amount,
    claims.patient_responsibility,
    claims.allowed_ratio,
    claims.paid_at,
    claims.denied_at,
    claims.denial_reason,
    CASE
        WHEN claims.status = 'paid' THEN round(
            extract(epoch FROM (claims.paid_at - claims.submitted_at))::numeric / 86400,
            6
        )
    END AS submission_to_payment_days
FROM rcm360.claims
JOIN rcm360.encounters USING (encounter_id);
