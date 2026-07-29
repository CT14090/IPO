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

## Codex Handoff — 2026-07-29

Wednesday, July 29, 2026 follow-up after implementing the next fix for the ARM market fallback issue.

What Codex changed
- `ipo_tracker/db.py`
  - added a new ticker-keyed `company_market_history` table that stores the last good market values independently of the latest snapshot row
  - `upsert_snapshot(...)` now persists successful market values into that history table
  - `initialize_database()` now backfills `company_market_history` from older non-null snapshot rows so legacy data can still be recovered
  - `load_dashboard_rows()` now uses ticker-keyed market history when the latest snapshot has null market fields
- `tests/test_db.py`
  - added regression coverage for direct market-history reuse after a failed refresh
  - added regression coverage for rebuilding market history from older snapshots and then reusing it after a failed refresh

Why this change was made
- The earlier fallback still depended too much on the latest snapshot chain.
- The live ARM diagnostics continued to say `Previous snapshot market data available: no.` even after we had earlier user evidence that ARM once had non-null market values.
- This new design gives us a stable last-good market source keyed by ticker, plus a migration path from existing snapshot history.

What is already code-verified
- The new history path does not depend on the latest snapshot row containing market values.
- The new history path survives a later failed market refresh because the last-good values are stored separately.
- The new history table is rebuilt from older snapshots during initialization, which should help if the deployed app already has older successful market rows.

What still needs live validation
1. Refresh `ARM` again and inspect diagnostics.
   - Best-case outcome: `market_data_note` now says `Previous snapshot market data available: yes.` after a Yahoo rate-limit refresh.
2. If it still says `no`, that would now point much more strongly to an environment/data reality:
   - there may truly be no prior non-null ARM market values in the deployed local DB anymore
   - this would no longer look like the old selection bug

Claude is not required for this market-history step unless the new ticker-keyed fallback still fails live. If it does fail, the next question is likely about the deployed app’s actual SQLite history state rather than parser design.
