from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ipo_tracker import db


class DatabaseMarketFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_data_dir = db.DATA_DIR
        self.original_db_path = db.DB_PATH
        db.DATA_DIR = Path(self.temp_dir.name)
        db.DB_PATH = db.DATA_DIR / "test_ipo_lockup_tracker.db"
        db.initialize_database()
        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO companies (ticker, company_name, cik, ipo_date, lockup_days, theme)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("ARM", "Arm Holdings plc", 1973239, "2023-09-14", 180, "Semiconductors"),
            )
            row = conn.execute("SELECT id FROM companies WHERE ticker = 'ARM'").fetchone()
            if row is None:
                raise AssertionError("Failed to insert ARM company row for test setup")
            self.company_id = int(row["id"])
            conn.commit()

    def tearDown(self) -> None:
        db.DATA_DIR = self.original_data_dir
        db.DB_PATH = self.original_db_path

    def _write_snapshot(
        self,
        *,
        ipo_price,
        current_price,
        price_change_pct,
        avg_volume_30d,
        market_cap,
        market_data_note: str,
        ownership_context: dict | None = None,
    ) -> None:
        db.upsert_snapshot(
            self.company_id,
            filing_form="424B4",
            filing_date="2023-09-14",
            source_url="https://example.com/arm-424b4",
            lockup_days=180,
            unlock_date="2024-03-11",
            effective_unlock_date="2024-03-11",
            principal_holders=[{"holder": "SoftBank Group Corp.", "shares": 1025233999}],
            lockup_source="Lock-Up Restrictions section: Regex match: for a period of 180 days",
            lockup_conditions={},
            ownership_context=ownership_context or {},
            insider_sales=[],
            ipo_price=ipo_price,
            current_price=current_price,
            price_change_pct=price_change_pct,
            avg_volume_30d=avg_volume_30d,
            market_cap=market_cap,
            market_data_note=market_data_note,
            confidence_score=100,
            confidence_label="High",
            confidence_details="Parsed 1 principal holder rows",
            notes="Parsed 1 principal holder rows",
        )

    def test_load_dashboard_rows_reuses_persisted_market_history(self) -> None:
        self._write_snapshot(
            ipo_price=63.59,
            current_price=242.63,
            price_change_pct=281.55,
            avg_volume_30d=8_123_513,
            market_cap=259_147_956_224,
            market_data_note="Live data from Yahoo Finance via yfinance",
        )
        self._write_snapshot(
            ipo_price=None,
            current_price=None,
            price_change_pct=None,
            avg_volume_30d=None,
            market_cap=None,
            market_data_note="Market data fetch failed: Too Many Requests. Rate limited. Try after a while. Reusing in-process market cache.",
        )

        rows = db.load_dashboard_rows()

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["ipo_price"], 63.59)
        self.assertEqual(row["current_price"], 242.63)
        self.assertEqual(row["price_change_pct"], 281.55)
        self.assertEqual(row["avg_volume_30d"], 8_123_513)
        self.assertEqual(row["market_cap"], 259_147_956_224)
        self.assertIn("Previous snapshot market data available: yes.", row["market_data_note"])
        self.assertIn("Backfilled previous snapshot market data from local history.", row["market_data_note"])

    def test_initialize_database_backfills_market_history_from_existing_snapshots(self) -> None:
        self._write_snapshot(
            ipo_price=63.59,
            current_price=266.33,
            price_change_pct=318.82,
            avg_volume_30d=8_123_363,
            market_cap=284_461_400_064,
            market_data_note="Live data from Yahoo Finance via yfinance",
        )
        with db.get_connection() as conn:
            conn.execute("DELETE FROM company_market_history WHERE ticker = ?", ("ARM",))
            conn.commit()

        db.initialize_database()

        with db.get_connection() as conn:
            history_row = conn.execute(
                "SELECT ticker, ipo_price, current_price FROM company_market_history WHERE ticker = ?",
                ("ARM",),
            ).fetchone()
        if history_row is None:
            raise AssertionError("Expected ARM market history to be rebuilt from snapshots")

        self._write_snapshot(
            ipo_price=None,
            current_price=None,
            price_change_pct=None,
            avg_volume_30d=None,
            market_cap=None,
            market_data_note="Market data fetch failed: Too Many Requests. Rate limited. Try after a while.",
        )

        row = db.load_dashboard_rows()[0]
        self.assertEqual(row["ipo_price"], 63.59)
        self.assertEqual(row["current_price"], 266.33)
        self.assertIn("Previous snapshot market data available: yes.", row["market_data_note"])

    def test_load_dashboard_rows_preserves_ownership_context(self) -> None:
        self._write_snapshot(
            ipo_price=63.59,
            current_price=242.63,
            price_change_pct=281.55,
            avg_volume_30d=8_123_513,
            market_cap=259_147_956_224,
            market_data_note="Live data from Yahoo Finance via yfinance",
            ownership_context={
                "offering_shares_outstanding": 86_863_925,
                "current_shares_outstanding": 90_000_000,
                "tracked_holder_pct_of_offering": 24.3,
            },
        )

        row = db.load_dashboard_rows()[0]

        self.assertEqual(row["ownership_context"]["offering_shares_outstanding"], 86_863_925)
        self.assertEqual(row["ownership_context"]["current_shares_outstanding"], 90_000_000)
        self.assertEqual(row["ownership_context"]["tracked_holder_pct_of_offering"], 24.3)


if __name__ == "__main__":
    unittest.main()
