import json
import os
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from dashboard.model import CLAIM_FIELDS
from src.etl.source import SOURCE_ARCHIVE, SOURCE_SHA256, TABLE_COLUMNS, read_snapshot
from src.exports.dashboard_json import EXPORT_LOCK_SQL, build_payloads, export_dashboard, write_payloads
from src.exports.reconcile import (
    CLAIMS_SQL,
    RECONCILIATION_FIELDS,
    RECONCILIATION_SQL,
    _expected_totals,
    reconcile_claims,
    source_claims,
)

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


class DashboardExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = source_claims(read_snapshot(RAW_DIR))
        cls.example_claims = [
            next(row for row in cls.source.values() if row["status"] == status)
            for status in ("paid", "denied", "pending")
        ]
        claim_idx = TABLE_COLUMNS["claims"].index("claim_id")
        claim_ids = {row["claim_id"] for row in cls.example_claims}
        encounter_ids = {row["encounter_id"] for row in cls.example_claims}
        raw = read_snapshot(RAW_DIR)
        cls.sample = {
            "claims": [row for row in raw["claims"] if row[claim_idx] in claim_ids],
            "encounters": [row for row in raw["encounters"] if row[0] in encounter_ids],
        }

    def setUp(self):
        self.source_count = 6
        self.expected = source_claims(self.sample)
        self.records = [
            {field: claim[field] for field in CLAIM_FIELDS} for claim in self.expected.values()
        ]
        self.aggregates = [
            {"relation": relation, "status": status, **dict(zip(RECONCILIATION_FIELDS, values, strict=True))}
            for relation in ("base", "view")
            for status, values in _expected_totals(self.expected).items()
        ]
        self.engine = MagicMock()
        self.connection = self.engine.connect.return_value.__enter__.return_value
        self.cursor = self.connection.connection.driver_connection.cursor.return_value.__enter__.return_value
        self.db_rows = [dict(row) for row in self.expected.values()]
        lock, totals, records = [MagicMock() for _ in range(3)]
        totals.mappings.return_value.all.return_value = self.aggregates
        records.mappings.return_value.all.return_value = self.db_rows
        responses = {EXPORT_LOCK_SQL: lock, RECONCILIATION_SQL: totals, CLAIMS_SQL: records}
        self.connection.exec_driver_sql.side_effect = responses.__getitem__

        claim_id = self.records[0]["claim_id"]
        claim_rule = {
            "rule_id": "CLAIM_CHECK", "source_table": "claims", "category": "financial",
            "severity": "high", "recommended_action": "Review the source amounts.",
        }
        patient_rule = claim_rule | {"rule_id": "PATIENT_CHECK", "source_table": "patients"}
        issues = [
            {
                "rule_id": rule["rule_id"], "source_table": rule["source_table"], "record_ref": ref,
                "issue_category": rule["category"], "severity": rule["severity"],
                "recommended_action": rule["recommended_action"], "resolution_status": "open",
            }
            for rule, ref in ((claim_rule, claim_id), (patient_rule, "local-patient-ref"))
        ]
        self.audit = {
            "original": {
                "summary": {"source_rows": 6, "rules_total": 2, "rules_passed": 0, "issues_total": 2},
                "rules": [
                    rule | {"tested_rows": 1, "issue_count": 1, "pass_rate": "0"}
                    for rule in (claim_rule, patient_rule)
                ],
                "issues": issues,
            },
            "injected_test": {
                "summary": {
                    "source_rows": 6, "rules_total": 1, "expected_findings": 1,
                    "detected_findings": 1, "missed_findings": 0, "tests_passed": 1,
                },
                "rules": [
                    claim_rule | {
                        "expected_count": 1, "detected_count": 1, "missed_count": 0,
                        "detection_rate": "1", "result": "pass",
                    }
                ],
                "issues": [{"record_ref": "local-injected-ref"}],
            },
        }

    def test_unmodified_source_totals_match_the_independent_baseline(self):
        counts_and_amounts = _expected_totals(self.source)
        self.assertEqual(
            counts_and_amounts[None],
            (
                4737, 4737, 4737, Decimal("18033949.84"), Decimal("9172905.62"),
                Decimal("7938924.10"), Decimal("7779126.53"),
            ),
        )
        self.assertEqual({status: counts_and_amounts[status][0] for status in ("paid", "denied", "pending")},
                         {"paid": 4122, "denied": 426, "pending": 189})

    def test_export_uses_one_repeatable_read_transaction_and_writes_private_safe_files(self):
        with (
            TemporaryDirectory() as directory,
            patch("src.exports.dashboard_json.read_snapshot", return_value=self.sample) as read,
            patch("src.exports.dashboard_json.create_engine", return_value=self.engine) as make_engine,
            patch("src.exports.dashboard_json.run_quality", return_value=self.audit) as run_audit,
        ):
            output = Path(directory)
            count = export_dashboard("postgresql://example/rcm360", RAW_DIR, output)
            claims = json.loads((output / "claims.json").read_text(encoding="utf-8"))
            quality = json.loads((output / "quality.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(file.name for file in output.iterdir()), ["claims.json", "quality.json"])
        read.assert_called_once_with(RAW_DIR)
        run_audit.assert_called_once_with(self.cursor)
        self.connection.begin.assert_called_once_with()
        self.engine.dispose.assert_called_once_with()
        self.assertEqual(make_engine.call_args.args[0].drivername, "postgresql+psycopg")
        self.assertEqual(make_engine.call_args.kwargs["isolation_level"], "REPEATABLE READ")
        self.assertEqual(count, 3)
        self.assertEqual(claims["metadata"]["source_sha256"], SOURCE_SHA256)
        self.assertEqual(claims["metadata"]["generated_at"], quality["metadata"]["generated_at"])
        self.assertTrue(claims["metadata"]["generated_at"].endswith("+00:00"))
        self.assertEqual(quality["metadata"]["record_count"], 6)
        for row in claims["records"]:
            self.assertEqual(set(row), set(CLAIM_FIELDS))
            original = self.expected[row["claim_id"]]
            self.assertEqual(Decimal(row["billed_amount"]), original["billed_amount"])
            self.assertIn("T", row["submitted_at"])
            if row["status"] == "paid":
                self.assertEqual(Decimal(row["submission_to_payment_days"]), original["submission_to_payment_days"])
            else:
                self.assertIsNone(row["submission_to_payment_days"])
        self.assertEqual(len(quality["original"]["issues"]), 1)
        self.assertEqual(quality["original"]["issues"][0]["record_ref"], self.records[0]["claim_id"])
        self.assertEqual(quality["injected_test"]["issues"], [])

    def test_an_exact_total_mismatch_stops_before_export_and_qa(self):
        self.aggregates[0]["payer_paid_amount"] += Decimal("0.01")
        with (
            TemporaryDirectory() as directory,
            patch("src.exports.dashboard_json.read_snapshot", return_value=self.sample),
            patch("src.exports.dashboard_json.create_engine", return_value=self.engine),
            patch("src.exports.dashboard_json.run_quality") as run_audit,
        ):
            output = Path(directory)
            self._old_pair(output)
            with self.assertRaisesRegex(ValueError, "exact sums differ"):
                export_dashboard("postgresql://example/rcm360", RAW_DIR, output)
            self._assert_old_pair(output)
        run_audit.assert_not_called()

    def test_matching_totals_do_not_hide_view_field_or_grain_errors(self):
        original = self.db_rows[1]
        self.db_rows[1] = self.db_rows[0]
        with self.assertRaisesRegex(ValueError, "claim grain"):
            reconcile_claims(self.connection, self.expected)
        self.db_rows[1] = original | {"provider_id": "unexpected-provider"}
        with self.assertRaisesRegex(ValueError, "view record differs"):
            reconcile_claims(self.connection, self.expected)

    def test_unverified_archive_never_opens_a_database_connection(self):
        with TemporaryDirectory() as directory, patch("src.exports.dashboard_json.create_engine") as connect:
            raw = Path(directory)
            (raw / SOURCE_ARCHIVE).write_bytes(b"changed")
            output = raw / "output"
            with self.assertRaisesRegex(ValueError, "approved Misata archive SHA-256"):
                export_dashboard("postgresql://example/rcm360", raw, output)
            self.assertFalse(output.exists())
        connect.assert_not_called()

    def test_quality_validation_failure_preserves_existing_pair(self):
        claims, quality = build_payloads(self.records, self.audit, self.source_count)
        quality["injected_test"]["issues"] = [{"record_ref": "local-only"}]
        with TemporaryDirectory() as directory:
            output = Path(directory)
            self._old_pair(output)
            with self.assertRaisesRegex(ValueError, "only aggregate findings"):
                write_payloads(output, claims, quality)
            self._assert_old_pair(output)

    def test_second_replacement_failure_restores_previous_pair(self):
        claims, quality = build_payloads(self.records, self.audit, self.source_count)
        replace = os.replace

        def fail_on_quality(source, destination):
            if destination.name == "quality.json":
                raise PermissionError("test replacement failure")
            replace(source, destination)

        with TemporaryDirectory() as directory:
            output = Path(directory)
            self._old_pair(output)
            with (
                patch("src.exports.dashboard_json.os.replace", side_effect=fail_on_quality),
                self.assertRaisesRegex(PermissionError, "test replacement failure"),
            ):
                write_payloads(output, claims, quality)
            self._assert_old_pair(output)

    def _old_pair(self, output):
        for name in ("claims.json", "quality.json"):
            (output / name).write_text(f"old {name}", encoding="utf-8")

    def _assert_old_pair(self, output):
        self.assertEqual(sorted(file.name for file in output.iterdir()), ["claims.json", "quality.json"])
        for name in ("claims.json", "quality.json"):
            self.assertEqual((output / name).read_text(encoding="utf-8"), f"old {name}")
