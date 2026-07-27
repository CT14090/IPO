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

I applied the next Form 4 pass based on the previously chosen best options.

What changed:
- `ipo_tracker/insiders.py`
  - Switched Form 4 discovery away from issuer `submissions.json` walking and onto the issuer-centric SEC `browse-edgar?...&type=4&owner=include&output=atom` feed.
  - Added feed parsing, filing-link resolution, archive/detail-page candidate URL handling, and HTML-to-XML companion fallback.
  - Added structured lookup metadata with statuses like:
    - `sales_parsed`
    - `no_form4_filings_after_unlock`
    - `no_sale_transactions_after_unlock`
    - `filings_found_but_no_ownership_xml`
    - `feed_error`
  - To avoid a schema migration, the lookup metadata is stored as a sentinel record inside the existing `insider_sales` JSON list under `_lookup`.
  - `summarize_insider_sales(...)` now ignores that sentinel metadata automatically.
- `app.py`
  - Added parsing helpers that split stored insider-sale records into:
    - structured lookup metadata
    - actual sale transactions
  - Diagnostics JSON now includes `insider_sales.lookup` explicitly.
  - The company-card Form 4 panel now shows lookup status / reason and basic counts even when parsed sales remain zero, so a `0` is no longer completely opaque.
- `tests/test_insiders.py`
  - Reworked tests around the owner-include Atom feed path.
  - Added coverage for:
    - post-unlock filtering using feed entries
    - direct XML filing links
    - HTML filing links resolved via XML companion
    - zero-result lookup metadata
    - summary logic ignoring the `_lookup` sentinel

What did NOT change this pass:
- No new DB column or schema migration.
- No change to `ipo_tracker/sec.py` or `ipo_tracker/db.py` was required for this pass because the lookup metadata piggybacks on the existing `insider_sales_json` field.
- The Option C SEC submissions-history optimization for other filing types remains as implemented previously.

Current state / likely outcome:
- The repo now uses the better issuer-centric Form 4 discovery source that Claude argued for.
- The dashboard should now tell us whether `0` means:
  - no qualifying Form 4 filings after unlock,
  - filings existed but yielded no sale-code transactions,
  - feed/doc resolution failed,
  - or sales were actually parsed.

What still needs live validation:
- Redeploy / refresh the Streamlit app.
- Inspect `RDDT` specifically in the `Diagnostics` tab and in the company-card Form 4 panel.
- Confirm that `insider_sales.lookup.status` is now informative.
- Best-case outcome: `RDDT` shows nonzero parsed post-unlock sales.
- If `RDDT` still shows zero, the new lookup status should tell us whether the remaining issue is:
  - no issuer-linked Form 4s in SEC owner feed,
  - wrong document resolution from the feed links,
  - or sales existing but not matching our current sale-code parser.

Most useful next Claude contribution if needed:
- If live `RDDT` still fails, analyze whether SEC owner-feed entries for Reddit point to filing detail pages whose XML links need a more specific resolver than the current generic href scan.
- Secondary follow-up only if needed: review whether sale-code scope should stay `S` only or include other codes for this dashboard.
