"""Compare the claim view and source table with the pinned source records."""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.engine import Connection

from dashboard.model import AMOUNT_FIELDS, CLAIM_FIELDS
from src.etl.source import TABLE_COLUMNS, SourceRow

DECIMAL_FIELDS = (*AMOUNT_FIELDS, "allowed_ratio", "submission_to_payment_days")
RECONCILIATION_FIELDS = ("row_count", "claim_count", "encounter_count", *AMOUNT_FIELDS)
RECONCILIATION_SQL = """
WITH source_and_view AS (
    SELECT
        'base' AS relation,
        claim_id, encounter_id, status, billed_amount, allowed_amount,
        paid_amount AS payer_paid_amount, patient_responsibility
    FROM rcm360.claims
    UNION ALL
    SELECT
        'view' AS relation,
        claim_id, encounter_id, status, billed_amount, allowed_amount,
        payer_paid_amount, patient_responsibility
    FROM rcm360.claim_analytics
)
SELECT
    relation,
    status,
    count(*) AS row_count,
    count(DISTINCT claim_id) AS claim_count,
    count(DISTINCT encounter_id) AS encounter_count,
    sum(billed_amount) AS billed_amount,
    sum(allowed_amount) AS allowed_amount,
    sum(payer_paid_amount) AS payer_paid_amount,
    sum(patient_responsibility) AS patient_responsibility
FROM source_and_view
GROUP BY GROUPING SETS ((relation), (relation, status))
"""
CLAIMS_SQL = (
    f"SELECT {', '.join(CLAIM_FIELDS)}, encounter_id "
    'FROM rcm360.claim_analytics ORDER BY claim_id COLLATE "C"'
)


def source_claims(snapshot: dict[str, list[SourceRow]]) -> dict[str, dict]:
    provider_index = TABLE_COLUMNS["encounters"].index("provider_id")
    encounters = {
        row[0]: row[provider_index]
        for row in snapshot["encounters"]
    }
    expected = {}
    encounter_ids = set()
    for row in snapshot["claims"]:
        claim = dict(zip(TABLE_COLUMNS["claims"], row, strict=True))
        encounter_id = claim["encounter_id"]
        claim["provider_id"] = encounters[encounter_id]
        claim["payer_paid_amount"] = claim["paid_amount"]
        duration = None
        if claim["status"] == "paid":
            elapsed = claim["paid_at"] - claim["submitted_at"]
            # The approved source timestamps have second precision.
            elapsed_seconds = elapsed.days * 86400 + elapsed.seconds
            duration = (Decimal(elapsed_seconds) / 86400).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            )
        claim["submission_to_payment_days"] = duration
        expected[claim["claim_id"]] = {field: claim[field] for field in (*CLAIM_FIELDS, "encounter_id")}
        encounter_ids.add(encounter_id)

    if (
        not expected
        or len(expected) != len(snapshot["claims"])
        or len(encounter_ids) != len(expected)
        or encounter_ids != encounters.keys()
    ):
        raise ValueError("The source must contain unique claim and encounter links at claim grain")
    return expected


def _expected_totals(source: dict[str, dict]) -> dict[str | None, tuple]:
    groups = defaultdict(list)
    for claim in source.values():
        groups[None].append(claim)
        groups[claim["status"]].append(claim)
    return {
        status: (
            len(claims),
            len(claims),
            len(claims),
            *(sum((claim[field] for claim in claims), Decimal(0)) for field in AMOUNT_FIELDS),
        )
        for status, claims in groups.items()
    }


def reconcile_claims(connection: Connection, expected: dict[str, dict]) -> list[dict]:
    aggregates = _expected_totals(expected)
    expected_groups = {(relation, status) for relation in ("base", "view") for status in aggregates}
    rows = connection.exec_driver_sql(RECONCILIATION_SQL).mappings().all()
    groups = {(row["relation"], row["status"]) for row in rows}
    if len(rows) != len(expected_groups) or groups != expected_groups:
        raise ValueError("PostgreSQL claim reconciliation groups differ from the pinned source")
    for row in rows:
        if (
            any(not isinstance(row[field], Decimal) for field in AMOUNT_FIELDS)
            or tuple(row[field] for field in RECONCILIATION_FIELDS) != aggregates[row["status"]]
        ):
            scope = row["status"] or "all statuses"
            raise ValueError(
                f"PostgreSQL {row['relation']} claim counts or exact sums differ from the source for {scope}"
            )

    claims = connection.exec_driver_sql(CLAIMS_SQL).mappings().all()
    if len(claims) != len(expected) or {row["claim_id"] for row in claims} != expected.keys():
        raise ValueError("The PostgreSQL claim view does not match the pinned source claim grain")
    records = []
    for row in claims:
        if any(
            not isinstance(row[field], Decimal)
            for field in DECIMAL_FIELDS
            if field != "submission_to_payment_days" or row[field] is not None
        ) or dict(row) != expected[row["claim_id"]]:
            raise ValueError("A PostgreSQL claim view record differs from the pinned source")
        records.append({field: row[field] for field in CLAIM_FIELDS})
    return records
