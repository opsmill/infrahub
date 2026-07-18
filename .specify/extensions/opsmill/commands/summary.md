---
description: Produce a flow-level summary of the current Claude Code session — executive summary, chronological timeline, and outcomes — written into the active feature directory next to spec.md / plan.md.
scripts:
  sh: scripts/bash/check-prerequisites.sh --json --paths-only
  ps: scripts/powershell/check-prerequisites.ps1 -Json -PathsOnly
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

Supported argument: `--since <commit|time>` to bound the summary window.
Examples:

- `--since HEAD~10` — limit the timeline to phases that began after the
  10th-most-recent commit on this branch.
- `--since 14:00` — only include phases that occurred after 2 PM local time
  in the active session.

If no argument is given, summarize the **entire live session**.

## Goal

Produce a single markdown document that lets a teammate (or future-you)
understand the *flow* of the session in under 60 seconds. The unit of
output is the working session, not any one artifact. Different
granularity from `speckit.archive` (per-feature, permanent) and
`speckit.reconcile.run` (drift-fixing).

## Operating Constraints

**STAY AT THE FLOW LEVEL.** This summary is a narrative, not a
transcript. Do **NOT** include any of the following:

- Per-tool-call narration ("called Read on X.py, then called Edit on...")
- Diffs or hunks of any size
- Line numbers
- Code snippets longer than a single line
- File-by-file change logs (those belong in PR descriptions and `git log`)
- Step-by-step reproductions of debugging
- Quotes from the conversation buffer longer than one short clause

**STRICTLY ADDITIVE.** Do not modify `spec.md`, `plan.md`, `tasks.md`,
or any source files. The only file this command writes is the session
summary itself.

**IDEMPOTENT IN SPIRIT.** A second invocation in the same session must
produce a comparable summary, not a summary of summaries. Ignore
previously generated session files when composing the new one.

## Outline

1. Run `{SCRIPT}` from repo root and parse `FEATURE_DIR` from the JSON
   output. All paths must be absolute.

   - If `FEATURE_DIR` is missing, empty, or the resolved directory does
     not exist, **fail fast** with a clear error such as:
     `No feature directory resolved from current branch — /speckit.opsmill.summary requires an active feature branch.`
     Suggest the user switch to a feature branch and re-run.

2. Parse `$ARGUMENTS` for an optional `--since <value>`. Treat the
   value as opaque — pass it through to `git log --since=<value>` if it
   parses as a date/time, otherwise treat it as a git revision and use
   `git log <value>..HEAD`. Do not attempt to interpret it any further.

3. **Gather context** for the summary, in this order of preference:

   a. The live conversation context (primary source — the actual
      session is what is being summarized).
   b. `git log` on the current branch, optionally bounded by `--since`,
      for outcomes that already landed as commits.
   c. `FEATURE_DIR/spec.md`, `plan.md`, `tasks.md` if they exist — only
      to anchor terminology, not to copy content.

   Do **not** read every changed file. Do **not** generate diffs. Stay
   at the level of "what phase of work was happening, and what did it
   produce".

4. **Compose the summary** with exactly these three sections, in this
   order:

   ### Executive Summary

   One paragraph (2–4 sentences). What was this session about? What was
   the working theme? Reading just this paragraph should answer "what
   did they spend their time on today?".

   ### Timeline

   A chronological bullet list. Each entry is a single short line in
   the form `HH:MM — <human-readable phase>`, e.g.:

   - `10:42 — investigated failing E2E test in deployments_create.py`
   - `11:05 — narrowed cause to driver init order`
   - `11:30 — applied fix and re-ran suite`

   Aim for 5–15 entries. Collapse near-duplicate phases (e.g. three
   consecutive "ran tests" lines into one). If exact timestamps are not
   recoverable, use relative ordering with no `HH:MM` prefix and a
   leading dash only.

   ### Outcomes

   A short bullet list of concrete results from the session. Reference
   paths and PRs only — no diffs. Examples:

   - Opened PR #161 (speckit-extensions cleanup).
   - Materially changed `.specify/extensions/auto/`, `tinyspec/`.
   - Decided: extensions invoke skills, not slash commands.
   - Deferred: rewriting the auto extension's hook condition DSL.

5. **Write the file.**

   - Path: `FEATURE_DIR/sessions/session-YYYY-MM-DD-HHMM.md`, where
     `YYYY-MM-DD-HHMM` is the local time at invocation.
   - Create `FEATURE_DIR/sessions/` if it does not exist.
   - If a file with the same `HHMM` already exists, append a numeric
     suffix (`-2`, `-3`, …) rather than overwriting.

6. **Print the resolved path** back to the user as the final message,
   plus a one-line reminder that the summary is intentionally
   high-level and the conversation transcript / `git log` remain the
   sources of truth for detail.

## Quality Bar

A reader who was not in the session should, after under 60 seconds with
the document, be able to answer:

- What was the session trying to accomplish?
- What was the rough order of work?
- What concretely shipped, what was decided, what was deferred?

If the draft cannot pass that bar, tighten it before writing. If it
exceeds ~80 lines of markdown, you are too detailed — cut.
