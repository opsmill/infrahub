# IFC-3201 spec brief: Repository, Git state and Commit columns on the branches table

## 0. Decisions taken by the owner at the phase 1 checkpoint (2026-09-30) — these override the recommendations below where they differ
- **Base:** stack on PR #10779's branch `ple-branch-details-repos-infp-671` (branch details: Git repositories and tasks). The run branch `ple-branches-table-git-ifc-3201` is reset onto it; the PR targets `ple-branch-details-repos-infp-671`. Reuse its `entities/repository` data layer (`getBranchRepositoriesQueryOptions`, `BranchRepository`, `GitStatePill`, fakes) as-is; never fork it.
- **Row model:** fan out to one row per branch × repository, repeating every branch cell (checkbox, name, status, proposed changes, actions) on each repository row. Selection keyed by branch id so the toolbar and delete list count a branch once.
- **Empty state:** two texts keyed on the backend `sync_with_git` flag: "Not synced with Git" when false, "No repositories" otherwise. One row; text in the Repository cell; Git state and Commit cells blank (no dash). A `sync_with_git=false` branch that has read-only repositories lists them normally.
- **Commit cell:** 7-character mono hash, full hash in `title`, **with** a copy button on every row (`CommitHash` with `copyable`). `CommitHash` is not on the base; lift `shared/components/display/commit-hash.tsx` (+ its test) byte-identical from PR #10658 at the same path so the later merge is clean, and say so in the PR body.

## 1. Problem
Today you have to open each branch to see its Git health. Add `Repository`, `Git state` and `Commit` columns to `/branches`. A branch with several repositories shows as several ordinary rows, so a failing repository gets its own row. A branch with no Git repositories must look deliberately empty, not broken.

## 2. Key decisions (ranked by impact)

**a. Row model: fan out to one row per branch × repository.** The ticket's `RelationshipTable` analogy does not hold: it lists peer nodes and never repeats a parent. No fan-out exists anywhere in the app. Fanning out costs:
- **Row key.** `getRowId: (row) => row.id` (`branches-data-table.tsx:46`) produces duplicate ids. It needs a composite key `${branch.id}:${repository.id}`, `${branch.id}:none` (empty) or `${branch.id}:pending`.
- **Selection.** `selectedRows` becomes rows, so the toolbar's "N selected" and the delete list double-count.
- **Shift-range.** `get-toggle-selected-row-handler.ts` uses `row.index`, so ranges are counted in rows, not branches.
- **Page size.** `BRANCHES_PER_PAGE=40` counts branches, so a page renders 40+ rows.
- **Repeated cells.** Checkbox, name, status, proposed changes and actions repeat on every row. Proposed-changes queries are deduplicated by query key, so they are not fired twice.

*Recommendation (least blast radius):* the fetch and fan-out happen at table level, never in a cell. A cell cannot add rows.
- A pure rule `domain/rules/to-branch-table-rows.ts` maps `(branches, reposByBranch)` to `BranchTableRow { id, branch, repository | null, state: "pending" | "ok" | "empty" | "denied" | "error" }`. It keeps backend order within a branch.
- `BranchesDataTable` switches to typing its data as `BranchTableRow`, and `getRowId` uses `row.id`.
- Selection is keyed by **branch id**. Toggling any row of a branch toggles all of that branch's rows. The toolbar and delete modal get `uniqueBy(branch.id)`.
- Pagination still counts branches.
- All branch cells repeat, as the ticket says. See open question Q2.
- A stacked cell is the honest fallback (no key, selection or pagination impact), but the ticket forbids it ("no stacking inside a cell"). Use it only if the user rejects fan-out.
- Accept the jump from 1 pending row to N rows when a branch resolves.

