"""Validate privacy-minimized exports and calculate claim-grain measures."""

import csv
import io
import json
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, fields
from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING
from pathlib import Path


SCHEMA_VERSION = "1.0.0"
STATUSES = ("paid", "denied", "pending")
FILTER_FIELDS = ("payer", "provider_id", "status", "encounter_type")
DRILL_FIELDS = (*FILTER_FIELDS, "denial_reason")
SORTS = {
    "Newest submission": "submitted_at",
    "Highest billed": "billed_amount",
    "Highest payer payment": "payer_paid_amount",
}
ZERO = Decimal("0")
DECIMAL_TEXT = re.compile(r"-?\d+(?:\.\d+)?", re.ASCII)


class ExportError(ValueError):
    """The input is missing or does not satisfy the dashboard export contract."""


@dataclass(frozen=True)
class Claim:
    claim_id: str
    submitted_at: datetime
    payer: str
    encounter_type: str
    provider_id: str
    status: str
    billed_amount: Decimal
    allowed_amount: Decimal
    payer_paid_amount: Decimal
    patient_responsibility: Decimal
    allowed_ratio: Decimal
    paid_at: datetime | None
    denied_at: datetime | None
    denial_reason: str | None
    submission_to_payment_days: Decimal | None


CLAIM_FIELDS = tuple(field.name for field in fields(Claim))
AMOUNT_FIELDS = (
    "billed_amount", "allowed_amount", "payer_paid_amount", "patient_responsibility"
)


def required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExportError(f"{label} must contain text.")
    return value


def timestamp(value: object, label: str) -> datetime:
    value = required_text(value, label)
    try:
        if len(value) <= 10:
            raise ValueError
        return datetime.fromisoformat(value)
    except ValueError:
        raise ExportError(f"{label} must be an ISO 8601 timestamp.") from None


def decimal_text(value: object, label: str) -> Decimal:
    if not isinstance(value, str) or not DECIMAL_TEXT.fullmatch(value):
        raise ExportError(f"{label} must be a finite decimal string.")
    return Decimal(value)


def parse_claim(record: object) -> Claim:
    if not isinstance(record, dict) or record.keys() != set(CLAIM_FIELDS):
        raise ExportError("Claim record fields do not match the public contract.")

    values = {key: required_text(record[key], key) for key in ("claim_id", *FILTER_FIELDS)}
    if values["status"] not in STATUSES:
        raise ExportError("Claim status must be paid, denied, or pending.")

    values["submitted_at"] = timestamp(record["submitted_at"], "submitted_at")
    for key in ("paid_at", "denied_at"):
        values[key] = None if record[key] is None else timestamp(record[key], key)
    for key in (*AMOUNT_FIELDS, "allowed_ratio"):
        values[key] = decimal_text(record[key], key)
    for key, parse in (("submission_to_payment_days", decimal_text), ("denial_reason", required_text)):
        values[key] = None if record[key] is None else parse(record[key], key)
    if (values["submission_to_payment_days"] is not None) != (values["status"] == "paid"):
        raise ExportError("Days to payment must be present for paid claims only.")
    return Claim(**values)


def read_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as stream:
            payload = json.load(stream)
    except FileNotFoundError:
        raise ExportError(f"The {path.name} export is missing.") from None
    except (OSError, UnicodeError, ValueError):
        raise ExportError(f"The {path.name} export could not be read as JSON.") from None
    if not isinstance(payload, dict):
        raise ExportError(f"The {path.name} export must contain a JSON object.")
    return payload


def nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ExportError(f"{label} must be a nonnegative integer.")
    return value


@dataclass(frozen=True)
class Metadata:
    dataset_name: str
    source_sha256: str
    source_license: str
    generated_at: datetime
    record_count: int
    reconciled_with_postgres: bool


def parse_metadata(payload: dict, grain: str) -> Metadata:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("schema_version") != SCHEMA_VERSION:
        raise ExportError(f"The export must use schema version {SCHEMA_VERSION}.")
    if metadata.get("record_grain") != grain:
        raise ExportError("The export record grain does not match the contract.")
    sha256 = required_text(metadata.get("source_sha256"), "source_sha256")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
        raise ExportError("The source SHA-256 must be a hexadecimal digest.")
    reconciled = metadata.get("reconciled_with_postgres")
    if type(reconciled) is not bool:
        raise ExportError("PostgreSQL reconciliation status must be a boolean.")
    generated_at = timestamp(metadata.get("generated_at"), "generated_at")
    if generated_at.utcoffset() is None or generated_at.utcoffset().total_seconds() != 0:
        raise ExportError("The export timestamp must be in UTC.")
    return Metadata(
        required_text(metadata.get("dataset_name"), "dataset_name"),
        sha256.lower(), required_text(metadata.get("source_license"), "source_license"),
        generated_at, nonnegative_int(metadata.get("record_count"), "record_count"), reconciled,
    )


