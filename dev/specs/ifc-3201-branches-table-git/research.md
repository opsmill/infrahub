# Research: Repository, Git state and Commit columns on the branches table

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-30, rework 2026-10-01 (R14), rework A 2026-10-01 (R15)

Code references name the module and symbol; line numbers are left out on purpose. Paths are relative to `frontend/app/` unless stated. Every decision below comes from `plan-synthesis.md`; this file records the reasoning and the code it was checked against.

## What is on the base branch (`ple-branch-details-repos-infp-671`, PR #10779)

| Needed | On this base? | Consequence |
|---|---|---|
| Per-branch repository query, model, pill, ranking | Yes: `entities/repository/ui/queries/get-branch-repositories.query.ts::getBranchRepositoriesQueryOptions`, `domain/model/branch-repository.ts`, `ui/branch-repositories/git-state-pill.tsx::GitStatePill`, `domain/rules/rank-repositories.ts::rankRepositories` | Reused unchanged. |
| Repository fakes | Yes: `tests/fake/branch-repositories.ts` (`SYNC_STATUS`, `OPERATIONAL_STATUS`, `generateBranchRepository`, `generateBranchRepositoriesResult`) | Reused; no extra fake file since R14. |
| `CommitHash` | **No** (PR #10658 only) | Lifted (R8), then dropped with the Commit column (R14). |
| Branches table tests | **None** under `entities/branches/ui/branches-table/` | Both component test files are new. |
| Deterministic import-error E2E fixture | Class-local: `tests/e2e/branches/test_branch_details_repositories.py::TestBranchDetailsRepositoryImportError::broken_repository` | In scope: promoted to `tests/e2e/branches/conftest.py` as a function-scoped fixture with a `sync_with_git` parameter (plan IV). |

## R1 — Selection: the anchor row

Superseded by R14 (2026-10-01): one row per branch uses the base branch's ordinary per-row selection; the anchor row, the `enableRowSelection` predicate and the id-keyed shift-range handler are removed.

## R2 — Fan-out location and layering

Superseded 2026-10-01: the rule and its row model are deleted (R14). Kept as history.

**Decision**: `entities/branches/domain/rules/to-branch-table-rows.ts::toBranchTableRows({ branches, fetchByBranchId, orderRepositories })` does the fan-out. It gets the ordering as an injected parameter. The row types live in `entities/branches/domain/model/branch-table-row.ts`, built on `entities/repository/domain/model/branch-repository.ts`.

**Rationale**: the layering table in `dev/knowledge/frontend/entities-structure.md` puts limits on each layer:

- `domain/rules` may import only its own `domain/model`, `shared/` and generated types. It may not import `repository/domain/rules/rank-repositories.ts`.
- `domain/model` may import other entities' `domain/model`, so the types are legal.

Injecting `orderRepositories` keeps the rule pure and inside its layer. The tests still assert FR-006a on the rule's output, because they pass the real `rankRepositories`. A fan-out inside a cell is impossible, since a cell cannot add rows.

**Alternatives considered**:

- A `ui/` helper. It works, but breaks "pure helpers go in `domain/rules`".
- Placing the rule in `entities/repository`. It produces branches-table rows, so branches owns it.

## R3 — Ordering: `rankRepositories`, and the spec correction

Superseded by R14 (2026-10-01): `rankRepositories` is still the rule, but it now only picks the repository shown first and the worst Git state (spec FR-005) instead of ordering rows.

## R4 — Grid template: fixed tracks for the new columns

Superseded by R14 (2026-10-01): two fixed tracks (`REPOSITORIES_TRACK = "minmax(12rem, 18rem)"`, `GIT_STATE_TRACK = "9rem"`, `repeat(columnCount - 6, …)`) replace the three, and the one-track-per-column test is gone with `branches-data-table.test.tsx`.

## R5 — Data-fetch strategy: (a) one request per branch

Superseded by R15 (2026-10-01): option (b), one `InfrahubRepositoryBranchStatus` request per repository, replaces the per-branch requests; the comparison below is history.

**Decision**: use (a). `useQueries` over `getBranchRepositoriesQueryOptions({ branchName, syncWithGit: Boolean(branch.sync_with_git) })` runs once per loaded branch.

The options compared (P = pages loaded, 40 branches per page, R = number of repositories):

| | Requests | Permissions | Verdict |
|---|---|---|---|
| (a) per branch, #10779 options | 40·P (40, then 80, then 120), independent of R. Plus the existing 40·P proposed-changes queries | A normal node read per branch, so a denial affects only that branch (FR-012) | **Chosen.** Same key as branch details (`repositoryQueryKeys.branch({ branchName, kind })`), so the cache is shared. `syncWithGit=false` queries `CoreReadOnlyRepository` natively |
| (b) `InfrahubRepositoryBranchStatus` per repository, pivoted | 1 + R, flat while scrolling | Needs VIEW with ALLOW_ALL. One denial blanks the whole column | Rejected. It must fetch every branch and join by name, the order and filters don't match the table, and it excludes MERGED branches |
| (c) Backend list-of-ids variant | 1 | Same as (b) | Rejected: needs a backend change, which is out of scope |

**Rationale**: (a) is the only option that meets FR-003 (the backend's per-branch row set), FR-011 (per-branch loading) and FR-012 (per-branch denial) without backend work. Its request count is linear in branches shown, not in repositories.

**Constitution V**: this is an N+1 at the HTTP layer, recorded as a justified deviation in the plan's Complexity Tracking.

**Follow-up**: a backend list-of-ids variant of `InfrahubRepositoryBranchStatus` (option (c); the reader already accepts `repository_ids`). The follow-up ticket is to be created by the owner at the checkpoint. SC-007 is the threshold that bounds the current approach.

## R6 — Hook location

Superseded 2026-10-01: `useBranchTableRows` is deleted; each cell calls `useGetBranchRepositories` directly (R14). Kept as history.

**Decision**: `entities/branches/ui/hooks/use-branch-table-rows.ts::useBranchTableRows(branches): BranchTableRow[]`. It maps each `useQueries` result to a `BranchRepositoriesFetch`: `data` present → `data`; else `isError` → `{ status: "error" }`; else `{ status: "pending" }` (R10). It then calls `toBranchTableRows` with `orderRepositories: rankRepositories`, through a `combine` (R13).

**Rationale**: it produces branches-table rows, so it belongs to branches. `branches/ui` may import `repository/ui/queries` and `repository/domain/rules`.

**Alternatives**: `repository/ui/queries/get-branches-repositories.query.ts`. Rejected because it would couple the repository entity to branches-table row shapes.

## R7 — Extract `RepositoryNameLink`

After R14 the table no longer uses it; whether the extraction stays is the rework implementer's call (reverted). Kept as history.

**Decision**: add `entities/repository/ui/branch-repositories/repository-name-link.tsx::RepositoryNameLink({ repository, branchName, isDefaultBranch })`. It holds the `FolderGitIcon`, a `Link` to `getObjectDetailsUrl(kind, id, [getBranchQspOverride(branchName, isDefaultBranch)])` with `title={name}`, and the "Read-only" chip. `repository-row.tsx::RepositoryRow` uses it and keeps the unreachable icon and the `—` commit fallback. The native `title` stays after review (accepted); aligning it with `Tooltip` is a follow-up.

**Rationale**: FR-006 asks for the same name, link and marker as branch details. Two callers satisfy VII. The existing `branch-repositories-card.test.tsx` is the regression net.

**Alternatives**: copying the markup (it drifts), or reusing `RepositoryRow` (it renders a `<tr>`).

## R8 — Lift `CommitHash`

Superseded by R14 (2026-10-01): the Commit column is dropped, so `CommitHash` has no consumer and is no longer lifted.

## R9 — Polling

Superseded by R15 for the per-branch part: the 10 s poll now runs per status query while one of its rows is syncing, with a 60 s stale time.

**Decision**: keep #10779's `refetchInterval`: 10 s while any repository on that branch has `sync_status = syncing`, otherwise `false`. The options are passed unchanged.

**Rationale**: FR-014 asks for "the cadence already used by the branch details page". Only syncing branches poll, and each stops on settle. Changing the options would split the shared cache key's behaviour.

## R10 — Pending, denied and error rendering

Superseded by R15 for the per-branch part: pending, denied and error now apply to every row at once; the texts, the data-first order and the toast finding stand.

**Decision**: each state renders per branch, and the branch cells always render:

| State | Repositories cell | Git state cell |
|---|---|---|
| `pending` | `Spinner` (the `branch-proposed-changes-cell.tsx` pattern) | blank |
| `denied` (use-case returns `{ status: "denied" }` when every GraphQL error is `PERMISSION_DENIED`) | muted "No permission" | blank |
| `error` (the use-case throws, and no earlier `data` is held) | muted "Could not load repositories", with the query error's message as a tooltip and as visually hidden text | blank |

**Rationale**: FR-011 to FR-013 and SC-005. The query client default is `retry: false` (`shared/api/rest/client.ts::queryClient`), so a failure settles immediately. One spinner per pending branch keeps first paint calm (spec FR-011).

**Mapping order**: the cells read `data` first, then the error, then pending (the hook did so before R14). A failed background refetch (the 10 s syncing poll, or a window refocus) therefore keeps the last loaded result rendered, which is also how #10779's card reads its query.

**Finding (toast)**: the shared GraphQL client routes errors through `shared/api/graphql/error-handling.ts::handleGraphQLErrors`:

- `PERMISSION_DENIED` is skipped, so there is no toast for the denied state.
- Network errors throw without a toast.
- Any other GraphQL error calls `notifyUser`, which toasts, deduplicated by `toastId: "alert-error"`, unless the request context supplies `processErrorMessage`.

`get-branch-repositories-from-api.ts::fetchConnection` passes only `{ branch }`, so FR-013's "no toast" does not hold for GraphQL-level errors. The minimal fix is to pass a no-op `processErrorMessage` in that context. That is a one-line change to a #10779 file, and it also affects the branch details card, which renders its own failed state. **Decision: make the change.** FR-013 is explicit, and a page-level toast for a per-row degraded cell is the wrong surface on both pages. Nothing is lost: the use-case's thrown `Error` joins the backend messages, and the Repositories cell shows that message as the tooltip of "Could not load repositories" (and as visually hidden text). The card's failed state renders the same server message and is asserted to render without a toast.

## R11 — `isTruncated` ignored (superseded 2026-10-01)

Superseded by rework A: the repository list's `isTruncated` and each status page's `count` are both read. A cut repository list reads "Could not load repositories" on every row; a cut status page reads it on the branches that page could have listed (see data-model invariant 4).

## R12 — Remove `React.useMemo`; local fakes

**Decision**: remove `React.useMemo` from `branches-table.tsx::BranchesTable` (`columns`, `flatData`) and from `branches-data-table.tsx::BranchesDataTable` (`style`). The React Compiler memoizes (`dev/knowledge/frontend/react.md`, "React Compiler").

Superseded 2026-10-01 for the fakes: `tests/fake/branch-table-rows.ts` is deleted (R14). The 2026-09-30 decision was that new fakes go in `tests/fake/branch-table-rows.ts`:

- `FULL_COMMIT_HASH`: 40 characters.
- `generateBranchTableRow(overrides)`.

`SYNC_STATUS_NO_COLOUR` (`{ value: "mystery", label: null, color: null, description: null }`) is a constant local to `get-branch-table-columns.test.tsx`, not a shared fake.

That file imports `BranchListItem` from `entities/branches/domain/model/branch`. `tests/fake/branch.ts` keeps its stale `domain/branch.mappers` import, because fixing it would change betterer's results.

**Rationale**: touched files follow the project rule. Local fakes leave #10779's fake file untouched.

**Note (no-colour pill)**: `GitStatePill`'s fallback renders `value || label || "—"`. With `SYNC_STATUS_NO_COLOUR` it shows `mystery` in a grey `Badge`. FR-004 ("the label or value") and the spec's value-first edge case are met; tests assert what the pill renders.

## R13 — Per-branch row reuse with `combine`

Superseded by R14 (2026-10-01): with no table-level `useQueries` there is no `combine`; the structural-sharing finding is kept in `dev/knowledge/frontend/react.md`.

## R14 — Why one row per branch

Superseded by R15 for the per-branch data path (cells calling `useGetBranchRepositories`); one row per branch, the roll-up and the measurements stand.

**Decision** (owner, 2026-10-01, after trying the fan-out on a dev stack): the list goes back to one row per branch. The Repositories cell shows the first repository in `rankRepositories` order (failed imports first) as a pill, then "+N more" linking to the branch details page; the Git state cell shows that repository's pill (the worst state) with an `n/N` count and a per-label tooltip. The Commit column is dropped; the commit is in the pill's tooltip and on the branch details page. Each cell reads #10779's `useGetBranchRepositories`, one request per branch shared by key.

**Measurements** (24 branches × 16 repositories): the fan-out rendered 279 rows, 280 checkboxes, about 15 000 DOM nodes and about 200 console warnings, and was visibly slow. The 24 per-branch repository requests completed in 0.36 s in total, so the cost was rendering, not fetching. The ticket's "one row per repository" assumed one or two repositories per branch.

**Single-request finding**: one request for every branch is not available today. Aliasing 16 `InfrahubRepositoryBranchStatus` fields (one per repository) into one GraphQL document returns HTTP 500 `read() called while another coroutine is already waiting for incoming data`, and `Branch` has no repositories field. The backend follow-up is either a `repository_ids` list argument on `InfrahubRepositoryBranchStatus` or a fix to the concurrent-resolver path that the aliased document hits.

**Consequences**: R1, R3, R4, R8 and R13 are superseded; R2 and R6 (the fan-out rule and the table hook) have no code left; R5's per-branch strategy stood, now measured, until R15 replaced it.

**Alternatives considered**: a stacked cell listing every repository, which the ticket rules out ("no stacking inside a cell") and whose height grows with the repository count. The roll-up follows the Proposed changes cell's existing "first item + N more" pattern instead.

## R15 — Repository-anchored data, page-owned

**Decision** (owner, 2026-10-01, after the architecture review of the R14 implementation): the list reads the epic's `InfrahubRepositoryBranchStatus` once per repository, on the default branch, and pivots the rows to one `BranchRepositorySummary` per branch name in the branches domain (`summarizeBranchRepositories`). The page owns the fetch (`useGetBranchRepositorySummaries`, `useQueries` + `combine`), the summary rides on the row view-model (`BranchTableRow`), and the cells are pure. Repositories are ranked by Git state severity (`compareSyncStatusSeverity`: `error-import` > `unknown` > `syncing` > `in-sync`, then name). Requests: 1 + R, independent of pages loaded; a 60 s `staleTime` caps the refocus burst.

**Why**: the R14 implementation had three defects.

1. The cells owned and duplicated the data and its derivation: two cells ran the same query and the same ranking, and the derivation lived in `.tsx`, out of reach of pure tests.
2. The roll-up reused the details card's band ordering (`rankRepositories`), which ranks an unreachable remote above every other non-failed repository. An unreachable repository whose last import succeeded therefore came first, and the Git state cell read "In Sync" while another repository on the branch was syncing or unknown. Severity on `sync_status` alone fixes it.
3. The per-branch query mirrored the backend's row-set rule on the client (`getRepositoryListKind`: `CoreGenericRepository` when synced, `CoreReadOnlyRepository` otherwise), the rule the epic's query exists to keep server-side (FR-003).

**Consequences**: one failure blanks the column for every row; a denial does so when the repository list is denied (it reads both kinds in one query) or when every status read is denied, and a single denied status read leaves that repository out silently; merged branches read "No repositories"; the cache is no longer shared with the branch details page; the commit of a fresh synced branch is the fork-point commit. R5's option (b) is now chosen, and its rejection reasons (ALLOW_ALL, whole-column denial, join by name) are accepted as spec consequences.

**Alternatives considered**: keeping per-branch requests but lifting them into a table hook (fixes defect 1 only); one aliased document over every repository (HTTP 500 today, R14). The backend `repository_ids` follow-up collapses 1 + R to 2 requests without touching cells or rules.

## Risks

1. The GraphQL-level error toast (R10) is closed by the no-op `processErrorMessage` on the details card's fetcher; the list asserts no toast on a status error (`branches-table.test.tsx`).
2. ~~Unreachable repositories rank up without the reason shown.~~ Superseded by R15: severity ignores operational status.
3. ~~≈40 queries per page (N+1 over HTTP).~~ Superseded by R15: 1 + R requests.
4. `isTruncated` is ignored, so a truncated list is silently partial (R11).
5. The page's reload button refreshes branch queries and repository status; its busy indicator covers that reload only, not background polls.
6. ~~Pending → N rows pushes lower branches down.~~ Superseded 2026-10-01: one row per branch.
7. The PR touches #10779 files (fetcher no-op, card message, E2E fixture; `RepositoryNameLink`: reverted; `repository-row.tsx` is back to base. ~~It changes the shared toggle handler.~~ Superseded 2026-10-01: the handler is back to base.
8. ~~Anchor selection relies on row order.~~ Superseded 2026-10-01 (R1).
9. E2E is in scope: one `/branches` case over the `broken_repository` fixture promoted from `test_branch_details_repositories.py` to `tests/e2e/branches/conftest.py` (plan IV). The fixture's branch is created with `sync_with_git=False` today, so the branch details test's premise is verified on a live stack first (plan IV pre-step).

## E2E premise verification

**Status**: code-derived expectation, to be confirmed on a live stack (T032 ⚠️ partial: no stack was available in the implementing run).

**Expectation**: the branch details card lists repositories through `entities/repository/domain/use-cases/get-branch-repositories.ts::getRepositoryListKind(syncWithGit)`; since R15 the `/branches` list reads the status rows instead, whose backend row set gives the same answer. `getRepositoryListKind(false)` returns `CoreReadOnlyRepository`, so a `sync_with_git=False` branch lists only read-only repositories and its card should NOT list the broken `CoreRepository` the fixture creates. `getRepositoryListKind(true)` returns `CoreGenericRepository`, which includes it.

**Consequence for the E2E cases**:

| Test | `sync_with_git` |
|---|---|
| `tests/e2e/branches/test_branch_details_repositories.py::test_import_error_band_links_to_the_task_page` | `True` (was `False` through `BranchAPI.create`'s default; changes #10779's premise) |
| `tests/e2e/branches/test_branches_git_columns.py`, broken-branch case (repository pill, "Import Error") | `True` |
| `tests/e2e/branches/test_branches_git_columns.py`, "Not synced with Git" case | `False`, no fixture repository |

**Commit on a failed import**: expected to be set. `backend/infrahub/git/base.py` records the commit value when the repository is cloned (`update_commit_value`), before `.infrahub.yml` is read and the import fails. Also to be confirmed live.

**To confirm**: on a running stack, create the broken repository on a `sync_with_git=False` branch and on a `sync_with_git=True` branch, open each branch's details page, and record whether the Git repositories card lists it and whether the repository's `commit` is set on that branch.
