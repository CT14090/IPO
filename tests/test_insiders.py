from __future__ import annotations

import unittest
from unittest.mock import patch

from ipo_tracker.insiders import (
    fetch_post_unlock_sales,
    parse_form4_sales,
    summarize_insider_sales,
)


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
    @patch("ipo_tracker.insiders.iter_submission_records")
    def test_fetch_post_unlock_sales_filters_pre_unlock_filings_and_trades(self, iter_records_mock, fetch_text_mock) -> None:
        iter_records_mock.return_value = [
            {
                "form": "4",
                "accession_number": "0001111111-24-000001",
                "primary_document": "sale-one.xml",
                "filing_date": "2024-09-20",
            },
            {
                "form": "4/A",
                "accession_number": "0001111111-24-000002",
                "primary_document": "sale-two.xml",
                "filing_date": "2024-09-16",
            },
            {
                "form": "10-Q",
                "accession_number": "0001111111-24-000003",
                "primary_document": "quarterly.htm",
                "filing_date": "2024-09-21",
            },
        ]
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

        sales = fetch_post_unlock_sales(1736297, "2024-09-15")

        self.assertEqual(len(sales), 1)
        self.assertEqual(sales[0]["transaction_date"], "2024-09-19")
        self.assertEqual(sales[0]["shares_sold"], 12_000)
        self.assertIn("sale-one.xml", sales[0]["source_url"])

    @patch("ipo_tracker.sec.fetch_text")
    @patch("ipo_tracker.insiders.iter_submission_records")
    def test_fetch_post_unlock_sales_reads_archived_submission_fragments(self, iter_records_mock, fetch_text_mock) -> None:
        iter_records_mock.return_value = [
            {
                "form": "4",
                "accession_number": "0001111111-24-000111",
                "primary_document": "archived-form4.xml",
                "filing_date": "2024-09-20",
            }
        ]
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

        sales = fetch_post_unlock_sales(1111111, "2024-09-15")

        self.assertEqual(len(sales), 1)
        self.assertEqual(sales[0]["owner_name"], "Archived Insider")
        self.assertEqual(sales[0]["shares_sold"], 9_000)
        self.assertIn("archived-form4.xml", sales[0]["source_url"])

    @patch("ipo_tracker.sec.fetch_text")
    @patch("ipo_tracker.insiders.iter_submission_records")
    def test_fetch_post_unlock_sales_uses_xml_companion_when_primary_document_is_html(self, iter_records_mock, fetch_text_mock) -> None:
        iter_records_mock.return_value = [
            {
                "form": "4",
                "accession_number": "0001111111-24-000222",
                "primary_document": "form4.html",
                "filing_date": "2024-09-20",
            }
        ]
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

        sales = fetch_post_unlock_sales(1111111, "2024-09-15")

        self.assertEqual(len(sales), 1)
        self.assertEqual(sales[0]["owner_name"], "HTML Backed Insider")
        self.assertIn("form4.xml", sales[0]["source_url"])

    def test_summarize_insider_sales_totals_transactions_and_shares(self) -> None:
        summary = summarize_insider_sales(
            [
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
