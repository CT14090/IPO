# IPO Tracker Task Board

## Confirmed Done
- Confidence score / parse quality is implemented in `ipo_tracker/sec.py`, stored in `ipo_tracker/db.py`, and displayed in `app.py`.
- Crash fix / schema resilience is implemented; older snapshot rows load safely and missing confidence fields no longer break the app.
- Streamlit dashboard, deployment docs, and Discord webhook helper are already in place.
- Greenshoe disambiguation is implemented in `ipo_tracker/sec.py` and is visible in live ALAB validation.
- Dual-trigger / early release detection is implemented in `ipo_tracker/sec.py` and is visible in live ALAB validation.
- Post-IPO 8-K monitoring is implemented in `ipo_tracker/sec.py` and is visible in live ALAB validation.
- IPO date from cover-page parsing is implemented in `ipo_tracker/sec.py` and is visible in live ALAB validation.
- Refresh-path compatibility is hardened in `ipo_tracker/db.py` so snapshot writes can ignore extra fields safely during mixed revisions.
- Regression coverage now exists in `tests/test_sec.py` for the signed market-change helper, the long-window early-release percentage, greenshoe disambiguation, early-release and earnings-trigger detection, 8-K amendment detection, cover-page IPO date extraction, the spacer-table principal holder parser, and the ToC-only principal-holder rejection case.
- Regression coverage now exists in `tests/test_discovery.py` for source-name fallback and nameless-candidate skipping.
- The refreshed Streamlit screenshot confirms the market `% from IPO` column now uses the correct signed arithmetic.
- A dedicated `Diagnostics` tab now exposes row-level JSON export and exact computed values for QA without screenshots.
- Principal-holder table selection is now hardened to skip candidate tables without any numeric cell above 1000 before scoring, which blocks the ALAB table-of-contents false positive.
- ALAB live validation confirms the principal-holder rows are now real and `early_release_pct` being `null` is correct for that filing.
- Structured `lockup_conditions` data is stored in snapshots and surfaced as its own panel in the company cards.
- Market price/volume enrichment is wired through `ipo_tracker/market.py`, `ipo_tracker/sec.py`, `ipo_tracker/db.py`, and `app.py`.
- Automated IPO discovery is in `ipo_tracker/discovery.py`, uses EFTS as the primary path with RSS fallback, resolves real source/profile names, and falls back from `form_type` to `form` when SEC uses the alternate key.
- Confidence-based filtering is now in `app.py`, and low-confidence rows are visibly grouped as `Needs review` in the dashboard.

## Implemented in `main`, Pending Live Validation
- No open items right now. The latest visual pass did not surface problems in discovery, the lock-up conditions panel, market enrichment, or the confidence-filtered dashboard split.

## Needs Regression Tests
- No open SEC parser or discovery regression gaps are on the board right now.

## Next Up
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
- I was not able to execute the local test suite from this session because the local shell/runtime bridge is unavailable here, so the new coverage is committed but not locally run by me in this turn.
