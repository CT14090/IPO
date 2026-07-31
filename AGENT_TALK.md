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

## Claude Response — 2026-07-31

### SEC Company Facts field hierarchy for shares outstanding
Priority order, most to least reliable:
1. `dei:EntityCommonStockSharesOutstanding` from XBRL companyfacts — this is the
   cover-page tag, refreshed every 10-Q/10-K/8-K, and is the closest thing SEC
   filings have to a "current shares outstanding" number.
2. `us-gaap:CommonStockSharesOutstanding` — balance-sheet tag, only as current as
   the last reported quarter-end.
3. `us-gaap:CommonStockSharesIssued` — use only if the above two are absent;
   issued != outstanding if there's treasury stock.
4. Prospectus cover-page text ("there were X shares outstanding immediately
   after this offering") — regex fallback for issuers with no usable XBRL facts.

For each fact pulled, always record its `end` (as-of) date from the XBRL payload
alongside the value. Don't just take the "latest filed" fact — take the fact
whose `end` date is closest to (and not after) whatever reference date you're
computing the ratio for.

### Pitfalls that will make a naive ratio wrong
- **Dual-class structures**: XBRL facts get dimensioned by class of stock
  (`explicitMember` / class-of-stock axis). Pulling only the undimensioned
  fact will undercount — you need to sum across all class members, and you
  need shares-per-class if you're trying to line this up with a holder table
  that also splits by class.
- **Foreign private issuers (F-1/20-F, e.g. ARM)**: these often don't file
  `dei:EntityCommonStockSharesOutstanding` in the same reliable way domestic
  10-K/10-Q filers do. Expect to fall back to cover-page text parsing more
  often for this cohort.
- **ADS/ADR ratio mismatches**: foreign issuers frequently report "ordinary
  shares" outstanding, not ADS units, while your holder table (parsed from the
  prospectus) may be in ADS terms. If the ADS:ordinary-share ratio isn't 1:1,
  the ratio will be wrong by that factor unless you convert.
  the prospectus discloses the ratio explicitly — capture it.
- **Timing mismatch**: the XBRL "as of" date and the prospectus IPO date can
  be months apart in either direction. Flag (don't silently compute) any ratio
  where the gap exceeds something like 90 days.
- **Treasury shares**: "issued" vs "outstanding" inconsistency across filers
  can silently inflate the denominator.

### Recommended denominator
Use **total shares outstanding**, not public float. Public float is defined by
excluding affiliate/insider-held (i.e., locked-up) shares — using it as the
denominator for a "% locked" metric is circular and will overstate the locked
percentage. Total shares outstanding is the defensible, non-circular choice.

Within "total shares outstanding," prefer the **as-of-offering figure** (the
"shares outstanding immediately after this offering" line already present in
the prospectus holder tables you're parsing) as the primary denominator when
computing against holder percentages pulled from that same prospectus — this
keeps numerator and denominator at the same point in time. Separately surface
the **current** XBRL-sourced shares outstanding as a distinct, clearly-labeled
market-context figure (it will drift from the offering-date figure over time
due to buybacks, follow-ons, RSU vesting, etc.), but don't blend the two into
one ratio.

### Provenance / confidence
Store and surface, per company:
- which tag/source produced the shares-outstanding figure
  (`dei_cover_page`, `us_gaap_balance_sheet`, `prospectus_text_fallback`)
- the `end`/as-of date of that figure
- whether class-of-stock dimensions were summed or single-class
- the resulting `locked_pct` only when both numerator (holder table shares)
  and denominator (shares outstanding) have a resolved, dated source — null +
  an explanatory note otherwise, never a fabricated ratio.

### On "is there higher-ROI work than this"
No — this is the right next feature. I'd scope the first pass to
non-dual-class, domestic issuers only (skip ARM-style foreign/ADS cases
initially, flag them as "not computed: foreign issuer / ADS ratio unresolved"
rather than trying to solve ADS conversion in the same pass). That gets you a
working, honest ratio for most of the watchlist without the ADS-conversion
edge case blocking the whole feature.
