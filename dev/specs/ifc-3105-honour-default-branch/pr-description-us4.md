# Why

**A remote branch Infrahub refuses to import used to be skipped without telling the operator.** This PR
reports it in the repository's Tasks tab, and only when there is a reason to look.

When a repository's `default_branch` is not Infrahub's default branch, the remote branch named like
Infrahub's default (`main`, usually) collides with the mapped trunk and is never imported. The only
record was a structlog line, "Ignoring import of mismatched default branch", which never reaches the
task log. An operator who pushed to that branch saw nothing happen and had nothing to find.

The sync never creates the branch locally, so it usually shows up as new on every synchronization
and is skipped again. Reporting it on every cycle would add roughly one linked task per minute to the
repository's history.

**Goal:** record the skipped branch as a warning in a task linked to the repository, once when the
repository is connected, then only on a synchronization that either imported something or saw a
commit arrive on the skipped branch itself. An idle cycle records nothing.

> Skipped remote branch 'main' of repository demo: its name collides with the Infrahub default branch, which is mapped to this repository's default branch 'develop'.

**Non-goals:** persistent skipped-branch state on the repository node. The PRD asked for it; the
owner ruled a dedicated status surface overkill on 2026-09-04, so the task log is the intended design,
not a stopgap. Deduplicating the warning across workers is also out: it needs shared state, which is
the GraphQL schema gate this feature avoids.

