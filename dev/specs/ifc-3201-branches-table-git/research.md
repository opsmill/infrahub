# Research: Repository, Git state and Commit columns on the branches table

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-30

Code references name the module and symbol; line numbers are left out on purpose. Paths are relative to `frontend/app/` unless stated. Every decision below comes from `plan-synthesis.md`; this file records the reasoning and the code it was checked against.

## What is on the base branch (`ple-branch-details-repos-infp-671`, PR #10779)

| Needed | On this base? | Consequence |
|---|---|---|
| Per-branch repository query, model, pill, ranking | Yes: `entities/repository/ui/queries/get-branch-repositories.query.ts::getBranchRepositoriesQueryOptions`, `domain/model/branch-repository.ts`, `ui/branch-repositories/git-state-pill.tsx::GitStatePill`, `domain/rules/rank-repositories.ts::rankRepositories` | Reused unchanged. |
| Repository fakes | Yes: `tests/fake/branch-repositories.ts` (`SYNC_STATUS`, `OPERATIONAL_STATUS`, `generateBranchRepository`, `generateBranchRepositoriesResult`) | Reused; this feature's extra fakes go in a new local file (R12). |
| `CommitHash` | **No** (PR #10658 only) | Lifted (R8). `CopyToClipboardButton`, its only dependency, is byte-identical on this base and on #10658. |
| Branches table tests | **None** under `entities/branches/ui/branches-table/` | Both component test files are new. |
| Deterministic import-error E2E fixture | Class-local: `tests/e2e/branches/test_branch_details_repositories.py::TestBranchDetailsRepositoryImportError::broken_repository` | E2E is deferred, but the follow-up can lift this fixture (plan, Constitution Check IV). |

## R1 — Selection: the anchor row

**Decision**: The first row of each branch has id `branch.id` and every later row has id `${branch.id}:${repository.id}`. The table sets `enableRowSelection: (row) => isBranchAnchorRow(row.original)`. The identifier cell resolves `anchor = table.getRow(row.original.branch.id)` and reads `anchor.getIsSelected()`. It also passes `{ row: anchor, table }` to the shared shift-range handler. `selectedRows = table.getSelectedRowModel().flatRows.map((r) => r.original.branch)`. The row `Checkbox` in `branch-name-cell.tsx::BranchNameCell` gains `aria-label={`Select ${branch.name}`}`.

**Rationale**: these TanStack Table 8.21.3 semantics were checked in `table-core/src/features/RowSelection.ts`:

- `toggleAllRowsSelected(true)` skips rows whose `getCanSelect()` is false. `toggleAllRowsSelected(false)` deletes every id.
- `getIsAllRowsSelected` and `getIsSomePageRowsSelected` only consider selectable rows. So the header checkbox reflects branches.
- `row.toggleSelected(value)` goes through `mutateRowIsSelected`. That writes the id only when `getCanSelect()` is true and otherwise deletes it, so toggling a non-anchor row is a no-op.
- `getSelectedRowModel()` filters by the ids in `rowSelection`, so it contains anchors only. The toolbar count, the delete modal list and the logout reset (`toggleAllRowsSelected(false)`) therefore see one entry per branch without change (FR-008, SC-003).
- `getToggleSelectedRowHandler` slices `getRowModel().flatRows` by `row.index` and calls `toggleSelected(!isCellSelected)`. With the anchor passed in, `index` and `getIsSelected()` are the anchor's. Non-anchor rows inside the range are no-ops, so a range counts branches (FR-009).
- Selection survives pending → N: the anchor keeps id `branch.id` in every state (data-model).

**Alternatives considered**:

- (ii) Controlled `rowSelection` keyed by branch id, plus a mapping from row to branch. This needs two rules, a hook and state for the same observable result.
- (iii) Every row selectable, then dedup `selectedRows` by `branch.id`. The header checkbox then counts rows, and shift-range needs a forked handler.

**Cost**: the anchor convention is implicit, so it is named by `isBranchAnchorRow`. Each checkbox reads another row's state.

## R2 — Fan-out location and layering

**Decision**: `entities/branches/domain/rules/to-branch-table-rows.ts::toBranchTableRows({ branches, fetchByBranchId, orderRepositories })` does the fan-out. It gets the ordering as an injected parameter. The row types live in `entities/branches/domain/model/branch-table-row.ts`, built on `entities/repository/domain/model/branch-repository.ts`.

**Rationale**: the layering table in `dev/knowledge/frontend/entities-structure.md` puts limits on each layer:

- `domain/rules` may import only its own `domain/model`, `shared/` and generated types. It may not import `repository/domain/rules/rank-repositories.ts`.
- `domain/model` may import other entities' `domain/model`, so the types are legal.

Injecting `orderRepositories` keeps the rule pure and inside its layer. The tests still assert FR-006a on the rule's output, because they pass the real `rankRepositories`. A fan-out inside a cell is impossible, since a cell cannot add rows.

**Alternatives considered**:

- A `ui/` helper. It works, but breaks "pure helpers go in `domain/rules`".
- Placing the rule in `entities/repository`. It produces branches-table rows, so branches owns it.

## R3 — Ordering: `rankRepositories`, and the spec correction

**Decision**: Within a branch, rows follow `rankRepositories`. Import errors come first (rank 2). Unreachable remotes come next (rank 1, from `operationalStatus`). The rest follow (0). Each group is sorted by `name.localeCompare(…, { sensitivity: "base" })`.

**Rationale**: FR-006a requires the branch details page's order, and this is that rule, reused, not re-implemented. The phase 1 brief said "keeps backend order", which was wrong. The spec's FR-006a, US2-AS5 and the ordering clarification were corrected to this rule (synthesis §2). The unreachable status only affects order; it is not displayed (FR-016).

**Alternatives**: backend order was rejected because it contradicts FR-006a and differs from branch details.

## R4 — Grid template stays positional

**Decision**: `branches-data-table.tsx::defaultGridTemplateColumns` is unchanged. The three columns are inserted after `proposed_changes`, so there are 11 columns: `id`, `status`, `proposed_changes`, `repository`, `git_state`, `commit`, `branched_from`, `updated_at`, `created_at`, `created_by`, `actions`. They land inside `repeat(columnCount - 4, fit-content(COLUMN_MAX_WIDTH))`, which becomes `repeat(7, …)`. The first three tracks and the trailing `2.5rem` keep their columns.

**Rationale**: no existing track moves, and it needs zero code. A test asserts that `style.gridTemplateColumns` contains `repeat(7,`.

**Alternatives**: a per-column tracks map. Deferred to IFC-3146/3147 (Upstream, Last import), when more columns arrive (VII, YAGNI).

## R5 — Data-fetch strategy: (a) one request per branch

**Decision**: use (a). `useQueries` over `getBranchRepositoriesQueryOptions({ branchName, syncWithGit: Boolean(branch.sync_with_git) })` runs once per loaded branch.

The options compared (P = pages loaded, 40 branches per page, R = number of repositories):

| | Requests | Permissions | Verdict |
|---|---|---|---|
| (a) per branch, #10779 options | 40·P (40, then 80, then 120), independent of R. Plus the existing 40·P proposed-changes queries | A normal node read per branch, so a denial affects only that branch (FR-012) | **Chosen.** Same key as branch details (`repositoryQueryKeys.branch({ branchName, kind })`), so the cache is shared. `syncWithGit=false` queries `CoreReadOnlyRepository` natively |
| (b) `InfrahubRepositoryBranchStatus` per repository, pivoted | 1 + R, flat while scrolling | Needs VIEW with ALLOW_ALL. One denial blanks the whole column | Rejected. It must fetch every branch and join by name, the order and filters don't match the table, and it excludes MERGED branches |
| (c) Backend list-of-ids variant | 1 | Same as (b) | Rejected: needs a backend change, which is out of scope |

**Rationale**: (a) is the only option that meets FR-003 (the backend's per-branch row set), FR-011 (per-branch loading) and FR-012 (per-branch denial) without backend work. Its request count is linear in branches shown, not in repositories.

**Follow-up**: revisit (b)/(c) if profiling shows the ≈40 parallel requests matter.

## R6 — Hook location

**Decision**: `entities/branches/ui/hooks/use-branch-table-rows.ts::useBranchTableRows(branches): BranchTableRow[]`. It maps each `useQueries` result to a `BranchRepositoriesFetch`: `isPending` → `{ status: "pending" }`, `isError` → `{ status: "error" }`, otherwise `data`. It then calls `toBranchTableRows` with `orderRepositories: rankRepositories`.

**Rationale**: it produces branches-table rows, so it belongs to branches. `branches/ui` may import `repository/ui/queries` and `repository/domain/rules`.

**Alternatives**: `repository/ui/queries/get-branches-repositories.query.ts`. Rejected because it would couple the repository entity to branches-table row shapes.

## R7 — Extract `RepositoryNameLink`

**Decision**: add `entities/repository/ui/branch-repositories/repository-name-link.tsx::RepositoryNameLink({ repository, branchName, isDefaultBranch })`. It holds the `FolderGitIcon`, a `Link` to `getObjectDetailsUrl(kind, id, [getBranchQspOverride(branchName, isDefaultBranch)])` with `title={name}`, and the "Read-only" chip. `repository-row.tsx::RepositoryRow` uses it and keeps the unreachable icon and the `—` commit fallback.

**Rationale**: FR-006 asks for the same name, link and marker as branch details. Two callers satisfy VII. The existing `branch-repositories-card.test.tsx` is the regression net.

**Alternatives**: copying the markup (it drifts), or reusing `RepositoryRow` (it renders a `<tr>`).

## R8 — Lift `CommitHash`

**Decision**: copy `src/shared/components/display/commit-hash.tsx` and `commit-hash.test.tsx` byte-identical from `git -C /Users/paul/Projects/infrahub show ple-branches-card-ifc-3130:frontend/app/src/shared/components/display/…` (#10658's current head). The PR body mentions the lift. Usage: `<CommitHash hash={commit} copyable />`, which renders a 7-character mono hash with `title={hash}` and `CopyToClipboardButton` labelled `Copy commit <hash>`.

**Rationale**: the owner's decision (spec Clarifications). An identical add/add merges cleanly. The synthesis named `baecf35c7d`; the test file differs between that commit and the branch head (6 lines), so the branch head is the source, matching what #10658 will merge.

**Alternatives**: rewriting it means a conflict later. Rendering the hash inline in the cell duplicates #10658.

## R9 — Polling

**Decision**: keep #10779's `refetchInterval`: 10 s while any repository on that branch has `sync_status = syncing`, otherwise `false`. The options are passed unchanged.

**Rationale**: FR-014 asks for "the cadence already used by the branch details page". Only syncing branches poll, and each stops on settle. Changing the options would split the shared cache key's behaviour.

## R10 — Pending, denied and error rendering

**Decision**: each state renders per branch, and the branch cells always render:

| State | Repository cell | Git state and Commit cells |
|---|---|---|
| `pending` | `Spinner` (the `branch-proposed-changes-cell.tsx` pattern) | `Spinner` |
| `denied` (use-case returns `{ status: "denied" }` when every GraphQL error is `PERMISSION_DENIED`) | muted "No permission" | blank |
| `error` (the use-case throws) | muted "Could not load repositories" | blank |

**Rationale**: FR-011 to FR-013 and SC-005. The query client default is `retry: false` (`shared/api/rest/client.ts::queryClient`), so a failure settles immediately.

**Finding (toast)**: the shared GraphQL client routes errors through `shared/api/graphql/error-handling.ts::handleGraphQLErrors`:

- `PERMISSION_DENIED` is skipped, so there is no toast for the denied state.
- Network errors throw without a toast.
- Any other GraphQL error calls `notifyUser`, which toasts, deduplicated by `toastId: "alert-error"`, unless the request context supplies `processErrorMessage`.

`get-branch-repositories-from-api.ts::fetchConnection` passes only `{ branch }`, so FR-013's "no toast" does not hold for GraphQL-level errors. The minimal fix is to pass a no-op `processErrorMessage` in that context. That is a one-line change to a #10779 file, and it also affects the branch details card, which renders its own failed state. **Decision: make the change.** FR-013 is explicit, and a page-level toast for a per-row degraded cell is the wrong surface on both pages.

## R11 — `isTruncated` ignored

**Decision**: when `status === "ok"`, only `repositories` is used. `count` and `isTruncated` are not rendered. **Rationale**: spec Assumptions ("no more marker"). `REPOSITORY_FETCH_LIMIT = 500` is far above realistic per-branch counts.

## R12 — Remove `React.useMemo`; local fakes

**Decision**: remove `React.useMemo` from `branches-table.tsx::BranchesTable` (`columns`, `flatData`) and from `branches-data-table.tsx::BranchesDataTable` (`style`). The React Compiler memoizes (`dev/knowledge/frontend/react.md`, "React Compiler").

New fakes go in `tests/fake/branch-table-rows.ts`:

- `FULL_COMMIT_HASH`: 40 characters.
- `SYNC_STATUS_NO_COLOUR`: `{ value: "mystery", label: "Mystery", color: null, description: null }`.
- `generateBranchTableRow(overrides)`.

That file imports `BranchListItem` from `entities/branches/domain/model/branch`. `tests/fake/branch.ts` keeps its stale `domain/branch.mappers` import, because fixing it would change betterer's results.

**Rationale**: touched files follow the project rule. Local fakes leave #10779's fake file untouched.

**Note (no-colour pill)**: `GitStatePill`'s fallback renders `value || label || "—"`. With `SYNC_STATUS_NO_COLOUR` it shows `mystery` in a grey `Badge`. FR-004 ("the label or value") is met. The spec's edge-case wording ("the label, or the raw value if no label") reads label-first; the pill is reused unchanged (spec Assumptions), so tests assert what it renders.

## Risks

1. The GraphQL-level error toast (R10) is closed by the no-op `processErrorMessage`; the residual effect is that the branch details card loses a toast it never needed.
2. Unreachable repositories rank up without the reason shown (FR-016), so rows can look out of order.
3. ≈40 queries per page (N+1 over HTTP). Accepted, with batching as a follow-up (R5).
4. `isTruncated` is ignored, so a truncated list is silently partial (R11).
5. The page's reload button refreshes branch queries only.
6. Pending → N rows pushes lower branches down (spec edge case).
7. The PR touches #10779's `repository-row.tsx` and widens the shared toggle handler's generic (plan Complexity Tracking).
8. Anchor selection relies on the row order matching the data order, which `manualSorting: true` guarantees today.
9. E2E is in scope: one `/branches` case over the `broken_repository` fixture promoted from `test_branch_details_repositories.py` to `tests/e2e/branches/conftest.py` (plan IV). The promotion touches a #10779 test file.
