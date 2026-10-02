# Research: Git remote writeback failure handling

**Feature**: `dev/specs/ifc-3220-writeback-failure-handling`
**Date**: 2026-10-02, revised after [critiques/critique-20261002-1500.md](critiques/critique-20261002-1500.md)

Each section states a decision, the reason for it, and the alternatives that were rejected. Code
locations are cited as `module::symbol`. Line numbers are left out on purpose, because they move
before the plan merges.

---

## R0. Current behaviour, confirmed on `develop`

The branch is `origin/develop` at `04edcdd3f`. PR #10465 is in as `7d1bab3d1`, and PR #10542
(IFC-3105) is in as `807b58e3f`.

### The merge path

| Step | Where | What it does |
|---|---|---|
| 1 | `core/merge/orchestrator.py::BranchMergeOrchestrator.merge` | After `MERGED` and after the write block is lifted, calls `run_follow_ups`, then `dispatch_events`. |
| 2 | `core/merge/post_merge.py::PostMergeDispatcher.run_follow_ups` | Submits, in order: the repository merges, IPAM reconciliation, proposed-change cancellation, `BRANCH_DELETE` when `main.delete_branch_after_merge` is set, and `BRANCH_MERGE_POST_PROCESS`. Every submission is fire-and-forget (`run_deployment(..., timeout=0)`). One `log_exception_guard` wraps the whole `merge_repositories()` call. |
| 3 | `core/merge/repository_merge_dispatcher.py::RepositoryMergeDispatcher.merge_core_repositories` | Loops over every `CoreRepository` of the source branch that exists on main and is not `INACTIVE`. Submits one `GIT_REPOSITORIES_MERGE` when the branch syncs with Git or the repository is `STAGING`. No `context` is passed. |
| 4 | `git/tasks.py::merge_git_repository` | No retries. Takes the repository lock, calls `InfrahubRepository.merge`, ignores its return value, then sends `RefreshGitFetch`. A raise skips the broadcast and fails the run. The staging path records the commit and pushes nothing. |
| 5 | `git/repository.py::InfrahubRepository.merge` | Merge into the destination worktree, then push, then `create_commit_worktree`, then `update_commit_value`. A failed push or a failed record resets the worktree to the pre-merge commit. Without an origin, it merges and records with no push. |
| 6 | `core/merge/post_merge.py::PostMergeDispatcher.dispatch_events` | Runs the coalesced recompute through `MergeRecomputeCoordinator`, inside the `branch-merge` flow. A schema-changing merge also sends `SchemaUpdatedEvent`, which starts `computed_attribute/tasks.py::computed_attribute_setup_python`. |
| 7 | `core/branch/tasks.py::post_process_branch_merge` | Runs `PostMergeRegenerationDispatcher.dispatch` for generators and artifacts. |

A merge always targets Infrahub's default branch. `InfrahubRepository.rebase` has no caller, so no
other branch ever receives a writeback.

### The push

- `InfrahubRepository.push` sends `HEAD:refs/heads/<mapped branch>`, with no time bound. Neither
  `workers/infrahub_async.py::set_git_global_config` nor `push` sets a Git timeout.
- A transport failure raises `GitCommandError`, which `_raise_enriched_error_static` turns into
  `RepositoryConnectionError`, `RepositoryCredentialsError`, `RepositoryPermissionError` or a plain
  `RepositoryError`. `is_write_operation=True` is passed, so a 403 maps to the permission error.
  "Repository not found" maps to `RepositoryConnectionError`, although GitHub sends it for a private
  repository that the token cannot see.
- A per-ref rejection raises a plain `RepositoryError`. Only the wording of
  `git/repository.py::_describe_push_rejection` tells a policy denial from a non-fast-forward.
  GitPython already sets `PushInfo.REMOTE_REJECTED` for "[remote rejected]" and `PushInfo.REJECTED`
  for "[rejected]".
- A push failure never writes `operational_status`. Two tests pin that, and this work keeps it.
- Nothing captures the remote's own `remote:` lines. A GitHub branch-protection refusal explains
  itself only in those lines.
- Two operational-status maps look the exception type up exactly: `git/base.py::_raise_enriched_error`
  and `message_bus/operations/git/repository.py::connectivity`.

### The import

- `git/integrator.py::InfrahubRepositoryIntegrator.import_objects_from_files` deletes the queries,
  transforms, checks, generator definitions and objects that the imported commit lacks.
- `_apply_artifact_definitions` creates and updates artifact definitions. It never deletes one.
  `import_schema_files` never removes schema.
- A transform delete can be refused when an artifact definition still needs it, because
  `transformation` is mandatory on the artifact definition.
- The import writes through the SDK. `graphql/mutations/artifact_definition.py` then submits
  `REQUEST_ARTIFACT_DEFINITION_GENERATE` at once, which reads `repository.commit.value` when it runs.
- The synchronisation records first and imports second: `InfrahubRepositoryBase.pull` calls
  `update_commit_value` before `collect_pending_imports` hands the branch to the importer.
- Three paths import the default branch: the synchronisation (`collect_pending_imports`), the seed
  import after a fresh clone (`git/tasks.py::bootstrap_local_repository`), and the reimport of the
  current commit (`graphql/mutations/repository.py::ProcessRepository`).

### Regeneration

- The selective dispatcher and the blanket triggers read the repository commit from the graph when
  each per-definition flow runs (`generators/tasks.py`, `git/tasks.py::generate_artifact`).
- `RequestGeneratorDefinitionRun` carries the owning repository as
  `generator_definition.repository_id`. `RequestArtifactDefinitionGenerate` carries **no**
  repository. The PRD says that requests "already ... carry their owning repository". That is true
  for generators only. See R9.
- The coalesced Python pass knows the owning repository at gather time
  (`computed_attribute/gather.py`), and `core/merge/python_target_sources.py::GatheredPythonReadSets`
  drops it.
- Two dispatch points that the first draft missed: `_submit_full_terminal_regeneration` in the
  dispatcher, and `computed_attribute_setup_python` after a schema-changing merge.
- Nothing holds or defers regeneration today.

### Branches

- `core/branch/delete_coordinator.py` submits `GIT_REPOSITORIES_DELETE_BRANCH` when
  `git.delete_git_branch_after_merge` is set and the branch syncs with Git.
- `git/tasks.py::git_branch_delete` deletes the remote branch, gated only on `origin_has_branch`,
  then sends `RefreshGitRepositoryBranchDeleted`, which removes the local branch on every worker.
- Nothing orders that deletion after the repository merge, so it races the push on the success path
  too.
