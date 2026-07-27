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
- `RDDT` is now live-confirmed end-to-end: effective unlock date resolved to `2024-08-09`, the calendar unlock remains visible as `2024-09-17`, and the diagnostics show `insider_sales.lookup.status = sales_parsed` with real post-unlock Form 4 sales.
- The July 27, 2026 Streamlit startup `ImportError` is resolved in practice because the app is loading again and returning live diagnostics.

## Confirmed By Screenshots Or User Visual Pass
- The market `% from IPO` column now uses the correct signed arithmetic.
- Structured `lockup_conditions` data is surfaced as its own panel in the company cards.
- Market price and volume enrichment is visible in company cards and the overview table.
- Automated IPO discovery is visible in the dashboard and uses EFTS as the primary path with RSS fallback.
- Confidence-based filtering is visible, and lower-confidence rows move into the `Needs review` bucket.
- The current UI layout for overview, company cards, discovery, and diagnostics has not surfaced visual issues in the latest user pass.
- The current Form 4 UI state is visually correct for a zero-result case: the table shows `0`, and the card explains that no post-unlock Form 4 sale transactions were parsed yet.
- The pasted `RDDT` diagnostics JSON first confirmed the original zero-count bug, then later confirmed the fixed live path with real sales and corrected unlock timing.

## Implemented In `main`, Not Independently Re-Run In This Session
- Post-unlock Form 4 insider-sale tracking is wired through `ipo_tracker/insiders.py`, `ipo_tracker/sec.py`, `ipo_tracker/db.py`, and `app.py`.
- Refreshes persist both `insider_sales_json` and `effective_unlock_date` into snapshots.
- Diagnostics JSON includes both insider-sales data and the effective-vs-calendar unlock distinction.
- The SEC submissions path now uses cached company submissions and an Option C-style early-exit archive walk instead of blindly walking every archived fragment.
- Earnings-trigger companies now compute a distinct `effective_unlock_date` from the earliest qualifying earnings release filing plus trading-day offset, instead of always using `ipo_date + lockup_days` as the only boundary.
- The dashboard now uses `effective_unlock_date` for status, countdown, and Form 4 filtering while still preserving the calendar unlock date for transparency.
- The Form 4 source path has now been replaced with the issuer-centric SEC `browse-edgar?...&type=4&owner=include&output=atom` feed instead of relying on issuer `submissions.json` records for ownership filings.
- Structured Form 4 lookup metadata is now embedded alongside stored insider-sale records, and the company-card / diagnostics surfaces can distinguish between `sales parsed`, `no qualifying filings`, `no sale transactions`, and `feed/doc resolution` problems without a new DB migration.
- `ipo_tracker/insiders.py` no longer pulls `ipo_tracker.sec` at module import time; that import-hardening targeted the startup error path.
- Large Form 4 candidate batches now fetch ownership documents in parallel using a bounded thread pool, which should reduce SEC refresh time without changing the validated parsing logic.
- `app.py` now handles per-company `requests.RequestException` failures during `Refresh from SEC now`, keeps the previous snapshot for failed companies, and surfaces explicit sidebar warnings instead of crashing the whole app.
- Because I could not execute the local app or tests from this session, the performance improvement and refresh-resilience behavior still need a fresh user validation after deployment.

## Covered By Tests
- `tests/test_sec.py` covers lock-up extraction, fallback behavior, long-window early-release percent parsing, greenshoe disambiguation, early-release and earnings-trigger detection, 8-K amendment detection, cover-page IPO date extraction, holder parsing, trading-day offsets, effective unlock date resolution, and confidence scoring.
- `tests/test_discovery.py` covers source-name fallback and nameless-candidate skipping.
- `tests/test_insiders.py` now covers owner-include Form 4 feed parsing, post-unlock filtering, direct XML filing links, HTML-to-XML companion fallback, zero-result lookup metadata, and insider-sale summary math that ignores embedded lookup metadata.

## Still Open
- Validate whether the new parallel Form 4 document fetch materially reduces `Refresh from SEC now` time from the user's reported `> 1 minute`.
- Validate that the new per-company refresh failure handling prevents full-app crashes when SEC returns `HTTPError` during live refresh.
- Decide whether SEC rate-limit resilience needs an additional retry/backoff layer inside `ipo_tracker/sec.py`, or whether the app-level graceful degradation is enough.
- Confirm that the new `insider_sales.lookup.status` values are enough in practice to explain remaining zero-count cases without needing a DB-level dedicated lookup table.
- Decide later whether the overview-table `0` should gain a tooltip or footnote clarifying that the value means `parsed count`, not `confirmed none exist`.
- Decide later whether post-unlock insider activity should remain sale-code `S` only or expand to include non-open-market codes such as `F`.
- Improve per-holder lock-up term parsing.
- Compute shares outstanding versus locked percentage.
- Monitor resale registrations such as S-3 and S-8 filings.
- Add stronger automated IPO validation beyond the current discovery heuristics.
- Add more explicit provenance summaries for parsed, inferred, and unknown fields.
- Add market-impact context around unlock dates.
- If refresh is still too slow after the thread-pool pass, move to an incremental Form 4 update strategy that reuses previously stored history instead of reprocessing the full owner-feed window every refresh.

## Live Validation Checklist
- Press `Refresh from SEC now` after the latest deploy and confirm the app no longer crashes if one SEC request fails.
- If a refresh warning appears, confirm the sidebar names the affected ticker and that the rest of the dashboard still loads from the last good snapshots.
- Time a fresh `Refresh from SEC now` run after the latest deploy.
- Confirm the app still boots cleanly after the latest performance and refresh-resilience pass.
- Confirm the `Diagnostics` tab includes `calendar_unlock_date`, `effective_unlock_date`, and the `insider_sales` section with `lookup`, `summary`, and `transactions`.
- Confirm `RDDT` still shows `effective_unlock_date = 2024-08-09` and live parsed Form 4 sales after the performance change.
- Ignore Form 144-only evidence when judging this feature, because Form 144 is intent-to-sell, not completed Form 4 sale execution.

## Notes
- The repo is connected to GitHub live and I can read and update files on `main`.
- `main` is the branch to keep using for the project.
- Streamlit Cloud deployment is already working.
- Technical difficulty on my side: the local shell/runtime bridge is unavailable in this session, so I could not run the app or local test suite directly. That is why I am separating live-confirmed items from code-complete items instead of overstating certainty.
