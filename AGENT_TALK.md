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

I used the user's pasted `RDDT` diagnostics JSON to diagnose the first real Form 4 ingestion bug and patched it. This was not a UI-only issue.

Diagnosis:
- `RDDT` showed zero parsed Form 4 sales even though public post-unlock sale activity should exist.
- The old code in `ipo_tracker/insiders.py` only read `submissions -> filings -> recent`.
- Per SEC submissions API behavior, older filing history can move into additional JSON fragments listed under `submissions -> filings -> files`.
- `RDDT` is old enough relative to the current date that relevant post-unlock Form 4s may have fallen out of `recent`.
- The old code also assumed the listed `primaryDocument` would be directly parseable XML, but ownership filings can be HTML-backed with an XML companion document.

Code changes completed:
- Updated `ipo_tracker/insiders.py`.
  - Added submission-fragment loading from `filings.files`.
  - Added record iteration across both `recent` and archived fragment files.
  - Added XML-companion fallback when `primaryDocument` is `.htm` / `.html`.
  - Added a light content gate so only documents containing `<ownershipDocument` are parsed as Form 4 XML.
- Updated `tests/test_insiders.py`.
  - Added regression coverage for archived submission-fragment loading.
  - Added regression coverage for HTML-backed Form 4 filings that require the XML companion document.
- Updated `TASK_BOARD.md` to reflect the diagnosed ingestion gap and the patch.

Current truth state:
- The likely root cause for `RDDT` zero results has now been patched in code.
- I still have not live-validated the patched path because the local shell/runtime bridge is unavailable in this session.
- The next decisive check is a redeploy/refresh and then re-checking `RDDT` diagnostics.

Next required validation:
- Refresh the deployed app after the new commit is live.
- Inspect `RDDT` again.
- Confirm `insider_sales.summary.transaction_count` becomes nonzero.
- Confirm at least one transaction date is on or after `2024-09-17`.

Claude input is optional now. If Claude wants to add value, the best use would be reviewing whether `RDDT`'s early-release clause means we should eventually track a separate `effective_unlock_date` instead of just the calendar `unlock_date`.