- `git/base.py::get_filtered_remote_branches` returns **every** remote branch when
  `git.import_sync_branch_names` is empty, which is the default. A remote branch with no Infrahub
  branch is therefore imported as a new Infrahub branch at the next synchronisation.
- `git/tasks.py::git_branch_create` never writes `commit` on the new branch. A branch that never
  recorded its own commit reads the default branch's value at `branched_from`.

### No ancestry helper

No code in `backend/infrahub/git/` tests ancestry. The sibling epic IFC-3210 adds one in
`git/divergence/gateway.py`. This work needs the same question. See R4 and R19.

---

## R1. Where the delivery state lives

**Decision**: branch-local (`BranchSupportType.LOCAL`) attributes on `CoreRepository`, declared
`read_only=True` and `optional=True`, written and read on Infrahub's default branch only. The list
is in [data-model.md](data-model.md).

**Why `LOCAL`.** A LOCAL attribute never reaches a branch diff and never produces a merge conflict:
the diff query selects only `aware` and `agnostic` branch support, and the bulk merge touches only
`aware`. This satisfies FR-019 by declaration. A branch-safety test still asserts it, because the
constitution requires merge behaviour to be tested and not assumed.

**Why not `AGNOSTIC`.** An agnostic attribute is one value for every branch, which would fit a state
that lives on one branch. But agnostic values reach the diff, forced to `UPDATED`, as
`dev/knowledge/backend/git-integration.md` records. That breaks FR-019.

**Why `read_only=True`.** `graphql/manager.py` leaves read-only attributes out of the generated
create, update and upsert input types. The generic `CoreRepositoryUpdate` then cannot clear the
queue, which is the second half of FR-009. The system writes through the core node API, which does
not consult `read_only`.

**Why `CoreRepository` and not the generic.** A read-only repository never delivers. The PRD names
"CoreRepository / CoreGenericRepository" and leaves the choice open.

**Why the default branch only.** Every merge targets Infrahub's default branch (R0). The default
branch has no origin branch, so a read there never falls back to another branch.

### The read-inheritance consequence (FR-025)

`core/attribute.py::BaseAttribute.get_create_data` creates the attribute vertex of a LOCAL attribute
on an agnostic node on the global branch, and value edges are written on the branch of the write.
A read on branch B resolves B, then B's origin branch up to `branched_from`, then global. A branch
created while main has a pending delivery therefore reads main's delivery state as it was at the
fork, until B is rebased.

**Decision**: nothing in the backend reads the state on another branch. The store reads and writes
the default branch, whatever branch the caller runs on. The frontend keeps the eight attributes out
of every generic surface of `CoreRepository`: the main attribute list, the "extra" toggle of the
details page, and the column picker of the list view. It renders them only in a section of their
own that always queries the default branch (R14). Each attribute's description says that only the
default branch holds the live value.

**Rejected**: clearing the state when a branch is created. It adds a write to every branch creation
on a path unrelated to Git, and the sibling rejected the same idea for the same reason.

---

## R2. How the state is written, and the two locks

**Decision**: one Repository-pattern class, `WritebackIntentStore`, is the only read and write path.
It takes `db`, the lock registry and the default branch in its constructor. It writes through the
core node API (`NodeManager.get_one` on the default branch, then `node.save(db=..., fields=[...])`),
never through the SDK. The service, the abandoner and the barrier depend on a `DeliveryStatePort`
`Protocol` that the store implements, so their unit tests use an in-memory store.

**Why the core node API.** Node mutation events are produced by the GraphQL mutation layer
(`graphql/mutations/main.py` calls `events/generator.py::generate_node_mutation_events`). A core
`node.save` emits none. A bookkeeping write therefore starts no automation, which is FR-026 and the
intent of the PRD note on ADR 0016. The sibling epic writes through the SDK and accepts a `live`
event per rewrite, because a rewrite is rare. A delivery-state write happens on every git-synced
merge, so the same trade-off does not hold here.

**Who the write names.** `Node.save` defaults `user_id` to the system user. The abandonment save
passes the acting account's id, so the edge metadata names the user. Every other save names the
system, which performed it.

Every place that writes has database access: the merge flow, `post_process_branch_merge`, the
computed-attribute flows, and the git task workers (`git/tasks.py` already calls `get_database()`).

**Why one class.** FR-009 says no path may clear a pending delivery without a record. That rule can
only be enforced in one place. Each method of the store is one state transition, and the record and
the clear are one `save`.

### The locks

Two locks, always taken in this order:

| Lock | Name | Held by | Held for | Time to live |
|---|---|---|---|---|
| Repository lock (exists) | `lock.registry.get(name=<repository name>, namespace="repository")` | The Git part of a delivery attempt, and the removal step of an abandonment. | The Git work. Never across a release, never across a retry delay. | none, as today |
| Delivery-state lock (new) | `lock.registry.get(name=<repository id>, namespace="repository-delivery")` | Every store transition. | One read-modify-write. | 30 seconds, acquire bounded to 10 seconds |

**Why a second lock.** The enqueue runs in the merge flow, and the barrier runs in the merge flow
(`dispatch_events`), in `post_process_branch_merge` and in the computed-attribute flows. Taking the
repository lock there would make a branch merge wait behind a periodic sync or a running delivery.
The state lock is held for one read and one write.

**Why the state lock has a time to live.** It is taken inside the merge flow. A worker that died in
the middle of a transition would otherwise hold it for ever, and every later merge of that
repository would hang in its follow-ups. A transition is one read and one save, far under 30
seconds. When the acquire times out, the caller acts as when the store raises (R3, R9).

**Why the state lock is not optional.** Without it, this interleaving drops held work: the barrier
reads a non-empty queue; the delivery clears the queue and finds no held set; the barrier then
writes its held set, which nobody will release.

**Rejected**: a compare-and-set query in Cypher. It is more code than a lock and it is not a pattern
this codebase uses for node attributes.

---

## R3. The queue entry, and when it is written

**Decision**: `RepositoryMergeDispatcher.merge_core_repositories` writes the entry before it submits
`GIT_REPOSITORIES_MERGE`, and passes it in `GitRepositoryMerge.pending_merge`. Each repository's
enqueue is guarded on its own: a failed enqueue is logged, and the merge is still submitted with
`pending_merge` set. The flow writes the same entry again, idempotently, before its first attempt.

**Which merges are queued** (FR-005): only a repository whose internal status on the source branch
is `active`, that has a remote, on a source branch that syncs with Git, and whose source commit
carries repository content. A staging repository keeps today's path and is never queued. A
repository with no remote merges and records locally, as today.

