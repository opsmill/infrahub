# Phase 4 review synthesis: IFC-3201 branches table Git columns

> **Historical.** This is the 2026-09-30 review of the fan-out implementation (one row per branch and repository). The must-fix and should-fix items were applied in the review-pass commit; the advisory items are tracked as follow-ups in `pr-notes.md`. The fan-out was later replaced (research R14, R15), so file and symbol names below may no longer exist.

Eight reports (code, tests, UI, errors, types, comments, simplify, coderabbit-manual). Every item below was checked against the worktree source. No blockers. `n` = how many reviewers raised it independently. Paths are relative to `frontend/app/src/entities/` unless they start with `tests/` or `dev/`.

## (A) Must fix before PR

- **F1 (major, n=1)** `branches/ui/branches-table/branches-data-table.test.tsx:127-131`: the "repeating name/status/PCs" test only checks `new Set(texts).size === 1`, so it also passes when every cell is empty. **Fix:** assert each repeated column equals its expected text ("alpha", the status label, "Add VLANs") on all three rows.
- **F2 (minor, a11y, n=1)** `branches/ui/branches-table/cells/branch-repository-cell.tsx:25,34,42`: the four state texts use `text-subtle-muted`, which is under 4.5:1 contrast. styling.md keeps that tier for decorative text, and these states are what the ticket delivers. **Fix:** use `text-foreground-muted`. The spec needs the same correction (see below).
- **F3 (minor, a11y, n=1)** `branch-repository-cell.tsx:24`: the error reason sits in a `Tooltip nonInteractiveTrigger`, so keyboard and screen-reader users cannot reach it. FR-013 moved the reason from the toast into this tooltip, so for them the reason is now gone. **Fix:** add an `sr-only` span holding `row.errorMessage` next to the visible text, or make the trigger focusable.

## (B) Should fix in this PR (cheap, clear)

