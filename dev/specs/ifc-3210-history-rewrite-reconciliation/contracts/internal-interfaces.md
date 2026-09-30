# Internal contracts: Git history-rewrite reconciliation

**Feature**: `dev/specs/ifc-3210-history-rewrite-reconciliation`
**Date**: 2026-09-29

These are the backend interfaces this feature introduces or changes. They are not user-facing. The
user-facing GraphQL surface is in `repository_rewrite.graphql`.

---

## 1. `RemoteDivergenceDetector`

New. `backend/infrahub/git/divergence/detector.py`.

Classifies one tracked ref's remote head against the commit Infrahub **recorded in the graph** for
that branch. It holds no git code: a gateway supplies the two commits and answers the ancestry
question.

### Two comparisons, not one

The design turns on keeping these apart. They answer different questions, they read different
inputs, and they drive different outcomes.

| Question | Inputs | Drives | Who runs it |
|---|---|---|---|
| Was the history rewritten? | the commit **recorded in the graph** for this branch, against the remote head | the record and the trunk signal | whichever worker runs the synchronisation cycle |
| Does this clone need to move? | this worker's **branch worktree head**, against the remote head | the reset | every worker, independently, in `pull` |

`imported_commit` below is always the **graph** commit. It is never the local worktree head.

Conflating them breaks the feature in one of two ways, and an earlier draft of this design did not
say which input it meant:

- Use the worktree head for the classification, and a worker that missed the broadcast classifies
  `REWRITE` again on the next cycle. It writes a second record, increments the count and fires the
  trunk signal twice. SC-002 and FR-014 both fail.
- Use the graph commit for the reset, and once the reconciling worker has recorded the new commit
  every other worker classifies `UNCHANGED`, resets nothing, and keeps the discarded history for
  ever. SC-004 fails.

Splitting them makes both correct without a guard. The reconciling worker sees a stale graph commit
and records once. Every other worker sees a stale worktree and resets, records nothing, and
converges.

```text
classify(
    branch_name, infrahub_branch_name, imported_commit, remote_head, target_changed
) -> RefDivergence
```

### Contract

Rows are evaluated in order. The first match wins.

| Input | Output |
|---|---|
| `remote_head` is `None`, `imported_commit` is set | `REMOTE_ABSENT` |
| `remote_head` is `None`, `imported_commit` is `None` | `UNCHANGED` |
| `imported_commit` is `None` | `FAST_FORWARD` |
| `remote_head == imported_commit` | `UNCHANGED` |
| `imported_commit` is an ancestor of `remote_head` | `FAST_FORWARD` |
| **`remote_head` is an ancestor of `imported_commit`** | **`LOCAL_AHEAD`** |
| **The imported commit is absent from the local object database, `target_changed` is false** | **`REWRITE`** (see below) |
| **The imported commit is absent, `target_changed` is true** | **`RETARGET`** |
| Neither is an ancestor, `target_changed` is false | `REWRITE` |
| Neither is an ancestor, `target_changed` is true | `RETARGET` |
| Any other git failure | propagates as `RepositoryError`; the branch joins `failed_imports` |

The two absent-object rows sit **above** the ancestry rows, because those rows cannot run when the
object is missing. They also honour `target_changed`: a deliberate re-target whose old commit has
been garbage-collected is still a re-target, and recording it as a rewrite would consume the marker
and write a false record.

**The `LOCAL_AHEAD` row is what keeps this safe without PR #10465.** A branch left ahead of its
remote after a rejected push is a state the product reaches today. Without that row it falls into
"neither is an ancestor", classifies `REWRITE`, and the reset discards the unpushed commit. With
it, the branch resets nothing, records nothing, and keeps exactly today's behaviour.

`REMOTE_ABSENT` likewise keeps current behaviour: a tracked ref that disappeared from the remote is
not a lineage break. `spec.md` names it as an edge case.

**Only a genuinely missing object maps to `REWRITE`.** The gateway turns every git failure into a
`RepositoryError`, so a rule of "cannot be answered means rewrite" would let a lock file, an I/O
error or a permission problem on a fast-forward branch write a spurious record and fire the trunk
signal. The gateway must therefore distinguish "this object is not here" from "git could not be
asked", and only the first is a classification. Everything else propagates, and the classification task sends the
branch to `failed_imports` as it does for any other per-branch git failure.

