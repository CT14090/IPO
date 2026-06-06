from __future__ import annotations

import os
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
from ipo_tracker.discovery import discover_recent_ipo_candidates
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


def refresh_live_data() -> list[dict]:
    ensure_sec_user_agent()
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
            confidence_score=enriched["confidence_score"],
            confidence_label=enriched["confidence_label"],
            confidence_details=enriched["confidence_details"],
            notes=enriched["notes"],
        )
        rows.append({**company, **enriched})
    return rows


def compute_dashboard_rows(reference_date: date) -> list[dict]:
    rows = load_dashboard_rows()
    computed: list[dict] = []
    for row in rows:
        ipo_date = date.fromisoformat(row["ipo_date"])
        unlock_date = (
            date.fromisoformat(row["unlock_date"])
            if row["unlock_date"]
            else ipo_date + timedelta(days=row["lockup_days"])
        )
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


def render_company_card(row: dict) -> None:
    confidence_score = row.get("confidence_score", 0)
    confidence_label = row.get("confidence_label", "Seeded")
    confidence_details = row.get("confidence_details", "Seeded watchlist entry ready for SEC enrichment.")
    with st.expander(f"{row['ticker']}  |  {row['company_name']}", expanded=row["days_to_expiration"] <= DEFAULT_ALERT_DAYS):
        left, right = st.columns([2, 1])
        with left:
            st.write(
                f"IPO date: **{row['ipo_date']}** | Unlock date: **{row['unlock_date']}** | "
                f"Days to expiration: **{row['days_to_expiration']}**"
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
        with right:
            if row["source_url"]:
                st.link_button("Open SEC filing", row["source_url"])
            else:
                st.caption("SEC filing link will appear after a successful live refresh.")
            st.metric("Days to Expiration", row["days_to_expiration"])
            st.metric("Confidence", f"{confidence_score}/100")
        if row["principal_holders"]:
            st.subheader("Principal holders parsed from filing")
            st.json(row["principal_holders"])


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
avg_confidence = round(sum(row.get("confidence_score", 0) for row in rows) / max(1, total))

alert_rows = [row for row in rows if row["days_to_expiration"] == DEFAULT_ALERT_DAYS]
if alert_rows:
    st.warning(
        "3-day alert window: "
        + ", ".join(f"{row['ticker']} ({row['days_to_expiration']} days)" for row in alert_rows)
    )
else:
    st.info("No watchlist company is exactly three days from unlock on the selected reference date.")

overview_tab, companies_tab, discovery_tab, deployment_tab = st.tabs(["Overview", "Companies", "Discovery", "Deployment"])

with overview_tab:
    metric_cols = st.columns(5)
    metric_cols[0].metric("Watchlist IPOs", total)
    metric_cols[1].metric("Upcoming", upcoming)
    metric_cols[2].metric("Due in 7 days", due_soon)
    metric_cols[3].metric("Expired", expired)
    metric_cols[4].metric("Avg confidence", f"{avg_confidence}/100")
    st.caption(f"{watchlist_sources} company records currently have SEC filing links.")

    st.subheader("Unlock timeline")
    st.caption(
        "Each bar starts at the IPO date and ends at the estimated unlock date. The demo snapshot intentionally surfaces multiple overlapping unlock windows."
    )
    st.altair_chart(timeline_chart(rows), use_container_width=True)

    if due_soon:
        due_tickers = ", ".join(f"{row['ticker']} ({row['days_to_expiration']}d)" for row in rows if 0 <= row["days_to_expiration"] <= 7)
        st.success(f"Due soon: {due_tickers}")
    else:
        st.success("No lockups are due within the next 7 days for the chosen reference date.")

    st.subheader("Upcoming and recent unlocks")
    table_rows = [
        {
            "Company": row["company_name"],
            "Ticker": row["ticker"],
            "IPO Date": row["ipo_date"],
            "Unlock Date": row["unlock_date"],
            "Days to Expiration": row["days_to_expiration"],
            "Confidence": f"{row.get('confidence_label', 'Seeded')} ({row.get('confidence_score', 0)}/100)",
            "Status": row["status"],
            "Lock-up Days": row["lockup_days"],
            "Source": row["lockup_source"],
        }
        for row in rows
    ]
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

with companies_tab:
    st.subheader("Company detail")
    st.caption("Each company expands into a compact card so the layout stays readable on smaller screens.")
    for row in rows:
        render_company_card(row)

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

with deployment_tab:
    st.subheader("How to deploy this app")
    st.markdown(
        """
        1. Deploy from GitHub using `main` and `app.py` as the entrypoint.
        2. Keep `requirements.txt` at the repo root so Streamlit installs dependencies automatically.
        3. Add secrets in Streamlit Cloud for the Discord webhook and optional SEC user agent.
        """
    )
    st.code(
        'discord_webhook_url = "https://discord.com/api/webhooks/..."\nsec_user_agent = "IPO Lockup Tracker demo you@example.com"',
        language="toml",
    )
    st.info(
        "Streamlit Community Cloud is free for personal, non-commercial, and educational apps, and it syncs updates directly from GitHub."
    )
    st.caption("If you edit the repo on `main`, the Cloud app will pick up the changes automatically after the next refresh.")

st.subheader("Demo notes")
st.info(
    "This starter uses real US IPO names, CIKs, and filing lookups, but it also keeps a seeded local watchlist so the dashboard remains useful even if SEC data is temporarily unavailable. "
    "The Discord helper only sends when `days_to_expiration == 3`."
)
