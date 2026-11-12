# Research: Repositories and Git state columns on the branches list

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-30, rework 2026-10-01 (R14), rework A 2026-10-01 (R15), PR review 2026-10-08 (R16 to R19)

Code references name the module and symbol; line numbers are left out on purpose. Paths are relative to `frontend/app/` unless stated. This file records the reasoning behind each decision and the code it was checked against.

## What is on the base branch (`ple-branch-details-repos-infp-671`, PR #10779)

| Needed | On this base? | Consequence |
|---|---|---|
| Git state pill | Yes: `entities/repository/ui/branch-repositories/git-state-pill.tsx::GitStatePill` | Reused unchanged by the Git state cell. |
| Per-branch repository query for the details card | Yes: `entities/repository/ui/queries/get-branch-repositories.query.ts` | Not used by the list since R15; the list has its own documents (R16). |
| Branches table tests | **None** under `entities/branches/ui/branches-table/` | The component test files are new. |
| Deterministic import-error E2E fixture | Class-local: `tests/e2e/branches/test_branch_details_repositories.py::TestBranchDetailsRepositoryImportError::broken_repository` | Promoted to `tests/e2e/branches/conftest.py` as a function-scoped fixture that creates its branch with `sync_with_git=True`, so both E2E files share it (plan IV). |

## Superseded decisions

Each line names the decision and what replaced it. The full reasoning is in the Git history of this file.

- R1, selection through an anchor row for a branch's repeated rows: superseded by R14 (one row per branch, ordinary per-row selection).
- R2, a `toBranchTableRows` rule that turned each branch into one row per repository: superseded by R14; the rule and its row model are deleted.
- R3, ordering rows with the details card's `rankRepositories`: superseded by R15 (order by Git state severity, then name).
- R4, three fixed-width grid tracks for Repository, Git state and Commit: superseded by R14 (two fixed tracks, for Repositories and Git state).
- R5, one `CoreGenericRepository` request per loaded branch through the details card's query: superseded by R15 (one `InfrahubRepositoryBranchStatus` request per repository). The per-branch option needed about 40 requests per page; the per-repository option needs 1 + R requests, independent of pages loaded.
- R6, a `useBranchTableRows` table hook: superseded by R14, then by R15 (`useGetBranchGitStatuses`, R16).
- R7, extracting `RepositoryNameLink` from the details card's row: reverted with R14; the table renders its own repository pill.
- R8, lifting `CommitHash` from PR #10658: superseded by R14 (the Commit column is dropped).
- R11, ignoring a cut-short list: superseded by R15. A cut repository list reads "Could not load repositories" on every row; a status page cut at 500 branches reads it on the branches that page does not list.
- R13, row reuse through `combine` over per-branch queries: superseded by R14. The structural-sharing finding is kept in `dev/knowledge/frontend/react.md`.

## R9 — Polling

**Decision**: each repository's status query refreshes every 10 s while one of its rows has `sync_status = syncing`, and stops when no row is syncing (`entities/branch-git-status/ui/queries/get-repository-branch-status.query.ts::getRepositoryBranchStatusRefetchInterval`). The repository-list query and the status queries have a 60 s stale time.

**Rationale**: FR-014 asks for the cadence the branch details page already uses (`REPOSITORY_SYNC_REFETCH_INTERVAL_MS`). Only a repository that is syncing polls. A failed read polls every minute (`REPOSITORY_ERROR_REFETCH_INTERVAL_MS`) and a permission denial stops polling, as on the branch details page. Queries do not retry: the app query client turns retries off.

## R10 — Pending, denied and error rendering

**Decision**: the branch cells always render; the Repositories cell shows the state of the repository data, and the Git state cell stays blank until a repository on the branch has loaded. Which rows a failure affects is decided in R18.

**Mapping order**: each query result is read `data` first, then the error, then pending (`entities/branch-git-status/ui/hooks/use-get-branch-git-statuses.ts`). A failed background refetch (the syncing poll, or a window refocus) therefore keeps the last loaded result rendered, which is also how #10779's card reads its query.

**Finding (toast)**: the shared GraphQL client routes errors through `shared/api/graphql/error-handling.ts::handleGraphQLErrors`:

- `PERMISSION_DENIED` is skipped, so there is no toast for the denied state.
- Network errors throw without a toast.
- Any other GraphQL error calls `notifyUser`, which toasts, unless the request context supplies `processErrorMessage`.

