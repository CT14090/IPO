# IPO Tracker Task Board

## Confirmed By Live Evidence
- Confidence score / parse quality is implemented in `ipo_tracker/sec.py`, stored in `ipo_tracker/db.py`, and displayed in `app.py`.
- Crash fix / schema resilience is implemented; older snapshot rows load safely and missing confidence fields no longer break the app.
- Streamlit dashboard, deployment docs, and Discord webhook helper are already in place.
- Greenshoe disambiguation is implemented in `ipo_tracker/sec.py` and was confirmed on the live ALAB card when the unlock date moved to `2024-09-15`.
- Dual-trigger / early release detection is implemented in `ipo_tracker/sec.py` and was confirmed on the live ALAB card.
- Post-IPO 8-K monitoring is implemented in `ipo_tracker/sec.py` and was confirmed on the live ALAB card.
- IPO date from cover-page parsing is implemented in `ipo_tracker/sec.py` and was confirmed on the live ALAB card.
- Principal-holder table selection now skips false-positive tables without real numeric values, and ALAB live validation confirmed that real holder rows replaced the old table-of-contents match.
- `early_release_pct = null` for ALAB is now understood to be a correct filing outcome, not a parser failure.
- A dedicated `Diagnostics` tab now exposes row-level JSON export and exact computed values for QA.
- The Form 4 feature is now visibly deployed: the overview table shows a `Post-Unlock Form 4 Sales` column, and company cards show a `Post-unlock Form 4 sales` panel without crashing.

## Confirmed By Screenshots Or User Visual Pass
- The market `% from IPO` column now uses the correct signed arithmetic.
- Structured `lockup_conditions` data is surfaced as its own panel in the company cards.
- Market price and volume enrichment is visible in company cards and the overview table.
- Automated IPO discovery is visible in the dashboard and uses EFTS as the primary path with RSS fallback.
- Confidence-based filtering is visible, and lower-confidence rows move into the `Needs review` bucket.
- The current UI layout for overview, company cards, discovery, and diagnostics has not surfaced visual issues in the latest user pass.
- The current Form 4 UI state is visually correct for a zero-result case: the table shows `0`, and the card explains that no post-unlock Form 4 sale transactions were parsed yet.
- The pasted `RDDT` diagnostics JSON confirmed that the first Form 4 rollout returned zero transactions even though `RDDT` should have post-unlock sale activity, so the issue was a real ingestion + unlock-boundary bug rather than just missing visual validation.

## Implemented In `main`, Not Independently Re-Run In This Session
- Post-unlock Form 4 insider-sale tracking is wired through `ipo_tracker/insiders.py`, `ipo_tracker/sec.py`, `ipo_tracker/db.py`, and `app.py`.
- Refreshes persist both `insider_sales_json` and `effective_unlock_date` into snapshots.
- Diagnostics JSON includes both insider-sales data and the effective-vs-calendar unlock distinction.
- The SEC submissions path now uses cached company submissions and an Option C-style early-exit archive walk instead of blindly walking every archived fragment.
- Earnings-trigger companies now compute a distinct `effective_unlock_date` from the earliest qualifying earnings release filing plus trading-day offset, instead of always using `ipo_date + lockup_days` as the only boundary.
- The dashboard now uses `effective_unlock_date` for status, countdown, and Form 4 filtering while still preserving the calendar unlock date for transparency.
- Because I could not execute the local app or tests from this session, the patched positive-data path still needs live confirmation on `RDDT` after redeploy/refresh.

## Covered By Tests
- `tests/test_sec.py` covers lock-up extraction, fallback behavior, long-window early-release percent parsing, greenshoe disambiguation, early-release and earnings-trigger detection, 8-K amendment detection, cover-page IPO date extraction, holder parsing, trading-day offsets, effective unlock date resolution, and confidence scoring.
- `tests/test_discovery.py` covers source-name fallback and nameless-candidate skipping.
- `tests/test_insiders.py` covers Form 4 sale-only parsing, post-unlock filtering, archived submission-fragment loading behavior, XML-companion fallback for HTML-backed Form 4 filings, and insider-sale summary math.

## Still Open
- Confirm the patched Form 4 positive-data path against a real issuer with post-unlock sale filings. `RDDT` remains the primary validation target because its earnings-trigger unlock should move earlier than the naive `2024-09-17` calendar date.
- Decide later whether the overview-table `0` should gain a tooltip or footnote clarifying that the value means `parsed count`, not `confirmed none exist`.
- Decide later whether post-unlock insider activity should remain sale-code `S` only or expand to include non-open-market codes such as `F`.
- Improve per-holder lock-up term parsing.
- Compute shares outstanding versus locked percentage.
- Monitor resale registrations such as S-3 and S-8 filings.
- Add stronger automated IPO validation beyond the current discovery heuristics.
- Add more explicit provenance summaries for parsed, inferred, and unknown fields.
- Add market-impact context around unlock dates.

## Live Validation Checklist
- Confirm the `Diagnostics` tab includes `calendar_unlock_date`, `effective_unlock_date`, and the `insider_sales` section with both `summary` and `transactions`.
- Refresh the deployed app and inspect `RDDT` specifically.
- Confirm `RDDT` no longer appears as simply calendar-upcoming if the effective earnings-trigger unlock is earlier.
- Confirm `RDDT` shows a nonzero parsed Form 4 sale count and at least one transaction dated on or after the corrected effective unlock date.
- Ignore Form 144-only evidence when judging this feature, because Form 144 is intent-to-sell, not completed Form 4 sale execution.

## Notes
- The repo is connected to GitHub live and I can read and update files on `main`.
- `main` is the branch to keep using for the project.
- Streamlit Cloud deployment is already working.
- Technical difficulty on my side: the local shell/runtime bridge is unavailable in this session, so I could not run the app or local test suite directly. That is why I am separating live-confirmed items from code-complete items instead of overstating certainty.
