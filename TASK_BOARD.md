# IPO Tracker Task Board

## Confirmed Done
- Confidence score / parse quality is implemented in `ipo_tracker/sec.py`, stored in `ipo_tracker/db.py`, and displayed in `app.py`.
- Crash fix / schema resilience is implemented; older snapshot rows load safely and missing confidence fields no longer break the app.
- Streamlit dashboard, deployment docs, and Discord webhook helper are already in place.

## Implemented in `main`, Pending Live Validation
- Greenshoe disambiguation fix is in `ipo_tracker/sec.py`.
- Dual-trigger / early release detection is in `ipo_tracker/sec.py`.
- Post-IPO 8-K monitoring is in `ipo_tracker/sec.py`.
- IPO date from cover-page parsing is in `ipo_tracker/sec.py`.
- Rowspan-flattened principal holder parsing is in `ipo_tracker/sec.py`.
- Automated IPO discovery is in `ipo_tracker/discovery.py` and shown in the Streamlit `Discovery` tab.
- Discovery now uses EFTS as the primary path with RSS fallback and IPO-vs-secondary filtering.

## Next Up
- Add yfinance price and volume enrichment.
- Add confidence-based filtering and a visible `needs review` state.
- Add Form 4 insider tracking after unlock.
- Improve per-holder lock-up term parsing.
- Compute shares outstanding versus locked percentage.
- Monitor resale registrations such as S-3 and S-8 filings.

## Later
- Add stronger automated IPO validation beyond the current discovery heuristics.
- Add more explicit provenance summaries for parsed, inferred, and unknown fields.
- Add market-impact context around unlock dates.

## Notes
- The repo is connected to GitHub live and I can read and update files on `main`.
- `main` is the branch to keep using for the project.
- Streamlit Cloud deployment is already working.
