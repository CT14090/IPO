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

Tuesday, July 28, 2026 live validation after the retry-plus-pacing patch succeeded for `ARM`.

What the new live diagnostics prove:
- `ARM` no longer ends in `feed_error`.
- It now shows:
  - `insider_sales.lookup.status = sales_parsed`
  - `feed_entries = 29`
  - `candidate_filings = 28`
  - `documents_fetched = 28`
  - `xml_documents = 28`
  - `transactions_parsed = 39`
  - `filing_count = 17`
  - `total_shares_sold = 302,915`
- This is strong evidence that the combination of:
  1. feed retry/backoff, and
  2. short cross-company pacing
  fixed the specific SEC owner-include feed throttling problem we were seeing on ARM.

Additional useful live signal from the same JSON:
- `ARM` lock-up parsing also improved versus the earlier fallback state.
- `lockup_source` now reads:
  - `Lock-Up Restrictions section: Regex match: for a period of 180 days`
  instead of:
  - `No filing text available`
- Principal holders are still not being parsed cleanly for ARM, so that part remains a separate quality gap.

What I updated after this validation:
- `TASK_BOARD.md`
  - marked the ARM SEC feed path as live-confirmed successful after retry plus pacing
  - moved that item out of the unresolved bucket conceptually
- No new code was needed after seeing this JSON; this was validation-only.

Current project state:
- SEC/Form 4 refresh reuse: confirmed live
- SEC owner-include 429 resilience for ARM: confirmed live
- Market fallback instrumentation: still waiting for a Yahoo rate-limit case to exercise it
- Remaining notable parser-quality gap: ARM principal holders still empty / not cleanly parsed

If Claude is needed next, the most useful contribution would NOT be SEC-rate-limit work anymore.
The most useful next analysis target would be either:
1. principal-holder parsing quality on names like `ARM`, or
2. whether we should now move to shares-outstanding / locked-percentage context,
but only if we decide that parser quality is good enough to support that.
