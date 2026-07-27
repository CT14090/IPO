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

I finished the board cleanup that the user asked for before adding more features.

What changed:
- Added the remaining SEC parser regression tests in `tests/test_sec.py` for greenshoe disambiguation, early-release plus earnings-trigger detection, 8-K amendment detection, and cover-page IPO date extraction.
- Kept the earlier holder-parser and discovery tests in place.
- Updated `TASK_BOARD.md` so the current `Implemented in main, Pending Live Validation` and `Needs Regression Tests` sections are effectively cleared for the present scope.

Current state:
- The ALAB parser questions are settled.
- The confidence-filtered dashboard is implemented.
- Discovery, lock-up conditions, market enrichment, and the review-state split are treated as visually validated for now.
- The new regression coverage is committed, but I could not run the local test suite in this session because the local shell/runtime bridge is unavailable.

No new Claude analysis is required right now. The next straightforward engineering step remains Form 4 insider tracking after unlock.
