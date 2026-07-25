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
- The refreshed Streamlit screenshot confirms the market `% from IPO` display is now correct and signed properly.
- `tests/test_sec.py` now covers the signed market helper and the spacer-table parser.
- The ALAB spacer-table parser is in place in `ipo_tracker/sec.py` for the remaining holder-extraction path.

Still remaining:
- Live validation for ALAB principal holder extraction after the next refresh.

Next step for Claude:
- If the refreshed ALAB card still does not populate principal holders, we need the exact rendered HTML or a screenshot of that section.
- If it does populate correctly, we can close out parser cleanup and move to the next task-board item.
