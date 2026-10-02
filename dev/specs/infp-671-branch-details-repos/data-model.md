# Data Model: Branch details — Git repositories and tasks

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Frontend-only. No schema, no migration, no new GraphQL field. These are the **domain** shapes the entity layer maps API results into (`entities/<entity>/domain/model/`), and the pure rules over them (`domain/rules/`).

The repositories table is one server page ordered by name. A separate health query filters failing and syncing repositories on the server, independent of the page; each failing list stops at `REPOSITORY_HEALTH_LIST_LIMIT` (50) and carries the server's count. The decisions are in research.md § "Restructure (2026-10-02)".

## BranchRepository (`entities/repository/domain/model/branch-repository.ts`)

One repository as seen from one branch.

| Field | Type | Source | Notes |
|---|---|---|---|
| `id` | `string` | node `id` | |
| `kind` | `"CoreRepository" \| "CoreReadOnlyRepository"` | `__typename` | any type other than `CoreReadOnlyRepository` is normalised to `CoreRepository`; never `CoreGenericRepository` |
| `name` | `string` | `name.value`, fallback `display_label`, fallback `id` | |
| `isReadOnly` | `boolean` | `kind === READONLY_REPOSITORY_KIND` | drives the "Read-only" tag |
| `commit` | `string \| null` | `commit.value` on the branch | `null` → empty-value placeholder |
| `syncStatus` | `{ value: string \| null; label: string \| null; color: string \| null; description: string \| null }` | `sync_status` (Dropdown) on the branch | rendered from the schema's label/colour; raw value in a neutral tag when label/colour are missing |
| `operationalStatus` | `{ value: string \| null; label: string \| null }` | `operational_status` (Dropdown), branch-agnostic | |

The wire → domain mapping is `toBranchRepository` / `toBranchRepositories` in `api/branch-repository.mappers.ts` (entities-structure: mappers live in `api/`).

```ts
interface BranchRepositoryPage {
  repositories: BranchRepository[]; // one server page, ordered by name
  count: number;                    // the server's total, which drives the badge, the pager and the empty states
}

interface BranchRepositoryHealth {
  importErrors: BranchRepository[]; // sync_status__values: ["error-import"], ordered by name, at most 50
  importErrorCount: number;         // the server's total for that filter
  unreachable: BranchRepository[];  // operational_status__values: REPOSITORY_OPERATIONAL_ERRORS, ordered by name, at most 50
  unreachableCount: number;         // the server's total for that filter
  syncingCount: number;             // sync_status__values: ["syncing"], count only
}

type BranchRepositoriesErrorCode = "PERMISSION_DENIED" | "UNKNOWN";
class BranchRepositoriesError extends Error { readonly code: BranchRepositoriesErrorCode }

type RepositoryImportError =
  | { status: "found"; taskId: string; message: string }
  | { status: "not-found"; taskId: string | null }; // no failed task, or no error-level line
```

### Vocabulary (`domain/model/repository.ts`)

- `REPOSITORY_SYNC_STATUS_ERROR_VALUE = "error-import"`, `REPOSITORY_SYNC_STATUS_SYNCING = "syncing"`
- `REPOSITORY_OPERATIONAL_ERRORS = ["error-cred", "error-connection", "error"] as const`
- `IMPORT_WORKFLOWS` (research R2), `IMPORT_FAILED_TASK_STATES = [FAILED, CRASHED]`
- `IMPORT_LOG_LIMIT = 10_000` (backend cap; still needed because logs come oldest first)
- `MAX_VISIBLE_BANDS = 3`

### Rules (`entities/repository/domain/rules/`)

- `getRepositoryListKind(syncWithGit)` (`get-repository-list-kind.ts`) — `CoreReadOnlyRepository` when Sync with Git is off, else `CoreGenericRepository`. The GraphQL kind both queries list; not `BranchRepository.kind`.
- `hasImportError(repo)`, `isRepositoryUnreachable(repo)` (`repository-failures.ts`) — `unknown` and `online` are not failing.
- `getFailingRepositories(health)` — the band list: `importErrors`, then `unreachable` minus any already listed as an import error (one band per repository, import error wins: spec US2 scenario 5). Server order (name) within each group.
- `countUnlistedFailures(health)` — failing repositories past the list limit (`importErrorCount + unreachableCount` minus the listed rows); the bands summary adds them as "and N more".
- `getBandKind(repo): "import-error" | "unreachable"`.
- `isAnyRepositorySyncing(health)` (`is-any-repository-syncing.ts`) — `syncingCount > 0`. The single polling decision for the page query, the health query and the band lookups.
- `getLastErrorLine(logs): string | null` (`get-last-error-line.ts`) — last log with `severity` `error` or `critical`, verbatim, except Prefect's final-state wrapper `Finished in state <State>('…'[, type=<TYPE>])`, which is unwrapped to the exception it carries. A stopgap until `TaskError` is filled for git imports (IFC-3034; follow-ups.md).

