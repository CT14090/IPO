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

## Codex Handoff — 2026-07-27

Follow-up after the user hit a Streamlit startup `ImportError` on `from ipo_tracker.insiders import split_insider_sales_records, summarize_insider_sales`.

What I changed just now:
- `ipo_tracker/insiders.py`
  - Removed top-level imports from `ipo_tracker.sec`.
  - Replaced them with tiny local helper wrappers (`_normalize_cik`, `_sec_headers`, `_fetch_sec_text`) so `insiders.py` stays lightweight at module import time.
  - Goal: reduce import-time coupling between `insiders.py` and `sec.py` and avoid opaque deployment-time startup failures.

What did NOT change in behavior:
- The issuer-centric Form 4 source is still the SEC `browse-edgar?...&type=4&owner=include&output=atom` feed.
- Lookup metadata sentinel storage under `_lookup` is unchanged.
- App-side diagnostics / UI logic for Form 4 lookup status is unchanged.

Why this likely matters:
- The failing import line was in `app.py`, but the most likely real problem was an exception during `ipo_tracker.insiders` module initialization.
- This change makes that module much safer to import on Streamlit startup before any Form 4 work actually runs.

What needs validation now:
- Redeploy / refresh the Streamlit app and confirm it starts cleanly again.
- If the app loads, inspect `RDDT` in Diagnostics as planned.
- If the startup error persists, the next step is to capture the exact inner import exception from Streamlit logs because the issue is no longer likely to be caused by `insiders` importing `sec` too early.

Most useful next Claude contribution if needed:
- Only if the startup error persists after this import-hardening change: reason through any remaining module-level startup hazards in `app.py`, `sec.py`, and `insiders.py` without assuming the redacted Streamlit traceback is telling the whole story.
