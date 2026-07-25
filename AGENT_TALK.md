<!-- Reminder: If the remaining work is unclear or blocked by missing live validation, it is always okay to stop coding and update this file with a targeted question for Claude instead. -->

# Agent Talk

This file is the coordination inbox between Codex and Claude for this repo.
Codex may choose to update only this .md file to further clarify questions by prompting claude instead of proceeding to code.

## Workflow

1. Codex writes its handoff message here.
2. Claude reads the message, deletes it, and writes its response.
3. Codex reads Claude's response, makes the code changes, updates `TASK_BOARD.md`, deletes Claude's response, and writes the next handoff message.
4. The same message also appears in chat so the user sees the live status.

## Rules

- Keep messages short, direct, and actionable.
- Prefer file references, concrete next steps, and explicit status updates.
- When a task is complete, say so clearly.
- When a task is blocked, name the blocker and the next required input.
- Delete the previous message before writing the next one so the file always contains only the current handoff.

# IMPORTANT : DO NOT DELETE ANYTHING INCLUDING THIS LINE AND ABOVE

## Codex Response — 2026-07-25

Changed in `main`:
- Discovery identity normalization now ignores `Unknown`-like SEC values and falls back to the real title/ticker fields when they exist.
- EFTS discovery now reads `form` as a fallback when `form_type` is missing, so the Discovery form column should no longer be blank when SEC exposes the alternate key.
- Added focused tests in `tests/test_discovery.py` for unknown identity handling and EFTS form fallback.

Still remaining:
- Live validation in Streamlit after refresh.
- Principal-holder extraction for the ALAB filing is still the main parser blocker.
- I still need the raw `<table>` outerHTML as plain text before I can finish that parser path precisely; I cannot inspect the attachment file directly from this toolchain.
- The market `% from IPO` value is still worth a live screenshot check before I touch the sign logic, because the current code already computes the delta in the expected direction and I do not want to flip it blindly.

Next step for Claude:
- If you can, send a refreshed screenshot of the market context panel after refresh so I can verify whether the `% from IPO` display is actually wrong.
- If you want the parser fixed next, please paste the raw table HTML into chat so I can wire the spacer-table parser without guessing.
