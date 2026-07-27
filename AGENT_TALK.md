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

Current state after the user's latest live validation:
- The refresh crash is fixed in practice: the user confirmed the app no longer crashes on `Refresh from SEC now`.
- The first performance pass was NOT enough: the user measured refresh at roughly a minute or more even after the bounded thread-pool Form 4 fetch change.
- The user's latest `RDDT` diagnostics still show substantial historical Form 4 work per refresh, including:
  - `feed_entries = 100`
  - `candidate_filings = 100`
  - `documents_fetched = 43`
  - `xml_documents = 41`
  - `transactions_parsed = 209`
- That confirms the remaining bottleneck is still repeated historical Form 4 parsing work, not the crash path.

What I changed just now:
- `ipo_tracker/insiders.py`
  - Added snapshot-aware incremental Form 4 refresh support via `existing_records=`.
  - Reuses previously stored insider-sale records when the effective unlock date is unchanged.
  - Stops scanning once the feed reaches filing dates older than the latest known stored filing date.
  - Skips already-known direct archive XML / HTML-companion filings based on stored `source_url` values.
  - Merges newly parsed sale transactions into existing history instead of rebuilding from scratch every time.
  - Adds richer lookup metadata fields such as:
    - `reused_transactions`
    - `reused_filings`
    - `new_transactions_parsed`
  - Introduces incremental statuses such as `sales_reused` and `no_new_form4_filings`.
- `ipo_tracker/sec.py`
  - `enrich_company()` now passes prior snapshot insider-sales data into `fetch_post_unlock_sales(...)` when the company’s `effective_unlock_date` is unchanged.
  - If the effective unlock date changes, it intentionally falls back to a full refresh so correctness is preserved.
- `tests/test_insiders.py`
  - Added regression coverage for:
    1. reusing stored sales when there are no newer filings,
    2. merging a newer filing into stored history.

Why this was the chosen fix:
- The live evidence showed that bounded concurrency alone did not solve the problem.
- The highest-leverage next move was to eliminate repeated historical work, not just parallelize it.
- This approach preserves correctness because it only reuses stored Form 4 history when the effective unlock boundary is unchanged.
- It should be especially beneficial on the SECOND and later refreshes, which is why the next validation should compare back-to-back refresh runs rather than only a cold refresh.

What still needs validation:
- Measure two back-to-back refreshes after deployment. The second run matters most.
- For an unlocked name like `RDDT`, confirm that diagnostics can now show an incremental-reuse status such as `sales_reused` when there are no newer filings.
- If refresh is still slow even after this change, the remaining time is likely dominated by one of two things:
  1. upstream SEC latency / rate limits,
  2. other non-Form-4 enrichment work still being re-fetched each refresh.

Most useful next Claude contribution if needed:
- If the incremental-refresh pass still does not materially reduce repeat refresh time, analyze the remaining likely bottleneck split between:
  1. SEC rate-limit / latency behavior requiring retry-backoff or lower concurrency,
  2. non-Form-4 enrichment calls in `ipo_tracker/sec.py` still doing repeated work each refresh,
  3. a stronger delta model for insider sales that records the latest processed filing anchor explicitly.
- Please prioritize what should be instrumented next if we need another round, rather than proposing broad feature work.
