# Research: Git remote writeback failure handling

**Feature**: `dev/specs/ifc-3220-writeback-failure-handling`
**Date**: 2026-10-02

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
| 2 | `core/merge/post_merge.py::PostMergeDispatcher.run_follow_ups` | Submits, in order: the repository merges, IPAM reconciliation, proposed-change cancellation, `BRANCH_DELETE` when `main.delete_branch_after_merge` is set, and `BRANCH_MERGE_POST_PROCESS`. Every submission is fire-and-forget (`run_deployment(..., timeout=0)`). |
| 3 | `core/merge/repository_merge_dispatcher.py::RepositoryMergeDispatcher.merge_core_repositories` | One `GIT_REPOSITORIES_MERGE` per `CoreRepository` of the source branch that exists on main, is not `INACTIVE`, and either the branch syncs with Git or the repository is `STAGING`. No `context` is passed. |
| 4 | `git/tasks.py::merge_git_repository` | No retries. Takes the repository lock, calls `InfrahubRepository.merge`, ignores its return value, then sends `RefreshGitFetch`. A raise skips the broadcast and fails the run. |
| 5 | `git/repository.py::InfrahubRepository.merge` | Merge into the destination worktree, then push, then `create_commit_worktree`, then `update_commit_value`. A failed push or a failed record resets the worktree to the pre-merge commit. |
| 6 | `core/merge/post_merge.py::PostMergeDispatcher.dispatch_events` | Runs the coalesced recompute through `MergeRecomputeCoordinator`, inside the `branch-merge` flow. |
| 7 | `core/branch/tasks.py::post_process_branch_merge` | Runs `PostMergeRegenerationDispatcher.dispatch` for generators and artifacts. |

A merge always targets Infrahub's default branch. `InfrahubRepository.rebase` has no caller, so no
other branch ever receives a writeback.

### The push

- `InfrahubRepository.push` sends `HEAD:refs/heads/<mapped branch>`.
- A transport failure raises `GitCommandError`, which `_raise_enriched_error_static` turns into
  `RepositoryConnectionError`, `RepositoryCredentialsError`, `RepositoryPermissionError` or a plain
  `RepositoryError`. `is_write_operation=True` is passed, so a 403 maps to the permission error.
- A per-ref rejection raises a plain `RepositoryError`. Only the wording of
  `git/repository.py::_describe_push_rejection` tells a policy denial from a non-fast-forward.
- A push failure never writes `operational_status`. Two tests pin that, and this work keeps it.
- Nothing captures the remote's own `remote:` lines. A GitHub branch-protection refusal explains
  itself only in those lines.

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
- Nothing holds or defers regeneration today.

### Branch deletion

- `core/branch/delete_coordinator.py` submits `GIT_REPOSITORIES_DELETE_BRANCH` when
  `git.delete_git_branch_after_merge` is set and the branch syncs with Git.
- `git/tasks.py::git_branch_delete` deletes the remote branch, gated only on
  `origin_has_branch`, which reads the local remote-tracking refs.
- Nothing orders that deletion after the repository merge.

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
"CoreRepository / CoreGenericRepository" and leaves the choice open. The sibling epic puts its four
attributes on the generic because both kinds record rewrites. Here only one kind delivers.

**Why the default branch only.** Every merge targets Infrahub's default branch (R0). The default
branch has no origin branch, so a read there never falls back to another branch.

### The read-inheritance consequence (FR-025)

`core/attribute.py::BaseAttribute.get_create_data` creates the attribute vertex of a LOCAL attribute
on an agnostic node on the global branch, and value edges are written on the branch of the write.
A read on branch B resolves B, then B's origin branch up to `branched_from`, then global. A branch
created while main has a pending delivery therefore reads main's delivery state as it was at the
fork, for ever, until B is rebased. The sibling data model records the same behaviour for its
record.

**Decision**: nothing in the backend reads the state on another branch. The store reads and writes
the default branch, whatever branch the caller runs on. In the frontend, the delivery attributes are
left out of the generic attribute list and rendered in a section of their own, which always queries
the default branch (R14). Each attribute's description says that only the default branch holds the
live value.

