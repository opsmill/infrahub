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
the default branch, whatever branch the caller runs on. The frontend keeps the nine attributes out
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

Every place that writes has database access: the branch merge flow, `post_process_branch_merge`,
the computed-attribute flows, and the git task workers (`git/tasks.py` already calls
`get_database()`).

**Why one class.** FR-009 says that only an abandonment, which writes a record, may remove an
undelivered entry. That rule can only be enforced in one place. Each method of the store is one
state transition, and the record and the removal are one `save`.

### The locks

Two locks, always taken in this order:

| Lock | Name | Held by | Held for | Time to live |
|---|---|---|---|---|
| Repository lock (exists) | `lock.registry.get(name=<repository name>, namespace="repository")` | The Git part of a delivery attempt, and the removal step of an abandonment. | The Git work. Never across a release, never across a retry delay. | none, as today. The deadlock cleanup deletes it after its holder died (R20). |
| Delivery-state lock (new) | `lock.registry.get(name=<repository id>, namespace="repository-delivery")` | Every store transition. | One read-modify-write. | 30 seconds, acquire bounded to 10 seconds |

**Why a second lock.** The enqueue runs in the branch merge flow, and the barrier runs in the
branch merge flow (`dispatch_events`), in `post_process_branch_merge` and in the computed-attribute
flows. Taking the repository lock there would make a branch merge wait behind a periodic sync or a
running delivery. The state lock is held for one read and one write.

**Why the state lock has a time to live.** It is taken inside the branch merge flow. A worker that
died in the middle of a transition would otherwise hold it for ever, and every later merge of that
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
enqueue is guarded on its own. A failed enqueue is retried with a bound. If the last retry fails
too, the dispatcher logs at error level, and the merge is still submitted with `pending_merge` set.
The dispatcher sets `GitRepositoryMerge.pending_merge_enqueued` to `True` only when one of its tries
returned. `merge_git_repository` writes the entry before its first attempt only when that flag is
`False`. The save that writes it also holds a `widen` marker of scope `all` for the repository.

**Which merges are queued** (FR-005): only a repository whose internal status on the source branch
is `active`, on a source branch that syncs with Git, and whose source commit carries repository
content. A staging repository keeps today's path and is never queued. The dispatcher does not test
for a remote: `location` is mandatory on every repository
(`core/schema/definitions/core/repository.py::core_generic_repository`), so every queued repository
has one.

**A clone with no `origin`.** Whether a clone has `origin` (`InfrahubRepositoryBase.has_origin`) is
a fact of one worker's disk. Because the location is mandatory, such a clone is broken. It is not a
repository without a remote. The flow has no separate path for it. The attempt fails at the fetch
(R4 step 2), records nothing, and keeps every entry in the queue. A local merge and record on that
worker would record a commit that the remote does not have (FR-001). It would also remove the
entries of earlier merges that the remote does not have yet (FR-009). A manual retry on another
worker, or after a fresh clone, delivers the queue.

**When a merge carries no repository content.** The dispatcher reads, for the source branch, the
`commit` value and the branch's `branched_from`, then reads the default branch's `commit` at that
time. It skips the enqueue when the source branch has no value, when its value equals the default
branch's value at `branched_from`, or when it equals the commit recorded now. A branch that never
recorded its own commit reads exactly the default branch's value at `branched_from`, so the second
test catches every data-only branch, including one forked before the trunk moved.

For such a merge the dispatcher also submits no `GIT_REPOSITORIES_MERGE`: there is nothing to merge,
and today's flow would only find nothing to merge and broadcast the commit the workers already hold.
A run that the previous code queued carries no `pending_merge`, so the flow builds the entry itself.
Before it does, it runs the same test and skips a merge that carries no content. Without that test,
such a run would queue an entry that FR-005 forbids.

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

**Why the first write is in the branch merge flow** (FR-005a). The coalesced recompute runs in
`dispatch_events` right after `run_follow_ups`, and `post_process_branch_merge` is submitted at the
end of `run_follow_ups`. Both consult the barrier. An entry written by `merge_git_repository` would
arrive after them.

**When the first write fails** (FR-005a). If the entry is not in the queue when the follow-ups
consult the barrier, the barrier sees no pending delivery for the repository and admits its work.
That work runs against the recorded commit, which does not hold the merge. `merge_git_repository`
writes the entry later, but the barrier held nothing for that work, so no release would run it
again. Two steps close this gap:

1. **A bounded retry.** The dispatcher retries a failed enqueue as the barrier retries a failed
   read (R9): `ENQUEUE_RETRIES` times, 3, after the delays of `ENQUEUE_RETRY_DELAYS_SECONDS`, 2, 8
   and 20 seconds. The values are the barrier's, for the same reason: a lock that a dead worker left
   expires within its 30-second time to live, and the last try starts at least 30 seconds after the
   first. `enqueue` is idempotent, so a try after a write that committed but raised finds the id
   present and returns.
2. **A second run of the regeneration.** When every try fails, `merge_git_repository` writes the
   entry with `widen=True`. The save that appends the entry also holds a `widen` marker of scope
   `all` for the repository, with the reason `UNHELD_FOLLOW_UP`. The queue is non-empty in that
   save, so the hold always succeeds, and the attempt's snapshot comes after it. The release after
   the delivery then runs a full regeneration of the repository's definitions against the delivered
   commit (R10). It covers every definition that the follow-ups dispatched without a hold.

A run that the previous code queued carries no `pending_merge`, and its follow-ups ran with no
barrier. The flow holds the same marker when it writes the entry of that run.

When `enqueue` refuses the id, it holds no marker. A refusal means that a try of the dispatcher
wrote the entry before the follow-ups ran, so the barrier saw it.

**When the write of `merge_git_repository` fails too.** That write is the first step of the
delivery task's first attempt, with the stage `enqueue` (R4 step 0, R5). A failure of it is retried
like a transient failure: the task retry runs the write again before it delivers. The write is
idempotent, so a retry after a write that committed but raised finds the id present and writes
nothing. If every attempt fails, the run ends `Failed`. It logs at error level the repository, the
source branch and the source commit, so that an operator can deliver the merge by hand, for example
with a merge of the source branch on the remote. This is a residual, and it needs a store that fails
at every try of the dispatcher and at every attempt of the task, about seven and a half minutes of
delays (R6). That merge's repository content is then neither queued nor delivered, and nothing
retries it later. No entry names its remote source branch, so the branch-deletion guard (R12) does
not keep that branch either.

**The cost.** When every try fails, and only then, the repository's definitions regenerate twice:
once against the old commit, and once against the delivered commit. A stale result never stays. The
retry delays the branch merge flow only while the store fails. The delays add up to 30 seconds for
each repository whose enqueue fails. When the lock acquire times out, each try also waits up to
`STATE_LOCK_ACQUIRE_SECONDS`, 10 seconds (R2).

**Rejected: no delivery for the repository whose write failed.** The graph already holds the merge.
Without a delivery, the remote never receives it.

**Rejected: an intent that the barrier reads, written before the follow-ups.** It is a write to the
same store, which just failed.

**Rejected: the follow-ups wait for the write with no bound.** The branch merge flow would then wait
for the whole failure of the store.

**When the flow writes the entry, and why that is safe** (FR-005b). The flow's write repairs a
failed first write. It must not put an abandoned entry back: a run of `merge_git_repository` can
wait in the Prefect queue while a user abandons. So the flow writes the entry only when
`pending_merge_enqueued` is `False`. Two runs have that value:

