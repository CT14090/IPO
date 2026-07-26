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

- Keep messages short, direct, and actionable.
- Prefer file references, concrete next steps, and explicit status updates.
- When a task is complete, say so clearly.
- When a task is blocked, name the blocker and the next required input.
- Delete the previous message before writing the next one so the file always contains only the current handoff.

# IMPORTANT : DO NOT DELETE ANYTHING INCLUDING THIS LINE AND ABOVE

## Codex Handoff — 2026-07-26

I patched `ipo_tracker/sec.py` so principal-holder table selection now skips any candidate table that does not contain a real numeric value above 1000 before scoring. That should block the ALAB table-of-contents rows from winning the match.

I also added a regression test in `tests/test_sec.py` for a ToC-only table so this specific failure stays fixed.

Please re-run ALAB refresh and pull a new `ALAB_diagnostics.json`. The only thing I still need to confirm is whether the refreshed snapshot now shows real holder rows and whether `early_release_pct` remains null after the refresh.

If `early_release_pct` is still null, treat it as a live-filing coverage question rather than a table-selection bug.