### Which branches the collector considers

`compare_local_remote` returns branches whose **local** head differs from the remote. That set
alone is not enough: a `default_branch` edit moves no ref, so it reports nothing, and the re-target
would never be classified at all.

The collector therefore takes the union of two sets:

- local head differs from the remote head — what `compare_local_remote` already gives, and what
  decides the reset;
- **graph commit differs from the remote head** — what decides the record, and what catches a
  re-target that moved no ref.

Both are needed. Neither is a subset of the other.

### Where the graph commit comes from

`collect_pending_imports` has no graph read of its own, and `get_commit_value` reads **git**, not
the graph. The per-branch graph commits are loaded once per cycle by
`git/utils.py::get_repositories_commit_per_branch` and carried on `RepositoryData.branches`.

**They are not where they need to be yet.** That data lives in `sync_remote_repositories`.
`sync_repository_from_origin` does not receive it, and neither does the subflow below it,
`sync_git_repo_with_origin_and_tag_on_failure`. Threading it from
`sync_remote_repositories` through both of those to `collect_pending_imports` is part of the work,
not an existing affordance. Re-reading it lower down instead would add a query per repository per
cycle and would race the writes the same cycle makes.

**"Exactly one record" assumes cycles do not overlap.** Two cycles running at once would both read
the same stale graph commit and both record. `GIT_REPOSITORIES_SYNC` prevents that today with
`concurrency_limit=1` and `CANCEL_NEW`. If that ever changes, the count needs a compare-and-set
rather than a read-then-write.

A branch with no recorded commit has never been imported. It cannot be a rewrite, so it classifies
`FAST_FORWARD` and takes the ordinary import path.

**That rule is close to dead code until branch creation writes a commit.** `git_branch_create`
creates and pushes the branch but never calls `update_commit_value`, and `commit` is LOCAL, so the
branch inherits the trunk's value as of its fork point. A read therefore almost always returns
something, and the classifier compares a branch's remote head against a trunk commit that has
nothing to do with it. That can classify a healthy branch `REWRITE`. Branch creation must write the
commit.

### Rules

- The detector never contacts the remote. The caller fetches first.
- The detector never writes. It returns a value.
- The detector runs without a database, so its unit tests need none.
- The detector is given the graph commit. It never reads the worktree, and it never decides whether
  this worker needs to reset. That decision belongs to the `pull` contract in section 3.
- **`target_changed` is supplied by the caller, and the caller is the only component that touches
  the suppression marker.** It reads the marker, deletes it, and passes the result here. Neither
  the detector nor the recorder reads the cache. See section 8.
- **Reset and record are two different decisions.** `REWRITE` and `RETARGET` both reset: both
  describe a branch whose local history no longer leads to the remote's, and both must end with
  the worktree on the remote head. Only `REWRITE` records. `LOCAL_AHEAD`, `REMOTE_ABSENT` and
  `UNCHANGED` do neither.

**The classification decides the record. It does not decide the reset.** They read different
inputs, so one table cannot carry both.

Record and signal, from the classification (graph against remote):

| Classification | Record | Signal |
|---|---|---|
| `UNCHANGED` | no | no |
| `FAST_FORWARD` | no | no |
| `LOCAL_AHEAD` | no | no |
| `REWRITE` | yes | trunk only |
| `RETARGET` | no | no |
| `REMOTE_ABSENT` | no | no |

Reset, from this worker's worktree against the remote, decided independently:

| Worktree against remote head | Graph commit | Action |
|---|---|---|
| Equal | equals the remote head | nothing |
| Equal | **differs from the remote head** | **write the commit, queue the import, and record if the classification is `REWRITE`** |
| Worktree is an ancestor of the remote head | any | pull, as today |
| Remote head is an ancestor of the worktree | any | nothing. The worktree is ahead, not diverged |
| Neither is an ancestor | any | reset onto the remote head |
| The remote carries no such ref | any | nothing |