### Use cases (`entities/repository/domain/use-cases/`)

- `getBranchRepositories({ branchName, syncWithGit, limit, offset }) → BranchRepositoryPage`. Rejects with `BranchRepositoriesError("PERMISSION_DENIED")` when the GraphQL error carries that catalogue code (read with `hasThrownCatalogueCode`), else `"UNKNOWN"`.
- `getBranchRepositoryHealth({ branchName, syncWithGit }) → BranchRepositoryHealth`.
- `getRepositoryImportTask({ branchName, repositoryId }) → string | null` — the newest FAILED or CRASHED import task's id. A failed lookup returns `null` (the band never disappears).
- `getImportTaskErrorMessage(taskId) → string | null` — `getLastErrorLine` over that task's log.
- `getRepositoryNames({ branchName, ids }) → Record<string, string>` — for the Tasks card's Related column; ids that aren't repositories are absent.

## TaskListItem (`entities/tasks/domain/model/task-list-item.ts`)

| Field | Type | Source |
|---|---|---|
| `id` | `string` | `id` |
| `title` | `string` | `title` |
| `branch` | `string \| null` | `branch` |
| `state` | `TaskState \| null` | `state` |
| `workflow` | `string \| null` | `workflow` |
| `relatedNodes` | `{ id: string; kind: string }[]` | `related_nodes` (nulls dropped) |
| `updatedAt` | `string` | `updated_at` |

```ts
type TaskListPage = { tasks: TaskListItem[]; count: number };
```

- Use case `getBranchTasks({ branchName, offset, limit })` over `GET_TASK_LIST` (research R3).
- Failed count: existing `getTaskCount({ branchName, state: [FAILED] })`. FAILED only: the Tasks page filters on a single state, so the count matches what the link opens.

### Vocabulary and rules (`entities/tasks/domain/`)

- `WORKFLOW_LABELS`, `WORKFLOW_PREFIX_LABELS` (`model/workflow-labels.ts`) — the label vocabulary (research R9).
- `getWorkflowLabel(workflow)` (`rules/get-workflow-label.ts`) — `null` → "—"; unknown → the id humanized. _(2026-10-02: moved from `domain/model/` to `domain/rules/`; `model/` keeps only the maps.)_
- `getTaskRelatedLabel(task, namesById, getKindLabel?, emptyLabel?)` (`rules/get-task-related-label.ts`) — research R10.
- `getRelatedNodeIds(tasks)` (`rules/get-related-node-ids.ts`) — sorted, unique related node ids of a page; the input of the names lookup.

## Pagination state

Shared with IFC-3130 (`shared/utils/table-pagination.ts`, `shared/hooks/use-table-pagination.ts`, taken verbatim):

- `PAGE_SIZE = 10`; `getOffset(page, pageSize)`; `getTotalPages`; `clampPage`; `getPageItems`; `formatPageWindow`; `getPageUrlKey(urlKey) = "${urlKey}_page"`.
- `useTablePagination({ urlKey }) → { page, pageSize, offset, setPage }`; dev-only warning when two mounted tables share a `urlKey`.
- `useCountClampedQuery({ page, pageSize }, getQueryOptions)` (`shared/hooks/use-count-clamped-query.ts`, this PR) — asks for the requested page and, when the server's count puts it past the end, for the last real page. The clamp happens in the data hook; the URL isn't written back.
- Fixed height: when `count > PAGE_SIZE`, the table container's min-height is `(PAGE_SIZE + 1) × CELL_HEIGHT_PX` (header + 10 rows). `CELL_HEIGHT_PX = 40` lives in `shared/components/table/style.tsx` (IFC-3130).

URL: `repositories_page`, `tasks_page` (`useTablePagination` with `urlKey` `repositories` and `tasks`), owned by each card. _(2026-10-02: was `repos_page` / `tasks_page`, owned by the Details tab page.)_

## State transitions

- Repositories card: `loading → ok | denied | failed`; `ok` renders `empty-not-synced | empty-none` when `count === 0`, else `table(+pager)` and the bands.
- Bands: from the health query, independent of the table page. Hidden until it loads; a failed health query shows no band.
- Band: `loading → found | not-found`; failure of either lookup behaves as `not-found` (the band never disappears).
- Bands list: `collapsed (≤3 visible) ⇄ expanded (all)` — only when more than 3; resets on another branch.
- Tasks card: `loading → ok(empty | table) | failed`.
