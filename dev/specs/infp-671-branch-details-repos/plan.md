# Implementation Plan: Branch details — Git repositories and tasks

**Branch**: `ple-branch-details-repos-infp-671` (on `cross-branch-repo-status-infp-671`) | **Date**: 2026-09-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `dev/specs/infp-671-branch-details-repos/spec.md`; source design `design/05-handoff.md` (lift sheet, queries); prototype `ple-design-branch-details-repos:frontend/app/src/pages/_proto/branch-details/revs/rev-06/`.

## Summary

Frontend-only. The branch details page takes the object details page's shape (header row with copy, status and Refresh; tab row; panel body card) and its Details tab becomes a column of four blocks on non-default branches: today's attributes in a "Details" card, a new **Git repositories** card, today's five action buttons (Merge ungated), and a new **Tasks** card replacing the tasks accordion.

The repositories card asks the server for one page of the branch's repositories (10, ordered by name) with a fixed height, and a second, server-filtered query for the failing ones (import errors and unreachable remotes) plus a count of syncing ones. Under the table, one band per failing repository, whatever page the table shows: import errors look up their newest failed import task lazily (≤ 3 until "Show all"), fetch its log once, and show its last error-level line; unreachable remotes show an amber band. The tasks card is server-paginated over the existing `GET_TASK_LIST` document. IFC-3130's `TablePagination` and `useTablePagination` serve both tables; each card keeps its page in the URL. Everything uses theme tokens (they exist on this base).

_(2026-10-02, restructure: this summary first described a 500-row fetch ranked and paginated on the client. The architecture review moved sort, pagination and failure filtering to the server; see research.md § "Restructure (2026-10-02)" and tasks.md § "Restructure".)_

The prototype's `rev-06` files are the visual reference; code is re-written into the entity layer, not copied from `_proto/` (lift sheet: "Copy the code; never cherry-pick").

## Technical Context

**Language/Version**: TypeScript (strict), React 19 with the React Compiler (no manual `useMemo`/`useCallback`/`React.memo`).

**Primary Dependencies**: Vite, TanStack Query, `gql.tada` + `graphqlClient`, `nuqs` (URL state), `react-router`, `@infrahub/ui` (`Card`, `CardHeader`, `Button`, `LinkButton`, `Tooltip`, `buttonVariants`, theme tokens), Tailwind v4, `lucide-react`. No new dependency.

**Storage**: N/A (reads only).

**Testing**: Vitest (unit + browser-mode component tests, `tests/components/render`, `vi.mock` on query hooks); pytest-playwright e2e in `tests/e2e/branches/`.

**Target Platform**: Desktop browsers; light and dark themes.

**Project Type**: Web application, frontend slice (`frontend/app`, `frontend/packages/ui` read-only).

**Performance Goals**: Constant request count per page view (1 branch + 1 repositories page + 1 repository health + ≤ 3 failed-task lookups + ≤ 3 logs, each once per task + 1 tasks page + 1 failed count + ≤ 1 repository names), independent of repository and task counts. No layout shift between pages (fixed table height).

**Constraints**: Only data the backend returns today (no Upstream, "N behind", Last import). Merge not gated. Task manager page cap 200 (we use 10). `log_limit` counts across all runs in a request (one task per log request). Sort, pagination and failure filtering are the server's (page-architecture, "backend is authoritative").