**Decision**: both requests of the `branch-git-status` entity pass a no-op `processErrorMessage` (`api/get-branch-git-repositories-from-api.ts`, `api/get-repository-branch-status-from-api.ts`). FR-013 asks for no toast, and a page-level toast for a degraded cell is the wrong surface. The error message stays reachable as the tooltip and visually hidden text of the cell. The branch details card's fetcher is not changed by this feature.

## R12 — No manual memoization; the no-colour pill

**Decision**: `branches-table.tsx::BranchesTable` and `branches-data-table.tsx::BranchesDataTable` use no `React.useMemo`. The React Compiler memoizes (`dev/knowledge/frontend/react.md`, "React Compiler").

**No-colour pill**: `GitStatePill`'s fallback renders `value || label || "—"` in a grey `Badge` when the schema defines no colour for a state.

## R14 — Why one row per branch

**Decision** (owner, 2026-10-01, after trying the one-row-per-repository list on a dev stack): the list goes back to one row per branch. The Repositories cell shows the first repository as a pill, then "+N more" linking to the branch details page; the Git state cell shows the first repository's pill (the worst state) with an `n/N` count and a per-label tooltip. The Commit column is dropped; the commit is in the pill's tooltip and on the branch details page.

**Measurements** (24 branches × 16 repositories): one row per repository rendered 279 rows, 280 checkboxes, about 15 000 DOM nodes and about 200 console warnings, and was visibly slow. The 24 per-branch repository requests completed in 0.36 s in total, so the cost was rendering, not fetching. The ticket's "one row per repository" assumed one or two repositories per branch.

**Single-request finding**: one request for every branch is not available today. Aliasing 16 `InfrahubRepositoryBranchStatus` fields (one per repository) into one GraphQL document returns HTTP 500 `read() called while another coroutine is already waiting for incoming data`, and `Branch` has no repositories field. The backend follow-up is either a `repository_ids` list argument on `InfrahubRepositoryBranchStatus` or a fix to the concurrent-resolver path that the aliased document hits.

**Alternatives considered**: a stacked cell listing every repository, which the ticket rules out ("no stacking inside a cell") and whose height grows with the repository count. The roll-up follows the Proposed changes cell's existing "first item + N more" pattern instead.

## R15 — Repository-anchored data, page-owned

**Decision** (owner, 2026-10-01, after the architecture review of the R14 implementation): the list reads the epic's `InfrahubRepositoryBranchStatus` once per repository and pivots the rows to one `BranchGitStatus` per branch name (`entities/branch-git-status/domain/rules/summarize-branch-git-statuses.ts::summarizeBranchGitStatuses`). The page owns the fetch (`useGetBranchGitStatuses`, `useQueries` with `combine`), the summary rides on the row view-model (`BranchTableRow.gitStatus`), and the cells are pure. Repositories are ordered by Git state severity (`domain/rules/sync-status-severity.ts::compareWorstSyncStatusFirst`: `error-import` > `unknown` > `syncing` > `in-sync`, then name). Requests: 1 + R, independent of pages loaded; a 60 s stale time bounds the requests a window refocus sends.

**Why**: the R14 implementation had three defects.

1. The cells owned and duplicated the data and its derivation: two cells ran the same query and the same ranking, and the derivation lived in `.tsx`, out of reach of pure tests.
2. The roll-up reused the details card's band ordering (`rankRepositories`), which ranks an unreachable remote above every other non-failed repository. An unreachable repository whose last import succeeded therefore came first, and the Git state cell read "In Sync" while another repository on the branch was syncing or unknown. Severity on `sync_status` alone fixes it.
3. The per-branch query mirrored the backend's row-set rule on the client (`getRepositoryListKind`: `CoreGenericRepository` when synced, `CoreReadOnlyRepository` otherwise), the rule the epic's query exists to keep server-side (FR-003).

**Consequences**: merged branches read "No repositories"; the cache is not shared with the branch details page; the commit of a fresh synced branch is the fork-point commit; the status query needs view permission on all branches. How failures spread is revised by R18.

**Alternatives considered**: keeping per-branch requests but lifting them into a table hook (fixes defect 1 only); one aliased document over every repository (HTTP 500 today, R14). The backend `repository_ids` follow-up collapses 1 + R to 2 requests without touching cells or rules.

