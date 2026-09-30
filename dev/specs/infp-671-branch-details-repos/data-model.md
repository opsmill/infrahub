# Data Model: Branch details — Git repositories and tasks

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Frontend-only. No schema, no migration, no new GraphQL field. These are the **domain** shapes the entity layer maps API results into (`entities/<entity>/domain/model/`), and the pure rules over them (`domain/rules/`).

## BranchRepository (`entities/repository/domain/model/branch-repository.ts`)

One repository as seen from one branch.

| Field | Type | Source | Notes |
|---|---|---|---|
| `id` | `string` | node `id` | |
| `kind` | `"CoreRepository" \| "CoreReadOnlyRepository"` | `__typename` | |
| `name` | `string` | `name.value`, fallback `display_label`, fallback `id` | |
| `isReadOnly` | `boolean` | `kind === READONLY_REPOSITORY_KIND` | drives the "Read-only" tag |
| `commit` | `string \| null` | `commit.value` on the branch | `null` → empty-value placeholder |
| `syncStatus` | `{ value: string \| null; label: string \| null; color: string \| null; description: string \| null }` | `sync_status` (Dropdown) on the branch | rendered from the schema's label/colour; raw value in a neutral tag when label/colour are missing |
| `operationalStatus` | `{ value: string \| null; label: string \| null }` | `operational_status` (Dropdown), branch-agnostic | |

### Constants (`domain/model/repository.ts`, existing file extended)

- `REPOSITORY_SYNC_STATUS_IMPORT_ERROR = "error-import"`
- `REPOSITORY_OPERATIONAL_ERRORS = ["error-cred", "error-connection", "error"] as const`
- `REPOSITORY_FETCH_LIMIT = 500`
- `IMPORT_WORKFLOWS` (research R2), `IMPORT_LOG_LIMIT = 10_000` (backend cap)
- `MAX_VISIBLE_BANDS = 3`

### Rules (`entities/repository/domain/rules/`)

- `hasImportError(repo): boolean` — `syncStatus.value === "error-import"`.
- `isRepositoryUnreachable(repo): boolean` — `operationalStatus.value` ∈ `REPOSITORY_OPERATIONAL_ERRORS`. `unknown` and `online` are not failing.
- `getRepositoryRank(repo): 2 | 1 | 0` — 2 import error, 1 unreachable, 0 otherwise.
- `rankRepositories(repos): BranchRepository[]` — stable sort by rank desc, then `name` with `localeCompare` (case-insensitive). Pure; returns a new array.
- `getFailingRepositories(repos): BranchRepository[]` — `rankRepositories(repos).filter(rank > 0)`; the band list (FR-024).
- `getBandKind(repo): "import-error" | "unreachable"` — import error wins (spec US2 scenario 5).

## BranchRepositoriesResult (`domain/use-cases/get-branch-repositories.ts`)

```ts
type BranchRepositoriesResult =
  | { status: "ok"; repositories: BranchRepository[]; count: number; isTruncated: boolean }
  | { status: "denied" };
```

- Input: `{ branchName: string; syncWithGit: boolean }`. `syncWithGit === false` → kind `CoreReadOnlyRepository`, else `CoreGenericRepository`.
- `isTruncated = count > repositories.length`.
- Non-permission GraphQL errors throw (the card's failed state).

## RepositoryImportError (`domain/use-cases/get-repository-import-error.ts`)

The band's content for one failing repository.

```ts
type RepositoryImportError =
  | { status: "found"; taskId: string; message: string }
  | { status: "not-found"; taskId: string | null };   // task missing, or no error-level line
```

- Input: `{ branchName, repositoryId }`.
- `getLastErrorLine(logs): string | null` (rule, `domain/rules/get-last-error-line.ts`) — last log with `severity` `error` or `critical` (case-insensitive), message verbatim (no trim of inner newlines; trailing whitespace trimmed).
- `taskId` is kept in `not-found` when a task exists without an error line, so the band can still link to it; when `null`, the band links to the repository (FR-022).

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

### Rules (`entities/tasks/domain/`)

- `getWorkflowLabel(workflow: string | null): string` (`model/workflow-labels.ts`) — map in research R9; `null` → "—"; unknown → the id.
- `getTaskRelatedLabel(task, repositoriesById: Map<string, string>, getKindLabel?: (kind) => string): string` (`rules/get-task-related-label.ts`) — research R10. Lives in `tasks` domain and takes the repository names as a plain map, so `tasks` doesn't import `repository`.

## Pagination state (`shared/utils/table-pagination.ts`)

- `TABLE_PAGE_SIZE = 10`, `TABLE_ROW_HEIGHT_PX = 40`.
- `getTotalPages(totalCount, pageSize) = max(1, ceil(max(totalCount, 0) / pageSize))`.
- `clampPage(page, totalPages)` — non-finite → 1, truncates, clamps to `[1, totalPages]`.
- `getPageItems(page, totalPages, siblingCount = 1): (number | "ellipsis")[]`.
- `formatPageWindow(page, pageSize, totalCount): string` — "Showing X to Y of Z" / "Showing X of Z".
- Fixed height: when `totalPages > 1`, the table container's min-height is `(TABLE_PAGE_SIZE + 1) × TABLE_ROW_HEIGHT_PX` (header + 10 rows).

URL: `repos_page`, `tasks_page` (positive integers, default 1), owned by the Details tab page.

## State transitions

- Repositories card: `loading → ok | denied | failed`; `ok` renders `empty-not-synced | empty-none | table(+bands)`.
- Band: `loading → found | not-found`; failure of the band query behaves as `not-found` (the band never disappears).
- Bands list: `collapsed (≤3 visible) ⇄ expanded (all)` — only when more than 3.
- Tasks card: `loading → ok(empty | table) | failed`.
