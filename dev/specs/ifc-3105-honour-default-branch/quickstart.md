# Quickstart: Validating the feature

Runnable checks that prove each user story end to end. Automated coverage per tier is listed in
[research.md](./research.md) (decision D7); this page is the manual and CI recipe.

## Prerequisites

- A development stack built from this branch: `uv run invoke dev.build && uv run invoke dev.start`,
  with at least two task workers so that warm-clone behaviour can be observed on a worker that did
  not perform the initial clone. Infrahub's default branch is `main` unless noted.
- A Git remote you control (a local bare repository served over `file://` inside the worker
  containers, or a Gogs/Gitea instance) with:
  - repository `trunk-develop`: default branch `develop`, plus a branch named `main`, containing an
    artifact definition or transform whose output differs between `develop` and `main`;
  - repository `trunk-stable`: default branch `stable`, no `main`, plus a branch `develop`;
  - repository `empty`: initialised, no commits.

## Scenario 1: warm clone targets the configured trunk (US1, SC-001)

1. Connect `trunk-develop` as a read-write repository with `default_branch = develop`.
2. Wait for the initial sync; confirm the repository is `ONLINE` and the artifact reflects the
   `develop` tree.
3. Push a new commit to `develop` on the remote. Wait one sync cycle.
4. Regenerate the artifact from the UI. Repeat until a worker that already held a clone handles the
   run (check the worker identity in the task run name).

**Expected**: the artifact reflects the new `develop` commit. Worker logs show no re-clone and no
"couldn't find remote ref" naming `main`.

Automated: `uv run pytest backend/tests/functional/git/test_repository_default_branch.py`. The
warm-clone test in that file fails on `stable` before the fix and passes after.

## Scenario 2: staging plus non-default trunk (US1 scenario 3, FR-006)

1. Create an Infrahub branch `feature-a`. On that branch, connect `trunk-develop` with
   `default_branch = develop`.
2. Open a proposed change from `feature-a` to `main` and let the checks run.

**Expected**: the repository's checks and merge-conflict validation complete against the `develop`
tree, and the result matches what the same repository produces when connected on `main`.

## Scenario 3: the contract cannot be bypassed (US2)

```bash
uv run pytest backend/tests/unit/git/test_git_repository.py -k "construct or read_only_fetch or mapped"
```

**Expected**: constructing the read-write object without `default_branch`, and separately without
`internal_status`, is rejected; the read-only object accepts no trunk and its fetch failure still
raises the classified connection error; the mapping hooks return identity for read-only and the
trunk mapping for read-write.

Mutation check for FR-009: temporarily change the push refspec in
`backend/infrahub/git/repository.py::InfrahubRepository.push` back to the bare branch name and run

```bash
uv run pytest backend/tests/component/git/test_git_repository.py -k non_main_default_branch
```

**Expected**: the test fails with the bare refspec and passes with the `HEAD:refs/heads/...` refspec.

Carrier check for FR-003:

```bash
grep -rn "default_branch_name" backend/infrahub/
grep -n "default_branch" backend/infrahub/git/models.py
```

**Expected**: no output from either command. The first also proves `merge_git_repository`
(`git/tasks.py`) stopped forwarding a trunk, which is the direct factory caller easiest to miss
because it does not go through `get_initialized_repo`.

Placement check for the component-design rule:

```bash
grep -rn "resolve_graph_settings\|list_remote_refs\|ensure_branch_exists" backend/infrahub/git/base.py backend/infrahub/git/repository.py
grep -rn "check_connectivity" backend/infrahub/
```

**Expected**: the first command returns only call sites (the factories importing the resolver), never
a `def` — the definitions live in `git/graph_settings.py` and `git/remote_refs.py`. The second returns
nothing; the connectivity classmethod is gone.

## Scenario 4: misconfigured trunk rejected at connect time (US3, SC-003)

1. Connect `trunk-stable` leaving `default_branch` at `main`.

   **Expected**: the request fails with
   `Branch 'main' does not exist on the remote repository trunk-stable; the remote's default branch is 'stable'.`
   and no repository named `trunk-stable` exists afterwards.

2. Retry with `default_branch = stable`.

   **Expected**: the repository is created and synchronises normally.

3. Connect `trunk-stable` again under another name with `default_branch = develop`.

   **Expected**: no error and no warning; `develop` is imported as Infrahub's `main`.

4. Connect a repository whose URL does not resolve.

   **Expected**: the existing connectivity error, not a trunk message.

5. Connect `empty` with `default_branch = main`.

   **Expected**: `Branch 'main' does not exist on the remote repository empty; the remote is empty or has no default branch.`

Automated: `uv run pytest backend/tests/unit/git/test_git_repository.py -k remote_refs` for the
listing and the pure check, and
`uv run pytest backend/tests/integration/git/test_git_live_remote.py -k trunk` for the mutation path
against a Gogs remote whose default branch is `master`.

## Scenario 5: skipped colliding branch visible from the repository (US4, SC-004)

1. Connect `trunk-develop` (trunk `develop`, remote also has `main`). Open the repository's detail
   page and its Tasks tab.

   **Expected**: the "Adding repository" task is listed and its log contains one warning:
   `Skipped remote branch 'main' of repository trunk-develop: its name collides with the Infrahub default branch, which is mapped to this repository's default branch 'develop'.`

