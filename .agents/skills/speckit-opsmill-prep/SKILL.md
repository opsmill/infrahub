---
name: speckit-opsmill-prep
description: Run the speckit preparation phases end-to-end — specify, plan, critique,
  tasks — making all decisions autonomously. Stops before implementation.
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: github-spec-kit
  source: opsmill:commands/prep.md
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

You are running the **preparation phases of the speckit pipeline** end-to-end. The user's input (above) is the feature description that will seed the specification phase.

This skill is the prefix of `speckit-opsmill-auto`: it covers Specify → Plan → Critique → Tasks → Spec/Ask Alignment Check and **stops before implementation**. Use it when you want a feature fully designed and broken down into a `tasks.md` ready for review, but you do not want the agent to execute the tasks autonomously.

Execute every phase below **in order**, making all decisions autonomously. Do not stop to ask the user for input between phases — if a phase requires choices (e.g., clarification questions in specify, research decisions in plan), use your best judgment and proceed. The user expects a hands-off, one-shot execution up through `tasks.md`.

After **each phase**, invoke the `speckit-checkpoint-commit` skill to commit the artifacts produced by that phase before moving on.

> Each phase below is executed by invoking the named skill (e.g. via the agent's Skill tool). Skills are agent-agnostic, so this workflow runs identically across any harness that supports skill discovery — not only those exposing speckit slash commands.

### Phase 1 — Specify

Invoke the `speckit-specify` skill with the user's feature description (`$ARGUMENTS`).

- Complete the full specify workflow: generate a short name, create the spec directory, write `spec.md`, run quality checks.
- If clarification questions arise, answer them yourself based on context and best judgment — do **not** pause for user input.
- Commit the spec artifacts.

### Phase 2 — Plan

Invoke the `speckit-plan` skill.

- Complete the full plan workflow: research unknowns, generate `plan.md`, `research.md`, `data-model.md`, API contracts, `quickstart.md`.
- Make all design decisions autonomously.
- Commit the plan artifacts.

### Phase 3 — Critique

Invoke the `speckit-critique-run` skill.

- Run the dual-lens (Product + Engineering) critique against `spec.md` and `plan.md` before any tasks are generated.
- For any 🎯 **Must-Address** findings, apply the suggested fixes to `spec.md` / `plan.md` autonomously and commit them — do not pause for user approval.
- For 💡 Recommendations, apply them when the fix is clear and low-risk; otherwise note and move on.
- 🤔 Questions: resolve with your best judgment based on context (same rule as the Specify phase).
- If the verdict is 🛑 **RETHINK**, loop back to `speckit-plan` (or `speckit-specify` if the spec itself is the problem), re-run the critique, then continue.
- Commit the critique report and any spec/plan updates before moving on.

### Phase 4 — Tasks

Invoke the `speckit-tasks` skill.

- Generate the full `tasks.md` with dependency-ordered, actionable tasks.
- Skip the optional `speckit-analyze` skill unless something looks inconsistent — use your judgment.
- Commit the tasks artifact.

### Phase 5 — Spec/Ask Alignment Check

The earlier phases can drift from a detailed PRD: clarifications get over-applied, scope creeps in from research, or requirements get rephrased away. This phase catches that before the user sees `tasks.md`.

#### 5a. Decide whether to run the check

Inspect `$ARGUMENTS`. The check is **only meaningful when the user provided a substantive PRD** — either inline or by reference. Decide based on the following, in order:

1. **`$ARGUMENTS` contains one or more URLs** (links to a Notion / Confluence / Google Doc / GitHub issue / Linear ticket / shared Markdown / PDF). Treat each URL as a likely PRD location. **Run the check.**
2. **`$ARGUMENTS` itself looks like a detailed PRD** — multiple paragraphs with structure such as headings, bullet lists of requirements, explicit goals/non-goals, acceptance criteria, or > ~400 characters of substantive description. **Run the check.**
3. **`$ARGUMENTS` is a one-line description, vague brief, or empty.** **Skip the check** — there is no source-of-truth document to align against. Write a short note in your final summary stating you skipped this phase and why, and proceed to Completion.

#### 5b. Resolve the source-of-truth PRD

If you decided to run the check:

- For each URL in `$ARGUMENTS`, fetch its content using the harness's web fetch tool (in Claude Code: the `WebFetch` tool). Extract the requirement-bearing sections.
- **If the harness has no web-fetch capability at all** (the tool is absent, not merely failing): you cannot resolve URL-only PRDs. Fall back to any inline PRD content in `$ARGUMENTS`. If the only source was a URL and there is no inline content, you cannot run a meaningful check — skip the rest of Phase 5, record `verdict: ⚠️ SKIPPED — source PRD unreachable (no web-fetch tool)` in the alignment report, and note it prominently in the Completion summary so the user knows alignment was not verified.
- If a URL is gated (auth required, 404, network error), record that and fall back to whatever PRD content is in `$ARGUMENTS` itself. If neither is usable, skip the rest of Phase 5 with a note.
- Concatenate the fetched / inline PRD content into a single "source PRD" view that you will compare against `spec.md`.

#### 5c. Compare source PRD to `spec.md`

Read the current `spec.md` end-to-end and judge it against the source PRD. You are looking for **significant** drift, not stylistic differences. Significant means:

- A requirement, goal, or explicit non-goal in the PRD is **missing** from the spec.
- The spec **adds** a requirement, scope item, or constraint that does **not** appear in the PRD and was not a necessary clarification.
- A requirement's semantics have been **changed** (e.g., "users can opt out" became "admins can opt users out"; "must support 10k req/s" became "should scale").
- Acceptance criteria in the PRD are **dropped** or **softened** in the spec.
- The spec contradicts a stated PRD constraint (compatibility, deadline, dependency, etc.).

Cosmetic, structural, or expansion-of-detail differences are **not** drift. The spec is allowed to be longer, more precise, and to flesh out implicit requirements.

#### 5d. Write the alignment report

Write `<spec-dir>/alignment-check.md` with:

1. **Source** — which URL(s) and / or inline ask were used as the source PRD.
2. **Verdict** — one of `✅ ALIGNED`, `⚠️ MINOR DRIFT (proceeding)`, or `🛑 SIGNIFICANT DRIFT (re-running prep)`.
3. **Findings** — table of `Severity | Category (missing / added / changed / dropped / contradicted) | PRD reference | Spec reference | Description`.
4. **Action** — what you decided to do (proceed, or re-run which phases).

Commit the report via `speckit-checkpoint-commit`.

#### 5e. Remediate significant drift (with retry budget)

This step is the **loop body**. Initialize a remediation counter to `0` before the first entry. Enter this step whenever the most recent 5d verdict is `🛑 SIGNIFICANT DRIFT`.

While the latest verdict is `🛑 SIGNIFICANT DRIFT`:

1. **Check the budget first.** If the counter is already `2`, do **not** start another pass — go to "budget exhausted" below.
2. **Increment the counter** (this pass now counts against the budget of 2).
3. **Update `spec.md`** by re-invoking the `speckit-specify` skill with an augmented input that includes:
   - The original `$ARGUMENTS` content (and fetched PRD body if from URL).
   - An explicit list of the drift findings the spec must fix (missing requirements to add, off-scope items to remove, semantic changes to revert).
   The skill will update the existing `spec.md` in place.
4. **Re-run Phase 2 (Plan)** to refresh `plan.md` against the corrected spec.
5. **Re-run Phase 3 (Critique)** to validate the corrected spec/plan.
6. **Re-run Phase 4 (Tasks)** to regenerate `tasks.md` against the corrected plan.
7. **Re-run Phase 5c–5d** (do **not** re-resolve the source PRD — keep the same source) to produce a fresh verdict, then return to the top of this loop and re-evaluate it.

**Loop exits:**

- **Aligned/minor** — a pass produces `✅ ALIGNED` or `⚠️ MINOR DRIFT`: accept it and proceed to Completion.
- **Budget exhausted** — the counter reached `2` and the verdict is still `🛑 SIGNIFICANT DRIFT`: stop. Update `alignment-check.md` with verdict `🛑 UNRESOLVED — manual review required`, list the remaining findings, and surface this prominently in the Completion summary. Do **not** silently proceed.

**Retry budget**: at most **2 remediation passes**, tracked by the counter above.

Commit each remediation pass's artifacts as it runs (the inner skills handle their own commits; you only need to commit the updated `alignment-check.md` at the end of each pass).

## Completion

After all five phases are complete, provide a brief summary:

- Feature name and spec directory
- Number of tasks generated in `tasks.md`
- Any critique findings that were addressed inline
- **Alignment check status** — verdict, source PRD reference, number of remediation passes used (if any), and any unresolved drift
- Any notable decisions you made autonomously

**Machine-readable status line (REQUIRED).** The **final line** of your output MUST be exactly:

`STATUS: <READY|BLOCKED> | SPEC_DIR: <absolute spec-dir path> | REASON: <short reason or n/a>`

- `STATUS: READY` — `tasks.md` was generated **and** the alignment outcome is `✅ ALIGNED`, `⚠️ MINOR DRIFT`, or `⚠️ SKIPPED`. Only in this state is the spec safe to implement.
- `STATUS: BLOCKED` — alignment is `🛑 UNRESOLVED` after the retry budget, or any phase could not complete. This is the explicit failure signal the parent `speckit-opsmill-auto` checks before deciding whether to start implementation; do not dress an unresolved run up as a success.
- `SPEC_DIR` MUST be the absolute path to the spec directory, so the parent can hand it to the implement phase without parsing prose.

Keep this as the literal last line, unwrapped.

Do **not** proceed to implementation, review, or extraction. The user will run those phases (or `speckit-opsmill-auto` from scratch) when ready.