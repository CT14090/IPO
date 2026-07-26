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
- Regression coverage now exists in `tests/test_sec.py` for the signed market-change helper, the long-window early-release percentage, and the spacer-table principal holder parser.
- Regression coverage now exists in `tests/test_discovery.py` for source-name fallback and nameless-candidate skipping.
- The refreshed Streamlit screenshot confirms the market `% from IPO` column now uses the correct signed arithmetic.
- A dedicated `Diagnostics` tab now exposes row-level JSON export and exact computed values for QA without screenshots.

## Implemented in `main`, Pending Live Validation
- Automated IPO discovery is in `ipo_tracker/discovery.py` and shown in the Streamlit `Discovery` tab.
- Discovery uses EFTS as the primary path with RSS fallback and IPO-vs-secondary filtering.
- Discovery entity resolution now prefers real source/profile names and skips nameless candidates instead of emitting `CIK ####` rows.
- Discovery form values now fall back from `form_type` to `form` so the UI can show a non-blank form when SEC returns the alternate key.
- Structured `lockup_conditions` data is now stored in snapshots and surfaced as its own panel in the company cards.
- Market price/volume enrichment is now wired through `ipo_tracker/market.py`, `ipo_tracker/sec.py`, `ipo_tracker/db.py`, and `app.py`.

## Needs Follow-up
- The ALAB diagnostics JSON still shows the principal holder parser reading the table of contents instead of the stockholder table.
- The same diagnostics JSON still shows `early_release_pct` as `null` and the principal-holder score inflated to 100 because the parser accepted page-number rows.
- Live validation is still needed for the refreshed Discovery tab after the latest fixes, but the main blocking issue is the ALAB parser shape.

## Needs Regression Tests
- Add a regression test that rejects table-of-contents rows when extracting principal holders.
- Add a regression test that captures `early_release_pct` from the full lock-up section when the percentage appears later in the section.
- Add parser tests for greenshoe disambiguation.
- Add parser tests for early-release and earnings-trigger detection.
- Add parser tests for 8-K amendment detection.
- Add parser tests for cover-page IPO date extraction.
- Discovery identity/form fallback tests are now covered in `tests/test_discovery.py`.

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