**Rejected**: clearing the state when a branch is created. It adds a write to every branch creation
on a path unrelated to Git, and the sibling rejected the same idea for the same reason.

---

## R2. How the state is written, and the two locks

**Decision**: one Repository-pattern class, `WritebackIntentStore`, is the only read and write path.
It takes `db` and the lock registry in its constructor. It writes through the core node API
(`NodeManager.get_one` on the default branch, then `node.save(db=..., fields=[...])`), never through
the SDK.

**Why the core node API.** Node mutation events are produced by the GraphQL mutation layer
(`graphql/mutations/main.py` calls `events/generator.py::generate_node_mutation_events`). A core
`node.save` emits none. A bookkeeping write therefore starts no automation, which is FR-026 and the
intent of the PRD note on ADR 0016. The sibling epic writes through the SDK and accepts a `live`
event per rewrite, because a rewrite is rare. A delivery-state write happens on every git-synced
merge, so the same trade-off does not hold here.

Every place that writes has database access: the merge flow, `post_process_branch_merge`, and the
git task workers (`git/tasks.py` already calls `get_database()`).

**Why one class.** FR-009 says no path may clear a pending delivery without a record. That rule can
only be enforced in one place. Each method of the store is one state transition, and the record and
the clear are one `save`.

### The locks

Two locks, always taken in this order:

| Lock | Name | Held by | Held for |
|---|---|---|---|
| Repository lock (exists) | `lock.registry.get(name=<repository name>, namespace="repository")` | The delivery attempt and the abandonment, which both touch Git. | The Git work. |
| Delivery-state lock (new) | `lock.registry.get(name=<repository id>, namespace="repository-delivery")` | Every store transition. | One read-modify-write. |

**Why a second lock.** The enqueue runs in the merge flow, and the barrier runs in the merge flow
(`dispatch_events`) and in `post_process_branch_merge`. Taking the repository lock there would make
a branch merge wait behind a periodic sync or a running delivery. The state lock is held for one
read and one write.

**Why the state lock is not optional.** Without it, this interleaving drops held work: the barrier
reads a non-empty queue; the delivery clears the queue and finds no held set; the barrier then
writes its held set, which nobody will release. Under the state lock the barrier's "queue is
non-empty, add to the held set" and the delivery's "take the held set, clear the queue" cannot
interleave.

**Rejected**: a compare-and-set query in Cypher. It is more code than a lock and it is not a pattern
this codebase uses for node attributes.

---

## R3. The queue entry, and when it is written

**Decision**: `RepositoryMergeDispatcher.merge_core_repositories` writes the entry before it submits
`GIT_REPOSITORIES_MERGE`, and passes the entry id in `GitRepositoryMerge`. The flow writes the same
entry again, idempotently by id, before its first attempt.

**What the entry holds** (FR-005):

| Field | Source |
|---|---|
| `entry_id` | A new UUID. |
| `source_branch` | The Infrahub source branch name. |
| `source_git_branch` | The remote branch, through `_get_mapped_remote_branch`. For a non-default branch this is the same name. |
| `source_commit` | `CoreRepository.commit` read on the **source** branch, which is what Infrahub imported and merged. |
| `merged_at` | The merge time. |

**Why the graph commit and not the worktree head.** The graph merge merged the objects imported at
that commit. Delivering exactly that commit keeps the remote content and the merged data aligned.
Today's merge reads the local worktree head, which normally equals it, but which a worker can hold
ahead of the import.

**Why the first write is in the merge flow** (FR-005a). The coalesced recompute runs in
`dispatch_events` right after `run_follow_ups`, and `post_process_branch_merge` is submitted at the
end of `run_follow_ups`. Both consult the barrier. An entry written by the delivery flow would arrive
after them, and the barrier would see an empty queue.

**Why the flow writes it again.** If the first write fails, `log_exception_guard` absorbs the error
and the merge carries on. The flow then still delivers the merge. Only the hold is lost in that
case, which is today's behaviour, and the failure is logged.

