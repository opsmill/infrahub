# Quickstart: validate the branches table Git columns

**Feature**: [spec.md](./spec.md) | Contracts: [ui-cells.md](./contracts/ui-cells.md), [graphql.md](./contracts/graphql.md)

## Prerequisites

- The worktree is on `ple-branches-table-git-ifc-3201`, stacked on `ple-branch-details-repos-infp-671`.
- Frontend dependencies are installed (`cd frontend/app && pnpm install`).

## Feature tests

```bash
cd frontend/app && pnpm vitest run src/entities/branch-git-status src/entities/branches
```

This covers:

- `src/entities/branch-git-status/`:
  - `domain/rules/summarize-branch-git-statuses.test.ts`, `sync-status-severity.test.ts`, `format-branch-git-status.test.ts`, `get-unknown-sync-status.test.ts`, `to-branch-git-status-error.test.ts`: the grouping per branch, the order worst first, the tooltip and notice texts, the Unknown fallback and the permission mapping.
  - `api/branch-git-repository.mappers.test.ts`, `api/repository-branch-status.mappers.test.ts`, `domain/use-cases/get-branch-git-repositories.test.ts`, `domain/use-cases/get-repository-branch-status.test.ts`: the mapping of both documents and their errors.
  - `ui/queries/get-repository-branch-status.query.test.ts`: the poll while syncing and the stale time.
  - `ui/hooks/use-get-branch-git-statuses.test.ts`: one repository-list request, one status request per repository, data first, a denied or failed list, every status read denied, one failed status read, a cut list, no repositories and no branches.
- `src/entities/branches/ui/branches-table/`:
  - `cells/branch-repositories-cell.test.tsx`: worst repository, link, tooltip, "+N more" and its accessible name, the "could not be loaded" notice, and the loading, empty, denied and error texts.
  - `cells/branch-git-state-cell.test.tsx`: pill colour, `n/N`, the count tooltip and `sr-only` text.
  - `branch-table-row.test.ts`, `branches-data-table.test.tsx`, `branches-table.test.tsx`: rows, selection, 1 + R requests, no new status request for a second page, and failures without a toast.
- `src/entities/branches/ui/queries/*.mutation.test.ts` and `branches-list.test.tsx`: create, delete, merge, rebase and reload invalidate the Git status cache.

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

- **`gc-ok`**: a branch with Sync with Git **on**, whose repositories imported successfully (at least two, for the "+N more" and count checks).
- **`gc-broken`**: a branch with Sync with Git on, with a repository in Import Error. Add a repository on that branch pointing at a Git repository without `.infrahub.yml`, the same approach as the `broken_repository` fixture in `tests/e2e/branches/conftest.py`.
- **`gc-nosync`**: a branch with Sync with Git **off**. For the "no repositories" case, use a stack with no read-only repository, or temporarily delete it.
- **`gc-viewer`**: a user without repository view permission on all branches, but with permission on branches.
- **`gc-merged`** (optional): a merged branch, shown through the status filter.

**Scenarios**:

| # | Do | Expect | Spec |
|---|---|---|---|
| 1 | Load `/branches` as admin | Headers read `… Proposed Changes · Repositories · Git state · Last Rebase …`. Neither new header has a filter or sort control. The branch name, status and proposed changes appear first. Every Repositories cell shows one spinner while Git state stays blank, then all fill in together without any column shifting sideways | FR-001, FR-011, FR-015, SC-004 |
| 2 | Look at `gc-ok` | One row. The Repositories cell shows the worst repository (severity, then name) as a pill linking to the repository opened on `gc-ok` (URL has `branch=gc-ok`), followed by "+N more". The Git state pill uses the schema's "In Sync" label and colour, followed by `N/N` | US1-AS1, US2-AS1, FR-004, FR-006 |
| 3 | Hover the repository pill, then the Git state pill, then the count | The pill tooltip reads `<state label> · <7-char commit>` (with a `read-only` part for a read-only repository). The Git state pill's tooltip shows the state's description; the count's tooltip lists the count per state label | US1-AS3, US2-AS2, FR-004, FR-006 |
| 4 | Look at `gc-broken` | The pill shows the broken repository, the Git state reads "Import Error" in the schema's colour with `1/N`, and the count tooltip reads `Import Error: 1 · In Sync: N−1`. The same after a reload. No warning icon, no commit column, no upstream or last-import value | US1-AS2, US2-AS2, US2-AS5, FR-005, FR-016 |
| 5 | Click "+N more" on `gc-ok` | The branch details page for `gc-ok` opens and lists every repository (its own request; the list's cache is not shared) | US2-AS1, FR-004 |
| 6 | Tick `gc-ok`, then shift-click a later branch | Selection and the toolbar count behave as before the feature; Delete lists each branch once | US2-AS3, FR-008, FR-009, SC-003 |
| 7 | Look at `gc-nosync` with a read-only repository present | Its read-only repositories are shown like any other (pill, "+N more", roll-up) | US3-AS3, FR-003 |
| 8 | Look at `gc-nosync` with no read-only repository | Repositories reads "Not synced with Git" in a muted style. Git state is blank, with no dash | US3-AS1, FR-007 |
| 9 | Look at a synced branch with no repositories, and at `gc-merged` | Both read "No repositories" | US3-AS2 |
| 10 | Log in as `gc-viewer` | Every branch keeps its cells. Every Repositories cell reads "No permission" in a muted style. There is no toast and no page error | US3-AS4, FR-012, SC-005 |
| 11 | Make the GraphQL endpoint fail (devtools request blocking), then reload | Every row reads "Could not load repositories", and hovering it shows the error message. No toast appears. With the endpoint failing after a successful load, a background refetch keeps the loaded statuses | US3-AS5, FR-013 |
| 11a | Block only one repository's `GET_REPOSITORY_BRANCH_STATUS` request (devtools request blocking on its payload), then reload | Every row shows its other repositories and "1 repository could not be loaded"; hovering it reads `<repository>: <error message>`. No toast appears | FR-013 |
| 12 | Reload with the network tab open, then trigger "Import current commit" on `gc-ok`'s repository | Page load shows 1 + R repository requests (one list, one status per repository). While the repository syncs, its status request repeats every 10 s and stops once the sync settles. Refocusing the window within 60 s issues no request | FR-011, FR-014, SC-007 |
| 13 | Scroll to load the next page | The new branches append one row each, summarized without any new status request. The branch count per page is unchanged | US2-AS4, FR-010, SC-007 |
| 14 | Switch to the dark theme | The pills, the count and the muted texts are readable, with no light-only colour | Target platform |

## E2E

`tests/e2e/branches/test_branches_git_columns.py` (`shard_branches_repo`) uses the `broken_repository` fixture (`tests/e2e/branches/conftest.py`, function-scoped; returns a `BrokenRepository` from `tests/e2e/branches/broken_repository.py`). The fixture creates a branch with Sync with Git on, holding one repository in Import Error. The tests locate cells by the test ids `branch-repositories-cell-<branch>` and `branch-git-state-cell-<branch>` and check:

- On the broken branch's row, the repository pill names the repository and links to it on that branch, and the Git state pill reads "Import Error".
- A branch with Sync with Git off reads "Not synced with Git", or, when read-only repositories exist, lists one of them.

```bash
uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branches_git_columns.py
uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branch_details_repositories.py
```

Run them with the e2e stack up; see `dev/guides/frontend/writing-e2e-tests.md`.