**The second row is the one that is easy to lose.** The candidate set includes branches selected
because the graph commit differs, and on those the worktree can already be at the remote head, so
nothing needs resetting. `pull` cannot be relied on to close the gap: it returns early at
`if commit_after == commit_before: return True`, **before** `update_commit_value`, so a worktree
that did not move writes no commit and queues no import.

Without that row the graph never catches up. A `default_branch` edit then consumes its marker on
the first cycle and classifies `RETARGET`, and every cycle after that classifies `REWRITE`, writes
a record and fires the trunk event again. The failure repeats once a minute for the life of the
repository.

A worker whose graph already matches the remote still resets when its own worktree does not. That
is the `UNCHANGED` row of the first table meeting the last row of the second, and it is the whole
point of FR-001c. A single table keyed on the classification would leave that worker on the
discarded history for ever, flagged by `compare_local_remote` on every cycle and repaired by
nothing.

  A `RETARGET` that reset nothing would leave the branch stuck on a history the remote no longer
  has, which is the defect this feature removes. The PRD says a deliberate re-target is
  "reconciled, not reported" — reconciled is the reset, not reported is the missing record.

### Ancestry gateway

```text
is_ancestor(repository, ancestor_commit, descendant_commit) -> bool
```

It wraps `git merge-base --is-ancestor` through GitPython's `Repo.is_ancestor`. Every git failure
leaves it as a `RepositoryError`, so the detector handles one exception type and imports no git
library.

---

## 2. `HistoryRewriteRecorder`

New. `backend/infrahub/git/divergence/recorder.py`.

The sole write path for the four attributes. It owns last-write-wins, the increment and the trunk
signal.

```text
record(repository_id, repository_name, infrahub_branch_name, divergence, is_default_branch) -> bool
```

Returns whether a record was written.

### Contract

1. Writes nothing unless `divergence.classification` is `REWRITE`. `RETARGET` arrives already
   classified, so the recorder needs no precondition of its own and never reads the cache.
2. Rejects a divergence whose `imported_commit` equals its `remote_head`. That is a classifier bug.
3. Reads the current `rewrite_count` on that branch, writes `count + 1`, treating an absent value
   as zero.
4. Writes all four attributes in one mutation, on the Infrahub branch named.
5. Overwrites the previous record. It never accumulates and never clears.
6. Emits `RepositoryHistoryRewrittenEvent` at most once, and only when `is_default_branch` is true.
   **At most, not exactly.** The record write and the emit are separate operations. If the record
   lands and the emit fails, the next cycle sees the graph and the remote agree, classifies
   `UNCHANGED`, and nothing ever sends that signal again. SC-002 reads "exactly one signal", and
   what the design guarantees is "never more than one". Closing the gap needs an outbox, which is
   more machinery than a rare event is worth. It sits beside the record-write risk below.
7. Runs inside the repository-lock acquisition that **writes the reconciled commit**, immediately
   after that write. See "Where it is called" below.

### Where it is called

`RepositorySyncer.sync` takes the repository lock twice: once around `collect_pending_imports`, and
once per branch around `apply_branch_import`. The reconciled commit is written inside the **first**
one: `collect_pending_imports` calls `pull`, which defaults `update_commit_value=True`, and the
reset path of the sync task writes the commit the same way.

**The recorder runs there, beside that write.** Both properties the placement needs hold:

- **The count is safe.** The read-then-increment of step 3 happens inside a lock hold. What is
  unsafe is a call placed *between* the two acquisitions, not a call inside the first one.
- **The record cannot name a commit the graph lacks**, because the commit is written first. The
  two are separate GraphQL mutations, so a lock hold is **not** a transaction and they are not
  atomic. If the record write fails after the commit write, the commit stands and the record is
  lost: the next cycle classifies `UNCHANGED`, so that rewrite is never recorded and its trunk
  signal never fires. This is an accepted residual risk, listed in the plan's risk table. The
  reverse ordering would be worse, because it would let a record name a commit that was never
  written. `collect_pending_imports` also lets graph errors propagate, so a failed record write
  aborts collection for every branch and skips the broadcast; the record write must therefore be
  isolated per branch like the other per-branch failures.

