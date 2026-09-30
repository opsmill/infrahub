# Implementation Plan: Repository, Git state and Commit columns on the branches table

**Branch**: `ple-branches-table-git-ifc-3201` (on `ple-branch-details-repos-infp-671`, PR #10779) | **Date**: 2026-09-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `dev/specs/ifc-3201-branches-table-git/spec.md`; phase 1 research `research-brief.md`; decided plan `plan-synthesis.md`.

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Frontend-only. The branches list (`/branches`) gains three columns after "Proposed Changes": **Repository**, **Git state**, **Commit**. A branch fans out to one row per repository the backend returns for it, and every branch cell (checkbox, name, status, proposed changes, actions) repeats on each row. A branch with no repositories, or whose repository data is pending, denied or failed, keeps exactly one row with an explicit text or a spinner.

Approach (research R1–R13):

- **Data**: one `useQueries` entry per loaded branch over #10779's `getBranchRepositoriesQueryOptions`, so the list and the branch details card share one cache and one 10 s "while syncing" poll. No new GraphQL document, no backend change.
- **Fan-out**: a pure rule `toBranchTableRows` in `entities/branches/domain/rules/` maps branches plus their fetch states to a discriminated `BranchTableRow[]`. Ordering is injected (`rankRepositories`), because `domain/rules` may not import another entity's rules.
- **Selection**: the first row of each branch is its **anchor** (`id === branch.id`) and the only selectable row. The other rows mirror the anchor's state. TanStack's own selection APIs then count branches, so the toolbar, the delete modal and the logout reset stay untouched. The shared shift-range handler stores the last-selected row **id** and resolves indexes at shift time, so a range stays correct after rows above it expand.
- **Cells**: three new cells reuse `GitStatePill` (#10779), a new `RepositoryNameLink` (extracted from #10779's `RepositoryRow`) and `CommitHash` (lifted byte-identical from #10658).
- **Layout**: the three new columns get fixed-width tracks, so no column shifts sideways as data arrives (SC-004). `branches-data-table.tsx::defaultGridTemplateColumns` becomes `[fit-content(WIDE), fit-content(MAX), minmax(150px,200px), REPOSITORY_TRACK, GIT_STATE_TRACK, COMMIT_TRACK, repeat(n-7, fit-content(MAX)), 2.5rem]`, with `REPOSITORY_TRACK = "minmax(12rem, 18rem)"`, `GIT_STATE_TRACK = "9rem"` and `COMMIT_TRACK = "8rem"` declared as constants next to the template.

## Technical Context

**Language/Version**: TypeScript (strict), React 19 with the React Compiler (no `useMemo`/`useCallback`/`React.memo`; existing `React.useMemo` calls in touched files are removed).

**Primary Dependencies**: TanStack Table v8 (8.21.3; row selection, `getRowId`, `enableRowSelection` predicate), TanStack Query (`useQueries`, `queryOptions`), `@infrahub/ui` (`Checkbox`, `Spinner`, `Tooltip`), Tailwind v4 theme tokens (`text-subtle-muted`, `text-foreground-muted`), `lucide-react`. No new dependency.

**Storage**: N/A (reads only).

**Testing**: Vitest in browser mode (`vitest.config.ts`, Playwright provider). Pure rule tests in `.test.ts`, component tests in `.test.tsx` rendered with `tests/components/render`, and `vi.mock` on query hooks and use-cases, as the frontend usually does. Fakes: #10779's `tests/fake/branch-repositories.ts` reused, plus a new local `tests/fake/branch-table-rows.ts`.

**Target Platform**: Desktop browsers; light and dark themes (tokens only, no literal colours except the schema's own dropdown colour).

**Project Type**: Web application, frontend slice (`frontend/app`). `frontend/packages/ui` is read-only.

**Performance Goals**: The branch cells render as fast as today (SC-004). Repository requests are one per loaded branch (≈40 per page of `BRANCHES_PER_PAGE = 40`), independent of the repository count. Repeated branch cells add no request: proposed-changes queries are deduplicated by query key. `useBranchTableRows` passes a `combine` to `useQueries` and returns a stable per-branch record; rows are rebuilt only for branches whose result reference changed, so one resolution re-renders one branch's rows (SC-007, research R13). No `useMemo`.

**Constraints**: Only data the backend returns today. There is no Upstream, "behind by N", Last import or operational status (FR-016). No column filter, sort or hide (FR-015, FR-017). `isTruncated` is ignored (spec Assumptions). Page size still counts branches (FR-010).

**Scale/Scope**: 13 new files and 8 changed files under `frontend/app/`, plus one new E2E test and one fixture promotion under `tests/e2e/branches/` (see Constitution Check IV).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ | No schema change. The Git state label, colour and description come from the `sync_status` dropdown the backend returns (`BranchRepositorySyncStatus`). `GitStatePill` falls back to a grey badge when the colour is missing and hard-codes no state. The row set per branch is what the backend returns; `sync_with_git` only chooses the empty-state wording (FR-003). |
| II. Branch-Safe by Default | ✅ | Every repository request carries **the row's** branch: `getBranchRepositoriesQueryOptions({ branchName: branch.name, … })`, keyed by `branchName`, sent as the GraphQL branch context. Nothing reads the branch selector's current branch. The repository link uses `getBranchQspOverride(branch.name, is_default)`, so it opens the repository on the row's branch and adds no parameter on the default branch. The feature only reads, so there is no merge behaviour to specify. |
| III. Type Safety & Explicit Contracts | ✅ | `BranchTableRow` is a discriminated union on `state`, and cells narrow on it. `BranchRepositoriesFetch` is a union over #10779's `BranchRepositoriesResult`. No `any` or `!`. New display columns use `columnHelper.display`, so they need no `as`. The existing accessor `as ColumnDef` casts are left alone. The three `BRANCH_FIELD_SCHEMAS` entries follow the file's existing header-only `as AttributeSchema` shape (`branch-field-schemas.ts::BRANCH_FIELD_SCHEMAS`), which is pre-existing convention and not a new pattern. Contracts are in `contracts/`. |
| IV. Test Discipline | ✅ | Test details are listed after this table. |
| V. Query Performance & Efficiency | ⚠️ deviation, justified | No backend query changes. There is one HTTP request per loaded branch (≈40 per page, 120 after three pages): an N+1 at the HTTP layer. V is written for Cypher, but its spirit applies, so the deviation is recorded in Complexity Tracking. The spec accepts it (Assumptions). It shares the cache with branch details, runs no per-repository or per-cell request, and has a bounded selection (`REPOSITORY_FETCH_LIMIT`). Batching options (b)/(c) are the recorded follow-up (research R5). |
| VI. Security & Input Boundaries | ✅ | Reads only. Permission is enforced by the server and surfaced per branch: `PERMISSION_DENIED` → "No permission" (FR-012). Text is rendered as text. |
| VII. Simplicity & Maintainability | ✅ | Details are listed after this table. |
| Quality gates | ✅ | biome ci, knip, betterer ci, vitest. Towncrier fragment `changelog/+ifc-3201-branches-table-git.added.md`. `dev/knowledge/frontend/shared-components.md` gains `CommitHash` only if #10658 has not merged first (its row travels with the lift). |

- **User-facing documentation**: one section in `docs/docs/git-integration/branch-synchronization.mdx` (or the page the docs skill chooses in phase 4.6) describing the three columns, the per-repository rows and the two empty-state texts ("Not synced with Git", "No repositories"). Owned by the docs phase, in the same PR.
- **Knowledge capture**: the anchor-row selection pattern goes in `dev/knowledge/frontend/shared-components.md` (phase 4.5).

**IV. Test Discipline, in detail:**

- **Pure rule test**: `to-branch-table-rows.test.ts` covers N rows, unique ids, the anchor first, injected ordering, both empty texts' states, denied, error, pending and a missing entry, and isolation between branches.
- **Component tests**: one test per SC-006 state (loaded, loading, "Not synced with Git", "No repositories", denied, failed, no colour, no commit), plus:
  - selection: one branch; shift-range over two branches; shift-range after a branch expanded from pending to N still counts branches; select-all; the header checkbox's indeterminate and all states with non-anchor rows present; logout reset clears the selection; a selected branch stays selected through pending → N;
  - accessibility: only the anchor checkbox is in the tab order, named "Select <branch>"; non-anchor checkboxes are named "Select <branch> (<repository name>)";
  - pending: one `role=status` per pending branch (the Repository cell's spinner only), not three;
  - failed: "Could not load repositories" carries the error message as a tooltip; a failed background refetch keeps the loaded rows (data-model invariant 9);
  - the column order, no filter or sort control;
  - the grid template has one track per column and the three new tracks are fixed.
- **Branch details card**: its failed state renders without a toast (`branch-repositories-card.test.tsx`, touched only if the existing test does not already cover it).
- **`CommitHash`**: its lifted test.
- **E2E: one happy-path case, in this PR.** The constitution asks for E2E on user-facing features and the fixture it needs exists on this base. New file `tests/e2e/branches/test_branches_git_columns.py` (`pytestmark = pytest.mark.shard_branches_repo`; `tests/e2e/conftest.py::_SHARD_MARKERS` is a fixed set, so there is no own marker): the `/branches` row for the broken branch shows the repository name, the "Import Error" pill and a 7-character commit; a second assertion checks a branch with no repositories reads "Not synced with Git".
  - **Pre-step**: verify on a live stack how a `sync_with_git=False` branch holding a `CoreRepository` renders on the branch details page. #10779's `test_branch_details_repositories.py` creates its branch with `sync_with_git=False` (via the `tests/e2e/helpers.py::BranchAPI.create` default) while its card queries read-only repositories for such a branch, so that test's premise needs checking before this feature's E2E reuses the fixture (Risks).
  - The import-error fixture is class-local today, `test_branch_details_repositories.py::TestBranchDetailsRepositoryImportError::broken_repository` (#10779, on this base). It is promoted to `tests/e2e/branches/conftest.py` as a **function-scoped** fixture (it uses `tmp_path`), together with its helpers, and gains a `sync_with_git: bool` parameter: `True` for this feature's test, while the branch details test keeps whatever it needs. The details test switches to the shared one. This is the third touch on a #10779 file (Complexity Tracking).
  - The shared fixture on PR #10649 (`test_repository_sync_status.py`) is unmerged.
  - **Locator audit**: audit `tests/e2e/branches/test_branches.py` locators for strict-mode violations under fan-out (`get_by_role("link", name="main", exact=True)` and the other branch-name links) and scope them to the anchor row.

**VII. Simplicity & Maintainability, in detail:**

- **Reuse first**: `GitStatePill`, `getBranchRepositoriesQueryOptions`, `rankRepositories`, `TableCell`, `TableColumnHeaderSimple`, `Spinner`, `CopyToClipboardButton` (via `CommitHash`) and the shift-range handler are all reused.
- **New primitive**: only `RepositoryNameLink`, extracted from existing markup, with two callers on day one.
- **Kept deliberately simple**: `CommitHash` is lifted, not rewritten. The grid template names three fixed tracks as constants rather than introducing a per-column tracks map (deferred to IFC-3146/3147). Selection uses the anchor row instead of controlled state or dedup.

Post-design re-check (after critique 2026-09-30): V is a recorded deviation. It and the touches outside the feature's own files are justified in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3201-branches-table-git/
├── spec.md
├── research-brief.md    # Phase 1 research + owner decisions
├── plan-synthesis.md    # Decided plan (input)
├── plan.md              # This file
├── research.md          # R1–R13 + risks
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── ui-cells.md
│   └── graphql.md
└── tasks.md             # /speckit-tasks (not created here)
```

### Source Code (repository root)

All paths are under `frontend/app/`. There is no `api/` change in any entity.

```text
src/entities/branches/
├── domain/model/branch-table-row.ts                      # NEW BranchTableRow, BranchTableRowState, BranchRepositoriesFetch, isBranchAnchorRow
├── domain/rules/to-branch-table-rows.ts                  # NEW toBranchTableRows (fan-out, ordering injected)
├── domain/rules/to-branch-table-rows.test.ts             # NEW
└── ui/
    ├── hooks/use-branch-table-rows.ts                    # NEW useBranchTableRows (useQueries → rule)
    └── branches-table/
        ├── branch-field-schemas.ts                       # CHANGED + repository, git_state, commit
        ├── get-branch-table-columns.tsx                  # CHANGED BranchTableRow helper, r.branch.* accessors, anchor lookup, 3 display columns
        ├── branches-data-table.tsx                       # CHANGED row type, enableRowSelection predicate, selectedRows → branches, fixed tracks for the 3 new columns (REPOSITORY_TRACK, GIT_STATE_TRACK, COMMIT_TRACK), useMemo removed
        ├── branches-data-table.test.tsx                  # NEW selection, a11y names, cells per state, headers, grid template (one track per column, 3 fixed)
        ├── branches-table.tsx                            # CHANGED data = useBranchTableRows(flatData), useMemo removed
        ├── branches-table.test.tsx                       # NEW pending → N rows, branch cells first, no toast
        └── cells/
            ├── branch-name-cell.tsx                      # CHANGED checkbox aria-label "Select <name>"
            ├── branch-repository-cell.tsx                # NEW
            ├── branch-git-state-cell.tsx                 # NEW
            └── branch-commit-cell.tsx                    # NEW

src/entities/repository/ui/branch-repositories/
├── repository-name-link.tsx                              # NEW extracted from RepositoryRow (icon, link, Read-only chip)
└── repository-row.tsx                                    # CHANGED uses RepositoryNameLink (#10779 file)

src/entities/nodes/object/ui/object-table/utils/
└── get-toggle-selected-row-handler.ts                    # CHANGED generic <T extends NodeCore> → <T>; last-selected anchor stored by row id

src/shared/components/display/
├── commit-hash.tsx                                       # NEW lifted byte-identical from #10658
└── commit-hash.test.tsx                                  # NEW lifted byte-identical from #10658

tests/fake/
└── branch-table-rows.ts                                  # NEW FULL_COMMIT_HASH, SYNC_STATUS_NO_COLOUR, generateBranchTableRow
```

Outside `frontend/app/`: `changelog/+ifc-3201-branches-table-git.added.md` (NEW); `docs/docs/git-integration/branch-synchronization.mdx` (CHANGED, docs phase); `tests/e2e/branches/conftest.py` (NEW or CHANGED, promoted fixture), `tests/e2e/branches/test_branches_git_columns.py` (NEW), `tests/e2e/branches/test_branch_details_repositories.py` (CHANGED), `tests/e2e/branches/test_branches.py` (CHANGED only if the locator audit finds a violation).

**Structure Decision**: This follows the entity layer in `dev/knowledge/frontend/entities-structure.md`.

- **Branches entity**: the row type and fan-out live in `entities/branches` because they describe branches-table rows. `domain/model` may import `entities/repository/domain/model`, and `domain/rules` imports only its own model. The hook sits in `branches/ui/hooks` and may import `repository/ui/queries` and `repository/domain/rules` (ui → other entity's ui/domain is allowed).
- **Repository entity**: `RepositoryNameLink` stays next to its first caller in `entities/repository/ui/branch-repositories/`.
- **Shared**: `CommitHash` stays at #10658's path so the eventual merge is add/add identical.

## Risks

| Risk | Mitigation |
|---|---|
| A non-permission GraphQL error toasts once. The shared client's `error-handling.ts::handleGraphQLErrors` calls `notifyUser` unless the request context sets `processErrorMessage`, and #10779's `get-branch-repositories-from-api.ts::fetchConnection` passes only `{ branch }`. Network errors do not toast. | The toast is deduplicated (`toastId: "alert-error"`), so at most one toast per page. FR-013's "no toast" holds for network errors only. Decision: close the gap. `fetchConnection` passes a no-op `processErrorMessage` in its request context, so a GraphQL-level failure surfaces only as the row's "Could not load repositories" (and, on the branch details card, as its own failed state). One-line change in a #10779 file, recorded in Complexity Tracking (research R10). The failure message stays reachable: the "Could not load repositories" text carries the query error's message as a tooltip, and the card's failed state is asserted to render without a toast. |
| Unreachable repositories rank above healthy ones although their status isn't shown (FR-016). | Spec FR-006a states the rule. Rows are still grouped by rank, then by name. |
| ≈40 requests per page (N+1 over HTTP). | Accepted by the spec and recorded as a Constitution V deviation (Complexity Tracking). The cache is shared, SC-007 bounds refocus requests and re-renders, and batching is a follow-up (R5). |
| `isTruncated` is ignored, so a list over 500 repositories is silently partial. | Spec Assumptions. `REPOSITORY_FETCH_LIMIT` is far above real counts. |
| Pending → N rows pushes lower branches down. | Spec edge case accepts it. The branch keeps its position, and its anchor id is stable. |
| The branches page reload button refreshes branch queries only. | The 10 s poll covers syncing repositories. Otherwise refocus and remount refresh. |
| Anchor-row selection relies on the row order matching the data order, and row indexes move when a branch above expands from pending to N rows. | `manualSorting: true` and no client sort. The shift-range handler stores the last-selected row id and resolves indexes at shift time (Complexity Tracking). Tests assert shift-range over two branches and a shift-range after a branch expanded from pending to N. |
| The PR rebases whenever #10779 changes (three touched files), and the `CommitHash` lift can drift from its source. | `CommitHash` is lifted from `ple-branches-card-ifc-3130` at the SHA recorded in the PR body (the implementer records the exact `git rev-parse` at lift time). Before merge, `git diff` the lifted file against that branch's tip. The base is a double stack (#10779 on the epic branch), so a squash-merge of #10779 requires `git rebase --onto`. |
| The branch details E2E's premise is unverified: #10779's `test_branch_details_repositories.py` creates its branch with `sync_with_git=False` (the `tests/e2e/helpers.py::BranchAPI.create` default), yet asserts a broken `CoreRepository` while its card queries read-only repositories for such a branch. | Pre-step in Constitution Check IV: verify on a live stack how that branch renders before this feature's E2E reuses the fixture; the promoted fixture takes `sync_with_git` explicitly. |
| Three changes are really #10779 behaviour changes (card toast, extraction, fixture). | If the owner prefers, the `processErrorMessage` no-op, the `RepositoryNameLink` extraction and the fixture promotion can land on #10779 first; this PR then rebases. The owner is asked at the phase 2 checkpoint. |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| A shared file changes: `get-toggle-selected-row-handler.ts::getToggleSelectedRowHandler` generic widened from `<T extends NodeCore>` to `<T>`, and the last-selected row is stored by **id** (not `row.index`); both indexes are resolved at shift time via `table.getRow(id).index`, falling back to a plain toggle when the stored id no longer exists. | `BranchTableRow` is not a `NodeCore`, and fan-out moves row indexes asynchronously (a branch above expands from pending to N), so a stored index can select branches the user never picked for bulk Delete. The body never uses the bound; object tables behave identically because their rows never move. | Forking the handler duplicates the shift-range logic. Casting the row breaks III. Controlled selection state (option ii) adds two rules, a hook and state for the same result. |
| One repositories request per visible branch (N+1 at the HTTP layer; Constitution V). | No branch-anchored or multi-repository query exists, and only per-branch reads meet FR-003, FR-011 and FR-012 without a backend change. | (b) per-repository pivot over `InfrahubRepositoryBranchStatus`: needs ALLOW_ALL, one denial blanks the whole column, and its order does not match the table. Follow-up: a backend list-of-ids variant of `InfrahubRepositoryBranchStatus` (the reader already accepts `repository_ids`); follow-up ticket to be created by the owner at the checkpoint. |
| Touching #10779's `get-branch-repositories-from-api.ts::fetchConnection` to pass a no-op `processErrorMessage`. | FR-013 forbids toasts for a per-branch load failure; the shared client toasts every non-permission GraphQL error unless the request opts out. | Catching the toast downstream is impossible (it fires inside the client). A separate fetcher for the list duplicates two GraphQL documents and splits the cache the spec requires to be shared. |
| Promoting #10779's class-local E2E fixture `broken_repository` to `tests/e2e/branches/conftest.py`. | The constitution requires an E2E case for user-facing changes; the fixture already builds the exact import-error scenario. | Duplicating the fixture body in a second file doubles a 50-line async setup and its cleanup. |
| Touching #10779's `repository-row.tsx` to extract `RepositoryNameLink`. | FR-006 requires "the same" repository name, link and Read-only marker as branch details. Two callers justify the extraction (VII). | Copying the markup lets the two drift, which is exactly what FR-006 forbids. Importing `RepositoryRow` itself isn't possible because it renders a whole `<tr>`. |
