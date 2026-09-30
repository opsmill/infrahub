# Data Model: Repository, Git state and Commit columns on the branches table

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This feature is frontend-only. It adds no schema, no migration, no GraphQL document and no API mapper. The shapes below are domain types in the branches entity, built on the repository model #10779 already defines. Paths are relative to `frontend/app/src/`.

## Consumed as-is: `BranchRepository` and `BranchRepositorySyncStatus`

These are defined in `entities/repository/domain/model/branch-repository.ts` and are not redefined here. This feature reads:

| Field | Used for |
|---|---|
| `BranchRepository.id` | the row id suffix; the link target |
| `BranchRepository.kind` | the link target (`getObjectDetailsUrl(kind, id, …)`) |
| `BranchRepository.name` | the link text and `title`; the name sort inside `rankRepositories` |
| `BranchRepository.isReadOnly` | the "Read-only" chip |
| `BranchRepository.commit` (`string \| null`) | the Commit cell; `null` means a blank cell |
| `BranchRepository.syncStatus` (`BranchRepositorySyncStatus`: `value`, `label`, `color`, `description`, all `string \| null`) | `GitStatePill`; `syncing` drives the poll |
| `BranchRepository.operationalStatus` | ordering only (rank 1). Never rendered (FR-016) |

`BranchRepositoriesResult` is `{ status: "ok"; repositories; count; isTruncated } | { status: "denied" }`. It is the use-case's return value. `count` and `isTruncated` are ignored (research R11).

## `BranchRepositoriesFetch` (`entities/branches/domain/model/branch-table-row.ts`)

This is the input for one branch: the query's state, flattened so the rule never sees TanStack.

```ts
export type BranchRepositoriesFetch =
  | BranchRepositoriesResult     // { status: "ok", … } | { status: "denied" }
  | { status: "pending" }
  | { status: "error"; message: string };
```

The hook maps each query result as follows. The first matching case wins:

| Query result | `BranchRepositoriesFetch` |
|---|---|
| `data` present | `data` |
| `isError` | `{ status: "error", message: error.message }` |
| otherwise (pending) | `{ status: "pending" }` |

`data` comes first so that a stale success stays rendered when a background refetch fails (invariant 9).

The fetch's `message` becomes the `error` row's `errorMessage`.

A branch with no entry in the map is treated as `pending`.

## `BranchTableRow` (same file)

```ts
export type BranchTableRowState = "pending" | "ok" | "empty" | "denied" | "error";

export type BranchTableRow = { id: string; branch: BranchListItem } & (
  | { state: "ok"; repository: BranchRepository }
  | { state: "error"; repository: null; errorMessage: string }
  | { state: Exclude<BranchTableRowState, "ok" | "error">; repository: null }
);

export function isBranchAnchorRow(row: BranchTableRow): boolean {
  return row.id === row.branch.id;
}
```

`BranchListItem` comes from `entities/branches/domain/model/branch.ts`. Cells narrow on `state`. `repository` is non-null exactly when `state === "ok"`. `errorMessage` exists only on the `error` row; the Repository cell shows it as the tooltip of "Could not load repositories" (FR-013).

### Rows per state, and which row is the anchor

The anchor is the only selectable row of a branch (research R1). Its id is always `branch.id`.

| Fetch | Rows for the branch | `state` | `id` | Anchor |
|---|---|---|---|---|
| `pending` (or missing) | 1 | `pending` | `branch.id` | that row |
| `ok`, 0 repositories | 1 | `empty` | `branch.id` | that row |
| `ok`, N ≥ 1 repositories | N, in `orderRepositories` order | `ok` | 1st: `branch.id`; k-th (k ≥ 2): `${branch.id}:${repository.id}` | the 1st row, which carries the top-ranked repository |
| `denied` | 1 | `denied` | `branch.id` | that row |
| `error` | 1 | `error` | `branch.id` | that row |

The empty text is not stored on the row. The Repository cell derives it from `branch.sync_with_git`: `false`/`null` gives "Not synced with Git", `true` gives "No repositories". This is the only use of the flag (FR-003, FR-007).

## `toBranchTableRows` (`entities/branches/domain/rules/to-branch-table-rows.ts`)

```ts
export function toBranchTableRows(params: {
  branches: BranchListItem[];
  fetchByBranchId: ReadonlyMap<string, BranchRepositoriesFetch>;
  orderRepositories: (repositories: BranchRepository[]) => BranchRepository[];
}): BranchTableRow[];
```

The rule is pure: no I/O, React or TanStack, and it imports only its own `domain/model` (research R2). The hook passes `orderRepositories: rankRepositories`; tests pass the same function.

**Invariants** (each asserted in `to-branch-table-rows.test.ts`):

1. **Row count**: a branch yields N rows when its fetch is `ok` with N ≥ 1 repositories, and exactly 1 row otherwise. So the total is ≥ `branches.length` (FR-002, FR-007, FR-010, SC-002).
2. **Branch order**: branches appear in input order, and each branch's rows are consecutive. The input is already ordered by `BranchesTable`: default branch first, then by name (FR-015).
3. **Repository order**: within a branch, `ok` rows follow `orderRepositories(repositories)` exactly (FR-006a).
4. **Anchor first**: the first row of every branch has `id === branch.id`. No other row of that branch does.
5. **Id uniqueness**: all ids are unique across the result. `branch.id` is unique per branch, and `repository.id` is unique within a branch's result.
6. **Stability**: the anchor id does not change as the fetch moves between `pending`, `ok`, `empty`, `denied` and `error`, so selection survives a state change.
7. **Isolation**: one branch's fetch never affects another branch's rows (SC-005).
8. **Backend-authoritative set**: the repositories shown are exactly those in the result, with no filtering on `sync_with_git`, `status` or `kind` (FR-003). This includes read-only repositories on a `sync_with_git=false` branch.
9. **Stale success wins**: a background refetch failure keeps the last loaded rows. The hook's mapping (`data` first, then `isError`, then pending) guarantees it; it is asserted in the hook's test (`use-branch-table-rows.test.ts`, T011), since the rule only sees the mapped fetch.

## `BRANCH_FIELD_SCHEMAS` additions (`entities/branches/ui/branches-table/branch-field-schemas.ts`)

These are header-only schemas for `TableColumnHeaderSimple`. They follow the file's existing object shape.

```ts
repository: { name: "repository", label: "Repository", kind: "Text" } as AttributeSchema,
git_state:  { name: "git_state",  label: "Git state",  kind: "Text" } as AttributeSchema,
commit:     { name: "commit",     label: "Commit",     kind: "Text" } as AttributeSchema,
```

None of them is added to `BRANCH_FILTER_DEFINITIONS` (FR-015). The column ids match the keys: `repository`, `git_state`, `commit`.

## Test fakes (`tests/fake/branch-table-rows.ts`, new)

- `FULL_COMMIT_HASH`: a 40-character hex string whose first 7 characters are `8f3c2a1`.
- `SYNC_STATUS_NO_COLOUR = { value: "mystery", label: "Mystery", color: null, description: null }` is not in this file: it is a constant local to `get-branch-table-columns.test.tsx` (T015).
- `generateBranchTableRow(overrides)`: an `ok` row over `generateBranch` and `generateBranchRepository`.

It reuses `tests/fake/branch.ts::generateBranch` and `tests/fake/branch-repositories.ts::{SYNC_STATUS, OPERATIONAL_STATUS, generateBranchRepository, generateBranchRepositoriesResult}`.
