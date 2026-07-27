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

The confidence-based filtering feature is now implemented in `app.py`.

Current dashboard behavior:
- A sidebar slider sets the minimum confidence threshold for rows shown as ready.
- Rows below that threshold are grouped into a visible `Needs review` bucket.
- Overview tables now split into ready rows and needs-review rows.
- Company cards now show a `Review` metric and mark low-confidence cards in the expander title.
- The diagnostics payload now includes review state and minimum-confidence context.

Current project state:
- The ALAB principal-holder parser fix remains in place.
- `early_release_pct = null` remains correct for ALAB and is no longer an open parsing bug.
- The dashboard is now more readable because lower-confidence rows are no longer mixed into the main ready view.

No new analysis is required right now. The next straightforward engineering step is the next feature from the board, which is Form 4 insider tracking after unlock.
