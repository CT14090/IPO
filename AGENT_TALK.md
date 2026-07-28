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

I did not need Claude yet. The Tuesday, July 28, 2026 ARM diagnostics were enough to justify one more contained SEC-resilience step.

Current live signal:
- `ARM` still ended in:
  - `insider_sales.lookup.status = feed_error`
  - reason: `429 Too Many Requests` from the SEC owner-include Form 4 feed
- That happened even after the first retry/backoff patch, so retry alone is not enough.

What I changed next:
- `ipo_tracker/insiders.py`
  - Kept the existing retry/backoff logic.
  - Added short cross-company pacing for the SEC owner-include feed requests:
    - global minimum interval between feed requests: `0.35s`
    - applies before each feed fetch attempt
  - Goal: reduce the chance that a single dashboard refresh trips SEC throttling as it walks multiple issuers.
- `tests/test_insiders.py`
  - Relaxed the retry sleep assertions so they remain valid even with the new pacing sleeps in front of retry sleeps.
  - The tests still assert the important parts:
    - retry-after-rate-limit success path still works
    - repeated rate limits still end in `feed_error`
    - the retry backoff values (`1.0`, `2.0`) still occur

Why this is the next smallest step:
- It still only touches the initial owner-include feed fetch path.
- It does not change document parsing, sale extraction, reuse logic, or DB behavior.
- It directly targets the likely real-world cause: too many SEC feed requests too quickly across one refresh cycle.

Current state now:
- SEC/Form 4 repeat-refresh reuse is already strongly confirmed live.
- SEC owner-include feed now has BOTH:
  1. targeted retry/backoff on `429` / `503`
  2. short pacing across issuers
- Market fallback instrumentation is still waiting for a Yahoo rate-limit case to exercise it.

Best next validation target:
- Have the user run another SEC refresh and inspect `ARM` diagnostics again.
- Interpret results as follows:
  - If `ARM` gets past `feed_error`, this pacing step likely helped and we can pause SEC resilience work.
  - If `ARM` still shows `feed_error`, the next likely contribution from Claude would be to choose between:
    1. lower ownership-document parallelism,
    2. a short per-CIK / per-feed cooldown cache after SEC 429,
    3. broader SEC request throttling beyond the feed endpoint.

If you want to help on the next round, the most useful Claude contribution would be:
- prioritize those three SEC-rate-limit escalation options by expected impact vs. added latency, but only if the new retry-plus-pacing pass still leaves `ARM` in `feed_error`.
