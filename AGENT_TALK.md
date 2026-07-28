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

A deploy-blocking regression was found and fixed on Tuesday, July 28, 2026.

What broke:
- Streamlit failed at import time on:
  - `from ipo_tracker.sec import enrich_company`
- Root cause was not Streamlit config and not the new SEC logic itself.
- `ipo_tracker/sec.py` on `main` had become physically truncated during the last edit.
- The file ended mid-function inside `determine_effective_unlock_date(...)`, before the rest of that function and before the `enrich_company(...)` definition.
- Because the Python module was incomplete, importing `ipo_tracker.sec` failed and surfaced as the app-level `ImportError`.

What Codex did:
- compared the current broken `sec.py` with the last known-good version before the truncation
- restored the missing tail of the module while preserving the newer embedded-header principal-holder parsing changes already on `main`
- restore commit:
  - `1dfaded` `Restore truncated sec module tail`

What is restored by that fix:
- completion of `determine_effective_unlock_date(...)`
- the full `enrich_company(...)` helper
- the module can now parse/import again unless there is a separate runtime issue

Important interpretation:
- this was a file-corruption / incomplete-commit style regression
- it does NOT invalidate the earlier SEC feed retry/pacing work
- it does NOT invalidate the embedded principal-holder parser work conceptually
- it simply means the repo had a broken `sec.py` artifact that prevented any of that code from loading

Current next validation target:
1. redeploy / rerun the app and confirm import-time startup succeeds again
2. then resume the previously planned ARM holder validation:
   - refresh SEC data
   - inspect `ARM` diagnostics
   - check whether `principal_holders` is still `[]` or now populated

Only if the app starts cleanly but ARM holder rows are still empty would Claude analysis be useful again.
