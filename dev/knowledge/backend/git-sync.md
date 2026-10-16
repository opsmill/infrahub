# Git Sync

> Part of: `dev/knowledge/backend/` | Related: [Architecture](architecture.md), [Git Push Queue](git-push-queue.md)

How Infrahub maps and imports branches from external git repositories, how the sync flow reads the
per-branch state of each repository, and how git and import errors surface. Read this before
reasoning about which remote branches get imported, how many queries a sync run costs, or why a git
failure carries (or lacks) a message - the logic is split across several methods and is easy to
mis-trace.

## The repository object and where its default branch comes from

The per-flow repository object is built by `InfrahubRepository.init` / `.new`, and those are the only
two places that read a read-write repository's configuration from the graph. They call
`resolve_graph_settings` (`backend/infrahub/git/graph_settings.py`), which performs one SDK read of
the repository node and returns its default branch, internal status and location.

- **The default branch is a required constructor field.** `InfrahubRepository` declares
  `default_branch: str` and `internal_status: RepositoryInternalStatus` with no defaults, so an
  object cannot exist without them. There is no fallback to Infrahub's default branch anywhere.
- **Every construction resolves it**, not only the one that clones. The object is therefore correct
  whether or not the worker already had a local copy — the distinction that used to decide whether
  the graph was read at all.
- **The read happens on a named Infrahub branch.** `get_initialized_repo` and both factories take a
  required `infrahub_branch_name`, which is also added to the factory's 30-second cache key. The
  branch matters because `internal_status` is branch-scoped and a repository created inside a branch
  exists only there until its proposed change merges.
- **The factories set `infrahub_branch_name` on the instance** from that parameter, so the branch the
  node was read on and the branch the object reports are one value. `_update_operational_status`
  reads it, so status writes name the branch the operation ran on. That attribute is
  `BranchSupportType.AGNOSTIC`, though, so its value is shared across branches and the named branch
  has no observable effect on what an operator sees.
- **The read-only kind has no default branch at all.** It tracks a single `ref`, and the three
  branch-mapping hooks below are the identity on it.

Three abstract hooks on `InfrahubRepositoryBase` keep the base class from needing a default branch of
its own: `_get_mapped_remote_branch`, `_get_mapped_target_branch` and `_resolve_worktree_identifier`.
The read-write kind implements the mapping described below; the read-only kind returns its input.

## Branch import and mapping

- A repository's own `default_branch` is mapped onto Infrahub's default branch by
  `_get_mapped_target_branch` on `InfrahubRepository`: when a commit lands on the
  repository's default branch, it is recorded against Infrahub's default branch, whatever either
  is named.
- Because of that mapping, when the repository's default branch differs from Infrahub's, a remote
  branch literally named like Infrahub's default branch cannot be imported — it would collide with
  the mapped default. The skip is decided in `InfrahubRepository.validate_remote_branch`, *not* in
  `_get_mapped_target_branch`. It returns `False` for this case and for a name Infrahub cannot
  store as a branch, and `True` for a branch to import. The collision test itself is one method,
  `_collides_with_infrahub_default_branch`, which `validate_remote_branch` and the skip record both
  call, so nothing re-derives it.
- The sync never creates the colliding branch locally, so it usually shows up as new on every sync
  and is skipped again, logging "Ignoring import of mismatched default branch" to the process log
  each time. A clone whose remote HEAD is the colliding branch does hold it as a local branch, and
  the local/remote comparison does not list it until it moves. So `collect_pending_imports` decides
  the skip from the remote alone: whenever the remote has the colliding branch, it is recorded in
  `CollectedImports.skipped_branches`, whether or not the comparison listed it.
- It is also recorded in `advanced_skipped_branches` when its remote head moved during this run's
  fetch. Its remote-tracking ref is read before the fetch and compared after it. A branch absent from
  that earlier read counts as moved, because it was pushed after this clone's last fetch. A worker
  with no clone makes one before the read, so its first sync does not see the branch as new.
- `RepositorySyncer.sync` returns a `SyncOutcome`: a `SyncReport` of the skipped, imported and
  advanced branches, the branches it advanced with their commits, and the branches that failed. A
  failed branch does not raise there. Its callers report the skipped branches, then raise
  `RepositoryBranchesFailedError` carrying the outcome through `git/sync.py::raise_if_branches_failed`.