- **F4 (minor, n=2)** `branches/ui/hooks/use-branch-table-rows.ts:17-18`: the comment cites a spec ID "(SC-007)", which code-doc-style forbids, and restates the declarations. **Fix:** `// Reuse row objects while a branch's result is unchanged, so another branch resolving does not re-render them.`
- **F5 (minor, n=2)** `cells/branch-repository-cell.tsx:39`: the `row.state !== "ok"` catch-all really means "empty". **Fix:** use `row.state === "empty"`.
- **F6 (nit, n=2)** `branches/ui/branches-table/branches-table.tsx:34`: the hook is called inside a JSX prop. **Fix:** hoist it to `const rows = useBranchTableRows(flatData)`.
- **F7 (nit, n=2)** `use-branch-table-rows.ts:37-38`: `rowsByBranch.set` runs on every call. **Fix:** set only when the entry is missing.
- **F8 (minor, n=1)** `branches/domain/rules/to-branch-table-rows.ts:6`: `domain/rules` imports another entity's `domain/model`, which the entities-structure.md:89 layering table forbids. One precedent exists (`artifacts/domain/rules/assert-artifact-object.ts`). **Fix:** derive the type in the rule as `Extract<BranchTableRow, { state: "ok" }>["repository"]`.
- **F9 (minor, a11y, n=1)** `branches/ui/branches-table/get-branch-table-columns.tsx:36-47,82,122`: on mirror rows only the checkbox leaves the tab order, so the branch-name link, the Proposed changes pills and the actions button each add a duplicate tab stop per repository. **Fix:** pass `excludeFromTabOrder` (or `tabIndex={-1}`) to those controls on non-anchor rows. The commit copy button stays tabbable because it differs per row.
- **F10 (minor, n=1)** `repository/ui/branch-repositories/branch-repositories-card.tsx:79` and `repository/api/get-branch-repositories-from-api.ts:72`: the no-op `processErrorMessage` also drops the card's toast, and `BranchRepositoriesFailed` shows no reason, so the server message now reaches the user nowhere. **Fix:** pass `error.message` to `BranchRepositoriesFailed` as secondary text or a tooltip, following the F3 pattern.
- **F11 (minor, n=2)** `tests/e2e/branches/conftest.py:124-131`: `contextlib.suppress(Exception)` in teardown swallows failures silently. A leaked `CoreRepository` then pollutes later tests. **Fix:** catch, and log with the repository name.
- **F12 (minor, n=1)** `tests/e2e/branches/test_branches.py:145-150`: the `den1-maintenance-conflict` and `atl1-delete-upstream` locators are unscoped and non-exact. Mirror rows repeat the name link, so either branch having two or more repositories breaks strict mode. **Fix:** use `_anchor_branch_link` for all three.
- **F13 (minor, n=0, found in verification)** `use-branch-table-rows.test.ts:147-166`: the identity test only covers a branch resolving *below* `main`. The WeakMap exists for the other case: a branch resolving to several rows shifts every later row's index, and `replaceEqualDeep`, which compares by index, would not keep those rows. **Fix:** add a case where an upper branch resolves to N>1 rows, and assert that the lower branch's rows keep their identity.
- **F14 (minor, n=2)** `nodes/object/ui/object-table/utils/get-toggle-selected-row-handler.test.ts`: no test covers a shift-click range deselect, a first-ever shift-click, or non-anchor rows staying unselected. **Fix:** add these three cases.
- **F15 (minor, tests)** `branches-data-table.test.tsx:160-172`: add a confirm step, then assert `mutateAsync` received exactly one branch (SC-003).
- **F16 (minor, tests)** `branches-table.test.tsx:190-205`: the test sleeps 100 ms and then asserts `≤2`. **Fix:** use `expect.poll` and state the exact expected count.
- **F17 (minor, tests)** `use-branch-table-rows.test.ts:167-186`: the test reads TanStack internals (`observers[0].options`) and duplicates `get-branch-repositories.query.test.ts`. **Fix:** delete it.
- **F18 (minor, tests)** `repository/api/get-branch-repositories-from-api.test.ts:34`: **Fix:** pin `processErrorMessage: expect.any(Function)` in the context matcher.
- **F19 (nit, tests)** Three small cleanups:
  - Drop the `.Toastify__toast` selectors (`branches-table.test.tsx:264` and the card test).
  - Restore `navigator.clipboard` with `vi.stubGlobal` (`get-branch-table-columns.test.tsx:208`).
  - Remove the dead `/[-—]/` loop (`get-branch-table-columns.test.tsx:304-306`).
- **F20 (nit, comments, n=1)** Four comment edits:
  - `get-toggle-selected-row-handler.ts:4`: drop "Ids, not indexes:".
  - `conftest.py:53`: replace "the band" with "the failed flow run".
  - `test_branches_git_columns.py:3-4` and `test_branch_details_repositories.py:3-4`: keep only line 1 of each docstring.
- **F21 (nit, n=1)** `branches/domain/model/branch-table-row.ts:12`: drop the `export` on `BranchTableRowState`.

## (C) Advisory / follow-up

Adopt these only if cheap in the same file:
- Use a single `TableCell` with a `switch` in `branch-repository-cell.tsx` (simplify). This pairs well with F2, F3 and F5.
- Use per-cell `data-testid` instead of sibling-index lookups, in both the unit tests (`COLUMN_COUNT` math) and the e2e XPath `following-sibling::*[n]` (n=2: tests, coderabbit).
- Key the grid tracks by column id instead of position (`branches-data-table.tsx:22-38`). The track test re-parses CSS against constants exported only for the test, so drop it or switch to header x-offsets (n=2).
- Call `toBranchTableRows` once with every branch, as the contract says (n=2). This conflicts with the per-branch cache, so keep the per-branch call and amend the contract.
- Surface a stale marker when a background refetch keeps failing (errors). This is already documented as invariant 9 / R11.
- Remaining low-priority suggestions:
  - Use `Tooltip` instead of `title` on the repository name (UI).
  - Add an `isAnchor` field to the row model (types).
  - Merge BranchNameCell's two optional props into one (types). Accept as is.
  - Inline `getBranchRepositoryColumns`.
  - Add a `mockBranchTableDeps()` test helper.
  - Make `broken_repository` a plain fixture instead of a factory.
  - Split `branches-table.test.tsx` along its mocking seams.
  - Make the GIVEN/WHEN/THEN markers consistent.
  - Add a comment on the `table.getRow(branch.id)` invariant.
  - Unify the chip shapes and add a Spinner `motion-reduce` variant. Both are design-system wide.

