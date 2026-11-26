"""Load the approved snapshot with python -m src.etl.load_postgres."""

import argparse
import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql

from src.etl.source import SOURCE_SHA256, TABLE_COLUMNS, SourceRow, read_snapshot

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = ROOT / "sql" / "schema" / "001_source_tables.sql"
VIEW_SQL = ROOT / "sql" / "views" / "001_claim_analytics.sql"


def load_snapshot(cursor: psycopg.Cursor, snapshot: dict[str, list[SourceRow]]) -> list[str]:
    """Load empty tables and verify existing rows in the caller's transaction."""
    # Serialize setup and concurrent loader runs. Table locks also prevent
    # independent writes between the snapshot check and the final commit.
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext('rcm360.source_snapshot'))")
    cursor.execute(SCHEMA_SQL.read_text(encoding="utf-8"), prepare=False)
    tables = {table: sql.Identifier("rcm360", table) for table in TABLE_COLUMNS}
    cursor.execute(
        sql.SQL("LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE").format(
            sql.SQL(", ").join(tables.values())
        )
    )

    empty_tables = []
    for table, fields in TABLE_COLUMNS.items():
        columns = sql.SQL(", ").join(map(sql.Identifier, fields))
        select = sql.SQL("SELECT {} FROM {}").format(columns, tables[table])
        existing = cursor.execute(select).fetchall()
        expected = snapshot[table]
        if not existing:
            empty_tables.append(table)
        elif len(existing) != len(expected) or set(existing) != set(expected):
            raise ValueError(f"Existing rcm360.{table} rows differ from the approved snapshot")

    for table in empty_tables:
        columns = sql.SQL(", ").join(map(sql.Identifier, TABLE_COLUMNS[table]))
        statement = sql.SQL("COPY {} ({}) FROM STDIN").format(tables[table], columns)
        with cursor.copy(statement) as copy:
            for row in snapshot[table]:
                copy.write_row(row)

        select = sql.SQL("SELECT {} FROM {}").format(columns, tables[table])
        loaded = cursor.execute(select).fetchall()
        expected = snapshot[table]
        if len(loaded) != len(expected) or set(loaded) != set(expected):
            raise ValueError(f"Loaded rcm360.{table} rows differ from the approved snapshot")

    cursor.execute(VIEW_SQL.read_text(encoding="utf-8"), prepare=False)
    return empty_tables


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "raw")
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        parser.error("Set DATABASE_URL to a PostgreSQL connection string")

    try:
        snapshot = read_snapshot(args.raw_dir)
        with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
            loaded = load_snapshot(cursor, snapshot)
    except (OSError, ValueError) as exc:
        print(f"Snapshot load failed. {exc}", file=sys.stderr)
        return 1
    except psycopg.Error as exc:
        detail = f" (SQLSTATE {exc.sqlstate})" if exc.sqlstate else ""
        print(f"PostgreSQL snapshot load failed. {type(exc).__name__}{detail}", file=sys.stderr)
        return 1

    print(f"Verified source SHA-256 {SOURCE_SHA256}")
    for table, rows in snapshot.items():
        action = "Loaded" if table in loaded else "Matched"
        print(f"{action} rcm360.{table} ({len(rows):,} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
