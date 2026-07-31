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

## Codex Handoff — 2026-07-31

ARM ownership-denominator extraction and RDDT class-row cleanup are now patched locally on `main`.

What changed
- In `ipo_tracker/sec.py`:
  - `_extract_prospectus_shares_outstanding(...)` now recognizes explicit label-first denominator phrases such as:
    - ARM-style `Ordinary shares to be outstanding upon completion of this offering ...`
    - RDDT-style `Class A, Class B, and Class C common stock to be outstanding after this offering ...`
  - `_derive_offering_shares_outstanding(...)` now prefers explicit prospectus text before falling back to holder-percent derivation.
  - `_promote_embedded_header_rows(...)` now absorbs follow-on class-label/unit rows into the promoted header, which targets RDDT-style mixed Class A / Class B tables.
  - `_is_plausible_holder_name(...)` now rejects bare class-label rows such as `Class A`, `Class B`, and `Shares`.

Targeted local validation completed
- `python -m unittest` passed for the focused ownership cases covering:
  - derived denominator fallback
  - explicit ARM prospectus denominator preference
  - conservative null tracked-holder percentage for overlap
  - RDDT-style class-row header promotion
  - class-label holder-name rejection
  - label-first prospectus denominator extraction

Important safety outcome
- This patch does **not** loosen the overlap / foreign-issuer safeguards.
- It only improves the denominator source priority and the RDDT header cleanup path.
- Additional non-null tracked-holder percentages were not forced in this pass.

Next live validation target
1. Refresh `ARM` and confirm the ownership block now shows a non-null offering-date denominator sourced from prospectus text.
2. Refresh `RDDT` and confirm `principal_holders` no longer contains `Class A` / `Class B` header-row artifacts.
3. If both look clean, then evaluate whether any additional non-null tracked-holder percentages are now safe to surface.
