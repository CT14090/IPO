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

I processed Claude's latest guidance and updated the repo notes accordingly. No app code changed in this pass.

What changed:
- `TASK_BOARD.md` now names `RDDT` as the primary live-validation target for the Form 4 positive-data path.
- The board also records that Form 144 should not be treated as evidence for or against the Form 4 parser, because Form 144 is intent-to-sell rather than completed Form 4 execution.
- The zero-state wording decision is settled for now: keep the company-card copy as-is because it correctly says `parsed`, not `none exist`.
- The overview-table `0` caveat remains a later UX decision, not a blocker.

Current truth state:
- Form 4 feature deployment is real and visible in the app.
- Zero-result UI state is confirmed live.
- Positive-result Form 4 parsing is still unconfirmed live.
- `RDDT` is the concrete next issuer to test because its unlock date was `2024-09-17` and public post-unlock Form 4 sales exist.

Next required user validation:
- Refresh the deployed app.
- Open `RDDT` specifically.
- Check whether `Post-Unlock Form 4 Sales` becomes nonzero.
- If possible, capture the `Diagnostics` tab JSON for `RDDT`, especially `insider_sales.summary` and `insider_sales.transactions`.

Potential future Claude analysis, if needed later:
- edge cases around duplicate `4` vs `4/A` filings
- whether a tooltip/footnote should be added to the overview-table Form 4 count
- how to validate multiple reporting owners in one filing more explicitly
