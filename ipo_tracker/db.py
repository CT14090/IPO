from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Sequence

from .config import WATCHLIST


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "ipo_lockup_tracker.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, ddl: str) -> None:
    if column_name in _table_columns(conn, table_name):
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def _row_value(row: sqlite3.Row | None, key: str, default):
    if row is None:
        return default
    keys = row.keys()
    if key not in keys:
        return default
    value = row[key]
    if value is None:
        return default
    return value


def _int_or_none(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def initialize_database() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL UNIQUE,
                company_name TEXT NOT NULL,
                cik INTEGER NOT NULL,
                ipo_date TEXT NOT NULL,
                lockup_days INTEGER NOT NULL,
                theme TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS company_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                filing_form TEXT,
                filing_date TEXT,
                source_url TEXT,
                lockup_days INTEGER NOT NULL,
                unlock_date TEXT NOT NULL,
                effective_unlock_date TEXT,
                principal_holders_json TEXT NOT NULL,
                lockup_source TEXT NOT NULL,
                lockup_conditions_json TEXT NOT NULL DEFAULT '{}',
                insider_sales_json TEXT NOT NULL DEFAULT '[]',
                ipo_price REAL,
                current_price REAL,
                price_change_pct REAL,
                avg_volume_30d INTEGER,
                market_cap INTEGER,
                market_data_note TEXT NOT NULL DEFAULT '',
                confidence_score INTEGER NOT NULL DEFAULT 0,
                confidence_label TEXT NOT NULL DEFAULT 'Seeded',
                confidence_details TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL,
                fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(company_id) REFERENCES companies(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS webhook_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                alert_date TEXT NOT NULL,
                webhook_url_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL,
                sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(company_id) REFERENCES companies(id)
            )
            """
        )
        _ensure_column(conn, "company_snapshots", "lockup_conditions_json", "TEXT NOT NULL DEFAULT '{}'" )
        _ensure_column(conn, "company_snapshots", "effective_unlock_date", "TEXT")
        _ensure_column(conn, "company_snapshots", "insider_sales_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "company_snapshots", "ipo_price", "REAL")
        _ensure_column(conn, "company_snapshots", "current_price", "REAL")
        _ensure_column(conn, "company_snapshots", "price_change_pct", "REAL")
        _ensure_column(conn, "company_snapshots", "avg_volume_30d", "INTEGER")
        _ensure_column(conn, "company_snapshots", "market_cap", "INTEGER")
        _ensure_column(conn, "company_snapshots", "market_data_note", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "company_snapshots", "confidence_score", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "company_snapshots", "confidence_label", "TEXT NOT NULL DEFAULT 'Seeded'")
        _ensure_column(conn, "company_snapshots", "confidence_details", "TEXT NOT NULL DEFAULT ''")
        conn.commit()


def seed_companies() -> None:
    initialize_database()
    with get_connection() as conn:
        existing = {
            row["ticker"]
            for row in conn.execute("SELECT ticker FROM companies").fetchall()
        }
        for company in WATCHLIST:
            if company["ticker"] in existing:
                continue
            conn.execute(
                """
                INSERT INTO companies (ticker, company_name, cik, ipo_date, lockup_days, theme)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    company["ticker"],
                    company["company_name"],
                    company["cik"],
                    company["ipo_date"].isoformat(),
                    company["lockup_days"],
                    company["theme"],
                ),
            )
        conn.commit()