## R16 — Own entity with its own queries

**Decision** (2026-10-08, PR review): the list's data lives in its own entity, `entities/branch-git-status/`, with its own GraphQL documents, queries and query keys:

- `api/get-branch-git-repositories-from-api.ts`: `GET_BRANCH_GIT_REPOSITORIES` reads `CoreGenericRepository` (id, name, `__typename`, count) in one 500-row page, ordered by name.
- `api/get-repository-branch-status-from-api.ts`: `GET_REPOSITORY_BRANCH_STATUS($id, $limit)` reads `InfrahubRepositoryBranchStatus` (branch name, commit, sync status).
- `ui/queries/branch-git-status.query-keys.ts`: `branchGitStatusQueryKeys.repositories(params)` and `branchGitStatusQueryKeys.repositoryBranchStatus(params)`, under `["branch-git-status"]`, which branch create, delete, merge and rebase and the list's reload button invalidate.
- `ui/hooks/use-get-branch-git-statuses.ts::useGetBranchGitStatuses(branchNames)`: the composed hook the branches table calls.

**Why**: the earlier implementation read the repository list through #10779's details card query with added options (`syncWithGit`, `isSyncing`). Adding options that change a query's behaviour for a new screen couples two features through one query: a change for the card can break the list. A query reused exactly as it is would have been fine. The list needs a smaller read (no pagination, no operational status) and different failure handling, so it gets its own documents. The `branches` entity imports `branch-git-status`; `branch-git-status` does not import `branches` and takes plain branch names.

**Alternatives considered**: keeping the read inside the `branches` entity (it is about repositories, not branches, and pulled repository types into `branches/domain`); fixing the layers inside `entities/repository` (its only consumer would be this list).

## R17 — No branch context on the list request

**Decision** (2026-10-08, PR review): the repository list and status requests carry no branch context. A request without `context.branch` goes to `/graphql`, which reads the default branch (`shared/config/config.ts`, `shared/api/graphql/client.ts`).

**Why**: the earlier hook read every branch to find the default branch by `is_default` and sent it as the request's branch. That made the entity depend on the branch list, added a "No default branch found" error that a user cannot act on, and duplicated what the GraphQL endpoint already does. The lookup, the error and the dependency are removed.

## R18 — Report a failure at the narrowest scope

**Decision** (2026-10-08, PR review): a failure affects only the rows and repositories it belongs to (`summarizeBranchGitStatuses`, cells in `entities/branches/ui/branches-table/cells/`):

| Failure | Repositories cell | Git state cell |
|---|---|---|
| The repository list is pending | Loading indicator, every row | Blank |
| The repository list is denied, or every status read is denied | "No permission", every row | Blank |
| The repository list fails, or returns fewer repositories than its count (over 500) | "Could not load repositories", every row, with the reason as tooltip and visually hidden text | Blank |
| A repository's status page is cut at 500 branches and does not list this branch | "Could not load repositories" on that row, naming the repositories | Blank |
| One repository's status read fails or is denied | On every row: the repositories that loaded, then "1 repository could not be loaded" or "N repositories could not be loaded", with `<repository>: <message>` or `<repository>: No permission` as tooltip and visually hidden text | The worst state among the repositories that loaded; `n/N` counts loaded repositories only |
| One repository's status read is pending | The repositories that loaded; the loading indicator only when none has loaded | The worst state among the repositories that loaded; `n/N` counts loaded repositories only |
| A status row has no sync status | Counted and shown as the schema's Unknown choice (`domain/rules/get-unknown-sync-status.ts`) | Same |

**Why**: the earlier rule turned one failed status read into "Could not load repositories" on every row, one pending read into a spinner on every row, and hid a denied repository without saying so. The operator lost every other repository's state because of one repository. Reporting each failure where it happens keeps the rest of the list useful and names the repository that needs attention.

**Accepted limitation**: a failed status read has no rows, so the client cannot tell which branches that repository lists, and it does not re-derive that set from the branch's sync flag (FR-003). The notice therefore appears on every branch, including branches not synced with Git that a failed read/write repository would never list.

## R19 — PR #10658's status files are not lifted

**Decision** (2026-10-08, PR review): this feature does not lift PR #10658's `InfrahubRepositoryBranchStatus` files (API, model, mappers, use case) into `entities/repository/`. The entity of R16 has its own smaller status document and mapper.