**b. Data source: recommend (a), per-branch queries.**
| | Requests | Permissions | Notes |
|---|---|---|---|
| (a) #10779 `getBranchRepositoriesQueryOptions({branchName, syncWithGit})` via `useQueries` over loaded branches | 40 per page (120 after 3 pages), independent of R. On top of the existing 40 proposed-changes queries, that is about 80 on the first page | Normal node read per branch, so a denial is per branch | Shares its cache key with the branch-details card. `syncWithGit=false` selects `CoreReadOnlyRepository` natively |
| (b) `InfrahubRepositoryBranchStatus` per repository, pivoted | 1 + R, flat while scrolling | Needs VIEW with ALLOW_ALL. One denial kills the whole column | Must fetch all branches (`limit` = branch count) and join by name. Table order and filters do not match. Excludes MERGED, so merged branches get no row |
| (c) Backend list-of-ids variant | 1 | Same as (b) | Backend change, so out of scope. The reader already accepts `repository_ids` |

Choose (a); revisit (b)/(c) only if profiling demands it. The epic spec lists "extra columns on the global branches view" as out of scope; this ticket supersedes that line, and the spec should record it.

**c. Dependency on sibling PRs.** Nothing in this base contains #10658, #10779 or #10649. `entities/repository/` does not exist here yet.
- **(i) Stack on `ple-branch-details-repos-infp-671` (#10779), PR against it.** Smallest diff, no duplication: pill, data layer and fakes come free. Cost: blocked until the draft (3 failing checks) merges; rebases whenever #10779 changes its key root; lacks `CommitHash` (#10658).
- **(ii) Re-implement on the feature branch.** Merges independently, but adds another `repository.query-keys.ts`, pill and fetcher, with guaranteed dedup later. Breaks reuse-first.
- **(iii) Copy #10779's files verbatim.** Add/add merges cleanly only if byte-identical at merge time; any later #10779 edit becomes a conflict and silently forks the code.

The HIGH `repository.query-keys.ts` add/add conflict (`["repository"]` #10658 vs `["repositories"]` #10779) and the MEDIUM duplicate `"error-import"` constant (#10779 vs #10649) exist regardless of this ticket.
*Recommendation: (i).* Merge order #10658 → #10649 → #10779 (rebased) → this. Build the Commit cell last; if #10658 is still open then, see Q1.

**d. Empty state.** Follow the backend semantics. A `sync_with_git=false` branch still lists its `CoreReadOnlyRepository` rows, as #10779 does. The explicit empty state appears only when a branch returns zero repositories: one row, with the text in the Repository cell and blank Git state and Commit cells (no dash). The text depends on the backend field `branch.sync_with_git`, which is displayed here, not used as a filter:
- Candidate A (recommended): "Not synced with Git" when `sync_with_git=false`, "No repositories" otherwise.
- Candidate B: one string, "No Git repositories", for both cases.

Style: `text-subtle-muted`.

**e. Git state pill.** Reuse #10779's `GitStatePill`: label, colour and description (tooltip) from the Dropdown, grey `Badge` fallback, **`getTextColor`** contrast (as `homepage/ui/git-repository.tsx`). Not `DropdownCell` (lch trick) nor #10658's duplicate `SyncStatusCell`. It is `rounded-md` vs Status's `rounded-full`, with `proposed_changes` between them, which partly settles "Status vs Git state look alike".

**f. Commit cell.** `CommitHash` from #10658: mono 7-character hash, full hash in `title`, **no copy button** in the dense list (copy stays on detail cards). Null renders blank; a fresh branch's fork-point commit is shown as returned.

**g. Header, position and schemas.** Use `TableColumnHeaderSimple` (no filter or sort). Insert the three columns right after `proposed_changes` (index 3), before `branched_from`. They land inside the `repeat(n-4, …)` track, so the positional template stays valid without changes. Add `repository`, `git_state` and `commit` (`kind: "Text"`, labels "Repository", "Git state", "Commit") to `BRANCH_FIELD_SCHEMAS`. They are not added to `BRANCH_FILTER_DEFINITIONS`. The Repository cell shows the repository name as a link to the repository object.

**h. Polling.** **Keep** #10779's 10 s poll while syncing: only syncing branches poll, they stop on settle, and unchanged options keep the cache shared with branch details. Profile before capping.

**i. Denied or error.** Per branch; branch cells always render. `denied` → one row, muted "No permission" in Repository. Other error → one row, muted "Could not load repositories" (no toasts). Pending → one row, spinner (`branch-proposed-changes-cell` pattern).

## 3. Constraints
- **Layering:** ui → domain → api; no gql in `ui/`; never import another entity's `api/`; branch context injected at `ui/`.
- **Reuse first:** no new primitive without justification and a `shared-components.md` entry.
- **Backend authoritative:** colour, label and row set from the backend; no client mirror of `sync_with_git`/MERGED/DELETING filters.
- **React Compiler:** no `useMemo`/`useCallback`/`React.memo`; early returns pending → error → success → default.
- **Minimal comments; kebab-case files; `useGet…` hooks; object-shaped keys reused from #10779.**
- **CI gate:** `biome ci .`, `knip`, `betterer ci`, `pnpm test`.

## 4. Affected files (`frontend/app/src`)
**From #10779 (stacked):** `entities/repository/domain/model/branch-repository.ts`, `api/get-branch-repositories-from-api.ts`, `domain/use-cases/get-branch-repositories.ts`, `ui/queries/get-branch-repositories.query.ts`, `ui/queries/repository.query-keys.ts`, `ui/branch-repositories/git-state-pill.tsx`, fakes `tests/fake/{dropdown,repository,branch-repositories}.ts`.
**From #10658:** `shared/components/display/commit-hash.tsx`.

**Domain (new):** `entities/branches/domain/model/branch-table-row.ts` (type) and `entities/branches/domain/rules/to-branch-table-rows.ts` (+ `.test.ts`).

**UI (change, `entities/branches/ui/branches-table/`):** `get-branch-table-columns.tsx` (three columns, cells read `row.branch`), `branches-data-table.tsx` (row type, `getRowId`), `branches-table.tsx` (`useQueries` + fan-out), `branches-toolbar.tsx` (dedup), `branch-field-schemas.ts`, existing cells (`row.branch` accessor).

**UI (new):** `cells/branch-repository-cell.tsx` (name, empty, denied and error text), `cells/branch-git-state-cell.tsx`, `cells/branch-commit-cell.tsx`.

## 5. Test plan (must exist)
1. `to-branch-table-rows.test.ts` must cover: 1 branch × N repositories gives N rows with unique ids and stable order; zero repositories gives one `empty` row; denied, error and pending each give one row. Exemplar: `repository-branch-status.test.ts` (#10658), plain `describe`/`it` over fakes.
2. `branches-data-table.test.tsx` must cover: selecting a row of a multi-repository branch makes the toolbar show "1 selected", and the delete list contains that branch once; the grid template has a track for every column. Exemplar: `repository-branches-card/columns.test.tsx` (#10658), plus `get-toggle-selected-row-handler` usage.
3. Cell rendering with `useGetBranchRepositories` mocked: the three headers; chip background equals the dropdown colour (`asRenderedColour`), grey fallback without colour; 7-character commit with full hash in `title`; empty-state text (not "-"); denied still renders name and status. Exemplar: `branch-repositories-card.test.tsx` (#10779).
4. Optional E2E in `tests/e2e/branches/test_branches.py`: a `/branches` row shows `demo-edge`, an import-error chip and the commit. Exemplar: `test_repository_sync_status.py` (#10649) fixture.

## 6. Out of scope
`Upstream`, `Last import` (never wire `updated_at`); filters/sort on new columns; backend/GraphQL changes; `import_error`/`activity`; merge gating; row hover grouping; resolving sibling-PR conflicts (belongs in #10779's rebase).

## 7. Open questions (defaults in bold)
1. **Base: stack on #10779** and pull `CommitHash` from #10658 (merged or via the stack), or build standalone on the feature branch?
2. **Repeat every branch cell (checkbox, name, status, proposed changes, actions) on each repository row**, or show them only on the first row of each branch?
3. Empty-state wording: **"Not synced with Git" / "No repositories"** (A), or a single "No Git repositories" (B)?
4. For `sync_with_git=false` branches: **show their read-only repositories as rows (backend semantics)**, or always show the empty state?
5. Commit copy button in the list: **no**, or yes (`copyable`)?