**When a merge carries no repository content.** The dispatcher reads, for the source branch, the
`commit` value and the branch's `branched_from`, then reads the default branch's `commit` at that
time. It skips the enqueue when the source branch has no value, when its value equals the default
branch's value at `branched_from`, or when it equals the commit recorded now. A branch that never
recorded its own commit reads exactly the default branch's value at `branched_from`, so the second
test catches every data-only branch, including one forked before the trunk moved.

**What the entry holds**:

| Field | Source |
|---|---|
| `entry_id` | A new UUID. |
| `source_branch` | The Infrahub source branch name. |
| `source_git_branch` | The remote branch, through `_get_mapped_remote_branch`. |
| `source_commit` | `CoreRepository.commit` read on the **source** branch, which is what Infrahub imported and merged. |
| `merged_at` | The merge time. |
| `delete_source_git_branch` | `False`. The branch-deletion guard sets it (R12). |

**Why the graph commit and not the worktree head.** The graph merge merged the objects imported at
that commit. Delivering exactly that commit keeps the remote content and the merged data aligned.

**Why the first write is in the merge flow** (FR-005a). The coalesced recompute runs in
`dispatch_events` right after `run_follow_ups`, and `post_process_branch_merge` is submitted at the
end of `run_follow_ups`. Both consult the barrier. An entry written by the delivery flow would arrive
after them.

**Why the flow writes it again, and why that is safe** (FR-005b). The flow's write repairs a failed
first write. It must not resurrect an abandoned entry: a merge flow can wait in the Prefect queue
while a user abandons. The queue keeps the last 256 removed entry ids, and `enqueue` refuses an id
that is present or recently removed. A run queued by the previous code carries no `pending_merge`.
The flow then builds the entry itself from the source branch's graph commit, as the dispatcher would.

**Rejected**: keying the queue on the Infrahub branch. The Infrahub branch can be deleted right
after the merge (`delete_branch_after_merge`), while the remote branch is protected by FR-011.

---

## R4. The delivery attempt

**Decision**: one component, `RepositoryWritebackService`, built per repository at the top of each
flow, with one entry point, `deliver(final_attempt)`. The merge flow, the retry flow and the
recovery check (R20) all call it (FR-007).

### The algorithm

Under the repository lock:

1. **Snapshot.** Under the state lock, take a snapshot of the queue and of the held set, and stamp
   `attempt_started_at` and `last_progress_at`. If the queue is empty, no import is owed and the held
   set is empty, return. If only held work remains, go to step 14.
2. **Fetch**, bounded in time (R6). Let **H** be the remote head of the destination, and **R** the
   commit recorded for the destination.
3. **Destination check** (FR-022). If R is neither H nor an ancestor of H, the destination was
   rewritten. Mark the queue unreplayable with the cause `destination-rewritten`. Push nothing. A
   worker that does not hold R locally treats it as rewritten, which is the safe reading.
4. **Observation** (FR-012). Drop from the replay every entry whose source commit is H or an
   ancestor of H. The remote already holds it.
5. **Source check** (FR-020). For each remaining entry, the source commit must be the remote head of
   its source branch or an ancestor of it. If it is not, mark the queue unreplayable with the cause
   `source-discarded`. Push nothing. A missing remote branch fails the check too.
6. **Replay.** Reset the destination worktree to H. Merge each remaining source commit, in queue
   order, with the same `--no-ff` rule as today (`git.use_explicit_merge_commit`). On a conflict,
   abort, reset to the pre-attempt commit, and mark the queue unreplayable with the cause
   `replay-conflict`, naming the entry.
7. **Push** once, if any entry was replayed, bounded in time. On a failure, reset the worktree to
   the pre-attempt commit (FR-002) and classify the failure (R5).
8. Let **M** be the final head.
9. **Import obligation.** If H is not R, or an import is already owed, save
   `import_owed_commit = M` through the store. This save comes **before** the commit write: a crash
   between the two then leaves an obligation that the next attempt honours, never a recorded commit
   with nothing owed.
10. **Record.** Create the commit worktree of M and write the commit, through `update_commit_value`
    as today (FR-001). On a failure, reset the worktree behind the remote. The next attempt observes
    the delivery and records it.
11. **Import** at M on the default branch when an import is owed (FR-023). On success, clear the
    obligation. On a failure, classify it (R5) and stop: the obligation stays, the entries stay, and
    the held work stays held.
12. **Broadcast** `RefreshGitFetch` pinned to M, as `merge_git_repository` does today.
13. **Delete source branches.** For each delivered entry with `delete_source_git_branch` set, and
    that no remaining entry names, delete the remote branch and send
    `RefreshGitRepositoryBranchDeleted` (R12).

Then, outside the repository lock:

14. **Release** the held snapshot (R10).
15. **Clear.** Under the state lock: remove the snapshot's entries and add their ids to
    `removed_entry_ids`; remove the held items whose hold sequence is not above the snapshot's;
    set `delivery_last_delivered_commit` to M when something was pushed; set the status `none` if
    the queue is now empty, otherwise `pending`; clear the cause and the message when `none`.

**Why the record comes before the import.** The import writes artifact definitions through the SDK,
and each write submits a generation that reads the recorded commit. With the import first, those
generations would read R. The synchronisation already records first (R0).

**Why the release runs outside the repository lock.** The release awaits generator runs through
`_dispatch_plan`. A generator run calls `get_initialized_repo(commit=M)`, and
`git/integrator.py::initialize_local` takes the repository lock to fetch a missing commit on a worker
that has not heard the broadcast yet. Holding the lock across the release would deadlock. The
broadcast goes first so that most workers already hold M.

**What a second attempt between steps 13 and 15 does.** It takes the free repository lock, observes
every entry on the remote, records nothing new, and releases the held set again. Over-execution, the
accepted direction.

**Why the checks run before the replay.** A worker can hold a discarded commit in its object
database long after the remote dropped it. A replay that merges it and pushes would restore it. A
leaked credential is the case that matters (SC-007).

**Why the destination check refuses rather than rebases.** A source branch forked from the old trunk
contains the old trunk. Merging it onto the rewritten trunk restores every discarded trunk commit.
This is IFC-3210's FR-005b, and the sibling's merge path refuses for the same reason.

**Why the import happens only when owed.** When the remote did not move, M is R plus the merged
branches, and the graph already holds every object of M. An import would cost a full import for
nothing. When the remote moved, nothing else will import M: the synchronisation compares local and
remote Git, which then agree.

