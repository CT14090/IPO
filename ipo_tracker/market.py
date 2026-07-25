from __future__ import annotations

from datetime import date, timedelta
from typing import Any

try:
    import yfinance as yf
    _YFINANCE_AVAILABLE = True
except ImportError:
    _YFINANCE_AVAILABLE = False


def _safe_float(value: Any) -> float | None:
    try:
        f = float(value)
        return None if f != f else f  # reject NaN
    except (TypeError, ValueError):
        return None


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

    try:
        stock = yf.Ticker(ticker)

        # ── Current price + market cap ─────────────────────────────────────
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

        # ── IPO-date closing price ─────────────────────────────────────────
        # Fetch a 5-day window to handle weekends / market holidays
        ipo_date_obj = date.fromisoformat(ipo_date)
        hist_end = (ipo_date_obj + timedelta(days=5)).isoformat()
        hist = stock.history(start=ipo_date_obj.isoformat(), end=hist_end)
        ipo_price: float | None = None
        if not hist.empty:
            ipo_price = _safe_float(hist["Close"].iloc[0])

        # ── 30-day average daily volume ────────────────────────────────────
        vol_end = date.today()
        vol_start = vol_end - timedelta(days=45)  # extra buffer for trading days
        vol_hist = stock.history(
            start=vol_start.isoformat(), end=vol_end.isoformat()
        )
        avg_volume_30d: int | None = None
        if not vol_hist.empty:
            recent = vol_hist["Volume"].tail(30)
            if len(recent) > 0:
                avg_volume_30d = int(recent.mean())

        # ── % change from IPO price to current ────────────────────────────
        price_change_pct: float | None = None
        if ipo_price and current_price and ipo_price > 0:
            price_change_pct = round(
                (current_price - ipo_price) / ipo_price * 100, 2
            )

        note = "Live data from Yahoo Finance via yfinance"
        if current_price is None:
            note = "Price data unavailable — ticker may not be listed yet"

        return {
            "ipo_price": round(ipo_price, 2) if ipo_price else None,
            "current_price": round(current_price, 2) if current_price else None,
            "price_change_pct": price_change_pct,
            "avg_volume_30d": avg_volume_30d,
            "market_cap": market_cap,
            "data_source": "yfinance",
            "market_data_note": note,
        }

    except Exception as exc:
        empty["market_data_note"] = f"Market data fetch failed: {exc}"
        return empty