**Skipped when nothing can be delivered.** When the source commit equals the commit recorded for the
destination, the merge carries no repository content. No entry is written. This happens for every
git-synced branch that changed only data, since such a branch reads the trunk's commit.

**Rejected**: keying the queue on the Infrahub branch. The Infrahub branch can be deleted right
after the merge (`delete_branch_after_merge`), while the remote branch is protected by FR-011.

---

## R4. The delivery attempt

**Decision**: one component, `RepositoryWritebackService`, with one entry point, `deliver`. The
merge flow and the retry flow both call it (FR-007). It runs under the repository lock and works on
a snapshot of the queue taken at the start.

### The algorithm

1. Take a snapshot of the queue under the state lock. If it is empty, return. Mark the status
   `pending`.
2. Fetch the remote. Let **H** be the remote head of the destination, and **R** the commit recorded
   for the destination.
3. **Destination check** (FR-022). If R is not an ancestor of H, or is H, the destination was
   rewritten. Mark the queue unreplayable with the cause `destination-rewritten`. Push nothing.
   A worker that does not hold R locally treats it as rewritten, which is the safe reading.
4. **Observation** (FR-012). Drop from the replay every entry whose source commit is already an
   ancestor of H, or is H. The remote already holds it.
5. **Source check** (FR-020). For each remaining entry, the source commit must be an ancestor of the
   remote head of its source branch, or equal to it. If it is not, mark the queue unreplayable with
   the cause `source-discarded`. Push nothing. A missing remote branch fails the check too.
6. Reset the destination worktree to H. Merge each remaining source commit, in queue order, with the
   same `--no-ff` rule as today (`git.use_explicit_merge_commit`). On a conflict, abort, reset to
   the pre-attempt commit, and mark the queue unreplayable with the cause `replay-conflict`, naming
   the entry.
7. If any entry was replayed, push once. On a failure, reset the worktree to the pre-attempt commit
   (FR-002) and classify the failure (R5).
8. Let **M** be the final head. If H is not R, the remote holds commits Infrahub has not imported:
   create the commit worktree and import the repository objects at M on the default branch
   (FR-023). On an import failure, reset the worktree to the pre-attempt commit and mark the cause
   `import-failed`. The remote keeps M, and the next attempt observes it.
9. Create the commit worktree of M and record M (FR-001). On a failure, reset the worktree behind
   the remote. The next attempt observes the delivery and records it.
10. Release the held regeneration (R10).
11. Under the state lock, remove the snapshot's entries and the released held identifiers, set
    `last_delivered_commit` to M when something was pushed, and set the status `none` if the queue
    is now empty, otherwise `pending`. Entries appended during the attempt stay.
12. Send `RefreshGitFetch` pinned to M, as `merge_git_repository` does today.

**Why the checks run before the replay.** A worker can hold a discarded commit in its object
database long after the remote dropped it. A replay that merges it and pushes would restore it. A
leaked credential is the case that matters (SC-007).

**Why the destination check refuses rather than rebases.** A source branch forked from the old trunk
contains the old trunk. Merging it onto the rewritten trunk restores every discarded trunk commit.
This is IFC-3210's FR-005b, and the sibling's merge path refuses for the same reason.

**Why the import happens only when H is not R.** When the remote did not move, M is R plus the
merged branches, and the graph already holds every object of M. An import would cost a full import
for nothing. When the remote moved, nothing else will import M: the synchronisation compares local
and remote Git, which then agree.

**Why one push for the whole queue.** FR-007 asks for it, and it gives the remote one update for an
outage, not one per merge.

**Rejected: storing the merge commit as a Git bundle.** The PRD measured and rejected it: it becomes
undeliverable as soon as the remote destination advances, and delivering it then needs a
force-push.

### The Git primitives

All new Git calls sit behind a port, `DeliveryGitPort`, so that the service is unit-testable without
Git (PRD testing decisions). The concrete adapter wraps `InfrahubRepository`.