- No try of the dispatcher's enqueue returned. The flow writes `model.pending_merge`.
- The previous code queued the run, so it carries no `pending_merge`. The flow builds the entry from
  the source branch's graph commit, as the dispatcher would.

In both runs, the entry was never in the queue, so no user can have abandoned it. The next
paragraph names the one exception. When the flag is `True`, the flow never writes. It only
delivers. If a user abandoned the entry meanwhile, the snapshot does not contain it, and the attempt
pushes nothing. This is the guarantee of FR-005b.

**The second guard.** One case remains: a try of the dispatcher committed its write but raised
after it, and every later try raised too. If a later try returns, it finds the id present, and the
dispatcher sets the flag. The flag is then `False` while the entry is in the queue. For this case,
`enqueue` refuses an id that is present, in `removed_entry_ids` (the last 256 ids that left the
queue), or in `delivery_last_abandonment.entries`. Both bounds expire. The entry can come back only
when 256 other entries leave the queue and a second abandonment replaces the record, all before the
late flow runs.

**Rejected**: keying the queue on the Infrahub branch. The Infrahub branch can be deleted right
after the merge (`delete_branch_after_merge`), while the remote branch is protected by FR-011.

---

## R4. The delivery attempt

**Decision**: one component, `RepositoryWritebackService`, built per repository at the top of each
flow, with one entry point, `deliver(final_attempt, manual, entry)`. `merge_git_repository`, the
retry flow and the recovery check (R20) all call it (FR-007). Its end has the same shape as the
abandonment of R8: the entries leave the queue under the repository lock, and the release runs
after the lock is released, under a lease.

### The algorithm

0. **Enqueue**, only when `entry` is not `None`. `merge_git_repository` passes the entry that the
   dispatcher could not write (R3), and every other caller passes `None`. Under the state lock,
   enqueue it with `widen=True`. A failure has the stage `enqueue` (R5): it records nothing on the
   repository, and the task retries it like a transient failure. A refused id is not a failure.
   When step 0 fails on the final attempt, the run stops there, so it also delivers none of the
   entries that were already queued. They wait for the recovery check, a manual retry, or the next
   delivery run of that repository.

Under the repository lock:

1. **Snapshot.** Under the state lock, read the queue and the held set, and stamp
   `attempt_started_at` and `last_progress_at` in `delivery_progress`. "Something to do" means a
   non-empty queue, or held work with no live release lease. If there is nothing to do, return
   `nothing-pending`. If only held work remains, take a lease through `lease_owed_release`, leave
   the repository lock, and go to step 16.
2. **Fetch**, with its time limit (R6). Let **H** be the remote head of the destination, and **R** the
   commit recorded for the destination. Move `last_progress_at`. On a clone with no `origin`, the
   fetch raises, and the attempt stops here, before any check. It pushes nothing, records nothing
   and keeps every entry (R3). R5 classifies the failure as `unclassified`.
3. **Destination check** (FR-022). If R is neither H nor an ancestor of H, the destination was
   rewritten. Mark the queue unreplayable with the cause `destination-rewritten`. Push nothing. A
   worker that does not hold R locally treats it as rewritten, which is the safe reading.
4. **Observation** (FR-012). Drop from the replay every entry whose source commit is H or an
   ancestor of H. The remote already holds it.
5. **Source check** (FR-020). For each remaining entry, the source commit must be the remote head of
   its source branch or an ancestor of it. If it is not, mark the queue unreplayable with the cause
   `source-discarded`. Push nothing. A missing remote branch fails the check too.
6. **Replay.** Reset the destination worktree to H, **always**, also when no entry remains to
   replay. Merge each remaining source commit, in queue order, with the same `--no-ff` rule as today
   (`git.use_explicit_merge_commit`). On a conflict, abort, reset to the pre-attempt commit, and mark
   the queue unreplayable with the cause `replay-conflict`, naming the entry.
7. **Push** once, if any entry was replayed, with its time limit (R6). On a failure, reset the
   worktree to the pre-attempt commit (FR-002) and classify the failure (R5). Move
   `last_progress_at`.
8. Let **M** be the worktree head. Because step 6 always resets to H, M is H on the observation
   path, and H plus the replayed merges otherwise.
9. **Import obligation.** If H is not R, or an import is already owed, save
   `import_owed_commit = M` through the store. This save comes **before** the commit write: a crash
   between the two then leaves an obligation that the next attempt honours, never a recorded commit
   with nothing owed.
10. **Record.** Create the commit worktree of M and write the commit, through `update_commit_value`
    as today (FR-001). On a failure, reset the worktree behind the remote. The next attempt observes
    the delivery and records it. Move `last_progress_at`.
11. **Import** at M on the default branch when an import is owed (FR-023). Move `last_progress_at`
    before and after it. On success, clear the obligation, unless the queue grew past the snapshot
    meanwhile. On a failure, classify it (R5) and stop: the obligation stays, the entries stay, and
    the held work stays held.
12. **Broadcast** `RefreshGitFetch` pinned to M, as `merge_git_repository` does today.
13. **Delete source branches.** For each delivered entry with `delete_source_git_branch` set, and
    that no remaining entry names, delete the remote branch and send
    `RefreshGitRepositoryBranchDeleted` (R12). A branch that is already gone counts as deleted. A
    deletion that fails is logged at warning level and does not fail the attempt, because the
    delivery itself succeeded. The remote branch then stays, as it does today when
    `git_branch_delete` fails.
14. **Settle.** Under the state lock, in one save: remove the snapshot's entries into
    `removed_entry_ids` and bump the version; set `delivery_last_delivered_commit` to M when
    something was pushed; set the status from what remains, and clear the cause and the message when
    it is `none`; add a **release lease** that names the held items that no live lease covers, up
    to the snapshot's highest sequence (R10). The held items stay.
15. Leave the repository lock.

Then, outside the repository lock:

16. **Release** the held items of the lease window (R10). The releaser renews the lease after each
    awaited step. If the release fails, set the lease's expiry to now, then classify the failure
    (stage `release`, R5) and stop. The held items stay (R10, rule 4).
17. **Clear.** Under the state lock: remove each held item of the lease window that still has the
    sequence that the lease names, and end the lease. An item held again meanwhile stays.

**Why the entries leave under the lock.** Two kinds of waiter take the repository lock the moment
it is free: an abandonment and the branch-deletion guard. If the entries stayed queued until after
the release, an abandonment would pass its version check and record as "dropped" merges that the
remote already holds, and the guard would flag an entry whose deletion step has already run, so the
branch would never be deleted. Settling under the lock bumps the version first: the abandonment is
refused as stale, and the guard finds no entry and deletes the branch itself.

**Why the record comes before the import.** The import writes artifact definitions through the SDK,
and each write submits a generation that reads the recorded commit. With the import first, those
generations would read R. The synchronisation already records first (R0).

**Why the release runs outside the repository lock.** The release awaits generator runs through
`_dispatch_plan`. A generator run calls `get_initialized_repo(commit=M)`, and
`git/integrator.py::initialize_local` takes the repository lock to fetch a missing commit on a worker
that has not heard the broadcast yet. Holding the lock across the release would deadlock. The
broadcast goes first so that most workers already hold M.

**Why the release has a lease.** Between steps 15 and 17, a waking retry chain, a manual retry or
the recovery check can start a run. That run must not release the same items again. While a lease
is live, a run releases only the items that the lease does not cover, such as an item held again
after the lease was taken, and the recovery check does nothing for the covered items. A lease that
expires, because the releasing worker died, makes the release owed again, and the recovery check
starts it. A run whose release fails does not wait for that: it sets the lease's expiry to now, so
the retry of its task releases the items again (R10, rule 4).

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

