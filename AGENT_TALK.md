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

Root cause is table SELECTION, not row filtering.

`extract_principal_holders()` calls `pd.read_html(html_text, match="Principal and Selling Stockholders")`. pandas' `match=` does a substring search across a table's full text, and the prospectus table-of-contents contains that exact phrase as a row (paired with a page number). So the ToC table is matched and scored by `_table_score()` alongside — or instead of — the real stockholder table, because the scoring keywords ("principal", "beneficial", "stockholder", "owner", "voting") also appear in ToC section titles. That produces the page-number "holders" (133, 138, 156) seen in the ALAB diagnostics.

The spacer-table path (`_extract_holders_from_spacer_table`) is not the culprit — it already requires an exact `"name of beneficial owner"` header match and a share value `> 1000`.

Requested fix, in `extract_principal_holders()` / `_table_score()`:

1. Before scoring, drop any candidate table that has no cell with a numeric value > 1000 anywhere in it. Real ownership tables always contain six/seven-figure share counts; ToC tables only contain page numbers.
2. Keep the existing keyword scoring as a secondary signal, applied only to tables that pass the numeric-value filter.
3. Leave `_is_placeholder_holder` row filtering as-is — it's a reasonable secondary net, not the primary fix.

Separately: `early_release_pct` showing `null` is likely NOT a parser bug — `_find_section_window` already uses `after=3000` and the percent regex looks correct against current code (tests in `tests/test_sec.py` and `test_sec_fixes.py` confirm this passes on isolated HTML). Before touching that logic, re-run "Refresh from SEC now" for ALAB to rule out a stale `company_snapshots` row from before these fixes were deployed — `fetch_latest_snapshots()` always serves the last-written row via `MAX(id)`, so an old snapshot will keep showing old bad data until a fresh live refresh runs.

Next step: implement the numeric-value table filter above, redeploy, trigger a live refresh for ALAB, then re-pull `ALAB_diagnostics.json` to confirm both holders and `early_release_pct` before marking this done.
