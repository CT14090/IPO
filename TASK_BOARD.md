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
- The July 27, 2026 per-company refresh failure handling is live-confirmed in the negative case: the app no longer hard-crashes on the refresh path that previously raised SEC `HTTPError`.
- The incremental Form 4 refresh optimization is now strongly live-confirmed: the user measured a cold SEC refresh at about `40s` and the second refresh at about `5s`.
- The latest `RDDT` diagnostics confirm the repeat-refresh reuse path is active: `reused_transactions = 453`, `reused_filings = 53`, `candidate_filings = 2`, `documents_fetched = 2`, `xml_documents = 2`, and `new_transactions_parsed = 26`.
- On Tuesday, July 28, 2026, `ARM` initially exposed a live SEC `429` feed failure, and the later retry-plus-pacing pass successfully cleared that path: `insider_sales.lookup.status = sales_parsed`, `feed_entries = 29`, `candidate_filings = 28`, `xml_documents = 28`, and `transactions_parsed = 39`.
- The ARM follow-up diagnostics also confirm that the lock-up parser improved from the earlier fallback state: `lockup_source` now resolves to `Lock-Up Restrictions section: Regex match: for a period of 180 days` instead of `No filing text available`.
- The restored `sec.py` tail fixed the import-time deploy regression: the app is loading again, which confirms `ipo_tracker.sec` imports successfully after the truncation repair.
- ARM principal-holder parsing is now live-confirmed to return a real holder row instead of `[]`: the diagnostics show `holder = SoftBank Group Corp.` with `shares = 1,025,233,999`.
- On Wednesday, July 29, 2026, the user confirmed that the first SEC refresh was materially slower than the second again, so the repeat-refresh speed gap is restored in production.
- The latest ARM diagnostics also confirm the in-process market cache is active in production because `market_data_note` now includes `Reusing in-process market cache.` on the faster second run.

## Confirmed By Screenshots Or User Visual Pass
- The market `% from IPO` column now uses the correct signed arithmetic.
- Structured `lockup_conditions` data is surfaced as its own panel in the company cards.
- Market price and volume enrichment is visible in company cards and the overview table.
- Automated IPO discovery is visible in the dashboard and uses EFTS as the primary path with RSS fallback.
- Confidence-based filtering is visible, and lower-confidence rows move into the `Needs review` bucket.
- The current UI layout for overview, company cards, discovery, and diagnostics has not surfaced visual issues in the latest user pass.
- The current Form 4 UI state is visually correct for both zero-result and populated-result cases.
- The pasted `RDDT` diagnostics JSON first confirmed the original zero-count bug, then later confirmed the fixed live path with real sales and corrected unlock timing.

