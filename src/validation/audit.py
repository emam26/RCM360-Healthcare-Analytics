"""Audit the PostgreSQL snapshot and exercise the same rules on isolated cases."""

import json
import os
import sys
from dataclasses import dataclass
from decimal import Decimal

import psycopg
from psycopg import sql

from src.etl.source import TABLE_COLUMNS
from src.validation.rules import PRIMARY_KEYS, Rule, audit_table, build_rules


@dataclass(frozen=True)
class Evaluation:
    tested_rows: int
    failures: dict[int, str | None]


def copy_statements() -> list[sql.Composable]:
    """Lock the sources during a transaction-local, constraint-free copy."""
    source_tables = {table: sql.Identifier("rcm360", table) for table in TABLE_COLUMNS}
    statements = [
        sql.SQL("LOCK TABLE {} IN SHARE MODE").format(sql.SQL(", ").join(source_tables.values()))
    ]
    for table, fields in TABLE_COLUMNS.items():
        statements.append(
            sql.SQL(
                """
                CREATE TEMP TABLE {} ON COMMIT DROP AS
                SELECT row_number() OVER (ORDER BY {} COLLATE "C") AS audit_row_id, {}
                FROM {}
                """
            ).format(
                sql.Identifier(f"qa_{table}"),
                sql.Identifier(PRIMARY_KEYS[table]),
                sql.SQL(", ").join(map(sql.Identifier, fields)),
                source_tables[table],
            )
        )
    return statements


def evaluation_statement(rule: Rule) -> sql.Composable:
    return sql.SQL(
        """
        WITH evaluations AS ({}),
        totals AS (SELECT count(*) AS tested_rows FROM evaluations)
        SELECT totals.tested_rows, evaluations.audit_row_id, evaluations.record_ref
        FROM totals
        LEFT JOIN evaluations ON evaluations.failed
        ORDER BY evaluations.audit_row_id
        """
    ).format(rule.evaluation)


def evaluate(cursor: psycopg.Cursor, rule: Rule) -> Evaluation:
    rows = cursor.execute(evaluation_statement(rule)).fetchall()
    tested_rows = rows[0][0]
    failures = {row_id: record_ref for _, row_id, record_ref in rows if row_id is not None}
    if len(failures) != sum(row_id is not None for _, row_id, _ in rows):
        raise ValueError(f"Quality rule {rule.rule_id} produced multiple findings for a source row")
    return Evaluation(tested_rows, failures)


def _fraction(numerator: int, denominator: int) -> str | None:
    if denominator == 0:
        return None
    return format(Decimal(numerator) / Decimal(denominator), "f")


def _rule_info(rule: Rule) -> dict:
    return {
        "rule_id": rule.rule_id,
        "source_table": rule.source_table,
        "category": rule.category,
        "severity": rule.severity,
        "recommended_action": rule.recommended_action,
    }


def _issue(rule: Rule, record_ref: str | None, resolution_status: str) -> dict:
    return {
        "rule_id": rule.rule_id,
        "source_table": rule.source_table,
        "record_ref": record_ref,
        "issue_category": rule.category,
        "severity": rule.severity,
        "resolution_status": resolution_status,
        "recommended_action": rule.recommended_action,
    }


def _run_case(
    cursor: psycopg.Cursor, rule: Rule, original: Evaluation
) -> tuple[dict, list[dict]]:
    with cursor.connection.transaction(force_rollback=True):
        rows = cursor.execute(rule.injection.statement).fetchall()
        changed = {row_id for (row_id,) in rows}
        if len(changed) != rule.injection.expected_changes:
            raise ValueError(f"Could not seed the expected rows for {rule.rule_id}")
        expected = changed | rule.injection.additional_rows
        after = evaluate(cursor, rule)

    detections = after.failures.keys() - original.failures.keys()
    missed = expected - detections
    detected_count = len(detections)
    expected_count = len(expected)
    result = "pass" if detected_count == expected_count and not missed else "fail"
    details = [
        {
            **_issue(
                rule, after.failures[row_id], "detected" if row_id in expected else "unexpected"
            ),
            "audit_row_id": row_id,
        }
        for row_id in sorted(detections)
    ]
    details.extend(
        {**_issue(rule, None, "missed"), "audit_row_id": row_id} for row_id in sorted(missed)
    )
    return {
        **_rule_info(rule),
        "expected_count": expected_count,
        "detected_count": detected_count,
        "missed_count": len(missed),
        "detection_rate": _fraction(expected_count - len(missed), expected_count),
        "result": result,
    }, details