| Port method | Built on |
|---|---|
| `fetch()` | `InfrahubRepositoryBase.fetch` |
| `remote_head(branch)` | `get_commit_value(branch_name=..., remote=True)` |
| `is_ancestor(ancestor, descendant)` | `git merge-base --is-ancestor`. Exit 1 means no. A missing object means no. Shared with IFC-3210 (R19). |
| `replay(destination, base, commits)` | `reset --hard`, then `merge` per commit, aborting on a conflict. |
| `push(destination)` | `InfrahubRepository.push`, extended by R5. |
| `reset(destination, commit)` | `_reset_to_pre_merge_commit`, which never raises. |
| `import_at(commit)` | `create_commit_worktree` plus `import_objects_from_files` on the default branch. |
| `record(commit)` | `create_commit_worktree` plus `update_commit_value`. |

---

## R5. Classifying a push failure, and keeping the remote's words

**Decision**: a pure function, `classify_delivery_failure(error) -> DeliveryFailure`, in
`git/writeback/classifier.py`. It reads the exception type first and the text only where the type
cannot say. `push` raises a new typed error for a per-ref rejection, and carries the remote's own
lines.

| Exception | Cause | Retried automatically |
|---|---|---|
| `RepositoryConnectionError`, except a TLS failure | `remote-unreachable` | Yes |
| `RepositoryConnectionError` with a TLS failure | `certificate` | No |
| `RepositoryCredentialsError` | `credentials` | No |
| `RepositoryPermissionError` | `permission` | No |
| `RepositoryPushRejectedError` with reason `policy` | `permission` | No |
| `RepositoryPushRejectedError` with reason `non-fast-forward` | `remote-advanced` | Yes. The remote moved between the fetch and the push, and the next attempt fetches again. |
| `RepositoryPushRejectedError` with reason `unknown` | `unclassified` | No |
| Any failure after a successful push | `record-failed` | Yes (FR-004) |
| A replay conflict | `replay-conflict` | No |
| Anything else | `unclassified` | No |

The cause list is closed and is an enum (Principle III). [data-model.md](data-model.md) has it.

**Why a typed error for per-ref rejections.** Today the policy and non-fast-forward cases are one
`RepositoryError` and differ only in wording. The retry decision must not depend on parsing our own
message. `RepositoryPushRejectedError` subclasses `RepositoryError`, so every existing
`except RepositoryError` keeps working, and its message keeps today's wording, which
`test_git_live_remote.py` asserts.

**Why the TLS case needs a subtype.** A certificate failure is a `RepositoryConnectionError` today,
told apart only by its message. Retrying it is pointless. The plan adds
`RepositoryTLSError(RepositoryConnectionError)`. The operational-status map in
`InfrahubRepositoryBase._raise_enriched_error` looks the status up by exact type, so it must gain
the subtype, or a TLS failure would move from `ERROR_CONNECTION` to `ERROR`.

### The remote's own message (FR-018)

GitPython's `Remote.push` accepts a `progress` handler. `git/util.py::RemoteProgress` keeps every
stderr line that is not a progress line in `other_lines`, and lines that start with `error:` or
`fatal:` in `error_lines`. A server-side message arrives as `remote: ...` lines, which land in
`other_lines`. Both examples below match no progress pattern:

- Gogs pre-receive hook: `remote: branch main is protected`
- GitHub protection: `remote: error: GH006: Protected branch update failed for refs/heads/main.`

**Decision**: `push` passes a `RemoteProgress` and joins the `remote:` lines, in order, into the
typed error. The delivery records them verbatim as the error message. When the remote sent no such
line, the message is the ref summary, as today.

**Rejected**: paraphrasing the remote. User story 3 of the PRD asks for the remote's own words.

---

## R6. The automatic retry

**Decision**: the delivery attempt is a Prefect `@task` with `retries=3`,
`retry_delay_seconds=[30, 120, 300]` and a `retry_condition_fn` that retries only a failure
classified as automatically retryable (R5). The task takes the repository lock inside each attempt.

**Why a task.** Prefect 3.8 supports `retry_condition_fn` on tasks only, not on flows. Every
existing `retries=` in the backend is on a task or on the webhook flow, which has no condition.

