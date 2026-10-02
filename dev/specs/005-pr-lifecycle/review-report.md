# PR lifecycle review

Review scope: `19c7d8bb5e3fb64b60dda3308cde01f8f5639345..b7c228ea4`, including the companion,
workflow, tests, specifications, evidence, and operator documentation. This report records findings
against that reviewed head; subsequent fixes require targeted verification.

The review workflow ran once. All six aspects were enabled by the extension defaults; no project
override exists. The configured wrapper was absent, so the extension's detection script was run
and the explicitly supplied commit range established scope. Specialist creation hit the agent
thread limit. With the coordinating agent's authorization, this independent reviewer applied
the code, comments, tests, errors, types, and simplify skills sequentially in one context.
No GitHub requests or mutations were made. Only this report was written.

## Findings

- **P1 — Preserve newer activity when observing a reopen.** Confidence: 100.
  Location at reviewed head: `utilities/pr_lifecycle.py:625` (`observe_activity`). A newly observed
  reopen replaces the calculated activity time unconditionally. A saved January baseline,
  June reopen, and September 27 human comment observed on September 28 produce June activity and
  `warning_needed=True`. This permits a warning before 60 days of inactivity; a later closure can
  consequently occur too early. Preserve the newest applicable activity when resetting the reopen
  cycle, including a newly observed head change. Add a delayed-scan regression containing both a
  reopen and later activity. The existing reopen test checks only the reopen event.

- **P2 — Fail a label operation when recovery finds no successful write.** Confidence: 100.
  Location at reviewed head: `utilities/pr_lifecycle.py:1669` (`Lifecycle.label`). After a rejected
  label write, the exception handler refreshes and returns without verifying the requested label
  state. A transport rejecting the write before applying it reproduced a successful method return
  with empty labels and no pending intent. Reconciliation can consequently claim completion while
  its requested warning or exemption label is absent. Verify the recovered presence/absence and
  propagate failure if the requested state was not achieved. Cover failed addition and removal,
  plus a lost response after a successful write. Subsequent closure checks remain conservative;
  this finding does not claim an active closure vulnerability.

Both findings were reproduced locally using existing fixture adapters and pure lifecycle calls.
Their missing regression scenarios are the important test gaps; they are not separate findings.

## Aspect results

- **Code:** The two findings above require correction. Repository boundaries, read-only observation,
  fresh closure gating, and independent outcome verification are otherwise coherent.
- **Comments:** No additional actionable discrepancy. Durable documentation correctly distinguishes
  local evidence, hosted validation, and activation, and discloses polling races.
- **Tests:** Strong behavioral coverage of receipts, forged markers, retention, pagination,
  calendar milestones, dashboard limits, and pinned upstream integration. Add the two regressions.
  The coordinator owns the final suite execution; this review does not claim a fresh full run.
- **Errors:** The label-recovery issue is the actionable silent failure. Other inspected paths
  preserve incomplete status or reject closure after incomplete data.
- **Types:** Frozen records and explicit boundary parsing are appropriate. Encapsulation 8/10,
  invariant expression 7/10, usefulness 9/10, enforcement 8/10. No additional blocking type issue.
- **Simplify:** No required refactor. Any future consolidation of warning proof checks must preserve
  the independent post-warning external-activity veto; matching a stored digest alone is insufficient.

## Disposition

Fix the two findings and run their focused regressions before delivery. Keep the mutation job
unconditionally disabled. The previously documented hosted-test prerequisite and mutation-capacity
limit remain activation blockers, not newly discovered defects or evidence of production recovery.

## Resolution

Both findings were fixed in `92c232e5e62ec2c8518e3a6a8b4d66c1f775a1e3`. Delayed reopen observations preserve newer
human activity and head changes. Label operations verify the requested presence or absence after
both successful responses and recovery; an unconfirmed result raises an error. The two added
regressions failed before the fixes, then passed in the complete 86-test suite. Existing lost-response
recovery tests also pass. See [final evidence](evidence/final-validation.txt).
