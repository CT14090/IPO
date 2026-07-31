from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from html import unescape
from io import StringIO
from statistics import median
from typing import Any

import pandas as pd
import requests

from .config import DEFAULT_LOCKUP_DAYS


SEC_BASE_HEADERS = {
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
SUBMISSIONS_BASE_URL = "https://data.sec.gov/submissions/"
COMPANYFACTS_BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts/"
IPO_FORMS = {"424B4", "424B1", "424B3", "S-1", "S-1/A", "F-1", "F-1/A"}
EARNINGS_RELEASE_FORMS = {"8-K", "8-K/A", "10-Q", "10-Q/A", "10-K", "10-K/A"}
SEC_REQUEST_MAX_ATTEMPTS = 3
SEC_REQUEST_RETRYABLE_STATUS_CODES = {429, 503}

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

HOLDER_TABLE_SIGNALS = (
    "beneficial owner",
    "beneficial ownership",
    "beneficial shareholder",
    "principal stockholder",
    "principal and selling",
    "shares beneficially",
    "selling stockholder",
    "stockholder",
    "shareholder",
    "percent of class",
    "voting power",
)

EXCLUDED_HOLDER_TABLE_KEYWORDS = (
    "fiscal quarter",
    "retained earnings",
    "additional paid-in capital",
    "additional paid in capital",
    "accumulated other comprehensive income",
    "cash flows",
    "balance sheet",
    "total assets",
    "total liabilities",
    "liabilities",
    "stockholders' equity",
    "shareholders' equity",
    "net income",
    "operating activities",
)

HOLDER_PLACEHOLDERS = {
    "beneficial owner", "beneficial owners", "holder", "holders", "name",
    "name of beneficial owner", "name of beneficial shareholder", "principal stockholder", "principal stockholders",
    "principal and selling shareholder", "principal and selling shareholders",
    "selling stockholder", "selling stockholders", "stockholder", "stockholders",
    "shareholder", "shareholders", "total",
}

SHARES_OUTSTANDING_FACT_PRIORITY = (
    ("dei", "EntityCommonStockSharesOutstanding"),
    ("us-gaap", "CommonStockSharesOutstanding"),
    ("us-gaap", "CommonStockSharesIssued"),
)

_PROSPECTUS_OUTSTANDING_PATTERNS = (
    re.compile(
        r"([0-9][0-9,]{3,})\s+(?:ordinary shares|shares of common stock|shares of our common stock|class a common stock|common shares)[^.]{0,160}?outstanding immediately after this offering",
        re.I,
    ),
    re.compile(
        r"([0-9][0-9,]{3,})\s+(?:ordinary shares|shares of common stock|shares of our common stock|class a common stock|common shares)[^.]{0,160}?outstanding after this offering",
        re.I,
    ),
    re.compile(
        r"there (?:will|would) be\s+([0-9][0-9,]{3,})[^.]{0,160}?outstanding immediately after this offering",
        re.I,
    ),
    re.compile(
        r"(?:ordinary shares|shares of common stock|shares of our common stock|class a common stock|class b common stock|class c common stock|class a, class b, and class c common stock|common shares)[^.]{0,160}?"
        r"to be outstanding (?:immediately after|upon completion of|after) this offering[^0-9A-Za-z]{0,20}([0-9][0-9,]{3,})\s+(?:ordinary shares|shares)\b",
        re.I,
    ),
)
_ADS_OR_FOREIGN_SIGNAL_RE = re.compile(r"american depositary shares|\bads\b|\badr\b|\bplc\b", re.I)
_PROXY_OVERLAP_SIGNAL_RE = re.compile(r"subject to voting proxy|voting proxy", re.I)
_HOLDER_CLASS_LABEL_RE = re.compile(
    r"^(?:class [abc](?: common stock)?|shares|%|class a, class b, and class c|before this offering|after this offering)$",
    re.I,
)

# ── Fix 3 ──────────────────────────────────────────────────────────────────────
_LOCKUP_AMENDMENT_RE = re.compile(
    r"(lock[- ]up|restricted period|lockup|early release|lock up period"
    r"|lock-up period will terminate|restricted period.*?end)",
    re.I,
)

# ── Fix 2 ──────────────────────────────────────────────────────────────────────
_EARLY_RELEASE_RE = re.compile(
    r"(earlier of|early release|lock[- ]up period will terminate"
    r"|restricted period.*?end|price condition"
    r"|trading day.*?following.*?earnings|earnings.*?trading day"
    r"|\d+%.*?greater than the ipo price)",
    re.I,
)
_EARNINGS_KEYWORD_RE = re.compile(
    r"(earnings|quarterly results|financial results)",
    re.I,
)
_TRADING_DAY_RE = re.compile(
    r"(trading day|trading date|second|third) trading day",
    re.I,
)
_PERCENT_EARLY_RELEASE_RE = re.compile(
    r"(\d{1,3})%\s+of\s+(?:eligible\s+)?(?:securities|shares)",
    re.I,
)
_QUARTER_END_RE = re.compile(r"quarter ending ([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", re.I)


@dataclass(slots=True)
class FilingReference:
    form: str
    filing_date: str
    accession_number: str
    primary_document: str
    filing_url: str


@dataclass
class LockupConditions:
    """Structured representation of potentially complex lock-up terms."""
    lockup_days: int
    lockup_source: str
    has_early_release: bool = False
    early_release_description: str = ""
    has_earnings_trigger: bool = False
    early_release_pct: int | None = None
    amendment_date: str | None = None
    amendment_url: str | None = None
    earnings_release_quarter_end: str | None = None
    earnings_release_date: str | None = None
    earnings_release_url: str | None = None
    effective_unlock_date: str | None = None
    effective_unlock_source: str | None = None

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
        if self.effective_unlock_date and self.effective_unlock_source:
            parts.append(
                f"Effective unlock date: {self.effective_unlock_date} ({self.effective_unlock_source})"
            )
        return " | ".join(parts)


def normalize_cik(cik: int | str) -> str:
    digits = re.sub(r"\D", "", str(cik))
    return digits.zfill(10)


def sec_headers() -> dict[str, str]:
    user_agent = os.environ.get("SEC_USER_AGENT", "IPO Lockup Tracker demo contact@example.com")
    return {**SEC_BASE_HEADERS, "User-Agent": user_agent}


def _should_retry_sec_request(exc: requests.RequestException) -> bool:
    response = getattr(exc, "response", None)
    if response is None:
        return False
    return response.status_code in SEC_REQUEST_RETRYABLE_STATUS_CODES


def _retry_delay_seconds(exc: requests.RequestException, attempt: int) -> float:
    response = getattr(exc, "response", None)
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, min(float(retry_after), 5.0))
            except ValueError:
                pass
    return float(min(attempt, 3))


