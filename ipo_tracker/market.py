from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any

try:
    import yfinance as yf
    _YFINANCE_AVAILABLE = True
except ImportError:
    _YFINANCE_AVAILABLE = False


MARKET_VALUE_KEYS = (
    "ipo_price",
    "current_price",
    "price_change_pct",
    "avg_volume_30d",
    "market_cap",
)
MARKET_PREVIOUS_AVAILABLE_NOTE = "Previous snapshot market data available: yes."
MARKET_PREVIOUS_MISSING_NOTE = "Previous snapshot market data available: no."
MARKET_REUSED_NOTE = "Reusing previous snapshot market data."
MARKET_CACHE_REUSED_NOTE = "Reusing in-process market cache."
MARKET_CACHE_TTL_SECONDS = 900
_MARKET_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}


def _safe_float(value: Any) -> float | None:
    try:
        f = float(value)
        return None if f != f else f  # reject NaN
    except (TypeError, ValueError):
        return None



def _append_note(note: str, extra: str) -> str:
    note = note.strip()
    if not note:
        return extra
    if extra in note:
        return note
    return f"{note} {extra}"



def _copy_market_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload)



def _market_cache_key(ticker: str, ipo_date: str) -> tuple[str, str]:
    return ticker.upper().strip(), ipo_date.strip()



def _market_cache_get(ticker: str, ipo_date: str) -> dict[str, Any] | None:
    key = _market_cache_key(ticker, ipo_date)
    cached = _MARKET_CACHE.get(key)
    if cached is None:
        return None
    cached_at, payload = cached
    if time.time() - cached_at > MARKET_CACHE_TTL_SECONDS:
        _MARKET_CACHE.pop(key, None)
        return None
    result = _copy_market_payload(payload)
    note = str(result.get("market_data_note", "")).strip()
    result["market_data_note"] = _append_note(note, MARKET_CACHE_REUSED_NOTE)
    return result



def _market_cache_set(ticker: str, ipo_date: str, payload: dict[str, Any]) -> dict[str, Any]:
    stored = _copy_market_payload(payload)
    _MARKET_CACHE[_market_cache_key(ticker, ipo_date)] = (time.time(), stored)
    return _copy_market_payload(stored)



def market_data_has_values(data: dict[str, Any] | None) -> bool:
    if not isinstance(data, dict):
        return False
    return any(data.get(key) is not None for key in MARKET_VALUE_KEYS)



def calculate_price_change_pct(ipo_price: Any, current_price: Any) -> float | None:
    """Return the percentage move from IPO price to current price."""
    ipo = _safe_float(ipo_price)
    current = _safe_float(current_price)
    if ipo is None or current is None or ipo <= 0:
        return None
    return round((current - ipo) / ipo * 100, 2)



def merge_market_snapshot(previous_snapshot: dict[str, Any], latest_market: dict[str, Any]) -> dict[str, Any]:
    """
    Keep the last good market snapshot when a live yfinance refresh fails.

    This prevents a transient Yahoo rate limit from overwriting already-good
    market data with all-null fields.
    """
    if market_data_has_values(latest_market):
        return latest_market

    note = str(latest_market.get("market_data_note", "")).strip()
    if not note.startswith("Market data fetch failed:"):
        return latest_market

    previous_market = {key: previous_snapshot.get(key) for key in MARKET_VALUE_KEYS}
    if not market_data_has_values(previous_market):
        return {
            **latest_market,
            "market_data_note": _append_note(note, MARKET_PREVIOUS_MISSING_NOTE),
        }

    price_change_pct = previous_snapshot.get("price_change_pct")
    if price_change_pct is None:
        price_change_pct = calculate_price_change_pct(
            previous_snapshot.get("ipo_price"),
            previous_snapshot.get("current_price"),
        )

    return {
        "ipo_price": previous_snapshot.get("ipo_price"),
        "current_price": previous_snapshot.get("current_price"),
        "price_change_pct": price_change_pct,
        "avg_volume_30d": previous_snapshot.get("avg_volume_30d"),
        "market_cap": previous_snapshot.get("market_cap"),
        "data_source": latest_market.get("data_source", "yfinance"),
        "market_data_note": _append_note(
            _append_note(note, MARKET_PREVIOUS_AVAILABLE_NOTE),
            MARKET_REUSED_NOTE,
        ),
    }



def fetch_market_data(ticker: str, ipo_date: str) -> dict[str, Any]:
    """
    Fetch price and volume context for a watchlist company using yfinance.

    Returns a dict with these keys (all nullable):
        ipo_price          float | None  — closing price on IPO date
        current_price      float | None  — most recent closing price
        price_change_pct   float | None  — % change from IPO price to current
        avg_volume_30d     int   | None  — 30-day average daily volume
        market_cap         int   | None  — current market cap in USD
        data_source        str           — always "yfinance"
        market_data_note   str           — human-readable status / warning
    """
    empty: dict[str, Any] = {
        "ipo_price": None,
        "current_price": None,
        "price_change_pct": None,
        "avg_volume_30d": None,
        "market_cap": None,
        "data_source": "yfinance",
        "market_data_note": "",
    }

    if not _YFINANCE_AVAILABLE:
        empty["market_data_note"] = "yfinance not installed; run: pip install yfinance"
        return empty

    if not ticker or ticker == "—":
        empty["market_data_note"] = "No ticker available for this company"
        return empty

    cached = _market_cache_get(ticker, ipo_date)
    if cached is not None:
        return cached

    try:
        stock = yf.Ticker(ticker)

        # Current price + market cap
        info = stock.info or {}
        current_price = (
            _safe_float(info.get("currentPrice"))
            or _safe_float(info.get("regularMarketPrice"))
            or _safe_float(info.get("previousClose"))
        )
        market_cap: int | None = None
        raw_cap = info.get("marketCap")
        if raw_cap is not None:
            try:
                market_cap = int(raw_cap)
            except (TypeError, ValueError):
                pass

        # IPO-date closing price. Fetch a 5-day window to handle weekends / holidays.
        ipo_date_obj = date.fromisoformat(ipo_date)
        hist_end = (ipo_date_obj + timedelta(days=5)).isoformat()
        hist = stock.history(start=ipo_date_obj.isoformat(), end=hist_end)
        ipo_price: float | None = None
        if not hist.empty:
            ipo_price = _safe_float(hist["Close"].iloc[0])

        # 30-day average daily volume.
        vol_end = date.today()
        vol_start = vol_end - timedelta(days=45)
        vol_hist = stock.history(
            start=vol_start.isoformat(), end=vol_end.isoformat()
        )
        avg_volume_30d: int | None = None
        if not vol_hist.empty:
            recent = vol_hist["Volume"].tail(30)
            if len(recent) > 0:
                avg_volume_30d = int(recent.mean())

        price_change_pct = calculate_price_change_pct(ipo_price, current_price)

        note = "Live data from Yahoo Finance via yfinance"
        if current_price is None:
            note = "Price data unavailable — ticker may not be listed yet"

        result = {
            "ipo_price": round(ipo_price, 2) if ipo_price else None,
            "current_price": round(current_price, 2) if current_price else None,
            "price_change_pct": price_change_pct,
            "avg_volume_30d": avg_volume_30d,
            "market_cap": market_cap,
            "data_source": "yfinance",
            "market_data_note": note,
        }
        return _market_cache_set(ticker, ipo_date, result)

    except Exception as exc:
        empty["market_data_note"] = f"Market data fetch failed: {exc}"
        return _market_cache_set(ticker, ipo_date, empty)
