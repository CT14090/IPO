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
- Latest confirmed work: discovery entity resolution fallback and structured lock-up conditions panel were added to `main`.
- Remaining open item: live principal stockholder table extraction on the ALAB filing still needs deeper debugging.
- Next likely action: inspect the real filing table HTML and then update the parser/tests accordingly.