## Implemented In `main`, Not Independently Re-Run In This Session
- Post-unlock Form 4 insider-sale tracking is wired through `ipo_tracker/insiders.py`, `ipo_tracker/sec.py`, `ipo_tracker/db.py`, and `app.py`.
- Refreshes persist both `insider_sales_json` and `effective_unlock_date` into snapshots.
- Diagnostics JSON includes both insider-sales data and the effective-vs-calendar unlock distinction.
- The SEC submissions path now uses cached company submissions and an Option C-style early-exit archive walk instead of blindly walking every archived fragment.
- Earnings-trigger companies now compute a distinct `effective_unlock_date` from the earliest qualifying earnings release filing plus trading-day offset, instead of always using `ipo_date + lockup_days` as the only boundary.
- The dashboard now uses `effective_unlock_date` for status, countdown, and Form 4 filtering while still preserving the calendar unlock date for transparency.
- The Form 4 source path has been replaced with the issuer-centric SEC `browse-edgar?...&type=4&owner=include&output=atom` feed instead of relying on issuer `submissions.json` records for ownership filings.
- Structured Form 4 lookup metadata is embedded alongside stored insider-sale records, and the company-card / diagnostics surfaces can distinguish between `sales parsed`, `no qualifying filings`, `no sale transactions`, `sales reused`, `feed/doc resolution`, and `feed_error` problems without a new DB migration.
- `ipo_tracker/insiders.py` no longer pulls `ipo_tracker.sec` at module import time; that import-hardening targeted the startup error path.
- `app.py` handles per-company `requests.RequestException` failures during `Refresh from SEC now`, keeps the previous snapshot for failed companies, and surfaces explicit sidebar warnings instead of crashing the whole app.
- `ipo_tracker/market.py` now writes explicit fallback diagnostics into `market_data_note` so the persisted snapshot can distinguish `Previous snapshot market data available: yes.` from `Previous snapshot market data available: no.` during Yahoo rate-limit failures.
- When a previous good market snapshot exists, `ipo_tracker/market.py` also appends `Reusing previous snapshot market data.` to the stored note while preserving the prior values.
- `ipo_tracker/insiders.py` retries the SEC owner-include Form 4 Atom feed up to 3 times for `429` and `503` responses, with short bounded backoff and `Retry-After` header support.
- `ipo_tracker/insiders.py` spaces owner-include feed requests across companies with a short global minimum interval before each feed fetch, which appears to have resolved the ARM feed-error path in live use.
- `ipo_tracker/sec.py` now promotes embedded multi-row principal-holder header rows into usable column names before canonicalizing records. This targets ARM-style tables where the real `Name / Number / Percent` headers sit inside the first body rows instead of in clean `<th>` columns.
- `ipo_tracker/sec.py` now drops raw numeric placeholder columns and bare `%` artifacts during holder-row canonicalization so wide ARM-style tables do not leak keys like `"8"` or `"20"` into the parsed object.
- `ipo_tracker/sec.py` now retries SEC prospectus text requests for transient `429` and `503` responses, records the fetch failure reason in notes, and stops claiming that lock-up terms or IPO dates were parsed from filing text when the HTML was unavailable during refresh.
- `ipo_tracker/market.py` now keeps a short-lived in-process cache for market fetches, so repeat refreshes in the same deployed app process can reuse the prior Yahoo response instead of redoing all market calls immediately.
- `ipo_tracker/db.py` now stores last-good market values in a ticker-keyed `company_market_history` table, backfills that table from older snapshots during initialization, and uses it when the newest snapshot has null market fields.
- `tests/test_db.py` now covers both direct market-history reuse and legacy-history backfill from older snapshots before a failed refresh.
- `ipo_tracker/sec.py` now scans all non-spacer value cells in ARM-style holder rows for the first explicit percent, so the spacer-table fast path no longer drops `percent` when multi-column ownership rows are present.
- `ipo_tracker/sec.py` now backfills missing `shares` and `percent` from row values even when the promoted-header path does not map every column name cleanly.
- `tests/test_sec.py` now covers an ARM-style spacer-table regression and still asserts that we preserve the first percent in row order, which is currently the pre-offering ownership percent.
- `ipo_tracker/sec.py` now falls back to the first plausible bare numeric percent cell when SEC table normalization strips `%` signs from ARM-style holder rows, while still preferring explicit percent cells first.
- `tests/test_sec.py` now covers the ARM-style numeric-percent regression where percent values arrive as plain `100` / `90.6` cells instead of `100%` / `90.6%`.
- `ipo_tracker/sec.py` had a later truncation regression on Tuesday, July 28, 2026; the missing bottom portion of `determine_effective_unlock_date(...)` and `enrich_company(...)` has now been restored on `main` so the module can import again.

## Covered By Tests
- `tests/test_sec.py` covers lock-up extraction, fallback behavior, long-window early-release percent parsing, greenshoe disambiguation, early-release and earnings-trigger detection, 8-K amendment detection, cover-page IPO date extraction, holder parsing, embedded multi-row holder-header promotion, ARM-style spacer-table percent retention, trading-day offsets, effective unlock date resolution, confidence scoring, suppression of stray numeric holder keys for the ARM-style embedded-header case, and truthful confidence details when filing HTML is unavailable.
- `tests/test_discovery.py` covers source-name fallback and nameless-candidate skipping.
- `tests/test_insiders.py` now covers owner-include Form 4 feed parsing, post-unlock filtering, direct XML filing links, HTML-to-XML companion fallback, zero-result lookup metadata, retry-after-rate-limit success, repeated-rate-limit feed failure, incremental history reuse when there are no new filings, incremental merge behavior when a newer filing appears, and insider-sale summary math that ignores embedded lookup metadata.
- `tests/test_market.py` covers market-snapshot reuse when a previous good snapshot exists, explicit no-previous-snapshot note behavior, unchanged successful-market-data behavior, and note-preservation when a cached market failure is later merged with reusable snapshot data.
- `tests/test_db.py` covers ticker-keyed market history reuse and rebuilding market history from older snapshots.

