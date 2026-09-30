# Alignment Check: spec vs source PRD

**Date**: 2026-09-29

## 1. Source

- Primary PRD: `design/05-handoff.md` (proposal §2, rejected §3, decisions §4, open questions §5, system gaps §6, lift sheet, queries, checks).
- Supporting: `design/00-brief.md`, `design/03-decisions.md` (rounds 1–6), `design/04-review.md`.
- Inline ask: the feature description passed to this run (same content as handoff §2).
- Caller's standing decisions (Merge ungated, backend-data-only, raw log line, tasks link out, desktop only, theme tokens, open questions 2–4 defaults, `TablePagination` as an early task).

Compared against `spec.md` after the critique updates (commit `e80adb7a4e`), with `plan.md` and `tasks.md` checked where the PRD is technical (lift sheet, queries).

## 2. Verdict

**⚠️ MINOR DRIFT (proceeding)**

Every requirement, decision, open question and check in the handoff is present in the spec or plan. The differences below are justified clarifications or base-branch facts, each recorded in the spec's Clarifications or the research, none changing what the PRD asks the page to do.

## 3. Findings

| Severity | Category | PRD reference | Spec reference | Description |
|---|---|---|---|---|
| Minor | changed | Handoff "Queries" 1: repositories query "Paginated"; lift sheet: "`rank` should become server-side ordering if the repository query supports it" | FR-013/FR-014; research R1; plan Complexity Tracking | Repositories are fetched in one request (limit 500) and ranked/paginated on the client. The server can only order by attribute value lexicographically, so it can't express "import error, then unreachable" — the lift sheet's own condition isn't met. Bounded, with a visible notice past the limit. |
| Minor | dropped | Rev-06 row "⋯" menu (Open repository, View tasks, Reimport last commit); `04-review.md` 4a hit-area fix | Clarifications (row menu); Out of Scope | The row menu isn't built: its items were stubs. The name links to the repository. Handoff §2 doesn't list the menu, and the lift sheet says "keep the row, the pill, the bands and the pagination". |
| Minor | changed | `04-review.md` 4c: with no repository permission, "branch tasks still show; only repository-linked tasks are hidden" | Clarifications (no-permission tasks); FR-040 | All tasks show; Related falls back to the object kind. Hiding rows on the client would break server pagination and the count the lift sheet requires. |
| Minor | added | — (handoff lists empty, loading, no-permission for the card) | FR-020 | A "couldn't be loaded" state for non-permission failures of the repository query. Necessary: otherwise a failure renders as an empty state. |
| Minor | added | — | FR-005, Clarifications (default branch) | New cards only on non-default branches (where today's actions and task list appear). The PRD doesn't address the default branch. |
| Minor | added | Handoff §2 "Empty states: no Git counterpart (Sync with Git off)" | FR-010, FR-019, Clarifications (Sync off) | On a Sync-off branch the card lists read-only repositories (they track every branch) and shows "Not synchronised with Git" only when none remain. Consistent with the empty state and with the cross-branch spec's row set. |
| Minor | added | — | FR-046 | Auto-refresh rules (tasks page 1 and failed count every 10s; repositories only while syncing). Today's task list already polls; the PRD's query 4 assumed IFC-3199 polling, which isn't on this base. |
| Minor | added | — | FR-053 | Branch-scoped links open the page's branch, not the selector's (critique X1, Principle II). Refinement of the handoff's links. |
| Minor | changed | Lift sheet: body `Card className="to-neutral-50"` | Research table "What is on the base branch", R12 | This base's `ObjectDetailsBody` uses `Card variant="panel"`; the plan follows the real object page, which is the PRD's intent ("same layers as the object details page"). |
| Minor | changed | Handoff §6 "Dark mode: this branch has no theme support" | FR-050, research | The theme exists on this base; FR-050 uses its tokens now instead of deferring. Satisfies the PRD's requirement more directly. |
| Minor | changed | Handoff query 4: "reuse IFC-3199's query keys where they overlap" | Research R7 | IFC-3199's frontend isn't on this base, so there are no keys to reuse; this feature defines `repositoryQueryKeys`. |
| Minor | changed | Lift sheet: `src/entities/tasks/ui/branch-tasks-table.tsx` | plan Project Structure | Became the shared `TasksTable` in `entities/tasks/ui/tasks-table/tasks-table.tsx`, with a configurable column set, so other task lists can adopt it (`follow-up-tasks-table.md`, IFC-3245). |
| Info | kept | Brief #1, #3 (warning/block on Merge) | Clarifications Q1, FR-031 | Reversed per handoff §4 round-6 decision; open question 1 carried with INFP-670 sign-off. FR-031 keeps today's existing Merge guards (critique E1), which the PRD's "today's inline buttons" implies. |
| Info | kept | Brief riskiest assumption; handoff §6 "latest import task per repository" | Research R2, FR-022, T001 | Code check found `git-repository-import-object` isn't tagged with the repository and the periodic sync tags the branch only in some calls. Covered by the not-found fallback, a verification task and a backend follow-up; the PRD's query is used as written. |

No requirement, goal, non-goal or acceptance criterion from the PRD is missing, softened or contradicted.

## 4. Action

Proceed. No remediation pass (counter 0). Items for the user to double-check are listed in the run summary: client-side repository ranking, the dropped row menu, tasks shown to users without repository permission, and the import-task tagging gap.