**Why**: the lifted files carried hand-written wire types in `domain/model`, fields nothing in the list reads (`id`, `__typename`, `isDefault`, `ref`) and query variables nobody passes, and their only consumer here was the list. Keeping them byte-identical to #10658 blocked fixing their layers. Without the lift, #10658 merges into `entities/repository/` without a conflict with this feature.

## R20 — Merge and rebase stay asynchronous; the status refreshes when the task ends

**Decision** (owner, 2026-10-08, PR review): the branch details page keeps sending `BranchMerge` and `BranchRebase` with `wait_until_completion: false`, as on the base branch. A long merge or rebase can last longer than a reverse proxy's request timeout, so waiting for the task inside the request is rejected.

The mutations invalidate `branchGitStatusQueryKeys.all` when the task is queued. The merge and rebase buttons then pass the returned task ID to `entities/branches/ui/hooks/use-refresh-branch-git-status-on-task-end.ts::useRefreshBranchGitStatusOnTaskEnd`, which checks the task every 5 s through the tasks entity (`entities/tasks/ui/queries/is-task-finished.query.ts::isTaskFinishedQueryOptions`, a count of the task in `TASK_FINAL_STATES`: COMPLETED, FAILED, CANCELLED, CRASHED). When the task reaches a final state, the hook invalidates `branchGitStatusQueryKeys.all` once and the check stops. The check shows no error toast, and it stops after 360 checks (about 30 minutes at one check every 5 s; refetches on focus or invalidation also count) so a task the server never lists does not poll forever. Once the task has finished or the limit is reached, the check never goes stale, so a window focus, reconnect or remount does not send it again.

**Limit**: the check runs only while the page that started it is open. A merge that deletes the branch navigates to the branches list and passes the merge task id in the router navigation state, so the branches list runs the same check and reads the status lists again when the task ends. When the user leaves the branch details page or the branches list before the task ends, the next read follows the 60 s stale time (R9).

## Risks

1. The GraphQL-level error toast (R10) is closed by the no-op `processErrorMessage` on the entity's two requests.
2. The page's reload button refreshes branch queries and repository status; its busy indicator covers that reload only, not background polls.
3. Up to 1 + 500 requests on a deployment with 500 repositories, each polling every 10 s while it syncs. The backend `repository_ids` follow-up (R14) removes the per-repository requests.
4. A branch created outside this page (Git import, another user) can read "No repositories" until the status lists are read again: on reload, or on a window refocus at least 60 s after the last read.
5. E2E: the `broken_repository` fixture's branch is created with `sync_with_git=True`, which changes the premise of #10779's details test (it used `BranchAPI.create`'s default, `False`). To be verified on a live stack (below).

## E2E premise verification

**Status**: code-derived expectation, to be confirmed on a live stack (T032 partial: no stack was available in the implementing run).

**Expectation**: the branch details card lists repositories through `entities/repository/domain/rules/get-repository-list-kind.ts::getRepositoryListKind(syncWithGit)`; the `/branches` list reads the status rows instead, whose backend row set gives the same answer. `getRepositoryListKind(false)` returns `CoreReadOnlyRepository`, so a `sync_with_git=False` branch lists only read-only repositories and its card should not list the broken `CoreRepository` the fixture creates. `getRepositoryListKind(true)` returns `CoreGenericRepository`, which includes it.

**Consequence for the E2E cases**:

| Test | `sync_with_git` |
|---|---|
| `tests/e2e/branches/test_branch_details_repositories.py::test_import_error_band_links_to_the_task_page` | `True` (was `False` through `BranchAPI.create`'s default; changes #10779's premise) |
| `tests/e2e/branches/test_branches_git_columns.py`, broken-branch case (repository pill, "Import Error") | `True` |
| `tests/e2e/branches/test_branches_git_columns.py`, branch without Git sync | `False`, no fixture repository; reads "Not synced with Git", or lists only read-only repositories when other tests left some |

**Commit on a failed import**: expected to be set. `backend/infrahub/git/base.py` records the commit value when the repository is cloned (`update_commit_value`), before `.infrahub.yml` is read and the import fails. Also to be confirmed live.

**To confirm**: on a running stack, create the broken repository on a `sync_with_git=False` branch and on a `sync_with_git=True` branch, open each branch's details page, and record whether the Git repositories card lists it and whether the repository's `commit` is set on that branch.
