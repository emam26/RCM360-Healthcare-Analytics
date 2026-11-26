import unittest
from decimal import Decimal
from unittest.mock import MagicMock

from src.etl.load_postgres import load_snapshot
from src.etl.source import TABLE_COLUMNS


class SnapshotLoadTest(unittest.TestCase):
    def setUp(self):
        self.cursor = MagicMock()
        self.snapshot = {table: [(table,)] for table in TABLE_COLUMNS}
        self.snapshot["claims"] = [("claim-test", Decimal("10.15"))]

    def test_same_snapshot_skips_all_copies(self):
        self.cursor.execute.return_value.fetchall.side_effect = list(self.snapshot.values())

        self.assertEqual(load_snapshot(self.cursor, self.snapshot), [])
        self.cursor.copy.assert_not_called()

    def test_mismatch_stops_before_writing_even_when_another_table_is_empty(self):
        existing = list(self.snapshot.values())
        existing[0] = []
        existing[-1] = [("claim-test", Decimal("10.16"))]
        self.cursor.execute.return_value.fetchall.side_effect = existing

        with self.assertRaisesRegex(ValueError, r"Existing rcm360\.claims rows differ"):
            load_snapshot(self.cursor, self.snapshot)
        self.cursor.copy.assert_not_called()

    def test_copies_exact_approved_rows_to_an_empty_table(self):
        existing = list(self.snapshot.values())
        existing[-1] = []
        self.cursor.execute.return_value.fetchall.side_effect = [
            *existing,
            self.snapshot["claims"],
        ]

        self.assertEqual(load_snapshot(self.cursor, self.snapshot), ["claims"])
        self.cursor.copy.assert_called_once()
        copy = self.cursor.copy.return_value.__enter__.return_value
        copy.write_row.assert_called_once_with(self.snapshot["claims"][0])
