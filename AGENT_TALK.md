<!-- Reminder: If the next step is unclear, blocked, or better handled by asking Claude for more analysis, it is always okay to stop coding and update this file instead of pushing ahead with code. We can also choose to only edit AGENT_TALK.md and prompt Claude again. -->

# Agent Talk

This file is the coordination inbox between Codex and Claude for this repo.
Codex may choose to update only this .md file to further clarify questions by prompting Claude instead of proceeding to code.

## Workflow

1. Codex writes its handoff message here.
2. Claude reads the message, deletes it, and writes its response.
3. Codex reads Claude's response, makes the code changes, updates `TASK_BOARD.md`, deletes Claude's response, and writes the next handoff message.
4. The same message also appears in chat so the user sees the live status.

## Rules

- Keep messages specific, direct, and actionable.
- Prefer file references, concrete next steps, and explicit status updates.
- When a task is complete, say so clearly.
- When a task is blocked, name the blocker and the next required input.
- Delete the previous message before writing the next one so the file always contains only the current handoff.

# IMPORTANT : DO NOT DELETE ANYTHING INCLUDING THIS LINE AND ABOVE


## Codex Update — 2026-07-31

### What changed
- Implemented a first-pass `ownership_context` feature in the real repo.
- `ipo_tracker/sec.py` now derives:
  - offering-date shares outstanding from parsed holder percentages when consistent,
  - current shares outstanding from SEC Company Facts with priority order
    `dei:EntityCommonStockSharesOutstanding` -> `us-gaap:CommonStockSharesOutstanding` -> `us-gaap:CommonStockSharesIssued`,
  - prospectus-text fallback when current XBRL facts are unavailable,
  - conservative `tracked_holder_pct_of_offering` only when parsed holder rows can be summed safely.
- `ipo_tracker/db.py` now persists `ownership_context_json` in snapshots and reloads it into dashboard rows.
- `app.py` now surfaces ownership context in three places:
  - overview table columns: `Tracked Holder %`, `Offering Shares Out`, `Current Shares Out`
  - company-card expander: `Ownership context`
  - diagnostics JSON: new top-level `ownership` block
- Added local regression coverage:
  - `tests/test_db.py::test_load_dashboard_rows_preserves_ownership_context`
  - `tests/test_sec.py::OwnershipContextTests`

### Conservative rules in this pass
- Foreign / ADS-looking issuers intentionally return a null tracked-holder percentage with an explanatory note.
- Ambiguous overlap cases (for example duplicated share counts suggesting beneficial-ownership overlap) intentionally return a null tracked-holder percentage instead of a fabricated aggregate.
- This means the feature is honest-by-default, not maximal-by-default.

### Local verification completed
- Targeted ownership tests passed locally:
  - DB ownership persistence test
  - ownership derivation happy-path test
  - ownership overlap-null test

### Local verification still limited
- I did not claim a full holder-parser regression pass locally because this runtime still lacks `lxml`, which `pandas.read_html` needs for the broader principal-holder HTML tests.
- That limitation affects old parser tests in this machine, not the new ownership logic itself.

### Next live checks
- Confirm the new overview columns render cleanly in Streamlit.
- Confirm diagnostics JSON includes the new `ownership` block.
- Confirm a clean domestic issuer shows a non-null tracked-holder percentage.
- Confirm `ALAB` stays null with an overlap note.
- Confirm `ARM` stays null with a foreign / ADS-style note.

### Claude only if needed
- No immediate Claude analysis is required for this pass.
- Use Claude next only if we want a stronger overlap heuristic, ADS-conversion support, or a broader strategy for dual-class / foreign issuers.
