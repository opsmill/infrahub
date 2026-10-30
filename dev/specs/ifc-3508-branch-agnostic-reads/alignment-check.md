# Alignment Check: spec.md Against the Brief

**Date**: 2026-10-30

## Source

- `branch-agnostic-wip/brief.md`, the inline PRD the user named. It is not committed, so there is no link. Its decisions were settled in a review session on 2026-10-29 and 2026-10-30.
- `branch-agnostic-wip/audit-report.md`, for the facts the brief relies on.

The brief contains no URL to fetch.

## Verdict

⚠️ MINOR DRIFT (proceeding)

Every goal, decision, rule, new test, open question and out-of-scope item of the brief has a matching requirement, acceptance scenario, assumption or task. The differences below either apply one of the brief's own rules to a case its tables do not name, or add detail the brief leaves to the plan. One drift, in tasks.md, was found and fixed during this check (finding 7).

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|---|---|---|---|---|
| Minor | changed | "Deleting a branch-aware node on a branch (PR 5)"; migration table, shape 2 | FR-023, FR-025; data-model.md shape 2 | The brief stops branch `deleted` edges on branch-agnostic relationships when the delete runs on a user branch. The spec also covers deletes on the default branch, which today write a default-branch `deleted` edge next to the `-global-` link. The brief's "Rule for edges between the same two vertices" forbids a default-branch edge too, so the spec applies that rule; the brief's table does not name the case. |
| Minor | added | "Peer existence check on every read (PR 5)", list of reads | FR-018; research R6; task T063 | The spec extends the check to every other read of `IS_RELATED` that can reach a branch-agnostic relationship or kind, for example `RelationshipCountPerNodeQuery` and `DependentNodesQuery`. The brief lists specific reads. The extension follows the brief's reason for moving filters and ordering into PR 5: no read may regress when the branch edges stop being written. |
| Minor | added | Group 3, "Why not the request branch" | US1 scenario 7; task T007 | The brief records, as found by reading the code, that `super_admin` granted on a branch lets mutations to `/graphql/B` write branch-agnostic nodes. The spec adds a test for it. The decision is unchanged. |
| Minor | added | "What each fix must include" | plan.md "Complexity Tracking"; task T014 | The brief does not mention E2E tests. The constitution requires them for user-facing features. The plan records an exception and makes it a gate for the reviewer. |
| Minor | added | IP pools, "fails with an error that names…" | contracts/user-visible-behavior.md; research R4 | The plan chooses `ResourceNotFoundError` for a namespace missing on the branch, and `PoolExhaustedError` for no usable resource. The prefix pool's `IndexError` is replaced by the same `PoolExhaustedError`. The brief names only what the error must contain. |
| Minor | added | Not in the brief | spec.md "Assumptions" | The check before deleting a branch-agnostic node uses the request branch's schema for every branch. The spec records this as a known limit. |
| Minor (fixed) | changed | The six PRs, PR 5: "the peer existence check on every read"; "each branch window for a branch-agnostic read" | tasks.md T069, T065; plan.md "Delivery by PR" | tasks.md had moved the window version of the check for branch-agnostic reads into PR 6. That would let PR 5 ship with a branch-agnostic read worse than before. The check is moved back into PR 5, and T065 adds a GraphQL test of that read. |
| Minor | changed | Group 4, `m062` | tasks.md T025 | The brief removes the flag from `m062`. The plan removes it only after confirming the query ignores the flag, because `m062` is a shipped migration. The audit reports that it does ignore the flag, so the result is the same. |

No requirement, goal, non-goal or acceptance criterion of the brief is missing, softened or contradicted. The three open questions remain open, as gates (tasks T061, T062 and T085). Research R7, R8 and R9 record evidence and a recommendation for each, without applying any.

## Action

Proceed. No remediation pass is needed. The fix for finding 7 is committed with this report.