def _describe_request_exception(exc: requests.RequestException) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        return f"HTTP {response.status_code}"
    return exc.__class__.__name__


def _request_with_retries(url: str) -> requests.Response:
    last_exc: requests.RequestException | None = None
    for attempt in range(1, SEC_REQUEST_MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, headers=sec_headers(), timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_exc = exc
            if attempt >= SEC_REQUEST_MAX_ATTEMPTS or not _should_retry_sec_request(exc):
                raise
            time.sleep(_retry_delay_seconds(exc, attempt))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("SEC request failed without a captured exception.")


def fetch_json(url: str) -> dict[str, Any]:
    response = _request_with_retries(url)
    return response.json()


def fetch_text(url: str) -> str:
    response = _request_with_retries(url)
    return response.text


def submissions_url(cik: int | str) -> str:
    return f"https://data.sec.gov/submissions/CIK{normalize_cik(cik)}.json"


def companyfacts_url(cik: int | str) -> str:
    return f"{COMPANYFACTS_BASE_URL}CIK{normalize_cik(cik)}.json"


def filing_document_url(cik: int | str, accession_number: str, primary_document: str) -> str:
    cik_no_leading_zero = str(int(normalize_cik(cik)))
    accession_no_dashes = accession_number.replace("-", "")
    return (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_no_leading_zero}/{accession_no_dashes}/{primary_document}"
    )


def _submission_fragment_url(name: str) -> str:
    if name.startswith("http://") or name.startswith("https://"):
        return name
    return f"{SUBMISSIONS_BASE_URL}{name.lstrip('/')}"


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@lru_cache(maxsize=256)
def _fetch_company_submissions_cached(normalized_cik: str) -> dict[str, Any]:
    return fetch_json(submissions_url(normalized_cik))


@lru_cache(maxsize=512)
def _fetch_submission_fragment_cached(name: str) -> dict[str, Any]:
    return fetch_json(_submission_fragment_url(name))


@lru_cache(maxsize=256)
def _fetch_companyfacts_cached(normalized_cik: str) -> dict[str, Any]:
    return fetch_json(companyfacts_url(normalized_cik))


def load_companyfacts(cik: int | str) -> dict[str, Any]:
    return _fetch_companyfacts_cached(normalize_cik(cik))


def load_company_submissions(cik: int | str) -> dict[str, Any]:
    return _fetch_company_submissions_cached(normalize_cik(cik))


def _recent_filing_values(container: dict[str, Any], key: str) -> list[str]:
    values = container.get(key, [])
    return values if isinstance(values, list) else []


def _filing_records_from_container(container: dict[str, Any]) -> list[dict[str, str]]:
    forms = _recent_filing_values(container, "form")
    accession_numbers = _recent_filing_values(container, "accessionNumber")
    primary_documents = _recent_filing_values(container, "primaryDocument")
    filing_dates = _recent_filing_values(container, "filingDate")
    return [
        {
            "form": form,
            "accession_number": accession_number,
            "primary_document": primary_document,
            "filing_date": filing_date,
        }
        for form, accession_number, primary_document, filing_date in zip(
            forms,
            accession_numbers,
            primary_documents,
            filing_dates,
        )
    ]


