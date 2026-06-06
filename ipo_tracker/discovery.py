from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from xml.etree import ElementTree as ET

import requests

from .config import WATCHLIST
from .sec import sec_headers


ATOM_NS = "{http://www.w3.org/2005/Atom}"
CURRENT_FILINGS_URLS = {
    "424B4": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=424B4&owner=include&count=100&output=atom",
    "F-1": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=F-1&owner=include&count=100&output=atom",
}


@dataclass(slots=True)
class DiscoveryCandidate:
    company_name: str
    ticker: str | None
    cik: int
    form: str
    filing_date: str
    filing_url: str
    reason: str
    confidence: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "company_name": self.company_name,
            "ticker": self.ticker,
            "cik": self.cik,
            "form": self.form,
            "filing_date": self.filing_date,
            "filing_url": self.filing_url,
            "reason": self.reason,
            "confidence": self.confidence,
        }


@lru_cache(maxsize=1)
def fetch_company_index() -> dict[int, dict[str, str]]:
    response = requests.get("https://www.sec.gov/files/company_tickers_exchange.json", headers=sec_headers(), timeout=30)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", [])
    index: dict[int, dict[str, str]] = {}
    for row in data:
        if len(row) < 3:
            continue
        cik = int(row[0])
        index[cik] = {
            "ticker": str(row[2]).strip(),
            "title": str(row[1]).strip(),
            "exchange": str(row[3]).strip() if len(row) > 3 else "",
        }
    return index


def _entry_text(entry: ET.Element, tag_name: str) -> str:
    element = entry.find(f"{ATOM_NS}{tag_name}")
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _entry_link(entry: ET.Element) -> str:
    for link in entry.findall(f"{ATOM_NS}link"):
        href = link.attrib.get("href", "").strip()
        if href:
            return href
    return ""


def _extract_cik(text: str) -> int | None:
    match = re.search(r"CIK[:\s]+0*(\d+)", text, flags=re.I)
    if match:
        return int(match.group(1))
    match = re.search(r"/data/(\d+)/", text)
    if match:
        return int(match.group(1))
    return None


def parse_discovery_candidates(feed_xml: str, *, form: str, watched_ciks: set[int], company_index: dict[int, dict[str, str]]) -> list[DiscoveryCandidate]:
    root = ET.fromstring(feed_xml)
    candidates: list[DiscoveryCandidate] = []
    seen: set[int] = set()

    for entry in root.findall(f"{ATOM_NS}entry"):
        title = _entry_text(entry, "title")
        summary = _entry_text(entry, "summary")
        filing_url = _entry_link(entry)
        filing_date = _entry_text(entry, "published") or _entry_text(entry, "updated")
        cik = _extract_cik(summary) or _extract_cik(filing_url)
        if cik is None or cik in watched_ciks or cik in seen:
            continue
        seen.add(cik)

        company_meta = company_index.get(cik, {})
        ticker = company_meta.get("ticker") or None
        company_name = company_meta.get("title") or company_meta.get("name") or title.replace(f"{form} -", "").strip() or title
        reason_bits = [f"SEC current filing type {form}"]
        if "initial public offering" in f"{title} {summary}".lower():
            reason_bits.append("mentions initial public offering")
        if ticker:
            reason_bits.append(f"mapped to ticker {ticker}")
        confidence = "High" if ticker else ("Medium" if cik else "Low")
        candidates.append(
            DiscoveryCandidate(
                company_name=company_name,
                ticker=ticker,
                cik=cik,
                form=form,
                filing_date=filing_date,
                filing_url=filing_url,
                reason="; ".join(reason_bits),
                confidence=confidence,
            )
        )
    return candidates


def discover_recent_ipo_candidates(limit: int = 10) -> list[dict[str, Any]]:
    watched_ciks = {company["cik"] for company in WATCHLIST}
    company_index = fetch_company_index()
    candidates: list[DiscoveryCandidate] = []

    for form, url in CURRENT_FILINGS_URLS.items():
        response = requests.get(url, headers=sec_headers(), timeout=30)
        response.raise_for_status()
        candidates.extend(
            parse_discovery_candidates(
                response.text,
                form=form,
                watched_ciks=watched_ciks,
                company_index=company_index,
            )
        )

    candidates.sort(key=lambda item: item.filing_date, reverse=True)
    return [candidate.as_dict() for candidate in candidates[:limit]]
