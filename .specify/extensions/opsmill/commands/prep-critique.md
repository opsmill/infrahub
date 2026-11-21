---
description: Phase of the opsmill-prep workflow — run the Product and Engineering critique of spec.md and plan.md, apply its findings, and report the verdict.
---

## User Input

```text
$ARGUMENTS
```

## Outline

You run **one phase** of the `opsmill-prep` workflow: **Critique**. The workflow file (`.specify/workflows/opsmill-prep/workflow.yml`) runs the other phases as separate steps and decides when a phase is repeated, so do only what this file describes, then stop.

Nobody can answer a question during this run. Wherever a choice comes up, use your best judgment and continue.

Do not commit: the workflow commits what this phase wrote.

Run the dual-lens (Product + Engineering) critique against `spec.md` and `plan.md`. Ignore the user input.

The feature directory is the `feature_directory` recorded in `.specify/feature.json`.

**Resolve the critique provider first.** Record the answer as `CRITIQUE_MODE`. Run this check from the repository root and read `CRITIQUE_MODE` off its output — do not decide from memory:

```bash
if [ -d .specify/extensions/critique ] || grep -q '"critique"' .specify/extensions/.registry 2>/dev/null; then
  echo "critique extension: installed"
else
  echo "critique extension: missing"
fi
```

| Check output | `CRITIQUE_MODE` |
|--------------|-----------------|
| `installed` | `extension` |
| `missing`, and you can dispatch clean-context subagents | `fallback` |
| `missing`, and no subagent dispatch is available | `none` |

Both signals are written by `specify extension add` itself, and neither is harness-specific — do not key the decision off `.claude/skills/speckit-critique-run/`, which only exists under Claude Code. A missing critique provider never blocks the run: it selects the branch below and it is reported on the verdict line.

**`CRITIQUE_MODE: extension`.** Invoke the `speckit-critique-run` skill. If that invocation fails — the skill is not found, or it errors out without returning findings — downgrade to `fallback`, or to `none` if no subagent dispatch is available, and report the mode that actually ran.

**`CRITIQUE_MODE: fallback`.** Dispatch **one** clean-context subagent to run the same dual-lens critique. Brief it self-contained: absolute paths to `spec.md`, `plan.md`, and the resolved project context files, plus the required return shape — findings tagged 🎯 Must-Address, 💡 Recommendation, or 🤔 Question, and a verdict of `PROCEED` or `RETHINK`. Findings only: the subagent must not edit the spec or plan.

**`CRITIQUE_MODE: none`.** Skip the critique. Never describe the run as critiqued, and do not substitute an unstructured reread of `spec.md` for the critique. The verdict is `PROCEED`.

**Handle the findings**, in `extension` and `fallback` modes alike:

- 🎯 **Must-Address**: apply the suggested fixes to `spec.md` / `plan.md`.
- 💡 Recommendations: apply them when the fix is clear and low-risk; otherwise note and move on.
- 🤔 Questions: resolve them with your best judgment from the context.
- A 🛑 **RETHINK** verdict: do **not** rerun the plan yourself. Report the verdict: the workflow reruns the plan phase, three plan and critique passes at most.

**Verdict line (REQUIRED).** The **final line** of your output MUST be exactly, unwrapped:

`CRITIQUE_VERDICT: <PROCEED|RETHINK> | CRITIQUE: <extension|fallback|none>`

The workflow reads this line to decide whether to rerun the plan. Write the two words `CRITIQUE_VERDICT: RETHINK` nowhere else in your output.
