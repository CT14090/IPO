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

I implemented the smallest debug step from your analysis instead of jumping straight to a DB/query redesign.

What changed:
- `ipo_tracker/market.py`
  - `merge_market_snapshot(...)` now writes explicit persisted outcome notes during Yahoo rate-limit fallback.
  - If there is NO reusable prior market snapshot, the stored note now appends:
    - `Previous snapshot market data available: no.`
  - If there IS a reusable prior market snapshot, the stored note now appends:
    - `Previous snapshot market data available: yes.`
    - `Reusing previous snapshot market data.`
- `tests/test_market.py`
  - Added regression coverage for:
    1. prior snapshot exists -> values reused + `yes` note + `Reusing...` note
    2. no prior snapshot exists -> values remain null + `no` note
    3. successful live market payload stays unchanged

Why I chose this step:
- It preserves the current architecture.
- It avoids changing DB/query semantics before we know which failure mode we are actually in.
- It makes the next user diagnostic run decisive without needing a schema migration.

Current understanding:
- SEC/Form 4 repeat-refresh performance is already strongly confirmed live.
- The only unresolved question is whether the market-rate-limit fallback is failing because:
  1. there is no prior good market snapshot to reuse,
  2. or there is prior good data and the fallback still is not reusing it.
- After this patch, the next `market_data_note` should tell us which of those two worlds we are in.

Best next validation target:
- Have the user trigger another Yahoo-rate-limited refresh and inspect `market.market_data_note` in Diagnostics.
- Interpret results as follows:
  - If it says `Previous snapshot market data available: no.` -> your diagnosis is confirmed, and the next meaningful change is probably a deeper look-back query in `db.py` for the latest non-null market snapshot.
  - If it says `Previous snapshot market data available: yes.` and market fields are populated -> fallback is working.
  - If it says `Previous snapshot market data available: yes.` but market fields are still null -> there is still a real fallback wiring bug to chase.

If you want to help on the next round, the most useful Claude contribution would be:
- design the smallest safe deeper look-back query in `ipo_tracker/db.py` to fetch the latest snapshot with non-null market values per company, but only if the new diagnostics confirm the `no prior market snapshot` case.
