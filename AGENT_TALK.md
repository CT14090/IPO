# Agent Talk

This file is the coordination inbox between Codex and Claude for this repo.

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

## Current State
- Repo: `CT14090/IPO` on GitHub, default branch `main`.
- Live app: Streamlit Cloud deployment is working at `https://mpwbeuzncs4bjcr5sh4mni.streamlit.app/`.
- Current repo posture: remote-first on `main`; commits are being published directly to GitHub with explicit commit messages.
- Latest task-board commit: `a76fb0b011764170580ffffa682c7bdb6923afb5` updated `TASK_BOARD.md` after live screenshot validation.
- Latest coordination-file commit before this update: `032d8c1ac310aa99784d54d032d1931b1f41d4dd` created this agent talk file.

- Confirmed done in code and live screenshots:
  - Confidence scoring exists in `ipo_tracker/sec.py` and is stored/displayed via `ipo_tracker/db.py` and `app.py`.
  - Schema resilience exists via `_ensure_column` and `_row_value`; stale snapshot rows no longer crash the app.
  - Greenshoe / overallotment false-positive suppression works; live ALAB unlock date is `2024-09-15`.
  - Dual-trigger / early-release detection works; ALAB notes show both `Early release clause detected` and `Earnings-linked trigger present`.
  - Post-IPO 8-K amendment scanning works; ALAB notes show `Updated by 8-K filed 2024-08-06`.
  - Cover-page IPO date parsing works; ALAB IPO date is parsed from filing text as `2024-03-20`.
  - Discovery tab exists and live EFTS primary-path results appear with `EFTS full-text match` in the Why column.

- Implemented in `main`, pending live validation / surfacing:
  - `lockup_conditions` is persisted in snapshot rows and rendered as a structured expander panel in company cards.
  - Discovery entity resolution now falls back from `company_tickers_exchange.json` to `data.sec.gov/submissions/CIK{cik}.json` so names can populate even when the ticker index misses a CIK.
  - The `Discovery` tab still needs a live redeploy check to confirm the fallback fully fixes the `Unknown` / blank ticker issue for current EFTS hits.

- Remaining open bugs / follow-up:
  - Principal stockholder table extraction still fails on the live ALAB filing; the card still says `Principal stockholder table not extracted cleanly`.
  - Discovery entity resolution was previously showing `Unknown` / `—` across rows; the code fix is in, but it needs live validation after redeploy.
  - Principal-holder extraction likely needs the actual filing table HTML or a fetch of the exact ALAB table structure before a reliable parser fix can be landed.

- Tests that exist now:
  - `tests/test_sec.py` covers lockup extraction, holder cleanup, and confidence scoring.
  - `tests/test_discovery.py` covers EFTS/RSS candidate parsing and the new submissions-profile fallback path.
  - Regression coverage still does not exist for greenshoe disambiguation, early-release detection, 8-K amendment detection, cover-page IPO date parsing, or rowspan-flattened holder extraction against the real filing shape.

- Planned next actions if nothing else interrupts:
  - Redeploy Streamlit and confirm the Discovery tab now shows real names/tickers where available.
  - Confirm the new structured `Lock-up conditions` expander is visible in company cards.
  - Debug the ALAB principal-holder table using the actual table HTML from the filing.
  - Then continue down `TASK_BOARD.md` order, starting with yfinance enrichment only after the live validation gaps are closed.
