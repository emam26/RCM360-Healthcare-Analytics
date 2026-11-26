CREATE SCHEMA IF NOT EXISTS rcm360;

-- One row per synthetic patient.
CREATE TABLE IF NOT EXISTS rcm360.patients (
    patient_id text PRIMARY KEY,
    full_name text NOT NULL,
    sex text NOT NULL,
    date_of_birth date NOT NULL,
    insurance text NOT NULL,
    city text NOT NULL,
    region text NOT NULL,
    country text NOT NULL,
    street_address text NOT NULL,
    postal_code text NOT NULL,
    phone text,
    registered_at timestamp without time zone NOT NULL,
    encounter_count integer NOT NULL CHECK (encounter_count >= 0),
    CONSTRAINT patients_registration_order CHECK (registered_at::date >= date_of_birth)
);

-- One row per synthetic provider.
CREATE TABLE IF NOT EXISTS rcm360.providers (
    provider_id text PRIMARY KEY,
    provider_name text NOT NULL,
    specialty text NOT NULL,
    npi text NOT NULL UNIQUE,
    facility text NOT NULL
);

-- One row per encounter, with one patient and one provider.
CREATE TABLE IF NOT EXISTS rcm360.encounters (
    encounter_id text PRIMARY KEY,
    patient_id text NOT NULL REFERENCES rcm360.patients (patient_id),
    provider_id text NOT NULL REFERENCES rcm360.providers (provider_id),
    patient_sex text NOT NULL,
    insurance text NOT NULL,
    admit_at timestamp without time zone NOT NULL,
    encounter_type text NOT NULL CHECK (encounter_type IN ('emergency', 'inpatient', 'outpatient')),
    los_hours numeric(12, 4) NOT NULL CHECK (los_hours > 0 AND los_hours <> 'NaN'::numeric),
    discharge_at timestamp without time zone NOT NULL,
    diagnosis_count integer NOT NULL CHECK (diagnosis_count >= 0),
    total_billed numeric(14, 2) NOT NULL CHECK (total_billed >= 0 AND total_billed <> 'NaN'::numeric),
    CONSTRAINT encounters_discharge_order CHECK (discharge_at > admit_at)
);

-- One row per diagnosis occurrence. A code can recur within an encounter.
CREATE TABLE IF NOT EXISTS rcm360.diagnoses (
    diagnosis_id text PRIMARY KEY,
    encounter_id text NOT NULL REFERENCES rcm360.encounters (encounter_id),
    patient_id text NOT NULL REFERENCES rcm360.patients (patient_id),
    patient_sex text NOT NULL,
    diagnosed_at timestamp without time zone NOT NULL,
    icd10_code text NOT NULL,
    description text NOT NULL,
    category text NOT NULL
);

-- One row per prescription linked to a diagnosis occurrence.
CREATE TABLE IF NOT EXISTS rcm360.prescriptions (
    prescription_id text PRIMARY KEY,
    diagnosis_id text NOT NULL REFERENCES rcm360.diagnoses (diagnosis_id),
    encounter_id text NOT NULL REFERENCES rcm360.encounters (encounter_id),
    patient_id text NOT NULL REFERENCES rcm360.patients (patient_id),
    category text NOT NULL,
    prescribed_at timestamp without time zone NOT NULL,
    drug text NOT NULL,
    dose numeric(12, 1) NOT NULL CHECK (dose > 0 AND dose <> 'NaN'::numeric),
    dose_unit text NOT NULL,
    frequency text NOT NULL,
    days_supply integer NOT NULL CHECK (days_supply > 0)
);