**Why these bounds.** About seven and a half minutes cover a blip, a load-balancer failover or a
Git server restart. The PRD assumes that real outages last days, so a longer automatic window buys
nothing and holds a worker slot.

**Why the lock is taken inside the attempt.** A retry delay holds no lock, so a periodic sync or a
manual retry can run between two attempts.

**Status while waiting**: the status stays `pending`, and the last cause and message are recorded,
so a user sees "pending, last attempt failed: remote unreachable". After the last attempt fails the
status becomes `action-required` (User Story 4).

**Rejected: retrying from the periodic synchronisation.** That is an unbounded automatic retry,
which FR-004 forbids.

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
itself.

**Decision**: both mutations require the permissions that an update of the repository on the
default branch requires:

- object `update` on `CoreRepository`, with `ALLOW_DEFAULT`, checked as
  `RecomputeComputedAttribute` and `ReadOnlyRepositoryImportLastCommit` check it;
- the global `manage_repositories` permission, which `RepositoryManagerPermissionChecker` requires
  for a repository CRUD mutation and which the frontend reports as `permission.update`;
- `edit_default_branch`, which `DefaultBranchPermissionChecker` already enforces for any mutation
  sent on the default branch. The frontend sends both mutations on the default branch.

**Why all three.** A retry records a commit on the default branch, and an abandonment can import
there (R8). The user needs exactly what editing the repository on the default branch needs. The UI
gating reads `MANAGE_REPOSITORIES`, and the backend check then agrees with it.

**Governance sign-off.** The delivery uses the repository's stored credential, not the acting
user's. A permitted user can therefore cause a push that the user could not personally make. A
proposed-change merge already has that property. The plan states it so it is signed off and not
inherited silently.

### Availability

The mutations read the state before they submit, and refuse with a `ValidationError` when:

- nothing is pending (both);
- the queue version named by an abandonment differs from the current one (abandon);
- the repository is read-only or `STAGING` (both).

The workflows check again under the locks, because the state can change between the mutation and
the run. This mirrors ADR 0014, where the mutations "re-check availability at execution time to
reject a stale action".

**Why the abandonment is a workflow too.** It needs Git and a worker: it re-imports at the recorded
commit (R8) and must not interleave with a running attempt, so it takes the repository lock.

**Rejected: ADR 0014's generic task actions.** Those act on a task run. Here the subject is the
repository's queue, which outlives every task run, so the action belongs on the repository.

---

## R8. The abandonment

**Decision**: `WritebackAbandoner.abandon(repository, queue_version, actor)`, run by the flow
`git-repository-delivery-abandon` under the repository lock.

1. Under the state lock, read the queue. Refuse when the version differs, or when nothing is
   pending.
2. Import the repository objects at the recorded commit R on the default branch (FR-024).
3. Release the held regeneration (R10).
4. Under the state lock, in one save: remove the snapshot's entries, write the abandonment record
   (entries, account id and name, time), remove the released held identifiers, and set the status.

**Why the import.** The graph merge put the abandoned merges' repository objects on the default
branch. R does not contain them. Without the import they stay until some later import removes them
at an arbitrary time, and the release in step 3 would run those definitions against files that do
not have them. The import is desired-state, so it removes exactly what R lacks.

**What the abandonment does not do.** It never touches the remote, and never deletes a remote
branch. If a push was accepted while its recording failed, the remote keeps the content, and the
synchronisation imports it once the queue is empty.

**Why the record is one attribute and not a log.** The temporal history of the node keeps every
earlier value of the attribute, and `updated_by` of the edge names the writer. One value answers
the common question, "what was dropped last, and by whom". A full log would need its own retention
and its own permission model.

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
with the id of the repository that owns it. On any branch other than the default branch, or when no
repository has a pending delivery, it returns every candidate after one read.

### Consultation points

