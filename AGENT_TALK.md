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

Current blocker in this thread is infrastructure only: no local terminal/runtime is attached here, so no shell/file edits are possible from this task. Please continue coding in the local-enabled Codex task.

Priority order from user:
1. improve ARM offering-date denominator extraction
2. improve RDDT mixed/dual-class holder-table handling
3. only after that, revisit whether we can compute more non-null tracked-holder percentages safely

### Why ARM is first

Latest ARM diagnostics now show:

- `principal_holders` contains a single plausible row:
  - `holder = "SoftBank Group Corp."`
  - `shares = 1025233999`
  - `percent = 100`
- `notes` says `Parsed 1 principal holder rows`
- `offering_shares_outstanding` was previously null, then the parser began surfacing a single holder row, but this still needs a reliable ownership-context denominator path.
- Current desired outcome is not “make more fields non-null at any cost”; it is “derive ARM’s offering-date denominator safely enough that ownership context is trustworthy.”

There was an earlier bad intermediate parse where ARM holder rows were polluted by unrelated financial-statement columns, e.g. values like:
- `Fiscal Quarter Ended June 30, 2023 AdditionalPaid-in Capital`
- `holder = "4051"`
That means the parser has already shown it can latch onto the wrong table if heuristics are too loose.

### ARM hypothesis / likely fix area

Please inspect the ownership path in `ipo_tracker/sec.py`, especially:
- `extract_principal_holders(...)`
- `_canonicalize_holder_row(...)`
- `_extract_prospectus_shares_outstanding(...)`
- `_derive_offering_shares_outstanding(...)`
- `build_ownership_context(...)`

Working hypothesis:
- ARM’s 424B4 has enough information to derive a denominator, but our current extraction path is either:
  1. not finding the right “shares outstanding immediately after / after this offering” text, or
  2. not using the parsed single controlling-holder row correctly/safely, or
  3. still selecting the wrong nearby table/text block in some runs.

Please prefer a conservative fix:
- If prospectus text explicitly provides post-offering / immediately-after-offering shares outstanding, use that.
- If falling back to holder-row derivation, only do it when table semantics are unambiguous.
- Do not loosen logic in a way that would reintroduce the bad financial-table capture.

### RDDT issue after ARM

Latest RDDT diagnostics show mixed / dual-class contamination in holder rows, e.g. rows like:
- `holder = "Class A", shares = "Class B", percent = "Class A"`
- `holder = "Shares", shares = "%", percent = "Shares"`

And earlier ownership notes said:
- `Holder rows imply inconsistent offering-date share counts (max deviation 99.8%).`

This strongly suggests the parser is not normalizing a multi-row / multi-class holder table correctly before denominator derivation.

Desired RDDT fix:
- Improve mixed/dual-class holder-table handling so header rows and class-label rows are dropped cleanly.
- Keep class-specific columns from being mistaken for actual holder records.
- Only derive offering-date denominator when post-cleaning holder rows agree tightly enough.
- If still ambiguous, keep null rather than forcing a denominator.

### Important safety rule for phase 3

After ARM and RDDT are improved, only then revisit whether more non-null `tracked_holder_pct_of_offering` values are safe.

Please keep current conservative behavior for:
- overlapping beneficial ownership rows
- duplicate share counts suggesting overlap
- proxy / voting-control style rows
- foreign / ADS ambiguity unless denominator and holder interpretation are actually clear

ALAB’s current null tracked-holder percentage due to overlapping/duplicate rows is acceptable and should not be “fixed” by loosening safeguards unless a clearly correct de-overlap method exists.

### Suggested implementation plan

1. Re-read current ownership helpers and existing ownership regression tests.
2. Add/adjust targeted regression coverage for ARM denominator extraction first.
3. Implement ARM fix conservatively.
4. Add/adjust targeted regression coverage for RDDT mixed/dual-class table cleaning.
5. Implement RDDT fix conservatively.
6. Re-run targeted ownership tests.
7. Only then evaluate whether any additional tracked-holder percentages can be computed safely.
8. Update `TASK_BOARD.md` and replace this note in `AGENT_TALK.md` with what changed and what remains.

### Useful user-provided diagnostic facts

ARM current state:
- company: Arm Holdings plc
- ticker: ARM
- cik: 1973239
- filing form: 424B4
- filing date: 2023-09-14
- source URL: `https://www.sec.gov/Archives/edgar/data/1973239/000119312523235320/d550931d424b4.htm`
- lockup source: `Lock-Up Restrictions section: Regex match: for a period of 180 days`
- principal holders currently:
  - SoftBank Group Corp. / 1,025,233,999 shares / 100%
- current shares outstanding from company facts is already working
- the task is specifically about improving offering-date denominator extraction for ownership context

RDDT current state:
- company: Reddit, Inc.
- ticker: RDDT
- mixed header/class rows are still the key table-normalization issue
- ownership denominator previously failed due to inconsistent row-implied totals

### Infrastructure note

This handoff exists because the current Codex thread lost local runtime attachment. The issue is not with repo contents. Please continue in the local-enabled task.
