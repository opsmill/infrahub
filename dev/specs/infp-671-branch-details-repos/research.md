# Research: Branch details — Git repositories and tasks

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-29

Code references name the module and symbol. Line numbers are left out on purpose: they drift.

## What is on the base branch (`cross-branch-repo-status-infp-671`)

| Thing the handoff assumes | On this base? | Consequence |
|---|---|---|
| `InfrahubRepositoryBranchStatus` (IFC-3127) | Yes (`backend/infrahub/graphql/queries/repository_branch_status/`) | Anchored on **one** repository across branches. This page needs **every** repository on **one** branch, so it isn't the data source (R1). |
| IFC-3199 header indicator (polls repository counts every 10s) | **No.** No frontend code for it on this base (no `sync_status` query outside the homepage widget, no IFC-3199 commit in `git log`). | Handoff query 4 ("reuse its query keys") has nothing to reuse. This feature defines its own keys (R7). |
| IFC-3200 Git repositories card | **No.** No card in `entities/repository/ui/`. | Build the card once in `entities/repository/ui/branch-repositories/` (spec clarification Q2). |
| IFC-3130 `TablePagination` | **No.** No `shared/components/table/`. | Add it here (R5). |
| Theme tokens / dark mode | **Yes.** `frontend/packages/ui/src/theme/` (provider, switch) and `styles/theme.css` (`danger*`, `warning*`, `success*`, `info*`, `foreground-muted`, `border`, `content*`…). Existing code already uses them (`BranchAttributes` uses `text-foreground-muted`, `TaskDisplay` uses `bg-danger-surface`). | The handoff's "this branch has no theme support" is stale for this base. FR-050 is met with the tokens that exist (R8). |
| Object page body `Card className="to-neutral-50"` | Changed: `ObjectDetailsBody` uses `Card variant="panel"`. | Use `variant="panel"`, not the prototype's class. |

## R1 — Repositories on the branch

**Decision**: One request per page view: the generic object list for `CoreGenericRepository` (or `CoreReadOnlyRepository` when the branch has Sync with Git off), sent with the **page's** branch as the GraphQL branch context (`graphqlClient.query({ context: { branch } })`), selecting `id`, `__typename`, `display_label`, `name { value }`, `commit { value }`, `sync_status { value label color description }`, `operational_status { value label color }`, and `count`. `limit = REPOSITORY_FETCH_LIMIT` (500). Ranking (import error → unreachable → rest, then name) and the 10-row pagination run on the client over that one result.

**Rationale**:
- `sync_status` and `commit` are branch-local/branch-aware attributes (cross-branch spec, Key Entities), so the branch context returns the branch's own values; `operational_status` is branch-agnostic and correct on every branch.
- The rank isn't expressible as server ordering. `OrderInput.by` orders by attribute **value, lexicographically**: `sync_status__value ASC` happens to put `error-import` first, but there's no way to put "unreachable" (`operational_status` in `error-cred|error-connection|error`) second across Git states without a computed field. Two filtered queries (failing, then the rest) would need their own count and page stitching for little gain.
- A branch has tens of repositories in practice; the prototype's worst case is 40. 500 leaves an order of magnitude of headroom. Over the limit, the card says only the first 500 are shown (spec edge case) and links to the repository list.
- On a Sync with Git off branch, read-write repositories don't import, so querying the read-only kind directly is simpler than filtering `__typename` on the client and keeps `count` right.

**Alternatives considered**:
- `InfrahubRepositoryBranchStatus` per repository: N requests, and it answers "one repository, all branches".
- Server-paginated list ordered by `sync_status__value`: loses the unreachable rank, and bands (FR-024) would still need every failing repository, i.e. a second query.
- A new backend field or ordering: out of scope ("only data the backend returns today"). Recorded as a follow-up with the handoff's `rank()` → server ordering note.

**Deviation recorded**: `dev/guidelines/frontend/page-architecture.md` § "Backend is authoritative" puts sort order and pagination on the server. This is a knowing, bounded exception (plan § Complexity Tracking).

## R2 — Latest import task and its last error line