| Point | Candidates | Owner from |
|---|---|---|
| `PostMergeRegenerationDispatcher.dispatch`, on the plan, before `_dispatch_plan` | generator runs, artifact generations | `generator_definition.repository_id`; a new `RequestArtifactDefinitionGenerate.repository_id` |
| `PostMergeRegenerationDispatcher._submit`, after the generator cascade reselects artifacts | artifact generations | as above |
| `PostMergeRegenerationDispatcher._full_regeneration`, and the flag-off path in `post_process_branch_merge` | "every definition of a repository" | see below |
| `core/merge/recompute_coalescing.py::_resolve_python_targets`, used by `MergeRecomputeCoordinator` and `RecomputeChainSubmitter` | Python computed attributes as `(kind, attribute)` | a new owner map from the Python target source |

### The artifact request gains its repository

`RequestArtifactDefinitionGenerate` gains `repository_id: str | None = None`.
`ArtifactSelector._build_request` fills it from `ProposedChangeArtifactDefinition.repository_id`,
which it already holds. The field is optional, so a run queued by the previous code still
validates. It crosses a flow boundary, which `dev/guidelines/backend/prefect-payloads.md` allows for
an identifier.

### The Python owner map

`GatheredPythonReadSets` drops the repository of each transform. It keeps it instead, and the
Python target source exposes `owner_of(kind, attribute) -> str | None`. The barrier consults it
after `_resolve_python_targets`, so it filters both a resolved result and the widened failsafe.

When the owner of a target is unknown while some repository has a pending delivery, the barrier
holds the target under every pending repository. Each release then runs it, which over-executes
and never skips.

### The full-regeneration fallback

`submit_full_regeneration` submits the two blanket triggers, which take a branch and enumerate every
definition. When a repository has a pending delivery, the barrier:

1. holds a `widen` marker for that repository, which releases as a full regeneration (R10);
2. submits the blanket triggers with a new optional parameter, `exclude_repository_ids`, naming the
   pending repositories.

With no pending delivery, the triggers are submitted with no new parameter, byte for byte as today,
which keeps the promise of ADR 0012 that the flag-off path is the blanket path exactly.

`git/tasks.py::generate_artifact_definition` and `generators/tasks.py::run_generator_definition`
gain `exclude_repository_ids: list[str] | None = None` and skip the definitions those repositories
own.

### The atomic hold

The barrier holds a repository's candidates only after it confirms, under the state lock, that the
repository's queue is still non-empty. When the delivery cleared the queue in between, the
candidates are dispatched. Together with step 11 of R4, this is what makes the barrier race-free.

### Holding is the normal path for a git-synced merge

`dispatch_events` runs right after `run_follow_ups` in the merge flow, a few milliseconds after the
first delivery attempt was submitted. For a merge of a git-synced branch that carries repository
changes, the coalesced pass will nearly always see a non-empty queue. The Python computed attributes
of that repository's transforms are then held and released as whole-kind recomputes, where today
they would be narrowed to node ids.

This is the PRD's stated cost: "over-regenerating within the held definitions only". It is stated
here because the PRD frames the hold as the failure path, and reviewers should know it is the normal
path for this kind of merge. Two facts bound it: R3 queues nothing for a branch that changed only
data, and a merge that changes a transform recomputes its attributes over the whole kind anyway.

**Rejected: holding the narrowed selection when the delivery succeeds at once.** It would persist
member and node id lists, which scale with the data, in a graph attribute, and FR-014 forbids it.

**Rejected: waiting for the first attempt before the follow-ups.** It would delay every git-synced
merge by the Git round trip, and by minutes when the remote is down.

---

## R10. The release

**Decision**: the release runs inline, at the end of a delivery (R4 step 10) or an abandonment
(R8 step 3), through a component, `HeldRegenerationReleaser`, behind a port of the service. It
dispatches first and clears second, by snapshot.

| Held identifier | Released as |
|---|---|
| Artifact definition id | `RequestArtifactDefinitionGenerate` with no `members` and no `limit`, through `_dispatch_plan`. |
| Generator definition id | `RequestGeneratorDefinitionRun` with no `target_members`, through `_dispatch_plan`, so the generator-to-artifact cascade runs as on a merge. |
| Python `(kind, attribute)` | `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` with `coalesced=True` and `widened=True`, as the coalesced pass submits a widened target, so the chain continues. |
| `widen` marker | Full regeneration: the blanket triggers, plus every Python computed attribute whole-kind. |

