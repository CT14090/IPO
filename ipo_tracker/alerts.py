from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

import requests


def hash_webhook_url(webhook_url: str) -> str:
    return hashlib.sha256(webhook_url.encode("utf-8")).hexdigest()


def build_discord_payload(company: dict[str, Any], days_to_expiration: int, reference_date: date) -> dict[str, Any]:
    unlock_date = company["unlock_date"]
    return {
        "content": (
            f"IPO lock-up alert: {company['ticker']} ({company['company_name']}) reaches unlock eligibility "
            f"in {days_to_expiration} days on {unlock_date}."
        ),
        "embeds": [
            {
                "title": f"{company['ticker']} unlock alert",
                "description": company.get("notes", "Lock-up milestone reached."),
                "color": 15158332,
                "fields": [
                    {"name": "Company", "value": company["company_name"], "inline": True},
                    {"name": "Ticker", "value": company["ticker"], "inline": True},
                    {"name": "IPO Date", "value": company["ipo_date"], "inline": True},
                    {"name": "Unlock Date", "value": unlock_date, "inline": True},
                    {"name": "Days to Expiration", "value": str(days_to_expiration), "inline": True},
                    {"name": "Reference Date", "value": reference_date.isoformat(), "inline": True},
                ],
            }
        ],
    }


def send_discord_webhook(
    webhook_url: str,
    company: dict[str, Any],
    days_to_expiration: int,
    reference_date: date,
) -> requests.Response:
    """
    Send a Discord message only when a company reaches the three-day alert boundary.

    The caller should guard this function so that it only runs when `days_to_expiration == 3`.
    """

    if days_to_expiration != 3:
        raise ValueError("Discord alerts are only sent when days_to_expiration == 3")
    payload = build_discord_payload(company, days_to_expiration, reference_date)
    response = requests.post(webhook_url, json=payload, timeout=20)
    response.raise_for_status()
    return response

