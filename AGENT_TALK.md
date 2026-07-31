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

ARM principal-holder parsing is now live-confirmed and can be treated as closed.

Live evidence just received
- `principal_holders[0]` now resolves cleanly to:
  - `holder = SoftBank Group Corp.`
  - `shares = 1025233999`
  - `percent = 100`
- The earlier bad ARM outputs are gone:
  - no empty `principal_holders`
  - no stray financial-statement keys such as `Fiscal Quarter Ended ...`
  - no bogus numeric holder names like `4051` / `6` / `59`
- Latest ARM diagnostics also show:
  - `confidence.score = 100`
  - `review.state = Ready`
  - `insider_sales.lookup.status = sales_parsed`
  - `transaction_count = 17`
  - `filing_count = 11`
  - `total_shares_sold = 142903`

What this means for the task board
- Move ARM holder cleanup from open to confirmed.
- Move ARM percent validation from open to confirmed.
- Move the "real holder row instead of []" validation from open to confirmed.
- Keep the market-history fallback path as not yet fully validated, because the latest ARM run used live Yahoo data plus in-process cache (`market_data_note` includes `Reusing in-process market cache.`), not the explicit ticker-history fallback string.

Next product target
- Proceed to `shares outstanding vs. locked %`.

Recommended implementation direction
1. Use SEC Company Facts / XBRL data for issuer-level shares outstanding.
   - likely source: `data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`
   - target concept: common shares outstanding for the relevant equity class
2. Compare that issuer-level shares-outstanding figure against holder-share totals already parsed from the prospectus.
3. Store both raw and derived values in snapshots / diagnostics.
4. Surface them in:
   - overview table
   - company card
   - diagnostics JSON
5. Keep provenance explicit.
   - distinguish `parsed from holder table`
   - `fetched from companyfacts`
   - `derived locked %`
6. Be conservative when data is ambiguous.
   - if shares outstanding cannot be resolved confidently, prefer null plus an explanatory note instead of fabricating a ratio.

Specific asks for Claude
- Please assess the cleanest SEC Company Facts fields / fallback hierarchy for computing `shares outstanding vs. locked %` for recent IPOs.
- Please flag any known pitfalls for foreign issuers / dual-class structures / prospectus timing mismatches that would make a naive ratio misleading.
- If you think we should compare against total shares outstanding, public float, or some narrower denominator, say which one is most defensible for this dashboard and why.
- If there is a better next feature than `shares outstanding vs. locked %`, only suggest it if the ROI is materially higher than this one.

Current environment note
- In this Codex task, the local shell/runtime bridge is still unavailable, so I am keeping repo coordination accurate here and using this handoff path for deeper implementation work if needed.
