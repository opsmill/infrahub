# Quickstart: validating Git Repository Commit Visibility

**Feature**: IFC-3101 | **Branch**: `pog-repo-commit-visibility-ifc-3101`

Runnable scenarios that prove each phase works. Contracts are in `contracts/`, shapes in
`data-model.md`. Implementation detail belongs in `tasks.md`.

## Prerequisites

```bash
uv sync --all-groups
cd frontend/app && pnpm install && cd ../..
uv run invoke dev.build && uv run invoke dev.start   # full stack with at least one task worker
```

## Phase A: contract and the graph read (the frontend hand-off)

1. Regenerated files are clean:

   ```bash
   uv run invoke schema.validate-graphqlschema
   cd frontend/app && pnpm codegen:graphql && pnpm codegen && git diff --exit-code src/shared/api/graphql/generated && cd ../..
   uv run invoke docs.validate
   ```

2. Run the commit-view query from `contracts/repository_git_state.graphql` against any existing
   repository id on `main`. Expected: `condition: UNAVAILABLE`,
   `unavailable.reason: NOT_IMPLEMENTED`, empty `edges`, no error, and the Infrahub-side fields
   populated, each checked against its own source: `branch_name` is the Infrahub branch queried,
   `git_ref` is the remote branch or tracked ref the branch resolves (a ref name, not a hash), and
   `imported_commit` equals the repository's `commit` attribute on that branch.

3. Run the drift query against a repository with several branches. Expected: one row per branch in
   the row set, each carrying the tracked commit its own branch resolves, with `remote_head` null and
   the column's unavailable state set. Switch to another Infrahub branch and confirm the commit-view
   answer follows it.

4. Permission: run the query as a user without `Core/Repository/view` (see
   `backend/tests/component/graphql/auth/`). Expected: `PERMISSION_DENIED`, identical to querying
   `CoreRepository` directly.

5. Laziness: selecting only Infrahub-side fields makes no worker request at all (component test
   asserts the recorded reader saw no call). Selecting `pending_count` sets
   `include_pending_count`; omitting it leaves the counting call unmade.

Backend tests for this phase:

```bash
uv run pytest backend/tests/unit/git/state/test_classification.py backend/tests/component/graphql/queries/test_repository_git_state.py
```

## Phase B: bounded RPC and the real read path

1. Timeout, shared-path PR: stop every task worker, run the commit-view query. Expected within
   `INFRAHUB_BROKER_RPC_TIMEOUT` seconds (default 30): a `WORKER_TIMEOUT` error with
   `http_status 504` and `data.retry_after_seconds`. Run the drift query with the workers still
   stopped and expect the opposite: no error, every branch row present with its Infrahub-side values,
   `remote_head` null, and `unavailable.reason: TIMEOUT` on the column alone. `GET /api/file/...`
   inherits the same bound and now fails with 504 instead of hanging; its separate defect, where a
   worker-side *error* still returns 200, is a different ticket and is not asserted here. Adding a
   repository while the workers are stopped must still leave no repository behind (T099).

2. Behind: using the `FileRepo` fixture (`backend/tests/helpers/file_repo.py`), add the repository
   and let the first import finish. Do **not** then push and wait for a sync tick: for a read-write
   repository that tick imports the new commits, so the state you were trying to observe is gone
   before you query. Pick one of two setups instead. Either pause `GIT_REPOSITORIES_SYNC` before
   pushing and drive a single `RefreshGitFetch` by hand, so the worker's `origin/<branch>` advances
   with no import; or run the scenario on a read-only repository pinned to that branch, where the
   refs check advances the remote-tracking ref and by design never imports. Then push two commits.
   Expected: `condition: BEHIND`, `pending_count: 2`, the two new commits `PENDING`, the imported
   commit `IMPORTED`, the newest `HEAD`.

3. Rewritten: the imported commit must stop being an ancestor of the head, which amending the tip
   does not achieve - an amended commit keeps its parent, so the imported commit below it is still
   reachable and the answer is `BEHIND`. Rewrite at or below the imported commit instead:
   `git reset --hard <imported>~1` on the fixture remote, commit something new, and force-push.
   Expected: `condition: REWRITTEN`, `pending_count: null`, no row `PENDING`, the imported hash
   absent from `edges` and present only in `imported_commit`.

4. Orphaned: do not try to garbage-collect the imported object away. FR-020 exists precisely because
   its commit worktree is a reachability root, so on a worker that imported it the object cannot be
   collected - that guarantee and this procedure cannot both hold. Produce the state directly
   instead: seed the repository's `commit` attribute with a well-formed hash the clone has never
   held. Expected: `condition: ORPHANED`, `pending_count: null`, no error, and the hash still
   reported in `imported_commit` so a user can see which commit went missing.

5. Not cloned: start a second worker with an empty repositories directory and route the read to it
   (or delete its clone directory). Expected: `condition: UNAVAILABLE`,
   `unavailable.reason: NOT_CLONED`, a `warm_up_task_id`, and exactly one `git_repository_warm_up`
   task in the task list even when the query is fired ten times concurrently. The next read after the
   task completes returns commits.

