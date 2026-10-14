# Git Push Queue

> Part of: `dev/knowledge/backend/` | Related: [Git Integration](git-integration.md), [Git Sync](git-sync.md), [Selective Post-Merge Regeneration](selective-merge-regeneration.md), [Coalesced Recompute on Merge and Rebase](merge-recompute.md)

A merge of a git-synced branch changes the content of a read-write repository in the graph first,
and the push of that content to the remote runs later, in its own flow. The push can fail after the
graph merge is done. So each such merge waits in the push queue of its repository until a delivery
pushes it, and the repository records why the last attempt failed. Read this before you change
`backend/infrahub/git/writeback/`, the merge follow-ups, or any path that imports the default branch
of a read-write repository.

The code calls one push of the queue a "delivery". The schema labels and the user docs call it a
"push".

## The push state

The state is in nine attributes of `CoreRepository`. Each one is `LOCAL`, read-only, and optional
with no default, so the schema migration of an upgrade adds them with no data migration. Only the
value on Infrahub's default branch is live. Another branch reads the value that the default branch
held at its `branched_from`, and nothing acts on that copy.

| Attribute | Holds |
|---|---|
| `delivery_status` | `none`, `pending` or `action-required` |
| `delivery_failure_cause` | The cause of the last failure, a `RepositoryDeliveryFailureCause` |
| `delivery_error` | The message of the last failure, with credentials removed |
| `delivery_queue` | The pending merges in merge order, the queue version, the recently removed entry ids and an owed import |
| `delivery_held_regeneration` | The regeneration held until a release, and the release leases |
| `delivery_last_abandonment` | The record of the last abandonment |
| `delivery_last_delivered_commit` | The commit of the last push that an attempt recorded. An attempt that finds the merges on the remote already keeps the old value |
| `delivery_reverted` | A pushed commit that a later rewrite of the remote default branch discarded |
| `delivery_progress` | When the delivery last moved, when the attempt started, and when a waiting retry is due |

`pending` means that merges wait and an attempt runs, is about to run, or waits for its automatic
retry. `action-required` means that merges wait and no automatic retry is due: the next merge flow
of the repository or a user starts the next attempt. When the queue is empty again, the status goes
back to `none` and the cause and the error are cleared.

`git/writeback/store.py::WritebackIntentStore`, behind `git/writeback/ports.py::DeliveryStatePort`,
is the only writer. `backend/tests/unit/git/writeback/test_single_writer.py` fails when a module of
the `infrahub` package names one of the nine attributes, other than the store, the schema definition
and the generated protocols. The transitions are pure functions of
`git/writeback/models.py::WritebackIntent`.

- Each transition is one read and at most one save, in its own transaction, under the
  `repository-delivery` lock: 30 s time to live, 10 s to acquire. The first statement of the
  transaction takes the database write lock of the repository node, because a lock with a time to
  live cannot protect a commit that takes longer.
- Never call the store inside an open transaction: the transition raises `ValueError`.
- The store writes through the node API, so a write emits no node event.
- A lock not acquired in time raises `DeliveryStateUnavailableError`. A stored value that does not
  match its model raises `DeliveryStateUnreadableError`, which names the repository and the attribute.
  The JSON values carry a `format` field for a later change of their shape.

## From a merge to the queue

`core/merge/repository_merge_dispatcher.py::RepositoryMergeDispatcher` runs in the merge follow-ups,
after the graph merge and before the follow-ups submit any regeneration
(`core/merge/post_merge.py::PostMergeDispatcher.run_follow_ups`):

- `git/writeback/content.py::read_pending_merges` builds one entry for each active repository whose
  content the merge changes. A repository gets no entry when the source branch records no commit,
  records the commit that the default branch held at the `branched_from` time of the branch (its
  creation or its last rebase) or holds now, or has the name of the
  remote branch that a delivery pushes to. A stored commit that is not a full commit id counts as no
  commit, so one repository cannot stop the others.
- The dispatcher queues all entries at the same time, each try on its own database session, with
  one try and three retries after 2, 8 and 20 s. The branch merge holds the global merge lock meanwhile.
- It submits `git.tasks.merge_git_repository` for each repository that has an entry, with the entry
  and the delivery tags. A merge that changes no content submits no merge flow. The merge run log
  gets one line for each queued repository.

The flow covers what the dispatcher could not do:

- When the content read failed, each active repository gets a merge flow with no entry, and the flow
  reads the content itself.
