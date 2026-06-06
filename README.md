# IPO Lockup Tracker Demo

This demo tracks a small watchlist of US IPOs, calculates when early investors are eligible to sell after the standard lock-up period, and shows the result in a Streamlit dashboard.

## What it does

- Seeds 3-5 recent US IPOs into a local SQLite database
- Calculates `IPO date + lock-up days = estimated unlock date`
- Highlights companies approaching unlock, including the `3 days left` alert boundary
- Attempts to enrich each company from SEC EDGAR filings when network access is available
- Includes a lightweight Discord webhook helper for alerting

## Run it

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## SEC configuration

The SEC asks for a descriptive user agent that includes contact information. Set it before running live refreshes:

```bash
export SEC_USER_AGENT="IPO Lockup Tracker demo you@example.com"
```

## Discord alerts

Set `DISCORD_WEBHOOK_URL` if you want the helper to send a message when a company reaches `days_to_expiration == 3`.

