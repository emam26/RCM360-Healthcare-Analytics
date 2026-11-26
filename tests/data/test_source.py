import unittest
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from src.etl.source import TABLE_COLUMNS, parse_csv, read_snapshot

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


class SourceParsingTest(unittest.TestCase):
    def test_claim_fields_keep_source_order_and_types(self):
        header = ",".join(TABLE_COLUMNS["claims"])
        values = (
            "claim-test,encounter-test,patient-test,commercial,inpatient,"
            "2026-01-01 09:00:00,100.25,0.5000,50.12,paid,"
            "2026-01-02 09:00:00,,50.12,50.13,"
        )
        [row] = parse_csv("claims", f"{header}\n{values}\n")
        claim = dict(zip(TABLE_COLUMNS["claims"], row, strict=True))
        self.assertEqual(claim["claim_id"], "claim-test")
        self.assertEqual(claim["submitted_at"], datetime(2026, 1, 1, 9))
        self.assertEqual(claim["paid_at"], datetime(2026, 1, 2, 9))
        self.assertIsNone(claim["denied_at"])
        self.assertIsNone(claim["denial_reason"])
        for field, expected in (
            ("billed_amount", "100.25"),
            ("allowed_ratio", "0.5000"),
            ("allowed_amount", "50.12"),
            ("paid_amount", "50.12"),
            ("patient_responsibility", "50.13"),
        ):
            self.assertIsInstance(claim[field], Decimal)
            self.assertEqual(str(claim[field]), expected)

    def test_postal_code_and_optional_phone_preserve_source_meaning(self):
        header = ",".join(TABLE_COLUMNS["patients"])
        values = (
            'patient-test,Synthetic Name,Female,1988-07-09,other,City,Region,'
            'United States,"12 Pine St, Suite 3",01234,,2025-05-02 13:00:00,0'
        )
        [row] = parse_csv("patients", f"{header}\n{values}\n")
        patient = dict(zip(TABLE_COLUMNS["patients"], row, strict=True))
        self.assertEqual(patient["date_of_birth"], date(1988, 7, 9))
        self.assertEqual(patient["postal_code"], "01234")
        self.assertEqual(patient["street_address"], "12 Pine St, Suite 3")
        self.assertIsNone(patient["phone"])
        self.assertEqual(patient["encounter_count"], 0)

    def test_missing_extra_and_reordered_fields_fail(self):
        with self.assertRaisesRegex(ValueError, "header"):
            parse_csv("providers", "provider_id,npi,provider_name,specialty,facility\n")
        header = ",".join(TABLE_COLUMNS["providers"])
        for values in ("p,Name,specialty,0123456789", "p,Name,specialty,0123456789,facility,extra"):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, "field count"):
                parse_csv("providers", f"{header}\n{values}\n")
        with self.assertRaisesRegex(ValueError, "provider_name"):
            parse_csv("providers", f"{header}\np,,specialty,0123456789,facility\n")

    def test_rejects_numeric_rounding_nonfinite_values_and_timezone_offsets(self):
        header = ",".join(TABLE_COLUMNS["claims"])
        for amount, timestamp, field in (
            ("10.125", "2026-01-01 09:00:00", "billed_amount"),
            ("NaN", "2026-01-01 09:00:00", "billed_amount"),
            ("10.12", "2026-01-01 09:00:00+00:00", "submitted_at"),
        ):
            with self.subTest(field=field, amount=amount), self.assertRaisesRegex(ValueError, field):
                values = f"c,e,p,other,outpatient,{timestamp},{amount},0.5000,5.06,pending,,,0.00,0.00,"
                parse_csv("claims", f"{header}\n{values}\n")


class ApprovedSnapshotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = read_snapshot(RAW_DIR)

    def test_table_row_counts_and_primary_keys(self):
        expected = {
            "patients": 1500,
            "providers": 60,
            "encounters": 4737,
            "diagnoses": 8427,
            "prescriptions": 5539,
            "lab_results": 14946,
            "claims": 4737,
        }
        self.assertEqual({table: len(rows) for table, rows in self.snapshot.items()}, expected)
        for table, rows in self.snapshot.items():
            with self.subTest(table=table):
                self.assertEqual(len({row[0] for row in rows}), len(rows))

    def test_claims_match_encounters_and_exact_financial_baseline(self):
        columns = TABLE_COLUMNS["claims"]
        claims = [dict(zip(columns, row, strict=True)) for row in self.snapshot["claims"]]
        encounter_ids = [row["encounter_id"] for row in claims]
        self.assertCountEqual(encounter_ids, (row[0] for row in self.snapshot["encounters"]))
        self.assertEqual(
            Counter(row["status"] for row in claims),
            {"paid": 4122, "denied": 426, "pending": 189},
        )
        for field, expected in (
            ("billed_amount", "18033949.84"),
            ("allowed_amount", "9172905.62"),
            ("paid_amount", "7938924.10"),
            ("patient_responsibility", "7779126.53"),
        ):
            with self.subTest(field=field):
                self.assertTrue(all(isinstance(row[field], Decimal) for row in claims))
                self.assertEqual(sum(row[field] for row in claims), Decimal(expected))
