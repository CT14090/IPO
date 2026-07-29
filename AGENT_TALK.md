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

Current state after the latest live ARM diagnostics.

What the live evidence now says
- `principal_holders[0]` is no longer empty.
- The row now resolves to:
  - `holder = SoftBank Group Corp.`
  - `shares = 1025233999`
- But `percent` is still missing entirely in live output.

Root-cause diagnosis
- This is no longer a table-selection bug.
- This is very likely a narrow percent-fallback bug in `ipo_tracker/sec.py`.
- `_first_percent_candidate(values)` currently only accepts cells that still contain a literal `%` character.
- If the live SEC/`pandas.read_html` normalization strips the `%` sign and leaves bare numeric cells like `100` or `90.6`, then:
  - `_first_share_candidate(...)` still succeeds
  - holder parsing still succeeds
  - but `_first_percent_candidate(...)` returns `None`
- That exactly matches the live ARM symptom: row present, shares present, percent absent.

Concrete code change to make
- In `ipo_tracker/sec.py`, update `_first_percent_candidate(values)` so it behaves like this:
  1. Prefer the first explicit percent cell containing `%`.
  2. If no explicit percent cell exists, accept the first plausible bare numeric percentage candidate where `0 <= value <= 100`.
  3. Keep ignoring large share-count cells, which are already filtered out by the numeric range.
- This should preserve the current semantic default of keeping the first percent in row order, which for ARM remains the pre-offering `100`.

Suggested implementation shape
```python

def _first_percent_candidate(values: list[str]) -> float | None:
    fallback_percent: float | None = None
    for value in values:
        cleaned = _clean_cell_text(value)
        parsed = _parse_holder_measure("percent", cleaned)
        if not isinstance(parsed, (int, float)):
            continue
        numeric = float(parsed)
        if "%" in cleaned:
            return numeric
        if fallback_percent is None and 0.0 <= numeric <= 100.0:
            fallback_percent = numeric
    return fallback_percent
```

Regression test to add
- In `tests/test_sec.py`, add an ARM-style regression where the row values are the same as the current ARM fixture except the percent cells are bare numeric text instead of `100%` / `90.6%`.
- Expected result should remain:
  - `holder = SoftBank Group Corp.`
  - `shares = 1025233999`
  - `percent = 100.0`

Important blocker on Codex side
- The diagnosis is complete.
- I could not safely patch `ipo_tracker/sec.py` from this thread because:
  - the local shell/runtime bridge is unavailable in this session, so I cannot edit or test the checked-out repo directly
  - the GitHub large-file fetch path truncates `ipo_tracker/sec.py`, which prevents a safe full-file replace through the GitHub contents API
- So the next best move is for Claude or a thread with a working local repo bridge to apply the 5-line helper change plus the regression test.

What to validate after patching
1. Refresh `ARM` again.
2. Inspect diagnostics.
3. Confirm `principal_holders[0].percent` is now present and non-null.
4. Confirm it resolves to `100.0` unless we later decide to switch semantics to the post-offering percent (`90.6`).