## Still Open
- ARM percent extraction is still not live-confirmed after the numeric-percent fallback patch: the code and regression are in `main`, but the latest production refresh has not yet been re-run from this session.
- Live-validate whether ARM now reports `Previous snapshot market data available: yes.` after the new ticker-keyed `company_market_history` fallback.
- If the diagnostics still show `Previous snapshot market data available: no.` after the ticker-keyed history fallback change, debug why no prior non-null ARM market values exist in the deployed local DB.
- Live-validate the ARM holder cleanup by confirming `principal_holders[0]` now contains only canonical keys such as `holder`, `shares`, and `percent`, with no stray numeric-string keys.
- Live-validate whether ARM now shows a non-null `percent` in `principal_holders[0]` after the numeric-percent fallback fix.
- Decide later whether we still want to switch ARM-style percent semantics from the current pre-offering default (`100%`) to the post-offering figure (`90.6%`).
- Live-validate the new SEC filing-fetch diagnostics by checking whether an ARM-style miss now says `Prospectus fetch failed during refresh: HTTP ...` instead of falsely claiming the lock-up and IPO date were parsed from filing text.
- Live-validate the new market fallback diagnostics by checking whether `market_data_note` explicitly says `Previous snapshot market data available: yes.` or `Previous snapshot market data available: no.` during a Yahoo rate-limit refresh.
- Decide whether Yahoo rate-limit resilience needs an additional cache or retry/backoff layer beyond snapshot preservation plus in-process reuse.
- Decide whether the cold-refresh path still needs another speed pass, even though repeat refreshes are now materially faster again in the latest live run.
- Confirm that the new `insider_sales.lookup.status` values are enough in practice to explain remaining edge cases without needing a DB-level dedicated lookup table.
- Decide later whether the overview-table `0` should gain a tooltip or footnote clarifying that the value means `parsed count`, not `confirmed none exist`.
- Decide later whether post-unlock insider activity should remain sale-code `S` only or expand to include non-open-market codes such as `F`.
- Improve per-holder lock-up term parsing.
- Compute shares outstanding versus locked percentage.
- Monitor resale registrations such as S-3 and S-8 filings.
- Add stronger automated IPO validation beyond the current discovery heuristics.
- Add more explicit provenance summaries for parsed, inferred, and unknown fields.
- Add market-impact context around unlock dates.

## Live Validation Checklist
- Press `Refresh from SEC now` twice after the latest deploy and confirm the first run is the slower cold pass while the second run remains materially faster because it reuses stored Form 4 history and in-process market results.
- In the `Diagnostics` tab for an unlocked name such as `RDDT`, confirm the lookup metadata still shows reuse-oriented fields such as `reused_transactions`, `reused_filings`, and a sharply reduced candidate/document fetch count on repeat refresh.
- Check an issuer that previously showed `feed_error` such as `ARM` and confirm whether the SEC Form 4 lookup now succeeds after retry plus pacing or still ends in `feed_error`.
- Confirm the app still does not crash if one SEC request fails and that the sidebar still names the affected ticker.
- Confirm the `Diagnostics` tab includes `calendar_unlock_date`, `effective_unlock_date`, and the `insider_sales` section with `lookup`, `summary`, and `transactions`.
- Confirm `RDDT` still shows `effective_unlock_date = 2024-08-09` and live parsed Form 4 sales after the incremental-refresh change.
- Confirm the app starts cleanly again after the restored `sec.py` tail.
- Refresh `ARM` and inspect whether `principal_holders` now contains real holder rows instead of an empty list.
- For `ARM`, inspect whether `principal_holders[0]` now has only canonical keys and no stray numeric-string placeholders.
- For `ARM`, inspect whether `principal_holders[0].percent` is now present and non-null after the numeric-percent fallback fix.
- Reproduce a Yahoo Finance rate-limit scenario and inspect `market_data_note`.
- Confirm whether `market_data_note` now backfills to `Previous snapshot market data available: yes.` after the new ticker-keyed market-history fallback.
- If `market_data_note` still says `Previous snapshot market data available: no.` after the ticker-keyed history fallback change, treat that as a real deployed-history gap rather than the old snapshot-selection bug.
- If an issuer still returns `principal_holders = []` together with `No filing text available`, inspect whether the notes now include the specific fetch failure reason and no longer overstate filing-text parsing.
- Ignore Form 144-only evidence when judging the Form 4 feature, because Form 144 is intent-to-sell, not completed Form 4 sale execution.

## Notes
- The repo is connected to GitHub live and I can read and update files on `main`.
- `main` is the branch to keep using for the project.
- Streamlit Cloud deployment is already working.
- Technical difficulty on my side: the local shell/runtime bridge is unavailable in this session, so I could not run the app or local test suite directly. That is why I am separating live-confirmed items from code-complete items instead of overstating certainty.
- Additional current blocker: the GitHub large-file fetch path truncates `ipo_tracker/sec.py` in this thread, so a safe whole-file remote patch to that file is not practical here without a working local file bridge.