## (D) Rejected after verification

- **Remove the module-level WeakMaps (simplify, "HIGH VALUE").** Part of the premise is true: `query-core@5.101.4 queriesObserver.js:154` does run `this.#combinedResult = replaceEqualDeep(this.#combinedResult, combine(input))`. But `replaceEqualDeep` pairs rows by array index. When a branch resolves from 1 pending row to N repository rows, every later branch's rows change index, get compared against unrelated rows, and come back as new objects. That breaks SC-007. The caches key by branch object, so they survive the shift. The robustness point also fails: a deep-equal but new `BranchListItem` already keeps its identity through the `replaceEqualDeep` pass that runs on top of the caches. Keep the caches and add F13 to lock in the behaviour.

## Spec corrections implied

1. In `contracts/ui-cells.md:13`, `plan-synthesis.md:85`, `research-brief.md:51` and `tasks.md:11`, replace `text-subtle-muted` with `text-foreground-muted` for the state texts.
2. In `contracts/ui-cells.md:31` and spec E3, the error reason must be reachable by keyboard and screen reader (visually hidden text or a focusable trigger), not only a hover tooltip.
3. Extend spec P4: controls on repeated rows (name link, Proposed changes pills, actions menu) are out of the tab order as well as the checkbox. The commit copy button stays.
4. In `contracts/ui-cells.md` (usage of `toBranchTableRows`), record that the hook calls it once per branch to keep the per-branch identity cache.
5. `RepositoryNameLink` reveals a truncated name with `title`; change it to `Tooltip` only if C is adopted.
6. FR-013 / card: the branch details "Failed" state shows the error message (F10).

## Fix-pass grouping (disjoint files)

- **G1 hook + rule**
  - Items: F4, F6, F7, F8, F21.
  - Files: `use-branch-table-rows.ts`, `to-branch-table-rows.ts`, `branch-table-row.ts`, `branches-table.tsx`.
- **G2 branch cells + columns**
  - Items: F2, F3, F5, F9, and the single-`TableCell` refactor from C.
  - Files: `branch-repository-cell.tsx`, `get-branch-table-columns.tsx`, `branch-name-cell.tsx`, the proposed-changes and actions cell files, and `get-branch-table-columns.test.tsx` (including the F19 clipboard/regex nits and new tests for F3/F9).
- **G3 repository card**
  - Items: F10, F18.
  - Files: `branch-repositories-card.tsx`, `branch-repositories-states.tsx`, `branch-repositories-card.test.tsx` (including the Toastify nit), `get-branch-repositories-from-api.test.ts`.
- **G4 unit tests**
  - Items: F1, F13, F14, F15, F16, F17, the rest of F19, and the F20 handler comment.
  - Files: `branches-data-table.test.tsx`, `branches-table.test.tsx`, `use-branch-table-rows.test.ts`, `get-toggle-selected-row-handler.ts` and its `.test.ts`.
  - Run after G1 and G2 land, or tolerate their text changes (F2 changes no copy, so it is safe to run in parallel).
- **G5 e2e**
  - Items: F11, F12, and the F20 e2e comment/docstring edits.
  - Files: `tests/e2e/branches/conftest.py`, `test_branches.py`, `test_branches_git_columns.py`, `test_branch_details_repositories.py`.
- **G6 spec**
  - Items: spec corrections 1-6.
  - Files: `dev/specs/ifc-3201-branches-table-git/*`.

After all groups finish, run the full CI gate: `biome ci`, `knip`, `betterer ci`, `pnpm test`.
