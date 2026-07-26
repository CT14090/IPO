from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import Any
from xml.etree import ElementTree as ET

import requests

from .config import WATCHLIST
from .sec import normalize_cik, sec_headers


ATOM_NS = "{http://www.w3.org/2005/Atom}"

# ── Source URLs ────────────────────────────────────────────────────────────────
EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"
CURRENT_FILINGS_RSS = {
    "424B4": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=424B4&owner=include&count=100&output=atom",
    "S-1":   "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=S-1&owner=include&count=100&output=atom",
    "F-1":   "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=F-1&owner=include&count=100&output=atom",
}

# ── IPO vs. secondary / shelf filter signals ───────────────────────────────────
# These run client-side on RSS results; EFTS already filters server-side via q=
_IPO_POSITIVE_RE = re.compile(
    r"(initial public offering|our initial public offering|"
    r"first time we have offered|going public)",
    re.I,
)
_SECONDARY_DISQUALIFY_RE = re.compile(
    r"(secondary offering|resale prospectus|"
    r"selling stockholders are offering|"
    r"we are not selling any shares|"
    r"shelf registration)",
    re.I,
)

_MISSING_IDENTITY_VALUES = {
    "",
    "-",
    "—",
    "na",
    "n/a",
    "none",
    "null",
    "unknown",
    "unavailable",
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
    response = requests.get(
        "https://www.sec.gov/files/company_tickers_exchange.json",
        headers=sec_headers(),
        timeout=30,
    )
    response.raise_for_status()
    index: dict[int, dict[str, str]] = {}
    for row in response.json().get("data", []):
        if len(row) < 3:
            continue
        cik = int(row[0])
        index[cik] = {
            "ticker": str(row[2]).strip(),
            "title": str(row[1]).strip(),
            "exchange": str(row[3]).strip() if len(row) > 3 else "",
        }
    return index


@lru_cache(maxsize=256)
def fetch_submission_profile(cik: int) -> dict[str, str]:
    """
    Fallback identity lookup for CIKs that are not in the ticker index.

    The submissions endpoint exists for all filers and gives us the entity name,
    plus a ticker when one is available.
    """
    url = f"https://data.sec.gov/submissions/CIK{normalize_cik(cik)}.json"
    try:
        response = requests.get(url, headers=sec_headers(), timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        return {}

    payload = response.json()
    tickers = [str(item).strip() for item in payload.get("tickers", []) if str(item).strip()]
    exchanges = [str(item).strip() for item in payload.get("exchanges", []) if str(item).strip()]
    title = _pick_identity(
        payload.get("name"),
        payload.get("entityName"),
        payload.get("companyName"),
    )
    return {
        "ticker": tickers[0] if tickers else "",
        "title": title,
        "exchange": exchanges[0] if exchanges else "",
    }


def _is_missing_identity(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip().lower()
    return text in _MISSING_IDENTITY_VALUES


def _is_placeholder_company_name(value: Any) -> bool:
    if _is_missing_identity(value):
        return True
    text = str(value).strip().lower()
    return bool(re.fullmatch(r"cik\s+\d+", text))


def _pick_identity(*values: Any) -> str:
    for value in values:
        if not _is_missing_identity(value):
            return str(value).strip()
    return ""


def _pick_display_identity(*values: Any) -> str:
    for value in values:
        if _is_placeholder_company_name(value):
            continue
        picked = _pick_identity(value)
        if picked:
            return picked
    return ""


def _resolve_company_identity(cik: int, company_index: dict[int, dict[str, str]]) -> tuple[str, str | None, str, str]:
    meta = company_index.get(cik, {})
    profile = fetch_submission_profile(cik)

    name = _pick_identity(meta.get("title"), profile.get("title")) or f"CIK {cik}"
    ticker = _pick_identity(meta.get("ticker"), profile.get("ticker")) or None
    exchange = _pick_identity(meta.get("exchange"), profile.get("exchange"))

    source_parts: list[str] = []
    if meta:
        source_parts.append("ticker index")
    if profile:
        source_parts.append("submissions profile")
    if not source_parts:
        source_parts.append("SEC lookup")

    return name, ticker, exchange, ", ".join(source_parts)


def _ipo_confidence(title: str, summary: str, has_ticker: bool) -> tuple[str, str]:
    """
    Score a filing as High / Medium / Low IPO confidence.

    Low    - explicit secondary / shelf signal in text
    High   - explicit IPO language AND ticker is mapped
    Medium - no disqualifying signals, or IPO language without ticker
    """
    combined = f"{title} {summary}"
    disq = _SECONDARY_DISQUALIFY_RE.search(combined)
    if disq:
        return "Low", f"Disqualified: {disq.group(0)[:60]}"
    pos = _IPO_POSITIVE_RE.search(combined)
    if pos:
        reason = f"IPO signal: '{pos.group(0)[:40]}'"
        return ("High" if has_ticker else "Medium"), reason
    return "Medium", "No disqualifying signals; unverified"


# ── EFTS full-text search (primary path) ──────────────────────────────────────
def _search_efts(
    *,
    watched_ciks: set[int],
    company_index: dict[int, dict[str, str]],
    lookback_days: int = 90,
    page_size: int = 40,
) -> list[DiscoveryCandidate]:
    """
    Query efts.sec.gov full-text search for 424B4 / S-1 / F-1 filings that
    explicitly mention 'initial public offering'. No API key required.

    Server-side filtering removes secondaries and shelf registrations before
    the response reaches us, so client-side scoring is a safety net only.
    """
    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    end = date.today().isoformat()
    params: dict[str, Any] = {
        "q": '"initial public offering"',
        "forms": "424B4,S-1,F-1",
        "dateRange": "custom",
        "startdt": start,
        "enddt": end,
        "from": 0,
        "hits.hits._source": "entity_name,file_date,form_type",
    }
    try:
        response = requests.get(
            EFTS_BASE,
            params=params,
            headers=sec_headers(),
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException:
        return []

    hits = response.json().get("hits", {}).get("hits", [])
    candidates: list[DiscoveryCandidate] = []
    seen: set[int] = set()

    for hit in hits:
        src = hit.get("_source", {})
        entity_name = _pick_identity(src.get("entity_name"), src.get("company_name"), src.get("issuer_name"))
        form_type = _pick_identity(src.get("form_type"), src.get("form"), src.get("type")) or "—"
        file_date = src.get("file_date", "")

        cik_match = re.match(r"^0*(\d+)-", hit.get("_id", ""))
        if not cik_match:
            continue
        cik = int(cik_match.group(1))
        if cik == 0 or cik in watched_ciks or cik in seen:
            continue
        seen.add(cik)

        resolved_name, ticker, exchange, source = _resolve_company_identity(cik, company_index)
        name = _pick_display_identity(entity_name, resolved_name, src.get("company_name"), src.get("issuer_name"))
        if _is_placeholder_company_name(name):
            continue

        ticker = _pick_identity(ticker, src.get("ticker"), src.get("symbol")) or None
        exchange = _pick_identity(exchange)
        confidence, reason = _ipo_confidence(entity_name, "", bool(ticker))
        if confidence == "Low":
            continue

        filing_url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar"
            f"?action=getcompany&CIK={normalize_cik(cik)}"
            f"&type={form_type}&dateb=&owner=include&count=1"
        )
        reason_bits = ["EFTS full-text match", reason]
        if source:
            reason_bits.append(f"resolved via {source}")
        if exchange:
            reason_bits.append(f"exchange: {exchange}")
        candidates.append(DiscoveryCandidate(
            company_name=name,
            ticker=ticker,
            cik=cik,
            form=form_type,
            filing_date=file_date,
            filing_url=filing_url,
            reason="; ".join(reason_bits),
            confidence=confidence,
        ))

    return candidates


# ── RSS current-filings feed (fallback path) ──────────────────────────────────
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
    m = re.search(r"CIK[:\s]+0*(\d+)", text, flags=re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"/data/(\d+)/", text)
    if m:
        return int(m.group(1))
    return None


def parse_discovery_candidates(
    feed_xml: str,
    *,
    form: str,
    watched_ciks: set[int],
    company_index: dict[int, dict[str, str]],
) -> list[DiscoveryCandidate]:
    """Parse an EDGAR Atom RSS feed entry list into DiscoveryCandidate objects."""
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

        resolved_name, ticker, exchange, source = _resolve_company_identity(cik, company_index)
        fallback_name = _pick_display_identity(
            title.replace(f"{form} -", "").strip(),
            title,
            summary,
            resolved_name,
            f"CIK {cik}",
        )
        name = fallback_name or _pick_display_identity(resolved_name, title, summary)
        if _is_placeholder_company_name(name):
            continue

        confidence, reason = _ipo_confidence(title, summary, bool(ticker))
        if confidence == "Low":
            continue  # drop confirmed secondaries / shelf registrations

        seen.add(cik)
        reason_bits = [f"SEC RSS ({form})", reason]
        if source:
            reason_bits.append(f"resolved via {source}")
        if exchange:
            reason_bits.append(f"exchange: {exchange}")
        candidates.append(DiscoveryCandidate(
            company_name=name,
            ticker=ticker,
            cik=cik,
            form=form,
            filing_date=filing_date,
            filing_url=filing_url,
            reason="; ".join(reason_bits),
            confidence=confidence,
        ))

    return candidates


# ── Public entrypoint ─────────────────────────────────────────────────────────
def discover_recent_ipo_candidates(limit: int = 20) -> list[dict[str, Any]]:
    """
    Discover recent IPO candidates from SEC filings.

    Primary path  - EFTS full-text search with q="initial public offering",
                    which filters out secondaries server-side.
    Fallback path - RSS current-filings feeds for 424B4, S-1, F-1 with
                    client-side IPO/secondary scoring.

    Results sorted: High confidence first, then most-recent filing date.
    Low-confidence candidates (confirmed secondaries/shelf) are dropped.
    """
    watched_ciks = {company["cik"] for company in WATCHLIST}
    company_index = fetch_company_index()

    # Primary: EFTS full-text search
    candidates = _search_efts(watched_ciks=watched_ciks, company_index=company_index)

    # Fallback: RSS feeds if EFTS unavailable
    if not candidates:
        by_cik: dict[int, DiscoveryCandidate] = {}
        for form, url in CURRENT_FILINGS_RSS.items():
            try:
                response = requests.get(url, headers=sec_headers(), timeout=30)
                response.raise_for_status()
            except requests.RequestException:
                continue
            for candidate in parse_discovery_candidates(
                response.text,
                form=form,
                watched_ciks=watched_ciks,
                company_index=company_index,
            ):
                existing = by_cik.get(candidate.cik)
                if existing is None or candidate.filing_date >= existing.filing_date:
                    by_cik[candidate.cik] = candidate
        candidates = list(by_cik.values())

    candidates.sort(key=lambda c: c.filing_date, reverse=True)
    priority = {"High": 0, "Medium": 1, "Low": 2}
    sorted_candidates = sorted(candidates, key=lambda c: (priority.get(c.confidence, 9), c.filing_date), reverse=False)

    return [c.as_dict() for c in sorted_candidates[:limit]]