def parse_claims(payload: dict) -> tuple[Metadata, tuple[Claim, ...]]:
    metadata = parse_metadata(payload, "one row per claim")
    if not metadata.reconciled_with_postgres:
        raise ExportError("The claims export is awaiting PostgreSQL reconciliation.")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ExportError("The claims export must contain a records array.")
    if len(records) != metadata.record_count:
        raise ExportError("The claims export count does not match its metadata.")
    claims = tuple(parse_claim(record) for record in records)
    if len({claim.claim_id for claim in claims}) != len(claims):
        raise ExportError("The claims export contains duplicate claim keys.")
    if len({claim.submitted_at.tzinfo is None for claim in claims}) > 1:
        raise ExportError("Claim submission timestamps must use a consistent timezone convention.")
    return metadata, claims


@dataclass(frozen=True)
class ClaimFilters:
    start: date
    end: date
    payer: str | None = None
    provider_id: str | None = None
    status: str | None = None
    encounter_type: str | None = None


def filter_claims(
    claims: Iterable[Claim], filters: ClaimFilters, drill: tuple[str, str] | None = None
) -> tuple[Claim, ...]:
    active = [(key, getattr(filters, key)) for key in FILTER_FIELDS if getattr(filters, key)]
    if drill is not None:
        if drill[0] not in DRILL_FIELDS:
            raise ValueError("Unsupported drill field")
        active.append(drill)
    return tuple(
        claim for claim in claims
        if filters.start <= claim.submitted_at.date() <= filters.end
        and all(getattr(claim, key) == value for key, value in active)
    )


def ratio(numerator: int | Decimal, denominator: int | Decimal) -> Decimal | None:
    return Decimal(numerator) / Decimal(denominator) if denominator else None


def denial_reason_pareto(claims: Iterable[Claim]) -> list[tuple[str, int, Decimal]]:
    counts = Counter(claim.denial_reason for claim in claims if claim.status == "denied" and claim.denial_reason)
    total = sum(counts.values())
    cumulative = 0
    rows = []
    for reason, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        cumulative += count
        rows.append((reason, count, Decimal(cumulative) / total))
    return rows


@dataclass(frozen=True)
class Metrics:
    count: int
    denied: int
    pending: int
    billed: Decimal
    allowed: Decimal
    payer_paid: Decimal
    responsibility: Decimal
    denied_billed: Decimal
    average_days: Decimal | None

    @property
    def denial_rate(self) -> Decimal | None:
        return ratio(self.denied, self.count)


def summarize(claims: tuple[Claim, ...] | list[Claim]) -> Metrics:
    denied = [claim for claim in claims if claim.status == "denied"]
    days = [claim.submission_to_payment_days for claim in claims if claim.submission_to_payment_days is not None]
    totals = [sum((getattr(claim, key) for claim in claims), ZERO) for key in AMOUNT_FIELDS]
    return Metrics(
        len(claims), len(denied), sum(claim.status == "pending" for claim in claims),
        *totals, sum((claim.billed_amount for claim in denied), ZERO),
        ratio(sum(days, ZERO), len(days)),
    )


def group_by(claims: Iterable[Claim], key: str) -> dict:
    groups = {}
    for claim in claims:
        value = (
            claim.submitted_at.date().replace(day=1)
            if key == "month" else getattr(claim, key)
        )
        if value is not None:
            groups.setdefault(value, []).append(claim)
    return groups


def discrete_percentile(values: Iterable[Decimal], percentile: Decimal) -> Decimal | None:
    """Return PostgreSQL percentile_disc's observed value using exact decimal ranks."""
    if not ZERO <= percentile <= Decimal("1"):
        raise ValueError("Percentile must be between zero and one.")
    ordered = sorted(values)
    if not ordered:
        return None
    rank = int((Decimal(len(ordered)) * percentile).to_integral_value(rounding=ROUND_CEILING))
    return ordered[max(0, rank - 1)]


def payment_timing_by_payer(
    claims: Iterable[Claim],
) -> list[tuple[str, int, Decimal, Decimal]]:
    """Summarize discrete P50/P90 submission-to-payment days for paid claims by payer."""
    summaries = []
    for payer, rows in group_by(claims, "payer").items():
        durations = [
            claim.submission_to_payment_days for claim in rows
            if claim.status == "paid" and claim.submission_to_payment_days is not None
        ]
        if not durations:
            continue
        summaries.append((
            payer, len(durations),
            discrete_percentile(durations, Decimal("0.50")),
            discrete_percentile(durations, Decimal("0.90")),
        ))
    return sorted(summaries, key=lambda row: row[0])


def search_claims(claims: Iterable[Claim], query: str, sort_by: str) -> list[Claim]:
    term = query.strip().casefold()
    search_fields = ("claim_id", "payer", "provider_id", "status", "denial_reason", "encounter_type")
    matches = [
        claim for claim in claims
        if not term or any(term in (getattr(claim, key) or "").casefold() for key in search_fields)
    ]
    return sorted(matches, key=lambda claim: (getattr(claim, SORTS[sort_by]), claim.claim_id), reverse=True)


def claims_csv(claims: Iterable[Claim]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(CLAIM_FIELDS)
    for claim in claims:
        row = (getattr(claim, key) for key in CLAIM_FIELDS)
        writer.writerow(value.isoformat() if isinstance(value, datetime) else value for value in row)
    return buffer.getvalue()
