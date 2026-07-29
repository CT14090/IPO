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

Wednesday, July 29, 2026 follow-up after implementing the ARM holder-percent fix.

What Codex changed
- `ipo_tracker/sec.py`
  - updated the spacer-table fast path so it scans all non-spacer value cells for the first explicit percent instead of assuming the percent always sits in a fixed position
  - added fallback extraction for `shares` and `percent` from row values in `_canonicalize_holder_row(...)` when column-name normalization misses them
- `tests/test_sec.py`
  - added an ARM-style spacer-table regression that expects:
    - `holder = SoftBank Group Corp.`
    - `shares = 1025233999`
    - `percent = 100.0`

Current parsing assumption
- For ARM-style rows that expose both pre-offering and post-offering percentages, the parser currently keeps the first percent in row order.
- In the current fixture and intended live behavior, that means keeping the pre-offering figure (`100%`) rather than the post-offering figure (`90.6%`).
- This matches the existing embedded-header test and is the least disruptive default for now.

What still needs live validation
1. Refresh `ARM` again and inspect diagnostics.
2. Confirm whether `principal_holders[0]` now includes a non-null `percent` field.
3. If it does, confirm whether the value is `100.0`, which would match the current parsing rule.

When Claude is useful
- Claude is not required to validate whether the field now appears; that is a straight live test.
- Claude may still be useful later if we want to revisit the semantic choice between pre-offering percent (`100%`) and post-offering percent (`90.6%`) after we confirm the bug itself is fixed.
