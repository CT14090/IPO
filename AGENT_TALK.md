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

Current state after the user's newest live validation on Monday, July 27, 2026:
- SEC/Form 4 repeat-refresh performance is now strongly confirmed.
- User-measured refresh timing:
  - first SEC refresh: about `40s`
  - second SEC refresh: about `5s`
- Latest `RDDT` diagnostics confirm the incremental reuse path is live:
  - `status = sales_parsed`
  - `reused_transactions = 453`
  - `reused_filings = 53`
  - `candidate_filings = 2`
  - `documents_fetched = 2`
  - `xml_documents = 2`
  - `new_transactions_parsed = 26`
- This is no longer ambiguous: repeated historical Form 4 work is dramatically reduced on the second refresh.

Important new finding:
- The market-snapshot preservation path does NOT appear to be surfacing correctly yet in live diagnostics.
- The user still got:
  - `ipo_price = null`
  - `current_price = null`
  - `price_change_pct = null`
  - `avg_volume_30d = null`
  - `market_cap = null`
  - `market_data_note = "Market data fetch failed: Too Many Requests. Rate limited. Try after a while."`
- The expected appended note (`Reusing previous snapshot market data.`) did NOT appear.
- That means one of two things is likely true:
  1. the previous snapshot already had null market values for `RDDT`, so there was nothing to preserve,
  2. the preservation merge path is not actually receiving / matching the previous good market snapshot the way we expected.

Relevant code state already in `main`:
- `ipo_tracker/market.py`
  - `MARKET_VALUE_KEYS`
  - `market_data_has_values(data)`
  - `merge_market_snapshot(previous_snapshot, latest_market)`
- `app.py`
  - `refresh_live_data()` calls `merge_market_snapshot(company, enriched)` before persisting the snapshot.

What is now firmly established:
- The SEC/Form 4 optimization worked.
- The cold refresh is still materially slower than the hot refresh, but that is now an optimization question, not a correctness failure.
- The market-rate-limit fallback still needs debugging or at least better instrumentation.

Best next Claude contribution:
- Focus ONLY on diagnosing why the market snapshot reuse did not show up.
- Please analyze likely failure modes in this exact flow, especially:
  1. whether `company` in `refresh_live_data()` is guaranteed to include the last good market fields at the moment `merge_market_snapshot(company, enriched)` runs,
  2. whether the previous snapshot could already be null because a prior failed refresh overwrote it before this fix shipped,
  3. whether the preservation merge should happen inside `enrich_company()` or `_persist_snapshot()` instead of at the app layer,
  4. whether additional diagnostics should explicitly expose `previous_market_available = true/false` so we can distinguish "preservation logic failed" from "nothing good was left to preserve".
- Please prioritize the smallest reliable debug/improvement step rather than broad feature ideas.
