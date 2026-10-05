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

> **Superseded 2026-10-02** by § "Restructure (2026-10-02)" D1–D2: one server page ordered by name, plus a server-filtered failing/syncing query. The failing-first rank is dropped from the table; the bands carry it. The deviation from "backend is authoritative" recorded below no longer exists.


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

> **Amended 2026-10-02** by § "Restructure (2026-10-02)" D3: the lookup asks for the newest **failed** (`FAILED`, `CRASHED`) import, not the newest import, and the log is a second request keyed on the task id, fetched once.


**Decision**: For each failing repository **whose band is rendered** (the first 3; the rest once "Show all" is used), one request:
`InfrahubTask(branch: <page branch>, related_node__ids: [<repo id>], workflow: IMPORT_WORKFLOWS, limit: 1, log_limit: IMPORT_LOG_LIMIT)` selecting `count`, `id`, `state`, `updated_at`, `logs { edges { node { message severity timestamp } } }`.
The band's text is the **last** log whose `severity` is `error` or `critical` (the task manager maps levels 40/50 to those, `task_manager/flow_run/constants.py::LOG_LEVEL_MAPPING`). `IMPORT_LOG_LIMIT = 10_000`, the backend cap (`task_manager/flow_run/reader.py::NB_LOGS_LIMIT`).

`IMPORT_WORKFLOWS` (flow names in `backend/infrahub/git/tasks.py`):
`git-repository-add-read-write`, `git-repository-add-read-only`, `git-repository-import-object`, `git-read-only-repository-import-last-commit`, `git-repository-pull-read-only`, `sync-git-repo-with-origin`.

**Rationale**:
- The task manager returns flow runs newest first (`task_manager/flow_run/reader.py::…read_flow_runs`, `FlowRunSort.START_TIME_DESC`), so `limit: 1` is the latest.
- `log_limit` applies to the **whole request**, across every returned flow run, in ascending time order (`…read_logs`). With `limit: 1` the budget is that one task's; asking for several repositories in one request would let one noisy task starve the others. Hence one request per rendered band, lazily: at most 3 on first render.
- Logs come back oldest first, with no ordering or "last N" option, and the `logs.count` field is the number returned, not the total, so there's no way to read only the tail. The error line that ends an import is near the end, so the limit is the backend cap: a lower one (the first draft used 500) would cut that line off a long log and show an earlier error, or none. The backend reads logs in batches of 200 and stops at the last one, so a short log still costs one call. A log past 10,000 lines can still lose its tail; see follow-ups.md.

**Riskiest assumption (brief: "that the frontend can reliably tie a task to a repository")** — verified in code, and it is only partly true:

| Flow | Tags branch | Tags repository |
|---|---|---|
| `git-repository-add-read-write`, `-add-read-only`, `-pull-read-only`, `git-read-only-repository-import-last-commit` | yes | yes (`add_tags(branches=…, nodes=[repository_id])`) |
| `git-repository-import-object` (`import_objects_from_git_repository`) | yes | **no** (`add_branch_tag` only) |
| `sync-git-repo-with-origin` (`sync_git_repo_with_origin_and_tag_on_failure`) | only when `infrahub_branch` is passed | only **on failure** |

> Superseded by "R2 verification results" below: `build_import_plan` tags the running flow with branch + repository, so `git-repository-import-object` and `sync-git-repo-with-origin` are both findable.

`sync_status = error-import` is written by `git/integrator.py::…build_import_plan` / `apply_import_plan` on any import failure, whichever flow ran it. The first draft concluded from the table above that import-object and periodic-sync failures could be invisible to `branch` + `related_node__ids` + `IMPORT_WORKFLOWS`. They are not: `build_import_plan` tags the running flow with the branch and the repository before anything that writes `sync_status`, so both are findable (see "R2 verification results"). What stays unfindable is a failure before that `add_tags` call, which writes no `sync_status`, and the worker-bootstrap import inside `git_repositories_sync`.

**Decision on the gap**: Don't guess from `parameters` or titles in the frontend. The band always shows for a repository in Import Error (it comes from `sync_status`, not from the task); when the lookup finds nothing it says the error details couldn't be found and links to the repository (FR-022). A verification task (tasks.md, Phase 1) seeds a failing import through each path and records which ones resolve. Follow-up ticket (backend, small): tag `git-repository-import-object` with the repository id, and `sync-git-repo-with-origin` with the branch it imported; better still, the handoff's `last_import_task` field on the repository.

