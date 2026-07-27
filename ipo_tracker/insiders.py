from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import PurePosixPath
import re
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import requests


ATOM_NS = "{http://www.w3.org/2005/Atom}"
FORM4_FORMS = {"4", "4/A"}
LOOKUP_META_KEY = "_lookup"
OWNER_INCLUDE_FORM4_COUNT = 100
OWNER_INCLUDE_FORM4_FEED = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcompany&CIK={cik}&type=4&dateb=&owner=include"
    "&count={count}&output=atom"
)
SALE_TRANSACTION_CODES = {"S"}


def _normalize_cik(cik: int | str) -> str:
    from .sec import normalize_cik

    return normalize_cik(cik)


def _sec_headers() -> dict[str, str]:
    from .sec import sec_headers

    return sec_headers()


def _fetch_sec_text(url: str) -> str:
    from .sec import fetch_text

    return fetch_text(url)


def _strip_namespaces(root: ET.Element) -> None:
    for element in root.iter():
        if isinstance(element.tag, str) and "}" in element.tag:
            element.tag = element.tag.split("}", 1)[1]


def _node_text(node: ET.Element | None, path: str) -> str | None:
    if node is None:
        return None
    child = node.find(path)
    if child is None or child.text is None:
        return None
    text = child.text.strip()
    return text or None


def _parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _atom_text(node: ET.Element, tag_name: str) -> str:
    element = node.find(f"{ATOM_NS}{tag_name}")
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _atom_link(node: ET.Element) -> str:
    for link in node.findall(f"{ATOM_NS}link"):
        href = link.attrib.get("href", "").strip()
        if href:
            return href
    return ""


def _extract_form_from_entry(title: str, summary: str) -> str:
    combined = f"{title} {summary}"
    match = re.search(r"\b(4/A|4)\b", combined, flags=re.I)
    return match.group(1).upper() if match else ""


@lru_cache(maxsize=256)
def _fetch_owner_include_feed(normalized_cik: str) -> str:
    url = OWNER_INCLUDE_FORM4_FEED.format(cik=normalized_cik, count=OWNER_INCLUDE_FORM4_COUNT)
    response = requests.get(url, headers=_sec_headers(), timeout=30)
    response.raise_for_status()
    return response.text


