# Rework contract (2026-10-01): one row per branch

Owner decision after trying the fan-out on a dev stack with 24 branches × 16 repositories: 279 rows,
280 checkboxes, ~15 000 DOM nodes, ~200 console warnings, visibly slow. The 24 per-branch requests
complete in 0.36 s total, so the cost is rendering, not fetching. The ticket's "one row per
repository" assumed one or two repositories per branch. The list goes back to one row per branch and
shows repositories the way the Proposed changes cell shows a many-cardinality relationship.

## Columns (after "Proposed changes", before "Branched from")

| id | header (`TableColumnHeaderSimple`) | cell |
|---|---|---|
| `repositories` | Repositories | `BranchRepositoriesCell` |
| `git_state` | Git state | `BranchGitStateCell` |

The Commit column is dropped. The commit is shown in the repository pill's tooltip and on the
branch details page.

## Data

Each cell calls the existing `useGetBranchRepositories({ branchName: branch.name, syncWithGit: Boolean(branch.sync_with_git) })`
from `entities/repository/ui/queries/get-branch-repositories.query.ts` (PR #10779). Both cells of a
row share one query by key; the branch details page shares the same cache and the same 10 s poll
while a repository is syncing. One request per branch, as before. No table-level `useQueries`, no
row model, no fan-out rule.

Repositories are ordered with `rankRepositories` (failed imports first, then unreachable, then by
name). `ranked[0]` is "the first repository" below.

## `BranchRepositoriesCell({ branch })` — `cells/branch-repositories-cell.tsx`

`TableCell className="h-auto min-h-14"`, early returns:

- pending → `Spinner` (one `role="status"`), as `BranchProposedChangesCell`.
- `{ status: "denied" }` → `<span className="text-foreground-muted">No permission</span>`.
- query error → `<span className="text-foreground-muted">Could not load repositories</span>` wrapped
  in `@infrahub/ui` `Tooltip` with `error.message`, plus `<span className="sr-only">{error.message}</span>`.
- ok with 0 repositories → `<span className="text-foreground-muted">` "Not synced with Git" when
  `branch.sync_with_git` is falsy, "No repositories" otherwise.
- ok with N ≥ 1 → the Proposed changes layout (`Row className="flex-wrap"`):
  - `LinkPill` to `getObjectDetailsUrl(ranked[0].kind, ranked[0].id, [getBranchQspOverride(branch.name, Boolean(branch.is_default))])`,
    `className="max-w-40"`, content: `FolderGitIcon` (shrink-0) + `<span className="truncate">{name}</span>`.
    Wrap the pill in `Tooltip` whose message is one line: `<Git state label> · <7-char commit>` (omit the
    commit part when `commit` is null; append ` · read-only` when `isReadOnly`).
  - when N > 1: react-router `Link` to `getBranchDetailsUrl(branch.name)` with text `+{N - 1} more`,
    `className="shrink-0 whitespace-nowrap text-foreground-muted text-sm hover:underline"` (same as
    the Proposed changes "+N more").

## `BranchGitStateCell({ branch })` — `cells/branch-git-state-cell.tsx`

`TableCell className="h-auto min-h-14"`:

- pending, denied, error, or 0 repositories → blank cell (no spinner, no dash).
- N ≥ 1 → `GitStatePill syncStatus={ranked[0].syncStatus}` (the worst state, since failed imports
  rank first). When N > 1, follow it with `<span className="text-foreground-muted text-xs">{n}/{N}</span>`
  where `n` = number of repositories whose `syncStatus.value` equals `ranked[0].syncStatus.value`,
  and wrap the pair in a `Tooltip` listing counts per label, e.g. `Import Error: 1 · In Sync: 15`.

## Table

- `BranchesDataTable` / `getBranchTableColumns` go back to `BranchListItem` rows (`getRowId: row.id`),
  the original per-row selection and the original `getToggleSelectedRowHandler` call. The anchor-row
  selection, `isBranchAnchorRow`, `enableRowSelection` predicate, `repositoryName` /
  `excludeFromTabOrder` props and the `tabIndex={-1}` plumbing are removed.
- Grid template: `[fit-content(WIDE), fit-content(MAX), minmax(150px, 200px), REPOSITORIES_TRACK, GIT_STATE_TRACK, repeat(columnCount - 6, fit-content(MAX)), 2.5rem]`
  with `REPOSITORIES_TRACK = "minmax(12rem, 18rem)"`, `GIT_STATE_TRACK = "9rem"` (fixed so cells
  filling in do not shift columns).
- Checkbox keeps `aria-label={`Select ${branch.name}`}` (accessibility win, independent of layout).
- `React.useMemo` stays removed (React Compiler).

## Removed from the branch (revert to base or delete)

- `entities/branches/domain/model/branch-table-row.ts`, `domain/rules/to-branch-table-rows.ts` (+test),
  `ui/hooks/use-branch-table-rows.ts` (+test), `cells/branch-repository-cell.tsx`, `cells/branch-commit-cell.tsx`,
  `tests/fake/branch-table-rows.ts`, `branches-data-table.test.tsx` (fan-out selection cases).
- `entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler.ts` (+ its new test): back to base.
- `frontend/packages/ui/src/components/button/button.tsx`: back to base (no `excludeFromTabOrder`).
- `cells/branch-proposed-changes-cell.tsx`, `cells/branch-actions-cell.tsx`: back to base.
- `shared/components/display/commit-hash.tsx` + test (lifted from #10658): removed; no consumer.
- `BRANCH_FIELD_SCHEMAS`: `repository`/`commit` entries replaced by `repositories`; `git_state` stays.

## Kept

- #10779 touches: `fetchConnection` no-op `processErrorMessage`, card failed state with message,
  `RepositoryNameLink` extraction (card only now; still two call sites? No: the table no longer uses
  it. Keep the extraction only if `repository-row.tsx` reads better with it; otherwise revert it too
  and drop the file — implementer's call, say which).
- E2E: `tests/e2e/branches/conftest.py` factory fixture and the `sync_with_git=True` premise in
  `test_branch_details_repositories.py` stay (still the correct premise). `test_branches.py` goes
  back to base (one row per branch again). `test_branches_git_columns.py` asserts, on the broken
  branch's row: the repository pill names the repository and links to its page, the Git state pill
  reads "Import Error"; and a `sync_with_git=False` branch reads "Not synced with Git".

## Tests (vitest browser mode)

- `get-branch-table-columns.test.tsx`: headers order (Repositories, Git state after Proposed Changes,
  no filter/sort control); ok row with 3 repositories: pill shows the ranked-first (failing) repository,
  links with `branch=<name>` (default branch: no param), tooltip holds label + 7-char commit,
  "+2 more" links to the branch details URL; Git state pill colour = schema colour, `1/3` count,
  tooltip with per-label counts; single repository: no count; colourless status → grey badge;
  commit null → tooltip without commit; pending → one `role="status"` in Repositories, blank Git
  state; denied / error (with sr-only message) / empty (two texts) → texts in `text-foreground-muted`,
  Git state blank, no `-`/`—`.
- `branches-table.test.tsx`: branch cells render while repositories pending; one request per branch
  (`getBranchRepositories` mock called once per branch, with the right `branchName`/`syncWithGit`);
  refocus within staleTime issues no extra request; GraphQL error on one branch → that row reads
  "Could not load repositories", others intact, no toast; `PERMISSION_DENIED` → "No permission".
- `branch-repositories-card.test.tsx` and `get-branch-repositories-from-api.test.ts` keep the
  no-toast and message cases from the fix pass.
