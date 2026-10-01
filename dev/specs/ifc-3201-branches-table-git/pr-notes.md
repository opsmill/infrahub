# PR notes — IFC-3201

## Rework 2026-10-01

**Measurements**: the owner tried the one-row-per-repository list on a dev stack with 24 branches × 16 repositories: 279 rows, 280 checkboxes, about 15 000 DOM nodes, about 200 console warnings, visibly slow. The 24 per-branch repository requests took 0.36 s in total, so the cost was rendering, not fetching (research R14).

**Decision**: one row per branch. The Repositories column shows the first repository (failed imports first, then unreachable, then by name) as a pill linking to the repository on that branch, with its Git state and 7-character commit in the tooltip, then "+N more" to the branch details page. The Git state column shows the worst state's pill with an `n/N` count and a per-label tooltip. The Commit column is dropped. Selection is the ordinary per-row = per-branch selection again.

**Removed** (back to base or deleted): the row model, the fan-out rule, the `useQueries` table hook and their tests; `branch-repository-cell.tsx`, `branch-commit-cell.tsx`, `branches-data-table.test.tsx`, `tests/fake/branch-table-rows.ts`; the anchor-row selection and the tab-order exclusion on mirror rows; the shared `getToggleSelectedRowHandler` change (generic widening, id-keyed anchor) and its test; the `frontend/packages/ui` `LinkButton` `excludeFromTabOrder` change; the `branch-proposed-changes-cell.tsx` and `branch-actions-cell.tsx` touches; `CommitHash` is no longer lifted from #10658 (no consumer), so the add/add merge concern is gone; the `test_branches.py` locator scoping.

**Kept**: the #10779 touches — `fetchConnection`'s no-op `processErrorMessage` and the card's failed state showing the server message; `RepositoryNameLink`: reverted; `repository-row.tsx` is back to base. The E2E `broken_repository` factory fixture in `tests/e2e/branches/conftest.py` and the `sync_with_git=True` premise of the details E2E. The `Select <branch>` checkbox name.

**Backend follow-ups**:

- A list-of-ids variant of `InfrahubRepositoryBranchStatus` (a `repository_ids` argument), so one request covers every repository on every branch.
- The aliased-resolver bug: aliasing 16 `InfrahubRepositoryBranchStatus` fields into one document returns HTTP 500 `read() called while another coroutine is already waiting for incoming data`. `Branch` has no repositories field, so there is no other single-request path today.

