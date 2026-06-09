from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from html import unescape
from io import StringIO
from typing import Any

import pandas as pd
import requests

from .config import DEFAULT_LOCKUP_DAYS


SEC_BASE_HEADERS = {
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

IPO_FORMS = {"424B4", "424B1", "424B3", "S-1", "S-1/A", "F-1", "F-1/A"}

# ── Fix 1 ──────────────────────────────────────────────────────────────────────
# "underwriting" removed from this list.  It will never be used as a lockup
# section source; it contains the greenshoe/overallotment language that was
# causing false 30-day matches.
LOCKUP_SECTION_HEADINGS = (
    "lock-up agreements",
    "lockup agreements",
    "lock-up period",
    "lockup period",
    "lock-up restrictions",
    "shares eligible for future sale",
)

# "underwriting" is kept separately so the full-document fallback can still
# reach it as a last resort, but with the overallotment guard applied.
UNDERWRITING_HEADING = "underwriting"

# Signals that a day-count match is inside greenshoe/overallotment language.
_OVERALLOTMENT_RE = re.compile(
    r"(option to purchase|overallotment|over-allotment|purchase additional"
    r"|additional shares.*?underwriter|underwriter.*?additional shares)",
    re.I,
)

PRINCIPAL_TABLE_MATCHES = (
    "Principal and Selling Stockholders",
    "Principal Stockholders",
    "Principal and Executive Stockholders",
    "Beneficial Owner",
    "Beneficial Ownership",
    "Selling Stockholders",
)

HOLDER_PLACEHOLDERS = {
    "beneficial owner", "beneficial owners", "holder", "holders", "name",
    "name of beneficial owner", "principal stockholder", "principal stockholders",
    "selling stockholder", "selling stockholders", "stockholder", "stockholders",
    "shareholder", "shareholders", "total",
}

# ── Fix 3 ──────────────────────────────────────────────────────────────────────
# Keywords used when scanning post-IPO 8-K filings for lock-up amendments.
_LOCKUP_AMENDMENT_RE = re.compile(
    r"(lock[- ]up|restricted period|lockup|early release|lock up period"
    r"|lock-up period will terminate|restricted period.*?end)",
    re.I,
)

# ── Fix 2 ──────────────────────────────────────────────────────────────────────
# Patterns that detect conditional / dual-trigger expiry language.
_EARLY_RELEASE_RE = re.compile(
    r"(earlier of|early release|lock[- ]up period will terminate"
    r"|restricted period.*?end|price condition"
    r"|trading day.*?following.*?earnings|earnings.*?trading day"
    r"|\d+%.*?greater than the ipo price)",
    re.I,
)
# Two separate patterns — earnings trigger is detected when BOTH appear within
# a 400-char window, in either order (the ALAB prospectus has trading-day before earnings).
_EARNINGS_KEYWORD_RE = re.compile(
    r"(earnings|quarterly results|financial results)",
    re.I,
)
_TRADING_DAY_RE = re.compile(
    r"(trading day|trading date|second trading)",
    re.I,
)
_PERCENT_EARLY_RELEASE_RE = re.compile(
    r"(\d{1,3})%\s+of\s+(?:eligible\s+)?(?:securities|shares)",
    re.I,
)


@dataclass(slots=True)
class FilingReference:
    form: str
    filing_date: str
    accession_number: str
    primary_document: str
    filing_url: str


# ── Fix 2 ──────────────────────────────────────────────────────────────────────
@dataclass
class LockupConditions:
    """Structured representation of potentially complex lock-up terms."""
    lockup_days: int
    lockup_source: str
    has_early_release: bool = False
    early_release_description: str = ""
    has_earnings_trigger: bool = False
    early_release_pct: int | None = None
    amendment_date: str | None = None        # set if sourced from 8-K
    amendment_url: str | None = None         # set if sourced from 8-K

    def notes_summary(self) -> str:
        parts = [f"Lock-up: {self.lockup_days} days ({self.lockup_source})"]
        if self.amendment_date:
            parts.append(f"Updated by 8-K filed {self.amendment_date}")
        if self.has_early_release:
            desc = self.early_release_description[:120] if self.early_release_description else ""
            pct = f" ({self.early_release_pct}% of shares)" if self.early_release_pct else ""
            parts.append(f"Early release clause detected{pct}: {desc}")
        if self.has_earnings_trigger:
            parts.append("Earnings-linked trigger present — actual unlock may precede calendar date")
        return " | ".join(parts)


def normalize_cik(cik: int | str) -> str:
    digits = re.sub(r"\D", "", str(cik))
    return digits.zfill(10)


def sec_headers() -> dict[str, str]:
    user_agent = os.environ.get("SEC_USER_AGENT", "IPO Lockup Tracker demo contact@example.com")
    return {**SEC_BASE_HEADERS, "User-Agent": user_agent}


def fetch_json(url: str) -> dict[str, Any]:
    response = requests.get(url, headers=sec_headers(), timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_text(url: str) -> str:
    response = requests.get(url, headers=sec_headers(), timeout=30)
    response.raise_for_status()
    return response.text


def submissions_url(cik: int | str) -> str:
    return f"https://data.sec.gov/submissions/CIK{normalize_cik(cik)}.json"


def filing_document_url(cik: int | str, accession_number: str, primary_document: str) -> str:
    cik_no_leading_zero = str(int(normalize_cik(cik)))
    accession_no_dashes = accession_number.replace("-", "")
    return (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_no_leading_zero}/{accession_no_dashes}/{primary_document}"
    )


def find_latest_ipo_filing(cik: int | str) -> FilingReference | None:
    submissions = fetch_json(submissions_url(cik))
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accession_numbers = recent.get("accessionNumber", [])
    primary_documents = recent.get("primaryDocument", [])
    filing_dates = recent.get("filingDate", [])

    for form, accession_number, primary_document, filing_date in zip(
        forms, accession_numbers, primary_documents, filing_dates
    ):
        if form not in IPO_FORMS:
            continue
        filing_url = filing_document_url(cik, accession_number, primary_document)
        return FilingReference(
            form=form,
            filing_date=filing_date,
            accession_number=accession_number,
            primary_document=primary_document,
            filing_url=filing_url,
        )
    return None


# ── Fix 3 ──────────────────────────────────────────────────────────────────────
def find_lockup_amendment_8k(
    cik: int | str,
    ipo_date: date,
) -> tuple[str | None, str | None, str | None]:
    """
    Scan 8-K / 8-K/A filings filed within 210 days of ipo_date for any that
    contain lock-up amendment language.

    Returns (filing_date, filing_url, relevant_excerpt) or (None, None, None).
    """
    try:
        submissions = fetch_json(submissions_url(cik))
    except requests.RequestException:
        return None, None, None

    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accession_numbers = recent.get("accessionNumber", [])
    primary_documents = recent.get("primaryDocument", [])
    filing_dates = recent.get("filingDate", [])
    cutoff = ipo_date + timedelta(days=210)

    for form, acc, doc, fdate in zip(forms, accession_numbers, primary_documents, filing_dates):
        if form not in {"8-K", "8-K/A"}:
            continue
        try:
            filing_dt = date.fromisoformat(fdate)
        except ValueError:
            continue
        if not (ipo_date <= filing_dt <= cutoff):
            continue
        url = filing_document_url(cik, acc, doc)
        try:
            html = fetch_text(url)
        except requests.RequestException:
            continue
        text = _strip_html(html)
        if _LOCKUP_AMENDMENT_RE.search(text):
            m = _LOCKUP_AMENDMENT_RE.search(text)
            start = max(0, m.start() - 50)
            excerpt = text[start : start + 400].strip()
            return fdate, url, excerpt

    return None, None, None


def _clean_cell_text(value: Any) -> str:
    text = unescape(str(value)).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _strip_html(html_text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html_text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _find_section_window(
    text: str,
    heading: str,
    before: int = 200,
    after: int = 2000,
) -> str | None:
    lowered = text.lower()
    index = lowered.find(heading)
    if index == -1:
        return None
    start = max(0, index - before)
    end = min(len(text), index + after)
    return text[start:end]


# ── Fix 1 + Fix 2 ──────────────────────────────────────────────────────────────
def _extract_lockup_days_from_window(
    text: str,
    *,
    allow_overallotment: bool = False,
) -> tuple[int | None, str | None]:
    """
    Extract a day count from a text window.

    When allow_overallotment=False (default), any match whose surrounding
    ~200-character context contains greenshoe/overallotment language is
    discarded to avoid the 30-day false positive.
    """
    patterns = [
        r"period ending[^.]{0,300}?(\d{2,3})\s+days",
        r"earlier of[^)]{0,200}?(\d{2,3})\s+days",
        r"for a period of\s+(\d{2,3})\s+days",
        r"period of\s+(\d{2,3})\s+days",
        r"(\d{2,3})\s+days after the date of this prospectus",
        r"(\d{2,3})\s+days from the date of this prospectus",
        r"(\d{2,3})[- ]day lock[- ]up",
        r"lock[- ]up(?:[^.]{0,300})?(\d{2,3})\s+days",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text, flags=re.I):
            days = int(m.group(1))
            if days < 60:
                if not allow_overallotment:
                    continue
            if not allow_overallotment:
                context_start = max(0, m.start() - 120)
                context_end = min(len(text), m.end() + 120)
                context = text[context_start:context_end]
                if _OVERALLOTMENT_RE.search(context):
                    continue
            return days, f"Regex match: {m.group(0)[:140]}"

    if re.search(r"one year", text, flags=re.I):
        return 365, "Detected one-year lock-up"
    return None, None


# ── Fix 2 ──────────────────────────────────────────────────────────────────────
def _has_earnings_trigger(text: str) -> bool:
    """Both 'earnings' and 'trading day' must appear within 400 chars of each other."""
    for m in _EARNINGS_KEYWORD_RE.finditer(text):
        window = text[max(0, m.start() - 300): m.end() + 300]
        if _TRADING_DAY_RE.search(window):
            return True
    return False


def _detect_early_release(section_text: str) -> tuple[bool, bool, int | None, str]:
    """
    Detect whether a lock-up section contains conditional / early-release terms.

    Returns:
        has_early_release: True if any early-exit language found
        has_earnings_trigger: True if an earnings-date trigger is present
        early_release_pct: percentage of shares subject to early release (or None)
        description: short human-readable excerpt of the condition
    """
    has_early = bool(_EARLY_RELEASE_RE.search(section_text))
    has_earnings = _has_earnings_trigger(section_text)

    pct: int | None = None
    pct_match = _PERCENT_EARLY_RELEASE_RE.search(section_text)
    if pct_match:
        try:
            pct = int(pct_match.group(1))
        except ValueError:
            pass

    description = ""
    if has_early:
        m = _EARLY_RELEASE_RE.search(section_text)
        start = max(0, m.start() - 20)
        description = section_text[start : start + 300].strip()

    return has_early, has_earnings, pct, description


def extract_lockup_conditions(html_text: str) -> LockupConditions:
    """
    Full lock-up extraction returning a structured LockupConditions object.

    Priority:
    1. Named lock-up sections (Fix 1: 'underwriting' excluded)
    2. Underwriting section with overallotment guard
    3. Full-document scan with overallotment guard
    4. Default 180 days
    """
    text = _strip_html(html_text)

    for heading in LOCKUP_SECTION_HEADINGS:
        section = _find_section_window(text, heading)
        if not section:
            continue
        days, reason = _extract_lockup_days_from_window(section, allow_overallotment=False)
        if days is not None:
            has_early, has_earnings, pct, desc = _detect_early_release(section)
            return LockupConditions(
                lockup_days=days,
                lockup_source=f"{heading.title()} section: {reason}",
                has_early_release=has_early,
                has_earnings_trigger=has_earnings,
                early_release_pct=pct,
                early_release_description=desc,
            )

    section = _find_section_window(text, UNDERWRITING_HEADING)
    if section:
        days, reason = _extract_lockup_days_from_window(section, allow_overallotment=False)
        if days is not None:
            has_early, has_earnings, pct, desc = _detect_early_release(section)
            return LockupConditions(
                lockup_days=days,
                lockup_source=f"Underwriting section (guarded): {reason}",
                has_early_release=has_early,
                has_earnings_trigger=has_earnings,
                early_release_pct=pct,
                early_release_description=desc,
            )

    days, reason = _extract_lockup_days_from_window(text, allow_overallotment=False)
    if days is not None and reason:
        has_early, has_earnings, pct, desc = _detect_early_release(text[:4000])
        return LockupConditions(
            lockup_days=days,
            lockup_source=f"Full document scan: {reason}",
            has_early_release=has_early,
            has_earnings_trigger=has_earnings,
            early_release_pct=pct,
            early_release_description=desc,
        )

    return LockupConditions(
        lockup_days=DEFAULT_LOCKUP_DAYS,
        lockup_source="Defaulted to 180 days after no confident lock-up match",
    )


# Backwards-compatible thin wrapper used by existing tests
def extract_lockup_days(html_text: str) -> tuple[int, str]:
    cond = extract_lockup_conditions(html_text)
    return cond.lockup_days, cond.lockup_source


# ── Fix 4 ──────────────────────────────────────────────────────────────────────
def extract_ipo_date_from_text(html_text: str) -> str | None:
    """
    Extract the IPO / prospectus date from filing text.

    Added: cover-page pattern "The date of this prospectus is <date>" which is
    present on virtually every 424B4 and missed by the original implementation.
    """
    text = _strip_html(html_text)
    patterns = [
        r"the date of this prospectus is ([A-Z][a-z]+ \d{1,2}, \d{4})",
        r"began trading on ([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
        r"completed the closing of the IPO on ([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
        r"priced on ([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
        r"this offering (?:was )?(?:priced|completed) on ([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            try:
                parsed = datetime.strptime(match.group(1).strip(), "%B %d, %Y").date()
                return parsed.isoformat()
            except ValueError:
                continue
    return None


def _normalize_holder_key(column: str) -> str:
    lower = column.strip().lower()
    if any(token in lower for token in ("beneficial owner", "holder", "owner", "name", "stockholder", "shareholder")):
        return "holder"
    if any(token in lower for token in ("beneficially owned", "amount owned", "share", "shares", "units", "owned")):
        return "shares"
    if any(token in lower for token in ("percent", "%", "ownership", "pct")):
        return "percent"
    if "voting" in lower:
        return "voting_power"
    if "class" in lower:
        return "class"
    return re.sub(r"\s+", " ", column.strip())


def _is_placeholder_holder(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text).strip().lower().strip(":")
    return normalized in HOLDER_PLACEHOLDERS


def _parse_holder_measure(key: str, text: str) -> int | float | str:
    cleaned = _clean_cell_text(text)
    if key == "shares":
        match = re.search(r"\d[\d,]*", cleaned)
        if match:
            digits = match.group(0).replace(",", "")
            try:
                return int(digits)
            except ValueError:
                pass
    if key in {"percent", "voting_power"}:
        match = re.search(r"\d+(?:\.\d+)?", cleaned)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                pass
    return cleaned


def _canonicalize_holder_row(row: pd.Series) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for column, value in row.items():
        if pd.isna(value):
            continue
        text = _clean_cell_text(value)
        if not text or text.lower() == "nan":
            continue
        key = _normalize_holder_key(str(column))
        if key == "holder":
            if _is_placeholder_holder(text):
                return {}
            record[key] = text
            continue
        if key in {"shares", "percent", "voting_power"}:
            record[key] = _parse_holder_measure(key, text)
            continue
        record[key] = text
    if "holder" not in record:
        return {}
    if len(record) == 1:
        return {}
    return record


def _table_score(table: pd.DataFrame) -> int:
    columns = " ".join(str(column).lower() for column in table.columns)
    score = 0
    for keyword in (
        "principal", "beneficial", "beneficially owned", "stockholder",
        "shareholder", "selling", "holder", "owner", "ownership", "voting",
    ):
        if keyword in columns:
            score += 2
    if table.shape[0] >= 2:
        score += 1
    for cell in table.head(5).fillna("").astype(str).to_numpy().flatten():
        cell_text = str(cell).lower()
        if "share" in cell_text or "%" in cell_text:
            score += 1
        if any(token in cell_text for token in ("director", "officer", "fund", "capital", "beneficially owned")):
            score += 1
    return score


# ── Fix 5 ──────────────────────────────────────────────────────────────────────
def _flatten_rowspans(html_fragment: str) -> str:
    """
    Pre-process an HTML table fragment to flatten rowspan attributes and strip
    footnote superscripts (<sup>) so pandas.read_html parses it cleanly.

    Falls back to the original fragment if lxml is unavailable or parsing fails.
    """
    try:
        from lxml import etree
        import lxml.html as lh
    except ImportError:
        return html_fragment

    try:
        root = lh.fragment_fromstring(html_fragment, create_parent="div")
    except Exception:
        return html_fragment

    for sup in root.xpath(".//sup"):
        sup.getparent().remove(sup)

    for table in root.xpath(".//table"):
        rows = table.xpath(".//tr")
        occupied: dict[tuple[int, int], str] = {}
        grid: list[list[str]] = []

        for r_idx, tr in enumerate(rows):
            col_idx = 0
            row_data: list[str] = []
            for td in tr.xpath("td|th"):
                while (r_idx, col_idx) in occupied:
                    row_data.append(occupied[(r_idx, col_idx)])
                    col_idx += 1

                text = (td.text_content() or "").strip()
                rowspan = int(td.get("rowspan", 1))
                colspan = int(td.get("colspan", 1))

                for extra_row in range(1, rowspan):
                    for extra_col in range(colspan):
                        occupied[(r_idx + extra_row, col_idx + extra_col)] = text

                for _ in range(colspan):
                    row_data.append(text)
                    col_idx += 1

            while (r_idx, col_idx) in occupied:
                row_data.append(occupied[(r_idx, col_idx)])
                col_idx += 1

            grid.append(row_data)

        if not grid:
            continue

        max_cols = max(len(r) for r in grid)
        new_table_parts = ["<table>"]
        for row in grid:
            new_table_parts.append("<tr>")
            for cell in row:
                new_table_parts.append(f"<td>{cell}</td>")
            for _ in range(max_cols - len(row)):
                new_table_parts.append("<td></td>")
            new_table_parts.append("</tr>")
        new_table_parts.append("</table>")

        new_table_el = lh.fragment_fromstring("".join(new_table_parts))
        table.getparent().replace(table, new_table_el)

    return etree.tostring(root, encoding="unicode", method="html")


def _read_html_tables(html_text: str, match: str | None = None) -> list[pd.DataFrame]:
    processed = _flatten_rowspans(html_text)
    html_io = StringIO(processed)
    try:
        if match:
            return pd.read_html(html_io, match=match)
        return pd.read_html(html_io)
    except (ValueError, ImportError):
        return []


def extract_principal_holders(html_text: str) -> list[dict[str, Any]]:
    tables: list[pd.DataFrame] = []
    for match in PRINCIPAL_TABLE_MATCHES:
        tables.extend(_read_html_tables(html_text, match=match))
    if not tables:
        tables = _read_html_tables(html_text)

    if not tables:
        return []

    best_records: list[dict[str, Any]] = []
    best_score = -1
    for table in tables:
        extracted_rows: list[dict[str, Any]] = []
        for _, row in table.head(12).iterrows():
            record = _canonicalize_holder_row(row)
            if record:
                extracted_rows.append(record)
        if not extracted_rows:
            continue
        score = _table_score(table) + len(extracted_rows) * 5
        if score > best_score:
            best_records = extracted_rows
            best_score = score
    return best_records[:10]


def _confidence_label(score: int) -> str:
    if score >= 80:
        return "High"
    if score >= 50:
        return "Medium"
    return "Low"


def assess_data_confidence(
    *,
    filing_form: str | None,
    lockup_source: str,
    principal_holders: list[dict[str, Any]],
    parsed_ipo_date: str | None,
    source_url: str | None,
    has_early_release: bool = False,
    has_8k_amendment: bool = False,
) -> tuple[int, str, str]:
    score = 0
    details: list[str] = []

    if source_url:
        score += 20
        details.append("SEC filing URL available")
    else:
        details.append("No filing URL found")

    if filing_form in IPO_FORMS:
        score += 20
        details.append(f"Matched filing form {filing_form}")
    elif filing_form:
        score += 10
        details.append(f"Found non-standard filing form {filing_form}")
    else:
        details.append("No filing form parsed")

    if lockup_source.startswith("Defaulted"):
        details.append("Lock-up term fell back to seeded default")
    else:
        score += 25
        details.append("Lock-up term parsed from filing text")

    if parsed_ipo_date:
        score += 10
        details.append("IPO date parsed from filing text")
    else:
        details.append("IPO date inherited from seeded watchlist")

    holder_count = len(principal_holders)
    if holder_count:
        score += 25
        details.append(f"Parsed {holder_count} principal holder rows")
    else:
        details.append("Principal holder table not cleanly parsed")

    if has_8k_amendment:
        score = min(100, score + 5)
        details.append("Unlock date cross-checked against post-IPO 8-K amendment")

    if has_early_release:
        details.append("Early release / dual-trigger clause detected — actual unlock may differ")

    final_score = min(100, score)
    return final_score, _confidence_label(final_score), "; ".join(details)


def enrich_company(company: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch the most relevant IPO filing for a company and derive an unlock
    estimate, now including:
      - Fix 1: greenshoe-safe lock-up day extraction
      - Fix 2: dual-trigger / early release detection
      - Fix 3: post-IPO 8-K amendment scanning
      - Fix 4: cover-page IPO date parsing
      - Fix 5: rowspan-flattened principal holder table extraction
    """
    base_ipo_date = date.fromisoformat(company["ipo_date"])

    try:
        filing_ref = find_latest_ipo_filing(company["cik"])
    except requests.RequestException as exc:
        unlock_date = base_ipo_date + timedelta(days=company["lockup_days"])
        return _error_result(company, unlock_date, f"SEC enrichment failed: {exc}")

    if filing_ref is None:
        unlock_date = base_ipo_date + timedelta(days=company["lockup_days"])
        return _error_result(
            company, unlock_date,
            "No IPO-related filing found in recent SEC submissions.",
            filing_ref=None,
        )

    try:
        html_text = fetch_text(filing_ref.filing_url)
        lockup_cond = extract_lockup_conditions(html_text)
        parsed_ipo_date_str = extract_ipo_date_from_text(html_text)
        principal_holders = extract_principal_holders(html_text)
    except (ValueError, TypeError, KeyError, requests.RequestException) as exc:
        unlock_date = base_ipo_date + timedelta(days=company["lockup_days"])
        return {
            "filing_form": filing_ref.form,
            "filing_date": filing_ref.filing_date,
            "source_url": filing_ref.filing_url,
            "lockup_days": company["lockup_days"],
            "unlock_date": unlock_date.isoformat(),
            "principal_holders": [],
            "lockup_source": "Seeded watchlist only",
            "lockup_conditions": None,
            "confidence_score": 20,
            "confidence_label": "Low",
            "confidence_details": f"Matched filing metadata, but live filing parse failed: {exc}",
            "notes": f"SEC filing could not be parsed cleanly: {exc}",
        }

    ipo_date = date.fromisoformat(parsed_ipo_date_str) if parsed_ipo_date_str else base_ipo_date
    unlock_date = ipo_date + timedelta(days=lockup_cond.lockup_days)

    amend_date, amend_url, amend_excerpt = find_lockup_amendment_8k(
        company["cik"], ipo_date
    )
    if amend_date:
        lockup_cond.amendment_date = amend_date
        lockup_cond.amendment_url = amend_url

    confidence_score, confidence_label, confidence_details = assess_data_confidence(
        filing_form=filing_ref.form,
        lockup_source=lockup_cond.lockup_source,
        principal_holders=principal_holders,
        parsed_ipo_date=parsed_ipo_date_str,
        source_url=filing_ref.filing_url,
        has_early_release=lockup_cond.has_early_release,
        has_8k_amendment=amend_date is not None,
    )

    notes = lockup_cond.notes_summary()
    if principal_holders:
        notes += f" | Extracted {len(principal_holders)} holder rows."
    else:
        notes += " | Principal stockholder table not extracted cleanly."

    return {
        "filing_form": filing_ref.form,
        "filing_date": filing_ref.filing_date,
        "source_url": filing_ref.filing_url,
        "lockup_days": lockup_cond.lockup_days,
        "unlock_date": unlock_date.isoformat(),
        "principal_holders": principal_holders,
        "lockup_source": lockup_cond.lockup_source,
        "lockup_conditions": {
            "has_early_release": lockup_cond.has_early_release,
            "has_earnings_trigger": lockup_cond.has_earnings_trigger,
            "early_release_pct": lockup_cond.early_release_pct,
            "early_release_description": lockup_cond.early_release_description,
            "amendment_date": lockup_cond.amendment_date,
            "amendment_url": lockup_cond.amendment_url,
        },
        "confidence_score": confidence_score,
        "confidence_label": confidence_label,
        "confidence_details": confidence_details,
        "notes": notes,
    }


def _error_result(
    company: dict[str, Any],
    unlock_date: date,
    message: str,
    filing_ref: FilingReference | None = None,
) -> dict[str, Any]:
    return {
        "filing_form": filing_ref.form if filing_ref else None,
        "filing_date": filing_ref.filing_date if filing_ref else None,
        "source_url": filing_ref.filing_url if filing_ref else None,
        "lockup_days": company["lockup_days"],
        "unlock_date": unlock_date.isoformat(),
        "principal_holders": [],
        "lockup_source": "Seeded watchlist only",
        "lockup_conditions": None,
        "confidence_score": 0,
        "confidence_label": "Low",
        "confidence_details": message,
        "notes": message,
    }
