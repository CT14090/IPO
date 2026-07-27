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

Current state after the user's latest refresh crash report:
- The user hit a live Streamlit crash on `Refresh from SEC now` caused by `requests.exceptions.HTTPError` during `ipo_tracker/sec.py -> fetch_json(...) -> load_company_submissions(...)`.
- The traceback showed the failure happened inside `enrich_company(company)` while `app.py` was refreshing all companies sequentially.
- The existing refresh path assumed every company refresh would succeed, so a single SEC HTTP failure crashed the whole app.

What I changed just now:
- `app.py`
  - Added `import requests`.
  - Added `_describe_request_error()` to make SEC/network failures human-readable in the sidebar.
  - Changed `refresh_live_data()` to catch `requests.RequestException` per company.
  - On a per-company refresh failure, the app now:
    - records a warning message with the ticker and HTTP/network error,
    - keeps the previous snapshot for that company,
    - continues refreshing the rest of the watchlist instead of crashing the whole app.
  - Updated the sidebar refresh UI so it now:
    - shows success when all companies refreshed,
    - shows a warning summary plus per-ticker messages when one or more companies failed.

Why this was the chosen fix:
- It directly addresses the user's current blocker: the app should stay usable even if SEC temporarily rejects or rate-limits one request.
- It does not silently hide errors. Failures are now explicit and localized.
- It avoids losing already-good snapshot data for unaffected companies.
- It is low-risk relative to adding a retry/backoff layer inside every SEC fetch call without first re-validating the live failure mode.

What is still open:
- We still need the user to validate live that `Refresh from SEC now` no longer crashes the app.
- We still need to measure whether refresh time improves materially after the earlier thread-pool Form 4 fetch pass.
- If SEC HTTP failures remain common, the next candidate change is a targeted retry/backoff layer in `ipo_tracker/sec.py` and possibly a lower or adaptive Form 4 fetch concurrency.
- If refresh remains too slow even when it no longer crashes, the next higher-leverage optimization is incremental Form 4 history reuse instead of full owner-feed reprocessing on every refresh.

Most useful next Claude contribution if needed:
- If the live app still throws SEC-related warnings frequently after this change, analyze whether the better next step is:
  1. SEC request retry/backoff in `ipo_tracker/sec.py`,
  2. lower/adaptive Form 4 parallelism in `ipo_tracker/insiders.py`, or
  3. incremental snapshot-aware Form 4 refresh.
- Prioritize based on likely root cause: rate limiting vs wasted repeated work.
