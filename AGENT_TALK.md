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

Wednesday, July 29, 2026 update after new ARM diagnostics showing:
- `principal_holders = []`
- `lockup_source = No filing text available`
- notes still implied filing-text parsing in the old deploy output

Diagnosis
- This was not the same ARM table-structure bug as before.
- In this refresh, the app never obtained usable prospectus HTML, so the holder parser never ran.
- Root problem = filing fetch miss / transient SEC access issue, not another embedded-header parsing miss.

What Codex changed in `main`
- `ipo_tracker/sec.py`
  - added bounded retry for SEC text/json fetches on transient `429` / `503`
  - records the fetch failure reason as a short note such as `HTTP 429`
  - stops rewarding confidence for `lock-up parsed from filing text` when the HTML was unavailable
  - stops claiming `IPO date parsed from filing text` when the app fell back to the seeded watchlist date
  - adds a clearer holder diagnostic: `Principal holder table not parsed because filing HTML was unavailable`
- `tests/test_sec.py`
  - added regression coverage for the missing-filing-HTML case so misleading confidence details are caught

Important distinction now
- If diagnostics show:
  - `principal_holders = []`
  - `No filing text available (...)`
- then we should read that as a fetch-layer issue.
- If diagnostics show real filing text but empty holders, that is a parser-layer issue.

Best next live validation target
1. Refresh the deployed app again.
2. If ARM still misses HTML, confirm the notes now explicitly say something like:
   - `Prospectus fetch failed during refresh: HTTP ...`
3. Also confirm the confidence details no longer falsely say:
   - `Lock-up term parsed from filing text`
   - `IPO date parsed from filing text`
   when the filing HTML was not fetched.

Claude is not needed unless we want broader strategy ideas for SEC fetch resilience beyond this bounded retry + truthful diagnostics pass.
This specific bug was minor and has already been addressed in code.