- The periodic cycle catches that error, sends the fetch message, and raises nothing further. A
  failed configured default branch is logged at error level and recorded as `error-import` on the
  branch the trunk imports into, because a trunk failure while it is collected writes no status of
  its own. The failure of any other branch is logged at info level.
- The cycle wraps each repository in its own `try` (`git/tasks.py::sync_remote_repository` is the
  per-repository step), so one repository that raises is logged and the cycle continues with the
  next one.
- The operator-facing record of the skip is a warning in the flow run's log, emitted through
  Prefect's run logger. The add flow writes it whenever its first sync skips a branch. The
  per-repository sync flow writes it only when the run imported a branch or saw a skipped branch
  advance (`SyncReport.reports_skipped_branches`).
- Each branch import runs as a flow run of its own (`git/sync.py::import_branch`), linked to the
  repository node and tagged only with the branch it imports into, so its logs and failure show on
  that branch. The sync flow's run is linked to its own branch when it writes the warning and, while
  the repository is online, to each branch that failed before its import. A failed import does not
  link the sync run, because its own run already shows it. A successful run where nothing moved adds
  nothing to the repository's task history.
- The reverse mapping — from an Infrahub branch name to the remote git branch — is the pure
  function `get_mapped_remote_branch` in `backend/infrahub/git/branch_mapping.py`. Any git
  operation that names a remote ref (`pull`, `push`) must route the branch name through it: when
  the repository's default branch differs from Infrahub's, the remote has no branch named after
  the Infrahub default, and the raw name fails with "couldn't find remote ref".
  `InfrahubRepository._get_mapped_remote_branch` is the read-write kind's implementation of the
  abstract hook, and it supplies the repository's own `default_branch` and
  `registry.default_branch`; code that has no repository object — the API server, which must never
  build one — calls the function directly. The function takes all three inputs as required
  parameters, so no caller can fall back to Infrahub's default branch by omitting the repository's
  trunk.
- Which remote branches a sync imports depends on the Infrahub branch the remote branch maps to
  (`_get_mapped_target_branch`), so the repository's default branch is judged as Infrahub's default
  branch, whatever its own name:
  - **That Infrahub branch exists.** `infrahub_branch_receives_imports` in
    `backend/infrahub/git/branch_mapping.py` decides, in every configuration: Infrahub's default
    branch always receives commits, and any other branch only with `sync_with_git` on.
  - **No Infrahub branch exists.** `git.import_sync_branch_names` (settings), a list of names or
    regex patterns, selects the remote branches the sync creates as new Infrahub branches, with
    `sync_with_git` on. **The list is empty by default, and an empty list selects every remote
    branch.** A remote branch that maps to Infrahub's default branch is never filtered.
- Passing that rule is not the last word, because `validate_remote_branch` still rejects a name the
  database cannot hold and the mismatched default branch described above.
- The sync applies the rule twice, because the first check reads a cache:
  - `get_filtered_remote_branches` in `backend/infrahub/git/base.py` runs over every remote branch
    before anything else, reading the branches from the worker's registry. It keeps a skipped
    branch out of the local/remote comparison, so a cycle with nothing to import does not pay for
    the branch listing below. The registry can lag behind the database, so a branch created moments
    earlier falls into the no-Infrahub-branch arm.
  - `_exclude_unimportable_branches` in `backend/infrahub/git/repository.py` re-checks the branches
    that comparison selected against the branch listing the collection reads from the database, and
    is the check that makes the rule hold. It also drops the branches whose status rejects a commit.
    A branch created after that listing is caught when its creation reports that it exists already.
- The API's commit view calls `infrahub_branch_receives_imports` too, so a branch the sync imports
  nothing into is reported as not tracked. The function must not be reused to decide whether
  a remote branch with no Infrahub counterpart is imported, which the import filters decide.
- A branch that imported commits before `sync_with_git` gated imports keeps its last imported commit,
  and the worker's clone keeps its local branch. Neither moves again, and nothing removes them.

### A push to the skipped branch can go unreported