**An owed import implies a non-empty queue.** The obligation is cleared before the settle, or the
attempt stops with its entries still queued. An abandonment clears both together. This invariant
lets the barrier's fast path read the scalar status alone (R9).

**Rejected: storing the merge commit as a Git bundle.** The PRD measured and rejected it: it becomes
undeliverable as soon as the remote destination advances, and delivering it then needs a
force-push.

### The Git primitives

All new Git calls sit behind a port, `DeliveryGitPort`, so that the service is unit-testable without
Git (PRD testing decisions). The concrete adapter wraps one `InfrahubRepository`.

| Port method | Built on |
|---|---|
| `fetch()` | `InfrahubRepositoryBase.fetch`, with `kill_after_timeout`. That method returns `False` on a clone with no `origin`. The adapter then raises `RepositoryError` and never treats it as a fetch. |
| `remote_head(git_branch)` | `git rev-parse refs/remotes/origin/<branch>`, bounded. Not `get_commit_value(remote=True)`: it reads through GitPython's object database, whose long-lived `cat-file` process no timeout covers. |
| `is_ancestor(ancestor, descendant)` | `git merge-base --is-ancestor`. Exit 1 means no. A missing object means no. Any other failure raises. Shared with IFC-3210 (R19). |
| `replay(base, commits)` | `reset --hard`, then `merge` per commit, aborting on a conflict. |
| `push()` | `InfrahubRepository.push`, extended by R5, with `kill_after_timeout`. |
| `reset(commit)` | `_reset_to_pre_merge_commit`, which never raises. |
| `record(commit)` | `create_commit_worktree` plus `update_commit_value`. |
| `import_at(commit)` | `import_objects_from_files` on the default branch. |
| `broadcast(commit)` | `RefreshGitFetch`, as in `merge_git_repository`. |
| `delete_remote_branch(git_branch)` | `delete_remote_branch` plus `RefreshGitRepositoryBranchDeleted`. |

Every other row that runs a Git command passes `kill_after_timeout` too (R6).

---

## R5. Classifying a failure, and keeping the remote's words

**Decision**: a pure function, `classify_delivery_failure(error, stage) -> DeliveryFailure`, in
`git/writeback/classifier.py`. `stage` is one of `enqueue`, `fetch`, `push`, `record`, `import`,
`replay` and `release`. It reads the exception type first. Per-ref push rejections get a typed
error whose reason comes from GitPython's `PushInfo` flags, not from text.

| Stage | Exception | Cause | Retried automatically |
|---|---|---|---|
| enqueue | any, while `merge_git_repository` writes the entry that the dispatcher could not write (R3) | left unchanged. The entry is not in the queue, and the store just failed, so the attempt records nothing on the repository. | yes. The task retry runs the write again before it delivers. After the final attempt, the run ends `Failed` with an error-level log line that names the repository, the source branch and the source commit (R3). |
| fetch, push | `RepositoryConnectionError` (unreachable, timeout, 5xx, a fetch or a push past its time limit, known only after Git ends) | `remote-unreachable` | yes |
| fetch, push | `RepositoryNotFoundError` (new subtype) | `not-found` | no |
| fetch, push | `RepositoryTLSError` (new subtype) | `certificate` | no |
| fetch, push | `RepositoryCredentialsError` | `credentials` | no |
| fetch | `RepositoryError` for a clone with no `origin` (R3) | `unclassified` | no. An automatic retry runs on the same worker and fails again. The message names the repository and says that the clone on this worker has no `origin`. It names no path. |
| push | `RepositoryPermissionError` | `permission` | no |
| push | `RepositoryPushRejectedError`, reason `policy` (`REMOTE_REJECTED`) | `permission` | no |
| push | `RepositoryPushRejectedError`, reason `non-fast-forward` (`REJECTED`) | `remote-advanced` | yes. The remote moved between the fetch and the push, and the next attempt fetches again. |
| push | `RepositoryPushRejectedError`, reason `unknown` | `unclassified` | no |
| record | any | `record-failed` | yes. The remote has the content (FR-004). |
| import | `DatabaseError`, `RepositoryConnectionError`, a GraphQL transport error | `import-interrupted` | yes |
| import | any other, for example a configuration or validation error of the content | `import-failed` | no |
| replay | a merge conflict | `replay-conflict` | no |
| replay | a killed local Git command (`LOCAL_GIT_TIMEOUT_SECONDS`) | `unclassified` | no. The message names the command. |
| release | any | the cause is left unchanged | yes, and never a reason for `action-required`. The failed run sets its lease's expiry to now, so the retry takes a new lease and releases again (R10, rule 4). The delivery is done; a release that still fails leaves the held work to the recovery check (R20). |
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

**A fetch or a push past its time limit.** When Git ends after `kill_after_timeout` passed and Git
failed, GitPython adds "process killed because it timed out" to the error lines
(`git/cmd.py::handle_process_output`). `_raise_enriched_error_static` raises
`RepositoryConnectionError` for that text, with a message of its own, so the attempt is retried.
GitPython does not stop the command at the limit, so this classification comes only after Git ends
(R6).

**A killed local Git command.** It is not a remote fault, so it must not become
`remote-unreachable`. GitPython reports it with a different text, "Timeout: the command ... did not
complete" (`git/cmd.py::Git.execute`), which names the command with its arguments.
`_raise_enriched_error_static` turns that text into a `RepositoryError` whose message names the Git
command and the limit, but not the arguments, which can name worker paths (`GIT_CALL_TIME_LIMIT`).
`create_commit_worktree` raises that error for its `worktree list` and its `worktree add`. At the replay, and in the checks before it, that error is
`unclassified`: the status becomes `action-required`, and the user retries. At the record, the
`record` row applies: the remote already has the content, so the failure is `record-failed` and is
retried.

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

## R6. The automatic retry, and time limits on Git commands

**Decision**: the delivery attempt is a Prefect `@task` with `retries=3`,
`retry_delay_seconds=[30, 120, 300]` and a `retry_condition_fn` that retries only a failure
classified as automatically retryable (R5). The task reads its attempt number from
`task_run.run_count` and passes `final_attempt` to `deliver`, which records `action-required` only on
the final attempt. Tests override the delays with `with_options(retry_delay_seconds=...)`.

**Why a task.** Prefect 3.8 supports `retry_condition_fn` on tasks only, not on flows.

**Why these bounds.** About seven and a half minutes cover a blip, a load-balancer failover or a Git
server restart. The PRD assumes that real outages last days, so a longer automatic window buys
nothing and holds a worker slot.

**Time limits on Git commands.** The adapter passes GitPython's `kill_after_timeout` to every Git
command that it runs. The limit does not stop every command; see "What the limit does" below.

| Command | Bound |
|---|---|
| The fetch | `FETCH_TIMEOUT_SECONDS`, 120 seconds |
| The push, and the deletion of a source branch at R4 step 13, which is a push too | `PUSH_TIMEOUT_SECONDS`, 300 seconds |
| Each local command: `rev-parse`, in `remote_head`; `merge-base --is-ancestor`; `reset --hard`, in `replay` and in `reset`; `merge` and `merge --abort`, in `replay`; `worktree list` and `worktree add`, in `create_commit_worktree` for `record` | `LOCAL_GIT_TIMEOUT_SECONDS`, 120 seconds |

**What the limit does** (GitPython 3.1.62, checked on IFC-3312):