**Scale/Scope**: Tens of repositories per branch (prototype worst case 40); tasks unbounded (server-paginated). ~20 new/changed frontend files, 2 e2e files (1 changed, 1 new).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ | No schema change. Git state label/colour come from the schema's `sync_status` dropdown, not hard-coded. Generated `shared/api/` untouched except `gql.tada` cache regen if codegen needs it. |
| II. Branch-Safe by Default | ✅ | Every read carries the **page's** branch explicitly (context or `branch` argument), never the selector's current branch. Read-only feature: no merge behaviour to specify. |
| III. Type Safety & Explicit Contracts | ✅ | `gql.tada` typed documents; domain types in `domain/model`; a typed `BranchRepositoriesError` (`PERMISSION_DENIED` / `UNKNOWN`) and a `found`/`not-found` union; no `any`, no `!`, no `as` (the dropdown fields are narrowed with guards). Contracts in `contracts/`. |
| IV. Test Discipline | ✅ | Unit tests for every rule and pagination util; component tests per scenario fixture; e2e updated (accordion test id) and extended (band → task page). |
| V. Query Performance & Efficiency | ✅ | No N+1 over repositories: bands are lazy and capped at 3 until expanded, and each log is fetched once per task. The table reads one server page; failures and syncing come from server filters. _(2026-10-02: was "with note" for the 500-row read, now gone.)_ |
| VI. Security & Input Boundaries | ✅ | Reads only; permission is enforced by the server and surfaced (`PERMISSION_DENIED` → no-access state). URL page params are parsed as integers and clamped. Error lines are rendered as text (no HTML). |
| VII. Simplicity & Maintainability | ✅ | `TablePagination` and `useTablePagination` are IFC-3130's, two callers here. No readiness logic, no gate. Reuses `GET_TASK_LIST`, `getTaskCount`, `RefreshButton`, `HeaderContainer`, `BranchAttributes`, the action buttons, task state badges. |
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

_(2026-10-02: updated for the restructure.)_

```text
frontend/app/src/
├── shared/
│   ├── components/table/table-pagination.tsx (+ test)   # IFC-3130 verbatim + aria-label + focus ring
│   ├── components/table/style.tsx                      # + CELL_HEIGHT_PX (IFC-3130 verbatim)
│   ├── utils/table-pagination.ts (+ test)               # IFC-3130 verbatim: PAGE_SIZE, getOffset, …
│   ├── hooks/use-table-pagination.ts (+ test)           # IFC-3130 verbatim: ${urlKey}_page, duplicate-key guard
│   ├── hooks/use-count-clamped-query.ts (+ test)        # NEW clamp a page against the server's count
│   └── api/graphql/error-handling.ts                    # + hasThrownCatalogueCode (IFC-3130 verbatim)
├── entities/repository/
│   ├── api/get-branch-repositories-from-api.ts (+ test) # Q1 one page, ordered by name
│   ├── api/get-branch-repository-health-from-api.ts     # Q1b failing + syncing, server-filtered
│   ├── api/branch-repository.mappers.ts (+ test)        # toBranchRepository(ies)
│   ├── api/get-repository-import-task-from-api.ts       # Q2 newest failed import, Q2b its log
│   ├── api/get-repository-names-from-api.ts             # Q5 names by ids (Tasks card)
│   ├── domain/model/repository.ts                       # vocabulary
│   ├── domain/model/branch-repository.ts                # BranchRepository, Page, Health, error, import error
│   ├── domain/rules/get-repository-list-kind.ts         # Sync with Git → list kind
│   ├── domain/rules/repository-failures.ts (+ test)     # hasImportError, unreachable, failing, band kind
│   ├── domain/rules/is-any-repository-syncing.ts        # the polling decision
│   ├── domain/rules/get-last-error-line.ts (+ test)     # Prefect wrapper stopgap
│   ├── domain/use-cases/get-branch-repositories.ts (+ test)       # page + denied; also tests health
│   ├── domain/use-cases/get-branch-repository-health.ts
│   ├── domain/use-cases/get-repository-import-error.ts (+ test)   # failed task id; its error line
│   ├── domain/use-cases/get-repository-names.ts
│   └── ui/
│       ├── queries/repository.query-keys.ts             # ["repository"] root, superset of IFC-3199's
│       ├── queries/get-branch-repositories.query.ts (+ test)
│       ├── queries/get-branch-repository-health.query.ts
│       ├── queries/get-repository-import-error.query.ts (+ test)
│       ├── queries/get-repository-names.query.ts
│       └── branch-repositories/                         # card + children (+ tests)
├── entities/tasks/
│   ├── domain/model/task-list-item.ts
│   ├── domain/model/workflow-labels.ts                  # label maps (vocabulary)
│   ├── domain/rules/get-workflow-label.ts (+ test)      # moved from model/
│   ├── domain/rules/get-task-related-label.ts (+ test)
│   ├── domain/rules/get-related-node-ids.ts
│   ├── domain/use-cases/get-branch-tasks.ts (+ test)    # over GET_TASK_LIST
│   ├── ui/queries/tasks.query-keys.ts                   # + branchList
│   ├── ui/queries/get-branch-tasks.query.ts (+ test)
│   ├── ui/tasks-table/tasks-table.tsx (+ test)          # plain five-column table
│   └── ui/branch-tasks/                                 # card, states (+ tests)
├── entities/branches/ui/
│   ├── branch-details.tsx (+ test)                      # column layout; fetches nothing for the cards
│   ├── branch-details/branch-details-header.tsx (+ test)
│   ├── routing/branch-urls.ts (+ test)                  # getBranchQsp
│   └── branch-tabs.tsx
├── entities/nodes/object/ui/object-details/refresh-button.tsx (+ test)  # single queryKeys, scoped last update
└── pages/branches/
    ├── details.tsx                                      # header + panel body
    └── branch-details/details-tab.tsx                   # unchanged from the base

tests/e2e/branches/test_branch_details.py                # accordion → Tasks card
tests/e2e/branches/test_branch_details_repositories.py   # band → task page
changelog/+infp-671-branch-details-repositories.added.md
dev/knowledge/frontend/shared-components.md              # + TablePagination row
```

