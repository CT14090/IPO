from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from ipo_tracker.config import DEFAULT_LOCKUP_DAYS
from ipo_tracker.market import calculate_price_change_pct
from ipo_tracker.sec import (
    LockupConditions,
    add_trading_days,
    assess_data_confidence,
    determine_effective_unlock_date,
    extract_ipo_date_from_text,
    extract_lockup_conditions,
    extract_lockup_days,
    extract_principal_holders,
    find_lockup_amendment_8k,
)


class SecParserTests(unittest.TestCase):
    def test_extract_lockup_days_from_lockup_section(self) -> None:
        html = """
        <html>
          <body>
            <h2>Lock-Up Agreements</h2>
            <p>The underwriters and selling stockholders agreed to restrictions for a period of 180 days after the date of this prospectus.</p>
          </body>
        </html>
        """

        days, source = extract_lockup_days(html)

        self.assertEqual(days, 180)
        self.assertIn("Lock-Up Agreements section", source)

    def test_extract_lockup_days_defaults_when_text_is_unclear(self) -> None:
        days, source = extract_lockup_days("<html><body><p>No usable lockup language here.</p></body></html>")

        self.assertEqual(days, DEFAULT_LOCKUP_DAYS)
        self.assertIn("Defaulted to 180 days", source)

    def test_extract_lockup_conditions_finds_early_release_pct_beyond_short_window(self) -> None:
        filler = "x" * 2400
        html = f"""
        <html>
          <body>
            <h2>Lock-Up Agreements</h2>
            <p>The lock-up period will terminate on the earlier of (i) the second trading day after the date that we publicly announce earnings or (ii) 180 days after the date of this prospectus.</p>
            <p>{filler}</p>
            <p>In addition, up to 20% of eligible securities may be released.</p>
          </body>
        </html>
        """

        conditions = extract_lockup_conditions(html)

        self.assertTrue(conditions.has_early_release)
        self.assertEqual(conditions.early_release_pct, 20)
        self.assertIn("Earnings-linked trigger", conditions.notes_summary())

    def test_extract_lockup_conditions_ignores_greenshoe_matches(self) -> None:
        html = """
        <html>
          <body>
            <h2>Underwriting</h2>
            <p>The underwriters may purchase additional shares for a period of 30 days after the date of this prospectus.</p>
            <h2>Lock-Up Restrictions</h2>
            <p>Our directors, officers and stockholders agreed not to sell shares for 180 days after the date of this prospectus.</p>
          </body>
        </html>
        """

        conditions = extract_lockup_conditions(html)

        self.assertEqual(conditions.lockup_days, 180)
        self.assertIn("Lock-Up Restrictions section", conditions.lockup_source)
        self.assertNotIn("30 days", conditions.lockup_source)

    def test_extract_lockup_conditions_detects_early_release_and_earnings_trigger(self) -> None:
        html = """
        <html>
          <body>
            <h2>Lock-Up Agreements</h2>
            <p>
              The lock-up period will terminate on the earlier of (i) the second trading day
              after the date that we publicly announce earnings for the quarter ending June 30, 2024 or
              (ii) 180 days after the date of this prospectus.
            </p>
          </body>
        </html>
        """

        conditions = extract_lockup_conditions(html)

        self.assertTrue(conditions.has_early_release)
        self.assertTrue(conditions.has_earnings_trigger)
        self.assertIsNone(conditions.early_release_pct)
        self.assertIn("earlier of", conditions.early_release_description.lower())
        self.assertEqual(conditions.earnings_release_quarter_end, "2024-06-30")

    @patch("ipo_tracker.sec.fetch_text")
    @patch("ipo_tracker.sec.fetch_json")
    def test_find_lockup_amendment_8k_returns_matching_amendment(self, fetch_json_mock, fetch_text_mock) -> None:
        fetch_json_mock.return_value = {
            "filings": {
                "recent": {
                    "form": ["8-K", "10-Q"],
                    "accessionNumber": ["0001111111-24-000001", "0001111111-24-000002"],
                    "primaryDocument": ["amendment.htm", "quarterly.htm"],
                    "filingDate": ["2024-08-06", "2024-08-10"],
                }
            }
        }
        fetch_text_mock.return_value = """
        <html>
          <body>
            <p>The lock-up period will terminate on the earlier of the earnings release date or 180 days after the date of this prospectus.</p>
          </body>
        </html>
        """

        filing_date, filing_url, excerpt = find_lockup_amendment_8k(1736297, date(2024, 3, 20))

        self.assertEqual(filing_date, "2024-08-06")
        self.assertIn("amendment.htm", filing_url or "")
        self.assertIn("lock-up period", (excerpt or "").lower())

    def test_extract_ipo_date_from_cover_page_text(self) -> None:
        html = """
        <html>
          <body>
            <p>The date of this prospectus is March 19, 2024.</p>
          </body>
        </html>
        """

        parsed_date = extract_ipo_date_from_text(html)

        self.assertEqual(parsed_date, "2024-03-19")

    def test_extract_principal_holders_cleans_headers_and_numeric_values(self) -> None:
        html = """
        <html>
          <body>
            <h2>Principal and Selling Stockholders</h2>
            <table>
              <tr>
                <th>Name of Beneficial Owner</th>
                <th>Shares Beneficially Owned</th>
                <th>Percent of Class</th>
              </tr>
              <tr>
                <td>Sequoia Capital</td>
                <td>12,345,678</td>
                <td>14.2%</td>
              </tr>
              <tr>
                <td>Founder Holdings LLC</td>
                <td>8,765,432</td>
                <td>10.1%</td>
              </tr>
              <tr>
                <td>Total</td>
                <td>21,111,110</td>
                <td>24.3%</td>
              </tr>
            </table>
          </body>
        </html>
        """

        holders = extract_principal_holders(html)

        self.assertEqual(len(holders), 2)
        self.assertEqual(holders[0]["holder"], "Sequoia Capital")
        self.assertEqual(holders[0]["shares"], 12_345_678)
        self.assertAlmostEqual(holders[0]["percent"], 14.2)
        self.assertEqual(holders[1]["holder"], "Founder Holdings LLC")
        self.assertEqual(holders[1]["shares"], 8_765_432)
        self.assertAlmostEqual(holders[1]["percent"], 10.1)

    def test_extract_principal_holders_handles_spacer_cells_and_ignores_toc(self) -> None:
        html = """
        <html>
          <body>
            <table>
              <tr><td>1</td><td>Overview</td></tr>
              <tr><td>7</td><td>Principal and Selling Stockholders</td></tr>
              <tr><td>12</td><td>Risk Factors</td></tr>
            </table>
            <table>
              <tr>
                <th>Name of Beneficial Owner</th>
                <th>Shares Beneficially Owned</th>
                <th>Percent of Class</th>
              </tr>
              <tr>
                <td>Sequoia Capital</td>
                <td width="1%">&nbsp;</td>
                <td>12,345,678</td>
                <td width="1%">&nbsp;</td>
                <td>14.2%</td>
              </tr>
              <tr>
                <td>Founder Holdings LLC</td>
                <td width="1%">&nbsp;</td>
                <td>8,765,432</td>
                <td width="1%">&nbsp;</td>
                <td>10.1%</td>
              </tr>
              <tr>
                <td>Total</td>
                <td width="1%">&nbsp;</td>
                <td>21,111,110</td>
                <td width="1%">&nbsp;</td>
                <td>24.3%</td>
              </tr>
            </table>
          </body>
        </html>
        """

        holders = extract_principal_holders(html)

        self.assertEqual(len(holders), 2)
        self.assertEqual(holders[0]["holder"], "Sequoia Capital")
        self.assertEqual(holders[0]["shares"], 12_345_678)
        self.assertAlmostEqual(holders[0]["percent"], 14.2)
        self.assertEqual(holders[1]["holder"], "Founder Holdings LLC")
        self.assertEqual(holders[1]["shares"], 8_765_432)
        self.assertAlmostEqual(holders[1]["percent"], 10.1)

    def test_extract_principal_holders_promotes_embedded_header_rows(self) -> None:
        html = """
        <html>
          <body>
            <h2>Principal and Selling Shareholder</h2>
            <table>
              <tr>
                <td></td>
                <td>Ordinary Shares beneficially owned prior to this offering</td>
                <td>Ordinary Shares beneficially owned prior to this offering</td>
                <td>Ordinary Shares being sold in this offering</td>
                <td>Ordinary Shares beneficially owned after this offering</td>
                <td>Ordinary Shares beneficially owned after this offering</td>
              </tr>
              <tr>
                <td>Name of Beneficial Shareholder</td>
                <td>Number</td>
                <td>Percent</td>
                <td>Number</td>
                <td>Number</td>
                <td>Percent</td>
              </tr>
              <tr>
                <td>SoftBank Group Corp.</td>
                <td>1,025,233,999</td>
                <td>100%</td>
                <td>95,500,000</td>
                <td>929,733,999</td>
                <td>90.6%</td>
              </tr>
              <tr>
                <td>Total</td>
                <td>1,025,233,999</td>
                <td>100%</td>
                <td>95,500,000</td>
                <td>929,733,999</td>
                <td>90.6%</td>
              </tr>
            </table>
          </body>
        </html>
        """

        holders = extract_principal_holders(html)

        self.assertEqual(len(holders), 1)
        self.assertEqual(holders[0]["holder"], "SoftBank Group Corp.")
        self.assertEqual(holders[0]["shares"], 1_025_233_999)
        self.assertAlmostEqual(holders[0]["percent"], 100.0)
        self.assertEqual(set(holders[0].keys()), {"holder", "shares", "percent"})

    def test_extract_principal_holders_rejects_toc_only_table(self) -> None:
        html = """
        <html>
          <body>
            <table>
              <tr><td>1</td><td>Overview</td></tr>
              <tr><td>7</td><td>Principal and Selling Stockholders</td></tr>
              <tr><td>12</td><td>Risk Factors</td></tr>
            </table>
          </body>
        </html>
        """

        holders = extract_principal_holders(html)

        self.assertEqual(holders, [])

    def test_add_trading_days_skips_weekends(self) -> None:
        self.assertEqual(add_trading_days(date(2024, 8, 6), 3), date(2024, 8, 9))
        self.assertEqual(add_trading_days(date(2024, 8, 8), 3), date(2024, 8, 13))

    @patch("ipo_tracker.sec.find_earnings_release_filing")
    def test_determine_effective_unlock_date_prefers_earlier_earnings_trigger(self, release_filing_mock) -> None:
        release_filing_mock.return_value = ("2024-08-06", "https://www.sec.gov/example-earnings-8k")
        conditions = LockupConditions(
            lockup_days=180,
            lockup_source="Lock-Up Agreements section: Regex match: 180 days",
            has_early_release=True,
            has_earnings_trigger=True,
            earnings_release_quarter_end="2024-06-30",
        )

        effective_date, release_date, release_url, source = determine_effective_unlock_date(
            1713445,
            conditions,
            calendar_unlock_date=date(2024, 9, 17),
        )

        self.assertEqual(effective_date, date(2024, 8, 9))
        self.assertEqual(release_date, "2024-08-06")
        self.assertEqual(release_url, "https://www.sec.gov/example-earnings-8k")
        self.assertIn("Earnings trigger", source or "")

    def test_calculate_price_change_pct_uses_signed_direction(self) -> None:
        down_move = calculate_price_change_pct(62.03, 29.0)
        up_move = calculate_price_change_pct(29.0, 62.03)

        self.assertIsNotNone(down_move)
        self.assertIsNotNone(up_move)
        self.assertLess(down_move, 0)
        self.assertGreater(up_move, 0)
        self.assertAlmostEqual(down_move, -53.27, places=2)
        self.assertAlmostEqual(up_move, 113.90, places=2)

    def test_assess_data_confidence_rewards_live_parsing(self) -> None:
        score, label, details = assess_data_confidence(
            filing_form="424B4",
            lockup_source="Lock-Up Agreements section: Regex match: 180 days",
            principal_holders=[{"holder": "Sequoia Capital", "shares": 123}],
            parsed_ipo_date="2024-03-21",
            source_url="https://www.sec.gov/example",
        )

        self.assertGreaterEqual(score, 80)
        self.assertEqual(label, "High")
        self.assertIn("Matched filing form 424B4", details)
        self.assertIn("Parsed 1 principal holder rows", details)

    def test_assess_data_confidence_penalizes_seeded_fallbacks(self) -> None:
        score, label, details = assess_data_confidence(
            filing_form=None,
            lockup_source="Seeded watchlist only",
            principal_holders=[],
            parsed_ipo_date=None,
            source_url=None,
        )

        self.assertLess(score, 50)
        self.assertEqual(label, "Low")
        self.assertIn("No filing URL found", details)
        self.assertIn("Principal holder table not cleanly parsed", details)


if __name__ == "__main__":
    unittest.main()
