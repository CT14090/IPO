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

I moved to the live ARM failure path instead of asking for more analysis first.

What I changed:
- `ipo_tracker/insiders.py`
  - Added targeted retry/backoff for the SEC owner-include Form 4 Atom feed request.
  - Retry policy:
    - up to 3 attempts total
    - retries only on `429` and `503`
    - honors `Retry-After` when present, capped to a short wait
    - otherwise uses short bounded delays (`1s`, then `2s`)
  - This patch is intentionally narrow: it only touches the initial owner-include feed fetch, not the rest of the parsing / reuse pipeline that is already behaving well.
- `tests/test_insiders.py`
  - Added regression coverage for:
    1. a `429` on the first feed request followed by a successful retry
    2. repeated `429` responses that still end in `feed_error`

Why I chose this step without looping back first:
- The user’s latest live diagnostics showed a concrete current failure on `ARM`:
  - `insider_sales.lookup.status = feed_error`
  - reason: `429 Too Many Requests` from SEC browse-edgar owner=include feed
- That is a real production problem with a very contained mitigation.
- The patch does not interfere with the already-confirmed repeat-refresh reuse logic.

Current state after this patch:
- SEC/Form 4 repeat-refresh performance is already strongly confirmed live.
- Market fallback instrumentation is already in place, but not yet exercised because the user’s later runs all showed successful Yahoo market data.
- New immediate validation target is whether `ARM` (or another issuer that was previously rate-limited) stops hitting `feed_error` as often after the feed retry patch.

Best next validation target:
- Have the user run another SEC refresh and inspect `ARM` diagnostics.
- Interpret results as follows:
  - If `ARM` now gets past `feed_error` and parses or reuses Form 4 history, the patch helped and we can decide whether document-level fetches need similar treatment later.
  - If `ARM` still ends in `feed_error`, then the remaining issue is probably broader SEC rate-limit behavior, and the next Claude contribution should be about the smallest safe escalation path: retry tuning, lower fetch concurrency, or a feed-level cooldown/cache.

If you want to help on the next round, the most useful Claude contribution would be:
- analyze whether the next SEC resilience step should be:
  1. lower parallelism / pacing for ownership document fetches,
  2. a short per-CIK cooldown cache after feed 429s,
  3. broader retry logic for document fetches too,
but only if the new feed retry still leaves ARM in `feed_error`.
