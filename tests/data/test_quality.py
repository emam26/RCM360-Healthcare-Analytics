import unittest
from importlib.util import find_spec
from unittest.mock import MagicMock, patch

from src.etl.source import TABLE_COLUMNS
from src.validation.audit import (
    Evaluation,
    _run_case,
    copy_statements,
    evaluation_statement,
    public_results,
    run_quality,
)
from src.validation.rules import FOREIGN_KEYS, build_rules


class QualityAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = {rule.rule_id: rule for rule in build_rules()}

    def test_rules_cover_structural_keys_and_known_injections(self):
        primary = {rule.source_table for rule in self.rules.values() if rule.category == "primary_key"}
        foreign = [rule for rule in self.rules.values() if rule.category == "foreign_key"]
        self.assertEqual(primary, set(TABLE_COLUMNS))
        self.assertEqual(len(foreign), 11)
        self.assertEqual(len(self.rules), 32)
        self.assertEqual(
            sum(
                rule.injection.expected_changes + len(rule.injection.additional_rows)
                for rule in self.rules.values()
            ),
            64,
        )

    def test_same_number_of_findings_cannot_mask_a_missed_record(self):
        cursor = MagicMock()
        cursor.execute.return_value.fetchall.return_value = [(2,), (3,), (4,)]
        original = Evaluation(20, {9: "existing"})
        after = Evaluation(20, {1: "duplicate", 2: "duplicate", 3: None, 5: "wrong", 9: "existing"})
        with patch("src.validation.audit.evaluate", return_value=after):
            result, details = _run_case(cursor, self.rules["PK_CLAIMS"], original)
        cursor.connection.transaction.assert_called_once_with(force_rollback=True)
        self.assertEqual(result["detected_count"], 4)
        self.assertEqual(result["expected_count"], 4)
        self.assertEqual(result["missed_count"], 1)
        self.assertEqual(result["detection_rate"], "0.75")
        self.assertEqual(result["result"], "fail")
        self.assertEqual(
            {row["audit_row_id"]: row["resolution_status"] for row in details},
            {1: "detected", 2: "detected", 3: "detected", 4: "missed", 5: "unexpected"},
        )

    def test_public_projection_rejects_injected_counts_with_an_unexpected_finding(self):
        cursor = MagicMock()
        cursor.execute.return_value.fetchall.return_value = [(2,), (3,), (4,)]
        after = Evaluation(20, {1: "copy", 2: "copy", 3: None, 4: " ", 5: "unexpected-ref"})
        with patch("src.validation.audit.evaluate", return_value=after):
            rule, issues = _run_case(cursor, self.rules["PK_CLAIMS"], Evaluation(20, {}))

        local = {
            "original": {"summary": {}, "rules": [], "issues": []},
            "injected_test": {"summary": {}, "rules": [rule], "issues": issues},
        }
        with self.assertRaisesRegex(ValueError, r"Cannot publish injected-test rule PK_CLAIMS"):
            public_results(local)
        self.assertEqual(rule["detected_count"], 5)
        self.assertEqual(rule["result"], "fail")
        self.assertEqual(issues[-1]["resolution_status"], "unexpected")

    def test_public_projection_accepts_a_reconciled_failed_rule_and_hides_test_details(self):
        cursor = MagicMock()
        cursor.execute.return_value.fetchall.return_value = [(2,), (3,), (4,)]
        after = Evaluation(20, {1: "copy", 2: "copy", 3: None})
        with patch("src.validation.audit.evaluate", return_value=after):
            rule, issues = _run_case(cursor, self.rules["PK_CLAIMS"], Evaluation(20, {}))

        summary = {
            "source_rows": 20, "rules_total": 1, "expected_findings": 4,
            "detected_findings": 3, "missed_findings": 1, "tests_passed": 0,
        }
        local = {
            "original": {"summary": {}, "rules": [], "issues": []},
            "injected_test": {"summary": summary, "rules": [rule], "issues": issues},
        }
        self.assertEqual(rule["result"], "fail")
        self.assertEqual(
            public_results(local)["injected_test"],
            {"summary": summary, "rules": [rule], "issues": []},
        )
        rule["result"] = "pass"
        with self.assertRaisesRegex(ValueError, "result does not match the detection counts"):
            public_results(local)

    def test_original_and_injected_audits_are_rolled_back_and_kept_separate(self):
        cursor = MagicMock()
        cursor.execute.return_value.fetchone.side_effect = [(10,)] * len(TABLE_COLUMNS)
        cursor.execute.return_value.fetchall.return_value = [(2,), (3,), (4,)]
        original = Evaluation(10, {9: "source-claim"})
        injected = Evaluation(10, {1: "copy", 2: "copy", 3: None, 4: " ", 9: "source-claim"})
        with (
            patch("src.validation.audit.build_rules", return_value=[self.rules["PK_CLAIMS"]]),
            patch("src.validation.audit.evaluate", side_effect=[original, injected]),
        ):
            local = run_quality(cursor)
        self.assertEqual(cursor.connection.transaction.call_count, 2)
        self.assertTrue(
            all(
                context.kwargs == {"force_rollback": True}
                for context in cursor.connection.transaction.call_args_list
            )
        )
        self.assertEqual(
            local["original"]["summary"],
            {"source_rows": 70, "rules_total": 1, "rules_passed": 0, "issues_total": 1},
        )
        self.assertEqual(
            local["injected_test"]["summary"],
            {
                "source_rows": 70, "rules_total": 1, "expected_findings": 4,
                "detected_findings": 4, "missed_findings": 0, "tests_passed": 1,
            },
        )
        self.assertEqual(local["original"]["rules"][0]["pass_rate"], "0.9")
        self.assertEqual(len(local["injected_test"]["issues"]), 4)
        self.assertEqual(public_results(local)["injected_test"]["issues"], [])
        self.assertEqual(public_results(local)["original"]["issues"][0]["record_ref"], "source-claim")

    def test_no_privacy_sensitive_or_unkeyed_issues_are_public(self):
        local = {
            "original": {
                "summary": {"issues_total": 3},
                "rules": [],
                "issues": [
                    {"source_table": "claims", "record_ref": "claim-1"},
                    {"source_table": "claims", "record_ref": None},
                    {"source_table": "patients", "record_ref": "patient-1"},
                ],
            },
            "injected_test": {"summary": {}, "rules": [], "issues": [{"record_ref": "copy-1"}]},
        }
        public = public_results(local)
        self.assertEqual(public["original"]["issues"], [local["original"]["issues"][0]])
        self.assertEqual(public["original"]["summary"]["issues_total"], 3)
        self.assertEqual(public["injected_test"]["issues"], [])
        self.assertEqual(len(local["injected_test"]["issues"]), 1)


