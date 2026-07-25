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

## Implemented in `main`, Pending Live Validation
- Rowspan-flattened principal holder parsing is in `ipo_tracker/sec.py`.
- Automated IPO discovery is in `ipo_tracker/discovery.py` and shown in the Streamlit `Discovery` tab.
- Discovery uses EFTS as the primary path with RSS fallback and IPO-vs-secondary filtering.
- Discovery entity resolution now falls back to SEC submissions profiles so names can populate even when the ticker index misses a CIK.
- Structured `lockup_conditions` data is now stored in snapshots and surfaced as its own panel in the company cards.
- Market price/volume enrichment is now wired through `ipo_tracker/market.py`, `ipo_tracker/sec.py`, `ipo_tracker/db.py`, and `app.py`.

## Needs Follow-up
- Principal holder extraction still needs better live coverage: ALAB currently reports `Principal stockholder table not extracted cleanly` even though the rest of the parser works.

## Needs Regression Tests
- Add parser tests for greenshoe disambiguation.
- Add parser tests for early-release and earnings-trigger detection.
- Add parser tests for 8-K amendment detection.
- Add parser tests for cover-page IPO date extraction.
- Add parser tests for rowspan-flattened holder extraction.
- Add discovery tests that cover the EFTS primary path and the RSS fallback path.

## Next Up
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