6. Freshness: `fetched_at` changes after a fetch on the answering worker. For a read-only
   repository, `checked_at` advances after a check cycle even when the remote has not moved, while
   `fetched_at` stays put; `answered_by` is absent from the payload and the worker identity appears
   in the API server log against the request id instead.

7. Trimmed fields: assert the schema exposes no `count`, no `author_email` and no `answered_by`, so a
   consumer cannot come to depend on them.

Tests:

```bash
uv run pytest backend/tests/component/message_bus/operations/git/test_commit_log.py backend/tests/component/message_bus/operations/git/test_branch_heads.py backend/tests/component/services/adapters/message_bus/test_rpc_timeout.py backend/tests/unit/errors
```

## Phase C: read-only refs check

1. Create a read-only repository pinned to `branch01` of a fixture remote. Push to `branch01` on the
   remote. Within `INFRAHUB_GIT_READ_ONLY_REFS_CHECK_INTERVAL_MINS` (set to 1 for the test) the
   commit view shows `BEHIND`; the repository's `commit` attribute is unchanged; no import task ran.

2. On demand: push again, run `InfrahubReadOnlyRepositoryCheckRefs`, observe `BEHIND` with the new
   count before the interval elapses.

3. Idle cost: with no upstream change, the flow log shows a refs listing and no fetch.

4. Tag move: pin a read-only repository to a tag, move the tag upstream, run the check, then read a
   file at the imported commit through `GET /api/file/{repository_id}/...`. Expected: content still
   served (FR-020). Delete the tag upstream and run the check again. Expected:
   `condition: NO_REMOTE`, no exception.

5. Serialisation: trigger the check and an import for the same repository together; the
   `RecordingLockRegistry` timeline (`backend/tests/adapters/lock/`) shows no overlap under
   `repository.<name>`.

6. Convergence: assert the recorded bus messages contain one `RefreshGitFetch` per Infrahub branch
   pinning the moved ref, each carrying the tracked commit rather than the new head.

7. Unreachable remote: point a fixture read-only repository at a remote that refuses connections,
   with a healthy read-only repository alongside it. Expected: the failure is recorded with the
   repository and the reason, the healthy repository is still checked in the same cycle, the flow run
   does not fail, and the next tick retries the failed one rather than skipping it. Trigger an import
   of the failing repository while its check is stuck and confirm the import is not blocked.

8. Non-accumulation: fire `InfrahubReadOnlyRepositoryCheckRefs` ten times concurrently for one
   repository. Expected: exactly one `ls-remote` against the remote, and every response either
   carries the task id of the run holding the claim or a run that exits without contacting the
   remote. Do not assert that all ten responses carry one id: a request admitted before the first
   run claims the repository submits its own run, which then finds the claim and exits. Kill the
   worker mid-check and confirm the next trigger is accepted rather than refused for the whole
   ceiling.

9. Observability: read the cycle record for a tick covering one moved and one unchanged repository.
   Expected: checked, moved, failed and duration present, plus one movement record naming the
   repository, the ref and both commits.

10. Interval: lengthen `INFRAHUB_GIT_READ_ONLY_REFS_CHECK_INTERVAL_MINS`, restart the worker, and
    confirm the due key's TTL follows the new value at the next tick with no schedule rewrite and no
    change to the every-minute cron.

Tests:

```bash
uv run pytest backend/tests/component/git/test_check_refs.py backend/tests/integration/git/test_readonly_refs_check.py
```

## Phase D: branch drift

Repository with many branches, three behind their remote. `InfrahubRepositoryBranchDrift` returns one
row per branch in the row set, exactly three with `condition: BEHIND` and a differing `remote_head`,
read-write branches with `sync_with_git = false` absent from the rows, and a read-only branch with
nothing imported or inherited as `NOT_TRACKED`. `BusRecorder` shows exactly one
`git.branch_heads.get` message.

Per-branch resolution and the query-count invariant, on the new graph query directly: a branch with
its own commit reports it; a branch that never imported reports its origin branch's fork-point value,
still does after the default branch imports a newer commit, and reports the newer one after a rebase;
the recorded database query count is identical for a fixture with 5 branches and one with 200.

```bash
uv run pytest backend/tests/component/core/query/test_repository_branch_values.py
```

## Phase E: frontend and end to end

```bash
cd frontend/app && pnpm test && pnpm exec biome ci . && pnpm knip && cd ../..
INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false uv run pytest -c tests/e2e/pytest.ini tests/e2e/repository/test_repository_commits.py -s --pdb
```

The e2e test uses the `demo_edge_repo` fixture, opens the repository's Commits tab, asserts a row per
commit with hash, summary, author and relative date, the head and imported markers, and that the
copy button places the full hash on the clipboard. The push-then-observe transition is covered at
component level on `FileRepo` instead of end to end, so no test waits out the one-minute sync tick.

## Before pushing

```bash
uv run invoke format
uv run invoke lint
uv run invoke docs.validate
uv run invoke release.validate-dockercomposeenv
```

Then `/pre-ci`.