- When every enqueue try failed, the flow queues the entry.
- In both cases, the flow holds a regeneration of every definition and Python computed attribute of
  the repository with the entry (`FullRegenerationReason.UNHELD_FOLLOW_UP`), because the follow-ups
  ran with no hold.
- When the source branch is deleted before the flow builds its entry, the flow uses the
  `source_commit` of its payload. With neither, it logs the merge to do by hand and ends `Failed`.

The queue refuses an entry whose id is queued, recently removed or abandoned, and an entry from the
remote branch that the delivery pushes to. A read-only repository and a staging repository keep
their own merge path and never use the queue.

## A delivery attempt

`git/writeback/service.py::RepositoryWritebackService.deliver` pushes the whole queue in one attempt.
Under the repository lock, it:

- stamps the start of the attempt and takes a snapshot of the queue. With no merge to deliver and no
  regeneration to release, it ends with `nothing-pending`;
- fetches, then reads the remote head of the destination and the commit that the default branch
  records;
- checks the queue against the remote, as the next list says;
- resets the destination worktree to the remote head and merges each remaining source commit by its
  id, in queue order;
- pushes once, when it replayed at least one merge;
- owes an import when the remote head differs from the recorded commit, when no commit is recorded,
  or when an earlier import is still owed, then records the new commit on the default branch and
  runs the owed import;
- asks the other workers to fetch the commit, and deletes each flagged remote source branch that no
  later queued merge comes from;
- removes the delivered merges from the queue and takes a release lease over the held items up to
  the snapshot that no live lease covers, in the save that ends the attempt.

Then, outside the repository lock, it releases the held regeneration under the lease. Generator runs
take the repository lock to fetch a commit that their worker lacks, so the release cannot run under
it.

The checks push nothing when they fail. After a rewrite or a discarded source, a replay would put
the discarded commits back on the remote, and a conflict needs a person to resolve it:

- The remote has no destination branch, or its history does not contain the recorded commit:
  `destination-rewritten`.
- A merge whose commit the remote head lacks, and whose remote source branch is gone or no longer
  contains that commit: `source-discarded`.
- A merge that conflicts with the remote head: `replay-conflict`.
- A merge that the remote head already contains is not replayed.

A failed replay, push or record resets the worktree to the commit that the default branch recorded
before the attempt, or to the remote head when it records none. After a failed record, the remote
holds the push, so the next attempt finds the merges on the remote and records the commit. A clone
with no `origin` fails the attempt as `unclassified` and keeps the queue.

With `git.use_explicit_merge_commit` at its default of `False`, a replay fast-forwards where it can,
and the new commit is the source commit, which the remote already has. When the worktree head (the
remote head and the merges replayed before) does not contain the source commit, or when that setting
is on, Git creates a merge commit. Its id depends on the time of the merge, so each replay gives a
new id. A failed replay or push discards it, and the next attempt replays the source commit again,
on any worker. After a successful push, the remote keeps it.

| Outcome | Meaning | Run state |
|---|---|---|
| `delivered` | The replayed merges are pushed and recorded | Completed |
| `observed` | The remote already held every merge, so nothing was pushed | Completed |
| `released` | The queue was empty, so the attempt only released held regeneration | Completed |
| `nothing-pending` | Nothing to deliver or release | Completed |
| `deferred` | Another retry chain of the repository is due later and delivers the queue | Completed |
| `failed` | A step failed | Failed |
| `unreplayable` | A check refused the queue | Failed |

## Failure causes and the automatic retry