**Alternatives considered**:
- Match `parameters.model.repository_id` on `InfrahubTask(branch, workflow)` results: reads an untyped `GenericScalar`, couples the UI to Prefect flow parameter shapes, and pages through unrelated tasks. Rejected.
- Dropping `branch` from the filter: returns other branches' imports. Rejected.
- `TaskError`: only filled for webhook tasks (handoff decision). Rejected until IFC-3034.

## R3 — Tasks table

**Decision**: Reuse `entities/tasks/api/get-task-list-from-api.ts::GET_TASK_LIST` (it already has `offset`, `limit`, `branchName`, `count`, `related_nodes`, `title`, `state`, `workflow`, `updated_at`) through a new use case `getBranchTasks({ branchName, offset, limit })` that returns `{ tasks, count }`. `getTaskList` drops `count` and `useGetTaskList` binds to the page-global `usePagination` QSP, so neither fits two independent tables. The failed count reuses `get-task-count` with `state: [FAILED]` and `branchName`: the Tasks page filter takes a single state, so counting CRASHED too would show a number its link can't open.

**Rationale**: Server pagination (`limit`/`offset`, `count`) as the handoff lift sheet asks. Page size 10 is under the task manager's 200 cap. Ordering is the task manager's (start time, newest first).

**Alternatives**: `InfrahubTaskBranchStatus` (only pending/running data-modifying tasks); client slicing of 200 tasks (breaks past 200, wrong count).

## R4 — Freshness

> **Amended 2026-10-02**: the syncing flag comes from the health query's server-filtered `syncing` count (`isAnyRepositorySyncing`), not from scanning the fetched list; the tasks query polls when `offset === 0`; a task's log is never polled.


**Decision** (revised by critique P4/E6): the tasks query refetches every 10s **on page 1 only** (`refetchInterval: page === 1 ? 10_000 : false`), and the failed count every 10s. The repositories and import-band queries refetch every 10s **only while a listed repository's `sync_status` is `syncing`** (`refetchInterval: (query) => anySyncing(query.state.data) ? 10_000 : false`; the band queries take the flag from the repositories result), and otherwise on Refresh and window refocus (TanStack's default). Intervals pause in background tabs by default. Today's `TaskDisplay` polls every 5s; 10s matches the cadence IFC-3199 chose for repository state.

## R5 — Table pagination

> **Superseded 2026-10-02** by § "Restructure (2026-10-02)" D4: IFC-3130's `table-pagination.tsx`, `table-pagination.ts`, `use-table-pagination.ts` and `CELL_HEIGHT_PX` are taken verbatim; `TABLE_PAGE_SIZE`, `TABLE_ROW_HEIGHT_PX` and the lucide chevrons are gone.


**Decision**: Add `shared/components/table/table-pagination.tsx` (`TablePagination`) and `shared/utils/table-pagination.ts` (`TABLE_PAGE_SIZE = 10`, `TABLE_ROW_HEIGHT_PX = 40`, `getTotalPages`, `clampPage`, `getPageItems`, `formatPageWindow`), from the prototype's copy of IFC-3130's component, with the prototype's neutral classes replaced by theme tokens and `lucide` chevrons kept (the shared `Icon` token set isn't needed). Unit tests for the utils.

**Rationale**: The existing `shared/components/ui/pagination.tsx::Pagination` is bound to the single `pagination` query-string parameter (`usePagination`) and `react-paginate`; two tables on one page can't each own one. IFC-3130 will land the same file path, so the later merge is a same-path conflict to resolve in favour of IFC-3130, not a second component. The page has two callers (repositories, tasks), satisfying the constitution's "two callers before extracting" rule.

## R6 — Page state in the URL

> **Superseded 2026-10-02** by § "Restructure (2026-10-02)" D4–D5: each card owns its page through `useTablePagination` (`repositories_page`, `tasks_page`), and `useCountClampedQuery` clamps it in the data hook instead of `usePageInRange` writing it back from an effect.


**Decision**: Two new keys in `shared/config/qsp.ts::QSP`: `REPOSITORIES_PAGE: "repos_page"` and `TASKS_PAGE: "tasks_page"`, read with `nuqs` `parseAsInteger.withDefault(1)` in the Details tab page component (`pages/branches/branch-details/details-tab.tsx`), clamped with `clampPage`, passed down as `page`/`onPageChange`. The card components stay controlled (page-architecture: pages own URL sync). The "Show all" band toggle is local UI state (not shareable).