- **A fetch or a push past its limit is classified only after Git ends.** The fetch and the push run
  through `Remote.fetch` and `Remote.push`. When the limit passes, `AutoInterrupt._terminate` closes
  the pipes before it kills Git, and the close waits until Git ends. When Git then fails, GitPython
  adds "process killed because it timed out" to the error lines, and R5 makes it
  `remote-unreachable`, which the chain retries. When Git then succeeds, the call returns normally.
- **A hung fetch or push is not stopped.** A remote that accepts the connection and never answers
  keeps the fetch or the push running, with the repository lock and the worker slot, until the
  connection ends. A test with a 2-second limit returned after 30 seconds.
- **A direct Git call is stopped by a watchdog that needs `ps`.** Every other command, the deletion
  of a source branch included, runs through `Git.execute`. There a watchdog kills Git when the limit
  passes, and GitPython reports "Timeout: the command ... did not complete". The watchdog finds the
  child processes of Git with `ps`. The runtime image has no `ps`, so there the watchdog cannot stop
  a direct Git call either.

**Open point for a later story**: a bound that stops a hung fetch or push, and a direct Git call in
the runtime image. Until it ships, FR-004 holds for these commands only when Git ends by itself.

A local command normally ends in seconds, so its limit matters only for a command that is stuck. A
killed local command raises a `RepositoryError` that names the command and the limit, and R5
classifies it. The deletion of a source branch is a push, so `delete_remote_branch` types its errors
as `push` does, and past its limit it raises `RepositoryConnectionError`. `reset` never raises: a killed reset is logged like any failed reset, and the failure
of the attempt still propagates. The limits live in `git/writeback/constants.py`.

**A killed local command can leave a lock file.** GitPython kills with `SIGKILL`, so a killed
`reset` or `merge` can leave `index.lock` in the destination worktree. Every later Git command in
that worktree would then fail until someone removed the file by hand. After it kills a local
command, the adapter removes that `index.lock` before it raises. That is safe because the adapter
holds the repository lock, so no other Git process on this worker writes to that worktree.

The import of R4 step 11 has no bound. It is not a Git command, and the local Git commands that
`import_objects_from_files` runs get no bound either. FR-004 therefore excludes the import, and
FR-027 covers it instead: while it runs, it holds the repository lock, so the delivery is not stale
(R20, condition 4), and the recovery check starts no second attempt.

**One retry chain per repository.** Before it waits, a retryable failure stores `retry_due_at`. A
run of `merge_git_repository` whose first attempt finds a retry already due in the future returns
at once, after its enqueue of R4 step 0 when it has one: that chain snapshots the queue at its next
attempt and delivers the new entry too. A manual retry never returns early, because a user asked
for it now. A chain that wakes after a manual retry delivered finds nothing and does nothing.

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
- the queue version named by an abandonment differs from the current one (abandon);
- the repository is read-only or `STAGING` (both).

A retry is allowed in every status other than `none`, a running attempt and a waiting automatic
retry included. The retry flow waits for the repository lock, so two attempts run one after the
other, and the second finds nothing. A user who fixed the cause need not wait for the next
automatic attempt.

**The workflows re-check differently.** The retry workflow checks nothing itself: it calls
`deliver`, whose step 1 decides, and "something to do" there also covers held work behind an empty
queue, which the recovery check submits the same workflow for. The abandon workflow re-checks the
version and the queue under both locks, inside the store transition. This mirrors ADR 0014, where
the mutations "re-check availability at execution time to reject a stale action".

**Why the abandonment is a workflow too.** It must not interleave with a running attempt, so it
takes the repository lock, which a worker flow already holds in the same way.

**Rejected: ADR 0014's generic task actions.** Those act on a task run. Here the subject is the
repository's queue, which outlives every task run, so the action belongs on the repository.

---

## R8. The abandonment

**Decision**: `WritebackAbandoner.abandon(queue_version, actor)`, run by the flow
`git-repository-delivery-abandon`. It changes no Git state and imports nothing.

1. Under the repository lock and the state lock, in one transition: refuse when the version differs
   or nothing is pending; otherwise remove every entry, add their ids to `removed_entry_ids`, bump
   the version, clear any owed import, write the abandonment record with the actor, the time, the
   version, the recorded commit and the owed import, and add a release lease that names every held
   item that no live lease covers. The save passes the actor's account id as `user_id`. The held
   items stay.
2. For each abandoned entry with `delete_source_git_branch` set, send
   `RefreshGitRepositoryBranchDeleted`, so that every worker drops its local branch. The remote
   branch stays (R12).
3. Leave both locks. Release the held items of the lease window (R10). If the release fails, set
   the lease's expiry to now and raise. The held items stay, and the recovery check of R20 releases
   them (R10, rule 4).
4. Under the state lock, remove each held item of the lease window that still has the sequence
   that the lease names, and end the lease.

**Why step 1 removes the entries before the release.** With the entries still queued, a delivery
attempt could start between the release and the clear and push the merges the user is abandoning.
After step 1, the queue is empty and no attempt can deliver them.

**What a crash between step 1 and step 4 leaves.** An empty queue with held items under a lease.
When the lease expires, the release is owed, and the recovery check of R20 starts a delivery flow,
which finds only held work and releases it. That is invariant 2 of the data model.

**What the abandonment does not do.** It never touches the remote, never deletes a remote branch,
and never re-imports. The repository section then says two things (FR-024): the default branch can
hold repository objects that the recorded commit lacks, and, when the record shows a dropped owed
import, it can lack objects that the recorded commit holds. It names that commit and offers
"Reimport current commit".

**Why the owed import is dropped and not kept.** An owed import that failed on content would fail
again at every recovery check, for ever. The reimport is the user's explicit way back.

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

1. holds a `widen` marker for that repository, which releases as a blanket regeneration of that
   repository (R10). The marker has a scope: `all` from `_full_regeneration` and the flag-off path,
   `terminals` from `_submit_full_terminal_regeneration`, which deliberately never re-runs the
   generators that just failed. Scope `all` covers every definition of the repository. Scope
   `terminals` covers only its artifact definitions, so its release still dispatches the held
   generator items and Python items. The marker also carries the `FullRegenerationReason` of the
   fallback that set it: the reason that `_full_regeneration` receives, `FEATURE_DISABLED` on the
   flag-off path, and the new `TERMINAL_SELECTION_FAILED` from `_submit_full_terminal_regeneration`.
   The release logs that reason (R10);
2. submits the blanket triggers with a new optional parameter, `exclude_repository_ids`, naming the
   pending repositories.

The barrier is not the only source of a marker. `merge_git_repository` holds one of scope `all`,
with the new reason `UNHELD_FOLLOW_UP`, in the save that writes an entry that the dispatcher could
not write (R3).

With no pending delivery, the triggers are submitted with no new parameter, byte for byte as today,
which keeps the promise of ADR 0012 that the flag-off path is the blanket path exactly.

`git/tasks.py::generate_artifact_definition` and `generators/tasks.py::run_generator_definition`
gain `exclude_repository_ids` and `include_repository_ids`, both `list[str] | None = None`. A
definition is skipped when its repository is excluded, or when an include list is given and its
repository is not in it.

### The atomic hold, with sequence numbers

The barrier holds a repository's candidates only after it confirms, under the state lock, that the
repository's queue is still non-empty. When the delivery settled the queue in between, the
candidates are dispatched. An owed import implies a non-empty queue (R4), so the queue alone
decides.

Each hold gets the next value of a per-repository sequence, and every held item keeps the sequence
of its latest hold. A release lease names the exact items that it covers, each with the sequence
that the item had when the lease was taken (R10). Its clear removes an item only when the item
still has that sequence. A definition held again while a release runs has a higher sequence, so it
survives the clear (FR-015).

