from __future__ import annotations

import unittest

from ipo_tracker.market import merge_market_snapshot


class MarketSnapshotTests(unittest.TestCase):
    def test_merge_market_snapshot_reuses_previous_values_when_available(self) -> None:
        previous_snapshot = {
            "ipo_price": 50.44,
            "current_price": 168.73,
            "price_change_pct": 234.52,
            "avg_volume_30d": 4_250_982,
            "market_cap": 32_482_050_048,
        }
        latest_market = {
            "ipo_price": None,
            "current_price": None,
            "price_change_pct": None,
            "avg_volume_30d": None,
            "market_cap": None,
            "data_source": "yfinance",
            "market_data_note": "Market data fetch failed: Too Many Requests. Rate limited. Try after a while.",
        }

        merged = merge_market_snapshot(previous_snapshot, latest_market)

        self.assertEqual(merged["ipo_price"], 50.44)
        self.assertEqual(merged["current_price"], 168.73)
        self.assertEqual(merged["price_change_pct"], 234.52)
        self.assertIn("Previous snapshot market data available: yes.", merged["market_data_note"])
        self.assertIn("Reusing previous snapshot market data.", merged["market_data_note"])

    def test_merge_market_snapshot_marks_when_no_previous_values_exist(self) -> None:
        previous_snapshot = {
            "ipo_price": None,
            "current_price": None,
            "price_change_pct": None,
            "avg_volume_30d": None,
            "market_cap": None,
        }
        latest_market = {
            "ipo_price": None,
            "current_price": None,
            "price_change_pct": None,
            "avg_volume_30d": None,
            "market_cap": None,
            "data_source": "yfinance",
            "market_data_note": "Market data fetch failed: Too Many Requests. Rate limited. Try after a while.",
        }

        merged = merge_market_snapshot(previous_snapshot, latest_market)

        self.assertIsNone(merged["ipo_price"])
        self.assertIn("Previous snapshot market data available: no.", merged["market_data_note"])
        self.assertNotIn("Reusing previous snapshot market data.", merged["market_data_note"])

    def test_merge_market_snapshot_leaves_successful_payload_unchanged(self) -> None:
        previous_snapshot = {
            "ipo_price": 50.44,
            "current_price": 168.73,
            "price_change_pct": 234.52,
            "avg_volume_30d": 4_250_982,
            "market_cap": 32_482_050_048,
        }
        latest_market = {
            "ipo_price": 51.00,
            "current_price": 170.00,
            "price_change_pct": 233.33,
            "avg_volume_30d": 4_300_000,
            "market_cap": 33_000_000_000,
            "data_source": "yfinance",
            "market_data_note": "Live data from Yahoo Finance via yfinance",
        }

        merged = merge_market_snapshot(previous_snapshot, latest_market)

        self.assertEqual(merged, latest_market)


if __name__ == "__main__":
    unittest.main()