**Decision**: For each failing repository **whose band is rendered** (the first 3; the rest once "Show all" is used), one request:
`InfrahubTask(branch: <page branch>, related_node__ids: [<repo id>], workflow: IMPORT_WORKFLOWS, limit: 1, log_limit: IMPORT_LOG_LIMIT)` selecting `count`, `id`, `state`, `updated_at`, `logs { edges { node { message severity timestamp } } }`.
The band's text is the **last** log whose `severity` is `error` or `critical` (the task manager maps levels 40/50 to those, `task_manager/flow_run/constants.py::LOG_LEVEL_MAPPING`). `IMPORT_LOG_LIMIT = 500`.

`IMPORT_WORKFLOWS` (flow names in `backend/infrahub/git/tasks.py`):
`git-repository-add-read-write`, `git-repository-add-read-only`, `git-repository-import-object`, `git-read-only-repository-import-last-commit`, `git-repository-pull-read-only`, `sync-git-repo-with-origin`.

**Rationale**:
- The task manager returns flow runs newest first (`task_manager/flow_run/reader.py::…read_flow_runs`, `FlowRunSort.START_TIME_DESC`), so `limit: 1` is the latest.
- `log_limit` applies to the **whole request**, across every returned flow run, in ascending time order (`…read_logs`). With `limit: 1` the budget is that one task's; asking for several repositories in one request would let one noisy task starve the others. Hence one request per rendered band, lazily: at most 3 on first render.
- Logs come back oldest first; the error line that ends an import is near the end. 500 lines covers every import log seen in the prototype's real tasks. A longer log degrades to FR-022 ("details couldn't be found"), never to a wrong line.

**Riskiest assumption (brief: "that the frontend can reliably tie a task to a repository")** — verified in code, and it is only partly true:

| Flow | Tags branch | Tags repository |
|---|---|---|
| `git-repository-add-read-write`, `-add-read-only`, `-pull-read-only`, `git-read-only-repository-import-last-commit` | yes | yes (`add_tags(branches=…, nodes=[repository_id])`) |
| `git-repository-import-object` (`import_objects_from_git_repository`) | yes | **no** (`add_branch_tag` only) |
| `sync-git-repo-with-origin` (`sync_git_repo_with_origin_and_tag_on_failure`) | only when `infrahub_branch` is passed | only **on failure** |

> Superseded by "R2 verification results" below: `build_import_plan` tags the running flow with branch + repository, so `git-repository-import-object` and `sync-git-repo-with-origin` are both findable.

`sync_status = error-import` is written by `git/integrator.py::…build_import_plan` / `apply_import_plan` on any import failure, whichever flow ran it. So a repository can be in Import Error while its failing task is invisible to `related_node__ids` (import-object), or tagged with the repository but not the branch (periodic sync).

**Decision on the gap**: Don't guess from `parameters` or titles in the frontend. The band always shows for a repository in Import Error (it comes from `sync_status`, not from the task); when the lookup finds nothing it says the error details couldn't be found and links to the repository (FR-022). A verification task (tasks.md, Phase 1) seeds a failing import through each path and records which ones resolve. Follow-up ticket (backend, small): tag `git-repository-import-object` with the repository id, and `sync-git-repo-with-origin` with the branch it imported; better still, the handoff's `last_import_task` field on the repository.

**Alternatives considered**:
- Match `parameters.model.repository_id` on `InfrahubTask(branch, workflow)` results: reads an untyped `GenericScalar`, couples the UI to Prefect flow parameter shapes, and pages through unrelated tasks. Rejected.
- Dropping `branch` from the filter: returns other branches' imports. Rejected.
- `TaskError`: only filled for webhook tasks (handoff decision). Rejected until IFC-3034.

## R3 — Tasks table

**Decision**: Reuse `entities/tasks/api/get-task-list-from-api.ts::GET_TASK_LIST` (it already has `offset`, `limit`, `branchName`, `count`, `related_nodes`, `title`, `state`, `workflow`, `updated_at`) through a new use case `getBranchTasks({ branchName, offset, limit })` that returns `{ tasks, count }`. `getTaskList` drops `count` and `useGetTaskList` binds to the page-global `usePagination` QSP, so neither fits two independent tables. The failed count reuses `get-task-count` with `state: [FAILED, CRASHED]` and `branchName`.

**Rationale**: Server pagination (`limit`/`offset`, `count`) as the handoff lift sheet asks. Page size 10 is under the task manager's 200 cap. Ordering is the task manager's (start time, newest first).

**Alternatives**: `InfrahubTaskBranchStatus` (only pending/running data-modifying tasks); client slicing of 200 tasks (breaks past 200, wrong count).

## R4 — Freshness