The lease names a set of items, not a range of sequences. The items that no live lease covers can
have gaps, for example when an expired lease, a live lease and later holds follow each other. A
range over the uncovered items would then overlap the live lease, and a clear by range would remove
the items of the live lease before that lease releases them.

**The fast path.** `pending_repository_ids` filters on the scalar `delivery_status` alone, which is
`pending` or `action-required` exactly when the queue is non-empty. A held-only state behind an
empty queue needs no barrier decision, since nothing is held there. The recovery check reads that
state per repository (R20).

### Where the barrier holds more than a merge started

Two consultation sites cannot tell a merge-started run from any other run on the default branch.
`computed_attribute_setup_python` runs for every `SchemaUpdatedEvent`, and the delivery's own
import can send one. `RecomputeChainSubmitter` levels run whatever started the chain, for example
`InfrahubRecomputeComputedAttribute`. While a repository has a pending delivery, the barrier holds
those runs too, for that repository's transforms.

**Decision**: accept the wider hold, and state it in FR-017. A held run is never dropped: it is
released with the next release of its repository, or by the recovery check when it was held after
the last release started. Passing a merge marker through the Prefect trigger and the chain would
cost a new parameter on four flows for a case that only delays work during an outage.

### When the store fails

**Decision**: retry the read, then fail open. If the store raises, or the state lock cannot be
acquired, the barrier reads the delivery state again. It retries `BARRIER_STATE_READ_RETRIES`
times, 3, after the delays of `BARRIER_STATE_READ_DELAYS_SECONDS`, 2, 8 and 20 seconds. A read that
succeeds decides as usual, so the barrier still holds the work of a pending repository. If the last
retry fails too, the barrier admits every candidate. It then logs at error level, with the branch
and the repositories of the candidates. Both constants live in `git/writeback/constants.py` (R18).

**Why a retry.** When a failure of the store is short, the barrier still holds the work. A lock that
a dead worker left is the clearest case: it expires within its 30-second time to live, and the last
read starts at least 30 seconds after the first.

**Why no durable hold after the last retry.** The hold is a write to the same store that the barrier
cannot read. When the read fails, the hold fails too. A hold kept only in the memory of a worker is
lost with the worker, and no release would ever cover it.

**Why the barrier does not raise.** Nothing retries the flows that consult the barrier. A raise
therefore drops the regeneration. That is under-execution, and ADR 0012 forbids it.

**The residual window.** Work admitted after the last retry runs against the recorded commit, which
is today's behaviour. That commit can differ from the commit that the delivery puts on the remote.
The barrier held nothing for that work, so the delivery does not run it again when it completes.
The next regeneration of the same definition corrects it. FR-016 and SC-004 state this exception.

**The cost.** The retry delays a flow only while the store fails. The delays add up to 30 seconds
for each consultation of the barrier. When the lock acquire times out, each read also waits up to
`STATE_LOCK_ACQUIRE_SECONDS`, 10 seconds (R2). A flow that consults the barrier, the branch merge
flow included, waits for that time.

### The narrowed selection, kept for a short time (FR-014, SC-008)

The coalesced recompute runs in `dispatch_events` right after `run_follow_ups`, a few milliseconds
after the first delivery attempt was submitted. A merge of a git-synced branch that carries
repository content will therefore nearly always see a non-empty queue. Holding identifiers only
would then turn every such merge's narrowed recompute into a whole-kind recompute.

**Decision**: at each hold, the barrier also writes the narrowed request of each candidate to the
cache, keyed by repository id, hold sequence and identifier. The value is the request model,
serialised. A release reads it per item, under the item's latest sequence. Inside the time to live,
it dispatches the narrowed request, so the dispatch equals what the merge would have dispatched with
no barrier. After it, or when the read fails, or when the serialised request exceeds 512 KiB, it
dispatches the identifier with no narrowing.

**A repeated hold writes a union.** An item keeps only its latest sequence, so a release reads only
the latest entry. Merge A can hold artifact definition D for member d1, and merge B hold D again for
member d2. If the entry of B held only d2, d1 would never be regenerated. So, on a repeated hold, the
barrier reads the entry of the previous sequence and writes the union of the two narrowed requests
under the new sequence, with the selectors' existing consolidation of member filters. If the
previous entry is missing, expired or too large, it writes no entry for the new sequence, and the
release dispatches that item with no narrowing. `hold` returns the previous sequence of every item
it refreshed, so the barrier knows which entry to read.

**Why this keeps FR-014.** The persisted state still holds identifiers only. The cache entry dies
before a long recovery could read it, which is exactly FR-014's purpose: "a long recovery cannot
dispatch a stale target set".

**The time to live is derived, not chosen.** `NARROWED_HOLD_TTL_SECONDS` is the sum of the retry
delays, plus the fetch and push timeouts times the number of attempts, plus a 10-minute margin for
the import and the settle. With the constants of R6 that is 450 + 4 × 420 + 600 = 2,730 seconds,
about 45 minutes. A merge whose delivery succeeds within its automatic retry chain regenerates as
precisely as today. A miss only widens. The derivation leaves out the local timeouts, because a local
command normally ends in seconds. It counts the fetch and push timeouts as if they stopped the
command, which they do not for a hung fetch or push (R6). A chain that runs longer than the cache,
for example after retried record failures or a hung fetch or push, only widens its release.

**Rejected: waiting for the first attempt before the follow-ups.** It would delay every git-synced
merge by the Git round trip, and by minutes when the remote is down.

---

## R10. The release

**Decision**: the release runs at the end of a delivery (R4 step 16) or an abandonment (R8 step 3),
outside the repository lock, through a component, `HeldRegenerationReleaser`, behind a port of the
service. It runs under a release lease, dispatches first and clears second. The clear removes only
the items that its lease names, at the sequences that the lease names.

### The release lease

The transition that settles a delivery or records an abandonment also adds a lease to the held set.
A lease names the exact items that it covers, and has an expiry. It names each item by its key, with
the `hold_seq` that the item had when the lease was taken. The key is the artifact or generator
definition id, the `(kind, attribute)` pair, or the `widen` marker. These named items are the
lease's window. A live lease covers an item that it names while the item keeps the named sequence.

A new lease takes every held item that no live lease covers, up to a bound:

- for a delivery, the highest sequence at the attempt's **snapshot**. A hold recorded after the
  snapshot can belong to a merge whose entry is still queued and not delivered, so it must wait for
  that entry's delivery;
- for an abandonment, and for a held-only run, no bound. The queue is then empty, so every held item
  belongs to an entry that has left it.

The releaser renews the expiry after each awaited step, because a release awaits generator runs and
can take minutes. Each renewal adds 15 minutes.

**Why a set and not a range.** The items that no live lease covers can have gaps. For example, lease
A expired, lease B is live, and new holds came after B was taken. A range from A's items to the new
holds would also span B's items. A clear by that range would remove B's items before B releases
them, and their work would be lost (FR-016). A set names only the items that its own release
dispatches.

The rules:

1. A release dispatches the items of its own window. Its clear removes each of those items that
   still has the named sequence, then its own lease. An item held again after the lease was taken
   has a higher sequence, so it stays, and the next lease takes it.
2. While a lease is live, no other run releases the items that it covers. A held-only run and the
   recovery check do nothing for them.
3. An expired lease protects nothing. A worker that died leaves one, and so does a release that
   failed (rule 4). The next lease takes its items, and the recovery check starts a release if no
   delivery comes.
