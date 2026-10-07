# Implementation Plan: Repositories and Git state columns on the branches list

**Branch**: `ple-branches-table-git-ifc-3201` (on `ple-branch-details-repos-infp-671`, PR #10779) | **Date**: 2026-09-30, rework 2026-10-01, rework A 2026-10-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `dev/specs/ifc-3201-branches-table-git/spec.md`; phase 1 research `research-brief.md`; decided plan `plan-synthesis.md`; rework contracts `rework-contract.md` (one row per branch) and `rework-contract-a.md` (repository-anchored data, binding).

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Frontend-only. The branches list (`/branches`) gains two columns after "Proposed Changes": **Repositories** and **Git state**. The list keeps one row per branch (rework 2026-10-01, research R14). The Repositories cell shows the worst repository as a pill, then "+N more" linking to the branch details page; the Git state cell shows the worst state's pill with an `n/N` count and a per-label tooltip on the count. A branch with no repositories, or whose repository data is pending, denied or failed, shows an explicit text or a spinner in the Repositories cell and a blank Git state cell.

Approach (rework A, research R15; R2, R7, R11, R12 stand; R1, R3–R6, R8, R13 and the per-branch parts of R5, R9, R10, R14 are superseded):

- **Data**: the page owns the fetch. `useGetBranchRepositorySummaries(branches)` reads the repository list once with #10779's `useQuery(getBranchRepositoriesQueryOptions({ branchName, syncWithGit: true, limit: REPOSITORY_FETCH_LIMIT, offset: 0 }))`, then runs `useQueries` over the repositories with `getRepositoryBranchStatusQueryOptions({ id, branchName: <default branch>, limit: 500 })` (the epic's `InfrahubRepositoryBranchStatus`), `staleTime: 60_000` and a 10 s `refetchInterval` while a row is syncing. `combine` calls the pure rule `summarizeBranchRepositories`, which pivots the rows to one `BranchRepositorySummary` per branch name. 1 + R requests, independent of pagination.
- **Ordering**: `compareSyncStatusSeverity` (`error-import` > `unknown` > `syncing` > `in-sync`), then repository name; `repositories[0]` is the pill and the worst state. Operational status no longer takes part.
- **Rows**: `toBranchTableRows(branches, summaries)` builds `BranchTableRow` (`BranchListItem` + `repositorySummary`), the view-model the table renders. `getRowId: row.id`, selection, toolbar and delete modal unchanged.
- **Cells**: pure, no hooks. `BranchRepositoriesCell({ branch })` reuses `LinkPill`, `Tooltip` and the Proposed changes cell's "+N more" link; `BranchGitStateCell({ summary })` reuses `GitStatePill` (#10779). The tooltip string comes from the pure `formatRepositoryState` / `formatSyncStatusCounts` rule.
- **Layout**: unchanged from the first rework: `[fit-content(WIDE), fit-content(MAX), minmax(150px, 200px), REPOSITORIES_TRACK, GIT_STATE_TRACK, repeat(columnCount - 6, fit-content(MAX)), 2.5rem]`, `REPOSITORIES_TRACK = "minmax(12rem, 18rem)"`, `GIT_STATE_TRACK = "9rem"`.

The first implementation (2026-09-30) fanned each branch out to one row per repository (research R1, R4, R13, superseded). The second (rework 2026-10-01) fetched per branch from inside the cells (research R14, data path superseded by R15). Both are in git history.

## Technical Context

**Language/Version**: TypeScript (strict), React 19 with the React Compiler (no `useMemo`/`useCallback`/`React.memo`).

**Primary Dependencies**: TanStack Table v8 (8.21.3; unchanged row selection), TanStack Query (`useQueries` with `combine`; #10779's `getBranchRepositoriesQueryOptions` for the repository list), `@infrahub/ui` (`Checkbox`, `Spinner`, `Tooltip`, `LinkPill`), Tailwind v4 theme tokens (`text-foreground-muted` for the state texts), `lucide-react`. No new dependency.

**Storage**: N/A (reads only).

**Testing**: Vitest in browser mode (`vitest.config.ts`, Playwright provider). Pure rule tests in `.test.ts` (`summarize-branch-repositories`, `sync-status-severity`, `format-repository-summary`), a `renderHook` test for `useGetBranchRepositorySummaries` mocking the `getBranchRepositories` and `getRepositoryBranchStatus` use cases, component tests for pure cells with summaries given as data, and a table test mocking the two use cases. Fakes: #10779's `tests/fake/branch-repositories.ts` and `tests/fake/branch.ts`.

**Target Platform**: Desktop browsers; light and dark themes (tokens only, no literal colours except the schema's own dropdown colour).

**Project Type**: Web application, frontend slice (`frontend/app`). `frontend/packages/ui` is read-only.

**Performance Goals**: The branch cells render as fast as today (SC-004). One row per branch keeps the DOM at today's size plus two cells per row. Requests: 1 + R per page load (16 on the dev stack), none on scroll, none within 60 s of a refocus (SC-007). Structural sharing in `combine` keeps untouched branches' summaries by reference. No `useMemo`.

**Constraints**: Only data the backend returns today. No Commit column, Upstream, "behind by N", Last import or operational status (FR-016). No column filter, sort or hide (FR-015, FR-017). `count` of the status page marks a cut page (branches past the cut read an error, never a guess); `limit: 500` is far above real branch counts. Page size still counts branches (FR-010).

**Scale/Scope**: the lifted #10658 status read (model, API, use case, tests), a severity rule, a query-options factory and key, a branches-domain model and two rules, one hook, one row view-model, two rewritten pure cells and their column wiring, their tests, and the E2E files under `tests/e2e/branches/` (see Constitution Check IV).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design, after the rework, and after rework A (2026-10-01).*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ | No schema change. The Git state label, colour and description come from the `sync_status` dropdown the status query returns. `GitStatePill` falls back to a grey badge when the colour is missing. The repositories counted per branch are the backend's status rows (FR-003); `sync_with_git` only chooses the empty-state wording. |
| II. Branch-Safe by Default | ✅ | The repository list and every status request are sent on the default branch, taken from the branches provider by `is_default`, never by name and never from the branch selector. The status rows name their branch, and the pivot keys by that name. The repository pill uses `getBranchQsp(branch.name)`; "+N more" uses `getBranchDetailsUrl(branch.name)`. The feature only reads. |
| III. Type Safety & Explicit Contracts | ✅ | `BranchRepositorySummary` and `RepositoryStatusFetch` are discriminated unions; cells narrow on `status`. `BranchTableRow extends BranchListItem`, so the table's consumers keep receiving branches. No `any` or `!`. Contracts are in `contracts/`. |
| IV. Test Discipline | ✅ | Test details are listed after this table. |
| V. Query Performance & Efficiency | ✅ | 1 + R requests, independent of branch count and of pages loaded. The backend `repository_ids` follow-up collapses it to 2 without touching cells or rules. |
| VI. Security & Input Boundaries | ✅ | Reads only. Permission is enforced by the server: a `PERMISSION_DENIED` on a status request reads "No permission" on every row (FR-012). Text is rendered as text. |
| VII. Simplicity & Maintainability | ✅ | Details are listed after this table. |
| Quality gates | ✅ | biome ci, knip, betterer ci, vitest. Towncrier fragment `changelog/+ifc-3201-branches-table-git.added.md`. |

- **User-facing documentation**: the section in `docs/docs/git-integration/branch-synchronization.mdx` describing the two columns and the four state texts; rework A changes the ordering sentence and the "No repositories" and "No permission" sentences.
- **Knowledge capture**: `dev/knowledge/frontend/react.md` keeps the `useQueries` `combine` structural-sharing pitfall without a ticket id; `dev/guidelines/frontend/page-architecture.md` § State ownership states that table cells render a view-model and do not fetch.

**IV. Test Discipline, in detail:**

- **Rule tests**: `summarize-branch-repositories.test.ts` (denied wins; pending wins over error; first error message; grouping by branch name; worst-first with ties by name; counts; no rows → empty ok; read-only repository on an unsynced branch, read/write one not); `sync-status-severity.test.ts` (order, unknown values); `format-repository-summary.test.ts` (label · commit · read-only, each optional).
- **Hook test**: `get-branch-repository-summaries.query.test.ts`: one repository-list request on the default branch; one status request per repository with `limit: 500`; summaries keyed by branch; data-first on a failed background refetch; `PERMISSION_DENIED` → all denied; `refetchInterval` 10 000 only while syncing and `staleTime` 60 000, asserted on the options factory.
- **Component tests**: `get-branch-table-columns.test.tsx` with pure cells and summaries as data: headers; worst-repository pill with link and branch parameter (the default branch included); tooltip text; "+N more"; Git state pill colour, `n/N`, count tooltip and `sr-only` text; single repository without count; colourless status → grey badge; pending → one `role="status"`; denied, error (`sr-only` message), both empty texts in `text-foreground-muted`, no `-` or `—`; an unreachable in-sync repository never outranks an import error, and `unknown` outranks `in-sync`.
- **Table tests**: `branches-table.test.tsx` mocking the two use cases: branch cells render while summaries are pending; 1 + R requests; a second page issues no new status request; denied → "No permission" on every row, no toast; one status error → "Could not load repositories" on every row, no toast.
- **Branch details card and fetcher**: `branch-repositories-card.test.tsx` and `get-branch-repositories-from-api.test.ts` keep the no-toast and message cases.
- Deviation from IV's mock rule, house style: tests mock use cases (`vi.mock`), per `dev/guides/frontend/writing-component-tests.md`; no external HTTP is mocked because none is called.
- **E2E: one happy-path case, in this PR.** `tests/e2e/branches/test_branches_git_columns.py` (`pytestmark = pytest.mark.shard_branches_repo`), assertions unchanged: on the broken branch's row the repository pill names the repository and the Git state pill reads "Import Error"; a `sync_with_git=False` branch reads "Not synced with Git". The `broken_repository` factory fixture lives in `tests/e2e/branches/conftest.py` and logs teardown failures. Every command carries `-c tests/e2e/pytest.ini`.

**VII. Simplicity & Maintainability, in detail:**

- **Reuse first**: #10658's status read (lifted), #10779's `getBranchRepositoriesQueryOptions`, `GitStatePill`, `LinkPill`, `Tooltip`, `TableCell`, `TableColumnHeaderSimple`, `Spinner` and the Proposed changes cell's "+N more" pattern.
- **One owner for the data**: the hook fetches, the rule derives, the row view-model carries, the cells render. No derivation in `.tsx`.
- **Kept deliberately simple**: the grid template names two fixed tracks as constants rather than a per-column tracks map (deferred to IFC-3146/3147).

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3201-branches-table-git/
├── spec.md
├── research-brief.md      # Phase 1 research + owner decisions
├── plan-synthesis.md      # Decided plan (input, 2026-09-30, superseded in part)
├── rework-contract.md     # Rework 2026-10-01: one row per branch
├── rework-contract-a.md   # Rework A 2026-10-01: repository-anchored data (binding)
├── plan.md                # This file
├── research.md            # R1–R15 + risks
├── data-model.md
├── quickstart.md
├── pr-notes.md            # PR description notes
├── contracts/
│   ├── ui-cells.md
│   └── graphql.md
└── tasks.md
```

### Source Code (repository root)

All paths are under `frontend/app/`.

```text
src/shared/api/graphql/
└── error-handling.ts                             # CHANGED + hasOnlyThrownCatalogueCode (hasThrownCatalogueCode is already on the base)

src/entities/repository/
├── api/
│   ├── get-branch-repositories-from-api.ts       # CHANGED no-op processErrorMessage (#10779 file)
│   └── get-repository-branch-status-from-api.ts  # LIFTED #10658
├── domain/
│   ├── model/repository-branch-status.ts (+ test)        # LIFTED #10658
│   ├── rules/sync-status-severity.ts (+ test)            # NEW compareSyncStatusSeverity
│   └── use-cases/get-repository-branch-status.ts (+ test) # LIFTED #10658
└── ui/
    ├── branch-repositories/branch-repositories-states.tsx # CHANGED failed state shows the server message (#10779 file)
    └── queries/
        ├── repository.query-keys.ts              # CHANGED + branchStatus(params), #10658's name and shape
        └── get-repository-branch-status.query.ts # NEW getRepositoryBranchStatusQueryOptions (factory, no hook)

src/entities/branches/
├── domain/
│   ├── model/branch-repository-summary.ts        # NEW BranchRepositoryState, SyncStatusCount, BranchRepositorySummary
│   └── rules/
│       ├── summarize-branch-repositories.ts (+ test) # NEW RepositoryStatusFetch, summarizeBranchRepositories
│       └── format-repository-summary.ts (+ test)     # NEW tooltip/summary string builder
└── ui/
    ├── queries/get-branch-repository-summaries.query.ts (+ test) # NEW the page-side fetch
    └── branches-table/
        ├── branch-table-row.ts                   # NEW BranchTableRow, toBranchTableRows
        ├── branch-field-schemas.ts               # CHANGED + repositories, git_state
        ├── get-branch-table-columns.tsx (+ test) # CHANGED typed on BranchTableRow; 2 display columns
        ├── branches-data-table.tsx               # CHANGED typed on BranchTableRow; fixed tracks
        ├── branches-table.tsx (+ test)           # CHANGED data={toBranchTableRows(flatData, summaries)}
        └── cells/
            ├── branch-name-cell.tsx              # CHANGED checkbox aria-label "Select <name>"
            ├── branch-repositories-cell.tsx      # REWRITTEN pure
            └── branch-git-state-cell.tsx         # REWRITTEN pure
```

Not lifted: #10658's hook `get-repository-branch-status.query.ts` with its hook (it forces the current branch); this base gets a factory-only file at the same path.

Outside `frontend/app/`: `changelog/+ifc-3201-branches-table-git.added.md`; `docs/docs/git-integration/branch-synchronization.mdx`; `tests/e2e/branches/conftest.py` (promoted fixture), `tests/e2e/branches/test_branches_git_columns.py`, `tests/e2e/branches/test_branch_details_repositories.py` (changed premise); `tests/e2e/branches/test_branches.py` back to base.

**Structure Decision**: This follows the entity layer in `dev/knowledge/frontend/entities-structure.md`. `branches/domain/rules/summarize-branch-repositories.ts` imports its own model and the repository entity's severity rule; the hook in `branches/ui/hooks` imports `repository/ui/queries`; the cells import `repository/ui/branch-repositories` (`GitStatePill`) and their own `domain/rules`.

## Risks

| Risk | Mitigation |
|---|---|
| One status denial or failure blanks the whole column. | Spec consequence, accepted by the owner (spec Session 2026-10-01, architecture review). The branch cells always render; the message stays reachable on "Could not load repositories". |
| A non-permission GraphQL error toasts through the shared client (`error-handling.ts::handleGraphQLErrors`) unless the request opts out. | The status use case maps errors to `RepositoryBranchStatusError` (`code`, `message`); the rendered failure is "Could not load repositories" with that message. `branches-table.test.tsx` asserts no toast on a status error. |
| `limit: 500` (`REPOSITORY_BRANCH_STATUS_LIMIT`) truncates a list of more than 500 branches per repository. | Far above real counts; `count > rows.length` is detected and the branches the cut could hide read "Could not load repositories" with the reason. |
| The branches page reload button refreshes branch queries and repository status. | Its busy indicator covers that reload only; the 10 s syncing poll does not spin it. |
| The PR rebases whenever #10779 changes. | The base is a double stack (#10779 on the epic branch), so a squash-merge of #10779 requires `git rebase --onto` (`pr-notes.md`). |
| The lifted #10658 files drift before #10658 merges. | SHAs and `cmp` results in `pr-notes.md`; the `branchStatus` key is the one deliberate conflict. |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| ~~A shared file changes: `get-toggle-selected-row-handler.ts`~~ | Superseded 2026-10-01: one row per branch needs no handler change; the file is back to base. | — |
| ~~One repositories request per visible branch (N+1 at the HTTP layer).~~ | Superseded by rework A: 1 + R requests over `InfrahubRepositoryBranchStatus` (research R15). | — |
| Lifting #10658's status files (`repository-branch-status.ts`, `get-repository-branch-status-from-api.ts`, `get-repository-branch-status.ts`, their tests, `hasThrownCatalogueCode`) before #10658 merges. | The list needs the epic's status read now; byte-identical copies merge cleanly as add/add of equal content. | Writing a second status read duplicates the GraphQL document and its mapping. |
| Adding `branchStatus` to #10779's `repository.query-keys.ts` with #10658's name and key shape, plus a factory-only `get-repository-branch-status.query.ts`. | #10658's hook forces the current branch; the list needs the default branch. | Lifting the hook would send the current branch. The key addition is a deliberate small merge conflict in one file, visible when #10658 lands. |
| Touching #10779's `get-branch-repositories-from-api.ts::fetchConnection` to pass a no-op `processErrorMessage`. | The details card renders its own failed state; a toast for it is the wrong surface. | Catching the toast downstream is impossible (it fires inside the client). |
| Promoting #10779's class-local E2E fixture `broken_repository` to `tests/e2e/branches/conftest.py`. | The constitution requires an E2E case for user-facing changes; the fixture already builds the exact import-error scenario. | Duplicating the fixture body doubles a 50-line async setup and its cleanup. |