## R7 — Query keys and Refresh

> **Amended 2026-10-02**: the root is `["repository"]` (IFC-3130 and IFC-3199's), keys are `branchRepositories`, `branchHealth`, `importTask`, `importLog`, `names` next to IFC-3199's `syncHealth`; `RefreshButton` has a single `queryKeys` prop and scopes its last-update time to those keys.


**Decision**:
- `entities/repository/ui/queries/repository.query-keys.ts::repositoryQueryKeys` (new): `all: ["repositories"]`, `branch: ({ branchName, kind }) => [...all, "branch", branchName, kind]`, `importError: ({ branchName, repositoryId }) => [...all, "import-error", branchName, repositoryId]`.
- `tasksQueryKeys` gains `branchList: ({ branchName, offset, limit }) => [...all, "branch-list", …]`; the failed count keeps `tasksQueryKeys.count(…)`.
- `RefreshButton` (`entities/nodes/object/ui/object-details/refresh-button.tsx`) gains an optional `queryKeys?: ReadonlyArray<readonly unknown[]>`; when set it invalidates each and counts fetching across all (`useIsFetching` with a predicate). The single-key API is unchanged for today's callers. The branch header passes `[branchesQueryKeys.all, repositoryQueryKeys.all, tasksQueryKeys.all]`: `branchesQueryKeys.all` rather than `.details({ branchName })`, because the header and the action buttons read other branch queries too.

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

> **Amended 2026-10-02**: the maps stay in `domain/model/workflow-labels.ts` (vocabulary); `getWorkflowLabel` moves to `domain/rules/get-workflow-label.ts` (a pure function).


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

> **Amended 2026-10-02**: the names come from a small `CoreGenericRepository(ids: …)` query over the page's related node ids (§ "Restructure (2026-10-02)" D6), not from the repositories card's list.


**Decision**: pure function `getTaskRelatedLabel(task, repositoriesById)`: first related node that is a listed repository → its name; no related nodes → "This branch"; otherwise the first node's kind, shown with the schema's label when `useSchema` knows it. Generator child runs are tagged with the definition and target, not the repository, so they show the definition's kind; placing them under a repository through `GeneratorDefinition.repository` is left out (another query per row, and the handoff lists it as a gap).

## R11 — No-permission detection

> **Amended 2026-10-02**: the api layer no longer imports `CombinedError`; the use case reads the code with IFC-3130's `hasThrownCatalogueCode` and rejects with `BranchRepositoriesError("PERMISSION_DENIED")`. The state stays: see D7 below.


**Decision**: The repositories use case inspects the GraphQL `errors` array: an error whose `extensions` parse (`shared/api/errors::parseCatalogueError`) to `ERROR_CODES.PERMISSION_DENIED` returns `{ status: "denied" }` instead of throwing; any other error throws (FR-020). The client already doesn't toast 403s (`shared/api/graphql/error-handling.ts`). `useGetObjectPermissions` isn't used: it reads the **current** branch from the branch selector, not the page's branch.

**Verified (critique E4)**: a denied list query errors rather than returning an empty list. `backend/infrahub/graphql/auth/query_permission_checker/object_permission_checker.py::ObjectPermissionChecker` calls `raise_for_permissions` with action `view` for every kind the query touches, so a user without view permission on `CoreGenericRepository` gets `PERMISSION_DENIED` for the whole request, never a silent empty list.

## R12 — Header, tabs, body

**Decision**: `entities/branches/ui/branch-details/branch-details-header.tsx::BranchDetailsHeader` using `entities/nodes/object/ui/object-details/object-details-header.tsx::HeaderContainer`, `CopyToClipboardButton` (with `aria-label="Copy branch name"`), `NodeMetadataPopover`, `BranchDefaultBadge`/`BranchStatusBadge`, `RefreshButton` (R7). `BranchTabs` takes the object tab row classes (`items-end gap-4 px-4`, no bottom border); the body is `Col className="gap-0 p-1"` + `Card variant="panel"` around the `Outlet`, as `ObjectDetailsBody`. `BranchWorkingNotice` is unchanged.

## R13 — Tests

- Unit (vitest): `rankRepositories` _(removed 2026-10-02, restructure R003; the failure rules are in `repository-failures.ts`)_, `isRepositoryUnreachable`, `getLastErrorLine`, `getWorkflowLabel`, `getTaskRelatedLabel`, table-pagination utils (including 10/11 boundaries and invalid pages).
- Component (vitest browser, `tests/components/render`): card per scenario fixture (the prototype's `buildData` scenarios, trimmed to real fields: incident/import-error, unreachable, many-errors (40 repos, 5 errors), all-clear, no-repos (Sync off), loading, denied, failed); bands (3 + Show all, not-found fallback); tasks table (loading, empty, failed, 11 rows pagination, title href); header (copy accessible name, refresh keys). Query hooks mocked with `vi.mock`, as `entities/repository/ui/repository-menu-section.test.tsx` does.
- E2E (pytest-playwright, `tests/e2e/branches/test_branch_details.py`): the existing test targets `data-testid="tasks-accordion"`, which goes away; update it to the Tasks card. New: "import error band links to the task page" (handoff), and the card renders on a branch with a repository. Seeding a real failing import in e2e depends on the R2 verification; if it can't be made deterministic, the band-link e2e asserts on a repository seeded in Import Error with a tagged read-only import, and the gap is noted in the PR.

## R2 verification results

> **Correction 2026-10-05**: the seeded stack (`scenarios/`) contradicts the periodic-sync row below. A failed `sync-git-repo-with-origin` run was tagged with the default branch only, so `InfrahubTask(branch: <other branch>, related_node__ids: [<repo>])` found nothing and the band showed its fallback. The cause is not traced (follow-ups.md). The same stack found the "Import current commit" task on a non-default branch. The other rows are still verified by code reading only (tasks.md T001).

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

**Decision (US2)**: `getLastErrorLine` still picks the last `error`/`critical` line, but when it is Prefect's `Finished in state <State>(<repr>)` wrapper the UI unwraps it (Python repr unescaped, `Flow run encountered an exception: ` prefix dropped) and shows `<Type>: <message>`; a wrapper that unwraps to nothing, or any other line, is shown as is.

**Remaining gap**: the worker-bootstrap import (default branch only, after a worker re-clones) is not findable. The band's FR-022 fallback covers it. Backend ask in `follow-ups.md`.

**T058 seeding**: use the initial add (`git-repository-add-read-write`). On a test branch, create a `CoreRepository` (`CoreRepositoryCreate`, as `tests/e2e/conftest.py` does for `demo-edge`) pointing at a local fixture repo whose default branch has an invalid `.infrahub.yml`. The flow is tagged at its start, fails deterministically and sets `error-import` on that branch. "Import current commit" (`RepositoryProcess` on the branch) is an equally resolvable second option. Avoid periodic sync: its timing isn't deterministic and its message lists every failing branch.

## Restructure (2026-10-02)

An architecture review of PR #10779, accepted by the owner, changed the data design and the shared pieces. The UX and the copy stay; the one visible change is that failing repositories no longer sort first in the table.

**D1 — Server page for the table.** `CoreGenericRepository` (or `CoreReadOnlyRepository` when Sync with Git is off) with `limit`, `offset`, `count` and `order: { by: [{ field: "name__value", direction: ASC }] }`. The review's point: page-architecture puts sort and pagination on the server, and the bands already put failures in front of the reader, so the table doesn't need to rank. Empty states read `count`.

**D2 — Server filter for the bands and for polling.** One request with three aliased lists: `importErrors` (`sync_status__values: ["error-import"]`), `unreachable` (`operational_status__values: [error-cred, error-connection, error]`) and `syncing` (`sync_status__values: ["syncing"]`, count only). GraphQL can't OR two attribute filters, so the two failing lists are deduplicated by `getFailingRepositories` (import error wins). This is IFC-3199's approach (`get-repository-sync-counts-from-api.ts` aliases filtered counts), with typed documents instead of `jsonToGraphQLQuery`. Bands are independent of the table page. `isAnyRepositorySyncing(health)` is the one polling decision, computed once in the card.

**D3 — Failed import lookup.** `InfrahubTask(branch, related_node__ids: [repo], workflow: IMPORT_WORKFLOWS, state: [FAILED, CRASHED], limit: 1)` gives the newest failed import (`state` is a `[StateType]` argument on `InfrahubTask`). The log is a second request, `InfrahubTask(ids: [taskId], log_limit: IMPORT_LOG_LIMIT)`, keyed on the task id with `staleTime: Infinity` and no polling: a finished task's log doesn't change, so polling re-asks only for the task id and refetches the log only when it changes. Hidden bands aren't mounted, so logs are fetched for shown bands only. `IMPORT_LOG_LIMIT` stays: logs still come oldest first.

Tasks that fail **before the run is tagged with the repository** stay unfindable. Checked in the backend:

- `git-repository-import-object` (`import_objects_from_git_repository`) tags only the branch at start; the repository tag comes from `InfrahubRepositoryIntegrator.build_import_plan`, after `get_initialized_repo`. A failure in between leaves a run with no repository tag.
- `sync-git-repo-with-origin` adds the repository tag on failure only when the repository was `online` before the sync; `build_import_plan` adds it otherwise, but the seeded stack showed periodic-sync failures tagged with `main` only (follow-ups.md).

The frontend could match `parameters.model.repository_id` on untagged runs, since `TaskNode.parameters` is exposed. Rejected as in R2: it reads an untyped `GenericScalar`, couples the UI to each flow's parameter shape (`model.repository_id` for import-object, a top-level `repository_id` for the sync) and pages through unrelated failed tasks on the client. The "details couldn't be found" fallback stays, and follow-ups.md asks the backend to tag the repository at the start of every repository flow.

**D4 — IFC-3130's shared pieces, verbatim.** `shared/utils/table-pagination.ts` (+ test), `shared/hooks/use-table-pagination.ts` (+ test), `shared/components/table/style.tsx` (`CELL_HEIGHT_PX`), `shared/api/graphql/error-handling.ts` (`hasThrownCatalogueCode`) and `shared/components/table/table-pagination.tsx` (+ test) come from `ple-branches-card-ifc-3130`. Two additive differences in `TablePagination`, which must also land in IFC-3130: the `aria-label` prop and `focusVisibleStyle` on its buttons (plus one test). `TABLE_ROW_HEIGHT_PX` is IFC-3130's `CELL_HEIGHT_PX`, same value.

**D5 — Clamping without an effect.** IFC-3130's `useTablePagination` doesn't clamp; its card writes the clamped page back from an effect, and IFC-3200 plans a `clampToCount` on the hook. This PR adds `shared/hooks/use-count-clamped-query.ts`: the data hook asks for the requested page, and when the server's count says it is past the end, asks for the last real page with a second observer. Both cards use it. The URL keeps the out-of-range number until the next page change, which the review accepted (react.md: no effect-driven redirects).

**D6 — Related names by id.** The Tasks card used to get repository names from a second `useGetBranchRepositories` call in `BranchDetails`. It now asks `CoreGenericRepository(ids: …)` for the related node ids of the page shown (≤ 10 tasks). Chosen over the kind label plus a link because it keeps today's copy, and over `useNodeLabel` per row because it is one request per page instead of one per node.

**D7 — Permission denied is real.** `ObjectPermissionChecker.check` calls `raise_for_permissions` with `view` for every kind the query reads, so a user without view permission on the repository kinds gets `PERMISSION_DENIED` for the whole request. Rows are never silently dropped. IFC-3200's critique E3 ("a permission-restricted repository is simply an absent row") doesn't match this code; the denied state stays, now based on that catalogue code.

**D8 — Tables stay hand-written.** IFC-3130 builds its card on `DataTable` with a `semanticTable` mode, `gridTemplateColumns`, skeleton props and a reworked `ObjectTableSkeleton`, none of which are on this base. Taking them means taking IFC-3130's 107-line `data-table.tsx` change while it is still under review, and the grid cells' borders and sticky columns would change this card's look, which the review keeps. IFC-3200's plan-synthesis also declines a shared `PaginatedTable` until a third consumer. The two tables stay plain `<table>`s; `TasksTable` drops its one-caller column API so IFC-3245 can generalise it.

**D9 — URL keys.** `useTablePagination({ urlKey: "repositories" })` and `({ urlKey: "tasks" })` give `repositories_page` and `tasks_page`. `repos_page` links stop working; they never shipped (this PR is unmerged), so no alias is kept.

**D10 — Test fixture root cause.** `test_import_error_band_links_to_the_task_page` failed twice in CI because `BranchAPI.create` defaults to `sync_with_git=False`: the card listed read-only repositories only and showed "Not synchronised with Git" (count 0), so the fixture's `CoreRepository` never got a row. Not a product bug under the current rule; the test now creates a Sync-with-Git branch and asserts on the band. The case does show that a `CoreRepository` created on a Sync-off branch still imports there (it reached `error-import`), so that empty state's "imports don't run on it" isn't always true. Raised for the owner in tasks.md.
