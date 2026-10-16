# Simplified PR lifecycle review

Reviewed the explicit helper, tests, two workflows, developer/operator documentation, and current
specification, plan, and tasks. The accepted scope is native stale processing, native Slack reminders,
and a stateless dashboard; production publishing and cleanup remain disabled.

## Important finding

- **P2 — Keep pending reviewers visible on blocked PRs** (confidence: 95%). In
  `.github/scripts/pr-lifecycle.cjs`, `classify` handles `BLOCKED` before requested reviewers and keeps
  the author as next actor. A same-head aggregate with `BLOCKED` and `REVIEW_REQUIRED`, alongside
  requested users/teams, therefore renders only the author and “Resolve conflicts, checks or unmet
  requirements.” All requested reviewers disappear from the dashboard because there is no separate
  reviewer column. This conflicts with the documented pending-reviewer visibility and misdirects
  review follow-up. Preserve requested reviewer names and review responsibility in this case without
  claiming review is the only possible blocker. Add a regression with both a requested user and team.
  Reproduced locally through the exported classifier; no API requests or mutations were involved.

## Aspect results

| Aspect | Result |
| --- | --- |
| Code | One important dashboard routing finding; no blocking write-safety issue found. |
| Comments | The visibility claim needs the routing correction above; accepted native timing and rollout limits are explicit. |
| Tests | All 11 tests pass; add the blocked-plus-pending-review regression above. |
| Errors | Collection/write failures propagate; reads and body-size validation precede mutations. Unknown merge data cannot establish readiness. |
| Types | Not applicable: the change adds CommonJS JavaScript without type declarations. Boundary validation was covered by code review. |
| Simplify | No significant additional simplification recommended; the helper avoids reconstructing native timing or delivery state. |

## Safety and verification

- Preview defaults to zero writes. Publish and stale jobs are unconditionally disabled, stale retains
  debug-only, and its dependency requires publishing success before future activation.
- Review history preserves decisive state through comment-only reviews and clears it on dismissal.
  Requested users and teams are paginated. Dashboard data is escaped and size-limited.
- Publishing requires an explicit open non-PR issue with the marker and only synchronizes owned
  exemption labels. Partial write failure remains visible and prevents successful job completion.
- Ran `node --test .github/scripts/pr-lifecycle.test.cjs` with the bundled Node runtime: 11 passed,
  zero failed. Historical private replay results were supplied by the implementation agent and were
  not independently repeated in this review. Hosted activation remains outside this review.

The review configuration file is absent; extension defaults enable all aspects. The review-run skill
was applied once. A specialist spawn was rejected by the agent thread limit, so applicable specialist
instructions were read and applied sequentially in this reviewer, as authorized. Repository guidance,
CLAUDE routing, constitution, documentation, Markdown, and code-comment guidelines were consulted.
The referenced root RTK.md was unavailable. No production code or external state was changed.

## Recommended action

Correct the pending-reviewer routing and add its regression before merging. Keep native timing,
continuation, and approval polling races as the explicitly accepted tradeoffs; no additional engine
or persistence layer is warranted.

## Resolution

The pending-reviewer finding is resolved. A blocked PR with REVIEW_REQUIRED includes the author
and requested users/teams as next actors, with an action covering review and other requirements.
The added regression failed before the correction and passes afterward; all 12 helper tests pass.
See [current test evidence](evidence/simplified-tests.txt). No write capability was enabled.
