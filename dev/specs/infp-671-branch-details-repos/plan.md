# Implementation Plan: Branch details — Git repositories and tasks

**Branch**: `ple-branch-details-repos-infp-671` (on `cross-branch-repo-status-infp-671`) | **Date**: 2026-09-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `dev/specs/infp-671-branch-details-repos/spec.md`; source design `design/05-handoff.md` (lift sheet, queries); prototype `ple-design-branch-details-repos:frontend/app/src/pages/_proto/branch-details/revs/rev-06/`.

## Summary

Frontend-only. The branch details page takes the object details page's shape (header row with copy, status and Refresh; tab row; panel body card) and its Details tab becomes a column of four blocks on non-default branches: today's attributes in a "Details" card, a new **Git repositories** card, today's five action buttons (Merge ungated), and a new **Tasks** card replacing the tasks accordion.

The repositories card loads every repository on the page's branch in one request, ranks failing ones first on the client (the rank can't be expressed as server ordering, research R1) and paginates at 10 with a fixed height. Under the table, one band per failing repository: import errors fetch their latest import task lazily (≤ 3 requests until "Show all") and show its last error-level log line; unreachable remotes show an amber band. The tasks card is server-paginated over the existing `GET_TASK_LIST` document. A shared `TablePagination` (IFC-3130's component, which isn't on this base) serves both tables; page numbers live in the URL. Everything uses theme tokens (they exist on this base).

The prototype's `rev-06` files are the visual reference; code is re-written into the entity layer, not copied from `_proto/` (lift sheet: "Copy the code; never cherry-pick").

## Technical Context

**Language/Version**: TypeScript (strict), React 19 with the React Compiler (no manual `useMemo`/`useCallback`/`React.memo`).

**Primary Dependencies**: Vite, TanStack Query, `gql.tada` + `graphqlClient`, `nuqs` (URL state), `react-router`, `@infrahub/ui` (`Card`, `CardHeader`, `Button`, `LinkButton`, `Tooltip`, `buttonVariants`, theme tokens), Tailwind v4, `lucide-react`. No new dependency.

**Storage**: N/A (reads only).

**Testing**: Vitest (unit + browser-mode component tests, `tests/components/render`, `vi.mock` on query hooks); pytest-playwright e2e in `tests/e2e/branches/`.

**Target Platform**: Desktop browsers; light and dark themes.

**Project Type**: Web application, frontend slice (`frontend/app`, `frontend/packages/ui` read-only).

**Performance Goals**: Constant request count per page view (1 branch + 1 repositories + ≤ 3 bands + 1 tasks page + 1 failed count), independent of repository and task counts. No layout shift between pages (fixed table height).

**Constraints**: Only data the backend returns today (no Upstream, "N behind", Last import). Merge not gated. Task manager page cap 200 (we use 10). `log_limit` counts across all runs in a request (one repository per band request). Repository fetch limit 500 with a visible notice past it.

**Scale/Scope**: Tens of repositories per branch (prototype worst case 40); tasks unbounded (server-paginated). ~20 new/changed frontend files, 1 e2e file changed/extended.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ | No schema change. Git state label/colour come from the schema's `sync_status` dropdown, not hard-coded. Generated `shared/api/` untouched except `gql.tada` cache regen if codegen needs it. |
| II. Branch-Safe by Default | ✅ | Every read carries the **page's** branch explicitly (context or `branch` argument), never the selector's current branch. Read-only feature: no merge behaviour to specify. |
| III. Type Safety & Explicit Contracts | ✅ | `gql.tada` typed documents; domain types in `domain/model`; discriminated unions for results (`ok`/`denied`, `found`/`not-found`); no `any`, no `!`, no `as` (the dropdown fields are narrowed with guards). Contracts in `contracts/`. |
| IV. Test Discipline | ✅ | Unit tests for every rule and pagination util; component tests per scenario fixture; e2e updated (accordion test id) and extended (band → task page). |
| V. Query Performance & Efficiency | ✅ with note | No N+1 over repositories: bands are lazy and capped at 3 until expanded. The single 500-row repository read is the deliberate trade-off in Complexity Tracking. |
| VI. Security & Input Boundaries | ✅ | Reads only; permission is enforced by the server and surfaced (`PERMISSION_DENIED` → no-access state). URL page params are parsed as integers and clamped. Error lines are rendered as text (no HTML). |
| VII. Simplicity & Maintainability | ✅ | `TablePagination` has two callers on day one. No readiness logic, no gate. Reuses `GET_TASK_LIST`, `getTaskCount`, `RefreshButton`, `HeaderContainer`, `BranchAttributes`, the action buttons, task state badges. |
| Quality gates | ✅ | biome ci, knip, betterer ci, vitest, e2e; Towncrier fragment `changelog/+infp-671-branch-details-repositories.added.md`; `dev/knowledge/frontend/shared-components.md` gains `TablePagination`. |

