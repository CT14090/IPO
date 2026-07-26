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
- Discovery now prefers real source/profile names over `CIK ####` placeholders and skips nameless candidates entirely.
- The ALAB spacer-table parser now ignores table-of-contents rows by requiring a real `Name of Beneficial Owner` header and a share count greater than 1000.
- `extract_lockup_conditions()` now looks farther into the lock-up section, so the `20% of eligible securities` early-release percentage is captured.
- Regression coverage in `tests/test_discovery.py` and `tests/test_sec.py` now matches those cases.

Still remaining:
- Live validation in Streamlit after refresh for Discovery rows and the ALAB holder table.

Next step for Claude:
- If Discovery still shows `CIK ####` rows after refresh, paste the updated screenshot and we will keep tightening the fallback path.
- If the ALAB holder table is still wrong, I’ll need the rendered HTML or another screenshot of that section so we can isolate the remaining shape difference.
