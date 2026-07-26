from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ipo_tracker.discovery import _resolve_company_identity, _search_efts, parse_discovery_candidates


class DiscoveryTests(unittest.TestCase):
    def test_parse_discovery_candidates_filters_watchlist_entries(self) -> None:
        feed_xml = """
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>424B4 - Example Holdings Inc.</title>
            <summary>CIK: 0000123456 | Form 424B4 | Initial public offering</summary>
            <published>2026-05-01</published>
            <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/123456/000119312526000001/0001193125-26-000001-index.html" />
          </entry>
          <entry>
            <title>424B4 - Already Watched Co.</title>
            <summary>CIK: 00001713445 | Form 424B4</summary>
            <published>2026-05-02</published>
            <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/1713445/000119312526000002/0001193125-26-000002-index.html" />
          </entry>
        </feed>
        """

        candidates = parse_discovery_candidates(
            feed_xml,
            form="424B4",
            watched_ciks={1713445},
            company_index={123456: {"ticker": "EXMP", "title": "Example Holdings Inc.", "exchange": "NASDAQ"}},
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.company_name, "Example Holdings Inc.")
        self.assertEqual(candidate.ticker, "EXMP")
        self.assertEqual(candidate.cik, 123456)
        self.assertEqual(candidate.form, "424B4")
        self.assertEqual(candidate.confidence, "High")
        self.assertIn("initial public offering", candidate.reason.lower())

    @patch("ipo_tracker.discovery.fetch_submission_profile")
    def test_resolve_company_identity_treats_unknown_values_as_missing(self, fetch_profile: MagicMock) -> None:
        fetch_profile.return_value = {
            "title": "Unknown",
            "ticker": "",
            "exchange": "",
        }

        name, ticker, exchange, source = _resolve_company_identity(123456, {})

        self.assertEqual(name, "CIK 123456")
        self.assertIsNone(ticker)
        self.assertEqual(exchange, "")
        self.assertIn("submissions profile", source)

    @patch("ipo_tracker.discovery.fetch_submission_profile")
    @patch("ipo_tracker.discovery.requests.get")
    def test_search_efts_uses_source_entity_name_when_profile_title_is_blank(
        self,
        mock_get: MagicMock,
        fetch_profile: MagicMock,
    ) -> None:
        fetch_profile.return_value = {
            "title": "",
            "ticker": "",
            "exchange": "",
        }

        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "0000123456-26-000001",
                        "_source": {
                            "entity_name": "Example Holdings Inc.",
                            "company_name": "",
                            "file_date": "2026-07-21",
                            "form": "424B4",
                        },
                    }
                ]
            }
        }
        mock_get.return_value = response

        candidates = _search_efts(watched_ciks=set(), company_index={})

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.company_name, "Example Holdings Inc.")
        self.assertEqual(candidate.form, "424B4")
        self.assertEqual(candidate.ticker, "")
        self.assertEqual(candidate.confidence, "Medium")

    @patch("ipo_tracker.discovery.fetch_submission_profile")
    @patch("ipo_tracker.discovery.requests.get")
    def test_search_efts_skips_nameless_candidates(
        self,
        mock_get: MagicMock,
        fetch_profile: MagicMock,
    ) -> None:
        fetch_profile.return_value = {
            "title": "",
            "ticker": "",
            "exchange": "",
        }

        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "0000999999-26-000001",
                        "_source": {
                            "entity_name": "Unknown",
                            "company_name": "",
                            "file_date": "2026-07-21",
                            "form": "424B4",
                        },
                    }
                ]
            }
        }
        mock_get.return_value = response

        candidates = _search_efts(watched_ciks=set(), company_index={})

        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