Post-design re-check: unchanged. No unjustified violation.

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-671-branch-details-repos/
├── design/              # Source PRD (design-jam output, read-only)
├── spec.md
├── plan.md              # This file
├── research.md          # R1–R13
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── graphql-queries.md
│   └── ui-components.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
frontend/app/src/
├── shared/
│   ├── components/table/table-pagination.tsx            # NEW TablePagination (IFC-3130 shape)
│   ├── utils/table-pagination.ts (+ .test.ts)           # NEW page math
│   └── config/qsp.ts                                    # + REPOSITORIES_PAGE, TASKS_PAGE
├── entities/repository/
│   ├── api/get-branch-repositories-from-api.ts          # NEW Q1
│   ├── api/get-repository-import-task-from-api.ts       # NEW Q2
│   ├── domain/model/repository.ts                       # + constants
│   ├── domain/model/branch-repository.ts                # NEW types
│   ├── domain/rules/rank-repositories.ts (+ test)       # NEW rank, unreachable, failing, band kind
│   ├── domain/rules/get-last-error-line.ts (+ test)     # NEW
│   ├── domain/use-cases/get-branch-repositories.ts (+ test)   # NEW mapping + denied
│   ├── domain/use-cases/get-repository-import-error.ts (+ test)
│   └── ui/
│       ├── queries/repository.query-keys.ts             # NEW
│       ├── queries/get-branch-repositories.query.ts     # NEW
│       ├── queries/get-repository-import-error.query.ts # NEW
│       └── branch-repositories/                         # NEW card + children (+ tests, fixtures)
├── entities/tasks/
│   ├── domain/model/branch-task.ts                      # NEW
│   ├── domain/model/workflow-labels.ts (+ test)         # NEW
│   ├── domain/rules/get-task-related-label.ts (+ test)  # NEW
│   ├── domain/use-cases/get-branch-tasks.ts (+ test)    # NEW over GET_TASK_LIST
│   ├── ui/queries/tasks.query-keys.ts                   # + branchList
│   ├── ui/queries/get-branch-tasks.query.ts             # NEW
│   └── ui/branch-tasks/                                 # NEW card, table, states (+ tests)
├── entities/branches/ui/
│   ├── branch-details.tsx                               # CHANGED column layout, accordion removed
│   ├── branch-details/branch-details-header.tsx (+ test)# NEW
│   └── branch-tabs.tsx                                  # CHANGED object tab row classes
├── entities/nodes/object/ui/object-details/refresh-button.tsx (+ test)  # CHANGED queryKeys
└── pages/branches/
    ├── details.tsx                                      # CHANGED header + panel body
    └── branch-details/details-tab.tsx                   # CHANGED owns repos_page/tasks_page

