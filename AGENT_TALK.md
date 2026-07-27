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

## Claude Response — 2026-07-27

Full analysis of both the refresh slowdown and the RDDT zero-Form-4 issue —
they are two separate bugs but need to be fixed together, since a speed-only
fix will still validate as broken.

### 1. Why refresh is slower (ipo_tracker/insiders.py + sec.py)

- `_iter_submission_records()` fetches every archived submission fragment
  listed under `filings.files` for a CIK, on every refresh, for every
  company, with no caching (discovery.py caches equivalent SEC lookups via
  @lru_cache; insiders.py does not).
- `submissions.json` for the same CIK is fetched independently 3 times per
  company per refresh: find_latest_ipo_filing(), find_lockup_amendment_8k(),
  and fetch_post_unlock_sales() each call it separately with no sharing.
- For every surviving Form 4/4A record, _candidate_document_urls() can
  trigger up to 2 sequential document fetches (XML companion + primary),
  uncapped in count.
- Everything above runs strictly sequentially across all 5 watchlist
  companies — no concurrency anywhere in enrich_company().

### 2. Why RDDT still shows 0 Form 4 sales (real bug, not just a fetch gap)

RDDT's own lockup_conditions show has_early_release=true and
has_earnings_trigger=true: the real lock-up ends on the earlier of (i) the
3rd trading day after Q2 2024 earnings (~early August 2024) or (ii) the
180-day calendar date (Sept 17, 2024). Reddit's Q2 2024 earnings were
reported in early August, meaning the *actual* unlock was over a month
before the calendar date currently stored as `unlock_date`.

But enrich_company() in sec.py always computes:
    unlock_date = ipo_date + lockup_days   (naive calendar calc only)
and never uses has_early_release / has_earnings_trigger, even though those
are already detected and stored.

Then fetch_post_unlock_sales() filters BOTH filing_date and transaction_date
against this naive unlock_dt. Any real Form 4 sale that happened in the
~6-week window between the true earnings-triggered unlock and the naive
Sept 17 calendar date is silently discarded — regardless of whether the
archive-fragment/XML-companion fetch logic works correctly. This is very
likely why transaction_count is still 0: the fetch logic may be fine, but
it's being pointed at the wrong start date.

This matches the deferred question from the prior handoff: "whether RDDT's
early-release clause means we should eventually track a separate
effective_unlock_date instead of just the calendar unlock_date." That
deferred item appears to be the actual root cause, not a nice-to-have.

Secondary, smaller note: SALE_TRANSACTION_CODES = {"S"} only counts code "S"
(open-market sale). Worth confirming this shouldn't also include code "F"
(shares withheld for taxes on vesting) depending on what "post-unlock
insider activity" is meant to capture — not blocking, just worth a decision.

### 3. Why both need to land together

Fixing only the caching/concurrency issue makes refreshes fast but RDDT (and
any other early-release company) will still show 0 Form 4 sales. Fixing
only the date-window bug won't address the slowdown. A validation pass after
only one fix will look "resolved" on one axis and still fail on the other.

### 4. Lookback strategy tradeoff (needs a decision before implementing)

Three options for how far back to search Form 4s:
  A. Always walk full archived history unconditionally (current behavior) —
     most correct, most expensive, is the direct cause of the slowdown.
  B. Only fetch archive fragments if `recent` doesn't already cover back to
     the (corrected) effective unlock date — cheapest, but a wrong coverage
     check would silently reintroduce missed filings.
  C. Fetch archive fragments but stop as soon as enough date coverage is
     reached (early exit) — same correctness guarantee as A, avoids the
     unnecessary tail-end fetches, moderately more code than a simple cache.

Whichever is chosen, the target date it searches back to must be the
corrected effective unlock date (accounting for earnings triggers), not the
naive calendar one — otherwise a faster lookback could still land after the
real unlock and continue returning zero results.

### Suggested fix scope (both together, per current direction)
- Compute and store a distinct `effective_unlock_date` (calendar unlock vs.
  earnings-trigger-adjusted) alongside the existing `unlock_date`, and use
  effective_unlock_date as the filter boundary in fetch_post_unlock_sales.
- Memoize submissions.json per CIK within a single refresh pass, shared
  across find_latest_ipo_filing / amendment lookup / insider sales.
- Adopt lookback Option C (early-exit archive walk) unless there's a reason
  to prefer B's lower cost despite the coverage-check risk.
- Re-validate against RDDT specifically: expect nonzero transaction_count
  with at least one sale dated after the corrected effective unlock
  (~early August 2024), not just after Sept 17, 2024.

No code changed by Claude in this pass — analysis only, per current process.
