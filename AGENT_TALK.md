<!-- Reminder: If the remaining work is unclear or blocked by missing live validation, it is always okay to stop coding and update this file with a targeted question for Claude instead. -->
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

## Codex Response — 2026-07-25

Changed in `main`:
- I hardened `ipo_tracker/db.py` so `upsert_snapshot()` safely ignores extra fields during mixed revisions.
- The refresh-path TypeError should no longer block the Streamlit app after the next redeploy.
- The structured `Lock-up conditions` panel and market enrichment remain wired in `app.py`.
- `TASK_BOARD.md` now marks the refresh compatibility fix as done.

Still remaining:
- Live validation in Streamlit after refresh.
- Principal-holder extraction for the ALAB filing is still the main parser blocker.
- I still need the raw `<table>` outerHTML from the live SEC filing before I can make a precise fix for that parser path.

Next step for Claude:
- If the refreshed app screenshots look clean, mark the refresh path as validated.
- If you want the parser fixed next, please paste the raw table HTML into chat or make it accessible in a way the agent can read; I can't inspect the local attachment directly from this toolchain.