-- One row per analyte result, in the stated unit and reference range.
CREATE TABLE IF NOT EXISTS rcm360.lab_results (
    lab_id text PRIMARY KEY,
    encounter_id text NOT NULL REFERENCES rcm360.encounters (encounter_id),
    patient_id text NOT NULL REFERENCES rcm360.patients (patient_id),
    collected_at timestamp without time zone NOT NULL,
    analyte text NOT NULL,
    unit text NOT NULL,
    value numeric(12, 2) NOT NULL CHECK (value <> 'NaN'::numeric),
    ref_low numeric(12, 1) NOT NULL,
    ref_high numeric(12, 1) NOT NULL,
    flag text NOT NULL CHECK (flag IN ('high', 'low', 'normal')),
    CONSTRAINT lab_results_reference_range CHECK (ref_low <= ref_high AND ref_high <> 'NaN'::numeric)
);

-- One row per claim. Every claim follows one encounter, and each encounter can
-- have at most one claim. In this snapshot, each encounter has exactly one.
CREATE TABLE IF NOT EXISTS rcm360.claims (
    claim_id text PRIMARY KEY,
    encounter_id text NOT NULL UNIQUE REFERENCES rcm360.encounters (encounter_id),
    patient_id text NOT NULL REFERENCES rcm360.patients (patient_id),
    payer text NOT NULL,
    encounter_type text NOT NULL CHECK (encounter_type IN ('emergency', 'inpatient', 'outpatient')),
    submitted_at timestamp without time zone NOT NULL,
    billed_amount numeric(14, 2) NOT NULL,
    allowed_ratio numeric(5, 4) NOT NULL CHECK (allowed_ratio BETWEEN 0 AND 1),
    allowed_amount numeric(14, 2) NOT NULL,
    status text NOT NULL CHECK (status IN ('paid', 'denied', 'pending')),
    paid_at timestamp without time zone,
    denied_at timestamp without time zone,
    paid_amount numeric(14, 2) NOT NULL,
    patient_responsibility numeric(14, 2) NOT NULL,
    denial_reason text,
    CONSTRAINT claims_amount_order CHECK (
        0 <= paid_amount
        AND paid_amount <= allowed_amount
        AND allowed_amount <= billed_amount
        AND billed_amount <> 'NaN'::numeric
        AND patient_responsibility BETWEEN 0 AND billed_amount
    ),
    CONSTRAINT claims_status_fields CHECK (
        (status = 'paid') = (paid_at IS NOT NULL)
        AND (status = 'denied') = (denied_at IS NOT NULL)
        AND (status = 'denied') = (denial_reason IS NOT NULL)
        AND (denial_reason IS NULL OR btrim(denial_reason) <> '')
    ),
    CONSTRAINT claims_outcome_order CHECK (
        (paid_at IS NULL OR paid_at >= submitted_at)
        AND (denied_at IS NULL OR denied_at >= submitted_at)
    )
);

-- Foreign-key joins and claim cohort filters.
CREATE INDEX IF NOT EXISTS encounters_patient_idx ON rcm360.encounters (patient_id);
CREATE INDEX IF NOT EXISTS encounters_provider_idx ON rcm360.encounters (provider_id);
CREATE INDEX IF NOT EXISTS diagnoses_encounter_idx ON rcm360.diagnoses (encounter_id);
CREATE INDEX IF NOT EXISTS diagnoses_patient_idx ON rcm360.diagnoses (patient_id);
CREATE INDEX IF NOT EXISTS prescriptions_diagnosis_idx ON rcm360.prescriptions (diagnosis_id);
CREATE INDEX IF NOT EXISTS prescriptions_encounter_idx ON rcm360.prescriptions (encounter_id);
CREATE INDEX IF NOT EXISTS prescriptions_patient_idx ON rcm360.prescriptions (patient_id);
CREATE INDEX IF NOT EXISTS lab_results_encounter_idx ON rcm360.lab_results (encounter_id);
CREATE INDEX IF NOT EXISTS lab_results_patient_idx ON rcm360.lab_results (patient_id);
CREATE INDEX IF NOT EXISTS claims_patient_idx ON rcm360.claims (patient_id);
CREATE INDEX IF NOT EXISTS claims_submitted_idx ON rcm360.claims (submitted_at);
CREATE INDEX IF NOT EXISTS claims_payer_status_idx ON rcm360.claims (payer, status);
