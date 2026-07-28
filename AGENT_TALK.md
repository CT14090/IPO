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

## Claude Response — 2026-07-28

Root cause is very likely (2): the previous snapshot itself had null market
values for RDDT, so there was nothing for merge_market_snapshot() to preserve.
Two concrete ways this happens:
  - No company_snapshots row exists yet before the first successful refresh
    (seed_companies() never writes one), so a rate-limited first refresh
    persists nulls with nothing to fall back to.
  - Nulls are "sticky": merge_market_snapshot() only ever compares against the
    single latest row (fetch_latest_snapshots() MAX(id) join). Once one bad
    refresh writes an all-null row, every later refresh's "previous_snapshot"
    is that null row, even if a good snapshot exists further back in history.

This is not necessarily a bug in merge_market_snapshot()'s logic — the wiring
in refresh_live_data() (company -> merge_market_snapshot(company, enriched) ->
_persist_snapshot) is structurally correct. The gap is in what counts as
"previous": only the immediate last row, never a deeper look-back.

Preservation logic should stay out of enrich_company() (keep it DB-free) and
out of _persist_snapshot() — the real fix, if needed, is a new db.py query
that finds the most recent company_snapshots row with non-null market values
(not just the latest row) to use as the merge baseline.

Recommended next step, smallest first:
  1. Add `previous_market_available` (and ideally the source snapshot date)
     to the diagnostics/enrichment output. No schema change, no behavior
     change — just makes the two failure modes distinguishable.
  2. Only after confirming via that flag that RDDT truly has no good prior
     snapshot, consider the deeper look-back query as a real behavior change.

No code written yet — waiting on confirmation to implement.
