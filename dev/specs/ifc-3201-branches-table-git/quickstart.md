# Quickstart: validate the branches table Git columns

**Feature**: [spec.md](./spec.md) | Contracts: [ui-cells.md](./contracts/ui-cells.md), [graphql.md](./contracts/graphql.md)

## Prerequisites

- The worktree is on `ple-branches-table-git-ifc-3201`, stacked on `ple-branch-details-repos-infp-671`.
- Frontend dependencies are installed (`cd frontend/app && pnpm install`).

## Feature tests

```bash
cd frontend/app && pnpm vitest run src/entities/branches src/entities/repository
```

This covers:

- `get-branch-table-columns.test.tsx`: headers, the Repositories cell (first repository, link, tooltip, "+N more"), the Git state cell (pill colour, `n/N`, per-label tooltip), and the pending, empty, denied and error texts.
- `branches-table.test.tsx`: branch cells first, one request per branch, no extra request on refocus, per-branch error and denial without a toast.
- #10779's `branch-repositories-card.test.tsx` and `get-branch-repositories-from-api.test.ts`: the no-toast and message cases.

The 2026-09-30 rule, hook, selection, handler and `CommitHash` tests were deleted with the fan-out (research R14).

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
- **`gc-broken`**: a branch with Sync with Git on, with a repository in Import Error. Add a repository on that branch pointing at a Git repository without `.infrahub.yml`, the same approach as `tests/e2e/branches/test_branch_details_repositories.py::TestBranchDetailsRepositoryImportError::broken_repository`.
- **`gc-nosync`**: a branch with Sync with Git **off**. For the "no repositories" case, use a stack with no read-only repository, or temporarily delete it.
- **`gc-viewer`**: a user with no view permission on repositories, but permission on branches.

**Scenarios** (rewritten 2026-10-01 for one row per branch):

| # | Do | Expect | Spec |
|---|---|---|---|
| 1 | Load `/branches` as admin | Headers read `… Proposed Changes · Repositories · Git state · Last Rebase …`. Neither new header has a filter or sort control. The branch name, status and proposed changes appear first. The Repositories cell shows one spinner while Git state stays blank, then both fill in without any column shifting sideways | FR-001, FR-011, FR-015, SC-004 |
| 2 | Look at `gc-ok` | One row. The Repositories cell shows the first repository in the branch details order as a pill linking to the repository opened on `gc-ok` (URL has `branch=gc-ok`), followed by "+N more". The Git state pill uses the schema's "In Sync" label and colour, followed by `N/N` | US1-AS1, US2-AS1, FR-004, FR-006 |
| 3 | Hover the repository pill, then the Git state pill and count | The pill tooltip reads `<state label> · <7-char commit>` (and ` · read-only` for a read-only repository). The count tooltip lists the count per state label | US1-AS3, US2-AS2, FR-004, FR-006 |
| 4 | Look at `gc-broken` | The pill shows the broken repository, the Git state reads "Import Error" in the schema's colour with `1/N`, and the tooltip reads `Import Error: 1 · In Sync: N−1`. The same after a reload. No warning icon, no commit column, no upstream or last-import value | US1-AS2, US2-AS2, US2-AS5, FR-005, FR-016 |
| 5 | Click "+N more" on `gc-ok` | The branch details page for `gc-ok` opens and lists every repository; it reuses the cached request | US2-AS1, FR-004 |
| 6 | Tick `gc-ok`, then shift-click a later branch | Selection and the toolbar count behave as before the feature; Delete lists each branch once | US2-AS3, FR-008, FR-009, SC-003 |
| 7 | Look at `gc-nosync` with a read-only repository present | Its read-only repositories are shown like any other (pill, "+N more", roll-up) | US3-AS3, FR-003 |
| 8 | Look at `gc-nosync` with no read-only repository | Repositories reads "Not synced with Git" in a muted style. Git state is blank, with no dash | US3-AS1, FR-007 |
| 9 | Look at a synced branch with no repositories | "No repositories" | US3-AS2 |
| 10 | Log in as `gc-viewer` | Every branch keeps its cells. Repositories reads "No permission" in a muted style. There is no toast and no page error | US3-AS4, FR-012, SC-005 |
| 11 | Stop the backend's GraphQL endpoint briefly (or throttle it to an error in devtools), then refocus | The affected branches read "Could not load repositories", and hovering it shows the error message. Branches loaded before the failure keep their cells. No toast appears (research R10) | US3-AS5, FR-013 |
| 12 | Trigger "Import current commit" on `gc-ok`'s repository | While it syncs, the branch's cells refresh every 10 s and stop once the sync settles. The network tab shows one repositories request per branch (not two per row) | FR-011, FR-014, SC-007, R9 |
| 13 | Scroll to load the next page | The new branches append one row each. The branch count per page is unchanged | US2-AS4, FR-010 |
| 14 | Switch to the dark theme | The pills, the count and the muted texts are readable, with no light-only colour | Target platform |

## E2E

`tests/e2e/branches/test_branches_git_columns.py` (`shard_branches_repo`) opens `/branches` with the `broken_repository` fixture (promoted to `tests/e2e/branches/conftest.py`, function-scoped, called with `sync_with_git=True`) and checks the broken branch's row: the repository pill names the repository and links to its page, and the Git state pill reads "Import Error"; and that a `sync_with_git=False` branch reads "Not synced with Git".

```bash
uv run pytest tests/e2e/branches/test_branches_git_columns.py
```

Run it with the e2e stack up; see `dev/guides/frontend/writing-e2e-tests.md`.
