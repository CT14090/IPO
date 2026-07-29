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

Wednesday, July 29, 2026 live follow-up after the user re-tested the deployed app.

What is now confirmed live
- The repeat-refresh performance fix is working again.
- User report: first SEC refresh was materially slower; second refresh decreased significantly.
- Latest ARM diagnostics also show `market_data_note` includes `Reusing in-process market cache.`
- That means the new in-process Yahoo market cache is active in production, not just in code.

Latest ARM live facts
- `insider_sales.lookup.status = sales_parsed`
- `candidate_filings = 1`
- `documents_fetched = 1`
- `xml_documents = 1`
- `reused_transactions = 39`
- `reused_filings = 17`
- `new_transactions_parsed = 1`
- `principal_holders = [{"holder": "SoftBank Group Corp.", "shares": 1025233999}]`
- `market_data_note = Market data fetch failed: Too Many Requests. Rate limited. Try after a while. Reusing in-process market cache. Previous snapshot market data available: no.`

What remains open
1. Historical market backfill still looks incomplete for ARM.
   - The note still says `Previous snapshot market data available: no.`
   - Since ARM had historical non-null market values in earlier user-provided diagnostics, either:
     - the deployed DB snapshot history no longer contains a good ARM market row, or
     - our latest-non-null backfill query/merge path still misses a valid older row.
2. ARM holder parsing is cleaner, but still incomplete.
   - The live row now has only canonical keys and no stray numeric placeholders, which is good.
   - But it still only surfaces `holder` and `shares`, with no `percent`.
   - We still need a decision on whether to preserve the pre-offering percent, the post-offering percent, or both when ARM-style tables expose multiple percent columns.

Interpretation
- No Claude analysis is required for the repeat-refresh speed issue anymore; that part is live-confirmed.
- Claude may still be useful for thinking through the best semantic rule for ARM-style percent selection if we want a stronger parsing policy before changing code.
- If we do not need Claude, the next coding target should be the historical-market-backfill miss, because that is now the clearest remaining bug surfaced by live diagnostics.
