from __future__ import annotations

import os
import re
from dataclasses import dataclass
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
LOCKUP_SECTION_HEADINGS = (
    "lock-up agreements",
    "lockup agreements",
    "shares eligible for future sale",
    "underwriting",
)
PRINCIPAL_TABLE_MATCHES = (
    "Principal and Selling Stockholders",
    "Principal Stockholders",
    "Beneficial Owner",
    "Selling Stockholders",
)


@dataclass(slots=True)
class FilingReference:
    form: str
    filing_date: str
    accession_number: str
    primary_document: str
    filing_url: str


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
    return f"https://www.sec.gov/Archives/edgar/data/{cik_no_leading_zero}/{accession_no_dashes}/{primary_document}"


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


def _strip_html(html_text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html_text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _find_section_window(text: str, heading: str, before: int = 200, after: int = 1600) -> str | None:
    lowered = text.lower()
    index = lowered.find(heading)
    if index == -1:
        return None
    start = max(0, index - before)
    end = min(len(text), index + after)
    return text[start:end]


def _extract_lockup_days_from_text(text: str) -> tuple[int | None, str | None]:
    patterns = [
        r"for a period of\s+(\d{2,3})\s+days",
        r"period of\s+(\d{2,3})\s+days",
        r"(\d{2,3})\s+days after the date of this prospectus",
        r"(\d{2,3})\s+days from the date of this prospectus",
        r"(\d{2,3})\s+day lock[- ]up",
        r"lock[- ]up(?:[^.]{0,300})?(\d{2,3})\s+days",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return int(match.group(1)), f"Regex match: {match.group(0)[:140]}"
    if re.search(r"one year", text, flags=re.I):
        return 365, "Detected one-year lock-up"
    return None, None


def extract_lockup_days(html_text: str) -> tuple[int, str]:
    text = _strip_html(html_text)
    for heading in LOCKUP_SECTION_HEADINGS:
        section = _find_section_window(text, heading)
        if not section:
            continue
        parsed_days, reason = _extract_lockup_days_from_text(section)
        if parsed_days is not None:
            return parsed_days, f"{heading.title()} section: {reason}"
    parsed_days, reason = _extract_lockup_days_from_text(text)
    if parsed_days is not None and reason:
        return parsed_days, reason
    return DEFAULT_LOCKUP_DAYS, "Defaulted to 180 days after no confident lock-up match"


def extract_ipo_date_from_text(html_text: str) -> str | None:
    text = _strip_html(html_text)
    patterns = [
        r"began trading on ([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
        r"completed the closing of the IPO on ([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
        r"priced on ([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            parsed = datetime.strptime(match.group(1), "%B %d, %Y").date()
            return parsed.isoformat()
    return None


def _normalize_holder_key(column: str) -> str:
    lower = column.strip().lower()
    if any(token in lower for token in ("beneficial owner", "holder", "owner", "name")):
        return "holder"
    if any(token in lower for token in ("share", "shares", "units")):
        return "shares"
    if any(token in lower for token in ("percent", "%")):
        return "percent"
    if "voting" in lower:
        return "voting_power"
    return re.sub(r"\s+", " ", column.strip())


def _canonicalize_holder_row(row: pd.Series) -> dict[str, str]:
    record: dict[str, str] = {}
    for column, value in row.items():
        if pd.isna(value):
            continue
        text = str(value).strip()
        if not text or text.lower() == "nan":
            continue
        key = _normalize_holder_key(str(column))
        if key in record and key != str(column).strip():
            continue
        record[key] = text
    return record


def _table_score(table: pd.DataFrame) -> int:
    columns = " ".join(str(column).lower() for column in table.columns)
    score = 0
    for keyword in ("principal", "beneficial", "stockholder", "shareholder", "selling", "holder", "owner"):
        if keyword in columns:
            score += 2
    for cell in table.head(5).astype(str).fillna("").to_numpy().flatten():
        cell_text = str(cell).lower()
        if "share" in cell_text or "%" in cell_text:
            score += 1
        if any(token in cell_text for token in ("director", "officer", "fund", "capital")):
            score += 1
    return score


def _read_html_tables(html_text: str, match: str | None = None) -> list[pd.DataFrame]:
    html_io = StringIO(html_text)
    try:
        if match:
            return pd.read_html(html_io, match=match)
        return pd.read_html(html_io)
    except (ValueError, ImportError):
        return []


def extract_principal_holders(html_text: str) -> list[dict[str, str]]:
    tables: list[pd.DataFrame] = []
    for match in PRINCIPAL_TABLE_MATCHES:
        tables.extend(_read_html_tables(html_text, match=match))
    if not tables:
        tables = _read_html_tables(html_text)

    if not tables:
        return []

    scored_tables = sorted(tables, key=_table_score, reverse=True)
    holder_tables: list[dict[str, str]] = []
    for table in scored_tables:
        if _table_score(table) <= 0:
            continue
        for _, row in table.head(10).iterrows():
            record = _canonicalize_holder_row(row)
            if record:
                holder_tables.append(record)
        if holder_tables:
            break
    return holder_tables


def enrich_company(company: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch the most relevant IPO filing for a company and derive an unlock estimate.

    This is intentionally opinionated for the demo:
    - it prefers a final prospectus or registration statement
    - it falls back to the seeded IPO date and a 180-day lock-up if parsing is weak
    """

    base_ipo_date = date.fromisoformat(company["ipo_date"])
    try:
        filing_ref = find_latest_ipo_filing(company["cik"])
    except requests.RequestException as exc:
        unlock_date = base_ipo_date + timedelta(days=company["lockup_days"])
        return {
            "filing_form": None,
            "filing_date": None,
            "source_url": None,
            "lockup_days": company["lockup_days"],
            "unlock_date": unlock_date.isoformat(),
            "principal_holders": [],
            "lockup_source": "Seeded watchlist only",
            "notes": f"SEC enrichment failed: {exc}",
        }

    if filing_ref is None:
        unlock_date = base_ipo_date + timedelta(days=company["lockup_days"])
        return {
            "filing_form": None,
            "filing_date": None,
            "source_url": None,
            "lockup_days": company["lockup_days"],
            "unlock_date": unlock_date.isoformat(),
            "principal_holders": [],
            "lockup_source": "Seeded watchlist only",
            "notes": "No IPO-related filing found in recent SEC submissions.",
        }

    try:
        html_text = fetch_text(filing_ref.filing_url)
        parsed_lockup_days, lockup_source = extract_lockup_days(html_text)
        parsed_ipo_date = extract_ipo_date_from_text(html_text)
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
            "notes": f"SEC filing could not be parsed cleanly: {exc}",
        }
    ipo_date = date.fromisoformat(parsed_ipo_date) if parsed_ipo_date else base_ipo_date
    unlock_date = ipo_date + timedelta(days=parsed_lockup_days)

    if principal_holders:
        notes = f"Live SEC filing parsed successfully. Extracted {len(principal_holders)} holder rows."
    else:
        notes = "Live filing parsed, but the principal stockholder table was not extracted cleanly."

    return {
        "filing_form": filing_ref.form,
        "filing_date": filing_ref.filing_date,
        "source_url": filing_ref.filing_url,
        "lockup_days": parsed_lockup_days,
        "unlock_date": unlock_date.isoformat(),
        "principal_holders": principal_holders,
        "lockup_source": lockup_source,
        "notes": notes,
    }
