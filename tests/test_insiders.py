from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import requests

from ipo_tracker.insiders import (
    fetch_post_unlock_sales,
    parse_form4_sales,
    split_insider_sales_records,
    summarize_insider_sales,
)


def _feed_response(xml_text: str) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.text = xml_text
    return response


def _http_error(status_code: int, reason: str = "Too Many Requests") -> requests.HTTPError:
    response = MagicMock()
    response.status_code = status_code
    response.reason = reason
    response.headers = {}
    error = requests.HTTPError(f"{status_code} Client Error: {reason}")
    error.response = response
    return error


class InsiderSalesTests(unittest.TestCase):
    def test_parse_form4_sales_keeps_only_sale_transactions(self) -> None:
        xml = """
        <ownershipDocument>
          <periodOfReport>2024-09-20</periodOfReport>
          <reportingOwner>
            <reportingOwnerId>
              <rptOwnerName>Jane Insider</rptOwnerName>
            </reportingOwnerId>
          </reportingOwner>
          <nonDerivativeTable>
            <nonDerivativeTransaction>
              <securityTitle><value>Common Stock</value></securityTitle>
              <transactionDate><value>2024-09-19</value></transactionDate>
              <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
              <transactionAmounts>
                <transactionShares><value>15000</value></transactionShares>
                <transactionPricePerShare><value>31.25</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
              </transactionAmounts>
              <postTransactionAmounts>
                <sharesOwnedFollowingTransaction><value>85000</value></sharesOwnedFollowingTransaction>
              </postTransactionAmounts>
              <ownershipNature>
                <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
              </ownershipNature>
            </nonDerivativeTransaction>
            <nonDerivativeTransaction>
              <securityTitle><value>Common Stock</value></securityTitle>
              <transactionDate><value>2024-09-18</value></transactionDate>
              <transactionCoding><transactionCode>A</transactionCode></transactionCoding>
              <transactionAmounts>
                <transactionShares><value>5000</value></transactionShares>
                <transactionPricePerShare><value>28.10</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
              </transactionAmounts>
            </nonDerivativeTransaction>
          </nonDerivativeTable>
        </ownershipDocument>
        """

        sales = parse_form4_sales(
            xml,
            filing_date="2024-09-20",
            source_url="https://www.sec.gov/example-form4.xml",
            form="4",
        )

        self.assertEqual(len(sales), 1)
        self.assertEqual(sales[0]["owner_name"], "Jane Insider")
        self.assertEqual(sales[0]["transaction_date"], "2024-09-19")
        self.assertEqual(sales[0]["shares_sold"], 15_000)
        self.assertEqual(sales[0]["price_per_share"], 31.25)
        self.assertEqual(sales[0]["shares_owned_following_transaction"], 85_000)
        self.assertEqual(sales[0]["ownership_type"], "D")
        self.assertEqual(sales[0]["transaction_code"], "S")

    @patch("ipo_tracker.sec.fetch_text")
    @patch("ipo_tracker.insiders.requests.get")
    def test_fetch_post_unlock_sales_filters_pre_unlock_filings_and_trades(self, mock_get, fetch_text_mock) -> None:
        mock_get.return_value = _feed_response(
            """
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>4 - Example Issuer</title>
                <updated>2024-09-20T18:00:00-04:00</updated>
                <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/1736297/000111111124000001/sale-one.xml" />
              </entry>
              <entry>
                <title>4/A - Example Issuer</title>
                <updated>2024-09-16T18:00:00-04:00</updated>
                <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/1736297/000111111124000002/sale-two.xml" />
              </entry>
            </feed>
            """
        )
        fetch_text_mock.side_effect = [
            """
            <ownershipDocument>
              <periodOfReport>2024-09-20</periodOfReport>
              <reportingOwner>
                <reportingOwnerId><rptOwnerName>Jane Insider</rptOwnerName></reportingOwnerId>
              </reportingOwner>
              <nonDerivativeTable>
                <nonDerivativeTransaction>
                  <transactionDate><value>2024-09-19</value></transactionDate>
                  <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
                  <transactionAmounts>
                    <transactionShares><value>12000</value></transactionShares>
                    <transactionPricePerShare><value>30.50</value></transactionPricePerShare>
                    <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
                  </transactionAmounts>
                </nonDerivativeTransaction>
              </nonDerivativeTable>
            </ownershipDocument>
            """,
            """
            <ownershipDocument>
              <periodOfReport>2024-09-16</periodOfReport>
              <reportingOwner>
                <reportingOwnerId><rptOwnerName>Jane Insider</rptOwnerName></reportingOwnerId>
              </reportingOwner>
              <nonDerivativeTable>
                <nonDerivativeTransaction>
                  <transactionDate><value>2024-09-10</value></transactionDate>
                  <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
                  <transactionAmounts>
                    <transactionShares><value>7000</value></transactionShares>
                    <transactionPricePerShare><value>29.75</value></transactionPricePerShare>
                    <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
                  </transactionAmounts>
                </nonDerivativeTransaction>
              </nonDerivativeTable>
            </ownershipDocument>
            """,
        ]

        records = fetch_post_unlock_sales(1736297, "2024-09-15")
        lookup, sales = split_insider_sales_records(records)

        self.assertEqual(lookup["status"], "sales_parsed")
        self.assertEqual(lookup["candidate_filings"], 2)
        self.assertEqual(lookup["transactions_parsed"], 1)
        self.assertEqual(len(sales), 1)
        self.assertEqual(sales[0]["transaction_date"], "2024-09-19")
        self.assertEqual(sales[0]["shares_sold"], 12_000)
        self.assertIn("sale-one.xml", sales[0]["source_url"])

    @patch("ipo_tracker.sec.fetch_text")
    @patch("ipo_tracker.insiders.requests.get")
    def test_fetch_post_unlock_sales_handles_direct_xml_filing_links(self, mock_get, fetch_text_mock) -> None:
        mock_get.return_value = _feed_response(
            """
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>4 - Archived Issuer</title>
                <updated>2024-09-20T18:00:00-04:00</updated>
                <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/1111111/000111111124000111/archived-form4.xml" />
              </entry>
            </feed>
            """
        )
        fetch_text_mock.return_value = """
        <ownershipDocument>
          <periodOfReport>2024-09-20</periodOfReport>
          <reportingOwner>
            <reportingOwnerId><rptOwnerName>Archived Insider</rptOwnerName></reportingOwnerId>
          </reportingOwner>
          <nonDerivativeTable>
            <nonDerivativeTransaction>
              <transactionDate><value>2024-09-19</value></transactionDate>
              <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
              <transactionAmounts>
                <transactionShares><value>9000</value></transactionShares>
                <transactionPricePerShare><value>30.00</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
              </transactionAmounts>
            </nonDerivativeTransaction>
          </nonDerivativeTable>
        </ownershipDocument>
        """

        records = fetch_post_unlock_sales(1111111, "2024-09-15")
        lookup, sales = split_insider_sales_records(records)

        self.assertEqual(lookup["status"], "sales_parsed")
        self.assertEqual(len(sales), 1)
        self.assertEqual(sales[0]["owner_name"], "Archived Insider")
        self.assertEqual(sales[0]["shares_sold"], 9_000)
        self.assertIn("archived-form4.xml", sales[0]["source_url"])

    @patch("ipo_tracker.sec.fetch_text")
    @patch("ipo_tracker.insiders.requests.get")
    def test_fetch_post_unlock_sales_uses_xml_companion_when_feed_points_to_html(self, mock_get, fetch_text_mock) -> None:
        mock_get.return_value = _feed_response(
            """
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>4 - HTML Backed Issuer</title>
                <updated>2024-09-20T18:00:00-04:00</updated>
                <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/2222222/000111111124000222/form4.html" />
              </entry>
            </feed>
            """
        )
        fetch_text_mock.side_effect = [
            """
            <ownershipDocument>
              <periodOfReport>2024-09-20</periodOfReport>
              <reportingOwner>
                <reportingOwnerId><rptOwnerName>HTML Backed Insider</rptOwnerName></reportingOwnerId>
              </reportingOwner>
              <nonDerivativeTable>
                <nonDerivativeTransaction>
                  <transactionDate><value>2024-09-19</value></transactionDate>
                  <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
                  <transactionAmounts>
                    <transactionShares><value>6000</value></transactionShares>
                    <transactionPricePerShare><value>27.50</value></transactionPricePerShare>
                    <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
                  </transactionAmounts>
                </nonDerivativeTransaction>
              </nonDerivativeTable>
            </ownershipDocument>
            """,
        ]

        records = fetch_post_unlock_sales(2222222, "2024-09-15")
        lookup, sales = split_insider_sales_records(records)

        self.assertEqual(lookup["status"], "sales_parsed")
        self.assertEqual(len(sales), 1)
        self.assertEqual(sales[0]["owner_name"], "HTML Backed Insider")
        self.assertIn("form4.xml", sales[0]["source_url"])

    @patch("ipo_tracker.insiders.requests.get")
    def test_fetch_post_unlock_sales_returns_lookup_metadata_when_no_feed_entries_qualify(self, mock_get) -> None:
        mock_get.return_value = _feed_response(
            """
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>4 - Example Issuer</title>
                <updated>2024-09-10T18:00:00-04:00</updated>
                <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/3333333/000111111124000333/form4.xml" />
              </entry>
            </feed>
            """
        )

        records = fetch_post_unlock_sales(3333333, "2024-09-15")
        lookup, sales = split_insider_sales_records(records)

        self.assertEqual(lookup["status"], "no_form4_filings_after_unlock")
        self.assertEqual(lookup["candidate_filings"], 0)
        self.assertEqual(sales, [])

    @patch("ipo_tracker.insiders.time.sleep")
    @patch("ipo_tracker.sec.fetch_text")
    @patch("ipo_tracker.insiders.requests.get")
    def test_fetch_post_unlock_sales_retries_rate_limited_feed_then_succeeds(self, mock_get, fetch_text_mock, sleep_mock) -> None:
        throttled = MagicMock()
        throttled.raise_for_status.side_effect = _http_error(429)
        success = _feed_response(
            """
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>4 - Retry Issuer</title>
                <updated>2024-09-20T18:00:00-04:00</updated>
                <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/7777777/000111111124000777/retry-sale.xml" />
              </entry>
            </feed>
            """
        )
        mock_get.side_effect = [throttled, success]
        fetch_text_mock.return_value = """
        <ownershipDocument>
          <periodOfReport>2024-09-20</periodOfReport>
          <reportingOwner>
            <reportingOwnerId><rptOwnerName>Retry Insider</rptOwnerName></reportingOwnerId>
          </reportingOwner>
          <nonDerivativeTable>
            <nonDerivativeTransaction>
              <transactionDate><value>2024-09-19</value></transactionDate>
              <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
              <transactionAmounts>
                <transactionShares><value>10000</value></transactionShares>
                <transactionPricePerShare><value>31.00</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
              </transactionAmounts>
            </nonDerivativeTransaction>
          </nonDerivativeTable>
        </ownershipDocument>
        """

        records = fetch_post_unlock_sales(7777777, "2024-09-15")
        lookup, sales = split_insider_sales_records(records)

        self.assertEqual(lookup["status"], "sales_parsed")
        self.assertEqual(len(sales), 1)
        self.assertEqual(sales[0]["owner_name"], "Retry Insider")
        self.assertGreaterEqual(sleep_mock.call_count, 1)
        self.assertTrue(any(call.args == (1.0,) for call in sleep_mock.call_args_list))
        self.assertEqual(mock_get.call_count, 2)

    @patch("ipo_tracker.insiders.time.sleep")
    @patch("ipo_tracker.insiders.requests.get")
    def test_fetch_post_unlock_sales_reports_feed_error_after_repeated_rate_limits(self, mock_get, sleep_mock) -> None:
        throttled = MagicMock()
        throttled.raise_for_status.side_effect = _http_error(429)
        mock_get.side_effect = [throttled, throttled, throttled]

        records = fetch_post_unlock_sales(8888888, "2024-09-15")
        lookup, sales = split_insider_sales_records(records)

        self.assertEqual(lookup["status"], "feed_error")
        self.assertEqual(lookup["candidate_filings"], 0)
        self.assertEqual(sales, [])
        self.assertGreaterEqual(sleep_mock.call_count, 2)
        self.assertTrue(any(call.args == (1.0,) for call in sleep_mock.call_args_list))
        self.assertTrue(any(call.args == (2.0,) for call in sleep_mock.call_args_list))
        self.assertEqual(mock_get.call_count, 3)

    @patch("ipo_tracker.sec.fetch_text")
    @patch("ipo_tracker.insiders.requests.get")
    def test_fetch_post_unlock_sales_reuses_existing_sales_when_no_new_filings(self, mock_get, fetch_text_mock) -> None:
        mock_get.return_value = _feed_response(
            """
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>4 - Example Issuer</title>
                <updated>2024-09-20T18:00:00-04:00</updated>
                <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/4444444/000111111124000444/reused.xml" />
              </entry>
            </feed>
            """
        )
        existing_records = [
            {
                "_lookup": {
                    "status": "sales_parsed",
                    "unlock_date": "2024-09-15",
                    "latest_filing_date": "2024-09-20",
                }
            },
            {
                "owner_name": "Existing Insider",
                "transaction_date": "2024-09-19",
                "shares_sold": 11_000,
                "price_per_share": 32.5,
                "ownership_type": "D",
                "filing_date": "2024-09-20",
                "period_of_report": "2024-09-20",
                "form": "4",
                "source_url": "https://www.sec.gov/Archives/edgar/data/4444444/000111111124000444/reused.xml",
            },
        ]

        records = fetch_post_unlock_sales(
            4444444,
            "2024-09-15",
            existing_records=existing_records,
        )
        lookup, sales = split_insider_sales_records(records)

        self.assertEqual(lookup["status"], "sales_reused")
        self.assertEqual(lookup["candidate_filings"], 0)
        self.assertEqual(lookup["documents_fetched"], 0)
        self.assertEqual(lookup["transactions_parsed"], 1)
        self.assertEqual(lookup["reused_transactions"], 1)
        self.assertEqual(len(sales), 1)
        fetch_text_mock.assert_not_called()

    @patch("ipo_tracker.sec.fetch_text")
    @patch("ipo_tracker.insiders.requests.get")
    def test_fetch_post_unlock_sales_merges_new_sales_into_existing_history(self, mock_get, fetch_text_mock) -> None:
        mock_get.return_value = _feed_response(
            """
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>4 - Example Issuer</title>
                <updated>2024-09-21T18:00:00-04:00</updated>
                <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/5555555/000111111124000555/new-sale.xml" />
              </entry>
              <entry>
                <title>4 - Example Issuer</title>
                <updated>2024-09-20T18:00:00-04:00</updated>
                <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/5555555/000111111124000554/old-sale.xml" />
              </entry>
            </feed>
            """
        )
        fetch_text_mock.return_value = """
        <ownershipDocument>
          <periodOfReport>2024-09-21</periodOfReport>
          <reportingOwner>
            <reportingOwnerId><rptOwnerName>New Insider</rptOwnerName></reportingOwnerId>
          </reportingOwner>
          <nonDerivativeTable>
            <nonDerivativeTransaction>
              <transactionDate><value>2024-09-20</value></transactionDate>
              <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
              <transactionAmounts>
                <transactionShares><value>9000</value></transactionShares>
                <transactionPricePerShare><value>33.10</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
              </transactionAmounts>
            </nonDerivativeTransaction>
          </nonDerivativeTable>
        </ownershipDocument>
        """
        existing_records = [
            {
                "_lookup": {
                    "status": "sales_parsed",
                    "unlock_date": "2024-09-15",
                    "latest_filing_date": "2024-09-20",
                }
            },
            {
                "owner_name": "Existing Insider",
                "transaction_date": "2024-09-19",
                "shares_sold": 11_000,
                "price_per_share": 32.5,
                "ownership_type": "D",
                "filing_date": "2024-09-20",
                "period_of_report": "2024-09-20",
                "form": "4",
                "source_url": "https://www.sec.gov/Archives/edgar/data/5555555/000111111124000554/old-sale.xml",
            },
        ]

        records = fetch_post_unlock_sales(
            5555555,
            "2024-09-15",
            existing_records=existing_records,
        )
        lookup, sales = split_insider_sales_records(records)

        self.assertEqual(lookup["status"], "sales_parsed")
        self.assertEqual(lookup["candidate_filings"], 1)
        self.assertEqual(lookup["documents_fetched"], 1)
        self.assertEqual(lookup["new_transactions_parsed"], 1)
        self.assertEqual(lookup["transactions_parsed"], 2)
        self.assertEqual(len(sales), 2)
        self.assertEqual(sales[0]["owner_name"], "New Insider")
        self.assertEqual(sales[0]["shares_sold"], 9_000)

    def test_summarize_insider_sales_ignores_lookup_metadata(self) -> None:
        summary = summarize_insider_sales(
            [
                {"_lookup": {"status": "sales_parsed", "candidate_filings": 2}},
                {
                    "transaction_date": "2024-09-19",
                    "shares_sold": 12_000,
                    "source_url": "https://www.sec.gov/form4-one.xml",
                },
                {
                    "transaction_date": "2024-09-18",
                    "shares_sold": 8_000,
                    "source_url": "https://www.sec.gov/form4-two.xml",
                },
                {
                    "transaction_date": "2024-09-17",
                    "shares_sold": 5_000,
                    "source_url": "https://www.sec.gov/form4-two.xml",
                },
            ]
        )

        self.assertEqual(summary["transaction_count"], 3)
        self.assertEqual(summary["filing_count"], 2)
        self.assertEqual(summary["total_shares_sold"], 25_000)
        self.assertEqual(summary["latest_sale_date"], "2024-09-19")


if __name__ == "__main__":
    unittest.main()
