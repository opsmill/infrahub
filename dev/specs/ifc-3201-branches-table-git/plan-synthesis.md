# IFC-3201 plan synthesis

Paths are relative to `frontend/app/`. I checked every claim below against the worktree at `f3e1676654`.

## 1. Decisions

### a. Selection: option (i), the first row of each branch is its only selectable row
- The first row of each branch has id `branch.id`. Every other row has id `${branch.id}:${repository.id}`. Set `enableRowSelection: (row) => row.id === row.original.branch.id`.
- **TanStack v8, checked:** `toggleAllRowsSelected(true)` skips rows where `getCanSelect()` is false. `getIsAllRowsSelected` and `getIsSomePageRowsSelected` count only selectable rows. `row.toggleSelected(true)` writes the id only when `getCanSelect()` is true. So the header checkbox, the logout reset and `getSelectedRowModel()` all see one row per branch.
- **Shared shift-range handler** (`get-toggle-selected-row-handler.ts`): it slices `getRowModel().flatRows` by `row.index` and calls `toggleSelected(!isCellSelected)` on each row.
  - On a non-selectable row, selecting does nothing and deselecting deletes an id that is not there, so it is harmless.
  - Pass it the branch's first row (`table.getRow(row.original.branch.id)`). Its `index` then anchors the range, and its `getIsSelected()` drives the direction.
  - The range therefore counts branches (FR-009).
  - Its `<T extends NodeCore>` bound is unused by the body, so widen it to `<T>`. No caller changes.
- **Why:** least code. The toolbar, delete modal and logout effect stay untouched. Selection survives pending → N because the first row keeps id `branch.id`. Option (ii) adds 2 rules, 1 hook and controlled state; (iii) adds a dedup and a forked handler.
- **Cost:** the anchor-row convention is implicit, so name it in the model as `isBranchAnchorRow(row)`. A shared file's generic changes, and every checkbox reads another row's state.
- **Testability:** add `aria-label={`Select ${branch.name}`}` to the row `Checkbox` in `cells/branch-name-cell.tsx`. Tests then use `getByRole("checkbox", { name: "Select feature" }).nth(1)`.

### b. Fan-out rule lives in `branches/domain/rules`, fan-out only, with the ordering injected
- The layering table (`entities-structure.md` l.89) says `domain/rules` may import only its own `domain/model`, `shared/` and generated types. It may not import another entity's rules, so `rankRepositories` is off-limits there.
- `domain/model` *may* import other entities' `domain/model`. So `branches/domain/model/branch-table-row.ts` defines `BranchTableRow` and `BranchRepositoriesFetch = BranchRepositoriesResult | {status:"pending"} | {status:"error"}` on top of the repository model types. The rule then imports only its own model.
- **Signature:** `toBranchTableRows({ branches, fetchByBranchId, orderRepositories }): BranchTableRow[]`. A missing map entry means pending. The hook and the tests both pass `rankRepositories`, so FR-006a is asserted on the rule's output.
- **Cost:** one extra parameter, for a pure fan-out test that respects layering. A `ui/` helper would work but breaks "pure helpers → `domain/rules`".

### c. Grid template: keep it positional
- With 11 columns, the three new ones land inside `repeat(n-4, fit-content(COLUMN_MAX_WIDTH))`, so no existing track moves. The spec accepts either option.
- Move to a per-column tracks map when Upstream and Last import (IFC-3146/3147) arrive; doing it now is YAGNI (VII). Test: `style.gridTemplateColumns` contains `repeat(7,`.

### Also decided
- **Hook:** `entities/branches/ui/hooks/use-branch-table-rows.ts`, `useBranchTableRows(branches): BranchTableRow[]`.
  - It uses `useQueries` over `getBranchRepositoriesQueryOptions({ branchName, syncWithGit: Boolean(b.sync_with_git) })`. The key is shared with branch details, and so is the 10 s poll (FR-014).
  - Each result maps to a fetch value: `isPending` → pending, `isError` → error, otherwise `data`. The hook then calls the rule.
  - It lives in branches because it produces branches-table rows. branches `ui` → repository `ui` is allowed.
  - Rejected: `repository/ui/queries/get-branches-repositories.query.ts`.
