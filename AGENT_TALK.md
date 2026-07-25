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