**Decision** (revised by critique P4/E6): the tasks query refetches every 10s **on page 1 only** (`refetchInterval: page === 1 ? 10_000 : false`), and the failed count every 10s. The repositories and import-band queries refetch every 10s **only while a listed repository's `sync_status` is `syncing`** (`refetchInterval: (query) => anySyncing(query.state.data) ? 10_000 : false`; the band queries take the flag from the repositories result), and otherwise on Refresh and window refocus (TanStack's default). Intervals pause in background tabs by default. Today's `TaskDisplay` polls every 5s; 10s matches the cadence IFC-3199 chose for repository state.

## R5 — Table pagination

**Decision**: Add `shared/components/table/table-pagination.tsx` (`TablePagination`) and `shared/utils/table-pagination.ts` (`TABLE_PAGE_SIZE = 10`, `TABLE_ROW_HEIGHT_PX = 40`, `getTotalPages`, `clampPage`, `getPageItems`, `formatPageWindow`), from the prototype's copy of IFC-3130's component, with the prototype's neutral classes replaced by theme tokens and `lucide` chevrons kept (the shared `Icon` token set isn't needed). Unit tests for the utils.

**Rationale**: The existing `shared/components/ui/pagination.tsx::Pagination` is bound to the single `pagination` query-string parameter (`usePagination`) and `react-paginate`; two tables on one page can't each own one. IFC-3130 will land the same file path, so the later merge is a same-path conflict to resolve in favour of IFC-3130, not a second component. The page has two callers (repositories, tasks), satisfying the constitution's "two callers before extracting" rule.

## R6 — Page state in the URL

**Decision**: Two new keys in `shared/config/qsp.ts::QSP`: `REPOSITORIES_PAGE: "repos_page"` and `TASKS_PAGE: "tasks_page"`, read with `nuqs` `parseAsInteger.withDefault(1)` in the Details tab page component (`pages/branches/branch-details/details-tab.tsx`), clamped with `clampPage`, passed down as `page`/`onPageChange`. The card components stay controlled (page-architecture: pages own URL sync). The "Show all" band toggle is local UI state (not shareable).

## R7 — Query keys and Refresh

**Decision**:
- `entities/repository/ui/queries/repository.query-keys.ts::repositoryQueryKeys` (new): `all: ["repositories"]`, `branch: ({ branchName, kind }) => [...all, "branch", branchName, kind]`, `importError: ({ branchName, repositoryId }) => [...all, "import-error", branchName, repositoryId]`.
- `tasksQueryKeys` gains `branchList: ({ branchName, offset, limit }) => [...all, "branch-list", …]`; the failed count keeps `tasksQueryKeys.count(…)`.
- `RefreshButton` (`entities/nodes/object/ui/object-details/refresh-button.tsx`) gains an optional `queryKeys?: ReadonlyArray<readonly unknown[]>`; when set it invalidates each and counts fetching across all (`useIsFetching` with a predicate). The single-key API is unchanged for today's callers. The branch header passes `[branchesQueryKeys.details({ branchName }), repositoryQueryKeys.all, tasksQueryKeys.all]`.

**Rationale**: The page spans three entities with different key roots; a synthetic page-level root would break the documented key shape (`dev/guidelines/frontend/naming-conventions.md`).

## R8 — Theme token mapping (FR-050)

| Prototype | Token |
|---|---|
| red band `bg-red-50`, `border-red-200`, `text-red-900/800/700` | `bg-danger-surface`, `border-danger/30`, `text-danger-strong`, `text-danger` |
| amber band `bg-amber-50`, `border-amber-200`, `text-amber-900/800/700` | `bg-warning-surface`, `border-warning-border`, `text-warning-strong`, `text-warning` |
| Commit tint `#e9f7fa`, icon `#087895` | `bg-info-surface`, `text-info` |
| Git state cell tint `#fff5f5` | dropped (the pill carries the state) |
| `bg-neutral-50` header row, `text-neutral-600`, `border-neutral-200` | `bg-content-muted`, `text-foreground-muted`, `border-border` |
| Skeleton `bg-neutral-200 animate-pulse` | `shared/components/loading/skeleton.tsx::Skeleton` |
| Git state pill colour | schema `sync_status.color` with `getTextColor` (as `entities/homepage/ui/git-repository.tsx`) |
| Task state badges | `entities/tasks/ui/task-display.tsx::getLogBadge` (existing `Badge` variants) |