tests/e2e/branches/test_branch_details.py                # CHANGED accordion → Tasks card; NEW band link test
changelog/+infp-671-branch-details-repositories.added.md # NEW
dev/knowledge/frontend/shared-components.md              # + TablePagination row
```

**Structure Decision**: Entity layer per `dev/knowledge/frontend/entities-structure.md`: repository data and the card in `entities/repository` (so IFC-3200 adopts it), branch tasks in `entities/tasks`, page composition in `entities/branches/ui/branch-details.tsx` and `pages/branches/`. Cross-entity imports go through `ui/` and `domain/` only, never another entity's `api/`. `tasks` never imports `repository`: repository names reach the Tasks card as a plain `Map` prop.

## Design notes

### Page and URL ownership

`pages/branches/branch-details/details-tab.tsx` reads `repos_page` and `tasks_page` with `nuqs` (`parseAsInteger.withDefault(1)`), and passes `page`/`onPageChange` into `BranchDetails` → cards. Cards clamp with `clampPage` for display and don't write back an out-of-range page (the URL keeps the user's value; the view shows the nearest valid page). This follows `dev/guidelines/frontend/page-architecture.md` § "Pages own URL sync".

### Repositories card render tree

`BranchRepositoriesCard` → `Card` + `CardHeader` ("Git repositories", count badge) →
`loading` → 3 `Skeleton` rows (`role="status"`, `aria-busy`) ·
`denied` → lock + "You don't have access to this branch's repositories" ·
`failed` → "Repositories couldn't be loaded" ·
`ok && empty` → "Not synchronised with Git" (Sync off) or "No Git repositories" ·
`ok` → `BranchRepositoriesTable` (rank → slice → rows; min-height when > 1 page; `TablePagination`) → `RepositoryErrorBands` (first 3 or all; summary line + Show all/Collapse) → truncation notice when `isTruncated`.

Each `ImportErrorBand` calls `useGetRepositoryImportError({ branchName, repositoryId })` itself, so collapsed bands never fetch (lazy by construction; no effect needed).

### Tasks card render tree

`BranchTasksCard` → `Card` + `CardHeader` ("Tasks", count badge, "N failed", "Open in Tasks") → `loading` (skeleton) · `failed` ("Task results didn't load.") · `empty` ("No tasks have run on this branch yet. Imports, generators and validations appear here as they run.") · table (Title link, state badge from `getLogBadge`, `getWorkflowLabel`, `getTaskRelatedLabel`, `DateDisplay`) + `TablePagination`. `placeholderData: keepPreviousData` avoids a loading flash between pages.

### Header

`BranchDetailsHeader` in `pages/branches/details.tsx` replaces today's `<header>`; `BranchWorkingNotice` stays above it. The default branch keeps `BranchDefaultBadge` and no tabs.

### Links (critique X1)

The page shows `/branches/:branchName`'s data while the branch selector may be on another branch, and `constructPath` forwards the selector's `branch` QSP. Every link to branch-scoped data therefore overrides it with the page's branch (`constructPath(path, [{ name: QSP.BRANCH, value: branchName }])`; no parameter on the default branch). A small helper in `entities/branches/ui/routing/branch-urls.ts` (`withBranch(path, branchName)`) serves the repository name, "Open repository", "Open in Tasks" and the failed-tasks link. Task detail links are branch-independent.

### Merge (critique E1)

`BranchMergeButton` is rendered unchanged, with the same `branch` prop. Its existing rules (signed-in, not default, not merged, no pending request, no ongoing merge task) stay; nothing from the repositories or tasks cards is passed to it. A component test asserts that the rendered action row is the same five components with the same props as before.

### Freshness (critique P4, E6)

Tasks page 1 and the failed count poll every 10s; later pages don't. Repositories and bands poll every 10s only while a repository is syncing; otherwise Refresh and window refocus. See research R4.

### Copy

All strings from `design/03-decisions.md` and rev-06 are kept verbatim where they describe real data ("— import failed", "View task log →", "Infrahub can't fetch new commits, so the commit shown may be out of date.", "Open repository", "Show all"/"Collapse", "Open in Tasks", "This branch"). The prototype's "Ask an administrator for read access to repositories on all branches" becomes "Ask an administrator for permission to view repositories." (the page queries one branch).

## Risks

| Risk | Mitigation |
|---|---|
| Import task not findable for some flows (research R2) | Band never depends on the task; `not-found` fallback; verification task; backend follow-up ticket. |
| IFC-3130 lands `table-pagination.tsx` at the same path | Same props; resolve in favour of IFC-3130 on merge. |
| IFC-3200 builds its own card in parallel | Card lives in `entities/repository/ui/branch-repositories/` with a branch-agnostic props contract; flag in the PR for IFC-3200. |
| Links opening the selector's branch instead of the page's | Link rule (Design notes "Links"); component tests assert `branch=<page branch>` on each outgoing link. |
| E2E can't deterministically produce an import error | Seed through the path the R2 verification proves; otherwise assert on the fallback band and note it. |
| Merge ungated is unsigned by INFP-670 | Spec clarification; PR description asks for sign-off before merge. |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Client-side ordering and pagination of repositories (page-architecture: "Sort order, pagination … belong to the server") | FR-013 ranks import errors, then unreachable remotes, first; the server orders by attribute value lexicographically only and can't express that rank (research R1). | Server `order: { by: [sync_status__value] }` drops the unreachable rank; two filtered queries need page stitching and a second count for the same result. Bounded by `REPOSITORY_FETCH_LIMIT` with a visible notice; follow-up is a backend ordering/field. |
| One band request per failing repository | `log_limit` is shared across all runs in one request (research R2); batching lets one long log starve the others. | Batched request: wrong or missing error lines. Capped at 3 until "Show all", so not an N+1 over the table. |