- **Extract `RepositoryNameLink`:** yes, as `entities/repository/ui/branch-repositories/repository-name-link.tsx` with props `{ repository, branchName, isDefaultBranch }` (icon, `Link` via `getObjectDetailsUrl` + `getBranchQspOverride`, "Read-only" chip).
  - It has two callers, which satisfies VII.
  - `repository-row.tsx` keeps the unreachable icon and the `—` commit fallback.
- **`React.useMemo`:** remove it from `branches-table.tsx` (`columns`, `flatData`) and `branches-data-table.tsx` (`style`). React Compiler handles memoization.
- **New columns' `as ColumnDef`:** new display columns use `columnHelper.display`, so they need no `as` (III). The existing accessor casts stay, because they are counted by betterer.

## 2. Spec corrections (for the conductor)

`rankRepositories` puts import errors first (rank 2), then unreachable repositories (rank 1, operational status), then sorts by name (case-insensitive, `localeCompare` with base sensitivity) within each rank. It does not keep backend order.

- **FR-006a**, replace with:
  > **FR-006a**: Within a branch, repository rows MUST be ordered by the same rule as the branch details page: repositories whose last import failed first, then repositories whose remote is unreachable, then the rest, each group sorted by repository name (case-insensitive). The unreachable status itself is not shown (FR-016); it only affects order.
- **US2-AS5**, replace the Then clause with:
  > **Then** the failed repository is the branch's first row and the others follow in the branch details page's order (unreachable remotes next, then by name), identically across reloads.
- **Clarification "In which order…"**, replace the answer with:
  > **The branch details page's order**: failed imports first, then unreachable remotes, then by name. The ordering rule is reused, not re-implemented.
- **Assumptions**, add:
  > When the backend truncates a branch's repository list, the list shows only the returned repositories, with no "more" marker.

## 3. Ordered tasks

**T0.** Lift `src/shared/components/display/commit-hash.tsx` and `.test.tsx` byte-identical from `baecf35c7d` (`git -C /Users/paul/Projects/infrahub show baecf35c7d:frontend/app/…`). Test: the lifted test itself. Mention the lift in the PR body.

**T1.** Model, rule and fakes.
- `src/entities/branches/domain/model/branch-table-row.ts`:
  - `BranchTableRowState`
  - `BranchTableRow = { id; branch: BranchListItem } & ({state:"ok"; repository: BranchRepository} | {state:"pending"|"empty"|"denied"|"error"; repository:null})`
  - `BranchRepositoriesFetch`
  - `isBranchAnchorRow(row) = row.id === row.branch.id`
- `src/entities/branches/domain/rules/to-branch-table-rows.ts`.
- Fakes in `tests/fake/branch-table-rows.ts`. It is local, so the #10779 fake file is not touched. It imports `BranchListItem` from `domain/model/branch`; leave `tests/fake/branch.ts`'s stale import alone, because fixing it changes betterer results.
  - `FULL_COMMIT_HASH` (40 chars)
  - `SYNC_STATUS_NO_COLOUR = {value:"mystery",label:"Mystery",color:null,description:null}`
  - `generateBranchTableRow(overrides)`
- Test: `domain/rules/to-branch-table-rows.test.ts`, copying `rank-repositories.test.ts`. It covers:
  - N repos → N unique ids, the first equal to `branch.id`
  - an import error in 3rd place moves first (`rankRepositories` injected)
  - empty gives one row for both sync flags; read-only repos on a non-synced branch are listed
  - denied, error, pending and a missing entry give one row each
  - two branches keep their order, and a denial on one does not affect the other

**T2 [P].** Extract `repository-name-link.tsx` and switch `repository-row.tsx` to it. Test: the existing `branch-repositories-card.test.tsx` must stay green.

**T3.** Widen the generic in `src/entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler.ts` to `<T>` and drop the `NodeCore` import. Then write the hook `src/entities/branches/ui/hooks/use-branch-table-rows.ts`. Test: covered in T7 (`branches-table.test.tsx`).

**T4 [P].**
- Add `repository`, `git_state`, `commit` (`kind:"Text"`, labels "Repository", "Git state", "Commit") to `branch-field-schemas.ts`. Nothing goes in `BRANCH_FILTER_DEFINITIONS`.
- Add three cells in `cells/`, each `TableCell className="h-auto min-h-14"`, taking `row: BranchTableRow`:
  - `branch-repository-cell.tsx`: `Spinner` when pending; `RepositoryNameLink` when ok; otherwise a muted `text-subtle-muted` text: "Not synced with Git", "No repositories", "No permission" or "Could not load repositories".
  - `branch-git-state-cell.tsx`: `GitStatePill` when ok, spinner when pending, blank otherwise.
  - `branch-commit-cell.tsx`: `<CommitHash hash copyable />` when ok with a commit, spinner when pending, blank otherwise.

