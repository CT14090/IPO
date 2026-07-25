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

## Claude Response — 2026-07-25

### Confirmed working from screenshot

- Lock-up conditions panel: ✅ Early release Yes, Earnings trigger Yes,
  8-K amendment date showing, Open 8-K amendment button present
- Market context panel: ✅ IPO price $62.03, current price, % from IPO,
  30D avg volume, market cap all rendering
- Feature 7 (yfinance) and structured lockup_conditions UI both confirmed live

### One number to fix: % from IPO shows +37% but should be negative

IPO price is $62.03. Current ALAB price is ~$29. That is approximately -53%,
not +37%. The sign is inverted. In market.py, check the price_change_pct
calculation. It should be:
price_change_pct = (current_price - ipo_price) / ipo_price \* 100
If current_price and ipo_price are being swapped anywhere, or if
ipo_price is being read from the wrong history row, that would cause
a positive result. Most likely the history() call for the IPO date is
returning a later date's price (post-split or post-run-up) rather than
the actual first trading day close of ~$36. Verify what hist["Close"].iloc[0]
actually returns for ALAB — it may be pulling the wrong row.

### Principal stockholder table — root cause identified from raw HTML

The ALAB table has this structure:

- Row 1 header: "Shares Beneficially Owned Prior to this Offering" with colspan=6,
  then "Shares of Common Stock Being Offered" with rowspan=2,
  then "Shares Beneficially Owned Following this Offering" with colspan=6
- Row 2 header: "Name of Beneficial Owner" | "Shares" | "%" | "Shares" | "%"
- Data rows: 21 <td> cells each, mostly empty spacer cells between values

pandas.read_html sees 21 columns with duplicate/empty names and cannot map
them. The \_flatten_rowspans fix does not help here because the problem is
colspan on headers, not rowspan on data cells.

Fix needed in sec.py — replace the generic \_read_html_tables approach for
principal holders with a targeted lxml parser that:

1. Finds the table containing "Beneficial Owner" or "Principal" in any header cell
2. Skips all <td> cells where width="1%" (these are pure spacers — every data
   row has them between the real value cells)
3. Reads only the non-spacer cells in order: name, shares_prior, pct_prior,
   shares_offered, shares_after, pct_after
4. Maps them to: holder, shares (use shares_prior), percent (use pct_prior)

The spacer pattern is consistent: every real value cell is preceded and followed
by a width="1%" empty td. So for each data row, extract only td elements where
width != "1%" and the parent tr has no page-break-inside style that marks it
as a header row.

Specifically in discovery.py / sec.py, add this function:

def \_extract_holders_from_spacer_table(html_text: str) -> list[dict]:
"""
Parse SEC principal stockholder tables that use width=1% spacer <td>
cells between actual data cells (common in EdgarOnline/Donnelley filings).
"""
try:
import lxml.html as lh
except ImportError:
return []

    root = lh.fromstring(html_text)
    # Find table with a header cell containing "Beneficial Owner"
    target_table = None
    for table in root.xpath(".//table"):
        header_text = " ".join(table.text_content().split()).lower()
        if "beneficial owner" in header_text or "principal stockholder" in header_text:
            target_table = table
            break
    if target_table is None:
        return []

    results = []
    for tr in target_table.xpath(".//tr"):
        # Skip header rows (contain <b> tags or header keywords)
        cells = tr.xpath("td|th")
        if not cells:
            continue
        row_text = " ".join(c.text_content().strip() for c in cells).lower()
        if any(kw in row_text for kw in [
            "name of beneficial", "shares beneficially", "being offered",
            "5% stockholder", "named executive", "directors and executive"
        ]):
            continue

        # Extract only non-spacer cells (width != "1%")
        value_cells = [
            c.text_content().strip()
            for c in cells
            if c.get("width") != "1%" and c.text_content().strip()
        ]
        if len(value_cells) < 2:
            continue

        holder = value_cells[0]
        # Skip aggregate/total rows
        if "all directors" in holder.lower() or not holder:
            continue
        # Strip footnote references like (1), (2)
        holder = re.sub(r"\(\d+\)\s*$", "", holder).strip()

        shares = None
        pct = None
        if len(value_cells) > 1:
            raw = value_cells[1].replace(",", "").replace(" ", "")
            if raw.replace(".", "").isdigit():
                shares = int(float(raw))
        if len(value_cells) > 2:
            raw = value_cells[2].replace("%", "").replace("*", "0").strip()
            try:
                pct = float(raw)
            except ValueError:
                pass

        if holder and (shares or pct):
            results.append({"holder": holder, "shares": shares, "percent": pct})

    return results

Then in extract_principal_holders(), try \_extract_holders_from_spacer_table()
first and only fall back to the pandas path if it returns nothing.

### Discovery entity resolution

Still showing Unknown/— for all rows. The fix I described previously still
applies: in \_search_efts(), after meta = company_index.get(cik, {}), add:
if not meta:
profile = fetch_submission_profile(cik)
name = profile.get("title") or entity_name or f"CIK {cik}"
ticker = profile.get("ticker") or None
else:
name = meta.get("title") or entity_name or f"CIK {cik}"
ticker = meta.get("ticker") or None

fetch_submission_profile() already exists in discovery.py — it just is not
being called from the EFTS code path.

Also: the Form column is blank in the Discovery table. The form_type field
from EFTS \_source is present — check that it is being passed through in
DiscoveryCandidate and rendered in the dataframe column.

### Regression tests

Still missing for all 5 fixes. tests/test_sec_fixes.py needs to be created.
The complete file was provided as an EOF block earlier in the conversation.

### Updated priority order

1. Fix % from IPO sign error in market.py (5-minute fix, wrong sign showing)
2. Fix Discovery entity resolution in \_search_efts() (wire in fetch_submission_profile)
3. Fix Form column blank in Discovery table
4. Fix principal holder extraction using \_extract_holders_from_spacer_table above
5. Add regression tests (test_sec_fixes.py)
6. Proceed to Feature 8 (confidence-based filtering)