An identifier that no longer resolves, for example a deleted definition, turns the release into a
full regeneration (FR-016). The PRD names this as "a further named fallback reason":
`FullRegenerationReason.HELD_SET_UNRESOLVED` is added beside the four that exist.

**Every release dispatch passes through the barrier, with `releasing` set to the repository being
released.** Its own candidates are admitted, and a candidate owned by another repository that is
still pending is held under that repository. A full regeneration therefore never runs another
pending repository's definitions.

**Why dispatch, then clear.** No step can be atomic across the graph and the orchestrator. Clearing
first and failing to dispatch drops the work (FR-016). Dispatching first and failing to clear
repeats it. The next clearing then releases again, which over-executes. That is the accepted
direction, and FR-015 and SC-004 state it.

**Why clear by snapshot.** A merge can append an entry, and its follow-up can add held identifiers,
while the release runs. A wholesale clear would drop both.

**Why inline and not a separate workflow.** A separate release workflow whose submission fails
leaves a held set behind an empty queue, which nothing would ever release.

---

## R11. The synchronisation does not advance a pending destination

**Decision**: `InfrahubRepository.collect_pending_imports` removes the repository's default branch
from the branches to pull when the store reports a pending delivery, and logs it once per cycle.
Every other branch synchronises as usual.

**Why.** The import is desired-state: it deletes the repository-owned objects that are not in the
imported commit. If the remote destination advanced during an outage, a synchronisation would pull
and import the remote head, which does not contain the pending merges, and delete their objects
from the default branch. They would come back at the delivery with new ids. The delivery imports
the remote commits itself (R4 step 8).

**The other import path.** `ProcessRepository` ("Reimport current commit") imports at the current
commit on a branch. On the default branch with a pending delivery it would delete the same objects.
The mutation refuses with a message that names the pending delivery.

**Cost.** One store read per repository per synchronisation cycle.

**Interaction with IFC-3210.** The sibling adds reconciliation in the same method. A rewrite of the
destination during an outage is then not reconciled until the queue clears. The delivery attempt
meanwhile refuses with `destination-rewritten` (R4 step 3), the user abandons, and the
reconciliation runs at the next cycle.

---

## R12. The branch-deletion guard (FR-011)

**Decision**: `git/tasks.py::git_branch_delete` asks the store whether any entry of the repository's
queue names the branch as `source_git_branch`. When one does, it skips the remote deletion, logs a
warning that names the pending delivery, and still sends `RefreshGitRepositoryBranchDeleted`, which
only removes local worktrees.

**Why the local worktrees may go.** The source commit is on the remote branch, which stays. Any
worker fetches it again at the delivery.

**Why the remote branch is not deleted later.** A deferred deletion is new persisted work with its
own failure modes. A leftover branch is visible and harmless. A remote branch that matches
`git.import_sync_branch_names` can then be imported again as an Infrahub branch. The default for
that setting is empty. The spec lists the case as out of scope.

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
  cause and the required action in plain words, the remote's message verbatim, and the pending
  merges in order.
- Two items in `entities/repository/ui/repository-menu-section.tsx`: "Retry push" and "Abandon
  pending push". Both are disabled without `permission.update`, and when the status allows no
  action.
- An abandonment confirmation modal that lists the merges it will drop and says what FR-024 does to
  the repository objects.
- The delivery attributes are left out of the generic attribute list of the repository page, so the
  inherited copy of a non-default branch is never shown as current. All of them are declared with
  `display=extra` too, which keeps them out of list views.
- Each mutation follows the existing three-file pattern: `api/*-from-api.ts` with gql.tada,
  `domain/use-cases/*.ts`, and `ui/queries/*.mutation.ts`. The task link toast and the query
  invalidation follow `import-current-commit`.

**Out of scope**: the per-branch status list and the status vocabulary (INFP-671).

---