4. When a release fails, its run sets the lease's expiry to now, through `expire_lease`, and only
   then handles the failure. Nothing cleared the items, so they stay held. The next run takes a new
   lease over them and releases every one. For a delivery, that run is the retry of its task (stage
   `release`, R5). For an abandonment, or when every retry fails, it is the run that the recovery
   check starts (rule 3). A release that dispatched part of its window before it failed dispatches
   that part again. That over-executes, which is the accepted direction (FR-015). If the store
   cannot set the expiry, the lease expires at its own time. A retry before then finds the lease
   live and does nothing, and the recovery check releases the items after the expiry.
5. Expired leases are cleaned up in the save that takes or clears a lease. When a new lease takes an
   item that an expired lease names, the item moves to the new lease. An expired lease also drops
   each item that the held set no longer holds at the named sequence. An expired lease that names no
   item any more is removed in the same save. A late clear by the run of an expired lease removes
   only the items that its lease still names, or nothing when its lease is gone.

| Held item | Released as |
|---|---|
| Artifact definition | The cached narrowed request if present, else `RequestArtifactDefinitionGenerate` with no `members` and no `limit`, through `_dispatch_plan`. |
| Generator definition | The cached narrowed request if present, else `RequestGeneratorDefinitionRun` with no `target_members`, through `_dispatch_plan`, so the generator-to-artifact cascade runs as on a merge. |
| Python `(kind, attribute)` | The cached narrowed submission if present, else `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` with `coalesced=True` and `widened=True`, as the coalesced pass submits a widened target, so the chain continues. |
| `widen` marker, scope `all` | Full regeneration of that repository's definitions: both blanket triggers with `include_repository_ids=[repository]`, plus every Python computed attribute whose transform that repository owns, over its whole kind. |
| `widen` marker, scope `terminals` | The artifact blanket trigger, with `include_repository_ids=[repository]`. The release then continues: it dispatches the generator items and the Python items of the window as the rows above say. The trigger covers the artifact items of the window, so they need no separate dispatch. |

A marker of scope `all` covers every held item, so its release dispatches nothing else. The marker
that `merge_git_repository` holds after a failed first write (R3) releases the same way. A marker of
scope `terminals` covers only the artifact definitions. If its release stopped after the trigger,
the clear would remove the held generator items and Python items without a dispatch (FR-016).

An identifier that no longer resolves, for example a deleted definition, turns the release into the
full `widen` release of that repository, as for scope `all` (FR-016). The PRD names this as "a
further named fallback reason": `FullRegenerationReason.HELD_SET_UNRESOLVED` is added beside the
four that exist.

**The reason that a `widen` release logs.** Each marker carries the `FullRegenerationReason` of the
code that set it (R9, R3): one of the four that exist, the new `TERMINAL_SELECTION_FAILED`, or the
new `UNHELD_FOLLOW_UP`. The release of a marker logs that reason. It logs `HELD_SET_UNRESOLVED` only
when a held identifier does not resolve.

**Every release dispatch passes through the barrier, with `releasing` set to the repository being
released.** Its own candidates are admitted, and a candidate owned by another repository that is
still pending is held under that repository.

**Why dispatch, then clear.** No step can be atomic across the graph and the orchestrator. Clearing
first and failing to dispatch drops the work (FR-016). Dispatching first and failing to clear
repeats it. The next clearing then releases again, which over-executes. That is the accepted
direction, and FR-015 and SC-004 state it.

**Why clear by sequence.** A merge can append an entry, and its follow-up can hold an identifier
again, while the release runs. A clear by value would drop the repeated hold. A clear by a range of
sequences would remove the items of another live lease (see "Why a set and not a range").

**Why inline and not a separate workflow.** A separate release workflow whose submission fails
leaves a held set that nothing would release. The lease and the recovery check of R20 cover the
crash cases of the inline release.

---

## R11. No other path imports a pending destination

**Decision**: three paths change while the store reports a pending delivery for the repository.

| Path | Change |
|---|---|
| `InfrahubRepository.collect_pending_imports`, the active loop | Removes the repository's default branch from the branches to pull. Removes from the new **and** the updated branches every remote branch that a pending entry names as its source. Logs both once per cycle. `_collect_staging_imports` keeps the full list, because a staging repository is never queued. |
| `git/tasks.py::bootstrap_local_repository` | Skips the seed import of the default branch after a fresh clone, and logs it. The clone itself proceeds. |
| `graphql/mutations/repository.py::ProcessRepository` | Refuses on **every** branch, with a message that names the pending delivery. |

**Why the default branch.** The import is desired-state: it deletes the repository-owned objects
that are not in the imported commit. If the remote destination advanced during an outage, an import
of the remote head would delete the objects of the pending merges. They would come back at the
delivery, possibly with new ids. The delivery imports the remote commits itself (R4 step 11).

**Why the kept source branches, new and updated.** R12 keeps a remote source branch whose Infrahub
branch was deleted. With `git.import_sync_branch_names` empty, which is the default, a worker with
no local branch of that name would import it as a new Infrahub branch at the next cycle. A worker
that kept its local branch sees a developer's push to it as an update instead, and `pull` would then
record a commit on a deleted Infrahub branch. That graph error propagates out of
`collect_pending_imports` and stops the synchronisation cycle of every later repository.

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

**The success path.** `BRANCH_DELETE` and the first attempt are submitted together. Both take the
repository lock, so one runs first:

- The guard first: it flags the entry and skips the deletion. The attempt deletes the branch at R4
  step 13.
- The attempt first: it settles the queue before it releases the lock (R4 step 14). The guard then
  finds no entry and deletes the branch itself, as today.

Either way the end state is today's, without the race.

**A gap the guard cannot close.** The guard protects a branch only once an entry names it. When the
merge's record fails after all its bounded retries (R3), no entry exists until the delivery writes
it at R4 step 0. If the deletion after merge runs in that window, it deletes the remote source
branch. The delivery's source check (R4 step 5) then marks the delivery `source-discarded`, and a
user must abandon it and deliver the merge by hand. The window needs the delivery-state store to
fail for longer than those retries while the deletion flow, which also writes to the database,
still succeeds, so it is narrow. Closing it would need the guard to refuse every deletion whose
branch head the remote default branch does not hold yet. That also keeps the branches of merges
that were never delivered, which the synchronisation then imports again as new Infrahub branches.
This plan accepts the gap and documents it.

**After an abandonment.** The abandonment sends `RefreshGitRepositoryBranchDeleted` for every
abandoned entry that carried the flag (R8 step 2), so every worker drops its local branch. No entry
names the remote branch any more. With `git.import_sync_branch_names` empty, the next
synchronisation on any worker imports it as a new Infrahub branch. That gives the user the
undelivered content back as a branch, which the user can merge again through Infrahub, and that
merge is delivered as a new entry. **To confirm with the product owner**: the alternative is to keep
the branch on the remote only.

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

**Gate.** Plan part L waits for the rewrite classification of IFC-3210. Without it, a rewrite of the
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
  in order. After an abandonment it shows the last record.
- Two items in `entities/repository/ui/repository-menu-section.tsx`: "Retry push" and "Abandon
  pending push". Both are disabled without `permission.update`, and as the table "Actions by status"
  of [data-model.md](data-model.md) says.
- An abandonment confirmation modal that lists the merges it will drop, says that nothing is
  removed from the remote, and says that repository objects of the dropped merges can stay on the
  default branch until a reimport.
- The nine attributes are left out of the main attribute list, the "extra" toggle
  (`object-data-display.tsx`) and the list-view column picker (`get-column-candidates.ts`) for
  `CoreRepository`, so the inherited copy of a non-default branch is never shown as current.
