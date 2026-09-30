# PR notes — IFC-3201

## Lifted files

`CommitHash` is lifted byte-identical from #10658 (`ple-branches-card-ifc-3130`) so the two PRs merge as an identical add/add.

- Source: `ple-branches-card-ifc-3130` at `e1042bef6e1f42686c2948d5576941fd65f447c3` (output of `git -C /Users/paul/Projects/infrahub rev-parse ple-branches-card-ifc-3130` at the time of the lift)
- Files:
  - `frontend/app/src/shared/components/display/commit-hash.tsx`
  - `frontend/app/src/shared/components/display/commit-hash.test.tsx`

Pre-merge check (empty output means the lifted files still match; re-run against the branch tip too, in case #10658 moved):

```bash
git diff e1042bef6e1f42686c2948d5576941fd65f447c3 -- frontend/app/src/shared/components/display/commit-hash*
git diff ple-branches-card-ifc-3130 -- frontend/app/src/shared/components/display/commit-hash*
```

Result on 2026-09-30: the tip of `ple-branches-card-ifc-3130` is still `e1042bef6e`. `cmp` of each worktree file against `git -C /Users/paul/Projects/infrahub show ple-branches-card-ifc-3130:<path>` reports **identical** for both files.

## Touches to #10779 (`ple-branch-details-repos-infp-671`)

This PR changes three things that #10779 introduced. The owner can land them on #10779 first, which shrinks this diff to the table work.

- `get-branch-repositories-from-api.ts::fetchConnection` passes a no-op `processErrorMessage` in the request context. Callers render their own failed state, so the shared client's error toast is suppressed. The details card already renders its own failed state (`BranchRepositoriesFailed`), so it stops toasting as well.
- `RepositoryNameLink` is extracted from `repository-row.tsx` into `repository-name-link.tsx`, so the card and the table cell share one link.
- The E2E `broken_repository` fixture moves from `test_branch_details_repositories.py` into `tests/e2e/branches/conftest.py`. It becomes a factory that takes `sync_with_git`, so both E2E files share it.

## Shared `getToggleSelectedRowHandler` change

`entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler.ts` is also used by the object table.

- The generic is widened from `T extends NodeCore` to `T`, because branch table rows are not nodes.
- The shift-click anchor is stored by row id, not by row index. Rows can be inserted above the last-selected row between two clicks, which happens when a branch's repositories resolve. The range is still computed from the current indexes of the two rows. Object-table behaviour is unchanged when no rows are inserted, and its tests stay green.

## Constitution V deviation: N+1 over HTTP

The table sends one repositories request per loaded branch: about 40 per page (`BRANCHES_PER_PAGE = 40`), 120 after three pages. No branch-anchored or multi-repository query exists, and only per-branch reads meet FR-003, FR-011 and FR-012 without a backend change. The cache is shared with the details card, and SC-007 bounds refocus requests and re-renders.

Follow-up: a backend list-of-ids variant of `InfrahubRepositoryBranchStatus`, so one request covers every loaded branch. The owner creates the ticket.

## Error tooltip text

A branch whose repositories request fails shows "Could not load repositories", and its tooltip shows the raw GraphQL `error.message`. This is the same text the shared client toasts today, so no new wording reaches users.

## Stacking and rebase

This branch is stacked on #10779, which is stacked on `stable`. If #10779 is squash-merged, rebase this branch with `--onto` so its commits are not replayed:

```bash
git rebase --onto origin/stable 88d25e50c8 ple-branches-table-git-ifc-3201
```

`88d25e50c8` is the current merge base with `origin/ple-branch-details-repos-infp-671`. Use the branch's last commit before the squash if it has moved.

## Live-stack verification pending

No Infrahub stack was running when Phase 6 was implemented, and none was started. The E2E code was linted (`ruff format`, `ruff check`, `ty check`) and collected (`uv run pytest -c tests/e2e/pytest.ini --collect-only -q tests/e2e/branches/`, 27 tests, shard guard passed). Nothing below has run against a stack.

- **PENDING: T032 premise.** Follow "E2E premise verification" in `research.md`. Check that a `sync_with_git=False` branch's details card does not list the broken `CoreRepository`, that a `sync_with_git=True` branch's card does, and that the failed repository has a commit on that branch.
- **PENDING: T034, details E2E premise change (#10779 finding).** `test_branch_details_repositories.py` now calls `broken_repository(sync_with_git=True)`. Before this PR the fixture created its branch with `BranchAPI.create`'s default (`sync_with_git=False`). This changes #10779's test premise. Run `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branch_details_repositories.py` and check that the card lists the repository, the band reads "import failed" and "is missing a configuration file", and "View task log" opens `/tasks/<task id>`.
- **PENDING: T035, `/branches` Git columns.** Run `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branches_git_columns.py`. On the broken branch's row, check the repository link, the "Import Error" pill (the `sync_status` dropdown label in `backend/infrahub/core/schema/definitions/core/repository.py`), a 7-character commit and its "Copy commit <hash>" button. Also check that a `sync_with_git=False` branch reads "Not synced with Git". The table is a flat CSS grid with no row element, so the test finds a row's cells as the 3rd, 4th and 5th siblings after its `branch-identifier-cell`. A column reorder breaks these offsets.
- **PENDING: T042, quickstart scenarios.** Run `quickstart.md` scenarios 1–14 on a dev stack. This includes the dark theme (scenario 14) and the network-tab check of one repositories request per branch (scenario 12).
- **PENDING: T036, `test_branches.py`.** Run `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branches.py`.

### T036 audit of `tests/e2e/branches/test_branches.py`

Every row of a branch repeats its name link (`BranchNameCell`). Only the first row carries the "Select <branch>" checkbox.

- `get_by_role("link", name="main", exact=True)` (two uses in `test_search_for_a_branch`) is a real violation. `main` syncs with Git, and in the `shard_branches_repo` stack it lists `demo-edge` (`demo_edge_repo`). It also lists every other CoreRepository alive at that moment, because repositories are branch-agnostic: `test_repository_objects.py` in the same shard, or a broken repository not yet cleaned up. So `main` can span several rows. Both uses are now scoped to the anchor row through `_anchor_branch_link` (the identifier cell that holds the "Select main" checkbox).
- `den1-maintenance-conflict` and `atl1-delete-upstream` are created with `sync_with_git=False` (`tests/e2e/data/scenario_branches.py`). They list read-only repositories only, the shard has none, so each is one row. Left unchanged.
- The random branches in the other tests (`BranchAPI.create` default `sync_with_git=False`) are one row each. Their `get_by_role("link", name=...)` and `get_by_text(branch)` locators are left unchanged.
- Out of scope, noted only: `test_branch_details.py::test_opens_detail_page_from_branches_list` clicks a `sync_with_git=False` branch's link, so it is one row and safe.
