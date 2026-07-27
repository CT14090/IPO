from __future__ import annotations

from datetime import date
from typing import Any
from xml.etree import ElementTree as ET

import requests

from .sec import fetch_json, fetch_text, filing_document_url, submissions_url


FORM4_FORMS = {"4", "4/A"}
SALE_TRANSACTION_CODES = {"S"}


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

    recent = submissions.get("filings", {}).get("recent", {})
    forms = _recent_filing_values(recent, "form")
    accession_numbers = _recent_filing_values(recent, "accessionNumber")
    primary_documents = _recent_filing_values(recent, "primaryDocument")
    filing_dates = _recent_filing_values(recent, "filingDate")

    sales: list[dict[str, Any]] = []
    for form, accession_number, primary_document, filing_date in zip(
        forms,
        accession_numbers,
        primary_documents,
        filing_dates,
    ):
        if form not in FORM4_FORMS:
            continue
        filing_dt = _parse_iso_date(filing_date)
        if filing_dt is None or filing_dt < unlock_dt:
            continue

        source_url = filing_document_url(cik, accession_number, primary_document)
        try:
            xml_text = fetch_text(source_url)
        except requests.RequestException:
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
