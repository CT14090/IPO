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

I implemented the combined fix path based on Claude's analysis and the user's preference for lookback Option C.

What changed in code:
- `ipo_tracker/sec.py`
  - Added cached company-submissions loading via `@lru_cache`.
  - Added a shared SEC submission-record walker with Option C early-exit behavior: fetch archived submission fragments only until enough historical date coverage is reached.
  - Added earnings-trigger quarter-end parsing from lock-up text.
  - Added `find_earnings_release_filing(...)` to locate the earliest qualifying earnings release filing before the calendar unlock date.
  - Added `add_trading_days(...)` and `determine_effective_unlock_date(...)`.
  - `enrich_company(...)` now computes both:
    - `unlock_date` = calendar lock-up date
    - `effective_unlock_date` = earlier earnings-trigger date when confidently resolved
- `ipo_tracker/insiders.py`
  - Reused the shared SEC submission walker from `sec.py`.
  - Form 4 filtering now uses the passed unlock boundary, which is now the corrected effective unlock date when available.
- `ipo_tracker/db.py`
  - Added `effective_unlock_date` to snapshot storage / loading.
- `app.py`
  - Dashboard math now uses `effective_unlock_date` for status, countdown, and Form 4 interpretation.
  - `calendar_unlock_date` is preserved and shown for transparency when it differs.
  - Diagnostics payload now includes both calendar and effective unlock dates.
  - Company cards now explain when an earlier earnings-trigger unlock overrides the calendar date.
- Tests
  - `tests/test_sec.py` now covers trading-day offset logic and effective unlock date resolution.
  - `tests/test_insiders.py` was realigned to the shared submission walker and still covers XML companion fallback and post-unlock sale parsing.

Current diagnosis state:
- The original zero-count `RDDT` case likely had two causes together:
  1. submissions-history coverage was too naive / expensive
  2. the code filtered Form 4s against the wrong date boundary (`2024-09-17` calendar unlock instead of the earlier earnings-trigger unlock)
- Both are now patched in code.

What still needs live validation:
- Refresh the deployed app after this code is live.
- Inspect `RDDT`.
- Confirm diagnostics show:
  - `calendar_unlock_date`
  - `effective_unlock_date`
  - non-empty `insider_sales` if the patched path is working as expected
- Confirm `RDDT` no longer behaves like a simple calendar-upcoming unlock if the effective unlock resolves to an earlier August 2024 date.

Claude analysis is optional now. The most useful next Claude contribution, if needed later, would be reviewing whether `find_earnings_release_filing(...)` should remain broad (`8-K` / `10-Q` / `10-K`) or be narrowed further once we see live `RDDT` results.
