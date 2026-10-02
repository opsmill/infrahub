# Implementation report: Branch details, Git repositories and tasks (INFP-671)

- **Status:** INCOMPLETE. 61 of 62 tasks are done. T062 is partial: the quickstart walk needs a live stack.
- **Spec dir:** `dev/specs/infp-671-branch-details-repos/`
- **Branch:** `ple-branch-details-repos-infp-671`, based on `origin/cross-branch-repo-status-infp-671`. Not pushed, no PR.
- **Base commit:** `5ddfe5cc1e` · **Head commit:** `eb3a658ea6` (before this report's commit)
- **Wall-clock:** about 1h30

## 1. Chunk ledger

| # | Chunk | Tasks | ✅/⚠️/❌ | Commits | Flags |
|---|---|---|---|---|---|
| 1 | Phase 1 Setup | T001–T002 | 2/0/0 | ab048e72e0, 67ffafab8a | T001 was verified by reading code, not by reproducing (see §6). Backend asks are in `follow-ups.md`. |
| 2 | Phase 2 Foundational | T003–T009 | 7/0/0 | 88d66ba827, 01d868d184, bd9a3a66ea, 03529c1adf, 693df05c98 | `repository.test.ts` was added to pin the constants. |
| – | Orchestrator | design doc fix | – | 3bfaf31101 | Coordinator request: dark mode and IFC-3199 notes in `design/04-review.md` and `05-handoff.md`. |
| 3a | US1 domain/api/queries | T010–T017 | 8/0/0 | 4f80e9b241, 0c91e27201, ed8f8d9ea6 | `graphqlClient.query` throws on GraphQL errors, so the api function unwraps the urql `CombinedError`. |
| 3b | US1 UI | T018–T024 | 7/0/0 | 3248f78c36 | Adds `getBranchQspOverride` so the `branch` param isn't doubled. PERMISSION_DENIED raises no toast (the shared handler already skips it). |
| 4a | US2 domain/api/query | T025–T030 | 6/0/0 | e1b3ac06b0, 3a79cf2fd4 | `getLastErrorLine` unwraps Prefect's `Finished in state Failed('…')` wrapper (see §6). |
| 4b | US2 bands | T031–T035 | 5/0/0 | f336e15412 | Truncation notice moved below the bands, per plan.md. Uses `border-danger/30`, because there is no danger-border token. |
| 5 | US3 | T036–T037 | 2/0/0 | ed2706b9ea | E2E written, not run. |
| 6a | US4 domain/queries | T038–T045 | 8/0/0 | fc54885610 | `getKindLabel` is injected, which keeps the rule pure. |
| 6b | US4 UI | T046–T051 | 6/0/0 | 271f4388f1, 96241158c4 | Tasks links carry `branch=` plus `filters=[branch__value]`. The tutorial e2e was also updated (it used `tasks-accordion`). |
| 7 | US5 | T052–T056 | 5/0/0 | 3b723e20dd, bb55b1a3cb | Refresh uses `branchesQueryKeys.all`, not `.details` (see §6). |
| 8 | Polish | T057–T062 | 5/1/0 | fe2489927a, 975e4d3083, d65d25ce9f, cdde41b9c1 | Dark mode was checked by grep, a token audit and a computed-colour test, not by eye. T062 was written up as `pr-notes.md`. |
| R | Review fixes | – | – | 51bebbd8b2, 07b43298d8, eb3a658ea6 | See §5. |

## 2. Tasks not completed

- **T062** (⚠️ partial, unticked). No dedicated stack was available: the backend on :8000 belongs to another branch and is read-only. Quickstart scenarios 1–11 were therefore not walked. `pr-notes.md` has the draft PR material (R2 outcome, backend asks, the INFP-670 sign-off request for ungated Merge, the e2e tests not yet run) and lists each scenario as "to walk by hand", with the tests that cover it.

## 3. Local-pass evidence

All vitest runs are browser mode (chromium, vitest 4.1.10), run from `frontend/app`. Final full-suite run by the orchestrator, after the review fixes: `./node_modules/.bin/vitest run` → `Test Files  222 passed (222)` / `Tests  1669 passed (1669)`.

| Test id | Type | Run command | Passed at | Env | Pass line |
|---|---|---|---|---|---|
| shared/utils/table-pagination.test.ts, shared/components/table/table-pagination.test.tsx, refresh-button.test.tsx, branch-urls.test.ts, repository.test.ts | unit/component | `vitest run <files> src/entities/branches` | 2026-09-29T17:56:46Z | vitest browser chromium | `Tests  89 passed (89)` |
| repository/domain/rules/rank-repositories.test.ts, domain/use-cases/get-branch-repositories.test.ts | unit | `vitest run src/entities/repository/domain` | 2026-09-29T18:05:10Z | same | `Tests  29 passed (29)` |
| repository/ui/branch-repositories/branch-repositories-card.test.tsx | component | `vitest run src/entities/repository src/entities/branches` | 2026-09-29T18:13Z | same | `Tests  113 passed (113)` |
| repository/domain/rules/get-last-error-line.test.ts, domain/use-cases/get-repository-import-error.test.ts | unit | `vitest run <2 files>` | 2026-09-29T18:18:50Z | same | `Tests  16 passed (16)` |
| repository/ui/branch-repositories/repository-error-bands.test.tsx | component | `vitest run src/entities/repository` | 2026-09-29T18:23:15Z | same | `Tests  93 passed (93)` |
| branches/ui/branch-details.test.tsx | component | `vitest run src/entities/branches/ui/branch-details.test.tsx` | 2026-09-29T18:27:06Z | same | `Tests  5 passed (5)` |
| tasks/domain/model/workflow-labels.test.ts, rules/get-task-related-label.test.ts, use-cases/get-branch-tasks.test.ts | unit | `vitest run src/entities/tasks/domain` | 2026-09-29T18:31:04Z | same | `Tests  40 passed (40)` |
| tasks/ui/branch-tasks/branch-tasks-card.test.tsx, branch-details.test.tsx (updated) | component | `vitest run src/entities/tasks/ui/branch-tasks src/entities/branches/ui/branch-details.test.tsx` | 2026-09-29T18:37:15Z | same | `Tests  20 passed (20)` |
| branches/ui/branch-details/branch-details-header.test.tsx | component | `vitest run <file>` | 2026-09-29T18:46:02Z | same | `Tests  6 passed (6)` |
| repository-error-bands.test.tsx › switches both band colours with the dark theme | component | `vitest run <file>` | 2026-09-29T18:52:44Z | same | `Tests  14 passed (14)` |
| Review-fix tests (get-branch-repositories-from-api.test.ts, query-option polling tests, out-of-range page tests, denied rule) | unit/component | `vitest run --reporter=verbose <13 files>` | 2026-09-29T19:08:00Z | same | `Tests  103 passed (103)` |
| tests/e2e/branches/test_branch_details.py (layout, card above Merge, `branch-tasks-card`, Validate row, header copy/refresh) | e2e | `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branch_details.py` | deferred — local E2E not supported | needs a dedicated stack | – |
| tests/e2e/branches/test_branch_details_repositories.py::TestBranchDetailsRepositoryImportError::test_import_error_band_links_to_the_task_page | e2e | `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/ -m shard_branches_repo` | deferred — local E2E not supported | needs a dedicated stack | – |
| tests/e2e/tutorial/tutorials/test_tutorial_1_object_create_update_diff_and_merge.py::…::test_4_view_diff_and_merge_into_main | e2e | `uv run pytest -c tests/e2e/pytest.ini <file>` | deferred — local E2E not supported | needs a dedicated stack | – |

The e2e files pass `py_compile`, `ruff check` and `ruff format --check`.

## 4. CI gate (final, run by the orchestrator at `eb3a658ea6`)

| Command | Result |
|---|---|
| `pnpm exec biome ci .` (run as `../node_modules/.bin/biome ci .` because the rtk hook mangles `pnpm exec biome`) | pass |
| `pnpm knip` | pass (only the config hint about `src/shared/api/graphql/generated/**`, which the base already has) |
| `pnpm exec betterer ci` | pass: "1 test stayed the same" (186 issues, same as base) |
| `pnpm test` (`vitest run`) | pass: 222 files, 1669 tests |

## 5. Review findings

| Severity | File | Summary | Resolution |
|---|---|---|---|
| High | repository/domain/model/repository.ts | `IMPORT_LOG_LIMIT=500`, but logs come oldest first, so a long log loses its last error line | Fixed: raised to the backend cap of 10 000. Backend ask for newest-first logs added to follow-ups.md. |
| High | tasks/ui/queries/get-branch-tasks.query.ts | Tasks offset was computed from the unclamped URL page | Fixed: page clamped to at least 1, and `usePageInRange` writes the page back when it's past the end (tasks and repos). |
| High | repository/api/get-branch-repositories-from-api.ts | The CombinedError unwrapping had no test | Fixed: api test added. |
| Medium | branch-tasks-card | The failed count included CRASHED, but the link opens FAILED only | Fixed: count is FAILED only (the Tasks page filter takes a single state). |
| Medium | query options | Polling rules were untested, and one test name was misleading | Fixed. |
| Medium | get-branch-tasks.ts | Unreachable `if (errors)` branch | Removed. |
| Medium | get-repository-import-error.ts | Bare `catch` swallowed errors silently | Now logs with `console.error`; the fallback is kept. |
| Medium | get-branch-repositories.ts | One denied error made the whole result "denied" | Fixed: "denied" only when every error is a denial. |
| Low | branch-urls.ts | `withBranch` was dead (only its test used it) | Removed. |
| Low | branch-repositories-card.tsx | "View all repositories" ignored Sync-off read-only kind | Fixed. |
| Low | import-error-band.tsx | With a task but no error line, the band links to the task. FR-022 says repository; data-model says task | Deferred: kept data-model's behaviour, since the task log is more useful. Spec wording to align. |
| Low | several | No Retry in failed states; `queryKey`/`queryKeys` not mutually exclusive; `isReadOnly` redundant with `kind`; unused `operational_status.color`; result-type placement drift from data-model; the two import-workflow lists could drift; e2e docstring points at a spec path; RefreshButton shows success when a refetch fails (predates this work) | Deferred. |

Simplify pass: skipped. The review-fix commit had already consolidated the code, and another automated rewrite would have needed another full gate.

## 6. Autonomous decisions

- **T001** was verified by reading code (`build_import_plan` tags every import run with the branch and the repository), not by live reproduction, because the only stack is read-only. Every path is found except the worker bootstrap import. T058 seeds an initial add.
- **Prefect wrapper:** `getLastErrorLine` unwraps `Finished in state Failed('Flow run encountered an exception: …')` to show `<Type>: <message>`. This deviates from the "verbatim" wording of T025/T027.
- **Refresh keys:** `branchesQueryKeys.all` instead of `.details({branchName})`, because the header and action state read other branch queries.
- **Links:** `getBranchQspOverride` is used as `overrideParams`, which avoids a doubled `branch` param. `withBranch` was removed.
- **Failed count** is FAILED only, so it matches what the link opens. CRASHED is excluded.
- **Truncation notice** sits below the bands, per plan.md, not in the table as T020 says.
- **E2E tests** are written but not run: there is no dedicated stack. Please confirm this call.
- **Design docs** `04-review.md` and `05-handoff.md` were corrected at the coordinator's request (commit 3bfaf31101). No spec or code change was needed.

## 7. Suggested next steps

1. Walk quickstart scenarios 1–11 on a dedicated stack, and run the three e2e files there.
2. Check both themes by eye on the branch page.
3. Open the PR using `pr-notes.md`, including the INFP-670 sign-off request for ungated Merge and the backend asks in `follow-ups.md`.
4. Decide the FR-022 and data-model wording, and look at the deferred low findings.