Exact token names are checked against `frontend/packages/ui/src/styles/theme.css` during implementation; if one is missing, use the nearest existing token, never a hex value.

## R9 — Workflow labels

**Decision**: `entities/tasks/domain/model/workflow-labels.ts::getWorkflowLabel(workflow)` with a static map, raw id as fallback:

| Label | Workflows |
|---|---|
| Import | `IMPORT_WORKFLOWS` (R2) except `sync-git-repo-with-origin` |
| Sync | `sync-git-repo-with-origin`, `git_repositories_sync` |
| Generator | `generator-run`, `generator-definition-run`, `request-generator-definition-run` |
| Artifacts | `artifact-generate`, `artifact-definition-generate`, `request_artifact_definitions_generate`, `git-repository-check-artifact-create` |
| Validate | `branch-validate` (`BRANCH_VALIDATE_WORKFLOW`) |
| Rebase | `branch-rebase` |
| Merge | `merge-branch-mutation`, `branch-merge`, `git-repository-merge` |

It's presentation copy, not a filter, so it doesn't break "backend is authoritative". A backend display name is a follow-up (handoff system gap).

## R10 — Related column

**Decision**: pure function `getTaskRelatedLabel(task, repositoriesById)`: first related node that is a listed repository → its name; no related nodes → "This branch"; otherwise the first node's kind, shown with the schema's label when `useSchema` knows it. Generator child runs are tagged with the definition and target, not the repository, so they show the definition's kind; placing them under a repository through `GeneratorDefinition.repository` is left out (another query per row, and the handoff lists it as a gap).

## R11 — No-permission detection

**Decision**: The repositories use case inspects the GraphQL `errors` array: an error whose `extensions` parse (`shared/api/errors::parseCatalogueError`) to `ERROR_CODES.PERMISSION_DENIED` returns `{ status: "denied" }` instead of throwing; any other error throws (FR-020). The client already doesn't toast 403s (`shared/api/graphql/error-handling.ts`). `useGetObjectPermissions` isn't used: it reads the **current** branch from the branch selector, not the page's branch.

**Verified (critique E4)**: a denied list query errors rather than returning an empty list. `backend/infrahub/graphql/auth/query_permission_checker/object_permission_checker.py::ObjectPermissionChecker` calls `raise_for_permissions` with action `view` for every kind the query touches, so a user without view permission on `CoreGenericRepository` gets `PERMISSION_DENIED` for the whole request, never a silent empty list.

## R12 — Header, tabs, body

**Decision**: `entities/branches/ui/branch-details/branch-details-header.tsx::BranchDetailsHeader` using `entities/nodes/object/ui/object-details/object-details-header.tsx::HeaderContainer`, `CopyToClipboardButton` (with `aria-label="Copy branch name"`), `NodeMetadataPopover`, `BranchDefaultBadge`/`BranchStatusBadge`, `RefreshButton` (R7). `BranchTabs` takes the object tab row classes (`items-end gap-4 px-4`, no bottom border); the body is `Col className="gap-0 p-1"` + `Card variant="panel"` around the `Outlet`, as `ObjectDetailsBody`. `BranchWorkingNotice` is unchanged.

## R13 — Tests

