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
    "lock-up period",
    "lockup period",
    "lock-up restrictions",
    "shares eligible for future sale",
    "underwriting",
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
    "beneficial owner",
    "beneficial owners",
    "holder",
    "holders",
    "name",
    "name of beneficial owner",
    "principal stockholder",
    "principal stockholders",
    "selling stockholder",
    "selling stockholders",
    "stockholder",
    "stockholders",
    "shareholder",
    "shareholders",
    "total",
}


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
        "principal",
        "beneficial",
        "beneficially owned",
        "stockholder",
        "shareholder",
        "selling",
        "holder",
        "owner",
        "ownership",
        "voting",
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


def _read_html_tables(html_text: str, match: str | None = None) -> list[pd.DataFrame]:
    html_io = StringIO(html_text)
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