def _dedupe_submission_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for record in sorted(
        records,
        key=lambda item: (item.get("filing_date", ""), item.get("accession_number", "")),
        reverse=True,
    ):
        key = (record.get("accession_number", ""), record.get("primary_document", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _oldest_covered_date(records: list[dict[str, str]]) -> date | None:
    filing_dates = [_parse_iso_date(record.get("filing_date")) for record in records]
    valid_dates = [filing_date for filing_date in filing_dates if filing_date is not None]
    return min(valid_dates) if valid_dates else None


def iter_submission_records(cik: int | str, *, oldest_needed_date: date | None = None) -> list[dict[str, str]]:
    submissions = load_company_submissions(cik)
    records = _filing_records_from_container(submissions.get("filings", {}).get("recent", {}))
    records = _dedupe_submission_records(records)
    oldest_covered = _oldest_covered_date(records)

    if oldest_needed_date is None:
        return records
    if oldest_covered is not None and oldest_covered <= oldest_needed_date:
        return records

    archive_files = sorted(
        submissions.get("filings", {}).get("files", []),
        key=lambda item: item.get("filingTo", ""),
        reverse=True,
    )
    for file_info in archive_files:
        name = file_info.get("name")
        if not name:
            continue
        try:
            fragment = _fetch_submission_fragment_cached(name)
        except requests.RequestException:
            continue
        if isinstance(fragment, dict) and "filings" in fragment:
            records.extend(_filing_records_from_container(fragment.get("filings", {}).get("recent", {})))
        elif isinstance(fragment, dict):
            records.extend(_filing_records_from_container(fragment))
        records = _dedupe_submission_records(records)
        oldest_covered = _oldest_covered_date(records)
        fragment_from = _parse_iso_date(file_info.get("filingFrom"))
        if fragment_from is not None and fragment_from <= oldest_needed_date:
            break
        if oldest_covered is not None and oldest_covered <= oldest_needed_date:
            break

    return records


def _format_long_date(value: date) -> str:
    return value.strftime("%B %d, %Y").replace(" 0", " ")


def add_trading_days(start_date: date, trading_days: int) -> date:
    current = start_date
    added = 0
    while added < trading_days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def find_latest_ipo_filing(cik: int | str, *, oldest_needed_date: date | None = None) -> FilingReference | None:
    for record in iter_submission_records(cik, oldest_needed_date=oldest_needed_date):
        form = record.get("form")
        accession_number = record.get("accession_number")
        primary_document = record.get("primary_document")
        filing_date = record.get("filing_date")
        if form not in IPO_FORMS:
            continue
        if not accession_number or not primary_document or not filing_date:
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
    cutoff = ipo_date + timedelta(days=210)

    for record in iter_submission_records(cik, oldest_needed_date=ipo_date):
        form = record.get("form")
        accession_number = record.get("accession_number")
        primary_document = record.get("primary_document")
        filing_date = _parse_iso_date(record.get("filing_date"))
        if form not in {"8-K", "8-K/A"}:
            continue
        if filing_date is None or not (ipo_date <= filing_date <= cutoff):
            continue
        if not accession_number or not primary_document:
            continue

        url = filing_document_url(cik, accession_number, primary_document)
        try:
            html = fetch_text(url)
        except requests.RequestException:
            continue
        text = _strip_html(html)
        if _LOCKUP_AMENDMENT_RE.search(text):
            match = _LOCKUP_AMENDMENT_RE.search(text)
            if match is None:
                continue
            start = max(0, match.start() - 50)
            excerpt = text[start : start + 400].strip()
            return filing_date.isoformat(), url, excerpt

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
    after: int = 3000,
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
        for match in re.finditer(pattern, text, flags=re.I):
            days = int(match.group(1))
            if days < 60 and not allow_overallotment:
                continue
            if not allow_overallotment:
                context_start = max(0, match.start() - 120)
                context_end = min(len(text), match.end() + 120)
                context = text[context_start:context_end]
                if _OVERALLOTMENT_RE.search(context):
                    continue
            return days, f"Regex match: {match.group(0)[:140]}"

    if re.search(r"one year", text, flags=re.I):
        return 365, "Detected one-year lock-up"
    return None, None


# ── Fix 2 ──────────────────────────────────────────────────────────────────────
def _has_earnings_trigger(text: str) -> bool:
    """Both 'earnings' and 'trading day' must appear within 400 chars of each other."""
    for match in _EARNINGS_KEYWORD_RE.finditer(text):
        window = text[max(0, match.start() - 300): match.end() + 300]
        if _TRADING_DAY_RE.search(window):
            return True
    return False


def _extract_earnings_trigger_quarter_end(text: str) -> str | None:
    match = _QUARTER_END_RE.search(text)
    if not match:
        return None
    try:
        parsed = datetime.strptime(match.group(1).strip(), "%B %d, %Y").date()
    except ValueError:
        return None
    return parsed.isoformat()


def _detect_early_release(section_text: str) -> tuple[bool, bool, int | None, str, str | None]:
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
        match = _EARLY_RELEASE_RE.search(section_text)
        if match is not None:
            start = max(0, match.start() - 20)
            description = section_text[start : start + 300].strip()

    quarter_end = _extract_earnings_trigger_quarter_end(section_text) if has_earnings else None
    return has_early, has_earnings, pct, description, quarter_end


def _parse_spacer_table_row(tr: Any) -> dict[str, Any] | None:
    cells = tr.xpath("./td|./th")
    if not cells:
        return None

    row_text = _clean_cell_text(" ".join(cell.text_content() for cell in cells)).lower()
    if any(
        keyword in row_text
        for keyword in (
            "name of beneficial",
            "shares beneficially",
            "being offered",
            "5% stockholder",
            "named executive",
            "directors and executive",
            "shares of common stock being offered",
            "shares beneficially owned following this offering",
        )
    ):
        return None

    value_cells = [
        _clean_cell_text(cell.text_content())
        for cell in cells
        if (cell.get("width") or "").strip() != "1%" and _clean_cell_text(cell.text_content())
    ]
    if len(value_cells) < 2:
        return None

    holder = re.sub(r"\(\d+\)\s*$", "", value_cells[0]).strip()
    if not holder:
        return None
    holder_lower = holder.lower()
    if any(token in holder_lower for token in ("all directors", "total", "aggregate")):
        return None
    if _is_placeholder_holder(holder):
        return None

    measure_cells = value_cells[1:]
    shares = _first_share_candidate(measure_cells)
    percent = _first_percent_candidate(measure_cells)
    if shares is None and percent is None:
        return None
    if isinstance(shares, int) and shares <= 1000:
        return None

    return {"holder": holder, "shares": shares, "percent": percent}


def _extract_holders_from_spacer_table(html_text: str) -> list[dict[str, Any]]:
    """
    Parse principal stockholder tables that use width=1% spacer <td> cells
    between the actual data cells.
    """
    try:
        import lxml.html as lh
    except ImportError:
        return []

    try:
        root = lh.fromstring(html_text)
    except Exception:
        return []

    target_table = None
    for table in root.xpath(".//table"):
        header_cells = table.xpath(".//th|.//td")
        has_name_header = any(
            _clean_cell_text(cell.text_content()).lower() == "name of beneficial owner"
            for cell in header_cells
        )
        if not has_name_header:
            continue

        large_numbers = [
            int(text)
            for text in (
                _clean_cell_text(cell.text_content()).replace(",", "")
                for cell in table.xpath(".//td")
            )
            if text.isdigit() and int(text) > 1000
        ]
        if not large_numbers:
            continue

        target_table = table
        break
    if target_table is None:
        return []

    results: list[dict[str, Any]] = []
    seen: set[tuple[str, Any, Any]] = set()
    for tr in target_table.xpath(".//tr"):
        record = _parse_spacer_table_row(tr)
        if not record:
            continue
        key = (record["holder"].lower(), record.get("shares"), record.get("percent"))
        if key in seen:
            continue
        seen.add(key)
        results.append(record)

    return results[:10]


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
            has_early, has_earnings, pct, desc, quarter_end = _detect_early_release(section)
            return LockupConditions(
                lockup_days=days,
                lockup_source=f"{heading.title()} section: {reason}",
                has_early_release=has_early,
                has_earnings_trigger=has_earnings,
                early_release_pct=pct,
                early_release_description=desc,
                earnings_release_quarter_end=quarter_end,
            )

    section = _find_section_window(text, UNDERWRITING_HEADING)
    if section:
        days, reason = _extract_lockup_days_from_window(section, allow_overallotment=False)
        if days is not None:
            has_early, has_earnings, pct, desc, quarter_end = _detect_early_release(section)
            return LockupConditions(
                lockup_days=days,
                lockup_source=f"Underwriting section (guarded): {reason}",
                has_early_release=has_early,
                has_earnings_trigger=has_earnings,
                early_release_pct=pct,
                early_release_description=desc,
                earnings_release_quarter_end=quarter_end,
            )

    days, reason = _extract_lockup_days_from_window(text, allow_overallotment=False)
    if days is not None and reason:
        has_early, has_earnings, pct, desc, quarter_end = _detect_early_release(text[:4000])
        return LockupConditions(
            lockup_days=days,
            lockup_source=f"Full document scan: {reason}",
            has_early_release=has_early,
            has_earnings_trigger=has_earnings,
            early_release_pct=pct,
            early_release_description=desc,
            earnings_release_quarter_end=quarter_end,
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
    if any(token in lower for token in ("beneficial owner", "beneficial shareholder", "holder", "owner", "name", "stockholder", "shareholder")):
        return "holder"
    if any(token in lower for token in ("beneficially owned", "amount owned", "share", "shares", "units", "owned", "number")):
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


def _is_plausible_holder_name(text: str) -> bool:
    cleaned = _clean_cell_text(text)
    if not cleaned or _is_placeholder_holder(cleaned):
        return False
    if _HOLDER_CLASS_LABEL_RE.fullmatch(cleaned):
        return False
    letters = sum(character.isalpha() for character in cleaned)
    digits = sum(character.isdigit() for character in cleaned)
    if letters < 2:
        return False
    if digits > letters * 2:
        return False
    return bool(re.search(r"[A-Za-z]{2,}", cleaned))


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


def _first_share_candidate(values: list[str]) -> int | None:
    for value in values:
        parsed = _parse_holder_measure("shares", value)
        if isinstance(parsed, int) and parsed > 1000:
            return parsed
    return None


def _first_percent_candidate(values: list[str]) -> float | None:
    fallback_percent: float | None = None
    for value in values:
        cleaned = _clean_cell_text(value)
        if "%" in cleaned:
            parsed = _parse_holder_measure("percent", cleaned)
            if not isinstance(parsed, (int, float)):
                continue
            numeric = float(parsed)
            return numeric
        if fallback_percent is not None:
            continue
        if not re.fullmatch(r"\d+(?:\.\d+)?", cleaned):
            continue
        numeric = float(cleaned)
        if 0.0 <= numeric <= 100.0:
            fallback_percent = numeric
    return fallback_percent


def _table_contains_excluded_holder_language(table: pd.DataFrame) -> bool:
    fragments = [str(column) for column in table.columns]
    fragments.extend(str(cell) for cell in table.head(6).fillna("").astype(str).to_numpy().flatten())
    haystack = " ".join(_clean_cell_text(fragment).lower() for fragment in fragments if fragment)
    return any(keyword in haystack for keyword in EXCLUDED_HOLDER_TABLE_KEYWORDS)


def _table_has_holder_signals(table: pd.DataFrame) -> bool:
    fragments = [str(column) for column in table.columns]
    fragments.extend(str(cell) for cell in table.head(6).fillna("").astype(str).to_numpy().flatten())
    haystack = " ".join(_clean_cell_text(fragment).lower() for fragment in fragments if fragment)
    return any(signal in haystack for signal in HOLDER_TABLE_SIGNALS)


def _canonicalize_holder_row(row: pd.Series) -> dict[str, Any]:
    record: dict[str, Any] = {}
    measure_texts: list[str] = []
    for column, value in row.items():
        if pd.isna(value):
            continue
        text = _clean_cell_text(value)
        if not text or text.lower() == "nan":
            continue
        key = _normalize_holder_key(str(column))
        if key == "holder":
            if not _is_plausible_holder_name(text):
                return {}
            record[key] = text
            continue
        measure_texts.append(text)
        if key in {"shares", "percent", "voting_power"}:
            if key in record and isinstance(record[key], (int, float)):
                continue
            record[key] = _parse_holder_measure(key, text)
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", key):
            continue
        if text == "%":
            continue
        record[key] = text
    if "holder" not in record:
        return {}
    if not isinstance(record.get("shares"), int):
        share_candidate = _first_share_candidate(measure_texts)
        if share_candidate is not None:
            record["shares"] = share_candidate
    if not isinstance(record.get("percent"), (int, float)):
        percent_candidate = _first_percent_candidate(measure_texts)
        if percent_candidate is not None:
            record["percent"] = percent_candidate
    if len(record) == 1:
        return {}
    if not any(isinstance(record.get(key), (int, float)) for key in ("shares", "percent", "voting_power")):
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
        if any(token in cell_text for token in ("director", "officer", "fund", "beneficially owned")):
            score += 1
    return score


def _table_has_real_numeric_values(table: pd.DataFrame) -> bool:
    for cell in table.fillna("").astype(str).to_numpy().flatten():
        text = _clean_cell_text(cell).replace(",", "")
        if not text:
            continue
        if not re.fullmatch(r"\d+(?:\.\d+)?", text):
            continue
        try:
            if float(text) > 1000:
                return True
        except ValueError:
            continue
    return False


def _table_has_default_columns(table: pd.DataFrame) -> bool:
    return all(
        isinstance(column, int) or (isinstance(column, str) and str(column).isdigit())
        for column in table.columns
    )


def _row_looks_like_holder_header_extension(row_values: list[str]) -> bool:
    normalized_values = [value.lower() for value in row_values if value]
    if not normalized_values:
        return False
    joined = " ".join(normalized_values)
    if re.search(r"\d[\d,]{3,}", joined):
        return False
    return any(
        token in joined
        for token in (
            "class a",
            "class b",
            "class c",
            "shares",
            "total outstanding",
            "voting power",
            "before this offering",
            "after this offering",
            "being offered",
            "%",
        )
    )


def _promote_embedded_header_rows(table: pd.DataFrame) -> pd.DataFrame:
    if table.empty:
        return table

    header_end = -1
    max_header_scan = min(len(table), 5)
    for row_idx in range(max_header_scan):
        row_values = [_clean_cell_text(value) for value in table.iloc[row_idx].tolist()]
        row_text = " ".join(value.lower() for value in row_values if value)
        if not row_text:
            continue
        if ("beneficial" in row_text or "shareholder" in row_text or "stockholder" in row_text) and (
            "name" in row_text or "number" in row_text or "percent" in row_text or "%" in row_text
        ):
            header_end = row_idx

    if header_end >= 0:
        max_extension_scan = min(len(table), header_end + 4)
        for row_idx in range(header_end + 1, max_extension_scan):
            row_values = [_clean_cell_text(value) for value in table.iloc[row_idx].tolist()]
            if not _row_looks_like_holder_header_extension(row_values):
                break
            header_end = row_idx

    if header_end < 0:
        return table

    header_rows = table.iloc[: header_end + 1].fillna("")
    rebuilt_columns: list[str] = []
    for col_idx in range(table.shape[1]):
        parts: list[str] = []
        seen_parts: set[str] = set()
        for row_idx in range(header_end + 1):
            text = _clean_cell_text(header_rows.iat[row_idx, col_idx])
            if not text:
                continue
            lower = text.lower()
            if lower in seen_parts:
                continue
            seen_parts.add(lower)
            parts.append(text)
        rebuilt_columns.append(" ".join(parts).strip() or str(table.columns[col_idx]))

    promoted = table.iloc[header_end + 1 :].copy().reset_index(drop=True)
    promoted.columns = rebuilt_columns
    return promoted


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
    spacer_records = _extract_holders_from_spacer_table(html_text)
    if spacer_records:
        return spacer_records

    tables: list[pd.DataFrame] = []
    for match in PRINCIPAL_TABLE_MATCHES:
        tables.extend(_read_html_tables(html_text, match=match))
    if not tables:
        tables = _read_html_tables(html_text)

    if not tables:
        return []

    best_records: list[dict[str, Any]] = []
    best_score = -1
    for original_table in tables:
        candidate_tables = [original_table]
        promoted_table = _promote_embedded_header_rows(original_table)
        if not promoted_table.equals(original_table):
            candidate_tables.append(promoted_table)

        for table in candidate_tables:
            if not _table_has_real_numeric_values(table):
                continue
            if _table_contains_excluded_holder_language(table):
                continue
            if not _table_has_holder_signals(table):
                continue
            extracted_rows: list[dict[str, Any]] = []
            for _, row in table.head(12).iterrows():
                record = _canonicalize_holder_row(row)
                if record:
                    extracted_rows.append(record)
            if not extracted_rows:
                continue
            score = _table_score(table) + len(extracted_rows) * 5
            if _table_has_default_columns(original_table) and not _table_has_default_columns(table):
                score += 8
            if score > best_score:
                best_records = extracted_rows
                best_score = score
    return best_records[:10]


def _coerce_share_count(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        numeric = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if numeric <= 0:
        return None
    return int(round(numeric))


def _coerce_percent_value(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        numeric = float(str(value).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if numeric < 0 or numeric > 100:
        return None
    return numeric


def _extract_prospectus_shares_outstanding(html_text: str) -> tuple[int | None, str | None]:
    if not html_text:
        return None, None
    text = _strip_html(html_text)
    for pattern in _PROSPECTUS_OUTSTANDING_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        try:
            shares = int(match.group(1).replace(",", ""))
        except ValueError:
            continue
        return shares, f"Prospectus text fallback: {match.group(0)[:160]}"
    return None, None


def _derive_offering_shares_outstanding(
    principal_holders: list[dict[str, Any]],
    html_text: str,
) -> tuple[int | None, str | None, str]:
    explicit_value, explicit_note = _extract_prospectus_shares_outstanding(html_text)
    if explicit_value is not None:
        return explicit_value, "prospectus_text_fallback", explicit_note or "Prospectus text fallback"

    derived_values: list[float] = []
    for holder in principal_holders:
        holder_name = str(holder.get("holder") or "").strip()
        shares = _coerce_share_count(holder.get("shares"))
        percent = _coerce_percent_value(holder.get("percent"))
        if shares is None or percent is None or percent == 0:
            continue
        if not _is_plausible_holder_name(holder_name):
            continue
        derived = shares / (percent / 100.0)
        if derived < shares:
            continue
        derived_values.append(derived)

    if derived_values:
        derived_median = float(median(derived_values))
        max_deviation = max(abs(value - derived_median) / derived_median for value in derived_values)
        if max_deviation <= 0.05:
            return (
                int(round(derived_median)),
                "principal_holder_percent_derived",
                f"Derived offering-date shares outstanding from {len(derived_values)} holder row(s); max deviation {max_deviation * 100:.1f}%.",
            )
        return (
            None,
            None,
            f"Holder rows imply inconsistent offering-date share counts (max deviation {max_deviation * 100:.1f}%).",
        )

    return None, None, "No reliable offering-date shares outstanding figure was derived."


def _select_companyfacts_share_fact(
    units: dict[str, Any],
    *,
    reference_date: date,
) -> tuple[int | None, str | None, bool]:
    undimensioned: list[tuple[date, date, int]] = []
    ignored_dimensions = False

    for entries in units.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            end_date = _parse_iso_date(entry.get("end"))
            share_count = _coerce_share_count(entry.get("val"))
            if end_date is None or share_count is None:
                continue
            if entry.get("segment"):
                ignored_dimensions = True
                continue
            filed_date = _parse_iso_date(entry.get("filed")) or end_date
            undimensioned.append((end_date, filed_date, share_count))

    if not undimensioned:
        return None, None, ignored_dimensions

    eligible = [candidate for candidate in undimensioned if candidate[0] <= reference_date]
    pool = eligible or undimensioned
    end_date, filed_date, share_count = max(pool, key=lambda item: (item[0], item[1], item[2]))
    return share_count, end_date.isoformat(), ignored_dimensions


def _load_current_shares_outstanding(
    cik: int | str,
    *,
    html_text: str,
    parsed_ipo_date: str,
    reference_date: date,
) -> dict[str, Any]:
    facts: dict[str, Any] | None = None
    failure_note: str | None = None
    try:
        facts = load_companyfacts(cik).get("facts", {})
    except requests.RequestException as exc:
        failure_note = f"Company Facts fetch failed: {_describe_request_exception(exc)}"

    dimension_note: str | None = None
    if isinstance(facts, dict):
        for taxonomy, concept in SHARES_OUTSTANDING_FACT_PRIORITY:
            concept_data = facts.get(taxonomy, {}).get(concept, {})
            if not isinstance(concept_data, dict):
                continue
            share_count, as_of, ignored_dimensions = _select_companyfacts_share_fact(
                concept_data.get("units", {}),
                reference_date=reference_date,
            )
            if share_count is not None:
                note = "Live current shares outstanding from SEC Company Facts."
                if ignored_dimensions:
                    note += " Additional class-level dimensions were ignored in this first-pass metric."
                return {
                    "current_shares_outstanding": share_count,
                    "current_shares_outstanding_as_of": as_of,
                    "current_shares_outstanding_source": f"{taxonomy}:{concept}",
                    "current_shares_outstanding_note": note,
                    "current_shares_outstanding_uses_dimensions": False,
                }
            if ignored_dimensions and dimension_note is None:
                dimension_note = "Only dimensioned class-level SEC share facts were available, so current shares outstanding was not computed from XBRL."

    fallback_value, fallback_note = _extract_prospectus_shares_outstanding(html_text)
    if fallback_value is not None:
        note = "Prospectus-era fallback used because no current undimensioned SEC Company Facts value was available."
        if fallback_note:
            note = f"{note} {fallback_note}"
        if failure_note:
            note = f"{note} {failure_note}"
        elif dimension_note:
            note = f"{note} {dimension_note}"
        return {
            "current_shares_outstanding": fallback_value,
            "current_shares_outstanding_as_of": parsed_ipo_date,
            "current_shares_outstanding_source": "prospectus_text_fallback",
            "current_shares_outstanding_note": note,
            "current_shares_outstanding_uses_dimensions": False,
        }

    note = failure_note or dimension_note or "No current shares outstanding fact was resolved."
    return {
        "current_shares_outstanding": None,
        "current_shares_outstanding_as_of": None,
        "current_shares_outstanding_source": None,
        "current_shares_outstanding_note": note,
        "current_shares_outstanding_uses_dimensions": False,
    }


def _tracked_holder_metrics(
    principal_holders: list[dict[str, Any]],
    *,
    offering_shares_outstanding: int | None,
    filing_form: str | None,
    company_name: str,
    html_text: str,
) -> tuple[int | None, float | None, str]:
    if offering_shares_outstanding is None:
        return None, None, "Tracked holder percentage was not computed because the offering-date denominator is unresolved."

    issuer_name = company_name or ""
    if (filing_form or "").startswith("F-") or _ADS_OR_FOREIGN_SIGNAL_RE.search(f"{issuer_name} {_strip_html(html_text)[:500]}"):
        return None, None, "Tracked holder percentage was not computed in this first pass because the issuer looks foreign or ADS-based."

    rows: list[tuple[str, int]] = []
    seen_shares: set[int] = set()
    duplicate_shares: set[int] = set()
    percent_total = 0.0
    for holder in principal_holders:
        holder_name = str(holder.get("holder") or "").strip()
        shares = _coerce_share_count(holder.get("shares"))
        percent = _coerce_percent_value(holder.get("percent"))
        if percent is not None:
            percent_total += percent
        if not holder_name or shares is None:
            continue
        if _PROXY_OVERLAP_SIGNAL_RE.search(holder_name):
            return None, None, "Tracked holder percentage was not computed because the parsed holder table includes proxy/overlap rows that cannot be safely summed."
        if shares in seen_shares:
            duplicate_shares.add(shares)
        seen_shares.add(shares)
        rows.append((holder_name, shares))

    if not rows:
        return None, None, "Tracked holder percentage was not computed because no numeric holder rows were available."
    if duplicate_shares:
        return None, None, "Tracked holder percentage was not computed because duplicate holder share counts suggest overlapping beneficial ownership rows."
    if percent_total > 100.5:
        return None, None, "Tracked holder percentage was not computed because parsed holder percentages exceed 100%, which suggests overlap or mixed share classes."

    tracked_shares = sum(shares for _, shares in rows)
    if tracked_shares > offering_shares_outstanding:
        return None, None, "Tracked holder percentage was not computed because summed parsed holder shares exceed the offering-date shares outstanding denominator."

    tracked_pct = round((tracked_shares / offering_shares_outstanding) * 100, 2)
    return tracked_shares, tracked_pct, f"Tracked holder percentage sums {len(rows)} parsed holder row(s) against the offering-date denominator."


def build_ownership_context(
    *,
    cik: int | str,
    company_name: str,
    filing_form: str | None,
    html_text: str,
    principal_holders: list[dict[str, Any]],
    parsed_ipo_date: str,
) -> dict[str, Any]:
    offering_shares_outstanding, offering_source, offering_note = _derive_offering_shares_outstanding(
        principal_holders,
        html_text,
    )
    current_context = _load_current_shares_outstanding(
        cik,
        html_text=html_text,
        parsed_ipo_date=parsed_ipo_date,
        reference_date=date.today(),
    )
    tracked_holder_shares, tracked_holder_pct, tracked_holder_note = _tracked_holder_metrics(
        principal_holders,
        offering_shares_outstanding=offering_shares_outstanding,
        filing_form=filing_form,
        company_name=company_name,
        html_text=html_text,
    )
    return {
        "offering_shares_outstanding": offering_shares_outstanding,
        "offering_shares_outstanding_as_of": parsed_ipo_date if offering_shares_outstanding is not None else None,
        "offering_shares_outstanding_source": offering_source,
        "offering_shares_outstanding_note": offering_note,
        "current_shares_outstanding": current_context.get("current_shares_outstanding"),
        "current_shares_outstanding_as_of": current_context.get("current_shares_outstanding_as_of"),
        "current_shares_outstanding_source": current_context.get("current_shares_outstanding_source"),
        "current_shares_outstanding_note": current_context.get("current_shares_outstanding_note"),
        "current_shares_outstanding_uses_dimensions": current_context.get("current_shares_outstanding_uses_dimensions", False),
        "tracked_holder_shares": tracked_holder_shares,
        "tracked_holder_pct_of_offering": tracked_holder_pct,
        "tracked_holder_pct_note": tracked_holder_note,
    }


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
    filing_text_available: bool = True,
    ipo_date_parsed_from_filing: bool | None = None,
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

    if not filing_text_available:
        details.append("Prospectus HTML unavailable during refresh")
    elif lockup_source.startswith("Defaulted"):
        details.append("Lock-up term fell back to seeded default")
    else:
        score += 25
        details.append("Lock-up term parsed from filing text")

    if ipo_date_parsed_from_filing is None:
        ipo_date_parsed_from_filing = bool(parsed_ipo_date)
    if ipo_date_parsed_from_filing:
        score += 10
        details.append("IPO date parsed from filing text")
    else:
        details.append("IPO date inherited from seeded watchlist")

    holder_count = len(principal_holders)
    if holder_count:
        score += 25
        details.append(f"Parsed {holder_count} principal holder rows")
    elif not filing_text_available:
        details.append("Principal holder table not parsed because filing HTML was unavailable")
    else:
        details.append("Principal holder table not cleanly parsed")

    if has_8k_amendment:
        score = min(100, score + 5)
        details.append("Unlock date cross-checked against post-IPO 8-K amendment")

    if has_early_release:
        score = min(100, score + 5)
        details.append("Early release / dual-trigger clause detected — actual unlock may differ")

    score = min(100, score)
    return score, _confidence_label(score), "; ".join(details)


def find_earnings_release_filing(
    cik: int | str,
    *,
    quarter_end: date,
    latest_unlock_date: date,
) -> tuple[str | None, str | None]:
    quarter_end_text = _format_long_date(quarter_end).lower()
    records = sorted(
        iter_submission_records(cik, oldest_needed_date=quarter_end),
        key=lambda item: item.get("filing_date", ""),
    )
    fallback_result: tuple[str | None, str | None] = (None, None)

    for record in records:
        form = record.get("form")
        accession_number = record.get("accession_number")
        primary_document = record.get("primary_document")
        filing_date = _parse_iso_date(record.get("filing_date"))
        if form not in EARNINGS_RELEASE_FORMS:
            continue
        if filing_date is None or filing_date < quarter_end or filing_date > latest_unlock_date:
            continue
        if not accession_number or not primary_document:
            continue

        url = filing_document_url(cik, accession_number, primary_document)
        try:
            text = _strip_html(fetch_text(url)).lower()
        except requests.RequestException:
            continue
        if not _EARNINGS_KEYWORD_RE.search(text):
            continue
        if quarter_end_text in text:
            return filing_date.isoformat(), url
        if fallback_result == (None, None):
            fallback_result = (filing_date.isoformat(), url)

    return fallback_result


def determine_effective_unlock_date(
    cik: int | str,
    lockup_conditions: LockupConditions,
    *,
    calendar_unlock_date: date,
) -> tuple[date, str | None, str | None, str | None]:
    if not (lockup_conditions.has_early_release and lockup_conditions.has_earnings_trigger):
        return calendar_unlock_date, None, None, None

    quarter_end = _parse_iso_date(lockup_conditions.earnings_release_quarter_end)
    if quarter_end is None:
        return calendar_unlock_date, None, None, None

    release_date_text, release_url = find_earnings_release_filing(
        cik,
        quarter_end=quarter_end,
        latest_unlock_date=calendar_unlock_date,
    )
    release_date = _parse_iso_date(release_date_text)
    if release_date is None:
        return calendar_unlock_date, None, None, None

    effective_unlock_date = add_trading_days(release_date, 3)
    if effective_unlock_date >= calendar_unlock_date:
        return calendar_unlock_date, release_date.isoformat(), release_url, None

    source = f"Earnings trigger: 3 trading days after earnings release filed {release_date.isoformat()}"
    return effective_unlock_date, release_date.isoformat(), release_url, source


# ── Convenience enrichment helper ─────────────────────────────────────────────
def enrich_company(company: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch and compute all live SEC-derived fields for one watchlist company.

    Returns a dict with keys consumed by the DB snapshot and Streamlit UI.
    """
    from .insiders import fetch_post_unlock_sales, summarize_insider_sales
    from .market import fetch_market_data  # local import to avoid circular dependency

    cik = company["cik"]
    seeded_ipo_date = company["ipo_date"]
    seeded_ipo_dt = date.fromisoformat(seeded_ipo_date)

    filing_ref = find_latest_ipo_filing(cik, oldest_needed_date=seeded_ipo_dt)
    source_url = filing_ref.filing_url if filing_ref else None
    filing_form = filing_ref.form if filing_ref else None
    filing_date = filing_ref.filing_date if filing_ref else None

    html_text = ""
    filing_fetch_note: str | None = None
    if source_url:
        try:
            html_text = fetch_text(source_url)
        except requests.RequestException as exc:
            filing_fetch_note = _describe_request_exception(exc)
            html_text = ""

    lockup_conditions = (
        extract_lockup_conditions(html_text)
        if html_text
        else LockupConditions(
            DEFAULT_LOCKUP_DAYS,
            f"No filing text available ({filing_fetch_note})" if filing_fetch_note else "No filing text available",
        )
    )
    principal_holders = extract_principal_holders(html_text) if html_text else []

    parsed_ipo_date = extract_ipo_date_from_text(html_text) if html_text else None
    parsed_ipo_date_from_filing = parsed_ipo_date is not None
    if not parsed_ipo_date:
        parsed_ipo_date = seeded_ipo_date
    parsed_ipo_dt = date.fromisoformat(parsed_ipo_date)
    ownership_context = build_ownership_context(
        cik=cik,
        company_name=company.get("company_name", ""),
        filing_form=filing_form,
        html_text=html_text,
        principal_holders=principal_holders,
        parsed_ipo_date=parsed_ipo_date,
    )

    amendment_date, amendment_url, amendment_excerpt = (None, None, None)
    try:
        amendment_date, amendment_url, amendment_excerpt = find_lockup_amendment_8k(
            cik=cik,
            ipo_date=parsed_ipo_dt,
        )
    except Exception:
        amendment_date, amendment_url, amendment_excerpt = None, None, None

    if amendment_date:
        lockup_conditions.amendment_date = amendment_date
        lockup_conditions.amendment_url = amendment_url
        if amendment_excerpt:
            if lockup_conditions.early_release_description:
                lockup_conditions.early_release_description = (
                    f"{lockup_conditions.early_release_description} | {amendment_excerpt}"
                )
            else:
                lockup_conditions.early_release_description = amendment_excerpt

    if lockup_conditions.lockup_days <= 0:
        lockup_conditions.lockup_days = DEFAULT_LOCKUP_DAYS

    calendar_unlock_dt = parsed_ipo_dt + timedelta(days=lockup_conditions.lockup_days)
    effective_unlock_dt, earnings_release_date, earnings_release_url, effective_unlock_source = determine_effective_unlock_date(
        cik,
        lockup_conditions,
        calendar_unlock_date=calendar_unlock_dt,
    )
    lockup_conditions.earnings_release_date = earnings_release_date
    lockup_conditions.earnings_release_url = earnings_release_url
    lockup_conditions.effective_unlock_date = effective_unlock_dt.isoformat()
    lockup_conditions.effective_unlock_source = effective_unlock_source

    insider_sales: list[dict[str, Any]] = []
    if date.today() >= effective_unlock_dt:
        existing_insider_sales = None
        if company.get("effective_unlock_date") == effective_unlock_dt.isoformat():
            existing_insider_sales = company.get("insider_sales", [])
        insider_sales = fetch_post_unlock_sales(
            cik,
            effective_unlock_dt.isoformat(),
            existing_records=existing_insider_sales,
        )
    insider_sales_summary = summarize_insider_sales(insider_sales)

    market = fetch_market_data(company.get("ticker", ""), parsed_ipo_date)
    price_change_pct = market.get("price_change_pct")

    confidence_score, confidence_label, confidence_details = assess_data_confidence(
        filing_form=filing_form,
        lockup_source=lockup_conditions.lockup_source,
        principal_holders=principal_holders,
        parsed_ipo_date=parsed_ipo_date,
        source_url=source_url,
        filing_text_available=bool(html_text),
        ipo_date_parsed_from_filing=parsed_ipo_date_from_filing,
        has_early_release=lockup_conditions.has_early_release,
        has_8k_amendment=bool(amendment_date),
    )

    notes = lockup_conditions.notes_summary()
    if filing_fetch_note:
        notes = f"{notes} | Prospectus fetch failed during refresh: {filing_fetch_note}"
    if insider_sales_summary["transaction_count"]:
        notes = (
            f"{notes} | Post-unlock Form 4 sales parsed: "
            f"{insider_sales_summary['transaction_count']} transaction(s) across "
            f"{insider_sales_summary['filing_count']} filing(s), "
            f"{insider_sales_summary['total_shares_sold']:,} shares sold"
        )
    if confidence_details:
        notes = f"{notes} | {confidence_details}"

    return {
        "filing_form": filing_form,
        "filing_date": filing_date,
        "source_url": source_url,
        "lockup_days": lockup_conditions.lockup_days,
        "unlock_date": calendar_unlock_dt.isoformat(),
        "effective_unlock_date": effective_unlock_dt.isoformat(),
        "principal_holders": principal_holders,
        "lockup_source": lockup_conditions.lockup_source,
        "ownership_context": ownership_context,
        "lockup_conditions": {
            "lockup_days": lockup_conditions.lockup_days,
            "lockup_source": lockup_conditions.lockup_source,
            "has_early_release": lockup_conditions.has_early_release,
            "early_release_description": lockup_conditions.early_release_description,
            "has_earnings_trigger": lockup_conditions.has_earnings_trigger,
            "early_release_pct": lockup_conditions.early_release_pct,
            "amendment_date": lockup_conditions.amendment_date,
            "amendment_url": lockup_conditions.amendment_url,
            "earnings_release_quarter_end": lockup_conditions.earnings_release_quarter_end,
            "earnings_release_date": lockup_conditions.earnings_release_date,
            "earnings_release_url": lockup_conditions.earnings_release_url,
            "effective_unlock_date": lockup_conditions.effective_unlock_date,
            "effective_unlock_source": lockup_conditions.effective_unlock_source,
        },
        "insider_sales": insider_sales,
        "ipo_price": market.get("ipo_price"),
        "current_price": market.get("current_price"),
        "price_change_pct": price_change_pct,
        "avg_volume_30d": market.get("avg_volume_30d"),
        "market_cap": market.get("market_cap"),
        "market_data_note": market.get("market_data_note", ""),
        "parsed_ipo_date": parsed_ipo_date,
        "confidence_score": confidence_score,
        "confidence_label": confidence_label,
        "confidence_details": confidence_details,
        "notes": notes,
    }
