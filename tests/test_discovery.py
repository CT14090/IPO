from __future__ import annotations

import unittest

from ipo_tracker.discovery import parse_discovery_candidates


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


if __name__ == "__main__":
    unittest.main()