## R15. Test harness

**Unit, no database** (`backend/tests/unit/git/writeback/`, `backend/tests/unit/core/merge/`):

- the classifier across every row of R5;
- the queue model: append, idempotent enqueue, snapshot removal, version bump;
- the service against an in-memory `DeliveryGitPort` and an in-memory store: observation, the two
  checks, replay conflict, push failure and reset, the import condition, release then clear;
- the barrier against an in-memory store: partition, the atomic hold, the fast path, unknown owners,
  `releasing`;
- the retry condition of the task.

**Component, with a database**: the store's transitions, `read_only` keeping the attributes out of
the update input, and the branch-safety test (no delivery attribute in a diff, never merged, the
inherited copy on a new branch).

**Integration, live Gogs remote** (`backend/tests/integration/git/test_git_live_remote.py`), reusing
`rejected_push_to_main` and `_install_remote_branch_rejection_hook`:

- two merges while rejected, then one retry delivers both in one push;
- the remote message is recorded verbatim;
- a remote that advanced during the outage is imported before the record;
- a replay conflict, then an abandonment, a record and a release;
- a force-pushed source branch gives `source-discarded` and pushes nothing;
- the remote branch deletion is refused while pending;
- a transient fault: the Gogs container is paused during the push and unpaused before the second
  automatic attempt. The class-scoped fixtures run sequentially, so the pause cannot hit another
  test.

**Deferral**: the release count is asserted through the dispatched workflows. IFC-3048's scenario
harness is the place for run counts on a real stack, if it has landed by then.

**E2E** (`tests/e2e/repository/`): the e2e stack serves repositories through the SDK `GitRepo`
helper from a local bare repository. The test writes a rejecting `pre-receive` hook into it, merges
a branch, opens the repository page, reads the cause, removes the hook, clicks "Retry push", and
waits for "Nothing pending".

---

## R16. Documentation

| File | Change |
|---|---|
| `dev/knowledge/backend/git-integration.md` | Replace the two volatile sections ("not ordered against post-merge regeneration", "writeback direction has no reconciliation"). The second one is already stale: `merge` pushes before it records since `7d1bab3d1`. Add the delivery queue, the barrier and the synchronisation deferral. Update the known limitation on remote branch deletion. |
| `dev/knowledge/backend/selective-merge-regeneration.md` | The barrier, the new fallback reason, and `exclude_repository_ids`. |
| `dev/knowledge/backend/merge-recompute.md` | The barrier consultation for the Python family. |
| `docs/docs/git-integration/branch-synchronization.mdx` | What happens when a push fails, the status, retry and abandon. |
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
own PR on `opsmill/infrahub-sdk-python`, merged before the pointer moves here. The sibling epic
regenerates the same file, so the two epics should land their SDK changes in one SDK PR, or in an
agreed order.

No `GRAPH_VERSION` bump: optional attributes are added by the schema migration that
`infrahub upgrade` runs (`NodeAttributeAddMigration`).

---

## R18. Configuration

No new setting. The retry bounds of R6 are constants beside the task, as `WEBHOOK_SEND_RETRIES` is
in `webhook/constants.py`. A setting would be configurability for a hypothetical need
(Principle VII).

---

## R19. Coordination with IFC-3210 and IFC-3002

- **The ancestry question.** IFC-3210 adds `git/divergence/gateway.py` for it. Whichever epic lands
  first adds the primitive, and the other reuses it. The question is one call either way.
- **The merge-path check.** IFC-3210's FR-005a makes `InfrahubRepository.merge` refuse a diverged
  source or destination. This work stops calling `merge` from the merge flow: the service replays
  instead, and its checks of R4 steps 3 and 5 are that refusal for the replay. If IFC-3210 lands
  first, its check moves into the service. If this work lands first, IFC-3210 has no merge-path
  change left to make.
- **The synchronisation path.** Both epics change `collect_pending_imports`. R11's exclusion runs
  before the sibling's classification.
- **IFC-3002.** `_resolve_python_targets` gains the barrier filter. Whoever changes that function
  next must keep it.
