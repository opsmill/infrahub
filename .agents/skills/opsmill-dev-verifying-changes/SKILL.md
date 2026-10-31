---
name: opsmill-dev-verifying-changes
description: >-
  Produces an evidence-backed PASS/FAIL self-check of a step's claimed result against its original
  pass criteria, in-context and without a subagent.
  TRIGGER when: confirming a test passes (or fails for the documented reason), pre-CI checks are
  clean, a rebase or merge preserved intent, a fix applied cleanly, or any "is this really done?"
  checkpoint where the next action is still reversible; also as the declared degraded fallback
  when opsmill-dev-judging-changes cannot dispatch a subagent.
  DO NOT TRIGGER when: the next action is irreversible (open or merge a PR, force-push, stamp a
  completion marker) and an author≠judge verdict is wanted → opsmill-dev-judging-changes;
  auditing a repository against conventions → opsmill-repo-auditing-repo-standards.
argument-hint: "<criteria source, or the pass criteria inline> [evidence: <commands that prove each criterion>]"
metadata:
  version: 0.1.0
  author: OpsMill
---

# Verifying changes

The cheap gate. No subagent, no receipt — one fresh reading of what the step was supposed to
achieve, and the actual output that proves each part of it. It exists because "the tests pass"
typed from memory is not evidence, and because re-reading the criteria (instead of recalling
them) is where most quiet drift gets caught.

Use it at reversible checkpoints. When the next action cannot be undone, use
`opsmill-dev-judging-changes` instead — a self-check proves only that the author agrees with
itself.

## The evidence rule

Never claim *done / passing / green / fixed / clean* without pasting the command **and** its real
output. If you cannot produce the output, the check fails — report why instead of asserting.

## Procedure

1. **Re-read the criteria fresh.** Open the source (the issue, the `.bug-analysis-<key>.md`, the
   spec section, the step's own stated goal). Do not work from memory of what it said.
2. **List each pass criterion** as its own line before checking anything.
3. **Prove each one.** Run the command that demonstrates it — the targeted test, the linter, the
   build, `git diff --stat <base>...HEAD`, `git status` — and paste the command with its output
   under that criterion.
4. **State the verdict.** PASS only when every criterion has proving output. Anything short of
   that is FAIL, with the failing criterion named.

Report in this shape:

```markdown
Criteria source: <ref>
| # | Criterion | Evidence | Y/N |
|---|---|---|---|
| a | Reproduction test passes | `pytest tests/test_x.py::test_bug -x` → 1 passed | Y |
| b | Test file unchanged from the test-writer's version | `git diff main...HEAD -- tests/` → empty | Y |
Verdict: PASS
```

## When it is the degraded fallback

`opsmill-dev-judging-changes` falls back to this procedure when it cannot dispatch a subagent.
In that case say *"judge ran in degraded mode — no subagent available"* in the report, and let
that skill write its `DEGRADED` receipt. Do not present a self-check as an independent verdict.

## Rationalisations to refuse

| Thought | Reality |
|---|---|
| "I ran it a minute ago, same result." | Paste it again. The point is the output on the record, not your recollection. |
| "The criteria are obvious, no need to reopen the file." | Reopening is the step. Drift hides in the clause you did not reread. |
| "Lint output is long, I'll summarise as clean." | Paste the tail that shows the exit status. A summary is an assertion. |
| "This is a tiny change." | Tiny changes get the same four lines. They are cheap. |
| "The next step is just a PR, I'll verify instead of judging." | Opening a PR is irreversible. That is the judge's job — `opsmill-dev-judging-changes`. |

## Common mistakes

- Checking against the criteria as you remember them, then discovering the source said something
  narrower.
- Pasting the command but not its output (or the output but not the exit status).
- Marking PASS with one criterion left as "should be fine".
- Presenting this self-check as an independent verdict when the judge could not run — say
  *degraded*.
