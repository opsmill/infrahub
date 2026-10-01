# Implementation Plan: Repository, Git state and Commit columns on the branches table

**Branch**: `ple-branches-table-git-ifc-3201` (on `ple-branch-details-repos-infp-671`, PR #10779) | **Date**: 2026-09-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `dev/specs/ifc-3201-branches-table-git/spec.md`; phase 1 research `research-brief.md`; decided plan `plan-synthesis.md`.

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Frontend-only. The branches list (`/branches`) gains two columns after "Proposed Changes": **Repositories** and **Git state**. The list keeps one row per branch (rework 2026-10-01, `rework-contract.md`, research R14). The Repositories cell shows the first repository in the branch details order as a pill, then "+N more" linking to the branch details page; the Git state cell shows the worst state's pill with an `n/N` count and a per-label tooltip. A branch with no repositories, or whose repository data is pending, denied or failed, shows an explicit text or a spinner in the Repositories cell and a blank Git state cell.

Approach (research R2, R5, R7, R9–R12, R14; R1, R3, R4, R8 and R13 are superseded):

- **Data**: each of the two cells calls #10779's `useGetBranchRepositories({ branchName, syncWithGit })`. Both cells of a row share one query by key, and the branch details card shares the same cache and the same 10 s "while syncing" poll. One request per branch. No table-level `useQueries`, no row model, no fan-out rule. No new GraphQL document, no backend change.
- **Ordering**: `rankRepositories` (failed imports first, then unreachable, then by name); `ranked[0]` is the repository shown and the worst state.
- **Selection**: unchanged from the base: `BranchListItem` rows, `getRowId: row.id`, the ordinary per-row checkbox and the unchanged shared `getToggleSelectedRowHandler`. The checkbox gains `aria-label="Select <branch>"`.
- **Cells**: `BranchRepositoriesCell` reuses `LinkPill`, `Tooltip` and the Proposed changes cell's "+N more" link; `BranchGitStateCell` reuses `GitStatePill` (#10779). No `CommitHash`.
- **Layout**: the two new columns get fixed-width tracks, so no column shifts sideways as data arrives (SC-004). `branches-data-table.tsx::defaultGridTemplateColumns` becomes `[fit-content(WIDE), fit-content(MAX), minmax(150px, 200px), REPOSITORIES_TRACK, GIT_STATE_TRACK, repeat(columnCount - 6, fit-content(MAX)), 2.5rem]`, with `REPOSITORIES_TRACK = "minmax(12rem, 18rem)"` and `GIT_STATE_TRACK = "9rem"`.

The first implementation (2026-09-30) fanned each branch out to one row per repository with anchor-row selection; it is kept in git history and in research R1, R4, R13 (superseded).

## Technical Context

**Language/Version**: TypeScript (strict), React 19 with the React Compiler (no `useMemo`/`useCallback`/`React.memo`; existing `React.useMemo` calls in touched files are removed).

**Primary Dependencies**: TanStack Table v8 (8.21.3; unchanged row selection), TanStack Query (#10779's `useGetBranchRepositories`), `@infrahub/ui` (`Checkbox`, `Spinner`, `Tooltip`, `LinkPill`), Tailwind v4 theme tokens (`text-foreground-muted` for the state texts), `lucide-react`. No new dependency.

**Storage**: N/A (reads only).

**Testing**: Vitest in browser mode (`vitest.config.ts`, Playwright provider). Pure rule tests in `.test.ts`, component tests in `.test.tsx` rendered with `tests/components/render`, and `vi.mock` on query hooks and use-cases, as the frontend usually does. Fakes: #10779's `tests/fake/branch-repositories.ts` and `tests/fake/branch.ts` reused; no new fake file.

**Target Platform**: Desktop browsers; light and dark themes (tokens only, no literal colours except the schema's own dropdown colour).

**Project Type**: Web application, frontend slice (`frontend/app`). `frontend/packages/ui` is read-only.

**Performance Goals**: The branch cells render as fast as today (SC-004). One row per branch keeps the DOM at today's size plus two cells per row (24 branches × 16 repositories rendered 279 rows and ~15 000 DOM nodes under the fan-out, research R14). Repository requests are one per loaded branch (≈40 per page of `BRANCHES_PER_PAGE = 40`), independent of the repository count; the two cells of a row share one query by key (SC-007). No `useMemo`.

**Constraints**: Only data the backend returns today. There is no Commit column, Upstream, "behind by N", Last import or operational status (FR-016). No column filter, sort or hide (FR-015, FR-017). `isTruncated` is ignored (spec Assumptions). Page size still counts branches (FR-010).

**Scale/Scope**: after the rework, two new cells and their column wiring under `frontend/app/src/entities/branches/ui/branches-table/`, two component test files, the #10779 touches listed under Project Structure, plus one new E2E test and one fixture promotion under `tests/e2e/branches/` (see Constitution Check IV).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design, and again after the rework (2026-10-01).*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ | No schema change. The Git state label, colour and description come from the `sync_status` dropdown the backend returns (`BranchRepositorySyncStatus`). `GitStatePill` falls back to a grey badge when the colour is missing and hard-codes no state. The repositories counted per branch are what the backend returns; `sync_with_git` only chooses the empty-state wording (FR-003). |
| II. Branch-Safe by Default | ✅ | Every repository request carries **the row's** branch: `useGetBranchRepositories({ branchName: branch.name, … })`, keyed by `branchName`, sent as the GraphQL branch context. Nothing reads the branch selector's current branch. The repository pill uses `getBranchQspOverride(branch.name, is_default)`, so it opens the repository on the row's branch and adds no parameter on the default branch; "+N more" uses `getBranchDetailsUrl(branch.name)`. The feature only reads. |
| III. Type Safety & Explicit Contracts | ✅ | Cells take `{ branch: BranchListItem }` and narrow on the query state and on #10779's `BranchRepositoriesResult` union (`ok` / `denied`). No `any` or `!`. New display columns use `columnHelper.display`, so they need no `as`. The `BRANCH_FIELD_SCHEMAS` entries `repositories` and `git_state` follow the file's existing header-only `as AttributeSchema` shape. Contracts are in `contracts/`. |
| IV. Test Discipline | ✅ | Test details are listed after this table. |
| V. Query Performance & Efficiency | ⚠️ deviation, justified | No backend query changes. One HTTP request per loaded branch (≈40 per page): an N+1 at the HTTP layer, recorded in Complexity Tracking. Measured on a dev stack: 24 requests in 0.36 s total (research R14), so fetching is not the bottleneck. A single request is not available today: aliasing one `InfrahubRepositoryBranchStatus` field per repository into one document returns HTTP 500, and `Branch` has no repositories field (R14). |
| VI. Security & Input Boundaries | ✅ | Reads only. Permission is enforced by the server and surfaced per branch: `PERMISSION_DENIED` → "No permission" (FR-012). Text is rendered as text. |
| VII. Simplicity & Maintainability | ✅ | Details are listed after this table. |
| Quality gates | ✅ | biome ci, knip, betterer ci, vitest. Towncrier fragment `changelog/+ifc-3201-branches-table-git.added.md`. No `shared-components.md` entry: `CommitHash` is no longer lifted and the anchor-row pattern no longer exists. |

- **User-facing documentation**: one section in `docs/docs/git-integration/branch-synchronization.mdx` describing the Repositories column (first repository, failed first, "+N more" opens the branch), the Git state column (worst state with a count) and the four state texts. Owned by the docs phase, in the same PR.
- **Knowledge capture**: the 2026-09-30 anchor-row entry in `dev/knowledge/frontend/shared-components.md` is removed; `dev/knowledge/frontend/react.md` keeps the `useQueries` `combine` structural-sharing note without an in-repo example.

**IV. Test Discipline, in detail:**

- **Component tests**: `get-branch-table-columns.test.tsx` covers:
  - headers: Repositories and Git state after Proposed Changes, no filter or sort control;
  - a branch with 3 repositories: the pill shows the ranked-first (failing) repository, links with `branch=<name>` (default branch: no parameter), its tooltip holds the label and the 7-character commit; "+2 more" links to the branch details URL; the Git state pill uses the schema colour, shows `1/3` and a per-label tooltip;
  - a single repository: no count; a colourless status: grey badge; `commit: null`: tooltip without commit;
  - pending: one `role="status"` (in Repositories), blank Git state;
  - denied, error (with the `sr-only` message) and empty (both texts): texts in `text-foreground-muted`, Git state blank, no `-` or `—`.
- **Table tests**: `branches-table.test.tsx` covers branch cells rendering while repositories are pending; one request per branch (`getBranchRepositories` called once per branch with the right `branchName` and `syncWithGit`); a refocus within `staleTime` issuing no extra request; a GraphQL error on one branch reading "Could not load repositories" while the others stay intact, with no toast; `PERMISSION_DENIED` reading "No permission".
- **Branch details card and fetcher**: `branch-repositories-card.test.tsx` and `get-branch-repositories-from-api.test.ts` keep the no-toast and message cases from the review fix pass.
- Deviation from IV's mock rule, house style: component tests mock the `ui/queries/*.query` hook and use-case tests mock `api/*-from-api`, per `dev/guides/frontend/writing-component-tests.md`; no external HTTP is mocked because none is called.
- **E2E: one happy-path case, in this PR.** `tests/e2e/branches/test_branches_git_columns.py` (`pytestmark = pytest.mark.shard_branches_repo`) asserts, on the broken branch's row: the repository pill names the repository and links to its page, and the Git state pill reads "Import Error"; and a `sync_with_git=False` branch reads "Not synced with Git".
  - The `broken_repository` fixture stays promoted to `tests/e2e/branches/conftest.py` as a function-scoped factory taking `sync_with_git`, and `test_branch_details_repositories.py` keeps its `sync_with_git=True` premise.
  - `tests/e2e/branches/test_branches.py` goes back to base: with one row per branch the 2026-09-30 locator scoping is no longer needed.
  - The live-stack premise check (research "E2E premise verification") still applies.

**VII. Simplicity & Maintainability, in detail:**

- **Reuse first**: `useGetBranchRepositories`, `rankRepositories`, `GitStatePill`, `LinkPill`, `Tooltip`, `TableCell`, `TableColumnHeaderSimple`, `Spinner` and the Proposed changes cell's "+N more" pattern are all reused.
- **Removed by the rework**: the row model, the fan-out rule, the table-level hook, the anchor-row selection, the shared handler change, the `packages/ui` `LinkButton` change and the `CommitHash` lift.
- **Kept deliberately simple**: the grid template names two fixed tracks as constants rather than a per-column tracks map (deferred to IFC-3146/3147).

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3201-branches-table-git/
├── spec.md
├── research-brief.md    # Phase 1 research + owner decisions
├── plan-synthesis.md    # Decided plan (input, 2026-09-30, superseded in part by rework-contract.md)
├── rework-contract.md   # Rework 2026-10-01: one row per branch (binding)
├── plan.md              # This file
├── research.md          # R1–R14 + risks
├── data-model.md
├── quickstart.md
├── pr-notes.md          # PR description notes
├── contracts/
│   ├── ui-cells.md
│   └── graphql.md
└── tasks.md
```

### Source Code (repository root)

All paths are under `frontend/app/`. The only `api/` change is `entities/repository/api/get-branch-repositories-from-api.ts` (no-op `processErrorMessage`).

```text
src/entities/branches/ui/branches-table/
├── branch-field-schemas.ts                       # CHANGED + repositories, git_state
├── get-branch-table-columns.tsx                  # CHANGED 2 display columns after proposed_changes
├── get-branch-table-columns.test.tsx             # NEW cells per state, headers, pill colour, count, tooltips, texts
├── branches-data-table.tsx                       # CHANGED fixed tracks REPOSITORIES_TRACK, GIT_STATE_TRACK; useMemo removed
├── branches-table.tsx                            # CHANGED useMemo removed
├── branches-table.test.tsx                       # NEW one request per branch, branch cells first, errors, no toast
└── cells/
    ├── branch-name-cell.tsx                      # CHANGED checkbox aria-label "Select <name>"
    ├── branch-repositories-cell.tsx              # NEW
    └── branch-git-state-cell.tsx                 # NEW

src/entities/repository/api/
└── get-branch-repositories-from-api.ts           # CHANGED fetchConnection passes a no-op processErrorMessage (#10779 file)

src/entities/repository/ui/branch-repositories/
├── branch-repositories-states.tsx                # CHANGED failed state shows the server message (#10779 file)
└── repository-name-link.tsx, repository-row.tsx  # RepositoryNameLink extraction: reverted
```

Back to base or deleted by the rework: `entities/branches/domain/model/branch-table-row.ts`, `entities/branches/domain/rules/to-branch-table-rows.ts` (+ test), `entities/branches/ui/hooks/use-branch-table-rows.ts` (+ test), `cells/branch-repository-cell.tsx`, `cells/branch-commit-cell.tsx`, `branches-data-table.test.tsx`, `tests/fake/branch-table-rows.ts`, `entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler.ts` (+ its test), `cells/branch-proposed-changes-cell.tsx`, `cells/branch-actions-cell.tsx`, `shared/components/display/commit-hash.tsx` (+ test), and `frontend/packages/ui/src/components/button/button.tsx`.

Outside `frontend/app/`: `changelog/+ifc-3201-branches-table-git.added.md` (NEW); `docs/docs/git-integration/branch-synchronization.mdx` (CHANGED, docs phase); `tests/e2e/branches/conftest.py` (NEW, promoted fixture), `tests/e2e/branches/test_branches_git_columns.py` (NEW), `tests/e2e/branches/test_branch_details_repositories.py` (CHANGED); `tests/e2e/branches/test_branches.py` back to base.

**Structure Decision**: This follows the entity layer in `dev/knowledge/frontend/entities-structure.md`. The two cells sit in `branches/ui/branches-table/cells/` and import `repository/ui/queries` (the query hook), `repository/ui/branch-repositories` (`GitStatePill`) and `repository/domain/rules` (`rankRepositories`), which `ui` → another entity's `ui`/`domain` allows.

## Risks

| Risk | Mitigation |
|---|---|
| A non-permission GraphQL error toasts once. The shared client's `error-handling.ts::handleGraphQLErrors` calls `notifyUser` unless the request context sets `processErrorMessage`. | `fetchConnection` passes a no-op `processErrorMessage`, so a GraphQL-level failure surfaces only as the cell's "Could not load repositories" (with its message as a tooltip and `sr-only` text) and, on the branch details card, as its failed state with the server message (research R10). |
| Unreachable repositories rank above healthy ones although their status isn't shown (FR-016), so the "worst" repository can be an unreachable one in sync. | Spec edge case. The count and the per-label tooltip still give every state present. |
| ≈40 requests per page (N+1 over HTTP). | Accepted (Complexity Tracking); measured at 0.36 s for 24 branches (R14). The cache is shared with the details card. Single-request follow-ups are recorded in R14. |
| `isTruncated` is ignored, so a list over 500 repositories is silently partial. | Spec Assumptions. `REPOSITORY_FETCH_LIMIT` is far above real counts. |
| The branches page reload button refreshes branch queries only. | The 10 s poll covers syncing repositories. Otherwise refocus and remount refresh. |
| The PR rebases whenever #10779 changes (touched files). | The base is a double stack (#10779 on the epic branch), so a squash-merge of #10779 requires `git rebase --onto` (`pr-notes.md`). |
| The branch details E2E's premise is unverified on a live stack (`sync_with_git=True` derived from `getRepositoryListKind`). | Research "E2E premise verification"; run both E2E files against a stack before merge. |
| The #10779 touches (card toast and message, fixture, `RepositoryNameLink` if kept) are really #10779 behaviour changes. | The owner can land them on #10779 first; this PR then rebases. |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| ~~A shared file changes: `get-toggle-selected-row-handler.ts`~~ | Superseded 2026-10-01: one row per branch needs no handler change; the file is back to base. | — |
| One repositories request per visible branch (N+1 at the HTTP layer; Constitution V). | No branch-anchored or multi-repository query exists, and only per-branch reads meet FR-003, FR-011 and FR-012 without a backend change. Measured at 0.36 s for 24 branches (R14). | (b) per-repository pivot over `InfrahubRepositoryBranchStatus`: needs ALLOW_ALL, one denial blanks the whole column, and its order does not match the table. One aliased document returns HTTP 500 today (R14). Follow-ups: a `repository_ids` list argument on `InfrahubRepositoryBranchStatus`, or a fix to the concurrent-resolver path (R14). |
| Touching #10779's `get-branch-repositories-from-api.ts::fetchConnection` to pass a no-op `processErrorMessage`. | FR-013 forbids toasts for a per-branch load failure; the shared client toasts every non-permission GraphQL error unless the request opts out. | Catching the toast downstream is impossible (it fires inside the client). A separate fetcher for the list duplicates two GraphQL documents and splits the cache the spec requires to be shared. |
| Promoting #10779's class-local E2E fixture `broken_repository` to `tests/e2e/branches/conftest.py`. | The constitution requires an E2E case for user-facing changes; the fixture already builds the exact import-error scenario. | Duplicating the fixture body in a second file doubles a 50-line async setup and its cleanup. |
| Touching #10779's `repository-row.tsx` to extract `RepositoryNameLink`. | See code: kept or reverted by the rework's implementer (the table no longer uses it). | — |