The advance check compares against the remote-tracking refs, and those move on every fetch, not only
the sync's own. After each successful sync the initiating worker broadcasts `RefreshGitFetch`, and every other
worker fetches on receipt (see [Git Integration](git-integration.md#how-the-workers-converge)). So a
push to the skipped branch is absorbed by whichever fetch runs first: when that is a broadcast fetch
on a worker whose next sync then finds nothing moved, the push is never reported. A single worker
ignores its own broadcasts, so there only the rarer fetches outside the sync can absorb a push: the
one a repository makes when its location changed, or when a pinned commit is missing from the clone.
More than one worker can also each report the same
push, at most once per worker. Reporting it reliably needs a baseline that only the sync writes, such
as a worker-local ref updated after each comparison.

## Per-branch repository read

`get_repositories_commit_per_branch` in `backend/infrahub/git/utils.py` builds the per-repository,
per-branch view the sync flow and the Python computed-attribute trigger gather both read. It issues
two kinds of query:

- One `NodeManager.query` on the default branch reads the repository nodes. That is one call but
  several queries — `node_get_list` to select the nodes, then the info and attribute reads behind
  `get_many` — so only the *number of branches* stops driving the query count, not the node read
  itself. The requested fields are `id`, `name`, `location`, `default_branch` and
  `operational_status`, every one of them branch-agnostic, so the branch the query runs on cannot
  change what a caller reads off the node it is handed as `RepositoryData.repository`.
- One `RepositoryBranchAttributesQuery` (`backend/infrahub/core/query/repository.py`) per chunk of
  `REPOSITORY_BRANCH_READ_CHUNK_SIZE` branch names resolves `commit` and `internal_status` for every
  repository on every branch in that chunk. Those two are the only attributes resolved per branch,
  and the per-branch values live only in `RepositoryData.branches` and `RepositoryData.branch_info`.
  No caller reads them off the node.

The field list is a correctness constraint, not an optimization. `NodeManager.query` builds the node
from the requested fields only, and an attribute that was not requested reads back its **schema
default** instead of raising — so a caller reading a field the query forgot to ask for gets a
plausible wrong value with no error. `operational_status` was in exactly that state: read by the
sync flow, absent from the field list, and therefore always `unknown`.

`REPOSITORY_BRANCH_READ_CHUNK_SIZE` is 100 and is defined in `backend/infrahub/git/constants.py`. It
is not a setting, so for N non-global branches the read costs `ceil(N / 100)` per-branch queries on
top of the node read, rather than one query per branch. When no repository exists the function
returns after the node read and issues no per-branch query at all.

Note that the chunk size bounds the *branch* dimension only. A chunk's result set is repositories ×
branches-in-chunk × attributes rows, and because the underlying query sets an explicit limit it does
not go through `database.query_size_limit` pagination — so the rows per chunk still grow with the
number of repositories.

The attribute source both callers read through is built by
`build_repository_branch_attributes_source` in
`backend/infrahub/core/repository_branch_status/factory.py`. Inside
`get_repositories_commit_per_branch` it is built once, before the chunk loop, and reused for every
chunk.

Every query the read issues — the node read and each chunk — is pinned to one `Timestamp` captured
before the first of them. Without that, a commit written between two chunks would leave the branches
in one chunk reporting the old commit and those in the next reporting the new one for the same
repository, which the computed-attribute gather would read as a branch diverging from the default.

The global branch (`-global-`) is filtered out of the branch names before the chunk loop, so it is
never a key of `RepositoryData.branches` or `RepositoryData.branch_info`. Callers that index those
dictionaries by branch name must skip it themselves rather than expect an entry.

### Why a repository created on a branch is visible from the default branch

The repository kinds are `BranchSupportType.AGNOSTIC`, so the node lands on the global branch
whatever branch it was created from and the default-branch node read finds it. The per-branch
attributes need a second mechanic. `internal_status` is `LOCAL`, defined once on
`CoreGenericRepository` and inherited unchanged by both kinds; `commit` is `LOCAL` on
`CoreRepository` and `AWARE` on `CoreReadOnlyRepository`.

`Attribute.get_create_data` (`backend/infrahub/core/attribute.py`) writes a `LOCAL` attribute on an
`AGNOSTIC` node to the global branch at **creation**, not to the branch it was created from; only a
later write goes through `get_branch_based_on_support_type()` and lands on a specific branch. An
`AWARE` attribute is not covered by that path — its creation row goes to the creating branch.

So a `CoreRepository` created on `feature-branch` and staged there resolves `internal_status` as
`inactive` on the default branch (the global row, `own_value` false) and `staging` on
`feature-branch` (its own row), which is what makes the sync flow enter staging mode and find the
branch via `get_staging_branch()`. The `inactive` fallback below is not involved in that path.

A `CoreReadOnlyRepository` created on a branch differs on one point: its `commit` is `AWARE`, so it
resolves only on the branch it was created from and `RepositoryData.branches` holds `None` for the
default branch until a commit is written there. The sync flow never sees this, reading
`CoreRepository` only; the computed-attribute gather does, and counts the branch as diverging from
the default, which it is.

`RepositoryData.branches` is typed `dict[str, str | None]`: a branch whose `commit` does not resolve
is present with a value of `None`. A branch whose `internal_status` does not resolve is recorded as
`inactive`; the branches affected are collected and logged as one warning per repository after the
chunk loop, rather than one per repository-and-branch pair inside it. A failing chunk raises rather
than being caught, so the read never returns a `RepositoryData` that silently omits branches.

## Rewritten history

`InfrahubRepository.collect_pending_imports` compares each branch twice. Keep the two comparisons
apart, because they drive different outcomes:

- **The commit the graph records against the remote head** says what happened to the branch:
  unchanged, fast-forward, rewrite, re-target or gone from the remote (`git/divergence/`). A
  re-target is a deliberate change of the default branch, which a cache marker announces
  ([The re-target marker](#the-re-target-marker)). The commits are read once per cycle by
  `get_repositories_commit_per_branch` and passed down through the sync flows.
- **This worker's worktree head against the remote head** says whether the clone moves. The sync
  moves a worktree by a hard reset onto the remote head it classified, so a worktree behind the
  remote fast-forwards and the commit imported is the one classified. A worktree that does not lead
  to the remote head, because the remote was rewritten or rewound, loses the commits it held, and
  that includes a worktree ahead of the remote. Such a commit is rare: a delivery resets the
  destination worktree when its replay, its push or its record fails. Only a failed reset, which the
  delivery logs, leaves an unpushed merge commit there. The next delivery attempt discards it,
  because it resets the worktree onto the remote head before its replay, and once the queue is empty
  the sync reset discards it too ([Git Push Queue](git-push-queue.md#a-delivery-attempt)). A
  worktree already on the remote head stays there. When the graph records another commit, the sync
  resets the worktree onto the same commit, which records it, and imports the branch again: a pull
  would move nothing, so it would record nothing.

A worker whose graph already holds the remote head can still hold the discarded history on disk. It
resets and logs the reconciliation, and its classification stays unchanged.

While a read-write repository has pending pushes, the sync leaves out its default branch and the
remote source branch of each pending merge before the classification, so none of them is
classified, moved or recorded until the queue clears. When the default branch is classified as a
rewrite, the sync also checks whether the new head still holds the last pushed commit, and records a
reverted push when it does not
([Git Push Queue](git-push-queue.md#the-reverted-push-record)).

The sync considers the branches whose local head differs from the remote, and also the local
branches whose graph commit differs from the remote head. Only branches that can still record a
commit take part in the second comparison. A branch that needs a rebase, is being merged, failed a
merge, is merged or is being deleted rejects the commit, and so does a branch Infrahub no longer
lists, so it would be selected again on every cycle. `git/branch_status.py::accepts_commit_write`
holds that rule for both comparisons. A commit write the graph still refuses, because the status
changed after the listing, fails that branch alone. The sync classifies a branch new to this worker too,
because the graph can hold a commit that another worker imported and the remote has since discarded.
A graph commit that is empty or not a full commit id counts as none, so the branch classifies as a
fast-forward and records a real commit. When git cannot read its object store, a new branch is still
created, but a branch this worker holds fails before its worktree moves. Each reset that discards a
commit, from the worktree or from the graph, logs one line with the branch, the discarded commit and
the commit that replaced it. A plain fast-forward logs nothing. The add flow passes no graph
commits, so it classifies nothing.

### The rewrite record

A rewrite is also recorded on the repository, in four `LOCAL` attributes of the repository generic:
`last_rewrite_previous_commit`, `last_rewrite_commit`, `last_rewrite_at` and `rewrite_count`.
`HistoryRewriteRecorder` (`git/divergence/recorder.py`) is the only writer. It writes only when the
graph comparison classifies the branch as a rewrite, so a worker that only resets its own stale
worktree records nothing.

- **Record right after the commit write, in the same hold of the repository lock.** After the import
  the next cycle already reads the new commit as unchanged, so a later record never happens.
- **A failed record fails its branch alone, at step `record`, and keeps its import queued.** The
  graph already holds the new commit, so no later cycle selects the branch again to import it, and
  that rewrite stays unrecorded. The import still runs, so the failure leaves `sync_status` alone. On
  the default branch it is logged at error level, and the run fails although the import converged.
- **A failed record is logged once, where it is caught, the way a failed import is.** The store
  chains the SDK error, so the reason is the API's own message for a known failure, and the
  traceback is kept only for an error that is not recognised, such as a lost connection.
- **A rewrite of the default branch also records a reverted push.** When the new head does not hold
  the last pushed commit, the delivery state records it in `delivery_reverted`, through
  `WritebackIntentStore.record_reverted`; a re-target clears the last pushed commit instead. A
  failure fails the default branch at step `record` and keeps its import, as above. A later rewrite
  records a pushed commit that is still unrecorded.
- **The count is what the branch reads, not what it did.** A branch-local read falls back to the
  origin branch, so a branch created after a trunk record reads that record and counts on from it.

A read-only repository records from the import of its last commit, in
`git/repository.py::InfrahubReadOnlyRepository.update_latest_commit`. The flow holds the repository
lock around it. It classifies the commit the ref resolves to against the commit the graph records,
imports that commit as before, and records a rewrite once the new commit is written. It never
resets the clone: a read-only repository follows its remote. A graph read or a classification that
fails logs a warning, and the import goes on, because the check must not change what is imported. A
record that fails fails the run after the import, as on the read-write path. Either way the next
import reads the new commit, so that rewrite stays unrecorded.

### The re-target marker

A change of `default_branch` moves the git branch that feeds Infrahub's default branch, so the trunk
commit in the graph is often not an ancestor of the new head. A marker in the cache
(`git/divergence/suppression.py`) tells the sync that this break is deliberate, so it resets the
trunk and records no rewrite.

- **Written inside the update transaction.** `InfrahubRepositoryMutation.mutate_update_object` writes
  it for the update and for every upsert of a read-write repository, before the commit. It is keyed
  by the new git branch, so each target has a marker of its own and a rolled-back update cannot
  replace the marker of a change that committed. The cache write is not part of the transaction, so
  a rolled-back update leaves its marker until the marker expires. That marker does nothing, because
  a cycle reads only the marker for the git branch that `default_branch` names.
- **Read only by `collect_pending_imports`**, once per cycle, for the trunk alone. The cycle reads
  only the marker of the git branch it synchronises, so markers for other targets do not apply and
  stay.
- **Cleared only by the cycle that reconciles it.** After the collection, the sync clears a marker
  it read once the trunk records the remote head of the branch the marker names. A failed trunk, an
  inactive repository, a default branch the remote does not hold yet, or a default branch that the
  sync skips for pending pushes keeps it.
- **Expires after seven days**, which only removes a marker that no cycle reconciles.

A read-only repository uses no marker. An update or an upsert that changes its `ref` or `commit`
submits the pull and the import of the last commit with `target_changed` set, after the transaction
commits: a workflow submitted before the commit still runs when the transaction rolls back. This
holds because the update opens and commits its own transaction, as every GraphQL request does. A
caller that already holds a transaction commits it after the submission.

A commit that a flow writes goes through the same update, so every change of the commit submits
another pull and import with `target_changed` set. "Import latest commit" carries no flag, so it can
meet a re-point. A run that resolves a `ref` the graph no longer records classifies nothing: it was
submitted before a change of `ref`. Two windows still record a false rewrite, and they are accepted,
because a read-only repository sends no trunk signal: a run that takes the lock after a change of
`ref` and before the runs of that change, and a run that comes after a pull writes a pin that the ref
does not hold and before the import that this write submits.

## Cloning and the repository lock

Creating the local copy deletes whatever is already at the repository directory before cloning
into it. The creation primitive does not take the repository lock itself, so every caller that
reaches it holds that lock; `initialize_local()`, which clones only when it finds no usable copy,
also re-checks once the lock is held and clones only if the copy is still absent or unusable. Two flows
on the same worker can otherwise ask for the same repository at the same time — a periodic sync
and a refresh request, say — and the second clone wipes the directory the first one just built,
invalidating the git objects already opened against it and leaving the sync unable to resolve a
commit.

The re-check treats a copy that fails validation like an absent one. The copy was absent before
the lock was taken, so a copy that is present but broken once the lock is held was left by a
concurrent clone that failed part-way (the clone succeeded but the checkout did not, say), and
cloning over it is the only way back to a usable copy. A `Repo` already opened on that broken copy
is closed first: once the directory is replaced it would keep reading the deleted object store.
The check before the lock still raises on a broken copy rather than replacing it.

The lock is reentrant per context, so a caller that already holds it for a wider critical section
pays nothing extra.

## Repository activity records

The `InfrahubRepositoryActivity` query answers what is running on a repository across every branch.
The per-branch statuses of a repository (`sync_status`, `internal_status`) each describe one branch,
and its connectivity status (`operational_status`, the same on every branch) records no run, so the
answer comes from records in the cache instead (`git/activity/`, keys in `git/state/cache_keys.py`).
The design targets the Redis cache driver.

- **A run record per run.** `RepositoryActivity.track` writes
  `git:activity:run:{repository_id}:{run_id}` when a run starts, with a lifetime of 300 seconds, and a
  background task rewrites it every 60 seconds. Each run has its own key, so two runs on one
  repository never overwrite each other. The record holds the operation, the phase (`fetching`,
  `building`, `applying`), the branch being built or applied, the worker and two times.
- **The lifetime is several renewals long** because a git fetch runs synchronously and blocks the
  event loop, which can delay a renewal by more than a minute. A fetch or a first clone that blocks
  for longer than 300 seconds lets the record expire until the next renewal. A killed worker leaves a
  record that expires within 300 seconds.
- **Every exit removes the record.** When the run ends, by success, failure or cancellation, the
  run leaves the per-process table and its renewal task is cancelled before anything is awaited. The
  renewal task is then awaited, so it cannot write the record again, the last-run record is written
  and the run record is deleted. That cleanup runs as a shielded task, because a cancel scope, such as
  a flow timeout, cancels again at every await and would otherwise skip it. Every cache call is best
  effort: a failure is logged and never fails the run.
- **One last-run record per operation.** `git:activity:last:{repository_id}:{operation}` keeps the
  most recent finished run of each operation for 30 days, so a periodic sync that imports nothing
  does not hide the result of another operation. It lists only the branches the run changed or
  failed on, by Infrahub branch name, and the last outcome of a branch wins. The syncer
  reports collection and rewrite-record failures after its imports, so a branch whose commit was
  imported but whose rewrite record failed is reported as failed. A run that fails before any branch
  outcome, for example on a fetch that cannot reach the remote, is recorded with no branches. A run
  whose work another run records calls `keep_last_run`, and the earlier last run stays in place.
- **Which flows write them.** The periodic sync writes one `sync` run per repository, created in
  `sync_remote_repository`. It covers the clone and default-branch import of the bootstrap and the
  syncer run in the `sync-git-repo-with-origin` subflow. Adding a read-write repository writes an
  `add` run. The syncer, `import_branch` and `RepositoryAdder.add` take the run as a required
  `activity` argument and report their phases and branch outcomes through it.
- **The flows outside the syncer record their own run.** Each one targets a single Infrahub branch.
  It records the branch as imported once the import, the push or the merge succeeds, so a broadcast
  that fails afterwards does not turn it into a failure, and as failed when the work before that
  raises. A cancelled run lists no branch, and every finished run except a last-commit import that
  imports nothing replaces the last run of its operation:
  - `git-repository-import-object` writes a `reimport` run: `building` while the plan is built, then
    `applying` once the repository lock is held. It has no `fetching` phase.
  - `git-read-only-repository-import-last-commit` writes a `reimport` run: `fetching` once the lock
    is held, then `building` and `applying` when it imports the objects of the commit. When the local
    ref already points at the commit, only the commit is written and the run keeps the earlier
    `reimport` last run, so it does not hide a failed import; the pull that the write submits imports
    the objects. The local branch of a ref never moves, so once
    the remote has moved past the commit the clone was created at, a branch ref is imported on every
    run, while a fetch can move a tag. The run ends when the commit
    is written, and that write submits the pull, which writes its own `pull` run.
  - `git-repository-pull-read-only` writes a `pull` run and `git-repository-add-read-only` an `add`
    run: `fetching` once the lock is held, then `building` and `applying` for each import. Adding an
    active repository sets `fetching` again before it resolves the tracked ref.
  - The task `git-branch-create` writes a `branch_create` run per repository, with no phase. A
    branch that already existed in git lists no branch, and a repository skipped because it cannot
    be read lists the branch as failed.
  - `git-repository-merge` writes a `merge` run on the destination branch, with no phase. A
    read-write repository delivers the merge through its push queue, so the run lists the branch as
    imported only when the delivery pushed, and as failed when the delivery fails or the merge was
    lost before it was queued. A delivery that pushes nothing, and a read-only repository whose
    destination already holds the source ref and commit, list no branch.
- **Read-only imports report their steps from inside the import.** `import_objects_from_files` takes
  the run id, like the sync subflow, and sets `building` and `applying` itself, because the read-only
  flows build and apply in that single subflow. `sync_from_remote` and `update_latest_commit` pass
  the run on to it. Without a run id nothing is reported.
- **The subflow receives the run id, not the run.** Subflow parameters are stored with the run, so
  the subflow looks the run up by id in `ACTIVE_RUNS`, a per-process table in
  `git/activity/factory.py`. The parent flow and the subflow therefore share one run object, and its
  write lock keeps a renewal from writing back an older phase after a newer one.
- **The repository lock is not part of the record.** In the syncer runs and the
  `git-repository-import-object` run, the lock is held for one phase at a time, never for a whole
  run, and the build phase runs without it. The read-only add, pull and last-commit import runs hold
  it through every phase. The `branch_create` run holds it while it creates and pushes the branch,
  records its commit and broadcasts it, and the delivery of a `merge` run while it replays, pushes,
  records and broadcasts. The
  query reports the lock holder separately, from the lock token (`{timestamp}::{worker_id}`). The
  token is written before the worker waits for the lock, so its time is when the worker asked for
  the lock (`requested_at`). Many flows take the lock without importing anything, so a held lock
  does not mean that a run is active. The lock key uses the repository name, so a repository
  renamed while a flow holds the lock does not report that lock.
- **Reading the records.** The resolver lists the run keys with `list_keys`, which scans the whole
  Redis keyspace, and returns early when it finds none, which saves a second round trip for an idle
  repository. A record that expires between the listing and the read is skipped. The six last-run keys are known,
  so they are read directly. The cache reads ignore the time-travel date. Branch names are mapped to
  existing branches and filtered by the caller's view permission.

## Import failures

A branch import is built by `build_import_plan` and applied by `apply_import_plan`. Each runs inside
the same boundary, `_import_failure_boundary` on the integrator; the apply step does not run when the
build step fails, so a failure is handled once. Every import goes through these two
methods: the add and sync flows, the scheduled sync of a new clone, the import-objects flow, and the
read-only flows through `import_objects_from_files`.

- **What the boundary does.** On any failure it sets the branch to `ERROR_IMPORT`, logs the failure
  once to the flow run's log, and raises `RepositoryImportError`
  (`backend/infrahub/git/import_errors.py`). `RepositoryConnectionError` and
  `RepositoryCredentialsError` also set the branch being imported to `ERROR_IMPORT`, but they are not
  logged or converted: they pass through unchanged and still stop the repository's sync.
  A failed `ERROR_IMPORT` write is logged and does not replace the import failure. The boundary
  ends after the last import step: setting the branch to `IN_SYNC` and sending `CommitUpdatedEvent`
  run outside it, so their failure cannot mark a fully imported branch as `ERROR_IMPORT`.
- **Expected and unrecognised failures.** `describe_import_error` is the single function that maps an
  exception to a readable message. A failure it recognises is logged at error level without a
  traceback. A failure it does not recognise is logged once with its traceback, which is the signal
  that the function needs a new entry. Both become `RepositoryImportError`. To make a new error
  type expected, add a `case` to that function and nothing else. The SDK `Error` base class is
  deliberately not mapped, because it also covers connection errors.
- **One error entry per failure.** The error entry carries `repository`, `branch`, `step` (`import`)
  and `reason` as log record fields for log shippers and alert rules. `raise_if_branches_failed`
  logs its warning with the same fields only for branches that failed before the import (step
  `collection`), so each failure appears once in the task log as an entry with these fields.
- **Summary of the import steps.** After the error entry, and before the branch is set to
  `ERROR_IMPORT`, the boundary logs a warning without these fields that names the import step that was running, the steps that ran before it and the steps
  that did not run, in the order of `ImportSummaryStep` in `backend/infrahub/git/integrator.py`.
  A step with nothing to import is still listed as completed. When the build step fails, the
  warning states that no import step ran. Connection and credential errors, and failures outside
  the boundary, are logged without this warning.
- **Naming the `.infrahub.yml` entry.** The mapping function only receives the exception, so the
  loops over `.infrahub.yml` entries, in the build and in the apply step, wrap their body in
  `import_entry(label)`. That context manager adds the entry's name and file as an exception note,
  and the message is prefixed with the notes, for example
  `GraphQL query 'backbone_service' (queries/backbone.gql): Violates uniqueness constraint 'name'`.
  A schema entry is labelled `Schema '<path>'` only when the path does not exist or names a
  directory without a schema file; errors in a schema file's content have no label, because they
  already name the file. The build
  loops that import Python modules (checks, Python transforms, generators) also pass the worktree
  directory to `import_entry`, so a syntax error names its file relative to the repository root.
  The file can be a helper module, not the entry's own file.
  Do not log inside an import step and then re-raise: the boundary logs, and a second entry
  duplicates the failure.
- **No Prefect traceback.** The import steps are plain methods, not `@task`s. An exception leaving a
  task is logged by Prefect with its traceback before the boundary can convert it. When
  `RepositoryImportError` or `RepositoryBranchesFailedError` leaves a flow, Prefect also writes a
  record with the traceback. Both types are registered with `@suppress_traceback_in_logs`, so the
  filter on the Prefect run loggers drops that record (see [Webhooks](webhooks.md) for the
  mechanism). The filter matches the exact type, so each class is registered on its own. Prefect's
  `Finished in state Failed(...)` entry has no traceback and stays.
- **A failure stays on its branch.** Containment does not rely on the boundary converting every
  failure. `import_branch` (`backend/infrahub/git/sync.py`) builds and applies one branch under the
  repository lock and returns any failure instead of raising it, including one raised outside the
  boundary such as a lock error, which it logs once with its traceback. Only
  `RepositoryConnectionError` and `RepositoryCredentialsError` are re-raised, so only the branch
  being imported is set to `ERROR_IMPORT`: recording them on every remaining branch would leave
  those statuses in place until a new commit or a manual re-import. `RepositorySyncer.sync` records
  a failed branch and continues with the next one. `RepositoryAdder.add` returns a failed
  default-branch import. For an active repository, `add_git_repository` still syncs the other
  branches and sends `RefreshGitFetch` before it fails with that error; for a repository that is
  not active, it syncs no other branch and fails with that error at once.
  `bootstrap_local_repository` returns the repository when the default-branch import fails, so the
  scheduled sync continues with its other branches; it returns `None` when the clone fails or when
  that import raises a connection or credential error.
- **Calling an import step directly.** The steps write to the run logger, which Prefect provides only
  inside a flow or task run. A test that calls one directly wraps the call in a flow
  (`tests/helpers/flow.py::call_in_flow`).

## Git error surfacing

`git merge` writes conflict output to **stdout**, not stderr. GitPython's `GitCommandError.stderr`
is therefore empty on a merge conflict, and the `RepositoryError` raised from the merge path
carries only its default message. Keep that in mind when asserting on error messages
(`pytest.raises(match=...)`) or when tempted to include `exc.stderr` in user-facing output for
merge failures.
