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

ARM principal-holder filtering is now tightened locally on `main`.

What changed
- In `ipo_tracker/sec.py`:
  - principal-holder candidate tables are now rejected when their headers/body include obvious financial-statement language such as `fiscal quarter`, `retained earnings`, `additional paid-in capital`, or `accumulated other comprehensive income`
  - holder rows are now rejected unless the holder field looks like a plausible textual name, which filters out bad values such as `4051`, `6`, and `59`
  - the bare numeric percent fallback remains in place, but only after the table/row passes these stricter holder-specific checks
- The current ARM semantic default is preserved:
  - first percent in row order
  - still expected to resolve to pre-offering `100.0` unless intentionally changed later

Tests added
- `tests/test_sec.py` now includes:
  - the existing ARM numeric-percent regression
  - a false-positive financial-table regression
  - a numeric-holder-name guard

Local validation completed
- Focused local checks passed for:
  - bare numeric percent fallback
  - financial-table rejection signals
  - plausible holder-name filtering
- I also directly verified that `_canonicalize_holder_row(...)` now returns `{}` for a financial row shaped like the bad live ARM diagnostics.

Next live validation target
1. Refresh `ARM` again.
2. Confirm `principal_holders` no longer contains financial-statement rows.
3. Confirm `principal_holders[0]` is a real holder row.
4. Confirm no extra financial-statement keys leak into the parsed object.
5. Confirm `percent` is present and non-null.
