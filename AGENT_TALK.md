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

Current scope completed:
- Rewrote `TASK_BOARD.md` into stricter evidence-based buckets so it now separates:
  - confirmed by live evidence
  - confirmed by screenshots / user visual pass
  - implemented in `main`, not independently re-run in this session
  - covered by tests
  - still open
- Implemented the next feature: post-unlock Form 4 insider-sale tracking.

Code changes completed:
- Added `ipo_tracker/insiders.py`.
  - `parse_form4_sales(...)` parses XML Form 4 filings.
  - It intentionally keeps only actual sale transactions (`transactionCode == "S"`).
  - `fetch_post_unlock_sales(...)` filters to Form 4 / 4-A filings on or after the unlock date and then filters transactions to post-unlock trade dates.
  - `summarize_insider_sales(...)` computes transaction count, filing count, total shares sold, and latest sale date.
- Updated `ipo_tracker/sec.py`.
  - `enrich_company(...)` now fetches post-unlock Form 4 sales after it computes the unlock date.
  - The notes string now includes a short insider-sale summary when sales exist.
  - Returned enrichment dict now includes `insider_sales`.
- Updated `ipo_tracker/db.py`.
  - Added `insider_sales_json` to snapshot schema.
  - Snapshot writes now persist insider sales.
  - Dashboard row loads now deserialize insider sales back into Python objects.
- Updated `app.py`.
  - Overview table now has `Post-Unlock Form 4 Sales`.
  - Overview metrics now include total Form 4 sale transactions across ready rows.
  - Company cards now render a `Post-unlock Form 4 sales` panel.
  - Diagnostics JSON now includes insider-sale summary + transactions.
- Added `tests/test_insiders.py`.
  - sale-only parsing
  - post-unlock filtering
  - summary math

Important accuracy note:
- I did not mark the new Form 4 feature as live-confirmed.
- It is on the board under `Implemented In main, Not Independently Re-Run In This Session` because the local shell/runtime bridge is unavailable in this session, so I could not run the app or local tests directly.

What still needs validation from the deployed app:
- Refresh from SEC.
- Confirm the overview table shows `Post-Unlock Form 4 Sales` without errors.
- Confirm at least one company card shows the new `Post-unlock Form 4 sales` panel.
- Confirm diagnostics JSON includes top-level `insider_sales.summary` and `insider_sales.transactions`.

Potential areas where deeper Claude analysis could still help later, but are not blockers right now:
- Form 4 amendment deduping (`4` vs `4/A`) if we start seeing duplicates in live data.
- Whether we should broaden beyond non-derivative sales into derivative dispositions for a later advanced view.
- Better heuristics for mapping multiple reporting owners to individual transactions when a filing includes more than one insider.

If Claude wants to contribute next, the most useful thing would be review-level analysis of likely real-world Form 4 edge cases rather than restating the existing plan.
