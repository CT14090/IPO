from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Any

import altair as alt
import pandas as pd
import requests
import streamlit as st

from ipo_tracker.alerts import hash_webhook_url, send_discord_webhook
from ipo_tracker.config import DEFAULT_ALERT_DAYS, DEMO_REFERENCE_DATE
from ipo_tracker.db import (
    initialize_database,
    load_dashboard_rows,
    record_webhook_event,
    seed_companies,
    upsert_snapshot,
    webhook_event_exists,
)
from ipo_tracker.discovery import discover_recent_ipo_candidates
from ipo_tracker.insiders import split_insider_sales_records, summarize_insider_sales
from ipo_tracker.market import calculate_price_change_pct, merge_market_snapshot
from ipo_tracker.sec import enrich_company


st.set_page_config(
    page_title="IPO Lockup Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def read_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
    except Exception:
        return default
    if value is None:
        return default
    return str(value).strip()


def ensure_sec_user_agent() -> str:
    user_agent = read_secret("sec_user_agent", "IPO Lockup Tracker demo you@example.com")
    os.environ["SEC_USER_AGENT"] = user_agent
    return user_agent


def _market_price_change_pct(row: dict) -> float | None:
    calculated = calculate_price_change_pct(row.get("ipo_price"), row.get("current_price"))
    if calculated is not None:
        return calculated
    stored = row.get("price_change_pct")
    if stored is None:
        return None
    try:
        return float(stored)
    except (TypeError, ValueError):
        return None


def _confidence_score(row: dict) -> int:
    try:
        return int(row.get("confidence_score", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _insider_sales_records(row: dict) -> list[dict[str, Any]]:
    records = row.get("insider_sales", [])
    return records if isinstance(records, list) else []


def _insider_sales(row: dict) -> list[dict[str, Any]]:
    _, sales = split_insider_sales_records(_insider_sales_records(row))
    return sales


def _insider_sales_lookup(row: dict) -> dict[str, Any]:
    lookup, _ = split_insider_sales_records(_insider_sales_records(row))
    if lookup:
        return lookup
    if not _has_unlocked_in_real_time(row):
        return {
            "status": "skipped_until_unlock",
            "reason": "Effective unlock date has not passed yet, so post-unlock Form 4 lookup has not run.",
        }
    return {
        "status": "no_lookup_metadata",
        "reason": "This snapshot predates the structured Form 4 lookup diagnostics rollout.",
    }


def _insider_sales_summary(row: dict) -> dict[str, Any]:
    return summarize_insider_sales(_insider_sales_records(row))


def _ownership_context(row: dict) -> dict[str, Any]:
    context = row.get("ownership_context", {})
    return context if isinstance(context, dict) else {}


def _current_unlock_date(row: dict) -> str | None:
    return row.get("effective_unlock_date") or row.get("unlock_date")


def _calendar_unlock_date(row: dict) -> str | None:
    return row.get("unlock_date")


def _has_unlocked_in_real_time(row: dict) -> bool:
    unlock_date = _current_unlock_date(row)
    if not unlock_date:
        return False
    try:
        return date.fromisoformat(unlock_date) <= date.today()
    except ValueError:
        return False


def _review_state(row: dict, minimum_confidence: int) -> str:
    return "Needs review" if _confidence_score(row) < minimum_confidence else "Ready"


def _split_rows_by_confidence(rows: list[dict], minimum_confidence: int) -> tuple[list[dict], list[dict]]:
    ready_rows: list[dict] = []
    needs_review_rows: list[dict] = []
    for row in rows:
        if _review_state(row, minimum_confidence) == "Needs review":
            needs_review_rows.append(row)
        else:
            ready_rows.append(row)
    return ready_rows, needs_review_rows


def _table_rows(rows: list[dict], minimum_confidence: int) -> list[dict[str, Any]]:
    return [
        {
            "Company": row["company_name"],
            "Ticker": row["ticker"],
            "IPO Date": row["ipo_date"],
            "Unlock Date": row["unlock_date"],
            "Calendar Unlock": row.get("calendar_unlock_date") or row["unlock_date"],
            "Days to Expiration": row["days_to_expiration"],
            "Review": _review_state(row, minimum_confidence),
            "Confidence": f"{row.get('confidence_label', 'Seeded')} ({_confidence_score(row)}/100)",
            "Status": row["status"],
            "Lock-up Days": row["lockup_days"],
            "IPO Price": _format_currency(row.get("ipo_price")),
            "Current Price": _format_currency(row.get("current_price")),
            "% From IPO": _format_percent(_market_price_change_pct(row)),
            "30D Avg Volume": _format_integer(row.get("avg_volume_30d")),
            "Market Cap": _format_integer(row.get("market_cap")),
            "Tracked Holder %": _format_plain_percent(_ownership_context(row).get("tracked_holder_pct_of_offering")),
            "Offering Shares Out": _format_integer(_ownership_context(row).get("offering_shares_outstanding")),
            "Current Shares Out": _format_integer(_ownership_context(row).get("current_shares_outstanding")),
            "Post-Unlock Form 4 Sales": _insider_sales_summary(row)["transaction_count"],
            "Source": row["lockup_source"],
        }
        for row in rows
    ]


def _persist_snapshot(company_id: int, enriched: dict) -> None:
    """
    Keep refreshes resilient if a deployed app revision temporarily lags behind
    the latest database schema.
    """
    price_change_pct = _market_price_change_pct(enriched)
    snapshot_kwargs = {
        "filing_form": enriched["filing_form"],
        "filing_date": enriched["filing_date"],
        "source_url": enriched["source_url"],
        "lockup_days": enriched["lockup_days"],
        "unlock_date": enriched["unlock_date"],
        "effective_unlock_date": enriched.get("effective_unlock_date"),
        "principal_holders": enriched["principal_holders"],
        "lockup_source": enriched["lockup_source"],
        "lockup_conditions": enriched.get("lockup_conditions"),
        "ownership_context": enriched.get("ownership_context"),
        "insider_sales": enriched.get("insider_sales", []),
        "ipo_price": enriched.get("ipo_price"),
        "current_price": enriched.get("current_price"),
        "price_change_pct": price_change_pct,
        "avg_volume_30d": enriched.get("avg_volume_30d"),
        "market_cap": enriched.get("market_cap"),
        "market_data_note": enriched.get("market_data_note", ""),
        "confidence_score": enriched["confidence_score"],
        "confidence_label": enriched["confidence_label"],
        "confidence_details": enriched["confidence_details"],
        "notes": enriched["notes"],
    }
    upsert_snapshot(company_id, **snapshot_kwargs)


def _describe_request_error(exc: requests.RequestException) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        reason = response.reason or "HTTP error"
        return f"HTTP {response.status_code} {reason}"
    return str(exc) or exc.__class__.__name__


def refresh_live_data() -> tuple[list[dict], int, list[str]]:
    ensure_sec_user_agent()
    rows: list[dict] = []
    refreshed_count = 0
    warnings: list[str] = []
    for company in load_dashboard_rows():
        try:
            enriched = enrich_company(company)
        except requests.RequestException as exc:
            warnings.append(
                f"{company['ticker']}: refresh failed ({_describe_request_error(exc)}). Keeping the previous snapshot for this company."
            )
            rows.append(company)
            continue
        enriched.update(merge_market_snapshot(company, enriched))
        _persist_snapshot(company["company_id"], enriched)
        enriched["price_change_pct"] = _market_price_change_pct(enriched)
        rows.append({**company, **enriched})
        refreshed_count += 1
    return rows, refreshed_count, warnings


def compute_dashboard_rows(reference_date: date) -> list[dict]:
    rows = load_dashboard_rows()
    computed: list[dict] = []
    for row in rows:
        ipo_date = date.fromisoformat(row["ipo_date"])
        calendar_unlock_date = (
            date.fromisoformat(row["unlock_date"])
            if row["unlock_date"]
            else ipo_date + timedelta(days=row["lockup_days"])
        )
        effective_unlock_date = (
            date.fromisoformat(row["effective_unlock_date"])
            if row.get("effective_unlock_date")
            else calendar_unlock_date
        )
        days_to_expiration = (effective_unlock_date - reference_date).days
        days_since_ipo = (reference_date - ipo_date).days
        unlock_progress = max(0.0, min(1.0, days_since_ipo / max(1, row["lockup_days"])))
        computed.append(
            {
                **row,
                "unlock_date": effective_unlock_date.isoformat(),
                "effective_unlock_date": effective_unlock_date.isoformat(),
                "calendar_unlock_date": calendar_unlock_date.isoformat(),
                "days_to_expiration": days_to_expiration,
                "days_since_ipo": days_since_ipo,
                "unlock_progress": unlock_progress,
                "status": (
                    "Due soon"
                    if days_to_expiration == DEFAULT_ALERT_DAYS
                    else ("Upcoming" if days_to_expiration > 0 else "Expired")
                ),
            }
        )
    return sorted(computed, key=lambda item: (item["days_to_expiration"], item["ticker"]))


def maybe_send_alerts(rows: list[dict], webhook_url: str, reference_date: date) -> list[str]:
    messages: list[str] = []
    if not webhook_url:
        return messages
    webhook_hash = hash_webhook_url(webhook_url)
    for row in rows:
        if row["days_to_expiration"] != DEFAULT_ALERT_DAYS:
            continue
        if webhook_event_exists(
            company_id=row["company_id"],
            alert_date=reference_date.isoformat(),
            webhook_url_hash=webhook_hash,
        ):
            messages.append(f"Already sent an alert for {row['ticker']} on this date.")
            continue
        try:
            response = send_discord_webhook(webhook_url, row, row["days_to_expiration"], reference_date)
            record_webhook_event(
                company_id=row["company_id"],
                alert_date=reference_date.isoformat(),
                webhook_url_hash=webhook_hash,
                payload={
                    "ticker": row["ticker"],
                    "company_name": row["company_name"],
                    "days_to_expiration": row["days_to_expiration"],
                    "unlock_date": row["unlock_date"],
                },
                status=f"sent:{response.status_code}",
            )
            messages.append(f"Sent Discord alert for {row['ticker']}.")
        except Exception as exc:
            record_webhook_event(
                company_id=row["company_id"],
                alert_date=reference_date.isoformat(),
                webhook_url_hash=webhook_hash,
                payload={
                    "ticker": row["ticker"],
                    "company_name": row["company_name"],
                    "days_to_expiration": row["days_to_expiration"],
                    "unlock_date": row["unlock_date"],
                    "error": str(exc),
                },
                status="error",
            )
            messages.append(f"Discord alert failed for {row['ticker']}: {exc}")
    return messages


def timeline_chart(rows: list[dict]) -> alt.Chart:
    frame = pd.DataFrame(
        [
            {
                "ticker": row["ticker"],
                "company_name": row["company_name"],
                "ipo_date": pd.to_datetime(row["ipo_date"]),
                "unlock_date": pd.to_datetime(row["unlock_date"]),
                "days_to_expiration": row["days_to_expiration"],
                "status": row["status"],
            }
            for row in rows
        ]
    )
    base = alt.Chart(frame).encode(
        y=alt.Y("ticker:N", sort="-x", title=None),
        tooltip=[
            alt.Tooltip("company_name:N", title="Company"),
            alt.Tooltip("ipo_date:T", title="IPO Date"),
            alt.Tooltip("unlock_date:T", title="Unlock Date"),
            alt.Tooltip("days_to_expiration:Q", title="Days to Expiration"),
            alt.Tooltip("status:N", title="Status"),
        ],
    )
    bar = base.mark_bar(height=18, cornerRadiusEnd=4).encode(
        x=alt.X("ipo_date:T", title="Timeline"),
        x2="unlock_date:T",
        color=alt.Color(
            "status:N",
            scale=alt.Scale(
                domain=["Upcoming", "Due soon", "Expired"],
                range=["#4f46e5", "#f59e0b", "#64748b"],
            ),
            legend=None,
        ),
    )
    points = base.mark_point(size=90, filled=True, color="#0f172a").encode(x="ipo_date:T")
    unlock_points = base.mark_point(size=90, filled=True, color="#ef4444").encode(x="unlock_date:T")
    return (bar + points + unlock_points).properties(height=36 * max(3, len(rows)))


def progress_badge(days_to_expiration: int) -> str:
    if days_to_expiration < 0:
        return "Expired"
    if days_to_expiration == 0:
        return "Today"
    if days_to_expiration == 1:
        return "1 day"
    if days_to_expiration <= 7:
        return f"{days_to_expiration} days"
    return f"{days_to_expiration} days"


def _format_currency(value) -> str:
    if value in (None, ""):
        return "—"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _format_integer(value) -> str:
    if value in (None, ""):
        return "—"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def _format_percent(value) -> str:
    if value in (None, ""):
        return "—"
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "—"


def _format_plain_percent(value) -> str:
    if value in (None, ""):
        return "—"
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "—"


def _diagnostics_label(row: dict, minimum_confidence: int) -> str:
    return f"{row.get('ticker', '—')} | {row.get('company_name', 'Unknown')} | CIK {row.get('cik', '—')} | {_review_state(row, minimum_confidence)}"


def _diagnostics_payload(
    row: dict,
    rows: list[dict],
    reference_date: date,
    summary: dict[str, int],
    minimum_confidence: int,
) -> dict[str, Any]:
    return {
        "generated_at": date.today().isoformat(),
        "reference_date": reference_date.isoformat(),
        "dashboard_summary": summary,
        "company": {
            "company_id": row.get("company_id"),
            "company_name": row.get("company_name"),
            "ticker": row.get("ticker"),
            "cik": row.get("cik"),
            "theme": row.get("theme"),
        },
        "timeline": {
            "ipo_date": row.get("ipo_date"),
            "unlock_date": row.get("unlock_date"),
            "calendar_unlock_date": row.get("calendar_unlock_date"),
            "effective_unlock_date": row.get("effective_unlock_date"),
            "days_to_expiration": row.get("days_to_expiration"),
            "days_since_ipo": row.get("days_since_ipo"),
            "unlock_progress": row.get("unlock_progress"),
            "status": row.get("status"),
        },
        "filing": {
            "filing_form": row.get("filing_form"),
            "filing_date": row.get("filing_date"),
            "source_url": row.get("source_url"),
            "lockup_days": row.get("lockup_days"),
            "lockup_source": row.get("lockup_source"),
            "lockup_conditions": row.get("lockup_conditions", {}),
            "principal_holders": row.get("principal_holders", []),
            "notes": row.get("notes"),
        },
        "market": {
            "ipo_price": row.get("ipo_price"),
            "current_price": row.get("current_price"),
            "price_change_pct": _market_price_change_pct(row),
            "avg_volume_30d": row.get("avg_volume_30d"),
            "market_cap": row.get("market_cap"),
            "market_data_note": row.get("market_data_note", ""),
        },
        "ownership": _ownership_context(row),
        "insider_sales": {
            "lookup": _insider_sales_lookup(row),
            "summary": _insider_sales_summary(row),
            "transactions": _insider_sales(row),
        },
        "confidence": {
            "score": row.get("confidence_score", 0),
            "label": row.get("confidence_label", "Seeded"),
            "details": row.get("confidence_details", ""),
        },
        "review": {
            "minimum_confidence": minimum_confidence,
            "state": _review_state(row, minimum_confidence),
        },
        "selected_row_index": next((index for index, candidate in enumerate(rows) if candidate.get("company_id") == row.get("company_id")), None),
    }


def render_lockup_conditions(conditions: dict) -> None:
    has_values = any(value not in (None, "", [], {}) for value in conditions.values())
    if not has_values:
        return

    with st.expander("Lock-up conditions", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Early release", "Yes" if conditions.get("has_early_release") else "No")
        col2.metric("Earnings trigger", "Yes" if conditions.get("has_earnings_trigger") else "No")
        col3.metric(
            "Early release pct",
            f"{conditions['early_release_pct']}%" if conditions.get("early_release_pct") is not None else "—",
        )
        col4.metric("8-K amendment", conditions.get("amendment_date") or "None")
        if conditions.get("effective_unlock_date"):
            st.caption(
                f"Effective unlock date: {conditions['effective_unlock_date']}"
                + (
                    f" ({conditions.get('effective_unlock_source')})"
                    if conditions.get("effective_unlock_source")
                    else ""
                )
            )
        if conditions.get("earnings_release_date"):
            st.caption(f"Earnings release filing date: {conditions['earnings_release_date']}")
        if conditions.get("early_release_description"):
            st.caption(conditions["early_release_description"])
        if conditions.get("earnings_release_url"):
            st.link_button("Open earnings release filing", conditions["earnings_release_url"])
        if conditions.get("amendment_url"):
            st.link_button("Open 8-K amendment", conditions["amendment_url"])


def render_market_context(row: dict) -> None:
    values = (
        row.get("ipo_price"),
        row.get("current_price"),
        _market_price_change_pct(row),
        row.get("avg_volume_30d"),
        row.get("market_cap"),
        row.get("market_data_note"),
    )
    if not any(value not in (None, "", [], {}) for value in values):
        return

    with st.expander("Market context", expanded=False):
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("IPO price", _format_currency(row.get("ipo_price")))
        col2.metric("Current price", _format_currency(row.get("current_price")))
        col3.metric("% from IPO", _format_percent(_market_price_change_pct(row)))
        col4.metric("30D avg volume", _format_integer(row.get("avg_volume_30d")))
        col5.metric("Market cap", _format_integer(row.get("market_cap")))
        if row.get("market_data_note"):
            st.caption(row["market_data_note"])


def render_ownership_context(row: dict) -> None:
    context = _ownership_context(row)
    has_values = any(value not in (None, "", [], {}) for value in context.values())
    if not has_values:
        return

    with st.expander("Ownership context", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Tracked holder %", _format_plain_percent(context.get("tracked_holder_pct_of_offering")))
        col2.metric("Tracked holder shares", _format_integer(context.get("tracked_holder_shares")))
        col3.metric("Offering shares out", _format_integer(context.get("offering_shares_outstanding")))
        col4.metric("Current shares out", _format_integer(context.get("current_shares_outstanding")))

        if context.get("offering_shares_outstanding_source") or context.get("offering_shares_outstanding_as_of"):
            st.caption(
                "Offering denominator: "
                f"{context.get('offering_shares_outstanding_source') or 'unknown source'}"
                + (
                    f" | as of {context.get('offering_shares_outstanding_as_of')}"
                    if context.get("offering_shares_outstanding_as_of")
                    else ""
                )
            )
        if context.get("offering_shares_outstanding_note"):
            st.caption(context["offering_shares_outstanding_note"])

        if context.get("current_shares_outstanding_source") or context.get("current_shares_outstanding_as_of"):
            st.caption(
                "Current shares source: "
                f"{context.get('current_shares_outstanding_source') or 'unknown source'}"
                + (
                    f" | as of {context.get('current_shares_outstanding_as_of')}"
                    if context.get("current_shares_outstanding_as_of")
                    else ""
                )
            )
        if context.get("current_shares_outstanding_note"):
            st.caption(context["current_shares_outstanding_note"])
        if context.get("tracked_holder_pct_note"):
            st.caption(context["tracked_holder_pct_note"])


def render_insider_sales(row: dict) -> None:
    insider_sales = _insider_sales(row)
    lookup = _insider_sales_lookup(row)
    if not insider_sales and not _has_unlocked_in_real_time(row):
        return

    summary = _insider_sales_summary(row)
    with st.expander("Post-unlock Form 4 sales", expanded=False):
        st.caption(f"Lookup status: {lookup.get('status', 'unknown')}")
        if lookup.get("reason"):
            st.caption(lookup["reason"])

        if not insider_sales:
            metric_cols = st.columns(4)
            metric_cols[0].metric("Feed entries", lookup.get("feed_entries", "—"))
            metric_cols[1].metric("Candidate filings", lookup.get("candidate_filings", "—"))
            metric_cols[2].metric("Documents fetched", lookup.get("documents_fetched", "—"))
            metric_cols[3].metric("Transactions parsed", lookup.get("transactions_parsed", 0))
            st.caption("No post-unlock Form 4 sale transactions were parsed for this issuer yet.")
            return

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Transactions", summary["transaction_count"])
        col2.metric("Unique filings", summary["filing_count"])
        col3.metric("Shares sold", _format_integer(summary["total_shares_sold"]))
        col4.metric("Latest sale date", summary.get("latest_sale_date") or "—")

        latest_url = next((sale.get("source_url") for sale in insider_sales if sale.get("source_url")), None)
        if latest_url:
            st.link_button("Open latest Form 4", latest_url)

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Owner": sale.get("owner_name") or "Unknown",
                        "Trade Date": sale.get("transaction_date") or "—",
                        "Shares Sold": _format_integer(sale.get("shares_sold")),
                        "Price/Share": _format_currency(sale.get("price_per_share")),
                        "Owned After": _format_integer(sale.get("shares_owned_following_transaction")),
                        "Ownership": sale.get("ownership_type") or "—",
                        "Form": sale.get("form") or "—",
                    }
                    for sale in insider_sales
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_company_card(row: dict, minimum_confidence: int) -> None:
    confidence_score = _confidence_score(row)
    confidence_label = row.get("confidence_label", "Seeded")
    confidence_details = row.get("confidence_details", "Seeded watchlist entry ready for SEC enrichment.")
    review_state = _review_state(row, minimum_confidence)
    label = f"{row['ticker']}  |  {row['company_name']}"
    if review_state == "Needs review":
        label += "  |  Needs review"
    with st.expander(label, expanded=row["days_to_expiration"] <= DEFAULT_ALERT_DAYS):
        left, right = st.columns([2, 1])
        with left:
            st.write(
                f"IPO date: **{row['ipo_date']}** | Unlock date: **{row['unlock_date']}** | "
                f"Days to expiration: **{row['days_to_expiration']}**"
            )
            if row.get("calendar_unlock_date") and row.get("calendar_unlock_date") != row.get("unlock_date"):
                st.caption(
                    f"Calendar unlock date: {row['calendar_unlock_date']} | Effective unlock uses the earlier earnings-trigger boundary."
                )
            st.progress(
                min(1.0, max(0.0, row["unlock_progress"])),
                text=f"{progress_badge(row['days_to_expiration'])} from IPO to unlock",
            )
            st.caption(
                f"Theme: {row['theme']} | CIK: {row['cik']} | Filing form: {row['filing_form'] or 'not parsed yet'}"
            )
            st.caption(row["notes"])
            st.caption(f"Data confidence: {confidence_label} ({confidence_score}/100)")
            if confidence_details:
                st.caption(confidence_details)
            render_lockup_conditions(row.get("lockup_conditions", {}))
            render_market_context(row)
            render_ownership_context(row)
            render_insider_sales(row)
        with right:
            if row["source_url"]:
                st.link_button("Open SEC filing", row["source_url"])
            else:
                st.caption("SEC filing link will appear after a successful live refresh.")
            st.metric("Days to Expiration", row["days_to_expiration"])
            st.metric("Confidence", f"{confidence_score}/100")
            st.metric("Review", review_state)
        if row["principal_holders"]:
            st.subheader("Principal holders parsed from filing")
            st.json(row["principal_holders"])


def render_diagnostics_tab(
    rows: list[dict],
    reference_date: date,
    summary: dict[str, int],
    minimum_confidence: int,
) -> None:
    st.subheader("Diagnostics")
    st.caption("Inspect the exact values behind the dashboard and download them as JSON for debugging or QA.")
    if not rows:
        st.info("No dashboard rows are available yet.")
        return

    options = {_diagnostics_label(row, minimum_confidence): row for row in rows}
    selected_label = st.selectbox("Company to inspect", list(options.keys()), index=0)
    selected_row = options[selected_label]
    payload = _diagnostics_payload(selected_row, rows, reference_date, summary, minimum_confidence)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Ticker", selected_row.get("ticker", "—"))
    metric_cols[1].metric("Days to Expiration", selected_row.get("days_to_expiration", "—"))
    metric_cols[2].metric("Confidence", f"{selected_row.get('confidence_score', 0)}/100")
    metric_cols[3].metric("Review", _review_state(selected_row, minimum_confidence))

    st.download_button(
        "Download diagnostics JSON",
        data=json.dumps(payload, indent=2, default=str),
        file_name=f"{selected_row.get('ticker', 'diagnostics')}_diagnostics.json",
        mime="application/json",
    )
    st.json(payload)


initialize_database()
seed_companies()
ensure_sec_user_agent()

st.markdown(
    """
    <style>
        .hero {
            padding: 1.5rem 1.25rem;
            border-radius: 1.25rem;
            background: linear-gradient(135deg, rgba(15,23,42,1) 0%, rgba(30,41,59,1) 45%, rgba(59,130,246,0.95) 100%);
            color: white;
            box-shadow: 0 18px 50px rgba(15,23,42,.18);
            margin-bottom: 1rem;
        }
        .hero h1 {
            margin-bottom: .35rem;
            font-size: 2.3rem;
        }
        .hero p {
            margin: 0;
            opacity: .9;
            max-width: 60rem;
        }
        .mini-card {
            border: 1px solid rgba(148,163,184,.25);
            border-radius: 1rem;
            padding: 1rem;
            background: rgba(255,255,255,.75);
            backdrop-filter: blur(6px);
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>IPO Lockup Tracker</h1>
        <p>Demo dashboard for US IPOs that estimates when early holders become eligible to sell after the lock-up period. The app is designed for Streamlit Community Cloud and updates automatically from the `main` branch.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Controls")
    use_live_sec = st.toggle("Enable live SEC enrichment", value=True)
    reference_mode = st.radio(
        "Reference date",
        options=["Demo snapshot", "Today"],
        index=0,
        help="The demo snapshot keeps multiple unlock windows visible at once. Switch to Today to use the actual current date.",
    )
    reference_date = DEMO_REFERENCE_DATE if reference_mode == "Demo snapshot" else date.today()
    st.caption(f"Using reference date: {reference_date.isoformat()}")
    minimum_confidence = st.slider(
        "Minimum confidence for ready rows",
        min_value=0,
        max_value=100,
        value=70,
        step=5,
        help="Rows below this threshold move into a Needs review bucket instead of the main dashboard view.",
    )
    st.caption("Lower-confidence rows stay available in the Companies tab under Needs review.")
    secret_webhook = read_secret("discord_webhook_url", "")
    webhook_url = st.text_input(
        "Discord webhook URL",
        value=secret_webhook,
        type="password",
        help="Optional. Sends a payload when days_to_expiration == 3. You can also store this in Streamlit secrets.",
    ).strip()
    run_alerts = st.toggle("Send Discord alerts during refresh", value=False)
    refresh_clicked = st.button("Refresh from SEC now", type="primary")
    if secret_webhook:
        st.caption("Discord webhook loaded from Streamlit secrets.")
    st.caption("For Streamlit Cloud: repo `CT14090/IPO`, branch `main`, entrypoint `app.py`.")

refresh_warnings: list[str] = []
refreshed_count = 0
if refresh_clicked and use_live_sec:
    with st.spinner("Refreshing SEC data..."):
        _, refreshed_count, refresh_warnings = refresh_live_data()
    if refresh_warnings:
        st.sidebar.warning(
            f"SEC refresh completed with {len(refresh_warnings)} warning(s). Previous snapshots were kept for the failed companies."
        )
        for message in refresh_warnings:
            st.sidebar.caption(message)
    else:
        st.sidebar.success(f"SEC enrichment refreshed for {refreshed_count} companies.")
elif refresh_clicked and not use_live_sec:
    st.sidebar.warning("Enable live SEC enrichment to pull SEC filings.")

rows = compute_dashboard_rows(reference_date)
ready_rows, needs_review_rows = _split_rows_by_confidence(rows, minimum_confidence)

if run_alerts and webhook_url and refresh_clicked:
    alert_messages = maybe_send_alerts(rows, webhook_url, reference_date)
    for message in alert_messages:
        st.sidebar.info(message)

total = len(rows)
ready_total = len(ready_rows)
needs_review_total = len(needs_review_rows)
upcoming = sum(1 for row in ready_rows if row["days_to_expiration"] > 0)
due_soon = sum(1 for row in ready_rows if 0 <= row["days_to_expiration"] <= 7)
expired = sum(1 for row in ready_rows if row["days_to_expiration"] < 0)
watchlist_sources = len({row["source_url"] for row in ready_rows if row["source_url"]})
post_unlock_form4_sales = sum(_insider_sales_summary(row)["transaction_count"] for row in ready_rows)
avg_confidence = round(sum(_confidence_score(row) for row in ready_rows) / max(1, ready_total))
summary = {
    "total": total,
    "ready": ready_total,
    "needs_review": needs_review_total,
    "upcoming": upcoming,
    "due_soon": due_soon,
    "expired": expired,
    "avg_confidence": avg_confidence,
    "post_unlock_form4_sales": post_unlock_form4_sales,
}

alert_rows = [row for row in rows if row["days_to_expiration"] == DEFAULT_ALERT_DAYS]
if alert_rows:
    st.warning(
        "3-day alert window: "
        + ", ".join(f"{row['ticker']} ({row['days_to_expiration']} days)" for row in alert_rows)
    )
else:
    st.info("No watchlist company is exactly three days from unlock on the selected reference date.")

overview_tab, companies_tab, discovery_tab, diagnostics_tab, deployment_tab = st.tabs(["Overview", "Companies", "Discovery", "Diagnostics", "Deployment"])

with overview_tab:
    metric_cols = st.columns(6)
    metric_cols[0].metric("Ready IPOs", ready_total)
    metric_cols[1].metric("Upcoming", upcoming)
    metric_cols[2].metric("Due in 7 days", due_soon)
    metric_cols[3].metric("Expired", expired)
    metric_cols[4].metric("Avg confidence", f"{avg_confidence}/100")
    metric_cols[5].metric("Form 4 sales", post_unlock_form4_sales)
    st.caption(
        f"Showing {ready_total} ready row(s) and {needs_review_total} needs-review row(s) out of {total} watchlist companies. "
        f"{watchlist_sources} ready company record(s) currently have SEC filing links."
    )

    st.subheader("Unlock timeline")
    st.caption(
        "Each bar starts at the IPO date and ends at the estimated unlock date. The demo snapshot intentionally surfaces multiple overlapping unlock windows."
    )
    if ready_rows:
        st.altair_chart(timeline_chart(ready_rows), use_container_width=True)
    else:
        st.info("No rows meet the current confidence threshold for the timeline view.")

    if due_soon:
        due_tickers = ", ".join(f"{row['ticker']} ({row['days_to_expiration']}d)" for row in ready_rows if 0 <= row["days_to_expiration"] <= 7)
        st.success(f"Due soon: {due_tickers}")
    else:
        st.success("No lockups are due within the next 7 days for the chosen reference date.")

    st.subheader("Upcoming and recent unlocks")
    if ready_rows:
        st.dataframe(pd.DataFrame(_table_rows(ready_rows, minimum_confidence)), use_container_width=True, hide_index=True)
    else:
        st.info("No ready rows meet the current confidence threshold.")
    if needs_review_rows:
        st.warning(
            f"{needs_review_total} row(s) are below the confidence threshold and grouped as Needs review."
        )
        st.dataframe(pd.DataFrame(_table_rows(needs_review_rows, minimum_confidence)), use_container_width=True, hide_index=True)

with companies_tab:
    st.subheader("Company detail")
    st.caption("Each company expands into a compact card so the layout stays readable on smaller screens.")
    if ready_rows:
        st.subheader(f"Ready ({ready_total})")
        for row in ready_rows:
            render_company_card(row, minimum_confidence)
    else:
        st.info("No rows meet the current confidence threshold.")
    if needs_review_rows:
        with st.expander(f"Needs review ({needs_review_total})", expanded=False):
            st.caption("These rows are below the current confidence threshold and deserve a closer look.")
            for row in needs_review_rows:
                render_company_card(row, minimum_confidence)

with discovery_tab:
    st.subheader("Recent IPO candidates from SEC")
    st.caption("This feed surfaces recent 424B4 and F-1 filings that are not already on the watchlist. It is a discovery queue, not a fully validated IPO list.")
    candidates = discover_recent_ipo_candidates(limit=10)
    if not candidates:
        st.info("No new candidates found right now.")
    else:
        discovery_rows = [
            {
                "Company": candidate["company_name"],
                "Ticker": candidate["ticker"] or "—",
                "CIK": candidate["cik"],
                "Form": candidate["form"],
                "Filed": candidate["filing_date"],
                "Confidence": candidate["confidence"],
                "Why": candidate["reason"],
            }
            for candidate in candidates
        ]
        st.dataframe(pd.DataFrame(discovery_rows), use_container_width=True, hide_index=True)
        st.caption("Use this tab to spot newly filed IPO candidates before they appear in the lock-up watchlist.")

with diagnostics_tab:
    render_diagnostics_tab(rows, reference_date, summary, minimum_confidence)

with deployment_tab:
    st.subheader("How to deploy this app")
    st.markdown(
        """
        1. Deploy from GitHub using `main` and `app.py` as the entrypoint.
        2. Keep `requirements.txt` at the repo root so Streamlit installs dependencies automatically.
        3. Add secrets in Streamlit Cloud for the Discord webhook and optional SEC user agent.
        """
    )
