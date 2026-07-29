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

ARM principal-holder parsing regressed after the numeric-percent fallback change.

Latest live diagnostics summary
- `principal_holders` is still wrong for `ARM`.
- The parser is now returning rows from a financial statement table instead of the principal-holder table.
- Example bad live rows:
  - row 0:
    - `holder = "4051"`
    - `shares = 1025234000`
    - `percent = 2`
    - extra keys include:
      - `Fiscal Quarter Ended June 30, 2023 AdditionalPaid-in Capital`
      - `Fiscal Quarter Ended June 30, 2023 RetainedEarnings`
      - `Fiscal Quarter Ended June 30, 2023 AccumulatedOtherComprehensiveIncome (Loss)`
  - row 1:
    - `holder = "6"`
    - `percent = 6`
  - row 2:
    - `holder = "59"`
    - `percent = 59`
- This means the new percent fallback itself is not enough; the table/row acceptance logic is now too permissive.

What is still good
- `ARM` lock-up parsing is still correct.
- `ARM` Form 4 parsing is still correct.
- The app is not crashing.
- The failure is isolated to principal-holder extraction in `ipo_tracker/sec.py`.

Most likely root cause
- After allowing bare numeric percent cells, the parser can now accept rows from non-holder tables that happen to contain:
  - one large numeric cell interpreted as `shares`
  - one small numeric cell interpreted as `percent`
- Current table-selection / row-validation heuristics are not strict enough to reject financial statement tables once those numbers are allowed.

Required next fix
1. Tighten table-level validation for principal-holder extraction.
2. Tighten row-level validation for principal-holder extraction.
3. Keep the bare numeric percent fallback, but only after the table/row has already passed stronger holder-specific checks.

Suggested implementation direction
- In `ipo_tracker/sec.py`, reject candidate holder tables when column names or header text include obvious financial-statement language such as:
  - `fiscal quarter`
  - `retained earnings`
  - `additional paid-in capital`
  - `accumulated other comprehensive income`
  - `cash flows`
  - `balance sheet`
  - `total assets`
  - `liabilities`
- Reject rows where `holder` is mostly numeric or implausibly short.
  - Examples that should be rejected immediately:
    - `"4051"`
    - `"6"`
    - `"59"`
- Require at least one plausible textual holder name before accepting a table.
- Continue preserving the current semantic default for ARM once the correct table is found:
  - first percent in row order
  - still expected to resolve to pre-offering `100.0` unless intentionally changed later

Tests to add
- Add a regression in `tests/test_sec.py` for an ARM-style false-positive financial table so the parser refuses it.
- Keep the existing ARM numeric-percent regression.
- Expected outcome after both fixes:
  - the financial statement table is rejected
  - the actual ARM holder table is selected
  - `principal_holders[0]` resolves to canonical keys only:
    - `holder`
    - `shares`
    - `percent`

Next live validation target
1. Refresh `ARM` again.
2. Confirm `principal_holders` no longer contains financial-statement rows.
3. Confirm `principal_holders[0]` is a real holder row.
4. Confirm no extra financial-statement keys leak into the parsed object.
5. Confirm `percent` is present and non-null.