**Why not after the import, which an earlier draft specified.** That draft argued a failed import
should leave no record, so the next cycle would classify `REWRITE` again and retry. That argument
is false: the commit is already written during collection, so the next cycle reads the *new* head
as the imported commit and classifies `UNCHANGED`. The rewrite would then never be recorded and the
trunk event would never fire, breaking SC-002's "exactly one signal".

**What a failed import means for the record.** The record describes the git reconciliation, which
did happen: the worktree moved and the graph holds the new commit. A failed object import is a
separate condition, reported through `failed_imports` and the repository's synchronisation status.
Conflating the two would make the record lie about git in order to describe an import.

### Injected ports

Principle III and `.agents/rules/backend-component-design.md` require the collaborators to be named
protocols passed to the constructor, so the recorder's unit tests need no database and no mocks.

| Port | What it does |
|---|---|
| `RepositoryRecordStore` | Reads `rewrite_count` for one repository and branch, and writes the four attributes in one call. |
| `RewriteEventEmitter` | Emits `RepositoryHistoryRewrittenEvent`. |

The production `RepositoryRecordStore` is backed by the SDK node API. A test substitutes an
in-memory one. The recorder itself imports neither the SDK nor the event service.

### Rules

- The recorder is never called from a worker's own pull path. That is FR-007, and the pull path has
  no recorder reference at all, so the rule holds by construction.
- The production store writes through the SDK node API. It does not change the `python_sdk`
  submodule.

---

## 3. `InfrahubRepositoryBase.pull`

Changed. `backend/infrahub/git/base.py`.

Before it pulls, it compares the branch worktree head and the remote head by ancestry. It
hard-resets onto the remote head only when **neither** is an ancestor of the other.

### Contract

| Condition | Behaviour |
|---|---|
| No origin | Returns `False`, unchanged. |
| Worktree head equals remote head | Returns `True`, unchanged. |
| Worktree head is an ancestor of remote head | Pulls, unchanged. |
| **Remote head is an ancestor of worktree head** | **Returns `True`. Resets nothing.** The worktree holds commits the remote does not. |
| Neither is an ancestor of the other | Hard-resets onto the remote head and creates the commit worktree. |
| No worktree, `create_if_missing` and a branch id | Creates the worktree, unchanged. |

**The locally-ahead row is mandatory here, not only in the detector.** FR-001a forbids resetting
such a branch. A rule keyed on "not an ancestor" would catch it, because a branch that is ahead of
its remote is also not an ancestor of it, and the reset would discard the unpushed commit this
whole feature is careful about.

The pull path answers this without any classification context: "is the remote head an ancestor of
the worktree head" is a pure ancestry question, the same gateway call the detector makes. What the
pull path cannot do is tell a rewrite from a deliberate re-target, because that needs the
suppression marker. It does not need to: both reset, and neither records.

### Rules

- The reset honours `update_commit_value` the same way the pull does. The broadcast handler passes
  `update_commit_value=False`, so a self-healing worker writes nothing to the graph.
- The reset writes no rewrite record and emits no event, whatever the caller (FR-007).
- No message raised from this path calls a divergent history a conflict (FR-003, FR-017).
- **This change cannot be implemented before PR #10465 lands.** Without the push-before-graph-write
  ordering, an unconditional reset can discard a merge commit that exists on one worker only.

---

## 4. `RepositorySyncer.sync`

Changed. `backend/infrahub/git/sync.py`.

It returns the branches the cycle advanced instead of returning nothing, and it raises for failed
branches only after its caller has had the chance to broadcast.

```text
sync(repo, staging_branch) -> SyncOutcome
```

`SyncOutcome` carries `reconciled: tuple[ReconciledBranch, ...]` and
`failed: tuple[FailedImport, ...]`.

### Contract

1. It no longer raises `raise_if_branches_failed` itself. It returns the failures.
2. The caller broadcasts every reconciled branch, then raises for the failures.
3. A branch that failed is absent from `reconciled`. A branch that succeeded is present whether it
   fast-forwarded or was reconciled from a rewrite.
4. The per-branch failure isolation that exists today is unchanged: one failing branch never stops
   the others being collected or imported.