**Structure Decision**: Entity layer per `dev/knowledge/frontend/entities-structure.md`: repository data and the card in `entities/repository` (so IFC-3200 adopts it), branch tasks in `entities/tasks`, page composition in `entities/branches/ui/branch-details.tsx` and `pages/branches/`. Cross-entity imports go through `ui/` and `domain/` only, never another entity's `api/`. The Tasks card reads repository names through `repository/ui/queries/get-repository-names.query.ts` (a `ui` → `ui` import the layering table allows), so `BranchDetails` no longer fetches the repository list a second time for it. _(2026-10-02: replaces "`tasks` never imports `repository`: names reach the Tasks card as a `Map` prop", which cost a second read of every repository.)_

## Design notes

### Page and URL ownership

Each card owns its page through IFC-3130's `useTablePagination({ urlKey })`: `repositories_page` and `tasks_page`. The data hook clamps it: `useCountClampedQuery` asks for the requested page and, once the server's count says it is past the end, for the last real page; the URL keeps the out-of-range number until the next page change. No effect writes the URL back. _(2026-10-02: replaces the Details tab page owning `repos_page`/`tasks_page` and `usePageInRange` writing the clamped page back from an effect. This departs from page-architecture § "Pages own URL sync" the same way IFC-3130's card does: a table that pages on its own owns its own key.)_

### Repositories card render tree

`BranchRepositoriesCard` → `Card` + `CardHeader` ("Git repositories", count badge from the server's `count`) →
`failed` → "Repositories couldn't be loaded" ·
`denied` (`BranchRepositoriesError` `PERMISSION_DENIED`) → lock + "You don't have access to this branch's repositories" ·
`loading` → 3 `Skeleton` rows (`role="status"`, `aria-busy`) ·
`count === 0` → "Not synchronised with Git" (Sync off) or "No Git repositories" ·
otherwise → `BranchRepositoriesTable` (one server page in name order; min-height when `count > PAGE_SIZE`) + `TablePagination` → `RepositoryErrorBands` from the health query (first 3 or all; summary line + Show all/Collapse).

Each `ImportErrorBand` calls `useGetRepositoryImportError` itself, so collapsed bands never fetch (lazy by construction; no effect needed). The hook chains the failed-task lookup (polled while syncing) and the log fetch (keyed on the task id, fetched once).

### Tasks card render tree

`BranchTasksCard` → `Card` + `CardHeader` ("Tasks", count badge, "N failed", "Open in Tasks") → `loading` (skeleton) · `failed` ("Task results didn't load.") · `empty` ("No tasks have run on this branch yet. Imports, generators and validations appear here as they run.") · `TasksTable` (Title link, state badge from `getLogBadge`, `getWorkflowLabel`, `getTaskRelatedLabel` over the page's repository names, `DateDisplay`) + `TablePagination`. The previous page stays on screen while the next one loads (placeholder data within the branch).

### Header

`BranchDetailsHeader` in `pages/branches/details.tsx` replaces today's `<header>`; `BranchWorkingNotice` stays above it. The default branch keeps `BranchDefaultBadge` and no tabs.

### Links (critique X1)

The page shows `/branches/:branchName`'s data while the branch selector may be on another branch, and `constructPath` forwards the selector's `branch` QSP. Every link to branch-scoped data therefore overrides it with the page's branch through one helper, `getBranchQsp(branchName)` in `entities/branches/ui/routing/branch-urls.ts`. It serves the repository name, "Open repository", "Open in Tasks" and the failed-tasks link. Task detail links are branch-independent. _(2026-10-02: the cards only render on non-default branches, so the default-branch case and the `isDefaultBranch` prop drilled for it are gone.)_

### Merge (critique E1)

`BranchMergeButton` is rendered unchanged, with the same `branch` prop. Its existing rules (signed-in, not default, not merged, no pending request, no ongoing merge task) stay; nothing from the repositories or tasks cards is passed to it. A component test asserts that the rendered action row is the same five components with the same props as before.

### Freshness (critique P4, E6)

Tasks page 1 and the failed count poll every 10s; later pages don't. The repositories page, the health query and the failed-task lookups poll every 10s only while the server counts a syncing repository (`isAnyRepositorySyncing`, computed once in the card from the health query); a task's log is never polled. Otherwise Refresh and window refocus. See research R4.

### Copy

All strings from `design/03-decisions.md` and rev-06 are kept verbatim where they describe real data ("— import failed", "View task log →", "Infrahub can't fetch new commits, so the commit shown may be out of date.", "Open repository", "Show all"/"Collapse", "Open in Tasks", "This branch"). The prototype's "Ask an administrator for read access to repositories on all branches" becomes "Ask an administrator for permission to view repositories." (the page queries one branch).

## Risks

| Risk | Mitigation |
|---|---|
| Import task not findable for some flows (research R2) | Band never depends on the task; `not-found` fallback; verification task; backend follow-up ticket. |
| IFC-3130 lands `table-pagination.tsx` at the same path | The shared files are IFC-3130's, verbatim, except `TablePagination`'s `aria-label` prop and focus ring, which must also land in IFC-3130 (pr-notes.md). |
| IFC-3200 plans files at the same paths (`get-branch-repositories-from-api.ts`, `branch-repository.ts`, `get-branch-repositories.ts`, `get-branch-repositories.query.ts`) and a `clampToCount` in `use-table-pagination.ts` | Recorded for the owner (tasks.md § Restructure, "Open decisions"). |
| IFC-3200 builds its own card in parallel | Card lives in `entities/repository/ui/branch-repositories/` with a branch-agnostic props contract; flag in the PR for IFC-3200. |
| Links opening the selector's branch instead of the page's | Link rule (Design notes "Links"); component tests assert `branch=<page branch>` on each outgoing link. |
| E2E can't deterministically produce an import error | Seed through the path the R2 verification proves; otherwise assert on the fallback band and note it. |
| Merge ungated is unsigned by INFP-670 | Spec clarification; PR description asks for sign-off before merge. |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| One failed-task lookup per rendered import-error band | `log_limit` is shared across all runs in one request (research R2); batching lets one long log starve the others. | Batched request: wrong or missing error lines. Capped at 3 until "Show all", and each log is fetched once per task. |

_(2026-10-02: the "client-side ordering and pagination of repositories" row is gone. The review accepted dropping the failing-first rank in the table, since the bands already put failures in front of the reader; the table is now a server page ordered by name.)_