**A merge that lands during the import.** The import is desired-state, so it can delete the
repository objects of a merge that landed after the snapshot, because M does not hold that merge's
files. When the queue grew past the snapshot while the import ran, the service keeps the obligation,
and the next attempt, which delivers the new entry, imports its own head. The objects come back,
possibly with new ids. A synchronisation import racing a merge has the same exposure today. Closing
it would need merges to wait for imports, which FR-010 forbids.

**Rejected: storing the merge commit as a Git bundle.** The PRD measured and rejected it: it becomes
undeliverable as soon as the remote destination advances, and delivering it then needs a
force-push.

### The Git primitives

All new Git calls sit behind a port, `DeliveryGitPort`, so that the service is unit-testable without
Git (PRD testing decisions). The concrete adapter wraps one `InfrahubRepository`.

| Port method | Built on |
|---|---|
| `fetch()` | `InfrahubRepositoryBase.fetch`, with `kill_after_timeout`. |
| `remote_head(git_branch)` | `get_commit_value(branch_name=..., remote=True)` |
| `is_ancestor(ancestor, descendant)` | `git merge-base --is-ancestor`. Exit 1 means no. A missing object means no. Any other failure raises. Shared with IFC-3210 (R19). |
| `replay(base, commits)` | `reset --hard`, then `merge` per commit, aborting on a conflict. |
| `push()` | `InfrahubRepository.push`, extended by R5, with `kill_after_timeout`. |
| `reset(commit)` | `_reset_to_pre_merge_commit`, which never raises. |
| `record(commit)` | `create_commit_worktree` plus `update_commit_value`. |
| `import_at(commit)` | `import_objects_from_files` on the default branch. |
| `broadcast(commit)` | `RefreshGitFetch`, as in `merge_git_repository`. |
| `delete_remote_branch(git_branch)` | `delete_remote_branch` plus `RefreshGitRepositoryBranchDeleted`. |

---

## R5. Classifying a failure, and keeping the remote's words

**Decision**: a pure function, `classify_delivery_failure(error, stage) -> DeliveryFailure`, in
`git/writeback/classifier.py`. `stage` is one of `push`, `record`, `import`. It reads the exception
type first. Per-ref push rejections get a typed error whose reason comes from GitPython's
`PushInfo` flags, not from text.

| Stage | Exception | Cause | Retried automatically |
|---|---|---|---|
| push | `RepositoryConnectionError` (unreachable, timeout, 5xx) | `remote-unreachable` | yes |
| push | `RepositoryNotFoundError` (new subtype) | `not-found` | no |
| push | `RepositoryTLSError` (new subtype) | `certificate` | no |
| push | `RepositoryCredentialsError` | `credentials` | no |
| push | `RepositoryPermissionError` | `permission` | no |
| push | `RepositoryPushRejectedError`, reason `policy` (`REMOTE_REJECTED`) | `permission` | no |
| push | `RepositoryPushRejectedError`, reason `non-fast-forward` (`REJECTED`) | `remote-advanced` | yes. The remote moved between the fetch and the push, and the next attempt fetches again. |
| push | `RepositoryPushRejectedError`, reason `unknown` | `unclassified` | no |
| record | any | `record-failed` | yes. The remote has the content (FR-004). |
| import | `DatabaseError`, `RepositoryConnectionError`, a GraphQL transport error | `import-failed` | yes |
| import | any other, for example a configuration or validation error of the content | `import-failed` | no |
| replay | a merge conflict | `replay-conflict` | no |
| any | anything else | `unclassified` | no |

The cause list is closed and is an enum (Principle III). [data-model.md](data-model.md) has it.

**Why the flags.** A GitHub ruleset reply, "(push declined due to repository rule violations)",
matches no marker of `_describe_push_rejection`, so a text match would call it `unclassified`. The
flags classify it as `REMOTE_REJECTED`. `RepositoryPushRejectedError` subclasses `RepositoryError`,
so every existing `except RepositoryError` keeps working, and its message keeps today's wording,
which `test_git_live_remote.py` asserts.

**Why two new subtypes.** A certificate failure and "Repository not found" are
`RepositoryConnectionError` today, told apart only by their message. Retrying either is pointless.
`RepositoryTLSError` and `RepositoryNotFoundError` subclass `RepositoryConnectionError`. Both
operational-status maps (R0) move from an exact-type lookup to an `isinstance` lookup, most specific
first, so both subtypes keep `ERROR_CONNECTION`.

### The remote's own message (FR-018)

GitPython's `Remote.push` accepts a `progress` handler. `git/util.py::RemoteProgress` keeps every
stderr line that is not a progress line in `other_lines`, and lines that start with `error:` or
`fatal:` in `error_lines`. A server-side message arrives as `remote: ...` lines, which land in
`other_lines`. Both examples below match no progress pattern:

- Gogs pre-receive hook: `remote: branch main is protected`
- GitHub protection: `remote: error: GH006: Protected branch update failed for refs/heads/main.`

**Decision**: `push` passes a `RemoteProgress` and joins the `remote:` lines, in order, into the
typed error. The delivery stores, verbatim, those lines and the ref summary. For any other error it
stores the typed message, never raw stderr, which can name worker paths. Every stored message passes
through one scrubber that removes `user:password@` from URLs, since a location can embed a token
(Constitution VI).

**Rejected**: paraphrasing the remote. User story 3 of the PRD asks for the remote's own words.

---

## R6. The automatic retry, and bounded Git commands

**Decision**: the delivery attempt is a Prefect `@task` with `retries=3`,
`retry_delay_seconds=[30, 120, 300]` and a `retry_condition_fn` that retries only a failure
classified as automatically retryable (R5). The task reads its attempt number from
`task_run.run_count` and passes `final_attempt` to `deliver`, which records `action-required` only on
the final attempt. Tests override the delays with `with_options(retry_delay_seconds=...)`.

**Why a task.** Prefect 3.8 supports `retry_condition_fn` on tasks only, not on flows.

**Why these bounds.** About seven and a half minutes cover a blip, a load-balancer failover or a Git
server restart. The PRD assumes that real outages last days, so a longer automatic window buys
nothing and holds a worker slot.

**Bounded Git commands.** The adapter passes `kill_after_timeout` to the fetch (120 seconds) and the
push (300 seconds). A remote that accepts the connection and never answers then fails as
`remote-unreachable` instead of holding the repository lock for ever. The bounds live in
`git/writeback/constants.py`.

**One retry chain per repository.** Before it waits, a retryable failure stores `retry_due_at`. A
merge flow whose first attempt finds a retry already due in the future returns at once: that chain
snapshots the queue at its next attempt and delivers the new entry too. A manual retry never
returns early, because a user asked for it now. A chain that wakes after a manual retry delivered
finds nothing and does nothing.