- Unit (vitest): `rankRepositories`, `isRepositoryUnreachable`, `getLastErrorLine`, `getWorkflowLabel`, `getTaskRelatedLabel`, table-pagination utils (including 10/11 boundaries and invalid pages).
- Component (vitest browser, `tests/components/render`): card per scenario fixture (the prototype's `buildData` scenarios, trimmed to real fields: incident/import-error, unreachable, many-errors (40 repos, 5 errors), all-clear, no-repos (Sync off), loading, denied, failed); bands (3 + Show all, not-found fallback); tasks table (loading, empty, failed, 11 rows pagination, title href); header (copy accessible name, refresh keys). Query hooks mocked with `vi.mock`, as `entities/repository/ui/repository-menu-section.test.tsx` does.
- E2E (pytest-playwright, `tests/e2e/branches/test_branch_details.py`): the existing test targets `data-testid="tasks-accordion"`, which goes away; update it to the Tasks card. New: "import error band links to the task page" (handoff), and the card renders on a branch with a repository. Seeding a real failing import in e2e depends on the R2 verification; if it can't be made deterministic, the band-link e2e asserts on a repository seeded in Import Error with a tagged read-only import, and the gap is noted in the PR.

## R2 verification results

**Method**: code reading of this worktree's backend, not a live reproduction. The only running stack belongs to another branch and is read-only, so no repository could be put in Import Error. One read-only `InfrahubTask(state: [FAILED, CRASHED])` query against it confirmed the log shape of a failed flow (see "Last error line" below).

**Correction to the R2 table**: every import goes through `git/integrator.py::InfrahubRepositoryIntegrator.build_import_plan`, whose first graph-facing step is `add_tags(branches=[infrahub_branch_name], nodes=[str(self.id)])`. `add_tags` tags the **current** flow run (`prefect.runtime.flow_run.id`). So every flow that reaches an import is tagged with the branch it imports into and the repository id, whatever the flow tags itself at start. The `InfrahubTask` filter is `tags all_ [namespace, branch/<b>, related_node/<id>]` (`task_manager/flow_run/filters.py`), which these tags satisfy.

| Path | Flow | Found by `branch` + `related_node__ids` + `IMPORT_WORKFLOWS`? | Flow ends Failed with error lines? |
|---|---|---|---|
| Initial add (read-write) | `git-repository-add-read-write` | Yes. Tagged at flow start and again in `build_import_plan`. | Yes. `RepositoryAdder.add` re-raises. |
| Initial add (read-only) | `git-repository-add-read-only` | Yes. Same as above. | Yes. |
| "Import current commit" (`RepositoryProcess` mutation) | `git-repository-import-object` | Yes. The flow only calls `add_branch_tag`, but `build_import_plan` adds the repository tag. The mutation always passes `commit`, so nothing can fail between the flow start and the tag except `get_initialized_repo`, which fails before any `sync_status` is written. | Yes. |
| Read-only pull | `git-repository-pull-read-only` | Yes. Tagged at start. | Yes. |
| Read-only "import last commit" | `git-read-only-repository-import-last-commit` | Yes. Tagged at start. | Yes. |
| Periodic sync (read-write only) | `sync-git-repo-with-origin`, a subflow of `git_repositories_sync` | Yes, per branch. `RepositorySyncer.sync` builds one import per branch with pending changes, and each `build_import_plan` adds that branch's tag to the subflow run. A run that imports several branches carries all their tags. | Yes. Per-branch failures are collected and re-raised as one `RepositoryError` "Unable to synchronize the following branches of repository X: b1 (step=import): …; b2 …". The message can therefore list other branches' failures too. |
| Worker bootstrap (fresh clone inside `git_repositories_sync`) | `git_repositories_sync` | **No.** `bootstrap_local_repository` runs the default-branch import directly in the parent flow. The tags land on `git_repositories_sync`, which is not in `IMPORT_WORKFLOWS`. | **No.** The failure is logged at `info` and swallowed, so the parent flow completes. Adding the workflow to `IMPORT_WORKFLOWS` would not help. |

Read-only repositories are not synced periodically: `git_repositories_sync` only reads `InfrahubKind.REPOSITORY`.

**Last error line**: the `error`/`critical` lines a failed flow ends with are Prefect's own. The live query showed, in this order, `Encountered exception during execution: <Type>('<message>')` followed by a multi-line traceback, then `Finished in state Failed('Flow run encountered an exception: <Type>: <message>')`. The **last** error line is always that `Finished in state Failed(...)` wrapper. It does contain the real cause (the re-raised exception's message), but inside Prefect framing. Integrator `log.error` lines (schema, config, query and object load failures) come earlier in the log, next to the steps that failed. `getLastErrorLine` as specified (T025/T027) will return the wrapper. The cause is readable in it, but unwrapping `Finished in state Failed('Flow run encountered an exception: ` … `')` would read better. That is a design decision for US2, not made here.

**Remaining gap**: the worker-bootstrap import (default branch only, after a worker re-clones) is not findable. The band's FR-022 fallback covers it. Backend ask in `follow-ups.md`.

**T058 seeding**: use the initial add (`git-repository-add-read-write`). On a test branch, create a `CoreRepository` (`CoreRepositoryCreate`, as `tests/e2e/conftest.py` does for `demo-edge`) pointing at a local fixture repo whose default branch has an invalid `.infrahub.yml`. The flow is tagged at its start, fails deterministically and sets `error-import` on that branch. "Import current commit" (`RepositoryProcess` on the branch) is an equally resolvable second option. Avoid periodic sync: its timing isn't deterministic and its message lists every failing branch.
