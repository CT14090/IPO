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

Answering both open questions from the last handoff.

### 1. Issuer to validate the positive-data path
Use RDDT — it's already on the watchlist (CIK 1713445), no need to add a new company.

- IPO date 2024-03-21, 180-day lock-up → unlock ~2024-09-17. That's well over a year in the past relative to the app's real-world "today," so Reddit insiders have had ample time to file post-unlock Form 4 sales.
- Public filings confirm real Form 4 sale activity exists for RDDT insiders after unlock (e.g. Chief Legal Officer Lee Benjamin Seong, CAO Michelle Reynolds — both selling under Rule 10b5-1 plans, visible via SEC EDGAR / secform4.com / openinsider.com).
- Note: there's also at least one Form 144 (co-founder Christopher Slowe) — Form 144 is a notice of intent to sell, not a completed Form 4 sale, so it won't and shouldn't show up in `insider_sales`. Don't treat a Form 144 hit as evidence of a parser bug if it's absent from the Form 4 list.

Recommended validation step: run a live refresh against RDDT specifically and confirm `insider_sales` comes back non-empty with a transaction dated on/after 2024-09-17.

### 2. Zero-state wording
Keep the distinction you already have. The current company-card caption — "No post-unlock Form 4 sale transactions were parsed for this issuer yet" — already says *parsed*, not *exist*, which is the correct hedge. Don't change that copy.

One gap: the Overview table just shows a bare `0` in the "Post-Unlock Form 4 Sales" column with no equivalent caveat. Consider a hover tooltip or footnote on that column clarifying it reflects "parsed," not "confirmed none exist" — otherwise a `0` there reads more confidently than the card's wording intends.

### Status
Blocked-on-my-end item is now unblocked: RDDT is the concrete example to test against instead of waiting for a lucky match.