def fetch_companies() -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, ticker, company_name, cik, ipo_date, lockup_days, theme
            FROM companies
            ORDER BY ipo_date DESC, ticker ASC
            """
        ).fetchall()
        return rows


def upsert_snapshot(
    company_id: int,
    *,
    filing_form: str | None,
    filing_date: str | None,
    source_url: str | None,
    lockup_days: int,
    unlock_date: str,
    effective_unlock_date: str | None,
    principal_holders: Sequence[dict] | None,
    lockup_source: str,
    lockup_conditions: dict | None,
    insider_sales: Sequence[dict] | None,
    ipo_price: float | None,
    current_price: float | None,
    price_change_pct: float | None,
    avg_volume_30d: int | None,
    market_cap: int | None,
    market_data_note: str,
    confidence_score: int,
    confidence_label: str,
    confidence_details: str,
    notes: str,
    **_extra: object,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO company_snapshots (
                company_id, filing_form, filing_date, source_url, lockup_days,
                unlock_date, effective_unlock_date, principal_holders_json, lockup_source,
                lockup_conditions_json, insider_sales_json, ipo_price, current_price,
                price_change_pct, avg_volume_30d, market_cap, market_data_note,
                confidence_score, confidence_label, confidence_details, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_id,
                filing_form,
                filing_date,
                source_url,
                lockup_days,
                unlock_date,
                effective_unlock_date,
                json.dumps(list(principal_holders or []), default=str),
                lockup_source,
                json.dumps(lockup_conditions or {}, default=str),
                json.dumps(list(insider_sales or []), default=str),
                ipo_price,
                current_price,
                price_change_pct,
                avg_volume_30d,
                market_cap,
                market_data_note,
                confidence_score,
                confidence_label,
                confidence_details,
                notes,
            ),
        )
        conn.commit()


def fetch_latest_snapshots() -> dict[int, sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.*
            FROM company_snapshots s
            INNER JOIN (
                SELECT company_id, MAX(id) AS max_id
                FROM company_snapshots
                GROUP BY company_id
            ) latest ON latest.max_id = s.id
            """
        ).fetchall()
        return {row["company_id"]: row for row in rows}


def load_dashboard_rows() -> list[dict]:
    companies = fetch_companies()
    snapshots = fetch_latest_snapshots()
    rows: list[dict] = []
    for row in companies:
        snapshot = snapshots.get(row["id"])
        rows.append(
            {
                "company_id": row["id"],
                "ticker": row["ticker"],
                "company_name": row["company_name"],
                "cik": row["cik"],
                "ipo_date": row["ipo_date"],
                "lockup_days": row["lockup_days"],
                "theme": row["theme"],
                "filing_form": _row_value(snapshot, "filing_form", None),
                "filing_date": _row_value(snapshot, "filing_date", None),
                "source_url": _row_value(snapshot, "source_url", None),
                "unlock_date": _row_value(snapshot, "unlock_date", None),
                "effective_unlock_date": _row_value(snapshot, "effective_unlock_date", None),
                "principal_holders": json.loads(_row_value(snapshot, "principal_holders_json", "[]")),
                "lockup_source": _row_value(snapshot, "lockup_source", "Seeded watchlist"),
                "lockup_conditions": json.loads(_row_value(snapshot, "lockup_conditions_json", "{}")),
                "insider_sales": json.loads(_row_value(snapshot, "insider_sales_json", "[]")),
                "ipo_price": _float_or_none(_row_value(snapshot, "ipo_price", None)),
                "current_price": _float_or_none(_row_value(snapshot, "current_price", None)),
                "price_change_pct": _float_or_none(_row_value(snapshot, "price_change_pct", None)),
                "avg_volume_30d": _int_or_none(_row_value(snapshot, "avg_volume_30d", None)),
                "market_cap": _int_or_none(_row_value(snapshot, "market_cap", None)),
                "market_data_note": _row_value(snapshot, "market_data_note", ""),
                "confidence_score": int(_row_value(snapshot, "confidence_score", 0)),
                "confidence_label": _row_value(snapshot, "confidence_label", "Seeded"),
                "confidence_details": _row_value(snapshot, "confidence_details", "Seeded watchlist entry ready for SEC enrichment."),
                "notes": _row_value(snapshot, "notes", "Seeded watchlist entry ready for SEC enrichment."),
            }
        )
    return rows


def record_webhook_event(
    *,
    company_id: int,
    alert_date: str,
    webhook_url_hash: str,
    payload: dict,
    status: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO webhook_events (
                company_id, alert_date, webhook_url_hash, payload_json, status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (company_id, alert_date, webhook_url_hash, json.dumps(payload), status),
        )
        conn.commit()


def webhook_event_exists(*, company_id: int, alert_date: str, webhook_url_hash: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM webhook_events
            WHERE company_id = ? AND alert_date = ? AND webhook_url_hash = ?
            LIMIT 1
            """,
            (company_id, alert_date, webhook_url_hash),
        ).fetchone()
        return row is not None