- Each mutation follows the existing three-file pattern: `api/*-from-api.ts` with gql.tada,
  `domain/use-cases/*.ts`, and `ui/queries/*.mutation.ts`. The task link toast and the query
  invalidation follow `import-current-commit`. Both mutations are sent with the default branch as
  their branch context, whatever branch the user selected, because the backend refuses any other.
- After an abandonment, the section names the recorded commit and says that the default branch can
  hold repository objects that the commit lacks. When the record shows a dropped owed import, it
  also says that the branch can lack objects that the commit holds. Both cases offer "Reimport
  current commit".

**Out of scope**: the per-branch status list, a signal on the proposed change or the repository
list, and the status vocabulary (INFP-671).

---

## R15. Test harness

**Unit, no database** (`backend/tests/unit/git/writeback/`, `backend/tests/unit/core/merge/`):

- the classifier across every row of R5, the flags included, a fetch outage, and a fetch and a push
  past their time limit;
- the scrubber;
- the queue model: append, idempotent enqueue, refusal of a removed id, snapshot removal, version;
- the held set: a repeated hold of the same identifier during a release survives the clear; two
  leases never cover one item; a lease over uncovered items with gaps never names the items of a
  live lease; an expired lease protects nothing, gives its items to the next lease, and is removed
  once it names none;
- the service against an in-memory `DeliveryGitPort` and an in-memory store: observation, the two
  checks, replay conflict, push failure and reset, the obligation saved before the record, a crash
  between the two, the import condition, the reset to H on the observation path, the settle under
  the lock, the release outside the lock, release then clear, and a release that fails once, whose
  task retry releases every item of the window under a new lease;
- the interleavings: an abandonment and a deletion guard that wait for the attempt find the entries
  already settled; a held-only run during a live lease does nothing;
- the barrier: partition, the atomic hold, the fast path, unknown owners, `releasing`, a state error
  that clears within the retries, fail-open after the last retry, the narrowed cache hit and miss,
  and two holds of one item with different members, which release both members;
- the retry condition and `final_attempt`;
- the recovery check against a fake `DeliveryRunQuery`: a run that waits in the queue, a run whose
  worker died, and a query that fails.

**Component, with a database**: the store's transitions and the lock time to live; `read_only`
keeping the attributes out of the update input; the branch-safety test (no delivery attribute in a
diff, never merged, the inherited copy on a new branch); the data-only skip (fork, trunk advances,
data-only merge, no entry); the enqueue retry, and the `widen` marker that `merge_git_repository`
holds after the last retry fails; the mutations refuse on another branch; a long queue of 200
entries.

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
- a lost attempt: the flow is killed after the snapshot, the test frees the repository lock as the
  deadlock cleanup does for a dead worker (R20), and the recovery check restarts it.

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
| `dev/knowledge/backend/git-integration.md` | Replace the two volatile sections ("not ordered against post-merge regeneration", "writeback direction has no reconciliation"). This spec's PR already corrected the second one to describe `develop` after `7d1bab3d1`; the implementation replaces both with the delivery design. Add the delivery queue, the barrier, the three import paths that wait, the recovery check, and the known limitation of branches forked during an outage. Add the two known limitations of the recovery (R20): a repository lock that a dead worker held waits for the deadlock cleanup, and a delivery run that stays in `PENDING` stops the automatic recovery. Update the known limitation on remote branch deletion. |
| `dev/knowledge/backend/selective-merge-regeneration.md` | The barrier, the new fallback reasons and the new place of `FullRegenerationReason`, the reason that a `widen` release logs, the two repository filters, and the narrowed cache. |
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

No new setting. The retry bounds, the enqueue retries of the dispatcher (R3), the read retries of
the barrier, the Git timeouts (fetch, push and local commands, R6), the stale bound and the cache
time to live are constants in `git/writeback/constants.py`, as `WEBHOOK_SEND_RETRIES` is in
`webhook/constants.py`.
A setting would be configurability for a hypothetical need (Principle VII).

---

## R19. Coordination with IFC-3210 and IFC-3002

- **The ancestry question.** IFC-3210 adds `git/divergence/gateway.py` for it. Whichever epic lands
  first adds the primitive, with one contract: `False` only for a missing object, a raise for every
  other failure. The other epic reuses it.
- **The merge-path check.** IFC-3210's FR-005a makes `InfrahubRepository.merge` refuse a diverged
  source or destination. After plan part C, `merge_git_repository` no longer calls `merge`: the
  service replays instead, and its checks of R4 steps 3 and 5 are that refusal for the replay.
  IFC-3210's merge-path task therefore moves into the service. `merge` stays only for
  `InfrahubRepository.rebase`, which has no caller, and for the live-remote tests of #10465. Both
  methods can be removed once those tests move to the service.
- **The synchronisation path.** Both epics change `collect_pending_imports`. R11's exclusion runs
  before the sibling's classification.
- **The SDK.** One PR for both epics (R17).
- **IFC-3002.** `_resolve_python_targets` and `computed_attribute_setup_python` gain the barrier
  filter. Whoever changes them next must keep it.

---

## R20. Liveness and recovery (FR-027)

**Decision**: a separate attribute, `delivery_progress`, a small JSON value, keeps `last_progress_at`,
`attempt_started_at` and `retry_due_at`. They live outside `delivery_queue`, so a progress write
never rewrites the queue (R23).

`last_progress_at` moves at every enqueue, attempt start and recorded failure, and at each step
boundary of an attempt: after the fetch, after the push, after the record, and before and after the
import.

A pending delivery is **stale** when all five hold:

1. its status is `pending`;
2. no automatic retry is due in the future;
3. `last_progress_at` is older than `STALE_AFTER`, 15 minutes, which exceeds the longest retry delay
   plus the fetch and push timeouts;
4. the repository lock is free (`lock.py::InfrahubLock.locked`);
5. the orchestrator holds no delivery run of the repository that waits to start, that is, no run in
   a state of type `SCHEDULED` or `PENDING`. The type `SCHEDULED` includes the states
   `AwaitingRetry` and `Late`.

Condition 4 covers what the timestamps cannot: a long import, which is not a Git command and has no
bound, and an attempt that waits behind a synchronisation for the lock.

Condition 5 covers a run that waits in a busy work queue. Such a run holds no lock and writes no
progress. Without condition 5, the check would count it as lost and submit one more run every
`STALE_AFTER` while the backlog lasts, and each extra run would make the backlog longer.

**How the five conditions combine.** All five must hold. Conditions 1 and 2 read the state: work
waits, and no retry chain owns it. Condition 5 reads the orchestrator: no run waits to start.
Conditions 3 and 4 judge a run that a worker took, so condition 5 leaves out the state `RUNNING`:

- A run whose worker is alive holds the repository lock, waits for it behind another holder, or
  writes progress at each step. Condition 3 or 4 then fails, and the delivery is not stale.
- A run whose worker died writes no more progress. Once the lock is free, conditions 3 and 4
  hold, also while the orchestrator still shows the run as `RUNNING`, and the check counts the run
  as lost. The first limitation below says when the lock of a dead worker becomes free.
- A run that a worker started a moment ago, and that has not taken the lock yet, can count as lost
  for that moment. The extra run that the check then submits waits for the lock, then finds nothing
  to do or delivers what remains.

**Known limitations of the recovery.** These cases delay or stop it:

- **A fetch or a push that hangs.** Its time limit does not stop it (R6). The attempt keeps the
  repository lock, so condition 4 fails, the recovery check submits nothing, and a manual retry
  waits for the lock too. The delivery stays `pending` until the connection ends. This is the open
  point of R6, for a later story.

