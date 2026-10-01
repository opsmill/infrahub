# PR notes — IFC-3201

## Rework A 2026-10-01 (architecture)

Binding contract: `rework-contract-a.md`; reasoning: research R15; spec: Clarifications "Session 2026-10-01 (architecture review)".

**Defects fixed** (in the one-row-per-branch implementation):

1. The two cells owned and duplicated the data and its derivation (same query, same ranking), and the derivation lived in `.tsx`.
2. The roll-up reused the details card's band ordering, so an unreachable repository whose last import succeeded ranked first and the Git state cell read "In Sync" while another repository on the branch was syncing or unknown.
3. The per-branch query mirrored the backend's row-set rule on the client, which the epic's `InfrahubRepositoryBranchStatus` exists to keep server-side.

**New data path**: `BranchesTable` → `useBranchRepositorySummaries(flatData)`: #10779's `useGetBranchRepositories({ branchName: <default branch>, syncWithGit: true })` for the repository list, then `useQueries` over the repositories with `getRepositoryBranchStatusQueryOptions({ id, branchName: <default branch>, limit: 500 })`, `staleTime: 60_000`, 10 s poll while a row is syncing; `combine` → pure `summarizeBranchRepositories` (severity `error-import` > `unknown` > `syncing` > `in-sync`, then name) → `toBranchTableRows` → pure cells. The default branch comes from the branches provider by `is_default`, never by name.

**Requests**: 1 + R per page load (16 on the dev stack), independent of how many branch pages are loaded; no new status request on scroll; no re-fetch within 60 s of a refocus. Before: one request per loaded branch (about 40 per page, +40 per page scrolled).

**Lifted from #10658** (`ple-branches-card-ifc-3130` at ``e1042bef6e1f42686c2948d5576941fd65f447c3``):

| File | `cmp` |
|---|---|
| `frontend/app/src/entities/repository/domain/model/repository-branch-status.ts` | `identical (`cmp` against `git show`, re-checked after formatting)` |
| `frontend/app/src/entities/repository/domain/model/repository-branch-status.test.ts` | `identical (`cmp` against `git show`, re-checked after formatting)` |
| `frontend/app/src/entities/repository/api/get-repository-branch-status-from-api.ts` | `identical (`cmp` against `git show`, re-checked after formatting)` |
| `frontend/app/src/entities/repository/domain/use-cases/get-repository-branch-status.ts` | `identical (`cmp` against `git show`, re-checked after formatting)` |
| `frontend/app/src/entities/repository/domain/use-cases/get-repository-branch-status.test.ts` | `identical (`cmp` against `git show`, re-checked after formatting)` |
| `frontend/app/src/shared/api/graphql/error-handling.ts` (`hasThrownCatalogueCode`, additive) | `identical (`cmp` against `git show`, re-checked after formatting)` |

Not lifted: #10658's `get-repository-branch-status.query.ts` hook, which forces the current branch. This base gets a factory-only file at the same path (`getRepositoryBranchStatusQueryOptions`).

**Merge note, `branchStatus` key**: `repositoryQueryKeys.branchStatus(params)` is added to #10779's `repository.query-keys.ts` with #10658's member name and key shape. Both PRs touch that file, so merging #10658 gives one small, visible conflict there; resolve it by keeping one `branchStatus` member. #10658's `all` is `["repository"]`, this base's is `["repositories"]`; pick one when resolving.

**Consequences for users**: the status query needs repository view permission on all branches, so a denial reads "No permission" on every row instead of one; one failed status request reads "Could not load repositories" on every row. Merged branches, if the list filter shows them, read "No repositories". The commit shown for a fresh synced branch is the fork-point commit. The cache is no longer shared with the branch details page.

**Cubic findings folded in** (local run 2026-10-01):

1. `combine` is data-first: a result holding `data` stays `ok` when a background refetch fails.
2. `staleTime` 60 s on the status queries caps the refocus burst.
3. The `n/N` count has `sr-only` text with the per-label counts.
4. The E2E `broken_repository` fixture logs teardown failures instead of `contextlib.suppress`.
5. `contracts/ui-cells.md`: the Git state tooltip wraps the count only, not the pill.
6. `data-model.md` and research R12: `SYNC_STATUS_NO_COLOUR` has `label: null`.
7. `quickstart.md`: the fixture lives in `tests/e2e/branches/conftest.py`.
8. `quickstart.md`: every E2E command carries `-c tests/e2e/pytest.ini`.
9. `dev/knowledge/frontend/react.md`: the `combine` note drops the ticket id and the history sentence.

**Follow-ups**:

- Backend: a `repository_ids` list argument on `InfrahubRepositoryBranchStatus`, collapsing 1 + R to 2 requests without touching cells or rules.
- Backend: the aliased-resolver bug: aliasing 16 `InfrahubRepositoryBranchStatus` fields into one document returns HTTP 500 `read() called while another coroutine is already waiting for incoming data`.
- The Proposed changes cell still fetches per branch (`branch-proposed-changes-cell.tsx` calls `useGetProposedChanges`); move it to the same page-owned pattern.
- #10779: each Git state pill logs a dev-only react-aria warning (`<Focusable> child must have an interactive ARIA role`), because `git-state-pill.tsx` wraps a plain span in `Tooltip nonInteractiveTrigger`. Fix in #10779 or the design-system `Tooltip`.
- #10779: its E2E `sync_with_git` premise (`test_branch_details_repositories.py` now calls `broken_repository(sync_with_git=True)`) is unverified on a live stack.
- Docs: older Git integration pages spell the sync status differently from the schema labels this section uses; align them in a docs pass.

## Rework 2026-10-01

**Measurements**: the owner tried the one-row-per-repository list on a dev stack with 24 branches × 16 repositories: 279 rows, 280 checkboxes, about 15 000 DOM nodes, about 200 console warnings, visibly slow. The 24 per-branch repository requests took 0.36 s in total, so the cost was rendering, not fetching (research R14).

**Decision**: one row per branch. The Repositories column shows the first repository (ordering superseded by rework A: severity, then name) as a pill linking to the repository on that branch, with its Git state and 7-character commit in the tooltip, then "+N more" to the branch details page. The Git state column shows the worst state's pill with an `n/N` count and a per-label tooltip. The Commit column is dropped. Selection is the ordinary per-row = per-branch selection again.

**Removed** (back to base or deleted): the row model, the fan-out rule, the `useQueries` table hook and their tests; `branch-repository-cell.tsx`, `branch-commit-cell.tsx`, `branches-data-table.test.tsx`, `tests/fake/branch-table-rows.ts`; the anchor-row selection and the tab-order exclusion on mirror rows; the shared `getToggleSelectedRowHandler` change (generic widening, id-keyed anchor) and its test; the `frontend/packages/ui` `LinkButton` `excludeFromTabOrder` change; the `branch-proposed-changes-cell.tsx` and `branch-actions-cell.tsx` touches; `CommitHash` is no longer lifted from #10658 (no consumer), so the add/add merge concern is gone; the `test_branches.py` locator scoping.

**Kept**: the #10779 touches — `fetchConnection`'s no-op `processErrorMessage` and the card's failed state showing the server message; `RepositoryNameLink`: reverted; `repository-row.tsx` is back to base. The E2E `broken_repository` factory fixture in `tests/e2e/branches/conftest.py` and the `sync_with_git=True` premise of the details E2E. The `Select <branch>` checkbox name.

**Follow-ups**: see "Rework A" above.

## Lifted files

Since rework A: the status read listed under "Rework A" above. `CommitHash` was lifted byte-identical from #10658 (`ple-branches-card-ifc-3130` at `e1042bef6e`) on 2026-09-30 and removed again by the first rework: the Commit column is dropped and nothing else uses it.

## Touches to #10779 (`ple-branch-details-repos-infp-671`)

This PR changes things that #10779 introduced. The owner can land them on #10779 first, which shrinks this diff to the table work.

- `get-branch-repositories-from-api.ts::fetchConnection` passes a no-op `processErrorMessage` in the request context. Callers render their own failed state, so the shared client's error toast is suppressed. The details card already renders its own failed state (`BranchRepositoriesFailed`), so it stops toasting as well. That failed state now shows the server error message, so the suppressed toast loses no information on either page.
- `RepositoryNameLink`: reverted; `repository-row.tsx` is back to base. The table no longer uses it since the rework.
- The E2E `broken_repository` fixture moves from `test_branch_details_repositories.py` into `tests/e2e/branches/conftest.py`. It becomes a factory that takes `sync_with_git`, so both E2E files share it.

## Constitution V: 1 + R requests

Since rework A the table sends 1 + R requests per page load (one repository list, one status request per repository), independent of branch count and of pages loaded. The per-branch N+1 deviation of the first rework is gone. The backend `repository_ids` follow-up collapses it to 2. The owner creates the tickets.

## Error tooltip text

When a status request fails, every Repositories cell shows "Could not load repositories", and its tooltip shows the raw GraphQL `error.message`. The same message is also rendered as visually hidden text for keyboard and screen-reader users. The branch details card's failed state shows its own request's message. This is the same text the shared client toasts today, so no new wording reaches users.

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
- **PENDING: T042, quickstart scenarios.** Run `quickstart.md` scenarios 1–14 (rework A) on a dev stack. This includes the dark theme (scenario 14) and the network-tab check of 1 + R repository requests per page load (scenario 12).
- **PENDING: `test_branches.py`.** Back to base since the rework; run `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branches.py` as a regression check.

### T036 audit of `tests/e2e/branches/test_branches.py`

Superseded 2026-10-01: with one row per branch, no branch spans several rows, so the anchor-row scoping (`_anchor_branch_link`) is reverted and `test_branches.py` is back to base.
