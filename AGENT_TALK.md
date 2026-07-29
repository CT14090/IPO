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

Minor ARM holder cleanup status on Wednesday, July 29, 2026:

What I verified directly in `main`
- The parser-side fix for the leaked ARM keys was already present in `ipo_tracker/sec.py` before this handoff refresh.
- `_canonicalize_holder_row(...)` now drops:
  - raw numeric column labels such as `"8"` / `"20"`
  - bare `%` text artifacts
- So the code path that should suppress the stray ARM keys is already live in source.

What I changed just now
- Tightened `tests/test_sec.py` so the ARM-style embedded-header regression now asserts:
  - parsed row count is still `1`
  - the SoftBank row still maps to `holder`, `shares`, `percent`
  - the parsed dict keys are exactly `{ "holder", "shares", "percent" }`
- Updated `TASK_BOARD.md` so the board no longer describes the numeric-key cleanup as purely open work.

Current state
- We now have:
  - source-level fix present
  - regression coverage strengthened
- We do not yet have fresh live validation from the deployed app proving that the ARM diagnostics JSON no longer shows numeric-string keys.

Best next validation target
- Refresh the deployed app and inspect `ARM` diagnostics.
- Expected result now:
  - `principal_holders[0]` contains only canonical keys
  - no `"8": "%"`
  - no `"20": "%"`

What still remains conceptually open
- product policy for wide holder tables with both pre-offering and post-offering metrics:
  - keep pre-offering `%` only
  - keep post-offering `%` only
  - or move to a richer structured representation later
- That is now a design decision, not the same bug as the leaked numeric keys.

Use Claude only if useful for the design question above.
For the numeric-key bug itself, Codex considers the code fix small and already handled; the next step is live validation, not deeper parser analysis.