- **A repository lock that a dead worker held.** The repository lock has no time to live
  (`lock.py::InfrahubLockRegistry.get`, R2). A worker that dies while it holds the lock leaves it
  held. Condition 4 then fails, so the recovery check submits nothing, and a manual retry waits for
  the lock too. This design adds no recovery of its own for that lock. The existing deadlock
  cleanup, `locks/tasks.py::clean_up_deadlocks`, runs every minute. It deletes a lock whose holder
  left the active-worker set, once the lock is older than `cache.clean_up_deadlocks_interval_mins`,
  15 minutes by default. A delivery attempt stamps its progress after it takes the lock, so the lock
  of a dead attempt is free at most about one minute after the delivery is stale. A lock that a
  later holder took, such as a synchronisation, keeps the recovery waiting until that lock is 15
  minutes old. A larger setting delays the recovery by the difference.
- **A deadlock cleanup that frees a lock from a live holder.** `dev/knowledge/backend/async-tasks.md`
  records that the deadlock cleanup can delete a lock that a live holder still has, after a short
  loss of connection between that worker and the cache. Two delivery attempts can then run Git work
  for the same repository at the same time. Each one works in its own worker's clone, and the state
  lock still serialises every store transition. The worst outcome is a second push that the remote
  rejects as a non-fast-forward, which is retried, or a second attempt that observes the first
  one's delivery and records nothing new. This is a limitation of the lock layer, not of this
  design.
- **A run that stays in `PENDING`.** Condition 5 counts a run in a state of type `PENDING` as a run
  that waits to start. A delivery run that the orchestrator never starts therefore stops the
  automatic recovery for as long as it stays in that state. The `crash-zombie-flows` automation does
  not end such a run, because it watches a run only after a heartbeat or an `AwaitingRetry` event
  (`trigger/system.py::TRIGGER_CRASH_ZOMBIE_FLOWS`). A manual retry still works: it submits a new
  run, which does not wait for the stuck one (R7).

**The recovery check.** It runs from the loop of `git/tasks.py::sync_remote_repositories`, for every
repository, before the bootstrap and whatever the outcome of the sync, under its own guard. A check
inside `sync_repository_from_origin` would be skipped whenever one branch fails to synchronise,
because that function catches the error that a failing branch raises. The check submits
`GIT_REPOSITORY_DELIVERY_RETRY` with a system context and the delivery tags below, then moves
`last_progress_at`, when:

- the delivery is stale; or
- held items wait that no live release lease covers, `last_progress_at` is older than
  `STALE_AFTER`, and no delivery run of the repository waits to start (condition 5).

The `touch` after a submission bounds it to one submission per `STALE_AFTER` per repository. While
the submitted run waits to start, condition 5 also stops a second submission. A submission that
finds an attempt running waits for the lock and then finds nothing to do.

**How the check finds the delivery runs.** Every delivery run carries two tags from its submission:

- the repository's node tag, `infrahub.app/node/<repository id>`. It is
  `workflows/constants.py::WorkflowTag.RELATED_NODE`, the tag that `workflows/utils.py::add_tags`
  writes for `nodes`;
- a marker, `infrahub.app/repository-delivery`, from a new member
  `WorkflowTag.REPOSITORY_DELIVERY`. The node tag alone also matches the other runs of the
  repository, such as its synchronisation and import runs, and any of them that waits would then
  stop the recovery.

Three submitters pass these tags to `submit_workflow`: the dispatcher, for the
`GIT_REPOSITORIES_MERGE` run of an `active` repository (R3), and the retry mutation and the
recovery check, for `GIT_REPOSITORY_DELIVERY_RETRY`. One function,
`git/writeback/runs.py::delivery_run_tags`, builds the tags for all three. A tag that the flow adds
when it starts is too late, because a run that waits in the queue has not started.
`services/adapters/workflow/worker.py::WorkflowWorkerExecution.submit_workflow` passes `tags` to
`run_deployment`. `WorkflowLocalExecution` ignores them, but it runs the flow at once, so no run
waits.

**The query.** The port `DeliveryRunQuery.has_queued_run(repository_id)` answers condition 5. Its
Prefect adapter makes one `read_flow_runs` call with `limit=1`, for the runs that carry both tags
and have a state of type `SCHEDULED` or `PENDING`. The check asks it last, and only when every other
condition of a trigger holds. A repository with no work to recover, or with recent progress, costs
no query. If the query fails, the check submits nothing for that repository in this cycle, logs
the failure at warning level, and asks again at the next cycle. It never submits without an answer.

**Why this is not an unbounded retry.** A stale delivery has no failure to retry: its attempt was
lost to a worker restart, a lost submission or a killed process. The new attempt is a first attempt
with its own bounded chain. If it fails on policy, the status becomes `action-required` and the
check stops.

**Manual retry.** The retry mutation is allowed in every status other than `none` (R7).

**Rejected: a heartbeat inside the import.** It would need a callback inside
`import_objects_from_files`, a large unrelated method. The lock condition covers the same case with
one read.

**Rejected: a `RUNNING` run counts as live too.** A run whose worker died would then stop the
recovery until the `crash-zombie-flows` automation (`trigger/system.py::TRIGGER_CRASH_ZOMBIE_FLOWS`)
marks it `CRASHED`. Conditions 3 and 4 already judge a run that a worker took, with no such
dependency.

---

## R21. Observability

**Decision**:

- Every delivery, retry and abandon run is tagged with the repository node and the default branch,
  so it appears in the repository's task list, as the synchronisation flow's runs do.
- A delivery run gets two tags at submission, not only inside the flow: the repository's node tag
  and the delivery marker, from `git/writeback/runs.py::delivery_run_tags` (R20). The recovery
  check then finds a run that waits in the queue. When the flow starts, it adds the other tags
  through `workflows/utils.py::add_tags`, which keeps the tags that the run already has.
- Every store transition logs one line with the repository, the entry ids, the status, the cause and
  the attempt number.
- A run ends `Failed` for the outcomes `failed` and `unreplayable`, and `Completed` for `delivered`,
  `observed` and `nothing-pending`.
- The barrier logs each hold at info level, with the repository and the held identifiers, and each
  fail-open at error level, after the last retry, with the branch and the repositories of the
  candidates.
- The branch merge flow's run log gains one line per queued repository, so the user who merged sees
  that a push is pending.
- The dispatcher logs a failed enqueue at error level after the last retry, with the repository and
  the entry id.
- `merge_git_repository` logs a failed enqueue of R4 step 0 at error level after the final attempt,
  with the repository, the source branch and the source commit (R3).

---

## R22. Rollback

A code revert is safe for the data: the nine attributes are additive, and the old code ignores
them. Two effects remain after a revert, and the release note says so:

- Entries still queued are never delivered by the old code. An operator delivers them by hand, or
  merges again.
- Held regeneration is never released. An operator runs a full regeneration of the default branch
  after the revert.

**Rejected: a setting that falls back to `InfrahubRepository.merge`.** It doubles the merge path to
test, for a rollback that a code revert already provides (Principle VII).

---

## R23. Growth of the stored history

Every change of the queue rewrites the whole `delivery_queue` value, and the temporal history keeps
every version. The progress timestamps live in `delivery_progress`, so a progress write or a
recovery touch never rewrites the queue. N merges during one outage therefore store about N²/2
entries in the history of the queue attribute. An entry is about 250 bytes, so 100 merges store about 1.2 MB, and 1,000 merges about
125 MB. Outages that long are not expected, and the component test of R15 covers a queue of 200
entries. If it becomes a concern, the entries can move to one attribute per transition, which this
plan does not need.
