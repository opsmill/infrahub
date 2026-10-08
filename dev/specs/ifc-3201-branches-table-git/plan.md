# Implementation Plan: Repositories and Git state columns on the branches list

**Branch**: `ple-branches-table-git-ifc-3201` (on `ple-branch-details-repos-infp-671`, PR #10779) | **Date**: 2026-09-30, rework 2026-10-01, rework A 2026-10-01, entity extraction 2026-10-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `dev/specs/ifc-3201-branches-table-git/spec.md`; the decisions behind each rework are in [research.md](./research.md) and in the spec's Clarifications.

## Summary

Frontend-only. The branches list (`/branches`) gains two columns after "Proposed Changes": **Repositories** and **Git state**. The list keeps one row per branch (research R14). The Repositories cell shows the repository in the worst Git state as a pill, then "+N more" linking to the branch details page; the Git state cell shows the worst state's pill with an `n/N` count and a per-state tooltip on the count. A branch with no repositories, or whose repository data is pending, denied or failed, shows an explicit text or a spinner in the Repositories cell and a blank Git state cell.

Approach (research R15 and the entity decisions that follow it):

- **Data**: the page owns the fetch, through the `branch-git-status` entity. `useGetBranchGitStatuses(branchNames)` (`entities/branch-git-status/ui/hooks/use-get-branch-git-statuses.ts`) reads the repository list once with `useQuery(getBranchGitRepositoriesQueryOptions({ limit: 500, offset: 0 }))`, the entity's own `GET_BRANCH_GIT_REPOSITORIES` document (`CoreGenericRepository`: id, name, `__typename`, count). It then runs `useQueries` over the repositories with `getRepositoryBranchStatusQueryOptions({ repositoryId, limit: 500 })`, the entity's own `GET_REPOSITORY_BRANCH_STATUS($id, $limit)` document over the epic's `InfrahubRepositoryBranchStatus`, with `staleTime: 60_000` and a 10 s `refetchInterval` while a row is syncing. Neither request carries a branch context, so both read the default branch. `combine` calls the pure rule `summarizeBranchGitStatuses`, which pivots the rows to one `BranchGitStatus` per branch name. 1 + R requests, independent of pagination.
- **Failure handling, narrowest scope**: a failed, denied or cut-short repository list affects every row; a failed, denied or pending status read affects only that repository. The cell shows the repositories that loaded and a notice "1 repository could not be loaded" or "N repositories could not be loaded", with `<repository>: <message>` or `<repository>: No permission` as the reason. "No permission" on every row only when the list is denied or every status read is denied.
- **Ordering**: `compareWorstSyncStatusFirst` (`error-import` > `unknown` > `syncing` > `in-sync`), then repository name; `repositories[0]` is the pill and the worst state. A row without a sync status takes the schema's `unknown` choice.
- **Rows**: `toBranchTableRows(branches, gitStatuses)` builds `BranchTableRow` (`BranchListItem` + `gitStatus`), the view-model the table renders. `getRowId: row.id`, selection, toolbar and delete modal unchanged.
- **Cells**: pure, no hooks. `BranchRepositoriesCell({ branch })` reuses `LinkPill`, `Tooltip` and the Proposed changes cell's "+N more" link; `BranchGitStateCell({ branch })` reuses `GitStatePill` (#10779). Tooltip strings come from the pure rules in `branch-git-status/domain/rules/format-branch-git-status.ts`. Test ids: `branch-repositories-cell-<branch>`, `branch-git-state-cell-<branch>`.
- **Layout**: each column carries its grid track in `meta.gridTrack`; Repositories `minmax(12rem, 18rem)`, Git state `9rem`, other columns `fit-content(...)`.

The first implementation (2026-09-30) fanned each branch out to one row per repository (research R1, R4, R13). The second (rework 2026-10-01) fetched per branch from inside the cells (research R14). Both are in git history.

## Technical Context

**Language/Version**: TypeScript (strict), React 19 with the React Compiler (no `useMemo`/`useCallback`/`React.memo`).

**Primary Dependencies**: TanStack Table v8 (8.21.3; unchanged row selection), TanStack Query (`useQuery`, and `useQueries` with `combine`), `@infrahub/ui` (`Checkbox`, `Spinner`, `Tooltip`), the app's `LinkPill` (`@/shared/components/ui/link-pill`), Tailwind v4 theme tokens (`text-foreground-muted` for the state texts), `lucide-react`. No new dependency.

**Storage**: N/A (reads only).

**Testing**: Vitest in browser mode (`vitest.config.ts`, Playwright provider). Pure rule and mapper tests in `.test.ts`, a `renderHook` test for `useGetBranchGitStatuses` mocking the `getBranchGitRepositories` and `getRepositoryBranchStatus` use cases, component tests for the two pure cells with Git statuses given as data, and a table test mocking the two use cases. Fakes: `tests/fake/branch-git-status.ts`, `tests/fake/branch.ts`.

**Target Platform**: Desktop browsers; light and dark themes (tokens only, no literal colours except the schema's own dropdown colour).

**Project Type**: Web application, frontend (`frontend/app`). `frontend/packages/ui` is read-only.

**Performance Goals**: The branch cells render as fast as today (SC-004). One row per branch keeps the DOM at today's size plus two cells per row. Requests: 1 + R per page load (R = number of repositories), none on scroll, none within 60 s of a refocus (SC-007). Structural sharing in `combine` keeps untouched branches' statuses by reference. No `useMemo`.

**Constraints**: Only data the backend returns today. No Commit column, Upstream, "behind by N", Last import or operational status (FR-016). No column filter, sort or hide (FR-015, FR-017). `count` of a status page marks a cut page: a branch missing from a cut page reads an error, never a guess; `limit: 500` is far above real branch counts. Page size still counts branches (FR-010).

**Scale/Scope**: one new entity (`branch-git-status`: two GraphQL documents, their mappers, two use cases, models, four rules, two query-options factories and their keys, one hook), one row view-model, two pure cells and their column wiring, the branch mutations' cache invalidation, their tests, and the E2E files under `tests/e2e/branches/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design, after each rework, and after the entity extraction (2026-10-08).*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ | No schema change. The Git state label, colour and description come from the `sync_status` dropdown the status query returns; a missing value takes the schema's `unknown` choice. `GitStatePill` falls back to a grey badge when the colour is missing. The repositories counted per branch are the backend's status rows (FR-003); `sync_with_git` only chooses the empty-state wording. |
| II. Branch-Safe by Default | ✅ | The repository list and every status request carry no branch context, so they read the default branch, never the branch selector's branch. The status rows name their branch, and the pivot keys by that name. The repository pill uses `getBranchQsp(branch.name)`; "+N more" uses `getBranchDetailsUrl(branch.name)`. The feature only reads. |
| III. Type Safety & Explicit Contracts | ✅ | `BranchGitStatus`, `RepositoryListFetch` and `RepositoryStatusFetch` are discriminated unions; cells narrow on `status`. `BranchTableRow extends BranchListItem`, so the table's consumers keep receiving branches. No `any` or `!`. Contracts are in `contracts/`. |
| IV. Test Discipline | ✅ | Test details are listed after this table. |
| V. Query Performance & Efficiency | ✅ | 1 + R requests, independent of branch count and of pages loaded. The backend `repository_ids` follow-up collapses it to 2 without touching cells or rules. |
| VI. Security & Input Boundaries | ✅ | Reads only. Permission is enforced by the server: a denied repository list, or a `PERMISSION_DENIED` on every status read, reads "No permission" on every row; a single denied status read is named in the "could not be loaded" notice (FR-012). Text is rendered as text. |
| VII. Simplicity & Maintainability | ✅ | Details are listed after this table. |
| Quality gates | ✅ | biome ci, knip, betterer ci, vitest. Towncrier fragment `changelog/+branches-list-git-columns.added.md`. |

- **User-facing documentation**: the section in `docs/docs/git-integration/branch-synchronization.mdx` describing the two columns, their texts and the "could not be loaded" notice.
- **Knowledge capture**: `dev/knowledge/frontend/entities-structure.md` records when a new screen's data need gets its own entity and queries instead of flags on another entity's query.

**IV. Test Discipline, in detail:**

- **Rule tests** (`branch-git-status/domain/rules/`): `summarize-branch-git-statuses.test.ts` (list failure on every branch; denied only when every read is; loaded repositories kept beside failed and pending ones; grouping by branch name; worst first with ties by name; counts; cut page → error; no rows → empty ok); `sync-status-severity.test.ts`; `format-branch-git-status.test.ts`; `get-unknown-sync-status.test.ts`; `to-branch-git-status-error.test.ts`.
- **Mapper and use-case tests**: `branch-git-repository.mappers.test.ts`, `repository-branch-status.mappers.test.ts`, `get-branch-git-repositories.test.ts`, `get-repository-branch-status.test.ts` (denial mapping).
- **Hook and query tests**: `use-get-branch-git-statuses.test.ts` (one list request, one status request per repository with `limit: 500`, statuses keyed by branch, data first on a failed background refetch, denied and failed list, per-repository failures); `get-repository-branch-status.query.test.ts` (`refetchInterval` only while syncing, `staleTime` 60 000).
- **Component tests**: `cells/branch-repositories-cell.test.tsx` and `cells/branch-git-state-cell.test.tsx` with Git statuses as data; `branches-table.test.tsx` and `branches-data-table.test.tsx` mocking the two use cases (branch cells render while statuses are pending, 1 + R requests, no new status request on a second page, no toast on failure).
- **Mutation tests**: create, delete, merge and rebase invalidate `branchGitStatusQueryKeys.all`.
- Deviation from IV's mock rule, house style: tests mock use cases (`vi.mock`), per `dev/guides/frontend/writing-component-tests.md`; no external HTTP is mocked because none is called.
- **E2E: one happy-path case, in this PR.** `tests/e2e/branches/test_branches_git_columns.py` (`pytestmark = pytest.mark.shard_branches_repo`) finds the cells by test id: on the broken branch's row the repository pill names the repository and links to it on that branch, and the Git state pill reads "Import Error"; a `sync_with_git=False` branch reads "Not synced with Git", or lists only read-only repositories when other tests left some. The `broken_repository` fixture (`tests/e2e/branches/conftest.py`, dataclass in `tests/e2e/branches/broken_repository.py`) logs teardown failures. Every command carries `-c tests/e2e/pytest.ini`.

**VII. Simplicity & Maintainability, in detail:**

- **Reuse first**: `GitStatePill`, `LinkPill`, `Tooltip`, `TableCell`, `TableColumnHeaderSimple`, `Spinner`, the repository polling intervals, and the Proposed changes cell's "+N more" pattern.
- **One owner for the data**: the hook fetches, the rule derives, the row view-model carries, the cells render. No derivation in `.tsx`.
- **Own queries, not flags**: the entity reads its own two documents instead of adding flags to #10779's branch repositories query or lifting #10658's status files.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3201-branches-table-git/
├── spec.md
├── plan.md                        # This file
├── research.md                    # Decisions and rejected approaches
├── data-model.md
├── quickstart.md
├── tasks.md
├── contracts/
│   ├── ui-cells.md
│   └── graphql.md
├── checklists/
│   └── requirements.md
├── critiques/
│   └── critique-2026-09-30.md
└── opsmill-implement-report.md
```

### Source Code (repository root)

All paths are under `frontend/app/`.

```text
src/entities/branch-git-status/                    # NEW entity: the branches list's Git state
├── api/
│   ├── get-branch-git-repositories-from-api.ts    # GET_BRANCH_GIT_REPOSITORIES: CoreGenericRepository id, name, __typename, count
│   ├── get-repository-branch-status-from-api.ts   # GET_REPOSITORY_BRANCH_STATUS($id, $limit)
│   ├── branch-git-repository.mappers.ts (+ test)  # wire → BranchGitRepositoryPage
│   └── repository-branch-status.mappers.ts (+ test) # wire → RepositoryBranchStatusPage
├── domain/
│   ├── model/
│   │   ├── branch-git-repository.ts               # BranchGitRepository, BranchGitRepositoryPage
│   │   ├── branch-git-status.ts                   # BranchGitStatus, BranchRepositoryState, SyncStatusCount, FailedRepository, UnloadedRepository, BranchGitStatusError
│   │   └── repository-branch-status.ts            # RepositoryBranchStatus, RepositoryBranchStatusPage
│   ├── rules/
│   │   ├── summarize-branch-git-statuses.ts (+ test) # summarizeBranchGitStatuses, RepositoryListFetch, RepositoryStatusFetch
│   │   ├── sync-status-severity.ts (+ test)       # compareWorstSyncStatusFirst
│   │   ├── format-branch-git-status.ts (+ test)   # tooltip, count and notice texts
│   │   ├── get-unknown-sync-status.ts (+ test)    # the schema's unknown choice
│   │   └── to-branch-git-status-error.ts (+ test) # PERMISSION_DENIED or UNKNOWN
│   └── use-cases/
│       ├── get-branch-git-repositories.ts (+ test)
│       └── get-repository-branch-status.ts (+ test)
└── ui/
    ├── hooks/use-get-branch-git-statuses.ts (+ test) # useGetBranchGitStatuses(branchNames)
    └── queries/
        ├── branch-git-status.query-keys.ts        # branchGitStatusQueryKeys: all, repositories, repositoryBranchStatus
        ├── get-branch-git-repositories.query.ts   # getBranchGitRepositoriesQueryOptions
        └── get-repository-branch-status.query.ts (+ test) # getRepositoryBranchStatusQueryOptions (60 s stale, 10 s poll while syncing)

src/entities/repository/domain/model/repository.ts # CHANGED + REPOSITORY_SYNC_STATUS_IN_SYNC, REPOSITORY_SYNC_STATUS_UNKNOWN

src/entities/branches/
└── ui/
    ├── branches-list.tsx (+ test)                 # CHANGED reload also invalidates branchGitStatusQueryKeys.all
    ├── queries/*.mutation.ts (+ tests)            # CHANGED create, delete, merge, rebase invalidate branchGitStatusQueryKeys.all
    └── branches-table/
        ├── branch-table-row.ts (+ test)           # NEW BranchTableRow, toBranchTableRows
        ├── branch-field-schemas.ts                # CHANGED + repositories, git_state
        ├── get-branch-table-columns.tsx           # CHANGED typed on BranchTableRow; 2 display columns; gridTrack in meta
        ├── branches-data-table.tsx (+ test)       # CHANGED typed on BranchTableRow; tracks from column meta
        ├── branches-table.tsx (+ test)            # CHANGED data={toBranchTableRows(branches, gitStatuses)}
        └── cells/
            ├── branch-name-cell.tsx               # CHANGED checkbox aria-label "Select <name>"
            ├── branch-repositories-cell.tsx (+ test) # REWRITTEN pure
            └── branch-git-state-cell.tsx (+ test) # REWRITTEN pure
```

Outside `frontend/app/`: `changelog/+branches-list-git-columns.added.md`; `docs/docs/git-integration/branch-synchronization.mdx`; `dev/knowledge/frontend/entities-structure.md`; `tests/e2e/branches/conftest.py` (shared fixture), `tests/e2e/branches/broken_repository.py`, `tests/e2e/branches/test_branches_git_columns.py`, `tests/e2e/branches/test_branch_details_repositories.py` (changed premise).

**Structure Decision**: This follows the entity layer in `dev/knowledge/frontend/entities-structure.md`. The list's Git state is its own entity, `branch-git-status`, with its own repository-list and status documents and queries. `BranchesTable` passes branch names to `useGetBranchGitStatuses`; the cells import their types and formatters from `branch-git-status/domain` and `GitStatePill` from `repository/ui/branch-repositories`. `branches` imports `branch-git-status`; `branch-git-status` does not import `branches`.

## Risks

| Risk | Mitigation |
|---|---|
| A failed, denied or cut-short repository list blanks the whole column. | The branch cells always render; the reason stays reachable on "Could not load repositories". A failure of one status read affects only that repository's entry in each cell. |
| A non-permission GraphQL error toasts through the shared client unless the request opts out. | Both documents pass a no-op `processErrorMessage`; the use cases map errors to `BranchGitStatusError` (`code`, `message`). `branches-table.test.tsx` asserts no toast on a failure. |
| `limit: 500` truncates a list of more than 500 repositories, or of more than 500 branches per repository. | Far above real counts; `count` above the rows read is detected, and the affected rows read "Could not load repositories" with the reason. |
| Up to R parallel status requests, each polling every 10 s while one of its rows is syncing. | The backend `repository_ids` follow-up collapses the reads to one request. |
| The PR rebases whenever #10779 changes. | The base is a double stack (#10779 on the epic branch), so a squash-merge of #10779 requires `git rebase --onto` (steps in the PR description). |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Promoting #10779's class-local E2E fixture `broken_repository` to `tests/e2e/branches/conftest.py`, with its dataclass in `tests/e2e/branches/broken_repository.py`. | The constitution requires an E2E case for user-facing changes; the fixture already builds the exact import-error scenario, and both E2E files now use it. | Duplicating the fixture body doubles a 50-line async setup and its cleanup. |
| A second document over `InfrahubRepositoryBranchStatus` beside #10658's. | The list needs the epic's status read now, without a branch context and with only the fields it reads. | Lifting #10658's files carried fields and variables nothing read, and coupled this PR to #10658's review. |
