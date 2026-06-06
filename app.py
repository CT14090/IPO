from __future__ import annotations

from datetime import date, timedelta

import altair as alt
import pandas as pd
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
from ipo_tracker.sec import enrich_company


st.set_page_config(
    page_title="IPO Lockup Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def refresh_live_data() -> list[dict]:
    rows = []
    for company in load_dashboard_rows():
        enriched = enrich_company(company)
        upsert_snapshot(
            company["company_id"],
            filing_form=enriched["filing_form"],
            filing_date=enriched["filing_date"],
            source_url=enriched["source_url"],
            lockup_days=enriched["lockup_days"],
            unlock_date=enriched["unlock_date"],
            principal_holders=enriched["principal_holders"],
            lockup_source=enriched["lockup_source"],
            notes=enriched["notes"],
        )
        rows.append({**company, **enriched})
    return rows


def compute_dashboard_rows(reference_date: date) -> list[dict]:
    rows = load_dashboard_rows()
    computed: list[dict] = []
    for row in rows:
        ipo_date = date.fromisoformat(row["ipo_date"])
        unlock_date = date.fromisoformat(row["unlock_date"]) if row["unlock_date"] else ipo_date + timedelta(days=row["lockup_days"])
        days_to_expiration = (unlock_date - reference_date).days
        days_since_ipo = (reference_date - ipo_date).days
        unlock_progress = max(0.0, min(1.0, days_since_ipo / max(1, row["lockup_days"])))
        computed.append(
            {
                **row,
                "unlock_date": unlock_date.isoformat(),
                "days_to_expiration": days_to_expiration,
                "days_since_ipo": days_since_ipo,
                "unlock_progress": unlock_progress,
                "status": "Due soon"
                if days_to_expiration == DEFAULT_ALERT_DAYS
                else ("Upcoming" if days_to_expiration > 0 else "Expired"),
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
    bar = base.mark_bar(height=18).encode(
        x=alt.X("ipo_date:T", title="Timeline"),
        x2="unlock_date:T",
        color=alt.Color(
            "status:N",
            scale=alt.Scale(domain=["Upcoming", "Due soon", "Expired"], range=["#4f46e5", "#f59e0b", "#64748b"]),
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


initialize_database()
seed_companies()

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
        <p>Demo dashboard for US IPOs that estimates when early holders become eligible to sell after the lock-up period. It is seeded with a compact watchlist so the layout shows multiple overlapping timelines right away.</p>
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
    webhook_url = st.text_input("Discord webhook URL", value="", type="password", help="Optional. Sends a payload when days_to_expiration == 3.")
    run_alerts = st.toggle("Send Discord alerts during refresh", value=False)
    refresh_clicked = st.button("Refresh from SEC now", type="primary")

if refresh_clicked and use_live_sec:
    with st.spinner("Refreshing SEC data..."):
        refresh_live_data()
    st.sidebar.success("SEC enrichment refreshed.")
elif refresh_clicked and not use_live_sec:
    st.sidebar.warning("Enable live SEC enrichment to pull SEC filings.")

rows = compute_dashboard_rows(reference_date)

if run_alerts and webhook_url and refresh_clicked:
    alert_messages = maybe_send_alerts(rows, webhook_url, reference_date)
    for message in alert_messages:
        st.sidebar.info(message)

total = len(rows)
upcoming = sum(1 for row in rows if row["days_to_expiration"] > 0)
due_soon = sum(1 for row in rows if 0 <= row["days_to_expiration"] <= 7)
expired = sum(1 for row in rows if row["days_to_expiration"] < 0)
watchlist_sources = len({row["source_url"] for row in rows if row["source_url"]})

metric_cols = st.columns(4)
metric_cols[0].metric("Watchlist IPOs", total)
metric_cols[1].metric("Upcoming", upcoming)
metric_cols[2].metric("Due in 7 days", due_soon)
metric_cols[3].metric("Expired", expired)
st.caption(f"{watchlist_sources} company records currently have SEC filing links.")

st.subheader("Unlock timeline")
st.caption("Each bar starts at the IPO date and ends at the estimated unlock date. The demo snapshot intentionally surfaces multiple overlapping unlock windows.")
st.altair_chart(timeline_chart(rows), use_container_width=True)

st.subheader("Upcoming and recent unlocks")
table_rows = [
    {
        "Company": row["company_name"],
        "Ticker": row["ticker"],
        "IPO Date": row["ipo_date"],
        "Unlock Date": row["unlock_date"],
        "Days to Expiration": row["days_to_expiration"],
        "Status": row["status"],
        "Lock-up Days": row["lockup_days"],
        "Source": row["lockup_source"],
    }
    for row in rows
]
st.dataframe(
    pd.DataFrame(table_rows),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Company detail")
detail_cols = st.columns(2)
for index, row in enumerate(rows):
    with detail_cols[index % 2]:
        with st.container(border=True):
            st.markdown(f"### {row['company_name']} (`{row['ticker']}`)")
            st.write(
                f"IPO date: **{row['ipo_date']}** | Unlock date: **{row['unlock_date']}** | "
                f"Days to expiration: **{row['days_to_expiration']}**"
            )
            st.progress(min(1.0, max(0.0, row["unlock_progress"])), text=f"{progress_badge(row['days_to_expiration'])} from IPO to unlock")
            st.caption(f"Theme: {row['theme']} | CIK: {row['cik']} | Filing form: {row['filing_form'] or 'not parsed yet'}")
            st.caption(row["notes"])
            if row["source_url"]:
                st.link_button("Open SEC filing", row["source_url"])
            if row["principal_holders"]:
                with st.expander("Principal holders parsed from filing"):
                    st.json(row["principal_holders"])
            else:
                with st.expander("Principal holders parsed from filing"):
                    st.write("No table was extracted yet for this company.")

st.subheader("Demo notes")
st.info(
    "This starter uses real US IPO names, CIKs, and filing lookups, but it also keeps a seeded local watchlist so the dashboard remains useful even if SEC data is temporarily unavailable. "
    "The Discord helper only sends when `days_to_expiration == 3`."
)
