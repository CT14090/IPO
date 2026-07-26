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

Current state:
- The principal-holder parser issue is fixed in `ipo_tracker/sec.py`.
- The ToC false positive is blocked by rejecting candidate tables that have no numeric cell above 1000 before scoring.
- I added a regression test in `tests/test_sec.py` for a ToC-only holder table.
- The latest ALAB diagnostics now show correct principal holders rather than table-of-contents rows.
- The remaining open question is `early_release_pct`, which is still `null`.

What the current ALAB diagnostics show:
- `has_early_release = true`
- `has_earnings_trigger = true`
- `amendment_date = 2024-08-06`
- `early_release_description` is populated with the early-release language excerpt
- `early_release_pct = null`
- principal holders are now real holders with shares and percentages, not ToC page numbers

Why I think this is a separate question:
- The holder-table bug was a table-selection problem.
- `early_release_pct` depends on how the filing phrases the early-release size, not on holder-table parsing.
- I do not want to infer a percentage from holder ownership percentages or from lock-up math unless the filing explicitly states it.

What I need from Claude:
- Analyze the current ALAB diagnostics and recommend the best path to extract `early_release_pct` reliably.
- Focus on whether the parser should search wider text windows, the 8-K amendment excerpt, alternate regex patterns, or a separate helper dedicated to percentage extraction.
- Call out any risks of false positives if we broaden the regex too aggressively.
- If the right answer is to leave `pct` null unless the filing states an explicit percentage, say that clearly.
- If a targeted parser extension is worth it, recommend the smallest safe change set and the best test fixture strategy.

Important constraints:
- Keep the existing `has_early_release` / `has_earnings_trigger` detection intact.
- Do not regress the fixed holder-table parsing behavior.
- Treat `pct` as optional enrichment, not required core unlock logic.

Please review the current filing wording and tell me whether `early_release_pct` is worth pursuing further for this project, and if so, what exact parser shape you would implement next.
