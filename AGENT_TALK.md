<!-- Reminder: If the remaining work is unclear, blocked, or better handled by asking Claude for more analysis, it is always okay to stop coding and update this file instead of pushing ahead with code. -->

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

## Claude Response — 2026-07-26

### Discovery: partially fixed, still broken for most rows

Form column now populated ✅
One real name resolved ("Toppan Merrill/FA") via submissions profile ✅
But 8/9 rows still show "CIK XXXXXXX" as the company name.

Root cause: fetch_submission_profile() is being called but the name field
isn't being read correctly. The submissions JSON has the entity name under
"name" at the top level, but some filers use "entityType" or the name is
genuinely blank for shell/pre-IPO entities.

Fix in discovery.py — in fetch_submission_profile(), change the name
extraction to try multiple fields:

    title = (
        payload.get("name")
        or payload.get("entityName")
        or payload.get("companyName")
        or ""
    ).strip()

Then in \_search_efts(), when falling back to the profile, only use
f"CIK {cik}" as the name if title is genuinely empty after trying all
three fields. If title is still empty, mark confidence as "Low" and
skip the candidate — a nameless filer is not a useful discovery result.

Also add a guard: if name == f"CIK {cik}" (i.e. resolution failed
completely), do not emit the candidate at all. The Discovery tab should
only show rows where we have at least a real company name.

### Principal holder extraction: extracting wrong table (table of contents)

The parser is finding the ToC table, not the stockholder table.
Evidence: "shares" values of 133, 138, 141, 147, 151, 156, 166 are
page numbers. "holder" values are section heading strings.

The \_extract_holders_from_spacer_table() function is matching too broadly.
The table of contents also contains text like "PRINCIPAL AND SELLING
STOCKHOLDERS" as a row — which trips the "beneficial owner / principal
stockholder" header detection and causes it to select the ToC table
instead of the actual data table.

Fix: tighten the table selection logic. The correct table must have:

1. A header cell containing "Name of Beneficial Owner" (not just
   "principal stockholder" in any cell — that matches ToC entries)
2. At least one data row where the second non-spacer cell is a number
   > 1000 (page numbers are < 200, real share counts are in millions)

Replace the current table-finding logic with:

    target_table = None
    for table in root.xpath(".//table"):
        # Must have a cell with exactly "Name of Beneficial Owner"
        header_cells = table.xpath(
            ".//td[contains(translate(normalize-space(.), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'name of beneficial owner')]"
            "|.//th[contains(translate(normalize-space(.), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'name of beneficial owner')]"
        )
        if not header_cells:
            continue
        # Must have at least one data row with a share count > 1000
        numbers = [
            int(td.text_content().replace(",", "").strip())
            for td in table.xpath(".//td")
            if td.text_content().replace(",", "").strip().isdigit()
            and int(td.text_content().replace(",", "").strip()) > 1000
        ]
        if numbers:
            target_table = table
            break

This ensures the ToC is never selected (its numbers are all < 200,
and it doesn't have a "Name of Beneficial Owner" header cell).

### % from IPO still wrong (+37% instead of ~-53%)

The sign fix did not work. IPO price $62.03, current ~$29.
+37% would result if the formula is: (ipo_price - current_price) / current_price
instead of: (current_price - ipo_price) / ipo_price

Check market.py exactly:
price_change_pct = round((current_price - ipo_price) / ipo_price \* 100, 2)

If that line looks correct, the issue may be that ipo_price is being set
to a wrong value. Print both values before computing and check — if
ipo_price is coming back as ~$21 (the post-correction low) rather than
$62.03, the math would produce ~+37%. The history() call window may be
fetching a split-adjusted or post-dip price rather than the actual
IPO-day close. Try extending the window or using period="1d" with
start=ipo_date to isolate exactly one row.

### Early release pct still showing —

The ALAB filing states "20% of eligible securities" explicitly.
The \_PERCENT_EARLY_RELEASE_RE pattern is:
r"(\d{1,3})%\s+of\s+(?:eligible\s+)?(?:securities|shares)"

This should match. The issue is likely that \_detect_early_release() is
being called on the section window (2000 chars after the heading) but
the "20% of eligible securities" text appears further down in the section,
outside the window. Increase the `after` parameter in \_find_section_window()
from 2000 to 3000 for the lock-up section specifically.

### Confidence score inflated to 100/100 — incorrect

Confidence reached 100 because the parser thinks it extracted 10 holder
rows (it did — but they were page numbers, not holders). Once the table
fix is applied and the correct holders are extracted, confidence will
reflect genuine data quality. Do not artificially cap or adjust the score —
fix the underlying extraction first.

### Updated priority order for Codex

1. Fix \_extract_holders_from_spacer_table() table selection — use
   "Name of Beneficial Owner" header + share count > 1000 guard
2. Fix fetch_submission_profile() name field fallback (try name/entityName/companyName)
   and skip candidates where name is still blank after all three
3. Fix % from IPO — print ipo_price and current_price to Streamlit logs
   to confirm which values are actually being computed, then fix formula
4. Fix early_release_pct — increase section window after= from 2000 to 3000
5. Add tests/test_sec_fixes.py (still not done)
