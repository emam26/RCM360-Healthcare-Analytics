"""Publish the dashboard JSON pair after verifying the PostgreSQL snapshot."""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkdtemp

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.pool import NullPool

from dashboard.model import SCHEMA_VERSION, parse_claims
from dashboard.quality import parse_quality
from src.etl.load_postgres import verify_loaded_snapshot
from src.etl.source import SOURCE_SHA256, read_snapshot
from src.exports.reconcile import DECIMAL_FIELDS, reconcile_claims, source_claims
from src.validation.audit import public_results, run_quality

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "dashboard" / "data"
CLAIM_GRAIN = "one row per claim"
QUALITY_GRAIN = "validation run across seven source tables"
EXPORT_LOCK_SQL = "SELECT pg_advisory_lock(hashtext('rcm360.dashboard_exports'))"


def _postgres_url(database_url: str) -> URL:
    try:
        url = make_url(database_url)
    except ArgumentError:
        raise ValueError("DATABASE_URL must be a valid PostgreSQL URL") from None
    if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
        raise ValueError("DATABASE_URL must use PostgreSQL with the Psycopg driver")
    return url.set(drivername="postgresql+psycopg")


def build_payloads(records: list[dict], audit: dict, source_count: int) -> tuple[dict, dict]:
    quality = public_results(audit)
    for scope in quality.values():
        if scope["summary"]["source_rows"] != source_count:
            raise ValueError("PostgreSQL audit source-row count differs from the pinned source")

    claims = []
    for row in records:
        record = dict(row)
        for field in DECIMAL_FIELDS:
            if row[field] is not None:
                record[field] = format(row[field], "f")
        for field in ("submitted_at", "paid_at", "denied_at"):
            if row[field] is not None:
                record[field] = row[field].isoformat()
        claims.append(record)

    provenance = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_name": "Hospital encounters, diagnoses and claims",
        "source_sha256": SOURCE_SHA256,
        "source_license": "CC0",
        "reconciled_with_postgres": True,
    }
    return (
        {
            "metadata": provenance | {"record_count": len(claims), "record_grain": CLAIM_GRAIN},
            "records": claims,
        },
        {
            "metadata": provenance | {"record_count": source_count, "record_grain": QUALITY_GRAIN},
            **quality,
        },
    )


def validate_payloads(claims_payload: dict, quality_payload: dict) -> None:
    claim_metadata, claims = parse_claims(claims_payload)
    quality = parse_quality(quality_payload, claim_metadata, claims)
    claim_provenance = {
        key: value for key, value in claims_payload["metadata"].items()
        if key not in {"record_count", "record_grain"}
    }
    quality_provenance = {
        key: value for key, value in quality_payload["metadata"].items()
        if key not in {"record_count", "record_grain"}
    }
    if claim_provenance != quality_provenance or claim_metadata.source_sha256 != SOURCE_SHA256:
        raise ValueError("The export files must share the pinned source provenance")
    if any(issue["record_ref"] is None for issue in quality.original_issues):
        raise ValueError("The quality export contains a reference outside the verified claims")


def write_payloads(output_dir: Path, claims_payload: dict, quality_payload: dict) -> None:
    validate_payloads(claims_payload, quality_payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(mkdtemp(prefix=".rcm360-export-", dir=output_dir))
    payloads = {"claims.json": claims_payload, "quality.json": quality_payload}
    installed = []
    keep_backups = False
    try:
        for name, payload in payloads.items():
            with (staging / name).open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, indent=2, ensure_ascii=False, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            target = output_dir / name
            if target.exists():
                shutil.copyfile(target, staging / f"previous-{name}")

        try:
            for name in payloads:
                os.replace(staging / name, output_dir / name)
                installed.append(name)
        except (OSError, KeyboardInterrupt):
            try:
                for name in reversed(installed):
                    backup = staging / f"previous-{name}"
                    if backup.exists():
                        os.replace(backup, output_dir / name)
                    else:
                        (output_dir / name).unlink()
            except OSError as restore_error:
                keep_backups = True
                raise OSError(
                    f"Could not restore the previous exports. Staged files remain in {staging}"
                ) from restore_error
            raise
    finally:
        if not keep_backups:
            for staged_file in staging.iterdir():
                staged_file.unlink()
            staging.rmdir()


def export_dashboard(database_url: str, raw_dir: Path, output_dir: Path) -> int:
    snapshot = read_snapshot(raw_dir)
    expected = source_claims(snapshot)
    source_count = sum(len(rows) for rows in snapshot.values())
    engine = create_engine(
        _postgres_url(database_url),
        isolation_level="REPEATABLE READ",
        poolclass=NullPool,
        hide_parameters=True,
    )
    try:
        with engine.connect() as connection:
            with connection.begin():
                # The session lock serializes export writers through file installation.
                # NullPool releases it when this connection closes.
                connection.exec_driver_sql(EXPORT_LOCK_SQL).close()
                records = reconcile_claims(connection, expected)
                with connection.connection.driver_connection.cursor() as cursor:
                    verify_loaded_snapshot(cursor, snapshot)
                    audit = run_quality(cursor)
            claims, quality = build_payloads(records, audit, source_count)
            write_payloads(output_dir, claims, quality)
    finally:
        engine.dispose()
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        parser.error("Set DATABASE_URL to a PostgreSQL connection string")

    try:
        claim_count = export_dashboard(database_url, args.raw_dir, args.output_dir)
    except (OSError, ValueError) as exc:
        print(f"Dashboard export failed. {exc}", file=sys.stderr)
        return 1
    except (SQLAlchemyError, psycopg.Error) as exc:
        print(f"PostgreSQL dashboard export failed. {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"Published claims.json and quality.json in {args.output_dir} with {claim_count:,} claims.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