5. **Its other two callers must be updated with it.** `sync` stops raising, so
   `git/tasks.py::sync_git_repo_with_origin_and_tag_on_failure` no longer reaches its `except` and
   would stop tagging failures, and `git/tasks.py::add_git_repository` calls `sync` directly and
   would silently ignore a failed initial import. Both must read the returned failures and act on
   them.

---

## 5. `sync_repository_from_origin`

Changed. `backend/infrahub/git/tasks.py`.

It sends one coalesced `RefreshGitFetch` covering every reconciled branch, before any raise.

### Contract

| Before | After |
|---|---|
| One message, for `staging_branch or registry.default_branch` only | One message, carrying every branch the cycle advanced |
| Sent after the sync returns, so a raise skips it | Sent before the failure for a failed branch is re-raised |
| Commit read from `repo.default_branch` | Commit taken per branch from `ReconciledBranch` |

### Rules

- Exactly one message per repository per cycle. The handler holds the repository lock once and
  fetches once.
- When the cycle advanced no branch, no message is sent. **This removes a heal that exists today.**
  `sync_repository_from_origin` currently sends the pinned trunk commit every cycle even when
  nothing changed, which brings a worker that missed an earlier broadcast back within a minute. The
  pull-path self-heal of FR-005 replaces it, and that is gated on PR #10465. Until it lands, keep
  sending the trunk message unconditionally: the "no branch advanced, no message" rule ships with
  the pull-path reset, not before it.
- When every branch failed, no message is sent.
- **A trunk failure is made loud without being made fatal.** Today
  `sync_repository_from_origin` catches `RepositoryError` and `CommitNotFoundError` and calls
  `log.info`; nothing propagates. FR-018 raises the severity of that path for the configured
  default branch: log at error level and record the failure against the repository's
  synchronisation status. It does **not** propagate out of the flow.

  Propagating would be a worse bug than the one it reports. `sync_remote_repositories` loops over
  every repository with no per-repository `try`, so a raise from one repository aborts the cycle
  for every repository after it, on every cycle. That is the outage US3 removes at branch level,
  recreated at repository level. "Loud" means visible and recorded, not fatal to its neighbours.

  Belt and braces: `sync_remote_repositories` also gains a per-repository `try` so that no future
  failure in one repository can stop the others. That guard is missing today and is worth having
  whatever FR-018 does.
- **The single-branch fields stay populated.** `infrahub_branch_name` and `infrahub_branch_id` are
  required on the message, so a coalesced message fills them, and `commit`, from its first pair. A
  worker still running the previous code then converges one branch instead of failing to construct
  the message. That is a degradation during a rolling deployment, not a failure, and the remaining
  branches converge on first contact through the pull-path rule of FR-005.

---

## 6. `RefreshGitFetch` handler

Changed. `backend/infrahub/message_bus/operations/git/repository.py::fetch`.

### Contract

1. It still ignores a message whose `meta.initiator_id` is this worker.
2. It still takes the repository lock and fetches once.
3. When `branches` is present, it resets each pair in turn, inside that one lock hold.
4. When `branches` is absent, it behaves exactly as it does today.
5. It still passes `update_commit_value=False`. A broadcast never writes to the graph.
6. One pair failing does not stop the rest. Each failure is logged with the branch it belongs to,
   and that branch converges on first contact through the pull-path rule of FR-005. The broadcast
   is a pre-warm, so a pair it could not converge costs promptness and not correctness.

---

## 7. Read-only detection

Changed. Attachment point depends on whether PR #10669 has reached **`develop`**. It is merged,
but into `pog-repo-commit-visibility-ifc-3101`, which has not landed yet. See `research.md` R10.

| If #10669 is on `develop` | If it is not |
|---|---|
| `backend/infrahub/git/refs_check/checker.py::ReadOnlyRepositoryRefsChecker._detect_movements` tells you a ref moved. Use that as the trigger only. | `backend/infrahub/git/repository.py::InfrahubReadOnlyRepository.update_latest_commit` resolves the new head. Classify there. |

