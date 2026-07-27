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

Current state after the user's latest live validation on Monday, July 27, 2026:
- The incremental Form 4 refresh optimization is now live-confirmed.
- User-measured refresh timing:
  - first SEC refresh: about `30s`
  - second SEC refresh: under `10s`
- Latest `RDDT` diagnostics confirm the reuse path is actually being exercised, not just assumed:
  - `status = sales_parsed`
  - `reused_transactions = 453`
  - `reused_filings = 53`
  - `candidate_filings = 2`
  - `documents_fetched = 2`
  - `xml_documents = 1`
  - `new_transactions_parsed = 12`
- That means the major SEC refresh bottleneck from repeated historical Form 4 rebuilding is materially improved on repeat refreshes.

New remaining issue surfaced by the same live validation:
- Market data can still be wiped on refresh when Yahoo Finance rate-limits the app.
- The user's diagnostics showed:
  - `ipo_price = null`
  - `current_price = null`
  - `price_change_pct = null`
  - `avg_volume_30d = null`
  - `market_cap = null`
  - `market_data_note = "Market data fetch failed: Too Many Requests. Rate limited. Try after a while."`
- So the SEC/Form 4 side improved, but the market-data path now needs graceful preservation under rate limiting.

What I changed after that validation:
- `ipo_tracker/market.py`
  - Added `MARKET_VALUE_KEYS`.
  - Added `market_data_has_values(data)` helper.
  - Added `merge_market_snapshot(previous_snapshot, latest_market)`.
  - Logic:
    - if latest market payload has real values, keep it
    - if latest payload failed with `Market data fetch failed: ...` and previous snapshot has real market values, reuse the previous market values
    - append note text: `Reusing previous snapshot market data.`
- `app.py`
  - `refresh_live_data()` now calls `merge_market_snapshot(company, enriched)` before persisting the refreshed snapshot.
  - Goal: a transient Yahoo rate limit should no longer replace previously good market fields with nulls.

Important nuance:
- I have NOT been able to live-run or locally test this market-preservation path because the local shell/runtime bridge is unavailable in this session.
- So the market-rate-limit preservation change is code-complete but still needs user validation after deploy.

Current assessment:
- SEC/Form 4 refresh performance: materially improved and now confirmed live.
- Crash resilience: confirmed live.
- Remaining practical issue: Yahoo rate-limit degradation should preserve prior market data instead of clearing the UI, but this still needs validation.

Most useful next Claude contribution if needed:
- Focus only on the market-data resilience question, not broad feature work.
- If the preservation fix works, the next likely design question is whether we should also add a short TTL cache / backoff on Yahoo requests to reduce the chance of rate-limit hits.
- If the preservation fix does NOT work, analyze whether the merge should happen earlier, later, or with a stricter note/error signature than `startswith("Market data fetch failed:")`.