2. Leave the remote untouched, on every branch, for several minutes, then reload the Tasks tab.

   **Expected**: no new task is listed for those cycles and no further skipped-branch warning. This
   is the point of the design: a standing collision must not add an entry every minute.

3. Push a commit to `develop` on the remote. Wait one cycle, then reload the Tasks tab.

   **Expected**: a "Sync git repo with origin" task is listed for that cycle, and its log contains
   one skipped-branch warning naming `main`.

4. Push a commit to `main` (the colliding branch) only. Wait one cycle.

   **Expected**: a "Sync git repo with origin" task is listed and its log contains one skipped-branch
   warning naming `main`, even though the cycle imported nothing. This is the case the design exists
   to cover: the operator has just pushed to the branch Infrahub is not importing. On a stack with
   more than one task worker, expect one such entry per worker as each one's first cycle after the
   push observes the moved head; that duplication is documented and not a fault.

5. Wait several further cycles with nothing moving.

   **Expected**: no additional warning once every worker has observed the push.

6. Delete `main` on the remote, then push a commit to `develop`. Wait one cycle.

   **Expected**: the sync task for that cycle contains no skipped-branch warning.

7. Recreate `main` on the remote, edit the repository's `default_branch` to `main`, then push a
   commit. Wait one cycle.

   **Expected**: no skipped-branch warning, because the collision no longer applies.

Automated: `uv run pytest backend/tests/component/git/test_sync_repository.py -k skipped` for the
report, the once-at-connect warning, the silent idle cycle and both sync triggers, and the functional
test in `backend/tests/functional/git/` for the node link on the child run.

## Scenario 6: Infrahub default branch other than `main` (US1 scenario 4)

1. Start a fresh stack with `INFRAHUB_INITIAL_DEFAULT_BRANCH=trunk`.
2. Connect a repository whose trunk is `main` with `default_branch = main`.
3. Run the read-write matrix: sync, artifact generation, a generator, a computed attribute, a
   proposed change with checks, and a merge that writes back.

**Expected**: every operation targets `main` on the remote and succeeds; the merge advances the
remote `main`.

## Scenario 7: a transform webhook on a non-default-trunk repository (D4)

1. With `trunk-develop` connected (trunk `develop`), configure a transform webhook against it.
2. Trigger it from an event whose context carries no branch.

**Expected**: the transform runs on Infrahub's default branch, and the commit is looked up for that
branch. It must not attempt to resolve an Infrahub branch named `develop`. This is the call site
where the removed fallback silently meant "the platform default" while reading a field that now
means "the trunk".

## Support diagnosis check (SC-005)

Every failure mode in this spec maps to a surface an operator or support engineer can reach without
worker process logs:

| Condition | Where it surfaces |
|---|---|
| Configured trunk absent from the remote, at connect | The create request fails with a validation error naming the trunk and the remote's default branch. No repository remains. |
| Remote unreachable or credentials wrong, at connect | The existing connectivity error, and `operational_status` of `ERROR_CONNECTION` or `ERROR_CRED` for the standalone check action. |
| Remote branch skipped for colliding with Infrahub's default branch | A warning in the "Adding repository" task log at connect, and in a "Sync git repo with origin" task log for any later cycle that imported something or saw a commit arrive on the skipped branch. Both tasks are linked to the repository. The second trigger is per worker, so one push to the skipped branch can produce one entry per worker. |
| Synchronisation failure while the repository is `ONLINE` | The sync child run is linked to the repository and carries the failure in its task log. |
| Repository unreachable or erroring during an operation on a non-default Infrahub branch | `operational_status` on **that branch**, not only on Infrahub's default branch. This is new: today every flow writes the status on the default branch regardless of where it ran, so a branch-scoped failure was invisible on its own branch. Recorded in the spec's Assumptions. |
| Trunk edited after connection to a branch that does not exist | Not surfaced by this feature. Documented as a known limitation in `docs/docs/git-integration/connect-repository.mdx`. |
| Standing collision on a repository where nothing moves on any branch for a long stretch | **Partially surfaced, by design.** The connect-time task carries the warning until it ages out with Prefect's flow-run retention; after that, nothing surfaces until a cycle imports a branch or sees the skipped branch advance. Any activity on either side of the collision re-reports, so this is confined to a wholly dormant repository. The product owner ruled a dedicated status surface for this condition overkill (2026-09-04), so this row is a deliberate limit rather than an outstanding item. |

Confirm each row from the repository's detail page and Tasks tab alone. The last row is the one
condition this feature deliberately does not fully cover; it is listed so the check is honest rather
than to claim it passes.

## Full local gate before pushing

```bash
uv run invoke format
uv run invoke lint
uv run pytest backend/tests/unit/git
uv run pytest backend/tests/component/git/test_sync_repository.py backend/tests/component/git/test_git_repository.py
uv run pytest backend/tests/functional/git
uv run invoke docs.generate && uv run invoke docs.validate
```

The last line matters because two message models change and the message-bus reference page is
generated from them.