**Do not use `RefMovement.previous_head` as the imported commit.** It comes from
`_resolve_local_head`, which reads `git_repo.commit("origin/<ref>")` off the local clone. That is a
disk read, and this section requires the graph value. A worker whose clone is stale would compare
two disk values and classify a rewrite that never happened, or miss one that did.

#10669 already carries the right reader: `refs_check/tracked_commit.py::TrackedCommitReader`, which
`_converge` uses for the same reason. Take `imported_commit` from that, and take only the "this ref
moved" signal from `_detect_movements`.

### Which mutation carries a rewrite, and it is not the update one

A force-pushed branch changes neither `ref` nor `commit` on the node, and
`InfrahubRepositoryMutation.mutate_update` submits its workflows **only** when one of those
changes. So a genuine rewrite never reaches that path at all, and anything routed through it would
always arrive with `target_changed` true — classifying every read-only rewrite as a `RETARGET` and
recording nothing.

The path a rewrite actually takes is `ReadOnlyRepositoryImportLastCommit`, which submits
`import_read_only_repository_last_commit`. That is where the detection belongs, and
`target_changed` is false there: nothing was re-pointed.

Splitting them by mutation:

| Mutation | Meaning | `target_changed` |
|---|---|---|
| `ReadOnlyRepositoryImportLastCommit` | pick up whatever the tracked ref now resolves to | false |
| `InfrahubRepositoryMutation.mutate_update`, `ref` changed | deliberate re-point | true |
| `InfrahubRepositoryMutation.mutate_update`, `commit` changed | deliberate re-pin | true |

### Which commit is the "imported" one here

The same rule as section 1: **the commit recorded in the graph** for that Infrahub branch, never
anything read from disk. This needs saying because the read-only path makes it easy to get wrong.
`update_latest_commit` resolves only the *new* head, `import_read_only_repository_last_commit`
calls `init` without a commit, and the update mutation submits `pull_read_only` concurrently, which
can write the new commit to the graph first.

`GitReadOnlyRepositoryImportCommit` carries no commit today, so the graph value has to be added to
it. The mutation already loads the node, so it reads `repo.commit.value` and puts it on the model.
Re-reading it later in the flow would race the concurrent pull and compare the new commit against
itself.

### Contract, either way

1. The import proceeds exactly as it does today. Detection changes nothing about it.
2. No reset is ever performed on a read-only repository (FR-009).
3. The record is written when the classification is `REWRITE`, **inside the repository-lock
   acquisition that writes the tracked commit**. Section 2 rule 7 and `data-model.md` invariant 3
   both require the read-then-increment of `rewrite_count` to sit inside a lock hold, and a
   read-only repository has no branch import to anchor it to. `import_read_only_repository_last_commit`
   already takes `lock.registry.get(name=..., namespace="repository")` around
   `update_latest_commit`, so the call belongs inside that block. If the attachment point is the
   refs checker of PR #10669 instead, its `_converge` already holds the same lock.
4. Nothing is recorded when the tracked ref or the pinned commit changed (FR-002, SC-007). The
   in-band `target_changed` flag on the workflow model carries that. Read-only repositories do not
   use the cache marker at all.
5. A read-only repository never emits the trunk signal, because it has no configured default branch.

---

## 8. Re-target suppression marker

New. Written by `backend/infrahub/graphql/mutations/repository.py::InfrahubRepositoryMutation.mutate_update`.

### Contract

| Trigger | Marker written for |
|---|---|
| `CoreReadOnlyRepository.ref` changes | The branch the mutation ran on |
| `CoreReadOnlyRepository.commit` changes | The branch the mutation ran on |
| `CoreRepository.default_branch` changes | Infrahub's default branch |

The `commit` trigger is easy to miss. SC-007 covers re-pointing to "a different branch, tag **or
commit**", and `mutate_update` submits the pull and the import when only `commit` changes. Pinning
a read-only repository to a commit that does not descend from the imported one is a deliberate
re-point, so it must be suppressed exactly like a `ref` change.

1. The marker is written after the update succeeds, and **before** any workflow is submitted. The
   read-only path submits a pull and an import from inside the same mutation. If the marker landed
   after the submission, the import could reach the classification first and record a spurious
   rewrite on a deliberate re-target.