**Status while waiting**: `pending`, with the last cause and message, so a user sees "pending, last
attempt failed: remote unreachable".

**Rejected: retrying from the periodic synchronisation.** That is an unbounded automatic retry,
which FR-004 forbids. The recovery check of R20 restarts a **lost** attempt only.

---

## R7. The retry and abandon mutations

**Decision**: two new mutations, `InfrahubRepositoryDeliveryRetry` and
`InfrahubRepositoryDeliveryAbandon`, registered by hand in `graphql/schema.py` beside
`InfrahubRepositoryProcess`. Both are thin. They check permissions, check that the action is
available, submit a workflow and return its task, as `ProcessRepository` does. The contract is in
[contracts/repository_delivery.graphql](contracts/repository_delivery.graphql).

### Authorization

A custom mutation name is invisible to the kind-based permission checkers: `graphql/analyzer.py`
skips a root field that is not a schema kind. Each mutation must therefore check permissions
itself. `DefaultBranchPermissionChecker` acts only when the request names the default branch, and
the two mutations act on the default branch whatever branch the request names.

**Decision**: both mutations refuse a request sent on any branch other than the default branch. Then
they check, explicitly:

- object `update` on `CoreRepository`, with `ALLOW_DEFAULT`;
- the global `manage_repositories` permission, which `RepositoryManagerPermissionChecker` requires
  for a repository CRUD mutation and which the frontend reports as `permission.update`;
- the global `edit_default_branch` permission.

**Why all three.** A retry records a commit on the default branch, and an abandonment changes what
the default branch will regenerate. The user needs exactly what editing the repository on the
default branch needs. The UI gating reads `manage_repositories`, and the backend then agrees with it.

**Governance sign-off.** The delivery uses the repository's stored credential, not the acting
user's. A permitted user can therefore cause a push that the user could not personally make. A
proposed-change merge already has that property. A user who merges through a proposed change can
lack all three permissions, so the retry persona is the operator who manages repositories, not the
author of the merge. Whether a retry should need less than an abandonment is an open governance
question, recorded in the plan.

### Availability

The mutations read the state before they submit. The table "Actions by status" in
[data-model.md](data-model.md) is the full rule. They refuse with a `ValidationError` when:

- nothing is pending (both);
- an attempt is running and is not stale (retry);
- the queue version named by an abandonment differs from the current one (abandon);
- the repository is read-only or `STAGING` (both).

The workflows check again under the locks, because the state can change between the mutation and
the run. This mirrors ADR 0014, where the mutations "re-check availability at execution time to
reject a stale action".

**Why the abandonment is a workflow too.** It must not interleave with a running attempt, so it
takes the repository lock, which a worker flow already holds in the same way.

**Rejected: ADR 0014's generic task actions.** Those act on a task run. Here the subject is the
repository's queue, which outlives every task run, so the action belongs on the repository.

---

## R8. The abandonment

**Decision**: `WritebackAbandoner.abandon(queue_version, actor)`, run by the flow
`git-repository-delivery-abandon`. It changes no Git state and imports nothing.

1. Under the repository lock and the state lock, in one transition: refuse when the version differs
   or nothing is pending; otherwise remove every entry, add their ids to `removed_entry_ids`, clear
   any owed import, and write the abandonment record with the actor, the time, the version, the
   recorded commit and the owed import. The save passes the actor's account id as `user_id`. The
   held set stays.
2. Leave both locks. Release the held snapshot (R10).
3. Under the state lock, remove the held items whose hold sequence is not above the snapshot's.

**Why step 1 removes the entries before the release.** With the entries still queued, a delivery
attempt could start between the release and the clear and push the merges the user is abandoning.
After step 1, the queue is empty and no attempt can deliver them.

**What a crash between step 1 and step 3 leaves.** An empty queue with a held set: a release is
owed. The recovery check of R20 starts a delivery flow, which finds only held work and releases it.
That is invariant 2 of the data model, in its revised form.

**What the abandonment does not do.** It never touches the remote, never deletes a remote branch,
and never re-imports. The repository section then says that the default branch can hold repository
objects that the recorded commit lacks, and offers "Reimport current commit" (FR-024).

**Rejected: a re-import at the recorded commit inside the abandonment.** Three reasons. The import
never deletes artifact definitions, so it cannot do what that design promised. It can refuse to
delete a transform that an artifact definition needs, so the only exit could fail. And it races
with merges that land meanwhile, deleting their objects.

**Why the record is one attribute and not a log.** The temporal history of the node keeps every
earlier value of the attribute, and the edge metadata names the user. One value answers the common
question, "what was dropped last, and by whom". A full log would need its own retention and its own
permission model.

**Rejected: an event for every abandonment.** It would need a new `EventType`, which changes the
webhook enums in the GraphQL schema, for a rare act whose record already lives on the repository.

---

## R9. The regeneration barrier

**Decision**: one component, `RegenerationBarrier`, in `core/merge/regeneration_barrier.py`, with
one entry point:

```text
admit(branch, candidates: list[OwnedRegeneration], releasing: str | None) -> list[OwnedRegeneration]
```

It returns the candidates to dispatch now and holds the rest. A candidate pairs a held identifier
with the id of the repository that owns it, and the narrowed request to dispatch if admitted. On any
branch other than the default branch, or when no repository has a pending delivery, it returns
every candidate after one read.

### Consultation points

| Point | Candidates | Owner from |
|---|---|---|
| `PostMergeRegenerationDispatcher.dispatch`, on the plan, before `_dispatch_plan` | generator runs, artifact generations | `generator_definition.repository_id`; a new `RequestArtifactDefinitionGenerate.repository_id` |
| `PostMergeRegenerationDispatcher._submit`, after the generator cascade reselects artifacts | artifact generations | as above |
| `PostMergeRegenerationDispatcher._full_regeneration`, `_submit_full_terminal_regeneration`, and the flag-off path of `post_process_branch_merge` | "every definition of a repository" | see below |
| `core/merge/recompute_coalescing.py::_resolve_python_targets`, used by `MergeRecomputeCoordinator` and `RecomputeChainSubmitter` | Python computed attributes as `(kind, attribute)` | the owner map of the Python target source |
| `computed_attribute/tasks.py::computed_attribute_setup_python`, on the default branch | the `(kind, attribute)` pairs it selected | the same owner map |

### The artifact request gains its repository

`RequestArtifactDefinitionGenerate` gains `repository_id: str | None = None`.
`ArtifactSelector._build_request` fills it from `ProposedChangeArtifactDefinition.repository_id`,
which it already holds. The field is optional, so a run queued by the previous code still
validates.

