# PR notes: INFP-671 branch details repositories

Draft material for the PR description.

## Live check against a seeded stack

`scenarios/` seeds a local stack (see its README). It creates these `scn-` branches: `scn-all-clear`,
`scn-import-error`, `scn-many-errors`, `scn-generator-failed`, `scn-many-tasks` and `scn-no-git`,
plus unreachable repositories (`--with-unreachable`). Every scenario page was checked with
`scenarios/verify.mjs` (screenshots plus text checks), except these, which the seed can't produce:

- the "Not synchronised with Git" and "No Git repositories" empty states: repositories are global,
  so every branch lists some
- exactly 10 repositories (no pager): the instance already has more
- a repository stuck mid-sync (`syncing`)
- the no-permission state (needs a restricted account and role).

These four are covered by component tests only. The e2e tests are still not run (see below).

Seeding found a backend issue: a failed periodic sync's task is tagged with the default branch
(`main`) only, so on another branch the band may not find its error line and falls back to "The
error details couldn't be found for this import." The seed works around it by running "Import
current commit" on each broken branch. Backend ask in `follow-ups.md`.

## R2 verification (T001)

Verified by reading this branch's backend code (see `research.md`, "R2 verification results").
The seeded stack contradicts it for the periodic sync (see above).

- Every import runs `InfrahubRepositoryIntegrator.build_import_plan`, which tags the running flow
  with the branch it imports into and the repository id. The band's lookup
  (`InfrahubTask(branch, related_node__ids, workflow: IMPORT_WORKFLOWS)`) finds: the initial add
  (read-write and read-only), "Import current commit" (`git-repository-import-object`), read-only
  pull, read-only "import last commit", and the periodic sync (`sync-git-repo-with-origin`).
- Not findable: the worker-bootstrap import inside `git_repositories_sync`, after a worker
  re-clones. The band shows its fallback ("The error details couldn't be found for this import." +
  "Open repository").
- The last `error` line of a failed flow is Prefect's
  `Finished in state Failed('Flow run encountered an exception: <Type>: <message>')`. The band
  unwraps it and shows `<Type>: <message>`.
- A periodic-sync failure message lists every failing branch of the repository, not only the one
  being viewed.

## Backend follow-ups (not blockers)

Details in `follow-ups.md`:

1. Run the worker-bootstrap import in its own tagged subflow, or at least log its failure at
   `error` instead of `info`.
2. Tag a failed periodic sync's task with the branch it imported, not only the default branch.
3. Expose the latest import task and its error per branch on `CoreGenericRepository` (for example
   `last_import_task`), so the UI links to it without log parsing. Also: tag
   `git-repository-import-object` with the repository id at flow start, and
   `sync-git-repo-with-origin` with the branch it imports, instead of relying on
   `build_import_plan`'s tags.
4. Newest logs first for `InfrahubTask` (a log order argument or a "last N logs" option), so the
   band can ask for the last few lines instead of up to 10,000.

## Sign-off request: INFP-670

@INFP-670 owner: this PR ships Merge **ungated**. Import errors, unreachable repositories and failed
tasks are shown above the Merge button, but the button does not change (no disable, no warning, no
confirmation). With Merge ungated, is the incident covered, or does this wait for INFP-670's backend
gate? The default stands until you answer: ship ungated, visibility only.

## E2E tests written but not run

They need the compose `/remote` directory, and the only local stack belongs to another worktree,
so they were not run locally. CI runs them in the `shard_branches_repo` shard:
`uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/ -m shard_branches_repo`.

- `tests/e2e/branches/test_branch_details_repositories.py::TestBranchDetailsRepositoryImportError::test_import_error_band_links_to_the_task_page`
  (new): adds a `CoreRepository` on a throwaway branch from a fixture repo without an
  `.infrahub.yml`, waits for `error-import` and the failed `git-repository-add-read-write` task,
  then checks the band shows "is missing a configuration file" and "View task log" opens
  `/tasks/<id>`. Skipped when `INFRAHUB_ADDRESS` is set (it needs the compose `/remote` directory).
- `tests/e2e/branches/test_branch_details.py`:
  `TestBranchDetailsDefaultBranch::test_display_branch_name_and_default_badge` (updated),
  `TestBranchDetailsNonDefaultBranch::test_display_branch_name_and_no_default_badge` (updated),
  `TestBranchDetailsNonDefaultBranch::test_git_repositories_card_renders_above_the_merge_button`
  (new), `TestBranchDetailsTasks::test_validate_task_row_opens_task_details` (new).
- `tests/e2e/tutorial/tutorials/test_tutorial_1_object_create_update_diff_and_merge.py`: the merge
  task check now reads the Tasks card instead of the removed tasks accordion.

## Quickstart scenarios (to walk by hand)

Not walked one by one by hand. `verify.mjs` covered the seeded pages (see "Live check" above);
9 (no permission) and the empty state in 10 were not reachable on the seeded stack.

- [ ] 1. Header on `/branches/bdr-demo`. Covered by
  `branch-details-header.test.tsx` (order, copy button name, status and default badges,
  description) and the e2e header checks.
- [ ] 2. Details tab order (Details, Git repositories, buttons, Tasks). Covered by
  `branch-details.test.tsx` ("renders Details, then Git repositories, then the action buttons,
  then Tasks") and e2e `test_git_repositories_card_renders_above_the_merge_button`.
- [ ] 3. Repositories card rows (Import Error first, unreachable icon, read-only tag, commit).
  Covered by `branch-repositories-card.test.tsx` (ranking, read-only tag, warning icon, Git
  state).
- [ ] 4. Red and amber bands, "View task log". Covered by `repository-error-bands.test.tsx` and
  e2e `test_import_error_band_links_to_the_task_page` (not run).
- [ ] 5. Merge unchanged by failures. No automated test asserts the button is unaffected;
  `BranchMergeButton` itself is unchanged by this PR (it only moved below the repositories card).
- [ ] 6. Tasks card (order, count, failed count, title links). Covered by
  `branch-tasks-card.test.tsx` and e2e `test_validate_task_row_opens_task_details`.
- [ ] 7. Refresh refetches repositories, bands and tasks. Covered by
  `branch-details-header.test.tsx` ("refreshes branches, repositories and tasks") and
  `refresh-button.test.tsx` (several query keys).
- [ ] 8. Dark theme. Covered by `repository-error-bands.test.tsx` ("switches both band colours
  with the dark theme", computed colours) and the FR-050 grep. Pills and tables not checked
  visually.
- [ ] 9. No repository view permission. Covered by `branch-repositories-card.test.tsx` ("says the
  user has no access"). The tasks-still-list half has no test.
- [ ] 10. Sync with Git off. Covered by `branch-repositories-card.test.tsx` ("not synchronised
  with Git") and `get-branch-repositories.test.ts` (row set).
- [ ] 11. Default branch: Details card only. Covered by `branch-details.test.tsx` ("on the
  default branch, renders only the Details card") and e2e
  `test_display_branch_name_and_default_badge`.
