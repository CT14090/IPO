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

I reviewed the latest ALAB diagnostics and the latest Claude analysis. The conclusion is now settled: `early_release_pct = null` is correct for ALAB because the live filing does not state an explicit percentage for the early-release clause.

Current state:
- The principal-holder parser fix is already in place and confirmed.
- The ALAB holder rows now look correct.
- The early-release trigger and earnings-trigger detection remain correct.
- The live filing only expresses a binary earlier-of unlock trigger, not a percentage-based partial release.

Decision:
- Do not broaden `_PERCENT_EARLY_RELEASE_RE` for ALAB right now.
- Keep `early_release_pct` as an optional enrichment field that stays null when the filing does not explicitly state a percentage.
- Avoid inferring a percentage from unrelated figures such as holder ownership percentages, directed share program percentages, or overallotment language.

Why this matters:
- Broadening the regex would likely create false positives against unrelated percentages elsewhere in the filing.
- The current parser already captures the actionable signal: `has_early_release = true` and `has_earnings_trigger = true`.
- For this project, that is enough to tell the user the unlock may happen earlier than the calendar date.

Please treat `early_release_pct` as closed for ALAB unless a future fixture shows a real filing with an explicit percentage-based early release clause.

If you want to keep exploring this area later, the next valid step would be to collect a real non-ALAB filing that explicitly states a tiered or percentage early-release clause and use that as a fixture before changing the parser.
