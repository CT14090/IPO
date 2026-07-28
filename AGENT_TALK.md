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

## Codex Handoff — 2026-07-28

Tuesday, July 28, 2026 live validation has now advanced beyond the prior `ARM principal_holders = []` state.

New live result from the user:
- `principal_holders` now contains a real parsed row:
  - `holder = SoftBank Group Corp.`
  - `shares = 1025233999`
- This is the main success condition we were trying to reach for the embedded-header parser pass.
- It means the parser is no longer completely missing the ARM-style prospectus table.

But the live output also shows the parser is not fully normalized yet:
- same row still contains stray unlabeled keys:
  - `"8": "%"`
  - `"20": "%"`
- So the current state is:
  - materially improved and live-useful
  - but not yet clean / final

Most likely interpretation:
- promoted header handling is now good enough to anchor the real holder row
- however duplicate or unlabeled percent columns from the wide ARM table are still leaking through into the canonicalized dict
- the parser is probably preserving columns whose normalized names are not mapped to `shares` / `percent` / `holder`, so their raw DataFrame column labels survive as numeric-string keys

What Codex already did after this validation:
- updated `TASK_BOARD.md` to reflect:
  - ARM holder parsing is now live-confirmed non-empty
  - residual cleanup remains for stray numeric-string keys and multi-percent interpretation

Best next engineering target:
1. clean up residual holder-row noise for ARM-style tables
2. decide policy for multi-percent / multi-number tables:
   - should we preserve pre-offering fields only?
   - post-offering fields only?
   - or structured separate fields?

If Claude is useful here, the best analysis target is:
- how to normalize wide prospectus holder tables with both pre-offering and post-offering columns without losing meaning or leaking raw numeric column names into the output dict
- especially whether the product should keep only one canonical `percent` / `shares` pair or move to a more explicit structure for wide tables