`git/writeback/classifier.py::classify_delivery_failure` maps the error and the step to a cause. It
reads the error type, which the Git layer sets from Git's output, and the reason of a refused push
([Git Integration](git-integration.md#how-git-errors-are-classified)). The import wraps most errors
in `RepositoryImportError`, so for the import step the classifier reads the type of the wrapped
error: a database error or an unreachable server gives `import-interrupted`.

| Cause | When | Retried |
|---|---|---|
| `remote-unreachable` | The fetch or the push cannot reach the remote, or runs past its time limit | Yes |
| `remote-advanced` | The remote refuses the push as a non-fast-forward, or cannot update the ref | Yes |
| `record-failed` | Infrahub cannot read the recorded commit, cannot record the push, or cannot read or write the push state after the push | Yes |
| `import-interrupted` | A database or connection error stops the import of the pushed commit | Yes |
| `not-found` | The remote repository does not exist, at the fetch, the push or the import | No |
| `certificate` | Git refuses the certificate of the remote, at the fetch, the push or the import | No |
| `credentials` | The remote refuses the credentials at the fetch or the push. At the import, this gives `import-failed` | No |
| `permission` | A hook or a branch protection refuses the push, or the account cannot push | No |
| `import-failed` | The import of the pushed commit fails for another reason | No |
| `unclassified` | Any other error, such as a replay merge that fails with no conflict | No |
| `replay-conflict`, `source-discarded`, `destination-rewritten` | A check refused the queue | No |

The stored message is the remote's own `remote:` lines and a sentence that names the refusal for a
refused push, a sentence that names the branch or the merge for a check that refuses the queue, the
typed message of another Infrahub error that does not repeat Git output, or a sentence that names
the step and the error type. `git/writeback/credentials.py::scrub_credentials` removes credentials
from it.

`git.tasks.deliver_pending_merges` is a Prefect task with three retries, after 30, 120 and 300 s
(`git/writeback/constants.py`). It retries only a `RetryableDeliveryError`. Before the wait, a
failed step records `retry_due_at`. A failed enqueue and a failure outside a step record nothing.
The last attempt records a retried cause as final. A final failure with merges queued sets
`action-required` and no retry is due. A cause that is not retried is final at once.

- An automatic first attempt that finds a retry due later returns `deferred`: the waiting retry
  takes its snapshot when it starts, so it delivers the new merge too. So one retry chain usually
  runs for a repository. A manual retry never defers, and a failure that records no due time lets the
  next merge flow start its own chain.
- A failed enqueue or release gives no cause. While merges are queued, the stored cause and error
  stay.
- A failed release never sets `action-required`: its merges are on the remote already.
- A failure outside a step, such as a state that cannot be read, is retried. On the last attempt it
  ends the attempt as `failed`, so the run fails and does not crash.

## Retry and abandon

Two mutations act on the queue:

| Mutation | Input | Flow |
|---|---|---|
| `InfrahubRepositoryDeliveryRetry` | `id` | `git-repository-delivery-retry` (`git.tasks.retry_repository_delivery`) |
| `InfrahubRepositoryDeliveryAbandon` | `id`, `queue_version` | `git-repository-delivery-abandon` (`git.tasks.abandon_repository_delivery`) |

Both refuse, in this order:

- a request off the default branch, because the permission checks read the branch of the request;
- an account without `update` on `CoreRepository` and the global `manage_repositories` and
  `edit_default_branch` permissions;
- an unknown id, and the id of a node that is not a repository, with the same `NodeNotFoundError`;
- a read-only or staging repository;
- an empty queue (`NothingPendingError`).

The abandonment also refuses a `queue_version` that is not the current one
(`DeliveryQueueChangedError`), so a user abandons only the queue that the user saw. A running
attempt or a waiting retry does not refuse a request: the flow waits for the repository lock. Both
mutations return the task at once.

The retry flow runs `deliver_pending_merges` with no entry and the `manual` value of its payload:
`True` from the mutation, `False` from the recovery check. It gets the same automatic retries. It
checks nothing itself: the first step of the attempt decides whether something is left.

The abandonment builds the repository from the graph only, with no clone, so it works when the
remote is gone. Under the repository lock, it reads the recorded commit, then drops the whole queue
and the owed import in one save, with the record in `delivery_last_abandonment`: the merges, the
account, the time, the queue version, the recorded commit and the dropped owed import. It tells the
workers that each source branch flagged for deletion is gone, then releases the held regeneration
under its lease, outside the repository lock. The run ends `Completed` with a message that names the
abandoned merges.

- A release that fails ends the lease at once, so the items stay held, and the run fails. Its log
  says that the merges are abandoned, that the barrier no longer holds the repository, and that a
  user can run the definitions and the computed attributes of the repository by hand to regenerate
  now. A later delivery run releases the items.
- A failed clear of the lease after the release keeps the lease, and the run fails. A later delivery
  run releases the items again once the lease expires.

An abandonment pushes nothing, deletes no remote branch and imports nothing. The objects of the
abandoned merges stay on the default branch until a user reimports the current commit, or until the
sync imports a new commit of the remote default branch. The queue refuses an abandoned entry id
while it is in the last abandonment record or among the last 256 removed ids.

## Imports that wait for the queue

An import of the default branch removes the repository objects that the imported commit lacks. While
a repository has pending pushes, the remote head lacks the pending merges, so an import of it would
remove their objects. While the status is not `none`, three paths wait:

| Path | What it does |
|---|---|
| `InfrahubRepository.collect_pending_imports`, the active loop | Leaves out the default branch and the remote source branch of each pending merge, new or updated, before the classification. No worktree moves, no commit is written, no rewrite is recorded. It logs the skipped branches. |
| `git/tasks.py::bootstrap_local_repository` | After a fresh clone that seeds the default branch, records no commit and skips the seed import. A seed into a staging branch still imports. |
| `graphql/mutations/repository.py::ProcessRepository` | Refuses the reimport on every branch, with `ReimportPendingPushesError`. The import flow (`git.tasks.import_objects_from_git_repository`) checks again under the repository lock, so a merge queued after the mutation accepted the reimport still stops it. |

A state that cannot be read fails closed: the sync of that repository stops for the cycle. The
staging path does not change. The delivery imports the remote head itself when it moved. A rewrite
of the remote default branch during the wait is reconciled at the first cycle after the queue
clears. Until then the delivery refuses it with `destination-rewritten`.

The wait also holds new merges when the remote default branch moves or is rewritten. The graph
keeps the commit that the default branch recorded before the wait, so
`git/merge_readiness.py::RemoteHeadsMergeCheck` finds a remote head that the graph did not record.
When a branch that syncs with Git records another commit than the default branch for that active
repository, the check refuses its merge with `RepositoryNotSynchronizedError`. The refusal comes
before the graph merge, so the branch stays open. A branch that records the commit of the default
branch has nothing to merge in Git, so the check compares only its own remote head. The refusal ends
when a delivery, automatic or manual, records the pushed commit, or when a user abandons the queue
and the next cycle imports the remote head.

The repository conversion (`core/convert_object_type/repository_conversion.py`) refuses with
`DeliveryPendingError` while merges are queued or held regeneration waits, because the conversion
deletes the node and its push state with it. Inside the repository lock, it holds the state lock
from the check to the deletion, so no merge is queued between them while the state lock lives. A
conversion also cannot set a read-only attribute of the target kind through its mapping.

## The kept source branch

With `main.delete_branch_after_merge` and `git.delete_git_branch_after_merge` on,
`git.tasks.git_branch_delete` can run before the delivery, and the remote source branch is then the
only place that holds the source commit. Under the state lock, `request_branch_deletion` flags each
queued merge from that branch. When it flags one, the task keeps the remote branch, logs a warning,
and sends no `RefreshGitRepositoryBranchDeleted`, so every worker keeps its local branch. When the
check fails, the task keeps the branch and logs the manual step. It does not raise, so the other
repositories still delete their branch.

The delivery deletes a flagged branch after the push, unless a later queued merge comes from it. An
abandonment keeps a flagged branch on the remote and tells the workers to drop their local copy. The
next sync then imports the branch as a new Infrahub branch, when `git.import_sync_branch_names`
allows its name, and the user can merge it again.

## The regeneration barrier and the release

Regeneration reads the commit that the default branch records. For a repository whose merge waits in
the queue, that commit lacks the merged content. The dispatcher queues the merge before the
follow-ups submit any regeneration, so the barrier sees the pending repository.

`core/merge/regeneration_barrier.py::RegenerationBarrier` acts on the default branch only, and
admits everything on another branch:

- A generator or artifact definition, or a Python-transform computed attribute, that a repository
  with pending pushes owns is held in `delivery_held_regeneration`, under the next hold sequence. The
  rest runs at once. A Python attribute whose owner is not known is held under every pending
  repository.
- A blanket regeneration holds a marker (`widen`) under each pending repository and excludes those
  repositories from the blanket runs.
- It never raises. When it cannot read or update the state after one try and three retries (after 2,
  8 and 20 s), it admits every candidate, and the holds written before the failure stay.

`core/merge/regeneration_release.py::HeldRegenerationReleaser` runs after a delivery or an
abandonment, under a release lease of 15 minutes. Each awaited step renews the lease. A timer also
renews it every 5 minutes while the release runs, because one step, such as a generator run, can
last longer than the lease (`git/writeback/service.py::release_under_lease`). The timer renews
through `git/writeback/store.py::LeaseRenewer`, on a database session of its own, because the
release uses the session of the flow at the same time. Its dispatches pass the barrier with the
released repository admitted, so work of another pending repository stays held. A regeneration of
the whole repository does not pass the barrier, because it runs only the definitions of that
repository. A release that fails ends its lease, keeps every item held, and records no
`action-required`. What a release runs is in [Selective Post-Merge
Regeneration](selective-merge-regeneration.md#held-regeneration) and [Coalesced
Recompute](merge-recompute.md#held-python-targets).

## The recovery check

`git/writeback/recovery.py::DeliveryRecoveryCheck` runs from the loop of
`git.tasks.sync_remote_repositories`, for each repository before its sync. It has its own guard,
database session and Prefect client, so a failure skips only the check of that repository. It
submits one `git-repository-delivery-retry` run with `manual=False`, a system context (the default
branch and an anonymous account) and the delivery tags, then moves the progress time, in two cases:

- **The delivery is stale**: the status is `pending`, no retry is due later, the delivery made no
  progress for `STALE_AFTER_SECONDS` (15 minutes), the repository lock is free, and no delivery run
  of the repository waits to start.
- **Held regeneration waits behind an empty queue**: at least one held item has no live release lease,
  the delivery made no progress for the same time, and no delivery run of the repository waits to
  start or runs.

Progress moves at each enqueue, attempt start and recorded failure, after the fetch, the push and
the record, and before and after the import. The check asks Prefect last, with one `read_flow_runs`
call for the runs that have both tags of `git/writeback/runs.py::delivery_run_tags`
(`PrefectDeliveryRunQuery`). For a stale delivery, it counts a state of type `SCHEDULED` or
`PENDING` only: a live worker holds the lock or writes progress, so a running run is left out. For
held regeneration, it counts `RUNNING` too, because a release holds no lock and writes no progress,
so only its run shows that it still works. When Prefect does not answer, the check submits nothing.
A queue at `action-required` gets no automatic run.

## Time limits on Git commands

- The fetch of a delivery has 120 s, its push and its deletion of a remote branch 300 s, and each
  local Git command 120 s.
- GitPython's `kill_after_timeout` does not stop a hung `Remote.fetch` or `Remote.push`. For an
  HTTP(S) remote, `git/base.py::stalled_transfer_limit` sets `GIT_HTTP_LOW_SPEED_LIMIT=1` and
  `GIT_HTTP_LOW_SPEED_TIME` to the limit for that one command, so Git ends a transfer that sends no
  data for that long. Git reports "Operation too slow", which raises `RepositoryConnectionError`, so
  the cause is `remote-unreachable`.
- GitPython stops a local Git command at its limit with `ps --ppid`, so the backend image installs
  `procps`.

## The reverted push record

When the sync classifies the default branch as rewritten ([Git
Sync](git-sync.md#rewritten-history)), it reads `delivery_last_delivered_commit`. When the new head
no longer holds that commit, the sync records it in `delivery_reverted` and logs a warning. Each
push fast-forwards the remote, so every earlier pushed commit survived when the last one did. A
clone that lacks the pushed commit records it too, because a fetch brings every ancestor of the new
head.

- A record that names the same pushed commit stays, so a later rewrite does not replace the first
  record.
- A change of `default_branch` with a live re-target marker is not a rewrite, so it records nothing.
  It forgets the last pushed commit instead (`forget_delivered_commit`), because that commit belongs
  to the previous default branch.
- A failed record fails the default branch at step `record` and keeps its import, as a failed
  rewrite record does.

Read this record through GraphQL, like the other eight attributes. The generic details page of the
repository shows the nine attributes only when the user selects **Extra**.

## Known limitations

- **An SSH remote has no stall limit.** A fetch or a push over SSH that hangs keeps the repository
  lock until the connection ends, so the recovery check submits nothing, and a manual retry and an
  abandonment wait too.
- **A transfer that sends data and then stalls** can take up to about twice its limit.
- **A repository lock that a dead worker held** has no time to live, so the recovery check and a
  manual retry wait for `locks/tasks.py::clean_up_deadlocks`. It runs every minute and deletes a lock
  whose holder left the active-worker set, once the lock is older than
  `cache.clean_up_deadlocks_interval_mins`.
- **A delivery run that stays in `PENDING`** counts as a run that waits to start, so the automatic
  recovery stops while it stays there, for a stale delivery and for held regeneration. The
  `crash-zombie-flows` automation does not end such a run. A manual retry still works while merges
  are queued: it submits a new run. With an empty queue, the retry mutation refuses.
- **A release whose generator run never ends** keeps its lease while its worker lives, because the
  timer renews it. No other run releases its items in that time.
- **A release run of a dead worker that stays in `RUNNING`** stops the automatic restart of the
  release until the `crash-zombie-flows` automation marks the run crashed. Its lease still expires,
  so the next delivery run after the expiry releases the items. A manual retry starts such a run
  only while merges are queued: the retry mutation refuses an empty queue.
- **A release that fails every time** gets a new automatic run every `STALE_AFTER_SECONDS`, with no
  limit. Each run makes up to four attempts, and each attempt can dispatch the held regeneration
  again.
- **One refusal blocks every later merge of the repository.** When the remote default branch moved
  or was rewritten, the merge check refuses each later merge of a branch with something to merge in
  the repository, before the graph merge. Otherwise each later merge is queued, and each attempt
  checks the whole queue, so it is refused for the same cause. This lasts until a user abandons the
  queue or, after `replay-conflict`, merges the source branch on the remote by hand and retries.
- **An abandonment drops the whole queue.** No mutation drops one merge.
- **A branch forked from the default branch while pushes are pending** holds the objects of the
  pending merges in its graph. Its Git branch comes from the local trunk head, which lacks their
  files. A sync import of that branch removes those objects there, and a merge of the branch then
  removes them from the default branch. The reimport refuses on every branch, but the sync of such a
  branch does not wait, because that would hold every developer push during an outage.
- **A remote source branch deleted before its merge is queued** is not kept: the guard finds no
  merge to flag. This needs the dispatcher to fail to read or to queue the merge. The delivery then
  refuses with `source-discarded`, and a user abandons the queue and merges the branch on the remote
  by hand.
- **A re-target marker stays while pushes are pending**, because the sync skips the default branch.
  After an outage longer than the seven days of the marker, a change of `default_branch` made during
  the outage reads as a rewrite.
- **A change of `default_branch` whose marker expired before the next sync reads as a rewrite**, so
  the sync can record a reverted push that did not happen. The rewrite record of
  [Git Sync](git-sync.md#the-rewrite-record) has the same limit.
- **A conversion that takes longer than the state lock lives** can still let a merge in. The state
  lock has a time to live of 30 s, so a merge can be queued when more than 30 s pass between the
  check of the conversion and the deletion of the node. That merge is dropped with no record.
- **A merge queues its entry under the state lock only**, not under the repository lock. So a merge
  can be queued after the second check of a reimport, or after the sync read the state, and before
  the import runs. That import then removes the objects of the merge from the default branch.
- **The history of the queue grows with the square of an outage.** Each change rewrites the whole
  `delivery_queue` value, and the temporal history keeps each version, so N merges during one outage
  store about N²/2 entries.

## Rollback

A revert of this code is safe for the data: the nine attributes are additive, and the older code
ignores them. Two effects remain after a revert:

- Merges still in a queue are never pushed. Push them by hand, or merge again.
- Held regeneration is never released. Run a full regeneration of the default branch.

## Key Files

| File | What |
|---|---|
| `git/writeback/models.py` | `WritebackIntent` and its transitions, the queue, the held regeneration, `DeliveryOutcome` |
| `git/writeback/store.py` | `WritebackIntentStore`, the only writer of the push state; `LeaseRenewer` |
| `git/writeback/service.py` | `RepositoryWritebackService`, one delivery attempt |
| `git/writeback/git_adapter.py` | `RepositoryDeliveryGitAdapter`, the Git work of an attempt, with a time limit on each command |
| `git/writeback/classifier.py` | `classify_delivery_failure`, the cause and the retry decision |
| `git/writeback/content.py` | `read_pending_merges`, which merges change content |
| `git/writeback/abandoner.py` | `WritebackAbandoner` |
| `git/writeback/recovery.py`, `runs.py` | `DeliveryRecoveryCheck`, `PrefectDeliveryRunQuery`, the delivery tags, the retry delay |
| `git/writeback/constants.py` | Retry delays, time limits, `STALE_AFTER_SECONDS`, lock and lease times |
| `git/writeback/factory.py` | `build_writeback_service`, `build_writeback_abandoner` |
| `core/merge/repository_merge_dispatcher.py` | `RepositoryMergeDispatcher`, the enqueue after a merge |
| `core/merge/regeneration_barrier.py`, `regeneration_release.py` | The barrier and the releaser |
| `git/tasks.py` | `merge_git_repository`, `deliver_pending_merges`, the retry and abandon flows, `git_branch_delete` |
| `graphql/mutations/repository.py` | The retry and abandon mutations, the reimport refusal |