2. It expires after one hour.
3. **The marker covers read-write repositories only.** A read-only re-target is carried in band
   instead: the mutation already computes the comparison, so it travels on the workflow model as an
   explicit flag. No cache, no expiry and no timing question on that path. See section 7.
4. **Exactly one component reads the marker: the detector's caller in the sync path**,
   `collect_pending_imports`. It reads and deletes it in one step, then passes the result to
   `classify` as `target_changed`. The detector never touches the cache, and neither does the
   recorder.
5. The read is destructive, so one marker suppresses one classification. A marker that outlived its
   reconciliation cannot go on suppressing genuine rewrites for the rest of its hour.
6. A lost marker produces one spurious record. The reconciliation is identical either way. This is
   documented in `research.md` R4 and in the knowledge docs.
7. The marker is read within one cron cycle of being written, because the widened candidate
   selection above puts the re-targeted trunk in the classified set as soon as its graph commit
   stops matching the remote head. There is no per-repository sync to submit:
   `GIT_REPOSITORIES_SYNC` is a single cron flow with `concurrency_limit=1` and `CANCEL_NEW`.

> An earlier draft had the recorder read the marker. That is incompatible with the recorder writing
> nothing unless the classification is already `REWRITE`: the recorder would return at step 1 and
> never consume the marker, which would then survive its full hour and suppress the next genuine
> rewrite of that branch. One reader, one consumer, and the consumption happens at classification
> time.

### How the read-write marker gets read

A `default_branch` edit **moves no git ref**, so `compare_local_remote` reports nothing for it. An
earlier draft answered this by having the mutation submit a sync for that repository. **There is no
such workflow.** `GIT_REPOSITORIES_SYNC` is one cron flow over every repository, with
`concurrency_limit=1` and `CANCEL_NEW`, so a submission would either be cancelled or re-run the
whole fleet.

The widened candidate selection is what makes the marker readable. The edit changes which remote
branch feeds Infrahub's default branch, so the graph commit for that branch stops matching the
remote head, and the next cron cycle picks it up. That is within a minute, well inside the marker's
hour.

### The read-write writer does not exist yet

`InfrahubRepositoryMutation.mutate_update` currently returns to `super().mutate_update` immediately
for any kind other than `CoreReadOnlyRepository`, so there is **no** existing comparison of the old
and new `default_branch`. Only the read-only comparison (`current_ref` against `new_ref`) is
already there. The read-write marker therefore needs that comparison added before the early return.
This is a change to the mutation, not a reuse of something already computed.

---

## 9. The merge guard

Changed. `backend/infrahub/git/tasks.py::merge_git_repository`.

FR-005 covers paths that advance a worktree **from the remote**. The merge path advances the
destination from local state and reads its source commit from the local branch ref, so FR-005 never
reaches it. This guard closes that.

### Contract

1. Fetch, then compare the **source** branch worktree and the **destination** branch worktree
   against their remote heads, using the same ancestry gateway as section 1.
2. When either has diverged, **refuse the merge** and raise a typed error naming a divergent remote
   history. The message never says "conflict" (FR-003, FR-017).
3. Never reset a diverged branch and merge it (FR-005c).
4. A locally-ahead branch is not diverged. It merges as it does today.

### Why it refuses instead of reconciling

`InfrahubRepository.merge` calls `update_commit_value` on the destination **before** it pushes. So
a reset-then-merge writes the merge commit to the graph, the next cycle finds the graph and the
remote in agreement, and the branch classifies `UNCHANGED`. The rewrite is then never recorded,
the trunk signal never fires, and the rewritten content is never re-imported. Resetting the source
is worse: it merges objects the graph never imported.

Reconciliation has one owner. The synchronisation cycle resets, records, signals and re-imports,
under the repository lock. A refused merge fails loudly, the next cycle reconciles, and the retry
succeeds.

### Accepted residual risk

The remote can be rewritten between this guard's fetch and the push that follows the merge. The
guard narrows that window and does not close it, so FR-005b is best-effort rather than guaranteed.
Closing it would need the remote to reject the push, which is branch protection on the remote and
outside this work.
