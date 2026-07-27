from __future__ import annotations

from datetime import date
from pathlib import PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET

import requests

from .sec import fetch_json, fetch_text, filing_document_url, normalize_cik, submissions_url


FORM4_FORMS = {"4", "4/A"}
SALE_TRANSACTION_CODES = {"S"}
SUBMISSIONS_BASE_URL = "https://data.sec.gov/submissions/"


def _recent_filing_values(recent: dict[str, Any], key: str) -> list[str]:
    values = recent.get(key, [])
    if isinstance(values, list):
        return values
    return []


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
        return date.fromisoformat(value)
    except ValueError:
        return None


def _submission_fragment_url(name: str) -> str:
    if name.startswith("http://") or name.startswith("https://"):
        return name
    return f"{SUBMISSIONS_BASE_URL}{name.lstrip('/')}"


def _filing_records_from_container(container: dict[str, Any]) -> list[dict[str, str]]:
    forms = _recent_filing_values(container, "form")
    accession_numbers = _recent_filing_values(container, "accessionNumber")
    primary_documents = _recent_filing_values(container, "primaryDocument")
    filing_dates = _recent_filing_values(container, "filingDate")

    records: list[dict[str, str]] = []
    for form, accession_number, primary_document, filing_date in zip(
        forms,
        accession_numbers,
        primary_documents,
        filing_dates,
    ):
        records.append(
            {
                "form": form,
                "accession_number": accession_number,
                "primary_document": primary_document,
                "filing_date": filing_date,
            }
        )
    return records


def _iter_submission_records(submissions: dict[str, Any]) -> list[dict[str, str]]:
    records = _filing_records_from_container(submissions.get("filings", {}).get("recent", {}))

    for file_info in submissions.get("filings", {}).get("files", []):
        name = file_info.get("name")
        if not name:
            continue
        try:
            fragment = fetch_json(_submission_fragment_url(name))
        except requests.RequestException:
            continue
        if isinstance(fragment, dict) and "filings" in fragment:
            records.extend(_filing_records_from_container(fragment.get("filings", {}).get("recent", {})))
        elif isinstance(fragment, dict):
            records.extend(_filing_records_from_container(fragment))

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record.get("accession_number", ""), record.get("primary_document", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _xml_companion_name(primary_document: str) -> str | None:
    path = PurePosixPath(primary_document)
    suffix = path.suffix.lower()
    if suffix == ".xml":
        return None
    if suffix not in {".htm", ".html"}:
        return None
    return str(path.with_suffix(".xml"))


def _candidate_document_urls(cik: int | str, accession_number: str, primary_document: str) -> list[str]:
    candidates: list[str] = []
    companion_name = _xml_companion_name(primary_document)
    if companion_name:
        candidates.append(filing_document_url(cik, accession_number, companion_name))
    candidates.append(filing_document_url(cik, accession_number, primary_document))

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


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
    if unlock_dt is None:
        return []

    try:
        submissions = fetch_json(submissions_url(cik))
    except requests.RequestException:
        return []

    sales: list[dict[str, Any]] = []
    for record in _iter_submission_records(submissions):
        form = record.get("form")
        accession_number = record.get("accession_number")
        primary_document = record.get("primary_document")
        filing_date = record.get("filing_date")
        if form not in FORM4_FORMS:
            continue
        if not accession_number or not primary_document or not filing_date:
            continue

        filing_dt = _parse_iso_date(filing_date)
        if filing_dt is None or filing_dt < unlock_dt:
            continue

        xml_text = ""
        source_url = None
        for candidate_url in _candidate_document_urls(cik, accession_number, primary_document):
            try:
                candidate_text = fetch_text(candidate_url)
            except requests.RequestException:
                continue
            if "<ownershipDocument" not in candidate_text:
                continue
            xml_text = candidate_text
            source_url = candidate_url
            break
        if not xml_text or not source_url:
            continue

        for sale in parse_form4_sales(
            xml_text,
            filing_date=filing_date,
            source_url=source_url,
            form=form,
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
    return sales


def summarize_insider_sales(sales: list[dict[str, Any]] | None) -> dict[str, Any]:
    records = list(sales or [])
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