### The Python owner map

`GatheredPythonReadSets` drops the repository of each transform. It keeps it instead, and the
Python target source exposes `owner_of(kind, attribute) -> str | None`. The barrier consults it
after `_resolve_python_targets`, so it filters both a resolved result and the widened failsafe.

When the owner of a target is unknown while some repository has a pending delivery, the barrier
holds the target under every pending repository. Each release then runs it, which over-executes and
never skips.

### The full-regeneration fallbacks

The blanket triggers take a branch and enumerate every definition. When a repository has a pending
delivery, the barrier:

1. holds a `widen` marker for that repository, which releases as a full regeneration of that
   repository's definitions (R10);
2. submits the blanket triggers with a new optional parameter, `exclude_repository_ids`, naming the
   pending repositories.

With no pending delivery, the triggers are submitted with no new parameter, byte for byte as today,
which keeps the promise of ADR 0012 that the flag-off path is the blanket path exactly.

`git/tasks.py::generate_artifact_definition` and `generators/tasks.py::run_generator_definition`
gain `exclude_repository_ids` and `include_repository_ids`, both `list[str] | None = None`. A
definition is skipped when its repository is excluded, or when an include list is given and its
repository is not in it.

### The atomic hold, with sequence numbers

The barrier holds a repository's candidates only after it confirms, under the state lock, that the
repository's queue is still non-empty. When the delivery cleared the queue in between, the
candidates are dispatched.

Each hold gets the next value of a per-repository sequence, and every held item keeps the sequence
of its latest hold. A release remembers the highest sequence of its snapshot, and its clear removes
only the items whose sequence is not above it. A definition held again while a release runs
therefore survives the clear (FR-015).

### When the store fails

If the store raises or the state lock cannot be acquired, the barrier admits every candidate and
logs at error level. Holding blindly could drop work that no release would ever cover, which is
under-execution, and ADR 0012 forbids it. Dispatching against the recorded commit is today's
behaviour.

### The narrowed selection, kept for a short time (FR-014, SC-008)

The coalesced recompute runs in `dispatch_events` right after `run_follow_ups`, a few milliseconds
after the first delivery attempt was submitted. A merge of a git-synced branch that carries
repository content will therefore nearly always see a non-empty queue. Holding identifiers only
would then turn every such merge's narrowed recompute into a whole-kind recompute.

**Decision**: at each hold, the barrier also writes the narrowed request of each candidate to the
cache, keyed by repository id and hold sequence, with a time to live of 15 minutes. The value is the
request model, serialised. A release reads it per item. Inside the time to live, it dispatches the
narrowed request, so the dispatch equals what the merge would have dispatched with no barrier. After
it, or when the read fails, or when the serialised request exceeds 512 KiB, it dispatches the
identifier with no narrowing.

**Why this keeps FR-014.** The persisted state still holds identifiers only. The cache entry dies
before a long recovery could read it, which is exactly FR-014's purpose: "a long recovery cannot
dispatch a stale target set".

**Why 15 minutes.** It covers the first attempt and every automatic retry (R6), plus a margin. A
merge whose delivery succeeds within the retry window regenerates as precisely as today.

**Rejected: waiting for the first attempt before the follow-ups.** It would delay every git-synced
merge by the Git round trip, and by minutes when the remote is down.

---

## R10. The release

**Decision**: the release runs at the end of a delivery (R4 step 14) or an abandonment (R8 step 2),
outside the repository lock, through a component, `HeldRegenerationReleaser`, behind a port of the
service. It dispatches first and clears second, by sequence.

| Held item | Released as |
|---|---|
| Artifact definition | The cached narrowed request if present, else `RequestArtifactDefinitionGenerate` with no `members` and no `limit`, through `_dispatch_plan`. |
| Generator definition | The cached narrowed request if present, else `RequestGeneratorDefinitionRun` with no `target_members`, through `_dispatch_plan`, so the generator-to-artifact cascade runs as on a merge. |
| Python `(kind, attribute)` | The cached narrowed submission if present, else `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` with `coalesced=True` and `widened=True`, as the coalesced pass submits a widened target, so the chain continues. |
| `widen` marker | Full regeneration of that repository's definitions: the blanket triggers with `include_repository_ids=[repository]`, plus every Python computed attribute whose transform that repository owns, over its whole kind. |

An identifier that no longer resolves, for example a deleted definition, turns the release into the
`widen` release of that repository (FR-016). The PRD names this as "a further named fallback
reason": `FullRegenerationReason.HELD_SET_UNRESOLVED` is added beside the four that exist.

**Every release dispatch passes through the barrier, with `releasing` set to the repository being
released.** Its own candidates are admitted, and a candidate owned by another repository that is
still pending is held under that repository.

**Why dispatch, then clear.** No step can be atomic across the graph and the orchestrator. Clearing
first and failing to dispatch drops the work (FR-016). Dispatching first and failing to clear
repeats it. The next clearing then releases again, which over-executes. That is the accepted
direction, and FR-015 and SC-004 state it.

**Why clear by sequence.** A merge can append an entry, and its follow-up can hold an identifier
again, while the release runs. A clear by value would drop the repeated hold.

**Why inline and not a separate workflow.** A separate release workflow whose submission fails
leaves a held set that nothing would release. The recovery check of R20 covers the crash cases of
the inline release.

---

## R11. No other path imports a pending destination

**Decision**: three paths change while the store reports a pending delivery for the repository.

| Path | Change |
|---|---|
| `InfrahubRepository.collect_pending_imports`, the active loop | Removes the repository's default branch from the branches to pull, and removes from the new branches every remote branch that a pending entry names as its source. Logs both once per cycle. `_collect_staging_imports` keeps the full list, because a staging repository is never queued. |
| `git/tasks.py::bootstrap_local_repository` | Skips the seed import of the default branch after a fresh clone, and logs it. The clone itself proceeds. |
| `graphql/mutations/repository.py::ProcessRepository` | Refuses on **every** branch, with a message that names the pending delivery. |

**Why the default branch.** The import is desired-state: it deletes the repository-owned objects
that are not in the imported commit. If the remote destination advanced during an outage, an import
of the remote head would delete the objects of the pending merges. They would come back at the
delivery, possibly with new ids. The delivery imports the remote commits itself (R4 step 11).

**Why the kept source branches.** R12 keeps a remote source branch whose Infrahub branch was
deleted. With `git.import_sync_branch_names` empty, which is the default, the synchronisation would
import it as a new Infrahub branch at the next cycle.

