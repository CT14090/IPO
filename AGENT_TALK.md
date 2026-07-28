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

Current state after the latest work on Tuesday, July 28, 2026:

1. The SEC/Form 4 feed issue is already fixed and live-confirmed.
- Problem was not the issuer logic anymore; it was SEC throttling on the owner-include Atom feed for names like `ARM`.
- Codex fixed that with:
  - bounded retry/backoff for `429` and `503`
  - short cross-company pacing between feed requests
- Live proof already seen in ARM diagnostics:
  - `insider_sales.lookup.status = sales_parsed`
  - `feed_entries = 29`
  - `candidate_filings = 28`
  - `xml_documents = 28`
  - `transactions_parsed = 39`

2. We have now moved on to the next requested item: principal-holder parsing quality.
- Commit already on `main`:
  - `c867568` `Improve principal holder parsing for embedded header tables`
- What that parser change does:
  - recognizes more holder-header placeholder phrases such as `Name of Beneficial Shareholder`
  - treats `Number` as a shares-like column when the table embeds minimal subheaders
  - avoids overwriting a stronger numeric shares/percent value with a later weaker duplicate
  - promotes embedded multi-row header rows into real DataFrame columns before canonicalizing holder rows
- This specifically targets SEC prospectus tables like ARM where the real `Name / Number / Percent` labels appear in the first body rows rather than as clean `<th>` headers.

3. I also added regression coverage so this work is not only code-without-guardrails.
- New commit on `main`:
  - `6de89b3` `Add regression test for embedded principal holder headers`
- The new unit test uses an ARM-shaped simplified table with:
  - a top row describing pre/post offering blocks
  - a second row with `Name of Beneficial Shareholder | Number | Percent | ...`
  - a `SoftBank Group Corp.` data row
- Expected result in the test:
  - parser returns one real holder row
  - `holder = SoftBank Group Corp.`
  - `shares = 1,025,233,999`
  - `percent = 100.0`

4. Docs are updated too.
- `TASK_BOARD.md` now records that:
  - the embedded-header parser improvement is implemented in `main`
  - the next live validation target is ARM `principal_holders`
- If Claude needs to inspect project status, the board is up to date.

What remains right now:
- We still do NOT have live evidence yet that ARM `principal_holders` is populated after this parser change.
- The next validation target is straightforward:
  - refresh SEC data
  - open ARM diagnostics
  - inspect whether `principal_holders` is still `[]` or now contains real rows

What Claude would be most useful for next, only if the live ARM validation still fails:
- analyze the exact remaining ARM holder-table structure and explain why the promoted-header path still misses it
- otherwise no further analysis is needed before the next validation step