**T5.** Columns, data table and selection.
- `get-branch-table-columns.tsx`:
  - `createColumnHelper<BranchTableRow>()`
  - accessors read `r.branch.*` with explicit ids
  - the identifier cell resolves `anchor = table.getRow(row.original.branch.id)` for `isSelected` and the handler
  - add the three `display` columns after `proposed_changes`
- `branch-name-cell.tsx`: add the `aria-label`.
- `branches-data-table.tsx`:
  - rows are `BranchTableRow`
  - `enableRowSelection: (row) => isBranchAnchorRow(row.original)`
  - `selectedRows = …flatRows.map(r => r.original.branch)`
  - drop `useMemo`

**T6.** `branches-table.tsx`: pass `data={useBranchTableRows(flatData)}` and drop `useMemo`. `BRANCHES_PER_PAGE` is unchanged.

**T7.** Component tests.
- `ui/branches-table/branches-data-table.test.tsx`. Copy the patterns of `branch-repositories-card.test.tsx` and `modal-delete-branch.test.tsx`. Mock `useAuth`, `get-proposed-changes.query`, `useSchema`, `get-objects-count.query` and `delete-branches.mutation`. It covers:
  - Selection: the new headers sit after "Proposed Changes"; ticking the 2nd checkbox of a 3-repo branch checks all 3 and shows "1 selected"; delete lists the branch once; shift-range over 2 branches shows "2 selected"; select-all counts branches.
  - Cells: pill colour and the `Mystery` grey fallback; `8f3c2a1` with the full hash in `title`; `Copy commit …` writes the full hash (stubs from `useCopyToClipboard.test.tsx`); no commit → no button; the empty, denied and error texts, with no `-` or `—`; pending shows spinners.
  - Other: no filter or sort control on the new headers; no `Credential Error` icon; `repeat(7,` in the template.
- `ui/branches-table/branches-table.test.tsx`. Mock `useGetBranchesPaginated` and the repository use-case. It covers branch cells rendering while pending, pending → 3 rows on rerender with the name staying first, and no toast on a branch error.

**T8.** Gates: `pnpm exec biome ci .`, `pnpm knip`, `pnpm exec betterer ci`, `pnpm test`.

**T9 (checkpoint decision).** E2E in `tests/e2e/branches/test_branches.py`, following the `test_repository_sync_status.py` pattern (#10649 fixture).

## 4. Risks for the checkpoint

- Unreachable repositories rank up without the reason being shown (FR-016), so rows can look out of order.
- About 40 queries per page (N+1 over HTTP). The spec accepts it; batching is a follow-up.
- `isTruncated` is ignored, so a truncated list is silently partial.
- The reload button refreshes branch queries only.
- Pending → N rows push lower branches down.
- The PR touches #10779's `repository-row.tsx`, so it rebases whenever that file changes, and it widens the shared toggle-handler generic.
- Anchor-row selection relies on row order matching the data, which `manualSorting` guarantees today.
- The constitution requires E2E, the brief calls it optional, and the fixture is on unmerged #10649.

## 5. Constitution check

- **II Branch-safe:** every request carries the row's branch (`getBranchRepositoriesQueryOptions({ branchName })`, keyed by `branchName`). Nothing reads the current branch. Links use `getBranchQspOverride(branchName, is_default)`, never the default branch's name.
- **III Type safety:** `BranchTableRow` is a discriminated union that cells narrow on `state`. No `any`, no `!`, no new `as`.
- **IV Test discipline:** a pure rule test (T1) and component tests for every SC-006 state (T7), mirroring source paths and reusing the #10779 fakes. Only query hooks and use-cases are mocked, as the frontend usually does. E2E is T9.
- **V Performance:** no backend change. The ~40 requests per page are accepted, and branch details shares the cache.
- **VII Simplicity:** anchor-row selection, the positional grid, one extraction with two callers, no new dependency, no manual memoization.
