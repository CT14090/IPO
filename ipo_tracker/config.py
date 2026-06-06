from __future__ import annotations

from datetime import date

DEMO_REFERENCE_DATE = date(2024, 9, 1)
DEFAULT_LOCKUP_DAYS = 180
DEFAULT_ALERT_DAYS = 3

WATCHLIST = [
    {
        "ticker": "RDDT",
        "company_name": "Reddit, Inc.",
        "cik": 1713445,
        "ipo_date": date(2024, 3, 21),
        "lockup_days": 180,
        "theme": "Consumer internet",
    },
    {
        "ticker": "ALAB",
        "company_name": "Astera Labs, Inc.",
        "cik": 1736297,
        "ipo_date": date(2024, 3, 20),
        "lockup_days": 180,
        "theme": "Semiconductors",
    },
    {
        "ticker": "KVYO",
        "company_name": "Klaviyo, Inc.",
        "cik": 1835830,
        "ipo_date": date(2023, 9, 20),
        "lockup_days": 180,
        "theme": "Marketing software",
    },
    {
        "ticker": "RBRK",
        "company_name": "Rubrik, Inc.",
        "cik": 1943896,
        "ipo_date": date(2024, 4, 25),
        "lockup_days": 180,
        "theme": "Data security",
    },
    {
        "ticker": "ARM",
        "company_name": "Arm Holdings plc",
        "cik": 1973239,
        "ipo_date": date(2023, 9, 14),
        "lockup_days": 180,
        "theme": "Semiconductors",
    },
]