Follow-up seen on the dev stack: each Git state pill logs a dev-only react-aria warning (`<Focusable> child must have an interactive ARIA role`) because `git-state-pill.tsx` (#10779) wraps a plain span in `Tooltip nonInteractiveTrigger`. One warning per pill; harmless at runtime; fix belongs in #10779 or the design-system `Tooltip`.

## Lifted files

None since the rework (2026-10-01). `CommitHash` was lifted byte-identical from #10658 (`ple-branches-card-ifc-3130` at `e1042bef6e`) on 2026-09-30 and is removed again: the Commit column is dropped and nothing else uses it.

## Touches to #10779 (`ple-branch-details-repos-infp-671`)

This PR changes things that #10779 introduced. The owner can land them on #10779 first, which shrinks this diff to the table work.

- `get-branch-repositories-from-api.ts::fetchConnection` passes a no-op `processErrorMessage` in the request context. Callers render their own failed state, so the shared client's error toast is suppressed. The details card already renders its own failed state (`BranchRepositoriesFailed`), so it stops toasting as well. That failed state now shows the server error message, so the suppressed toast loses no information on either page.
- `RepositoryNameLink`: reverted; `repository-row.tsx` is back to base. The table no longer uses it since the rework.
- The E2E `broken_repository` fixture moves from `test_branch_details_repositories.py` into `tests/e2e/branches/conftest.py`. It becomes a factory that takes `sync_with_git`, so both E2E files share it.

## Constitution V deviation: N+1 over HTTP

The table sends one repositories request per loaded branch: about 40 per page (`BRANCHES_PER_PAGE = 40`), 120 after three pages; the two cells of a row share it by query key. No branch-anchored or multi-repository query exists, and only per-branch reads meet FR-003, FR-011 and FR-012 without a backend change. Measured: 24 requests in 0.36 s total. The cache is shared with the details card.

Follow-ups: see "Backend follow-ups" above. The owner creates the tickets.

## Error tooltip text

A branch whose repositories request fails shows "Could not load repositories" in its Repositories cell, and its tooltip shows the raw GraphQL `error.message`. The same message is also rendered as visually hidden text for keyboard and screen-reader users, and the branch details card's failed state shows it too. This is the same text the shared client toasts today, so no new wording reaches users.

## Review

Eight reviewers ran on the implementation: code, tests, UI, errors, types, comments, simplify, and a CodeRabbit-style pass. The CodeRabbit CLI was not installed, so that pass was done manually instead. There were no blockers; the must-fix and should-fix items were applied in the fix pass, and the spec was corrected to match (spec Clarifications, "Session 2026-09-30 (review)").

Accepted as is:

- `RepositoryNameLink`: reverted; `repository-row.tsx` is back to base.
- ~~The hook returns rows grouped by branch id from `combine`~~ — superseded 2026-10-01: the hook is deleted.

Advisory items left as follow-ups:

- Derive the grid tracks from the column ids instead of their position (`branches-data-table.tsx`).
- Unify the chip shapes (Git state, Read-only, Status) across the design system.
- Add shared test mock helpers for the branches table tests.
- Make the `broken_repository` E2E fixture a plain fixture instead of a factory.
- Align the repository name's overflow reveal with `Tooltip`.

## Cubic (local, before the PR)

Round 1 (`cubic review -b ple-branch-details-repos-infp-671`): 7 findings, no P0/P1.

Fixed:

- `spec.md` cited `review-synthesis.md` without committing it; the synthesis is now in this directory.
- `opsmill-implement-report.md` still said the review pass was in progress and listed T039/T040 as deferred; updated.
- `dev/specs/docs/branches-list-git-state.checks.md` headed its walks with the wrong counts (17/12 for 19/14); corrected.
- The `LinkButton` workaround comment now names `react-aria-components@1.20`, per the code-doc rule on upstream workarounds. (Moot since the rework: the `LinkButton` change is reverted.)

Round 2 (after the fixes) could not run: the cubic CLI returned `Subscription expired` with an empty issue list. The four fixes above are verified against the source; cubic's PR review is the second round.

Declined, with reasons that will also answer the same findings on the PR:

- One repositories request per loaded branch (P2): the recorded Constitution V deviation above, measured at 0.36 s for 24 branches, with the backend follow-ups. No client-side concurrency cap exists in TanStack Query; batching belongs in the backend variant.
- E2E tests never run against a stack (P2): recorded under "Live-stack verification pending"; they run in this PR's CI E2E job.
- Base stacked toward `stable` (P3): epic IFC-3104 mandates that every PR under it targets the integration branch `cross-branch-repo-status-infp-671`; #10779 sits on it and this PR sits on #10779. The integration branch catches up with `develop` once and lands there when the epic completes.

## Stacking and rebase

This branch is stacked on #10779, which targets the epic integration branch `cross-branch-repo-status-infp-671`. If #10779 is squash-merged, rebase this branch with `--onto` so its commits are not replayed:

```bash
git rebase --onto origin/cross-branch-repo-status-infp-671 b7076f29f9 ple-branches-table-git-ifc-3201
```

`b7076f29f9` is #10779's tip at the time of writing; use its last commit before the squash if it has moved.

## Live-stack verification pending

No Infrahub stack was running when Phase 6 was implemented, and none was started. The E2E code was linted (`ruff format`, `ruff check`, `ty check`) and collected (`uv run pytest -c tests/e2e/pytest.ini --collect-only -q tests/e2e/branches/`, 27 tests, shard guard passed). Nothing below has run against a stack.

- **PENDING: T032 premise.** Follow "E2E premise verification" in `research.md`. Check that a `sync_with_git=False` branch's details card does not list the broken `CoreRepository`, that a `sync_with_git=True` branch's card does, and that the failed repository has a commit on that branch.
- **PENDING: T034, details E2E premise change (#10779 finding).** `test_branch_details_repositories.py` now calls `broken_repository(sync_with_git=True)`. Before this PR the fixture created its branch with `BranchAPI.create`'s default (`sync_with_git=False`). This changes #10779's test premise. Run `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branch_details_repositories.py` and check that the card lists the repository, the band reads "import failed" and "is missing a configuration file", and "View task log" opens `/tasks/<task id>`.
- **PENDING: T035/T055, `/branches` Git columns.** Run `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branches_git_columns.py`. On the broken branch's row, check that the repository pill names the repository and links to its page and that the Git state pill reads "Import Error" (the `sync_status` dropdown label in `backend/infrahub/core/schema/definitions/core/repository.py`). Also check that a `sync_with_git=False` branch reads "Not synced with Git".
- **PENDING: T042, quickstart scenarios.** Run `quickstart.md` scenarios 1–14 (rewritten 2026-10-01) on a dev stack. This includes the dark theme (scenario 14) and the network-tab check of one repositories request per branch (scenario 12).
- **PENDING: `test_branches.py`.** Back to base since the rework; run `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branches.py` as a regression check.

### T036 audit of `tests/e2e/branches/test_branches.py`

Superseded 2026-10-01: with one row per branch, no branch spans several rows, so the anchor-row scoping (`_anchor_branch_link`) is reverted and `test_branches.py` is back to base.
