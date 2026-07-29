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

ARM numeric-percent fallback is now patched locally on `main`.

What changed
- In `ipo_tracker/sec.py`, `_first_percent_candidate(values)` now:
  1. returns the first explicit percent cell containing `%`
  2. otherwise falls back to the first plausible bare numeric percentage in the `0..100` range
- This preserves the current row-order behavior, so ARM still prefers the pre-offering `100` over the later `90.6`.

Test coverage added
- `tests/test_sec.py` now includes an ARM-style spacer-table regression where the percent cells are plain `100` and `90.6` text without literal `%` signs.
- Expected result remains:
  - `holder = SoftBank Group Corp.`
  - `shares = 1025233999`
  - `percent = 100.0`

Next validation
1. Run the targeted sec tests locally.
2. Refresh `ARM` in the app.
3. Confirm `principal_holders[0].percent` is now present and non-null.
4. Confirm the row still contains only canonical keys: `holder`, `shares`, `percent`.
