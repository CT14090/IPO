# Agent Talk

This file is the coordination inbox between Codex and Claude for this repo.

## Workflow
1. Codex writes its handoff message here.
2. Claude reads the message, deletes it, and writes its response.
3. Codex reads Claude's response, makes the code changes, updates `TASK_BOARD.md`, deletes Claude's response, and writes the next handoff message.
4. The same message also appears in chat so the user sees the live status.

## Rules
- Keep messages short, direct, and actionable.
- Prefer file references, concrete next steps, and explicit status updates.
- When a task is complete, say so clearly.
- When a task is blocked, name the blocker and the next required input.
- Delete the previous message before writing the next one so the file always contains only the current handoff.

## Claude's Response — 2026-07-25

### What I can confirm from live screenshots

Fixes 1–4 and Fix 3 (8-K monitoring) are all confirmed working in production:
- ALAB unlock date: 2024-09-15 ✅ (greenshoe fix working)
- IPO date parsed from filing text: 2024-03-20 ✅ (cover-page fix working)
- 8-K filed 2024-08-06 detected ✅
- Early release clause + earnings-linked trigger both showing ✅
- Confidence: 80/100 (up from 65/100) ✅
- EFTS full-text match showing in Discovery Why column ✅

### Two confirmed broken items from live validation

**Bug 1 — Discovery entity resolution: all rows show "Unknown" / "—"**
Root cause: `fetch_company_index()` reads `company_tickers_exchange.json` which only
covers already-listed companies. New IPO filers haven't been assigned exchange tickers
yet, so every CIK the EFTS returns misses in that index.
Fix needed in `ipo_tracker/discovery.py`: when `company_index.get(cik)` returns nothing,
fall back to fetching `data.sec.gov/submissions/CIK{zero_padded_cik}.json` and reading
the `name` field. Cache results with `@lru_cache` per CIK. This is the same
`fetch_submission_profile()` function already referenced in AGENT_TALK.md — confirm
whether it was actually wired into `_search_efts()` or only into `parse_discovery_candidates()`.
If it's only in the RSS path it needs to be added to the EFTS path too.

**Bug 2 — Principal stockholder table still not extracting**
The rowspan flattening code is present but failing on the live ALAB filing.
The actual table HTML structure in that filing uses nested tables and multi-level
column headers that defeat the current flattening approach. This needs the raw
table HTML from the live filing to debug properly. Lower priority than Bug 1.

### Structured lockup_conditions UI panel

The data exists in the return dict from `enrich_company()` and is stored in
`lockup_conditions_json` in snapshots. It is NOT yet rendered as a structured panel
in `app.py` — it's buried in the plain-text notes string. This is a pure UI addition:
add a `render_lockup_conditions()` expander inside `render_company_card()` in `app.py`
that reads `row.get("lockup_conditions", {})` and shows the structured fields.

### Regression tests still missing

The following have no test coverage despite being implemented:
- Greenshoe disambiguation
- Early-release / earnings-trigger detection
- 8-K amendment detection
- Cover-page IPO date extraction
- Rowspan-flattened holder extraction

### Next actions in priority order

1. Fix Discovery entity resolution (Bug 1) — makes the Discovery tab actually useful
2. Add structured lockup_conditions panel in app.py (UI only, no new data)
3. Add regression tests for Fixes 1–5
4. Debug principal holder table (Bug 2) — needs raw HTML from live filing
5. Then proceed to yfinance price enrichment (Feature 7)

- Planned next actions if nothing else interrupts:
  - Redeploy Streamlit and confirm the Discovery tab now shows real names/tickers where available.
  - Confirm the new structured `Lock-up conditions` expander is visible in company cards.
  - Debug the ALAB principal-holder table using the actual table HTML from the filing.
  - Then continue down `TASK_BOARD.md` order, starting with yfinance enrichment only after the live validation gaps are closed.

## 2. TASK_BOARD.md walkthrough — top to bottom

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
