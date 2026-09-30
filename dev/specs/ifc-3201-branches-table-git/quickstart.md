# Quickstart: validate the branches table Git columns

**Feature**: [spec.md](./spec.md) | Contracts: [ui-cells.md](./contracts/ui-cells.md), [graphql.md](./contracts/graphql.md)

## Prerequisites

- The worktree is on `ple-branches-table-git-ifc-3201`, stacked on `ple-branch-details-repos-infp-671`.
- Frontend dependencies are installed (`cd frontend/app && pnpm install`).

## Feature tests

```bash
cd frontend/app && pnpm vitest run src/entities/branches src/entities/repository src/entities/nodes/object/ui/object-table/utils src/shared/components/display
```

This covers:

- `to-branch-table-rows.test.ts`: the rule invariants.
- `use-branch-table-rows.test.ts`: the query-result mapping, stale success wins.
- `get-branch-table-columns.test.tsx`: cells per state, headers, pill colour, commit, and the empty, denied and error texts.
- `branches-data-table.test.tsx`: selection and the grid template.
- `get-toggle-selected-row-handler.test.ts`: the generic shift-range handler.
- `branches-table.test.tsx`: pending → N rows.
- `commit-hash.test.tsx`: the lifted test.
- #10779's `branch-repositories-card.test.tsx`: the regression net for the `RepositoryNameLink` extraction.

## Full CI gate (before pushing)

```bash
cd frontend && pnpm exec biome ci .   # the pnpm workspace root, as `.github/workflows/ci.yml` runs it
cd frontend/app && pnpm knip && pnpm exec betterer ci && pnpm test
```

## Manual validation on `/branches`

**Setup**:

1. Run a dev stack (`uv run invoke dev.start`, or the demo stack) with the task manager.
2. Connect one read-write repository and one read-only repository.
3. Run `cd frontend/app && pnpm dev` and open `http://localhost:8080/branches`.

**Seed data**:

- **`gc-ok`**: a branch with Sync with Git **on**, whose repository imported successfully.
- **`gc-broken`**: a branch with Sync with Git on, with a repository in Import Error. Add a repository on that branch pointing at a Git repository without `.infrahub.yml`, the same approach as `tests/e2e/branches/test_branch_details_repositories.py::TestBranchDetailsRepositoryImportError::broken_repository`.
- **`gc-nosync`**: a branch with Sync with Git **off**. For the "no repositories" case, use a stack with no read-only repository, or temporarily delete it.
- **`gc-viewer`**: a user with no view permission on repositories, but permission on branches.

**Scenarios**:

| # | Do | Expect | Spec |
|---|---|---|---|
| 1 | Load `/branches` as admin | Headers read `… Proposed Changes · Repository · Git state · Commit · Last Rebase …`. None of the new headers has a filter or sort control. The branch name, status and proposed changes appear first. The Repository cell shows a spinner while Git state and Commit stay blank, then all three fill in without any column shifting sideways (rows below may move down) | FR-001, FR-011, FR-015, SC-004 |
| 2 | Look at `gc-ok` | One row per repository. The name links to the repository opened on `gc-ok` (URL has `branch=gc-ok`). The read-only repository has a "Read-only" chip. The pill uses the schema's "In Sync" label and colour, and hovering it shows the description. The commit shows 7 mono characters | US1-AS1, FR-004–006 |
| 3 | Hover the commit, then press its copy button | The full hash shows in the tooltip or title. The clipboard holds the full hash, and the tooltip reads "Copied!" | US1-AS3, FR-005 |
| 4 | Look at `gc-broken` | The broken repository is the branch's **first** row, with the "Import Error" pill in the schema's colour. The other repositories follow: unreachable ones next, then by name. The order is the same after a reload. There is no warning icon and no upstream or last-import value | US1-AS2, US2-AS5, FR-006a, FR-016 |
| 5 | Tick the 2nd row of a multi-repository branch | Every row of that branch shows as checked. The toolbar reads "1 selected". Delete lists the branch once | US2-AS2, SC-003 |
| 6 | Tick one branch, then shift-click a row of a later branch | "2 selected" for two branches, however many rows lie between | US2-AS3, FR-009 |
| 7 | Look at `gc-nosync` with a read-only repository present | Its read-only repositories are listed as ordinary rows | US3-AS3, FR-003 |
| 8 | Look at `gc-nosync` with no read-only repository | Exactly one row. Repository reads "Not synced with Git" in a muted style. Git state and Commit are blank, with no dash | US3-AS1, FR-007 |
| 9 | Look at a synced branch with no repositories | One row reading "No repositories" | US3-AS2 |
| 10 | Log in as `gc-viewer` | Every branch keeps its cells. Repository reads "No permission" in a muted style on one row per branch. There is no toast and no page error | US3-AS4, FR-012, SC-005 |
| 11 | Stop the backend's GraphQL endpoint briefly (or throttle it to an error in devtools), then refocus | The affected branches read "Could not load repositories", and hovering it shows the error message. Branches loaded before the failure keep their rows. The other rows are intact. No toast appears (research R10) | US3-AS5, FR-013 |
| 12 | Trigger "Import current commit" on `gc-ok`'s repository | While it syncs, the row's pill refreshes every 10 s and stops once the sync settles. The network tab shows one repositories request per branch, and the branch details page for `gc-ok` reuses it from the cache | FR-014, R5, R9 |
| 13 | Scroll to load the next page | The new branches append with their repository rows. The branch count per page is unchanged | US2-AS4, FR-010 |
| 14 | Switch to the dark theme | The pills, muted texts and the commit are readable, with no light-only colour | Target platform |

## E2E

`tests/e2e/branches/test_branches_git_columns.py` (`shard_branches_repo`) opens `/branches` with the `broken_repository` fixture (promoted to `tests/e2e/branches/conftest.py`, function-scoped, called with `sync_with_git=True`) and checks the broken branch's row: repository name, "Import Error" pill, 7-character commit; and that a branch without repositories reads "Not synced with Git".

```bash
uv run pytest tests/e2e/branches/test_branches_git_columns.py
```

Run it with the e2e stack up; see `dev/guides/frontend/writing-e2e-tests.md`.