@unittest.skipUnless(find_spec("pglast"), "pglast is required for PostgreSQL grammar checks")
class QualitySqlTest(unittest.TestCase):
    def test_all_queries_parse_and_write_only_to_temporary_tables(self):
        from pglast import ast, parse_sql
        from pglast.enums import OnCommitAction

        [lock, *copies] = [parse_sql(statement.as_string())[0].stmt for statement in copy_statements()]
        self.assertIsInstance(lock, ast.LockStmt)
        self.assertEqual({relation.schemaname for relation in lock.relations}, {"rcm360"})
        self.assertEqual(len(copies), 7)
        for statement in copies:
            self.assertIsInstance(statement, ast.CreateTableAsStmt)
            self.assertEqual(statement.into.rel.relpersistence, "t")
            self.assertEqual(statement.into.onCommit, OnCommitAction.ONCOMMIT_DROP)
            self.assertEqual(statement.query.fromClause[0].schemaname, "rcm360")

        for rule in build_rules():
            with self.subTest(rule=rule.rule_id):
                [evaluation] = parse_sql(evaluation_statement(rule).as_string())
                self.assertIsInstance(evaluation.stmt, ast.SelectStmt)
                [case] = parse_sql(rule.injection.statement.as_string())
                self.assertIsInstance(case.stmt, (ast.UpdateStmt, ast.DeleteStmt))
                self.assertEqual(case.stmt.relation.schemaname, "pg_temp")

    def test_audited_foreign_keys_match_the_schema(self):
        from pglast import ast, parse_sql
        from pglast.enums import ConstrType

        from src.etl.load_postgres import SCHEMA_SQL

        schema = [node.stmt for node in parse_sql(SCHEMA_SQL.read_text(encoding="utf-8"))]
        foreign_keys = {
            (table.relation.relname, column.colname, constraint.pktable.relname)
            for table in schema if isinstance(table, ast.CreateStmt)
            for column in table.tableElts if isinstance(column, ast.ColumnDef)
            for constraint in column.constraints or ()
            if constraint.contype == ConstrType.CONSTR_FOREIGN
        }
        self.assertEqual(foreign_keys, set(FOREIGN_KEYS))
