# Implementation report — IFC-3201 Repository, Git state and Commit columns on the branches table

**Spec dir**: `dev/specs/ifc-3201-branches-table-git/`
**Branch**: `ple-branches-table-git-ifc-3201` (base `origin/ple-branch-details-repos-infp-671`, PR #10779)
**Base commit at start of implementation**: `6ba0561c28`
**Head commit at end of implementation**: `8d370d917c` (before the review fix pass `5e9ecfd9d1`, the docs/knowledge commit and the rebase onto the moved base; the PR tip is whatever `git log -1` shows at PR time)
**Run**: 2026-09-30, seven clean-context chunks dispatched sequentially, one fixup by the orchestrator.

## 1. Chunk ledger

| # | Chunk (tasks.md phase) | Tasks | ✅ / ⚠️ / ❌ | Commit | Flagged upward |
|---|---|---|---|---|---|
| 1 | Phase 1: Setup | T001–T006 (6) | 6 / 0 / 0 | `33eff358e7` | `table.getRow` throws on unknown ids, so the id-anchored handler resolves through `rowsById`. One "why" comment each in the handler and in `fetchConnection`. |
| 2 | Phase 2: Foundational | T007–T014 (8) | 8 / 0 / 0 | `c3d73248f4` | SC-007 row-reference stability achieved with module-level `WeakMap` caches (per branch object, per fetch object), not `useMemo`; `toBranchTableRows` is therefore called once per branch, not once over all branches (contract deviation, documented). |
| 3 | Phase 3: US1 | T015–T021 (7) | 7 / 0 / 0 | `cb5c9400d4` | Three new columns built by a private `getBranchRepositoryColumns()` helper. "No filter/sort control" test asserts absence of buttons in the new header cells (the grid has no `columnheader` roles). |
| 4 | Phase 4: US2 | T022–T027 (6) | 6 / 0 / 0 | `2c74067c38` | Design-system `Checkbox` exposes `excludeFromTabOrder`/`aria-label` (react-aria), used instead of raw `tabIndex`. Visually hidden inputs are clicked through their `<label>` in tests. T024 exercises the real paginated query (offsets `[0, 40]`) with 41 branches × 3 repos = 123 rows. |
| 5 | Phase 5: US3 | T028–T031 (4) | 4 / 0 / 0 | `3a536f1e6a` | No-toast cases go through the real `fetchConnection` with `fetch` stubbed (mocking `graphqlClient.query` would bypass `handleGraphQLErrors`). Verified T029 is not vacuous by temporarily removing the no-op and watching it fail. Pre-existing `get-branch-repositories-from-api.test.ts` broke on the added context option → fixed by the orchestrator in `50186e1496`. |
| 6 | Phase 6: E2E | T032–T036 (5) | 3 / 2 / 0 | `cdeff50eff` | No stack was available: T032 (live premise check) and T034 (live run) are ⚠️ partial; the code-derived expectation (`sync_with_git=True` needed for both broken-repository tests) is recorded in research.md and pr-notes.md. T036 audit found and fixed two strict-mode locator violations in `test_branches.py` (`main` now fans out). `/branches` has no row element, so the new E2E reads the Repository/Git state/Commit cells as siblings of the identifier cell. |
| 7 | Phase 7: Polish | T037, T038, T041, T043 (4 of 7) | 4 / 0 / 0 | `8d370d917c` | T039 (docs) and T040 (knowledge) left for the ship pipeline's phases 4.6 and 4.5; T042 (dev-stack scenarios) pending. One earlier-chunk test file needed a whitespace-only biome fix. |

## 2. Tasks not completed

| Task | Reason |
|---|---|
| T032 | Live-stack premise verification: needs a running Infrahub. Code-derived expectation recorded; confirm live before merge. |
| T034 | The details E2E was switched to the shared fixture with `sync_with_git=True`; the `uv run pytest` run needs the e2e stack. |
| T042 | Quickstart scenarios 1–14 on a dev stack (incl. dark theme, network-tab request count): pending. |

## 3. Local-pass evidence

All runs in chromium via vitest browser mode from `frontend/app/`.

| Test id | Type | Run command | Passed at | Env | Verbatim pass line |
|---|---|---|---|---|---|
| `src/entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler.test.ts` (new) | unit | `pnpm vitest run <file>` | 2026-09-30T11:30:09Z | chromium/vitest | `Tests  6 passed (6)` |
| `src/shared/components/display/commit-hash.test.tsx` (lifted) | component | `pnpm vitest run <file>` | 2026-09-30T11:30:11Z | chromium/vitest | `Tests  5 passed (5)` |
| `src/entities/repository/ui/branch-repositories/branch-repositories-card.test.tsx` (extended, T029) | component | `pnpm vitest run <file>` | 2026-09-30T12:17:31Z | chromium/vitest | `Tests  21 passed (21)` |
| `src/entities/branches/domain/rules/to-branch-table-rows.test.ts` (new) | unit | `pnpm vitest run <file>` | 2026-09-30T11:38:19Z | chromium/vitest | `Tests  9 passed (9)` |
| `src/entities/branches/ui/hooks/use-branch-table-rows.test.ts` (new) | hook | `pnpm vitest run <file>` | 2026-09-30T11:38:21Z | chromium/vitest | `Tests  5 passed (5)` |
| `src/entities/branches/ui/branches-table/get-branch-table-columns.test.tsx` (new, extended T028) | component | `pnpm vitest run <file>` | 2026-09-30T12:17:23Z | chromium/vitest | `Tests  16 passed (16)` |
| `src/entities/branches/ui/branches-table/branches-table.test.tsx` (new, extended T024, T030) | component | `pnpm vitest run <file>` | 2026-09-30T12:17:35Z | chromium/vitest | `Tests  5 passed (5)` |
| `src/entities/branches/ui/branches-table/branches-data-table.test.tsx` (new) | component | `pnpm vitest run <file>` | 2026-09-30T12:06:33Z | chromium/vitest | `Tests  11 passed (11)` |
| `src/entities/repository/api/get-branch-repositories-from-api.test.ts` (assertion widened) | unit | `pnpm vitest run <file>` | 2026-09-30T12:2xZ (orchestrator run) | chromium/vitest | `PASS (3) FAIL (0)` (rtk-filtered output) |
| `tests/e2e/branches/test_branches_git_columns.py` (new) | e2e | `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branches_git_columns.py` | deferred — no local stack in this run | n/a | collected: `27 tests collected in 0.05s` (whole `tests/e2e/branches/`) |
| `tests/e2e/branches/test_branch_details_repositories.py` (fixture switched) | e2e | `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branch_details_repositories.py` | deferred — no local stack in this run | n/a | collected (see above) |
| `tests/e2e/branches/test_branches.py` (locators scoped) | e2e | `uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branches.py` | deferred — no local stack in this run | n/a | collected (see above) |
| Full frontend suite (T043) | all | `cd frontend/app && pnpm test` | 2026-09-30T12:32:18Z | chromium/vitest | `Test Files  229 passed (229)` / `Tests  1734 passed (1734)` |

CI gate (T043): `cd frontend && pnpm exec biome ci .` → `Checked 1643 files in 1360ms. No fixes applied.`; `pnpm knip` → exit 0, no findings; `pnpm exec betterer ci` → `"fix ts error" stayed the same. (186 issues)`; `pnpm test` → see last row. Lifted `commit-hash*` files re-verified byte-identical to `ple-branches-card-ifc-3130` @ `e1042bef6e`.

## 4. Review findings

Eight reviewers ran in parallel on `origin/ple-branch-details-repos-infp-671...8d370d917c`: speckit code, tests, errors, types, comments and simplify; a UI-craft pass (`emil-ui-review`); and a CodeRabbit pass that fell back to a manual review because the `coderabbit` CLI is not installed. One synthesizer deduplicated and verified them (scratchpad `review-synthesis.md`). No blockers.

| Severity | File | Finding | Outcome |
|---|---|---|---|
| major | `branches-data-table.test.tsx` | "rows repeat the branch cells" asserted only that all texts were equal, so it passed on empty cells | fixed: asserts the expected text per column |
| minor | `cells/branch-repository-cell.tsx` | state texts used `text-subtle-muted` (< 4.5:1) | fixed: `text-foreground-muted`; spec corrected |
| minor | `cells/branch-repository-cell.tsx` | error reason only in a non-focusable tooltip | fixed: `sr-only` text alongside the tooltip |
| minor | `get-branch-table-columns.tsx`, cells | repeated branch link, PC pill and actions trigger stayed tab stops on mirror rows | fixed: out of the tab order on non-anchor rows; `LinkButtonProps.excludeFromTabOrder` added in `packages/ui` |
| minor ×2 | `use-branch-table-rows.ts` | spec ID in a comment; redundant map `set` | fixed, then superseded: the module-level caches were removed (see below) |
| minor | `use-branch-table-rows.ts` (found by the new identity test) | `WeakMap` caches did not survive an earlier branch growing: TanStack's `replaceEqualDeep` pairs `combine` output by array index and copies mismatched rows | fixed: `combine` returns rows keyed by branch id; rule called once over all branches; no caches |
| minor | `to-branch-table-rows.ts` | `domain/rules` imported another entity's `domain/model` | fixed: `BranchTableRepository` alias exported from the row model |
| minor | `branches-table.tsx` | hook called inside a JSX prop | fixed: hoisted |
| minor | `branch-repositories-states.tsx` (#10779) | the suppressed toast left the card's failed state without the server message | fixed: message shown as muted text in the alert |
| minor | `tests/e2e/branches/conftest.py` | teardown swallowed exceptions silently | fixed: logged with traceback |
| minor | `tests/e2e/branches/test_branches.py` | two branch-link locators still unscoped under fan-out | fixed: anchor-row scoped |
| minor ×6 | test files | SC-003 mutation assertion, sleep-based refocus test, TanStack-internals test, unpinned `processErrorMessage`, `.Toastify__toast` selectors, clipboard stub not restored | fixed |
| minor | `branch-repository-cell.tsx` | `!== "ok"` catch-all | fixed: exhaustive `switch` on `row.state` |
| nit ×5 | comments/docstrings | restating or naming code | fixed |
| advisory | `branches-data-table.tsx`, pills, tests, e2e fixture | derive tracks from column ids; unify chip shapes; shared test mock helpers; plain fixture; Tooltip on repository name | deferred, listed in `pr-notes.md` |

Post-fix gate: `biome ci .` → `Checked 1643 files … No fixes applied.` (direct binary; the `pnpm exec biome` wrapper crashes on this machine today, on the main checkout too); `knip` clean; `betterer ci` → 186 issues, unchanged; `pnpm test` → `Test Files 229 passed (229)`, `Tests 1739 passed (1739)`; ruff clean on `tests/e2e/branches`.

## 5. Autonomous decisions

- E2E tests were written and collected but not run: no Infrahub stack was available and none was started (owner instruction). Recorded as pending in `pr-notes.md`.
- The `sync_with_git=True` change to #10779's details E2E rests on reading `getRepositoryListKind`, not on a live run.
- T039/T040 were done by the pipeline's docs and knowledge phases after the review pass, not inline in chunk 7 (both ticked; commit `f6e307168c` before the rebase).
- The pre-existing fetcher test that broke on the T003 context option was fixed by widening its assertion (`expect.objectContaining` on the context), not by reverting T003.
- Chunk 1's commit carries an `Opus 5.5` co-author line (the sub-agent's own attribution); not amended.

## 6. Suggested next steps

1. Done: phase 4 review fix pass (§4), phase 4.5 knowledge, phase 4.6 docs, phase 5 gate (green after the fix pass), rebase onto the moved base.
2. Phase 5.5 cubic loop, then the PR (see `pr-notes.md`).
3. Before merge: run the three E2E files against a stack (T032/T034), and quickstart scenarios (T042).

## 7. Rework (2026-10-01)

The owner tried the fan-out on a dev stack (24 branches × 16 repositories: 279 rows, 280 checkboxes, about 15 000 DOM nodes, about 200 console warnings, visibly slow; the 24 repository requests took 0.36 s in total) and reversed the one-row-per-repository decision. Binding contract: `rework-contract.md`; reasoning: research R14; spec: Clarifications "Session 2026-10-01".

| Area | Change |
|---|---|
| Layout | One row per branch. **Repositories**: first repository by `rankRepositories` (failed first) as a `LinkPill` with a `<state> · <commit>` tooltip, then "+N more" to the branch details page. **Git state**: worst state's `GitStatePill` with an `n/N` count and a per-label tooltip. Commit column dropped. |
| Data | Each cell calls #10779's `useGetBranchRepositories`; one request per branch, shared by key with the other cell and the branch details card. No table-level `useQueries`. |
| Removed | Row model, fan-out rule, table hook and their tests; repository and commit cells; `branches-data-table.test.tsx`; `tests/fake/branch-table-rows.ts`; anchor-row selection and mirror-row tab-order exclusion; the shared `getToggleSelectedRowHandler` change; the `packages/ui` `LinkButton` change; the proposed-changes and actions cell touches; the `CommitHash` lift; the `test_branches.py` locator scoping. |
| Kept | `fetchConnection` no-op `processErrorMessage`; card failed state with the server message; `RepositoryNameLink`: reverted; `repository-row.tsx` is back to base. |
| Tests | `get-branch-table-columns.test.tsx` and `branches-table.test.tsx` rewritten to the contract; card and fetcher no-toast cases unchanged; `test_branches_git_columns.py` asserts the repository pill and the "Import Error" pill. |
| Documents | Spec, plan, research (R14; R1/R3/R4/R8/R13 superseded), data model, contracts, quickstart, tasks (Phase 8, superseded tasks marked), PR notes, the docs section, the prose checks, the changelog fragment, and `dev/knowledge/frontend/{shared-components,react}.md`. |
| Backend follow-ups | A `repository_ids` list variant of `InfrahubRepositoryBranchStatus`; the aliased-resolver HTTP 500 (`read() called while another coroutine is already waiting for incoming data`) when 16 `InfrahubRepositoryBranchStatus` fields share one document. `Branch` has no repositories field. |

Still pending from §2: T032, T034 and T042 (live stack), now against the rewritten quickstart scenarios.

## 8. Rework A (2026-10-01)

The architecture review of §7's implementation found three defects: the two cells owned and duplicated the data and its derivation (pure logic in `.tsx`); the roll-up reused the details card's band ordering, so an unreachable but in-sync repository could hide a syncing or unknown one; and the per-branch query mirrored the backend's row-set rule on the client (`getRepositoryListKind`). Binding contract: `rework-contract-a.md`; reasoning: research R15; spec: Clarifications "Session 2026-10-01 (architecture review)"; tasks: Phase 9 (T059–T077), with T048–T050 superseded.

| Area | Change |
|---|---|
| Data | The page owns the fetch: `useBranchRepositorySummaries` reads the repository list once on the default branch and `InfrahubRepositoryBranchStatus` once per repository (`useQueries`, `staleTime` 60 s, 10 s poll while syncing); `combine` → pure `summarizeBranchRepositories`. 1 + R requests, independent of pagination. |
| Ordering | `compareSyncStatusSeverity`: `error-import` > `unknown` > `syncing` > `in-sync`, then name. Operational status no longer takes part. |
| Rows and cells | `BranchTableRow` (`BranchListItem` + `repositorySummary`) via `toBranchTableRows`; both cells are pure; the tooltip string is `formatRepositorySummary`; the Git state tooltip wraps the count only, with `sr-only` text. |
| Lifted from #10658 | Status model, API, use case, their tests, `hasThrownCatalogueCode`; SHA and `cmp` results in `pr-notes.md`. Not the hook (it forces the current branch): a `branchStatus` key and a factory-only query file instead. |
| Spec consequences | Denial or failure reads on every row; merged branches read "No repositories"; cache no longer shared with the branch details page. |
| Documents | Spec, plan, research R15 (R5/R9/R10/R14 per-branch parts superseded), data model, contracts, quickstart, tasks Phase 9, PR notes, the docs section's ordering and state sentences and its prose checks, `dev/knowledge/frontend/react.md`, `dev/guidelines/frontend/page-architecture.md`. |
| Cubic | Nine local findings folded in (listed in `pr-notes.md`). |

Still pending: T032, T034 and T042 (live stack), now against the rework A quickstart.
