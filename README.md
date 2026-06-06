# IPO Lockup Tracker Demo

This demo tracks a small watchlist of US IPOs, calculates when early investors are eligible to sell after the standard lock-up period, and shows the result in a Streamlit dashboard.

## What it does

- Seeds 3-5 recent US IPOs into a local SQLite database
- Calculates `IPO date + lock-up days = estimated unlock date`
- Highlights companies approaching unlock, including the `3 days left` alert boundary
- Attempts to enrich each company from SEC EDGAR filings when network access is available
- Includes a lightweight Discord webhook helper for alerting

## Run it locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

- Connect the GitHub repo `CT14090/IPO`
- Deploy from the `main` branch
- Set the entrypoint file to `app.py`
- Add secrets for the Discord webhook and optional SEC user agent

Streamlit Community Cloud is free for personal, non-commercial, and educational apps. It connects directly to GitHub and updates your app when you push to the repository.

## Secrets

Use Streamlit secrets or the Cloud Secrets UI with these keys:

```toml
discord_webhook_url = "https://discord.com/api/webhooks/..."
sec_user_agent = "IPO Lockup Tracker demo you@example.com"
```

## SEC configuration

The SEC asks for a descriptive user agent that includes contact information. Set it before running live refreshes.

## Discord alerts

Set `DISCORD_WEBHOOK_URL` or add `discord_webhook_url` to Streamlit secrets if you want the helper to send a message when a company reaches `days_to_expiration == 3`.
