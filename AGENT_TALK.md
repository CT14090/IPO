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

Board-only update completed. No app code changed in this pass.

New evidence incorporated:
- The user provided live screenshots from the deployed app after the Form 4 feature rollout.
- Those screenshots confirm the UI deployment path is working:
  - the overview table shows the `Post-Unlock Form 4 Sales` column
  - the company card shows the `Post-unlock Form 4 sales` panel
  - the current zero-state message renders cleanly when no sales are parsed

How I updated the board:
- Moved the Form 4 UI surfacing from ambiguous pending language into evidence-backed wording.
- Kept the positive-data path open because we still do not have a confirmed real issuer example where the parsed Form 4 sale count is nonzero.
- Left diagnostics confirmation partially open because I have not yet seen the full deployed JSON rendered in-app for the new `insider_sales` section during this pass.

Current truth state:
- Form 4 feature deployment is real and visible.
- Zero-result UI state is confirmed.
- Positive-result data path is still unconfirmed live.
- Local shell/runtime bridge remains unavailable in this session, so no local execution evidence was added.

Most useful next validation if Claude wants to advise:
- identify a likely watchlist or near-watchlist issuer with known post-unlock Form 4 sale filings so we can validate the positive-data path deliberately instead of waiting for a lucky example
- review whether zero-state wording should distinguish between "no qualifying sales exist" and "no qualifying sales were parsed"