**Why the reimport refuses on every branch.** A branch forked during the outage holds the pending
merges' objects in its graph, but its Git branch was created from the local trunk head, which lacks
their files. A reimport on that branch deletes them there, and a later merge of the branch carries
the deletion to the default branch. A synchronisation import of such a branch has the same effect.
Blocking it would block every developer push during an outage, so it stays a known limitation,
documented (R16).

**Cost.** One store read per repository per synchronisation cycle, shared with the recovery check
of R20.

**Interaction with IFC-3210.** The sibling adds reconciliation in the same method. A rewrite of the
destination during an outage is then not reconciled until the queue clears. The delivery attempt
meanwhile refuses with `destination-rewritten` (R4 step 3), the user abandons, and the
reconciliation runs at the next cycle.

---

## R12. The branch-deletion guard (FR-011)

**Decision**: `git/tasks.py::git_branch_delete` asks the store whether any entry of the repository's
queue names the branch as `source_git_branch`. When one does, it:

1. sets `delete_source_git_branch` on every such entry, through the store;
2. skips the remote deletion and logs a warning that names the pending delivery;
3. does **not** send `RefreshGitRepositoryBranchDeleted`, so every worker keeps its local branch.

The delivery then deletes the remote branch once the entry is delivered (R4 step 13), when no other
entry names it. An abandonment keeps it: its content was not delivered, and the remote branch is
then the only place that holds it.

**Why the guard marks the entry.** The deletion was requested, so the user expects the branch to go.
The entry already names the branch, so no new persisted work is needed: the flag rides on the entry
and disappears with it. This re-opens, with the facts of the critique, the alternative that the
first draft rejected as "new persisted work".

**The success path.** `BRANCH_DELETE` and the first attempt are submitted together, so the guard
often refuses while the first attempt runs. The attempt then deletes the branch a few seconds later.
The end state is today's, without the race.

**After an abandonment.** No entry names the branch any more. With `git.import_sync_branch_names`
empty, the next synchronisation imports it as a new Infrahub branch. That gives the user the
undelivered content back as a branch. It is documented as intended behaviour.

---

## R13. The reverted-delivery record (FR-021)

**Decision**: the store keeps `delivery_last_delivered_commit`, set at each delivery that pushed.
When the IFC-3210 reconciliation classifies the default branch as a rewrite, it asks the store
whether the last delivered commit is an ancestor of the commit it discards and not an ancestor of
the new head. When it is, it writes `delivery_reverted` with the delivered commit, the new head and
the time, and logs it.

**Why the last delivered commit is enough.** Each delivery pushes a fast-forward of the previous
remote head, since Infrahub never force-pushes. Every earlier delivered commit is therefore an
ancestor of the last one, until a rewrite. If the last one survived a rewrite, every earlier one
did too.

**Gate.** This slice waits for the rewrite classification of IFC-3210. Without it, a rewrite of the
default branch makes the synchronisation fail, and nothing reaches the check.

**Not cleared.** Like the sibling's rewrite record, it is a fact and not an alert. A later
reverted delivery overwrites it.

---

## R14. The frontend surface

**Decision**:

- A "Push to remote" section on the repository details page, for `CoreRepository` only. It always
  queries the default branch, whatever branch the user selected (FR-025). It shows the status, the
  cause, the required action in plain words, the sentence "Imports from the remote default branch
  are paused until the pending pushes clear", the remote's message verbatim, and the pending merges
  in order. After an abandonment it shows the last record, and advises "Reimport current commit".
- Two items in `entities/repository/ui/repository-menu-section.tsx`: "Retry push" and "Abandon
  pending push". Both are disabled without `permission.update`, and as the table "Actions by status"
  of [data-model.md](data-model.md) says.
- An abandonment confirmation modal that lists the merges it will drop, says that nothing is
  removed from the remote, and says that repository objects of the dropped merges can stay on the
  default branch until a reimport.
- The eight attributes are left out of the main attribute list, the "extra" toggle
  (`object-data-display.tsx`) and the list-view column picker (`get-column-candidates.ts`) for
  `CoreRepository`, so the inherited copy of a non-default branch is never shown as current.
- Each mutation follows the existing three-file pattern: `api/*-from-api.ts` with gql.tada,
  `domain/use-cases/*.ts`, and `ui/queries/*.mutation.ts`. The task link toast and the query
  invalidation follow `import-current-commit`.

**Out of scope**: the per-branch status list, a signal on the proposed change or the repository
list, and the status vocabulary (INFP-671).

---

## R15. Test harness

**Unit, no database** (`backend/tests/unit/git/writeback/`, `backend/tests/unit/core/merge/`):

- the classifier across every row of R5, the flags included;
- the scrubber;
- the queue model: append, idempotent enqueue, refusal of a removed id, snapshot removal, version;
- the held set: a repeated hold of the same identifier during a release survives the clear;
- the service against an in-memory `DeliveryGitPort` and an in-memory store: observation, the two
  checks, replay conflict, push failure and reset, the obligation saved before the record, a crash
  between the two, the import condition, the release outside the lock, release then clear;
- the barrier: partition, the atomic hold, the fast path, unknown owners, `releasing`, fail-open,
  the narrowed cache hit and miss;
- the retry condition and `final_attempt`.

**Component, with a database**: the store's transitions and the lock time to live; `read_only`
keeping the attributes out of the update input; the branch-safety test (no delivery attribute in a
diff, never merged, the inherited copy on a new branch); the data-only skip (fork, trunk advances,
data-only merge, no entry); the mutations refuse on another branch; a long queue of 200 entries.

**Integration, live Gogs remote** (`backend/tests/integration/git/test_git_live_remote.py`), reusing
`rejected_push_to_main` and `_install_remote_branch_rejection_hook`:

- two merges while rejected, then one retry delivers both in one push;
- the remote message is recorded verbatim;
- a remote that advanced during the outage is recorded, then imported, and the synchronisation
  skipped the default branch meanwhile;
- an artifact definition updated by that import renders against the delivered commit;
- a replay conflict, then an abandonment, a record and a release;
- a conflict resolved by hand on the remote, then a retry clears it by observation;
- a force-pushed source branch gives `source-discarded` and pushes nothing;
- the remote branch deletion is refused while pending, not imported again, and deleted after the
  delivery;
- a transient fault: the Gogs port is blocked for the first attempt and opened before the second,
  with short delays. Stopping the port fails the push at once, where a paused container would hang
  it;
- a lost attempt: the flow is killed after the snapshot, and the recovery check restarts it.

**Deferral**: the release count is asserted through the dispatched workflows. IFC-3048's scenario
harness is the place for run counts on a real stack, if it has landed by then.

