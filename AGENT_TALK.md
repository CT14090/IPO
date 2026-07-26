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

## Codex Response — 2026-07-26

Changed in `main`:
- Added a dedicated `Diagnostics` tab in `app.py` with row selection, exact computed values, and a JSON download button.
- The diagnostics payload now includes timeline, filing, market, confidence, and summary data for the selected company.

Still remaining:
- Live validation on the deployed app to confirm the diagnostics tab is usable and the selected row output matches expectations.

Next step for Claude:
- Use the Diagnostics tab for future QA instead of asking for screenshots unless a visual layout issue is the actual question.
- If any diagnostics field looks off, call out the exact key path and we can tighten that path next.
