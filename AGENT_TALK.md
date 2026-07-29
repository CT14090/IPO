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

Wednesday, July 29, 2026 follow-up after the user reported that the second SEC refresh again took more than 30 seconds and no longer showed a big improvement over the first run.

New diagnosis from the latest ARM diagnostics
- Form 4 reuse is still working correctly.
- Evidence from ARM:
  - `candidate_filings = 1`
  - `documents_fetched = 1`
  - `xml_documents = 1`
  - `reused_transactions = 35`
  - `reused_filings = 14`
- So the second-run slowdown is no longer mainly a Form 4 problem.

Most likely remaining bottleneck
- market refreshes via Yahoo / `yfinance`
- latest ARM diagnostics show:
  - all market values null
  - `market_data_note = Market data fetch failed: Too Many Requests. Rate limited. Try after a while. Previous snapshot market data available: no.`
- But historically ARM previously did have non-null market values, so `no` strongly suggested our reuse path was only checking the immediately latest snapshot instead of the latest non-null historical snapshot.
- Also, every refresh was still re-hitting Yahoo because we had no in-process market cache.

What Codex changed just now
- `ipo_tracker/market.py`
  - added a short-lived in-process cache for `fetch_market_data(ticker, ipo_date)`
  - repeat refreshes in the same deployed app process can now reuse the previous Yahoo result, including a recent rate-limit failure, instead of immediately refetching everything
  - cached responses append `Reusing in-process market cache.` in the note
- `ipo_tracker/db.py`
  - added historical backfill for market fields from the latest non-null market snapshot, not just the immediately latest snapshot
  - if the newest snapshot has null market data but an older snapshot has values, dashboard rows now carry forward those historical values for reuse
  - if the newest note is a market-fetch failure and an older good market snapshot is used, the note now appends:
    - `Previous snapshot market data available: yes.`
    - `Backfilled previous snapshot market data from local history.`
- `tests/test_market.py`
  - added coverage for note preservation when a cached market failure is merged with reusable snapshot data

Expected live effect
1. First refresh may still be somewhat cold.
2. Second refresh in the same app process should be meaningfully faster because:
   - Form 4 data is already incremental
   - market calls should now come from the in-process cache instead of Yahoo
3. If Yahoo is rate-limiting but older market history exists, diagnostics should stop saying `Previous snapshot market data available: no.` and should instead backfill from local history.

Best next live validation target
- Refresh twice again after this deploy.
- Check:
  - whether second refresh becomes materially faster
  - whether ARM `market_data_note` changes from `... available: no.` to a historical-backfill / cache-reuse note

Claude is not required for this step unless we still see poor second-run timing after the market cache and historical-backfill pass. At that point the remaining issue would likely be broader refresh orchestration rather than parser logic.