def _parse_form4_feed_entries(feed_xml: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(feed_xml)
    except ET.ParseError:
        return []

    entries: list[dict[str, str]] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        title = _atom_text(entry, "title")
        summary = _atom_text(entry, "summary")
        form = _extract_form_from_entry(title, summary)
        filing_url = _atom_link(entry)
        filing_date = _atom_text(entry, "updated") or _atom_text(entry, "published")
        if not filing_date:
            filing_date = _node_text(entry, "filing-date") or ""
        entries.append(
            {
                "form": form,
                "filing_date": filing_date[:10],
                "filing_url": filing_url,
                "title": title,
                "summary": summary,
            }
        )
    return entries


def _xml_companion_name(primary_document: str) -> str | None:
    path = PurePosixPath(primary_document)
    suffix = path.suffix.lower()
    if suffix == ".xml":
        return None
    if suffix not in {".htm", ".html"}:
        return None
    return str(path.with_suffix(".xml"))


def _xml_companion_url(url: str) -> str | None:
    clean_url = url.split("#", 1)[0]
    path = PurePosixPath(clean_url)
    companion_name = _xml_companion_name(path.name)
    if companion_name is None:
        return None
    return clean_url[: -len(path.name)] + companion_name


def _absolute_sec_url(href: str, base_url: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(base_url, href)


def _candidate_document_urls_from_filing_url(filing_url: str) -> list[str]:
    normalized = filing_url.strip().split("#", 1)[0]
    if not normalized:
        return []

    candidates: list[str] = []
    is_detail_page = bool(re.search(r"-index\.html?$", normalized, flags=re.I)) or "browse-edgar" in normalized
    if "/Archives/" in normalized and not is_detail_page:
        candidates.append(normalized)
        companion_url = _xml_companion_url(normalized)
        if companion_url:
            candidates.append(companion_url)

    if is_detail_page or not candidates:
        try:
            detail_text = _fetch_sec_text(normalized)
        except requests.RequestException:
            detail_text = ""
        if detail_text:
            hrefs = re.findall(r"href=[\"']([^\"']+\.(?:xml|htm|html))[\"']", detail_text, flags=re.I)
            for href in hrefs:
                candidates.append(_absolute_sec_url(href, normalized))

    candidates.append(normalized)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in sorted(candidates, key=lambda value: (0 if value.lower().endswith(".xml") else 1, value)):
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def _lookup_record(lookup: dict[str, Any]) -> dict[str, Any]:
    return {LOOKUP_META_KEY: lookup}


def split_insider_sales_records(records: list[dict[str, Any]] | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lookup: dict[str, Any] = {}
    sales: list[dict[str, Any]] = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        meta = record.get(LOOKUP_META_KEY)
        if isinstance(meta, dict) and not lookup:
            lookup = meta
            continue
        sales.append(record)
    return lookup, sales


def parse_form4_sales(
    xml_text: str,
    *,
    filing_date: str,
    source_url: str,
    form: str,
) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    _strip_namespaces(root)

    owner_names: list[str] = []
    for owner in root.findall(".//reportingOwner"):
        owner_name = _node_text(owner, "reportingOwnerId/rptOwnerName")
        if owner_name and owner_name not in owner_names:
            owner_names.append(owner_name)
    owner_label = " / ".join(owner_names) if owner_names else None
    period_of_report = _node_text(root, ".//periodOfReport") or filing_date

    sales: list[dict[str, Any]] = []
    for transaction in root.findall(".//nonDerivativeTransaction"):
        transaction_code = _node_text(transaction, "transactionCoding/transactionCode")
        if transaction_code not in SALE_TRANSACTION_CODES:
            continue

        disposed_code = _node_text(
            transaction,
            "transactionAmounts/transactionAcquiredDisposedCode/value",
        )
        if disposed_code and disposed_code.upper() != "D":
            continue

        shares_sold = _parse_int(_node_text(transaction, "transactionAmounts/transactionShares/value"))
        if shares_sold is None:
            continue

        transaction_date = _node_text(transaction, "transactionDate/value") or period_of_report
        sales.append(
            {
                "owner_name": owner_label,
                "security_title": _node_text(transaction, "securityTitle/value"),
                "transaction_date": transaction_date,
                "shares_sold": shares_sold,
                "price_per_share": _parse_float(
                    _node_text(transaction, "transactionAmounts/transactionPricePerShare/value")
                ),
                "shares_owned_following_transaction": _parse_int(
                    _node_text(
                        transaction,
                        "postTransactionAmounts/sharesOwnedFollowingTransaction/value",
                    )
                ),
                "ownership_type": _node_text(
                    transaction,
                    "ownershipNature/directOrIndirectOwnership/value",
                ),
                "transaction_code": transaction_code,
                "filing_date": filing_date,
                "period_of_report": period_of_report,
                "form": form,
                "source_url": source_url,
            }
        )

    return sales


def fetch_post_unlock_sales(cik: int | str, unlock_date: str | None) -> list[dict[str, Any]]:
    unlock_dt = _parse_iso_date(unlock_date)
    normalized_cik = _normalize_cik(cik)
    feed_url = OWNER_INCLUDE_FORM4_FEED.format(cik=normalized_cik, count=OWNER_INCLUDE_FORM4_COUNT)
    lookup: dict[str, Any] = {
        "source": "SEC browse-edgar owner=include Atom",
        "feed_url": feed_url,
        "unlock_date": unlock_date,
        "status": "uninitialized",
        "reason": "",
        "feed_entries": 0,
        "candidate_filings": 0,
        "documents_fetched": 0,
        "xml_documents": 0,
        "transactions_parsed": 0,
        "latest_filing_date": None,
    }
    if unlock_dt is None:
        lookup["status"] = "invalid_unlock_date"
        lookup["reason"] = "Unlock date was missing or invalid, so Form 4 lookup did not run."
        return [_lookup_record(lookup)]

    try:
        feed_text = _fetch_owner_include_feed(normalized_cik)
    except requests.RequestException as exc:
        lookup["status"] = "feed_error"
        lookup["reason"] = f"Owner-include Form 4 feed request failed: {exc}"
        return [_lookup_record(lookup)]

    feed_entries = _parse_form4_feed_entries(feed_text)
    lookup["feed_entries"] = len(feed_entries)

    candidate_entries: list[dict[str, str]] = []
    for entry in feed_entries:
        form = entry.get("form")
        filing_dt = _parse_iso_date(entry.get("filing_date"))
        if form not in FORM4_FORMS or filing_dt is None or filing_dt < unlock_dt:
            continue
        candidate_entries.append(entry)

    lookup["candidate_filings"] = len(candidate_entries)
    if candidate_entries:
        lookup["latest_filing_date"] = max(entry.get("filing_date") or "" for entry in candidate_entries)
    if not candidate_entries:
        lookup["status"] = "no_form4_filings_after_unlock"
        lookup["reason"] = "No Form 4 or 4/A filings on or after the unlock date were listed in the SEC owner=include feed."
        return [_lookup_record(lookup)]

    sales: list[dict[str, Any]] = []
    for entry in candidate_entries:
        xml_text = ""
        source_url = None
        for candidate_url in _candidate_document_urls_from_filing_url(entry.get("filing_url", "")):
            try:
                candidate_text = _fetch_sec_text(candidate_url)
            except requests.RequestException:
                continue
            lookup["documents_fetched"] += 1
            if "<ownershipDocument" not in candidate_text:
                continue
            xml_text = candidate_text
            source_url = candidate_url
            lookup["xml_documents"] += 1
            break
        if not xml_text or not source_url:
            continue

        for sale in parse_form4_sales(
            xml_text,
            filing_date=entry.get("filing_date", ""),
            source_url=source_url,
            form=entry.get("form", ""),
        ):
            transaction_dt = _parse_iso_date(sale.get("transaction_date"))
            if transaction_dt is None or transaction_dt < unlock_dt:
                continue
            sales.append(sale)

    sales.sort(
        key=lambda item: (
            item.get("transaction_date") or item.get("filing_date") or "",
            item.get("owner_name") or "",
        ),
        reverse=True,
    )
    lookup["transactions_parsed"] = len(sales)
    if sales:
        lookup["status"] = "sales_parsed"
        lookup["reason"] = (
            f"Parsed {len(sales)} post-unlock sale transaction(s) from {lookup['xml_documents']} ownership document(s)."
        )
    elif lookup["xml_documents"]:
        lookup["status"] = "no_sale_transactions_after_unlock"
        lookup["reason"] = "Ownership documents were fetched, but no sale-code transactions on or after the unlock date were parsed."
    else:
        lookup["status"] = "filings_found_but_no_ownership_xml"
        lookup["reason"] = "The owner-include feed listed candidate Form 4 filings, but no ownership XML document could be resolved from them."

    return [_lookup_record(lookup), *sales]


def summarize_insider_sales(sales: list[dict[str, Any]] | None) -> dict[str, Any]:
    _, records = split_insider_sales_records(list(sales or []))
    total_shares_sold = 0
    for sale in records:
        shares_sold = sale.get("shares_sold")
        if isinstance(shares_sold, int):
            total_shares_sold += shares_sold

    filing_count = len({sale.get("source_url") for sale in records if sale.get("source_url")})
    latest_sale_date = max(
        (
            sale.get("transaction_date") or sale.get("filing_date") or ""
            for sale in records
            if sale.get("transaction_date") or sale.get("filing_date")
        ),
        default=None,
    )

    return {
        "transaction_count": len(records),
        "filing_count": filing_count,
        "total_shares_sold": total_shares_sold,
        "latest_sale_date": latest_sale_date,
    }
