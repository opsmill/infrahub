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

## Live-stack verification pending

No Infrahub stack was running when Phase 6 was implemented, and none was started. The E2E code was linted (`ruff format`, `ruff check`, `ty check`) and collected (`uv run pytest -c tests/e2e/pytest.ini --collect-only -q tests/e2e/branches/`, 27 tests, shard guard passed). Nothing below has run against a stack.

- **PENDING: T032 premise.** Follow "E2E premise verification" in `research.md`. Check that a `sync_with_git=False` branch's details card does not list the broken `CoreRepository`, that a `sync_with_git=True` branch's card does, and that the failed repository has a commit on that branch.
- **PENDING: T034, details E2E premise change.** `test_branch_details_repositories.py` now calls `broken_repository(sync_with_git=True)`. Before this PR the fixture created its branch with `BranchAPI.create`'s default (`sync_with_git=False`). This changes #10779's test premise. Run `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branch_details_repositories.py` and check that the card lists the repository, the band reads "import failed" and "is missing a configuration file", and "View task log" opens `/tasks/<task id>`.
- **PENDING: T035, `/branches` Git columns.** Run `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branches_git_columns.py`. On the broken branch's row, check the repository link, the "Import Error" pill (the `sync_status` dropdown label in `backend/infrahub/core/schema/definitions/core/repository.py`), a 7-character commit and its "Copy commit <hash>" button. Also check that a `sync_with_git=False` branch reads "Not synced with Git". The table is a flat CSS grid with no row element, so the test finds a row's cells as the 3rd, 4th and 5th siblings after its `branch-identifier-cell`. A column reorder breaks these offsets.
- **PENDING: T036, `test_branches.py`.** Run `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branches.py`.

### T036 audit of `tests/e2e/branches/test_branches.py`

Every row of a branch repeats its name link (`BranchNameCell`). Only the first row carries the "Select <branch>" checkbox.

- `get_by_role("link", name="main", exact=True)` (two uses in `test_search_for_a_branch`) is a real violation. `main` syncs with Git, and in the `shard_branches_repo` stack it lists `demo-edge` (`demo_edge_repo`). It also lists every other CoreRepository alive at that moment, because repositories are branch-agnostic: `test_repository_objects.py` in the same shard, or a broken repository not yet cleaned up. So `main` can span several rows. Both uses are now scoped to the anchor row through `_anchor_branch_link` (the identifier cell that holds the "Select main" checkbox).
- `den1-maintenance-conflict` and `atl1-delete-upstream` are created with `sync_with_git=False` (`tests/e2e/data/scenario_branches.py`). They list read-only repositories only, the shard has none, so each is one row. Left unchanged.
- The random branches in the other tests (`BranchAPI.create` default `sync_with_git=False`) are one row each. Their `get_by_role("link", name=...)` and `get_by_text(branch)` locators are left unchanged.
- Out of scope, noted only: `test_branch_details.py::test_opens_detail_page_from_branches_list` clicks a `sync_with_git=False` branch's link, so it is one row and safe.