def run_quality(cursor: psycopg.Cursor) -> dict:
    """Produce local results and roll back the scratch copies before returning."""
    rules = build_rules()
    original_rules, original_issues = [], []
    injected_rules, injected_issues = [], []
    with cursor.connection.transaction(force_rollback=True):
        for statement in copy_statements():
            cursor.execute(statement)
        source_rows = sum(
            cursor.execute(
                sql.SQL("SELECT count(*) FROM {}").format(audit_table(table))
            ).fetchone()[0]
            for table in TABLE_COLUMNS
        )

        # Capture every original result before executing any mutation.
        originals = [evaluate(cursor, rule) for rule in rules]
        for rule, measure in zip(rules, originals, strict=True):
            issue_count = len(measure.failures)
            original_rules.append(
                {
                    **_rule_info(rule),
                    "tested_rows": measure.tested_rows,
                    "issue_count": issue_count,
                    "pass_rate": _fraction(measure.tested_rows - issue_count, measure.tested_rows),
                }
            )
            original_issues.extend(
                _issue(rule, record_ref, "open") for record_ref in measure.failures.values()
            )
            case, details = _run_case(cursor, rule, measure)
            injected_rules.append(case)
            injected_issues.extend(details)

    return {
        "original": {
            "summary": {
                "source_rows": source_rows,
                "rules_total": len(original_rules),
                "rules_passed": sum(rule["issue_count"] == 0 for rule in original_rules),
                "issues_total": len(original_issues),
            },
            "rules": original_rules,
            "issues": original_issues,
        },
        "injected_test": {
            "summary": {
                "source_rows": source_rows,
                "rules_total": len(injected_rules),
                "expected_findings": sum(rule["expected_count"] for rule in injected_rules),
                "detected_findings": sum(rule["detected_count"] for rule in injected_rules),
                "missed_findings": sum(rule["missed_count"] for rule in injected_rules),
                "tests_passed": sum(rule["result"] == "pass" for rule in injected_rules),
            },
            "rules": injected_rules,
            "issues": injected_issues,
        },
    }


def public_results(audit: dict) -> dict:
    """Project reconciled test totals and original claim issues."""
    original = audit["original"]
    injected = audit["injected_test"]
    for rule in injected["rules"]:
        expected = rule["expected_count"]
        detected = rule["detected_count"]
        missed = rule["missed_count"]
        if detected + missed != expected:
            raise ValueError(
                f"Cannot publish injected-test rule {rule['rule_id']}. "
                "Detected and missed counts do not add up to the expected count. "
                "Review the local audit for unexpected findings."
            )
        expected_result = "pass" if detected == expected and missed == 0 else "fail"
        if rule["result"] != expected_result:
            raise ValueError(
                f"Cannot publish injected-test rule {rule['rule_id']}. "
                "The rule result does not match the detection counts."
            )
    return {
        "original": {
            "summary": original["summary"],
            "rules": original["rules"],
            "issues": [
                issue
                for issue in original["issues"]
                if issue["source_table"] == "claims"
                and issue["record_ref"]
                and issue["record_ref"].strip()
            ],
        },
        "injected_test": {**injected, "issues": []},
    }


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Set DATABASE_URL to a PostgreSQL connection string", file=sys.stderr)
        return 2
    try:
        with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
            results = public_results(run_quality(cursor))
    except ValueError as exc:
        print(f"Quality audit failed. {exc}", file=sys.stderr)
        return 1
    except psycopg.Error as exc:
        detail = f" (SQLSTATE {exc.sqlstate})" if exc.sqlstate else ""
        print(f"PostgreSQL quality audit failed. {type(exc).__name__}{detail}", file=sys.stderr)
        return 1

    print(json.dumps(results, indent=2))
    original, injected = results["original"]["summary"], results["injected_test"]["summary"]
    return int(original["issues_total"] > 0 or injected["tests_passed"] != injected["rules_total"])


if __name__ == "__main__":
    raise SystemExit(main())
