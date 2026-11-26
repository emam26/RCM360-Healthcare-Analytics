"""Audit rule definitions and injections for the verified source."""

import re
from dataclasses import dataclass
from pathlib import Path

from psycopg import sql

from src.etl.source import TABLE_COLUMNS

SQL_DIR = Path(__file__).resolve().parents[2] / "sql" / "quality_checks"
PRIMARY_KEYS = {table: columns[0] for table, columns in TABLE_COLUMNS.items()}
FOREIGN_KEYS = (
    ("encounters", "patient_id", "patients"),
    ("encounters", "provider_id", "providers"),
    ("diagnoses", "encounter_id", "encounters"),
    ("diagnoses", "patient_id", "patients"),
    ("prescriptions", "diagnosis_id", "diagnoses"),
    ("prescriptions", "encounter_id", "encounters"),
    ("prescriptions", "patient_id", "patients"),
    ("lab_results", "encounter_id", "encounters"),
    ("lab_results", "patient_id", "patients"),
    ("claims", "encounter_id", "encounters"),
    ("claims", "patient_id", "patients"),
)


@dataclass(frozen=True)
class Injection:
    statement: sql.Composable
    expected_changes: int = 1
    additional_rows: frozenset[int] = frozenset()


@dataclass(frozen=True)
class Rule:
    rule_id: str
    source_table: str
    category: str
    severity: str
    recommended_action: str
    evaluation: sql.Composable
    injection: Injection


def audit_table(table: str) -> sql.Identifier:
    return sql.Identifier("pg_temp", f"qa_{table}")


def replace_first(table: str, assignment: str, eligible: str = "true") -> Injection:
    return Injection(
        sql.SQL(
            """
            UPDATE {source} AS target
            SET {assignment}
            WHERE audit_row_id = (
                SELECT audit_row_id FROM {source} WHERE {eligible}
                ORDER BY audit_row_id LIMIT 1
            )
            RETURNING audit_row_id
            """
        ).format(
            source=audit_table(table),
            assignment=sql.SQL(assignment),
            eligible=sql.SQL(eligible),
        )
    )


def _primary_key_rules() -> list[Rule]:
    evaluation = sql.SQL((SQL_DIR / "primary_key.sql").read_text(encoding="utf-8"))
    # The first row is also expected to fail after the second row copies its key.
    inject = sql.SQL(
        """
        UPDATE {source}
        SET {key} = CASE audit_row_id
            WHEN 2 THEN (SELECT {key} FROM {source} WHERE audit_row_id = 1)
            WHEN 3 THEN NULL
            WHEN 4 THEN ' '
        END
        WHERE audit_row_id IN (2, 3, 4)
        RETURNING audit_row_id
        """
    )
    rules = []
    for table, field in PRIMARY_KEYS.items():
        tokens = {"source": audit_table(table), "key": sql.Identifier(field)}
        rules.append(
            Rule(
                f"PK_{table.upper()}", table, "primary_key", "critical",
                f"Verify {field} mapping and restore a populated, unique key.",
                evaluation.format(**tokens),
                Injection(inject.format(**tokens), expected_changes=3, additional_rows=frozenset({1})),
            )
        )
    return rules


def _foreign_key_rules() -> list[Rule]:
    evaluation = sql.SQL((SQL_DIR / "foreign_key.sql").read_text(encoding="utf-8"))
    inject = sql.SQL(
        """
        UPDATE {source}
        SET {child_key} = CASE audit_row_id WHEN 1 THEN '__rcm360_test_absent__' ELSE NULL END
        WHERE audit_row_id IN (1, 2)
        RETURNING audit_row_id
        """
    )
    rules = []
    for table, field, parent in FOREIGN_KEYS:
        source, child_key = audit_table(table), sql.Identifier(field)
        rules.append(
            Rule(
                f"FK_{table.upper()}_{field.upper()}", table, "foreign_key", "high",
                f"Check the {field} mapping against the corresponding {parent} source row.",
                evaluation.format(
                    source=source,
                    key=sql.Identifier(PRIMARY_KEYS[table]),
                    parent=audit_table(parent),
                    parent_key=sql.Identifier(PRIMARY_KEYS[parent]),
                    child_key=child_key,
                ),
                Injection(inject.format(source=source, child_key=child_key), expected_changes=2),
            )
        )
    return rules


