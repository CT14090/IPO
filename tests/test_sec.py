from __future__ import annotations

import unittest

from ipo_tracker.config import DEFAULT_LOCKUP_DAYS
from ipo_tracker.sec import extract_lockup_days, extract_principal_holders


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


if __name__ == "__main__":
    unittest.main()