**E2E** (`tests/e2e/repository/test_repository_delivery.py`): the e2e stack serves repositories
through the SDK `GitRepo` helper from a local bare repository. The test writes a rejecting
`pre-receive` hook into it, merges a branch, opens the repository page on another branch, reads the
cause, removes the hook, clicks "Retry push" and waits for "Nothing pending". A second test makes
the push conflict, clicks "Abandon pending push", confirms the modal, and checks the record.

---

## R16. Documentation

| File | Change |
|---|---|
| `dev/knowledge/backend/git-integration.md` | Replace the two volatile sections ("not ordered against post-merge regeneration", "writeback direction has no reconciliation"). The second one is already stale: `merge` pushes before it records since `7d1bab3d1`. Add the delivery queue, the barrier, the three import paths that wait, the recovery check, and the known limitation of branches forked during an outage. Update the known limitation on remote branch deletion. |
| `dev/knowledge/backend/selective-merge-regeneration.md` | The barrier, the new fallback reason, the two repository filters, and the narrowed cache. |
| `dev/knowledge/backend/merge-recompute.md` | The barrier consultation for the Python family and the schema-scoped recompute. |
| `docs/docs/git-integration/branch-synchronization.mdx` | What happens when a push fails, the status, the paused imports, retry and abandon, what abandon leaves behind, and the kept source branch. |
| `docs/docs/git-integration/overview.mdx` | One paragraph pointing at the above. |
| `changelog/` | One `added` fragment, written with the `creating-changelog-entries` skill. |

---

## R17. Generated files and the SDK submodule

Adding attributes to `CoreRepository` regenerates `backend/infrahub/core/protocols.py`,
`backend/tests/protocols.py` and `python_sdk/infrahub_sdk/protocols.py`. Commit `c96b64675`, which
added `commit` to the generic, is the precedent for the full set. Two mutations change
`schema/schema.graphql`, and the frontend types follow with `pnpm codegen` and
`pnpm codegen:graphql`.

The SDK protocols file lives in the `python_sdk` submodule. Per `AGENTS.md`, that change needs its
own PR on `opsmill/infrahub-sdk-python`, merged before the pointer moves here.
`tasks/backend.py` diff-checks that file, so the sibling epic needs the same SDK change: its
data model's statement "no submodule change and no second PR" is wrong. One SDK PR should carry the
attributes of both epics, or the two must land in an agreed order.

No `GRAPH_VERSION` bump: optional attributes are added by the schema migration that
`infrahub upgrade` runs (`NodeAttributeAddMigration`).

---

## R18. Configuration

No new setting. The retry bounds, the Git timeouts, the stale bound and the cache time to live are
constants in `git/writeback/constants.py`, as `WEBHOOK_SEND_RETRIES` is in `webhook/constants.py`.
A setting would be configurability for a hypothetical need (Principle VII).

---

## R19. Coordination with IFC-3210 and IFC-3002

- **The ancestry question.** IFC-3210 adds `git/divergence/gateway.py` for it. Whichever epic lands
  first adds the primitive, with one contract: `False` only for a missing object, a raise for every
  other failure. The other epic reuses it.
- **The merge-path check.** IFC-3210's FR-005a makes `InfrahubRepository.merge` refuse a diverged
  source or destination. After slice C, the merge flow no longer calls `merge`: the service replays
  instead, and its checks of R4 steps 3 and 5 are that refusal for the replay. IFC-3210's merge-path
  task therefore moves into the service. `merge` keeps only the no-origin path and the live-remote
  tests of #10465, and can be removed once those tests move to the service.
- **The synchronisation path.** Both epics change `collect_pending_imports`. R11's exclusion runs
  before the sibling's classification.
- **The SDK.** One PR for both epics (R17).
- **IFC-3002.** `_resolve_python_targets` and `computed_attribute_setup_python` gain the barrier
  filter. Whoever changes them next must keep it.

---

## R20. Liveness and recovery (FR-027)

**Decision**: the queue keeps `last_progress_at` and `retry_due_at`. A pending delivery is **stale**
when its status is `pending`, no retry is due in the future, and `last_progress_at` is older than
`STALE_AFTER`, 15 minutes. That bound exceeds the longest retry delay plus the two Git timeouts.

`last_progress_at` moves at every enqueue, every attempt start, and every recorded failure.

**The recovery check.** The periodic synchronisation already reads the store for each repository
(R11). When it finds a stale delivery, or held work behind an empty queue, or an owed import behind
an empty queue, it submits `GIT_REPOSITORY_DELIVERY_RETRY` with a system context and moves
`last_progress_at`, so it submits at most once per `STALE_AFTER`.

**Why this is not an unbounded retry.** A stale delivery has no failure to retry: its attempt was
lost to a worker restart, a lost submission or a killed process. The new attempt is a first attempt
with its own bounded chain. If it fails on policy, the status becomes `action-required` and the
check stops.

**Manual retry.** The retry mutation is allowed for a stale `pending` as for `action-required`.

**Rejected: a liveness heartbeat during the attempt.** The Git timeouts already bound an attempt, so
a heartbeat would add writes on the hot path for no gain.

---

## R21. Observability

**Decision**:

- Every delivery, retry and abandon run is tagged with the repository node and the default branch,
  so it appears in the repository's task list, as the synchronisation flow's runs do.
- Every store transition logs one line with the repository, the entry ids, the status, the cause and
  the attempt number.
- A run ends `Failed` for the outcomes `failed` and `unreplayable`, and `Completed` for `delivered`,
  `observed` and `nothing-pending`.
- The barrier logs each hold at info level, with the repository and the held identifiers, and each
  fail-open at error level.
- The merge flow's run log gains one line per queued repository, so the user who merged sees that a
  push is pending.

---

## R22. Rollback

A code revert is safe for the data: the eight attributes are additive, and the old code ignores
them. Two effects remain after a revert, and the release note says so:

- Entries still queued are never delivered by the old code. An operator delivers them by hand, or
  merges again.
- Held regeneration is never released. An operator runs a full regeneration of the default branch
  after the revert.

**Rejected: a setting that falls back to `InfrahubRepository.merge`.** It doubles the merge path to
test, for a rollback that a code revert already provides (Principle VII).

---

## R23. Growth of the stored history

Every transition rewrites the whole `delivery_queue` value, and the temporal history keeps every
version. N merges during one outage therefore store about N²/2 entries in the history of that
attribute. An entry is about 250 bytes, so 100 merges store about 1.2 MB, and 1,000 merges about
125 MB. Outages that long are not expected, and the component test of R15 covers a queue of 200
entries. If it becomes a concern, the entries can move to one attribute per transition, which this
plan does not need.