def _domain_rules() -> list[Rule]:
    # Identities come from the SQL markers. Keep every evaluation paired with a case.
    source = (SQL_DIR / "domain_rules.sql").read_text(encoding="utf-8")
    lead, *sections = re.split(r"(?m)^-- rule ([A-Z_]+)\n", source)
    evaluations = {
        rule_id: sql.SQL(query.strip().removesuffix(";"))
        for rule_id, query in zip(sections[::2], sections[1::2], strict=True)
    }
    domain = (
        (
            "ENCOUNTER_PATIENT_AGREEMENT", "encounters", "relationship", "medium",
            "Compare the encounter's patient sex and insurance values with the linked patient.",
            replace_first("encounters", "insurance = CASE insurance WHEN 'other' THEN 'commercial' ELSE 'other' END"),
        ),
        (
            "CLAIM_ENCOUNTER_AGREEMENT", "claims", "relationship", "high",
            "Reconcile claim patient, payer, type, and billed fields with the linked encounter.",
            replace_first("claims", "payer = CASE payer WHEN 'other' THEN 'commercial' ELSE 'other' END"),
        ),
        (
            "PRESCRIPTION_DIAGNOSIS_AGREEMENT", "prescriptions", "relationship", "high",
            "Compare the linked diagnosis, patient, encounter, and category mappings.",
            replace_first("prescriptions", "category = '__rcm360_test_category__'"),
        ),
        (
            "ENCOUNTER_DISCHARGE_ORDER", "encounters", "chronology", "high",
            "Review source visit timestamps and confirm discharge follows admission.",
            replace_first("encounters", "discharge_at = admit_at - interval '1 second'"),
        ),
        (
            "CLAIM_SUBMISSION_ORDER", "claims", "chronology", "high",
            "Compare source submission time with the linked admission time.",
            replace_first(
                "claims",
                """submitted_at = (
                    SELECT admit_at - interval '1 second'
                    FROM pg_temp.qa_encounters
                    WHERE encounter_id = target.encounter_id
                )""",
            ),
        ),
        (
            "PRESCRIPTION_DIAGNOSIS_ORDER", "prescriptions", "chronology", "medium",
            "Review the prescription timestamp and the linked diagnosis timestamp.",
            replace_first(
                "prescriptions",
                """prescribed_at = (
                    SELECT diagnosed_at - interval '1 second'
                    FROM pg_temp.qa_diagnoses
                    WHERE diagnosis_id = target.diagnosis_id
                )""",
            ),
        ),
        (
            "CLAIM_OUTCOME_ORDER", "claims", "chronology", "high",
            "Check the record's payment or denial time against submission.",
            replace_first("claims", "paid_at = submitted_at - interval '1 second'", "status = 'paid'"),
        ),
        (
            "CLAIM_STATUS_DOMAIN", "claims", "status", "high",
            "Compare the source status with the approved paid, denied, and pending mappings.",
            replace_first("claims", "status = '__rcm360_test_status__'"),
        ),
        (
            "CLAIM_STATUS_FIELDS", "claims", "status", "high",
            "Check the outcome timestamps and denial reason required by the recorded status.",
            replace_first("claims", "denial_reason = NULL", "status = 'denied'"),
        ),
        (
            "CLAIM_AMOUNT_ORDER", "claims", "financial", "critical",
            "Verify the four exact source amounts and their documented bounds.",
            replace_first("claims", "paid_amount = allowed_amount + 0.01"),
        ),
        (
            "CLAIM_ALLOWED_RATIO", "claims", "financial", "medium",
            "Compare the source allowed amount and ratio against the half-cent residual tolerance.",
            replace_first(
                "claims",
                "allowed_ratio = CASE WHEN allowed_ratio >= 0.5 THEN 0 ELSE 1 END",
                "billed_amount > 0",
            ),
        ),
        (
            "CLAIM_STATUS_AMOUNTS", "claims", "financial", "high",
            "Check the status-dependent source amount identities before interpreting the record.",
            replace_first("claims", "patient_responsibility = 0.01", "status = 'pending'"),
        ),
        (
            "LAB_FLAG_AGREEMENT", "lab_results", "relationship", "medium",
            "Compare the result flag to the supplied value and reference interval.",
            replace_first("lab_results", "flag = CASE flag WHEN 'high' THEN 'low' ELSE 'high' END"),
        ),
        (
            "ENCOUNTER_CLAIM_COVERAGE", "encounters", "relationship", "high",
            "Compare the encounter's linked claims with the snapshot's one-claim grain.",
            Injection(
                sql.SQL(
                    """
                    WITH chosen AS (
                        SELECT e.audit_row_id AS encounter_row, c.audit_row_id AS claim_row
                        FROM pg_temp.qa_encounters AS e
                        JOIN pg_temp.qa_claims AS c USING (encounter_id)
                        ORDER BY e.audit_row_id, c.audit_row_id LIMIT 1
                    )
                    DELETE FROM pg_temp.qa_claims AS c USING chosen
                    WHERE c.audit_row_id = chosen.claim_row
                    RETURNING chosen.encounter_row
                    """
                )
            ),
        ),
    )
    if lead.strip() or set(evaluations) != {definition[0] for definition in domain}:
        raise ValueError("Quality rule SQL and rule definitions differ")
    return [
        Rule(rule_id, table, category, severity, action, evaluations[rule_id], injection)
        for rule_id, table, category, severity, action, injection in domain
    ]


def build_rules() -> list[Rule]:
    return _primary_key_rules() + _foreign_key_rules() + _domain_rules()