Jira: [IFC-3140](https://opsmill.atlassian.net/browse/IFC-3140)
Parent: [IFC-3105](https://opsmill.atlassian.net/browse/IFC-3105)
Epic: [INFP-670](https://opsmill.atlassian.net/browse/INFP-670)
Spec set: `dev/specs/ifc-3105-honour-default-branch/`, User Story 4

This is PR 4 of 4 in that spec's breakdown, and it **targets the feature branch
`pog-honour-default-branch-ifc-3105`**, not `develop`. PRs 2 (#10664) and 3 (#10696) are already on
that branch, so this diff is only User Story 4.

## What changed

**Behavioural**

- The add flow (`git-repository-add-read-write`) logs one warning per skipped branch, on success and
  on failure alike. A first sync that fails on some other branch still logs the warning before the
  error is re-raised.
- The per-repository sync flow (`sync-git-repo-with-origin`) logs the warnings, and links its run to
  the repository node, only when the run skipped a branch **and** either imported a branch or saw a
  skipped branch's remote head move (`SyncReport.reports_skipped_branches`). The existing
  link-on-failure-while-`ONLINE` rule is unchanged.
- The import already tags the run with its branch and the node, and every tag update is rebuilt from
  the flow-start tags. The carrier's `add_tags` call therefore repeats every branch an import was
  attempted on (`SyncReport.attempted_import_branches`, the imported and the failed ones), so
  reporting the skipped branch or linking a failed run never drops a branch's tag.
- A standing collision therefore costs one Tasks-tab entry at connect, then at most one per push that
  changes an imported branch, and zero to one per worker per push to the skipped branch. Successful
  idle cycles add nothing.
- The structlog line stays, so the process log still repeats once per cycle.

**Implementation**

- The collision predicate is one method, `_collides_with_infrahub_default_branch`, which
  `validate_remote_branch` and `collect_pending_imports` both call, so it is never re-derived.
  `validate_remote_branch` keeps its `bool` return.
- `CollectedImports` gains `skipped_branches` and `advanced_skipped_branches`. `skipped_branches` is
  decided from the remote, not from the new/updated comparison: a clone whose remote HEAD is the
  colliding branch holds it as a local branch, so the comparison does not list it until it moves.
- The advance check reads the colliding branch's remote-tracking ref **before** `fetch` and compares
  it after. It is a local read of that one ref, with no extra network call and no stored state. A
  branch absent from the pre-fetch read counts as moved, because it was pushed after this clone's
  last fetch. A worker with no clone makes one inside `init`, before the read, so its first sync does
  not report the branch as newly advanced.
- `RepositorySyncer.sync` returns a frozen `SyncReport(skipped_branches, imported_branches,
  failed_import_branches, advanced_skipped_branches)`. When a branch fails it raises the new
  `RepositoryBranchesFailedError(RepositoryError)` carrying the same report, so a carrier's `except`
  block has what a successful run returns.
- `CollectedImports` is a dataclass in `git/repository.py`, not a model in `git/models.py` as the task
  list says, so the two fields went there.

**What stayed the same**

- No schema, migration, GraphQL or REST change. No new repository attribute or status value.
- No new dependency. No new mypy, `ty` or ruff suppression.
- Every existing caller of `sync` that expects a `RepositoryError` still gets one: the new error is a
  subclass.

## How to review

Medium, and confined to `git/{repository,sync,tasks}.py`.

1. `backend/infrahub/git/repository.py` - `_collides_with_infrahub_default_branch`,
   `validate_remote_branch`, `collect_pending_imports`, `_get_colliding_branch_name` and
   `_find_skipped_branches`. The whole collection contract. Both ref reads are skipped on a clone
   with no `origin`, or when no name collides.
2. `backend/infrahub/git/sync.py` - `SyncReport` (with `reports_skipped_branches`),
   `RepositoryBranchesFailedError`, and the report built before `raise_if_branches_failed`.
3. `backend/infrahub/git/tasks.py` - `log_skipped_branches`, `report_sync_run` and the two carriers.
   `sync_git_repo_with_origin_and_tag_on_failure` handles the construction and the sync in separate
   `try` blocks, so each failure path reports and re-raises in place.
4. `backend/tests/component/git/test_sync_repository.py::TestSkippedBranchTaskLog` - the outcome
   evidence, driving both flows against a real app and a `file://` remote.

**Skim**

- `backend/tests/helpers/git.py::LocalRemote` - a trunk-first remote on disk, shared by the unit and
  component tests.
- `backend/tests/helpers/repository_sync.py` - the two flow runners and the log and tag readers.

**Where I would like extra scrutiny**

1. **The operational-status mutation now names the branch the operation ran on.** This landed in PR 2,
   but it is restated here as the plan asks: `_update_operational_status` names
   `infrahub_branch_name` rather than always Infrahub's default branch. The attribute is
   branch-agnostic, so nothing an operator reads back changes. It is a write-path change with no
   operator-visible effect.
2. **The advance trigger is unreliable with more than one worker.** Each worker compares against its
   own remote-tracking refs, and those also move when the worker handles another worker's post-sync
   `RefreshGitFetch` broadcast. So a push to the skipped branch can go unreported altogether, or be
   reported by more than one worker. A single worker ignores its own broadcasts, so there only its
   rarer fetches outside the sync (a changed location, a pinned commit missing from the clone) can
   absorb a push. This is accepted here as a documented limitation (`dev/knowledge/backend/git-sync.md`,
   research.md D6 correction). The fix is a baseline only the sync writes, such as a worker-local ref
   updated after each comparison. That is still no graph state, but it is a spec decision, so it is
   left as a follow-up.
3. **The re-wrap in `sync`.** `raise_if_branches_failed` still raises a plain `RepositoryError`, and
   `sync` re-raises it as `RepositoryBranchesFailedError` with the same identifier and message,
   `from None`. The alternative, passing the report into `raise_if_branches_failed`, would couple a
   repository method to a sync-layer type.
4. **Logs are asserted where the run logger emits them, not read back from the Prefect API.** The
   component tier's Prefect server persisted no flow-run logs at all in this environment (none, not
   just these), so the tests capture `prefect.flow_runs` records with `caplog` and filter on the
   record's `flow_run_id`. That is the stream the task log is fed from. Tags are read back from the
   server.

## How to test

```bash
# The local gate for this PR
uv run invoke format
uv run invoke lint
uv run pytest backend/tests/unit/git
INFRAHUB_USE_TEST_CONTAINERS=true uv run pytest -n 0 \
  backend/tests/component/git/test_sync_repository.py \
  backend/tests/component/git/test_git_repository.py
INFRAHUB_USE_TEST_CONTAINERS=true uv run pytest -n 0 backend/tests/functional/git
```

Results as of the last run: unit/git 270 passed; the two component files above 87 passed and 1
pre-existing xfail; functional/git 6 passed (before the remote-HEAD fix, not re-run since). `component/git/test_git_repository.py` needs
`INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES` unset when a local environment sets it; the new tests clear
the setting themselves.

**Evidence the guards bite, not just pass:**

- Dropping `advanced_skipped_branches` from the report's trigger condition fails
  `test_cycles_report_only_when_something_moved` on the cycle that only pushes to `main`. Paired with
  the trunk-push cycle in the same test, neither trigger can be dropped silently.
- Tagging with only the default branch fails
  `test_reporting_the_skipped_branch_keeps_the_tags_of_the_imported_branches`, which is the
  regression the repeated imported branches prevent. Leaving out the failed branches fails
  `test_cycle_that_imports_one_branch_and_fails_another_reports_the_skipped_branch`, which asserts
  the run's exact tag set.
- Removing the sync flow's `RepositoryBranchesFailedError` handler fails
  `test_cycle_that_imports_one_branch_and_fails_another_reports_the_skipped_branch`.
- Removing the warning from the add flow's failure path fails
  `test_connect_records_the_warning_when_another_branch_fails`.
- Leaving a branch absent from the pre-fetch read out of the advance check fails
  `test_colliding_branch_pushed_after_connect_is_reported` and
  `test_collect_pending_imports_detects_a_skipped_branch_that_advanced[colliding_branch_pushed_after_the_clone]`.
  `test_first_sync_on_a_fresh_worker_does_not_report_an_unchanged_colliding_branch` pins that this
  does not make a fresh worker report every branch.
- Deriving `skipped_branches` from the new/updated loops again fails
  `test_collect_pending_imports_records_the_colliding_remote_head_as_skipped` and
  `test_connect_records_the_warning_when_the_remote_head_is_the_colliding_branch`, whose remote's
  HEAD is the colliding branch.
- Moving the repository construction outside the sync flow's `try` fails
  `test_failing_node_read_links_the_run_while_online[online_repository]`.

## Impact & rollout

- **Backward compatibility:** no message or API change. `validate_remote_branch` keeps its signature.
- **Performance:** when a name collides, one local read of the colliding branch's remote-tracking ref
  before the fetch and one after. Nothing otherwise. No network call.
- **Config/env changes:** none.
- **Deployment notes:** safe to deploy.

## Checklist

- [x] Tests added/updated
- [x] Changelog entry added (`changelog/+ifc-3105-skipped-branch-task-log.added.md`)
- [x] External docs updated (`docs/docs/git-integration/overview.mdx`)
- [x] Internal .md docs updated (`dev/knowledge/backend/git-sync.md`, branch import and mapping;
      `dev/knowledge/backend/git-integration.md`, trunk resolution, staging and known limitations)
- [ ] I have reviewed AI generated content

<!--
Not included, so a reviewer does not have to ask:

No Playwright e2e test. Backend only change with no frontend work; the warning rides on the existing
node Tasks tab, which already lists node-tagged runs and renders their logs (plan Constitution Check,
Principle IV).

The PRD asks for the skipped branch condition as persistent repository state. That is superseded by
an owner decision of 2026-09-04 that a dedicated status surface for it is overkill, not left undone.
-->
