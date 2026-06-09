from __future__ import annotations

import unittest
from ipo_tracker.config import DEFAULT_LOCKUP_DAYS


def _make_html(body: str) -> str:
    return f"<html><body>{body}</body></html>"


class TestGreenshoeFix(unittest.TestCase):

    def setUp(self):
        from ipo_tracker.sec import extract_lockup_days
        self.extract = extract_lockup_days

    def test_does_not_match_30_day_overallotment_option(self):
        html = _make_html(
            "<h2>Underwriting</h2>"
            "<p>The underwriters have the option to purchase up to an additional "
            "2,970,000 shares from us at the initial public offering price, less "
            "the underwriting discount, for 30 days after the date of this "
            "prospectus.</p>"
        )
        days, source = self.extract(html)
        self.assertNotEqual(days, 30)

    def test_matches_180_day_lockup_when_both_sections_present(self):
        html = _make_html(
            "<h2>Underwriting</h2>"
            "<p>The underwriters have a 30-day option to purchase additional shares.</p>"
            "<h3>Lock-Up Agreements</h3>"
            "<p>Our officers and directors agreed not to sell for a period of "
            "180 days after the date of this prospectus.</p>"
        )
        days, source = self.extract(html)
        self.assertEqual(days, 180)

    def test_full_document_fallback_rejects_30_day_option(self):
        html = _make_html(
            "<p>The underwriters have an option to purchase additional shares for "
            "30 days after the date of this prospectus to cover overallotments.</p>"
        )
        days, source = self.extract(html)
        self.assertGreaterEqual(days, 60)


class TestDualTriggerFix(unittest.TestCase):

    def setUp(self):
        from ipo_tracker.sec import extract_lockup_conditions
        self.extract_cond = extract_lockup_conditions

    def test_detects_dual_trigger_structure(self):
        html = _make_html(
            "<h2>Lock-Up Agreements</h2>"
            "<p>Each holder agreed not to sell for a period ending on the "
            "earlier of (i) 180 days after March 19, 2024 and (ii) the "
            "opening of trading on the second trading day immediately following "
            "the Company's release of earnings for the quarter ending June 30, 2024.</p>"
        )
        cond = self.extract_cond(html)
        self.assertEqual(cond.lockup_days, 180)
        self.assertTrue(cond.has_early_release)
        self.assertTrue(cond.has_earnings_trigger)

    def test_detects_early_release_percentage(self):
        html = _make_html(
            "<h2>Lock-Up Agreements</h2>"
            "<p>The lock-up period is 180 days after the date of this prospectus. "
            "The Lock-Up Period will terminate with respect to 20% of eligible "
            "securities if the closing price is at least 25% greater than the "
            "IPO price for 5 out of 10 consecutive trading days.</p>"
        )
        cond = self.extract_cond(html)
        self.assertEqual(cond.lockup_days, 180)
        self.assertTrue(cond.has_early_release)
        self.assertEqual(cond.early_release_pct, 20)

    def test_no_false_positive_on_simple_lockup(self):
        html = _make_html(
            "<h2>Lock-Up Agreements</h2>"
            "<p>Our officers have agreed not to sell any shares for a period of "
            "180 days after the date of this prospectus.</p>"
        )
        cond = self.extract_cond(html)
        self.assertEqual(cond.lockup_days, 180)
        self.assertFalse(cond.has_early_release)
        self.assertFalse(cond.has_earnings_trigger)


class TestIPODateCoverPage(unittest.TestCase):

    def setUp(self):
        from ipo_tracker.sec import extract_ipo_date_from_text
        self.extract_date = extract_ipo_date_from_text

    def test_parses_cover_page_date(self):
        html = _make_html("<p>The date of this prospectus is March 19, 2024</p>")
        self.assertEqual(self.extract_date(html), "2024-03-19")

    def test_parses_cover_page_date_case_insensitive(self):
        html = _make_html("<p>the date of this prospectus is September 14, 2023</p>")
        self.assertEqual(self.extract_date(html), "2023-09-14")

    def test_existing_pattern_still_works(self):
        html = _make_html("<p>Our common stock began trading on April 25, 2024 on the Nasdaq.</p>")
        self.assertEqual(self.extract_date(html), "2024-04-25")

    def test_returns_none_when_no_date_found(self):
        html = _make_html("<p>No date information here.</p>")
        self.assertIsNone(self.extract_date(html))


class TestALABScenario(unittest.TestCase):

    ALAB_HTML = _make_html(
        "<p>The date of this prospectus is March 19, 2024</p>"
        "<h2>Underwriting</h2>"
        "<p>The underwriters have the option to purchase up to an additional "
        "2,970,000 shares at the IPO price, less the underwriting discount, "
        "for 30 days after the date of this prospectus.</p>"
        "<h2>Lock-Up Agreements</h2>"
        "<p>Each of our officers, directors, and holders of substantially all "
        "of our common stock have agreed not to sell for a period ending on the "
        "earlier of (i) 180 days after March 19, 2024 and (ii) the opening of "
        "trading on the second trading day immediately following the Company's "
        "release of earnings for the quarter ending June 30, 2024, subject to "
        "certain exceptions. The Lock-Up Period will terminate with respect to "
        "20% of eligible securities if certain price conditions are met.</p>"
    )

    def test_lockup_days_correct(self):
        from ipo_tracker.sec import extract_lockup_conditions
        cond = extract_lockup_conditions(self.ALAB_HTML)
        self.assertEqual(cond.lockup_days, 180)

    def test_dual_trigger_detected(self):
        from ipo_tracker.sec import extract_lockup_conditions
        cond = extract_lockup_conditions(self.ALAB_HTML)
        self.assertTrue(cond.has_early_release)
        self.assertTrue(cond.has_earnings_trigger)

    def test_early_release_pct_detected(self):
        from ipo_tracker.sec import extract_lockup_conditions
        cond = extract_lockup_conditions(self.ALAB_HTML)
        self.assertEqual(cond.early_release_pct, 20)

    def test_ipo_date_from_cover(self):
        from ipo_tracker.sec import extract_ipo_date_from_text
        self.assertEqual(extract_ipo_date_from_text(self.ALAB_HTML), "2024-03-19")

    def test_source_is_lockup_section_not_underwriting(self):
        from ipo_tracker.sec import extract_lockup_conditions
        cond = extract_lockup_conditions(self.ALAB_HTML)
        self.assertIn("Lock-Up", cond.lockup_source)
        self.assertNotIn("Underwriting", cond.lockup_source)


class TestBackwardsCompatibility(unittest.TestCase):

    def test_extract_lockup_days_from_lockup_section(self):
        from ipo_tracker.sec import extract_lockup_days
        html = _make_html(
            "<h2>Lock-Up Agreements</h2>"
            "<p>The underwriters and selling stockholders agreed to restrictions "
            "for a period of 180 days after the date of this prospectus.</p>"
        )
        days, source = extract_lockup_days(html)
        self.assertEqual(days, 180)
        self.assertIn("Lock-Up Agreements section", source)

    def test_extract_lockup_days_defaults_when_text_is_unclear(self):
        from ipo_tracker.sec import extract_lockup_days
        days, source = extract_lockup_days(
            "<html><body><p>No usable lockup language here.</p></body></html>"
        )
        self.assertEqual(days, DEFAULT_LOCKUP_DAYS)
        self.assertIn("Defaulted to 180 days", source)


if __name__ == "__main__":
    unittest.main()
