# Contract: UI cells, hook and selection

**Feature**: [../spec.md](../spec.md) | **Data model**: [../data-model.md](../data-model.md)

This file covers the props and rendering contracts for what the feature adds or changes on `/branches`, after the rework to one row per branch (2026-10-01, `../rework-contract.md`). Paths are relative to `frontend/app/src/`. Strings are verbatim from the spec.

## Common rules

- **Cell shape**: every new cell renders `TableCell` (`shared/components/table/table-cell.tsx`) with `className="h-auto min-h-14"`, the same row height as the existing cells.
- **Cell input**: each new cell takes `{ branch: BranchListItem }` and calls `useGetBranchRepositories({ branchName: branch.name, syncWithGit: Boolean(branch.sync_with_git) })` from `entities/repository/ui/queries/get-branch-repositories.query.ts` (#10779). Both cells of a row share one query by key. Early returns: pending, then denied, then error, then empty, then loaded.
- **Ordering**: `ranked = rankRepositories(repositories)`; `ranked[0]` is "the first repository" and its state is the worst (FR-005).
- **Loading**: `@infrahub/ui` `Spinner`, the `cells/branch-proposed-changes-cell.tsx::BranchProposedChangesCell` pattern, in the Repositories cell only. Git state stays blank while pending (FR-011), so a pending branch shows one `role="status"`.
- **Blank**: an empty `TableCell`. No `-`, no `—`, no placeholder text (FR-007).
- **Muted text**: `<span className="text-foreground-muted">…</span>`. Not `text-subtle-muted`: that tier is under 4.5:1 contrast and reserved for decorative text (FR-007, FR-012, FR-013).
- **Headers**: `TableColumnHeaderSimple` over the new `BRANCH_FIELD_SCHEMAS` entries, with no filter or sort control (FR-015).
- **Column position**: the two columns sit after `proposed_changes`. The display column ids are `repositories` and `git_state`.
- **Link rule**: the repository pill carries the **row's** branch via `getBranchQspOverride(branch.name, Boolean(branch.is_default))`. The default branch gets no `branch` parameter.

## `BranchRepositoriesCell` — `entities/branches/ui/branches-table/cells/branch-repositories-cell.tsx` (new)

```ts
interface BranchRepositoriesCellProps { branch: BranchListItem }
```

| Query state | Renders |
|---|---|
| pending | `Spinner` |
| `{ status: "denied" }` | muted "No permission" |
| error | muted "Could not load repositories", wrapped in `@infrahub/ui` `Tooltip` with `error.message`, plus `<span className="sr-only">{error.message}</span>` next to the visible text (FR-013) |
| ok, 0 repositories, `branch.sync_with_git` falsy | muted "Not synced with Git" |
| ok, 0 repositories, `branch.sync_with_git === true` | muted "No repositories" |
| ok, N ≥ 1 | the Proposed changes layout, `Row className="flex-wrap"`: the pill below, then, when N > 1, the "+N more" link below |

**Pill**: `LinkPill` to `getObjectDetailsUrl(ranked[0].kind, ranked[0].id, [getBranchQspOverride(branch.name, Boolean(branch.is_default))])`, `className="max-w-40"`, content `FolderGitIcon` (`shrink-0`) + `<span className="truncate">{name}</span>`. It is wrapped in `Tooltip` whose message is one line: `<Git state label> · <7-char commit>`; the commit part is omitted when `commit` is `null`, and ` · read-only` is appended when `isReadOnly` (FR-004).

**"+N more"**: react-router `Link` to `getBranchDetailsUrl(branch.name)`, text `+{N - 1} more`, `className="shrink-0 whitespace-nowrap text-foreground-muted text-sm hover:underline"` (the Proposed changes cell's "+N more").

## `BranchGitStateCell` — `cells/branch-git-state-cell.tsx` (new)

```ts
interface BranchGitStateCellProps { branch: BranchListItem }
```

| Query state | Renders |
|---|---|
| pending, denied, error, or 0 repositories | blank (no spinner, no dash) |
| ok, N = 1 | `<GitStatePill syncStatus={ranked[0].syncStatus} />` (`entities/repository/ui/branch-repositories/git-state-pill.tsx`) |
| ok, N > 1 | the same pill followed by `<span className="text-foreground-muted text-xs">{n}/{N}</span>`, where `n` = repositories whose `syncStatus.value` equals `ranked[0].syncStatus.value`; the pair is wrapped in a `Tooltip` listing counts per label, for example `Import Error: 1 · In Sync: 15` (FR-006) |

`GitStatePill` behaviour, reused unchanged:

- **Colour and label present**: a `rounded-md` chip. `backgroundColor` is the schema colour, and the text colour comes from `getTextColor(color)`.
- **Otherwise**: a grey `Badge` showing `value || label || "—"`.
- **Tooltip**: always wraps the chip, with `description` as its message.

The chip is `rounded-md`, which separates it from the Status column's `rounded-full` pill. The unreachable warning icon is **not** rendered here (FR-016).

## Table — `branches-data-table.tsx::BranchesDataTable` and `get-branch-table-columns.tsx`

| Aspect | Contract |
|---|---|
| Row type | `BranchListItem`, `getRowId: (row) => row.id`, as on the base branch |
| Selection | The base branch's per-row selection and its `getToggleSelectedRowHandler({ row, table })` call, unchanged (FR-008, FR-009) |
| Row checkbox | `aria-label={`Select ${branch.name}`}` |
| Grid template | `[fit-content(WIDE), fit-content(MAX), minmax(150px, 200px), REPOSITORIES_TRACK, GIT_STATE_TRACK, repeat(columnCount - 6, fit-content(MAX)), 2.5rem]`, `REPOSITORIES_TRACK = "minmax(12rem, 18rem)"`, `GIT_STATE_TRACK = "9rem"`; fixed so cells filling in do not shift columns (SC-004) |
| Memoization | none; `React.useMemo` stays removed (React Compiler) |

## `RepositoryNameLink`

See code: the table no longer uses it; the extraction from `repository-row.tsx` is kept or reverted by the rework's implementer.

## Superseded 2026-10-01

`BranchRepositoryCell`, `BranchCommitCell` (and its `CommitHash`), `useBranchTableRows`, the anchor-row selection contract (`enableRowSelection` predicate, `isBranchAnchorRow`, mirror rows, tab-order exclusion, id-keyed shift-range handler) and the three-track grid template described the one-row-per-repository fan-out. They were removed with it (research R14).
