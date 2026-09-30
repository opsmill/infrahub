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

- `get-branch-repositories-from-api.ts::fetchConnection` passes a no-op `processErrorMessage` in the request context. Callers render their own failed state, so the shared client's error toast is suppressed. The details card already renders its own failed state (`BranchRepositoriesFailed`), so it stops toasting as well. That failed state now shows the server error message, so the suppressed toast loses no information on either page.
- `RepositoryNameLink` is extracted from `repository-row.tsx` into `repository-name-link.tsx`, so the card and the table cell share one link.
- The E2E `broken_repository` fixture moves from `test_branch_details_repositories.py` into `tests/e2e/branches/conftest.py`. It becomes a factory that takes `sync_with_git`, so both E2E files share it.

## Shared `getToggleSelectedRowHandler` change

`entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler.ts` is also used by the object table.

- The generic is widened from `T extends NodeCore` to `T`, because branch table rows are not nodes.
- The shift-click anchor is stored by row id, not by row index. Rows can be inserted above the last-selected row between two clicks, which happens when a branch's repositories resolve. The range is still computed from the current indexes of the two rows. Object-table behaviour is unchanged when no rows are inserted, and its tests stay green.

## Shared `LinkButton` change (`frontend/packages/ui`)

`LinkButtonProps` gains an optional `excludeFromTabOrder`. React Aria's `Link` honours the prop at runtime but omits it from its types, so `LinkButton` forwards it through a spread with a one-line comment. The branches table uses it to keep the repeated branch-name link and Proposed changes pill on mirror rows out of the tab order (FR-008). `LinkPill` inherits the prop unchanged.

## Constitution V deviation: N+1 over HTTP

The table sends one repositories request per loaded branch: about 40 per page (`BRANCHES_PER_PAGE = 40`), 120 after three pages. No branch-anchored or multi-repository query exists, and only per-branch reads meet FR-003, FR-011 and FR-012 without a backend change. The cache is shared with the details card, and SC-007 bounds refocus requests and re-renders.

Follow-up: a backend list-of-ids variant of `InfrahubRepositoryBranchStatus`, so one request covers every loaded branch. The owner creates the ticket.

## Error tooltip text

A branch whose repositories request fails shows "Could not load repositories", and its tooltip shows the raw GraphQL `error.message`. The same message is also rendered as visually hidden text for keyboard and screen-reader users, and the branch details card's failed state shows it too. This is the same text the shared client toasts today, so no new wording reaches users.

## Review

Eight reviewers ran on the implementation: code, tests, UI, errors, types, comments, simplify, and a CodeRabbit-style pass. The CodeRabbit CLI was not installed, so that pass was done manually instead. There were no blockers; the must-fix and should-fix items were applied in the fix pass, and the spec was corrected to match (spec Clarifications, "Session 2026-09-30 (review)").

Accepted as is:

- `RepositoryNameLink` reveals a truncated name with the native `title`, not `Tooltip`.
- The hook returns rows grouped by branch id from `combine` and relies on TanStack's structural sharing for row identity; the first implementation's `WeakMap` caches were removed after the review pass's identity test showed they did not survive an earlier branch growing (research R13 addendum).

Advisory items left as follow-ups:

- Derive the grid tracks from the column ids instead of their position (`branches-data-table.tsx`).
- Unify the chip shapes (Git state, Read-only, Status) across the design system.
- Add shared test mock helpers (for example a `mockBranchTableDeps()`) for the branches table tests.
- Make the `broken_repository` E2E fixture a plain fixture instead of a factory.
- Align the repository name's overflow reveal with `Tooltip`.

## Cubic (local, before the PR)

Round 1 (`cubic review -b ple-branch-details-repos-infp-671`): 7 findings, no P0/P1.

Fixed:

- `spec.md` cited `review-synthesis.md` without committing it; the synthesis is now in this directory.
- `opsmill-implement-report.md` still said the review pass was in progress and listed T039/T040 as deferred; updated.
- `dev/specs/docs/branches-list-git-state.checks.md` headed its walks with the wrong counts (17/12 for 19/14); corrected.
- The `LinkButton` workaround comment now names `react-aria-components@1.20`, per the code-doc rule on upstream workarounds.

Declined, with reasons that will also answer the same findings on the PR:

- One repositories request per loaded branch (P2): the recorded Constitution V deviation above, with the backend list-of-ids follow-up. No client-side concurrency cap exists in TanStack Query; batching belongs in the backend variant.
- E2E tests never run against a stack (P2): recorded under "Live-stack verification pending"; they run in this PR's CI E2E job.
- Base stacked toward `stable` (P3): epic IFC-3104 mandates that every PR under it targets the integration branch `cross-branch-repo-status-infp-671`; #10779 sits on it and this PR sits on #10779. The integration branch catches up with `develop` once and lands there when the epic completes.

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
