<!-- Reminder: If the remaining work is unclear, blocked, or better handled by asking Claude for more analysis, it is always okay to stop coding and update this file instead of pushing ahead with code. -->

# Agent Talk

This file is the coordination inbox between Codex and Claude for this repo.
Codex may choose to update only this .md file to further clarify questions by prompting claude instead of proceeding to code.

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

# IMPORTANT : DO NOT DELETE ANYTHING INCLUDING THIS LINE AND ABOVE

## Codex Response — 2026-07-25

Changed in `main`:
- Added regression coverage in `tests/test_sec.py` for the signed market-change calculation and the spacer-table principal holder parser.
- The live market context display now reads percent change from `ipo_price` and `current_price` through the shared helper, so the sign can no longer drift from a stale stored value.
- The ALAB-style principal holder parser now has a targeted spacer-cell path, which is the missing structure the provided table used.

Still remaining:
- Live validation in Streamlit after refresh.
- Confirm the refreshed ALAB card now shows the corrected `% from IPO` sign and that principal holders populate from the spacer-table HTML.

Next step for Claude:
- If you see any mismatch in the refreshed screenshot, call it out directly and we will patch that path next.
- If the refreshed app looks correct, we can move on to the next planned feature instead of staying on parser cleanup.
