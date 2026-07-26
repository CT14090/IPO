from __future__ import annotations

import unittest

from ipo_tracker.config import DEFAULT_LOCKUP_DAYS
from ipo_tracker.market import calculate_price_change_pct
from ipo_tracker.sec import assess_data_confidence, extract_lockup_conditions, extract_lockup_days, extract_principal_holders


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
