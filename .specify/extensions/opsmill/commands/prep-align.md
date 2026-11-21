---
description: Phase of the opsmill-prep workflow — check that spec.md still matches the request, write alignment-check.md, and report the verdict.
---

## User Input

```text
$ARGUMENTS
```

## Outline

You run **one phase** of the `opsmill-prep` workflow: **Spec/Ask alignment check**. The workflow file (`.specify/workflows/opsmill-prep/workflow.yml`) runs the other phases as separate steps and decides when a phase is repeated, so do only what this file describes, then stop.

Nobody can answer a question during this run. Wherever a choice comes up, use your best judgment and continue.

Do not commit: the workflow commits what this phase wrote.

The user input above is the original request. The earlier phases can drift from a detailed PRD: clarifications get over-applied, scope creeps in from research, or requirements get rephrased away. This phase catches that.

The feature directory is the `feature_directory` recorded in `.specify/feature.json`.

### 1. Decide whether to run the check

The check is **only meaningful when the request is a substantive PRD**, inline or by reference. Decide in this order:

1. **The request contains one or more URLs** (Notion, Confluence, Google Doc, GitHub issue, Linear ticket, shared Markdown, PDF). Treat each URL as a likely PRD location. **Run the check.**
2. **The request itself looks like a detailed PRD** — several paragraphs with headings, bullet lists of requirements, explicit goals or non-goals, acceptance criteria, or more than about 400 characters of substantive description. **Run the check.**
3. **The request is a one-line description, a vague brief, or empty.** **Skip the check**: there is no source document to align against. The verdict is `SKIPPED`. If the request is short but still carries requirement-bearing detail, use your judgment and treat it as a PRD under rule 2.

### 2. Resolve the source PRD

- For each URL in the request, fetch its content with the harness's web fetch tool (in Claude Code: `WebFetch`) and extract the requirement-bearing sections.
- If a URL cannot be read (no web fetch tool, auth required, 404, network error), record that and fall back to the PRD content in the request itself. If neither is usable, the verdict is `SKIPPED`: write `alignment-check.md` with `⚠️ SKIPPED — source PRD unreachable`.
- Concatenate the fetched and inline PRD content into a single source PRD.

### 3. Compare the source PRD to `spec.md`

Read the current `spec.md` end to end and judge it against the source PRD. Look for **significant** drift, not stylistic differences:

- A requirement, goal, or explicit non-goal of the PRD is **missing** from the spec.
- The spec **adds** a requirement, scope item, or constraint that is not in the PRD and was not a necessary clarification.
- The semantics of a requirement **changed** (for example "users can opt out" became "admins can opt users out"; "must support 10k req/s" became "should scale").
- Acceptance criteria of the PRD are **dropped** or **softened**.
- The spec contradicts a stated PRD constraint (compatibility, deadline, dependency).

Cosmetic, structural, or expansion-of-detail differences are **not** drift. The spec may be longer and more precise, and may flesh out implicit requirements.

### 4. Write the alignment report

Write `alignment-check.md` in the feature directory, replacing an earlier one, with:

1. **Source** — the URL(s) or the inline request used as the source PRD.
2. **Verdict** — one of `✅ ALIGNED`, `⚠️ MINOR DRIFT`, `🛑 SIGNIFICANT DRIFT`, or `⚠️ SKIPPED` with its reason.
3. **Findings** — a table of `Severity | Category (missing / added / changed / dropped / contradicted) | PRD reference | Spec reference | Description`.

Do **not** correct the spec yourself. The workflow runs a remediation pass after a `SIGNIFICANT_DRIFT` verdict, two passes at most, and stops with an error when the drift remains.

**Verdict line (REQUIRED).** The **final line** of your output MUST be exactly, unwrapped:

`ALIGNMENT: <ALIGNED|MINOR_DRIFT|SIGNIFICANT_DRIFT|SKIPPED>`

The workflow reads this line to decide whether to run a remediation pass. Write the two words `ALIGNMENT: SIGNIFICANT_DRIFT` nowhere else in your output.
