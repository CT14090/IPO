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

State after the user's latest live validation:
- `RDDT` is now confirmed correct live.
- Effective unlock date resolved to `2024-08-09` instead of calendar `2024-09-17`.
- Live diagnostics show `insider_sales.lookup.status = sales_parsed` and 453 parsed post-unlock sale transactions across 53 unique filings.
- The startup `ImportError` is resolved in practice because the user is back in the app and diagnostics are working.

What I changed most recently:
- `ipo_tracker/insiders.py`
  - Kept the issuer-centric SEC owner-feed Form 4 source.
  - Added a performance pass that parallelizes ownership-document fetches for large candidate batches only.
  - Uses `ThreadPoolExecutor(max_workers=4)` when candidate filings are large (`>= 8`), while keeping small cases sequential for lower risk and more test stability.

Why this was the chosen optimization:
- The user's `RDDT` diagnostics show the real hot path clearly:
  - `candidate_filings`: 100
  - `documents_fetched`: 100
  - `xml_documents`: 100
- That means the slowdown is dominated by sequential ownership-document fetches, not by lock-up parsing anymore.
- This pass targets that exact bottleneck without changing the validated unlock logic or diagnostics structure.

What still needs validation:
- Measure whether SEC refresh time drops meaningfully from the user's reported `> 1 minute` after this parallel-fetch change is deployed.
- We do NOT need to re-prove `RDDT` correctness first unless the output changes unexpectedly.

If refresh is still too slow after this deploy, best next investigation:
- move from full re-scan behavior toward incremental reuse of already stored insider-sale history from the latest snapshot, so refreshes only fetch new Form 4 filings instead of reprocessing the entire owner-feed window every time.
- That would be the next higher-leverage optimization, but it is a more stateful change than the thread-pool pass.

Most useful next Claude contribution if needed:
- Only if refresh is still too slow after this deploy: analyze the cleanest incremental-update design for stored Form 4 history, especially how to detect 'no new filings' safely without weakening correctness.
