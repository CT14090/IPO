2. TASK_BOARD.md walkthrough — top to bottom

CONFIRMED DONE — all items in this section are verified by screenshots. No action needed.

IMPLEMENTED IN MAIN, PENDING LIVE VALIDATION

Rowspan-flattened principal holder parsing — ❌ Still failing. Screenshots confirm "Principal stockholder table not extracted cleanly" after live refresh. See Bug 2 above. No code suggestion yet — need the raw table HTML first. I'll ask you for that separately.

Automated IPO discovery / EFTS primary path — ⚠️ Structurally working but entity resolution broken. Every row shows Unknown/—. Tell Codex:

In _search_efts() in discovery.py, after doing meta = company_index.get(cik, {}), add a fallback: if meta is empty, call fetch_submission_profile(cik) and use its title field as the company name and ticker field as the ticker. The fetch_submission_profile() function already exists in the file — it just isn't being called from the EFTS path. Wire it in exactly the same way it's already used in _resolve_company_identity().

Discovery entity resolution fallback to submissions profile — ❌ Same issue as above. Codex added fetch_submission_profile() but didn't connect it to the EFTS path. Same fix applies.

Structured lockup_conditions expander panel — ❌ Not in UI yet. Tell Codex:

In app.py, add a render_lockup_conditions(conditions: dict) function and call it inside render_company_card() after the confidence details caption. It should read row.get("lockup_conditions", {}) and render an st.expander("Lock-up conditions") containing four st.metric() calls: Early release (Yes/No), Earnings trigger (Yes/No), Early release % (value or —), 8-K amendment date (value or None). If amendment_url is present, add an st.link_button("Open 8-K amendment", url). If early_release_description is non-empty, add an st.caption() with the first 200 chars. Only render the expander if at least one field is non-null/non-False.

NEEDS FOLLOW-UP

Principal holder extraction still failing on live ALAB filing — Blocked. I need to see the actual table HTML before suggesting a fix to Codex. Please do this:

Open https://www.sec.gov/Archives/edgar/data/1736297/000119312524073873/d285484d424b4.htm in your browser, use Cmd+F to find "Principal and Selling Stockholders", right-click the table that follows, click Inspect, then copy the outerHTML of the <table> element and paste it here.

Once I have that I can give Codex a precise fix.

NEEDS REGRESSION TESTS

All five items here have no tests. Tell Codex:

Create tests/test_sec_fixes.py with the full test suite I provided earlier in this conversation. It covers: greenshoe disambiguation (3 tests), dual-trigger detection (3 tests), cover-page IPO date parsing (4 tests), the full ALAB scenario (5 combined tests), and backwards compatibility (2 tests). The file was provided as a complete EOF block — use that verbatim.

NEXT UP

yfinance price enrichment — Ready to implement. All code has been provided as complete EOF blocks in this conversation (market.py, updated sec.py, db.py, app.py, requirements.txt). Tell Codex:

Implement Feature 7 using the complete EOF blocks provided by Claude earlier in this conversation. Files to create/replace: ipo_tracker/market.py (new), ipo_tracker/sec.py (add market fetch call in enrich_company()), ipo_tracker/db.py (6 new columns + migrations + updated upsert/load), app.py (price row in card + price columns in overview table), requirements.txt (add yfinance>=0.2).

Confidence-based filtering — After yfinance. No code written yet. Will provide after.

LATER — No action yet. Stays as-is. 
