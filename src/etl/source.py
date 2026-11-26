"""Validate and parse the approved Misata snapshot without modifying it."""

import csv
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZipFile

SOURCE_ARCHIVE = "hospital-encounters-claims.zip"
SOURCE_SHA256 = "ce8d4d2053ebe0bb1d89e6d5de0d370bbc19d04bcc122c351832916b6591897a"

# CSV column order and foreign-key load order.
TABLE_COLUMNS = {
    "patients": (
        "patient_id", "full_name", "sex", "date_of_birth", "insurance", "city",
        "region", "country", "street_address", "postal_code", "phone",
        "registered_at", "encounter_count",
    ),
    "providers": ("provider_id", "provider_name", "specialty", "npi", "facility"),
    "encounters": (
        "encounter_id", "patient_id", "provider_id", "patient_sex", "insurance",
        "admit_at", "encounter_type", "los_hours", "discharge_at",
        "diagnosis_count", "total_billed",
    ),
    "diagnoses": (
        "diagnosis_id", "encounter_id", "patient_id", "patient_sex",
        "diagnosed_at", "icd10_code", "description", "category",
    ),
    "prescriptions": (
        "prescription_id", "diagnosis_id", "encounter_id", "patient_id",
        "category", "prescribed_at", "drug", "dose", "dose_unit", "frequency",
        "days_supply",
    ),
    "lab_results": (
        "lab_id", "encounter_id", "patient_id", "collected_at", "analyte",
        "unit", "value", "ref_low", "ref_high", "flag",
    ),
    "claims": (
        "claim_id", "encounter_id", "patient_id", "payer", "encounter_type",
        "submitted_at", "billed_amount", "allowed_ratio", "allowed_amount",
        "status", "paid_at", "denied_at", "paid_amount", "patient_responsibility",
        "denial_reason",
    ),
}

NULLABLE_FIELDS = {"phone", "paid_at", "denied_at", "denial_reason"}
INTEGER_FIELDS = {"encounter_count", "diagnosis_count", "days_supply"}
DECIMAL_SCALES = {
    "billed_amount": 2,
    "allowed_amount": 2,
    "paid_amount": 2,
    "patient_responsibility": 2,
    "total_billed": 2,
    "allowed_ratio": 4,
    "los_hours": 4,
    "dose": 1,
    "value": 2,
    "ref_low": 1,
    "ref_high": 1,
}

SourceCell = str | int | Decimal | date | datetime | None
SourceRow = tuple[SourceCell, ...]


def parse_cell(field: str, value: str) -> SourceCell:
    if value == "" and field in NULLABLE_FIELDS:
        return None
    if not value.strip():
        raise ValueError("Expected a populated value")
    if field in DECIMAL_SCALES:
        amount = Decimal(value)
        if not amount.is_finite() or amount.as_tuple().exponent < -DECIMAL_SCALES[field]:
            raise ValueError("Expected a finite decimal at the source scale")
        return amount
    if field in INTEGER_FIELDS:
        return int(value)
    if field == "date_of_birth":
        return date.fromisoformat(value)
    if field.endswith("_at"):
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is not None or timestamp.isoformat(" ", "seconds") != value:
            raise ValueError("Expected a timezone-free timestamp at second precision")
        return timestamp
    return value


def parse_csv(table: str, csv_text: str) -> list[SourceRow]:
    """Map validated headers to typed rows in source field order."""
    columns = TABLE_COLUMNS[table]
    reader = csv.reader(StringIO(csv_text, newline=""), strict=True)
    if tuple(next(reader, [])) != columns:
        raise ValueError(f"{table}.csv header differs from the source schema")

    rows = []
    for record_number, values in enumerate(reader, start=2):
        if len(values) != len(columns):
            raise ValueError(f"{table}.csv record {record_number} has the wrong field count")
        row = []
        for field, value in zip(columns, values, strict=True):
            try:
                row.append(parse_cell(field, value))
            except (ValueError, ArithmeticError) as exc:
                raise ValueError(f"{table}.csv record {record_number} has invalid {field}") from exc
        rows.append(tuple(row))
    return rows


def read_snapshot(raw_dir: Path) -> dict[str, list[SourceRow]]:
    """Confirm the archive digest and extracted bytes before parsing."""
    archive_bytes = (raw_dir / SOURCE_ARCHIVE).read_bytes()
    if sha256(archive_bytes).hexdigest() != SOURCE_SHA256:
        raise ValueError(f"{SOURCE_ARCHIVE} does not match the approved Misata archive SHA-256")

    snapshot = {}
    with ZipFile(BytesIO(archive_bytes)) as archive:
        for table in TABLE_COLUMNS:
            name = f"{table}.csv"
            member = archive.read(name)
            if (raw_dir / name).read_bytes() != member:
                raise ValueError(f"{name} differs from the approved archive member")
            snapshot[table] = parse_csv(table, member.decode("utf-8"))
    return snapshot
