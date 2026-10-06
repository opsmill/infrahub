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

Conflating them breaks the feature in one of two ways:

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
| Either identifier is malformed | propagates as `RepositoryError`; the branch joins `failed_imports` |
| **The imported commit is absent and the remote head is absent too** | propagates as `RepositoryError` |
| **The imported commit is absent from the local object database, `target_changed` is false** | **`REWRITE`** (see below) |
| **The imported commit is absent, `target_changed` is true** | **`RETARGET`** |
| `imported_commit` is an ancestor of `remote_head` | `FAST_FORWARD` |
| The remote head does not contain the imported commit, `target_changed` is false | `REWRITE` |
| The remote head does not contain the imported commit, `target_changed` is true | `RETARGET` |
| Any other git failure | propagates as `RepositoryError`; the branch joins `failed_imports` |

The absent-object rows come **before** the ancestry rows because those rows cannot be
evaluated at all when the object is gone: the ancestry call raises instead of answering. They also
honour `target_changed`, so a deliberate re-target whose old commit has been garbage-collected is
still a re-target rather than a recorded rewrite.

**The two commits are not required in the same way.** An absent imported commit is a
classification, because a force push followed by a prune loses it in the ordinary way. An absent
remote head is a fault, because the fetch that ran before the classification brought that object
in. The absent-object rows therefore require the remote head to be present before they classify.
Without that check a remote head naming an object the repository does not hold reads as `REWRITE`,
so the recorder writes a record and the trunk signal fires over a broken clone. The ancestry rows
need no such check: the ancestry call raises on its own when either object is missing.

**A remote head behind the graph commit means the remote was rewound.** Every write of the graph
commit records a commit the remote already carries. `create_locally` records straight after a
clone. `pull` records a commit the fetch brought in. `reset_to_commit` records the SHA it pinned.
The synchronisation's new-branch path pushes first, and a rejected push raises into
`failed_imports` before the record is reached. `merge` pushes before it records and resets the
worktree when either step fails. The read-only paths record what they read from the remote. `merge`
skips the push when its caller passes `push_remote=False`, and records all the same. Only a test
passes it today, and `rebase` forwards it, so the audit holds for the product while that parameter
has no production caller. No
path leaves the graph holding a commit the remote never had, so a remote head that is an ancestor
of the imported commit means a force push, or a ref moved backwards. That discards content exactly
as a rewrite does, so it is reconciled and recorded.

**The worktree comparison reaches the same conclusion.** It used to leave a worktree ahead of its
remote alone, to protect a commit a rejected push had left behind. That state no longer arises:
`InfrahubRepository.merge` pushes before it records and resets the destination when either step
fails, `rebase` delegates to `merge`, and a branch whose creation push failed leaves the remote
with no such ref at all, which is a different row. So a worktree ahead of its remote also means a
rewind, and it resets.

Graph against remote still decides the record. Worktree against remote still decides the reset.
Keeping them apart is what lets one worker record while every other worker converges.

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

**Only branches that can still record a commit enter the second set.** The API refuses a commit on
a branch that needs a rebase, is being merged, failed a merge or is merged, a branch being deleted
loses its nodes, and a branch Infrahub no longer lists has nowhere to record one. The graph
comparison would select any of them again on every cycle and keep the early return from firing.
`git/branch_status.py::accepts_commit_write` holds the rule, and the collector's filter of the
branches it advances uses it too. A refusal the listing did not predict, such as a merge that starts
during the cycle, fails that branch alone. The periodic sync leaves them
out of the graph commits it passes down, using the branch listing it already reads once per cycle.

**A branch new to this worker is classified too.** The periodic sync runs on whichever worker picks
it up, and that worker may never have held the branch. The graph can still record a commit another
worker imported and the remote has since discarded. Skipping the classification there would leave
the rewrite unrecorded whenever the cycle lands on such a worker.

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

**"No more than one record" assumes cycles do not overlap.** Two cycles running at once would both read
the same stale graph commit and both record. `GIT_REPOSITORIES_SYNC` prevents that today with
`concurrency_limit=1` and `CANCEL_NEW`. If that ever changes, the count needs a compare-and-set
rather than a read-then-write.

A branch with no recorded commit has never been imported. It cannot be a rewrite, so it classifies
`FAST_FORWARD` and takes the ordinary import path.

**A read must tell a written commit from an inherited one.** `git_branch_create` creates and
pushes the branch but never calls `update_commit_value`, and `commit` is `LOCAL`, so the branch
reads the trunk's value as of its fork point. A plain read therefore almost always returns
something, and the classifier would compare a branch's remote head against a trunk commit that has
nothing to do with it. That classifies a healthy branch `REWRITE`.

Branch creation must write the commit, and the per-branch read must report a value the branch
never had as absent. `get_repositories_commit_per_branch` returns `commit.value`, which the
`LOCAL` fallback fills in, so the read needs to know which branch the value was written on. With
that, a branch created before the write lands classifies `FAST_FORWARD` and takes the ordinary
import path, and the rule above is live rather than unreachable.

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
  the worktree on the remote head. Only `REWRITE` records. `FAST_FORWARD`, `REMOTE_ABSENT` and
  `UNCHANGED` do neither.

**The classification decides the record. It does not decide the reset.** They read different
inputs, so one table cannot carry both.

Record and signal, from the classification (graph against remote):

| Classification | Record | Signal |
|---|---|---|
| `UNCHANGED` | no | no |
| `FAST_FORWARD` | no | no |
| `REWRITE` | yes | trunk only |
| `RETARGET` | no | no |
| `REMOTE_ABSENT` | no | no |

Reset, from this worker's worktree against the remote, decided independently:

| Worktree against remote head | Graph commit | Action |
|---|---|---|
| Equal | equals the remote head | nothing |
| Equal | **differs from the remote head** | **write the commit, queue the import, and record if the classification is `REWRITE`** |
| Worktree is an ancestor of the remote head | any | reset onto the remote head, which fast-forwards it. Not a pull: a pull fetches again and can import a newer commit than the one classified |
| Remote head is an ancestor of the worktree | any | reset onto the remote head. The remote was rewound |
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

A `RETARGET` that reset nothing would leave the branch stuck on a history the remote no longer has,
which is the defect this feature removes. The PRD calls a deliberate re-target "reconciled, not
reported": reconciled is the reset, not reported is the missing record.

### Ancestry gateway

The gateway is bound to one repository when it is built, so no call takes a repository:

```text
is_ancestor(ancestor_commit, descendant_commit) -> bool
```

```text
has_commit(commit) -> bool
```

```text
require_commit(commit) -> None
```

```text
require_present_commit(commit) -> None
```

`is_ancestor` runs `git merge-base --is-ancestor` as a plain git command through GitPython, and
reads exit status 1 as "not an ancestor" rather than as a failure. Every git failure leaves it as
a `RepositoryError`, so the detector handles one exception type and imports no git library.

`has_commit` answers whether the object is present, and it is what makes the absent-object rows
reachable. Without it "the object is gone" and "git could not be asked" arrive as the same
`RepositoryError`, so a commit that was garbage-collected raises on every cycle and the branch
never classifies at all. It is a separate call precisely so a missing object is a fact the detector
can act on rather than a failure it has to swallow.

`require_commit` checks the shape of an identifier alone: it raises unless the string is a full
object name, and a well formed identifier whose object is absent passes. The detector calls it on
both commits before any comparison, so a malformed identifier cannot read as a rewrite.

`require_present_commit` raises unless the object database holds that commit. It is the strict
form the absent-object rows need for the remote head. It raises rather than returning a boolean
because the error carries the repository name, which the gateway holds and the detector does not.
Returning a boolean would make the detector compose a git error message of its own.

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
2. Needs no precondition about the two commits matching. `RefDivergence` rejects at construction
   any classification other than `UNCHANGED` whose commits are equal, so every `REWRITE` that
   reaches the write path already carries two different commits. An `UNCHANGED` divergence does
   reach `record()` with matching commits, and rule 1 above stops it before anything is written.
3. Reads the current `rewrite_count` on that branch, writes `count + 1`, treating an absent value
   as zero.
4. Writes all four attributes in one mutation, on the Infrahub branch named.
5. Overwrites the previous record. It never accumulates and never clears.
6. Emits `RepositoryHistoryRewrittenEvent` at most once, and only when `is_default_branch` is true.
   **At most, not exactly.** The record write and the emit are separate operations. If the record
   lands and the emit fails, the next cycle sees the graph and the remote agree, classifies
   `UNCHANGED`, and nothing ever sends that signal again. What the design guarantees is "never
   more than one". Closing the gap needs an outbox, which is
   more machinery than a rare event is worth. It sits beside the record-write risk below.
7. Runs inside the repository-lock acquisition that **writes the reconciled commit**, immediately
   after that write. See "Where it is called" below.

### Where it is called

`RepositorySyncer.sync` takes the repository lock twice: once around `collect_pending_imports`, and
once per branch around `apply_branch_import`. The reconciled commit is written inside the **first**
one: `collect_pending_imports` moves every branch with `reset_to_commit`, which defaults
`update_commit_value=True`.

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

**Not after the import.** The commit is written during collection, so a recorder placed after the
import would find the next cycle reading the *new* head as the imported commit and classifying
`UNCHANGED`. The rewrite would never be recorded and the trunk event would never fire.

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
hard-resets onto the remote head whenever the worktree does not lead to it.

### Contract

| Condition | Behaviour |
|---|---|
| No origin | Returns `False`, unchanged. |
| Worktree head equals remote head | Returns `True`, unchanged. |
| Worktree head is an ancestor of remote head | Pulls, unchanged. |
| **Remote head is an ancestor of worktree head** | **Hard-resets onto the remote head.** The remote was rewound. |
| Neither is an ancestor of the other | Hard-resets onto the remote head and creates the commit worktree. |
| No worktree, `create_if_missing` and a branch id | Creates the worktree, unchanged. |

**The rule is "the worktree does not lead to the remote head".** Reset unless the worktree already
is the remote head, is an ancestor of it, or the remote carries no such ref. A worktree ahead of
its remote resets like any other, because nothing leaves a commit there that exists nowhere else.

The pull path answers this without any classification context: both ancestry questions are the
same gateway call the detector makes. What the pull path cannot do is tell a rewrite from a
deliberate re-target, because that needs the suppression marker. It does not need to: both reset,
and neither records.

### Rules

- The reset honours `update_commit_value` the same way the pull does, and forces no value of its
  own. The broadcast handler passes `update_commit_value=False`, so a reset driven by a broadcast
  writes nothing. A worker that heard **no** broadcast reaches the reset through `pull` or through
  `collect_pending_imports`, and both default to `True`, so that worker does write the commit. The
  write is idempotent: the reconciling worker already stored the same value. Do not read the
  broadcast handler's flag as a property of self-healing.
- The reset writes no rewrite record and emits no event, whatever the caller (FR-007).
- No message raised from this path calls a divergent history a conflict (FR-003, FR-017).
- **The unconditional reset is safe because of the merge ordering.** `InfrahubRepository.merge`
  pushes before it records and resets the destination worktree on failure, so no merge commit is
  left on one worker alone for this reset to discard.

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

**The catch boundary.** This function is the single owner of logging and recording a failed
reconciliation. It never propagates a failure of the configured default branch. It re-raises the
failure of any other branch, because the existing path tags the repository from that raise, and the
per-repository `try` added to `sync_remote_repositories` keeps the raise from reaching the next
repository.

### Contract

| Before | After |
|---|---|
| One message, for `staging_branch or registry.default_branch` only | One message, carrying every branch the cycle advanced |
| Sent after the sync returns, so a raise skips it | Sent before the failure for a failed branch is re-raised |
| Commit read from `repo.default_branch` | Commit taken per branch from `ReconciledBranch` |
| A staging sync names the staging branch | A staging sync names the branch its trunk maps onto, as `ReconciledBranch` does, so other workers move their trunk worktree |

### Rules

- Exactly one message per repository per cycle. The handler holds the repository lock once and
  fetches once.
- When the cycle advanced no branch, no message is sent. **This removes a heal that exists today.**
  `sync_repository_from_origin` currently sends the pinned trunk commit every cycle even when
  nothing changed, which brings a worker that missed an earlier broadcast back within a minute. The
  pull-path self-heal of FR-005 replaces it. **Order the two:** keep sending the trunk message
  unconditionally until the pull-path reset ships, then drop it. Shipping the "no branch advanced,
  no message" rule first leaves a stale worker with no heal on either side.
- When every branch failed, the coalesced message carries no pairs. The unconditional trunk
  message above still goes, because it is what heals a stale worker and nothing in this phase
  replaces it.
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
6. **It resets with `reset_to_commit` and runs no ancestry check.** It moves the worktree onto
   the pinned SHA without asking how the two commits relate, which is what the pull path asks.
   That is deliberate, because the broadcast carries a SHA the sending worker already resolved
   and the receiving worker is meant to converge on exactly it.
7. One pair failing does not stop the rest. Each failure is logged with the branch it belongs to,
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

The path a rewrite takes is `import_read_only_repository_last_commit`, so that is where the
detection belongs. **That flow does not tell you whether anything was re-pointed**, because two
different mutations submit it:

| Submitted by | Meaning | `target_changed` |
|---|---|---|
| `ReadOnlyRepositoryImportLastCommit` | pick up whatever the tracked ref now resolves to | false |
| `InfrahubRepositoryMutation.mutate_update`, `ref` changed | deliberate re-point | true |
| `InfrahubRepositoryMutation.mutate_update`, `commit` changed | deliberate re-pin | true |

`mutate_update` submits `GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT` alongside
`GIT_REPOSITORIES_PULL_READ_ONLY` on every `ref` or `commit` change. So the flow **must** read
`target_changed` from its own model and must never infer it from the fact that it is running. The
flag is set by whichever mutation submitted the work.

That also fixes the phase order: the in-band flag ships **with** the classification, not after it.
A classification that lands first would treat every re-point as a rewrite.

### Which commit is the "imported" one here

The same rule as section 1: **the commit recorded in the graph** for that Infrahub branch, never
anything read from disk. This needs saying because the read-only path makes it easy to get wrong.
`update_latest_commit` resolves only the *new* head, `import_read_only_repository_last_commit`
calls `init` without a commit, and the update mutation submits `pull_read_only` concurrently, which
can write the new commit to the graph first.

The graph commit is read **inside the repository lock, in the flow**, not in the mutation. The
mutation loads the node anyway, so putting `repo.commit.value` on the model looks cheaper, and it
is wrong: that read happens outside the lock. Two `ImportLastCommit` runs queued together would
both carry the same old commit, both classify `REWRITE`, and both record, so the count rises twice
for one rewrite.

Reading inside the lock costs one query on a path that already holds the lock, and makes the
read-then-increment of the count atomic with respect to another run.

There is no race with the concurrent `pull_read_only` to avoid here. That flow is submitted by
`mutate_update`, which is the re-point path and always arrives with `target_changed` true, so it
never records.

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
| `CoreRepository.default_branch` changes | Infrahub's default branch |

**That is the whole table.** Read-only repositories write no marker. A read-only re-point, whether
it changes `ref` or `commit`, is carried in band on the workflow model instead. SC-007 covers "a
different branch, tag **or commit**", and both of those reach the flow as an explicit
`target_changed` flag rather than through the cache.

1. The marker is written after the update succeeds, and before the mutation returns. Nothing else
   in that mutation reads it, so the ordering only has to put the write before the first
   synchronisation cycle that could classify the branch.
2. It expires after one hour.
3. **Exactly one component touches the marker: the detector's caller in the sync path**,
   `collect_pending_imports`. It reads the marker, passes the result to `classify` as
   `target_changed`, and **deletes it only after the commit write for that branch has succeeded**.
   The detector never touches the cache, and neither does the recorder.
4. Deleting at classification time is wrong. The reset, the commit write and the import all come
   after it, and any of them can fail. The marker would already be gone, so the next cycle sees a
   re-target it has no record of, classifies `REWRITE`, writes a record and **fires the trunk
   webhook**. Deleting after the commit write means a failed cycle simply retries with the marker
   still in place.
5. A lost marker costs more than a wrong row. It produces a false rewrite record **and** a false
   trunk webhook to whatever a customer has subscribed. `research.md` R4 carries this as an
   accepted loss path.
6. The cache has no atomic get-and-delete, so reading and deleting are two operations with a window
   between them. Nothing guards that window except `GIT_REPOSITORIES_SYNC` running with
   `concurrency_limit=1` and `CANCEL_NEW`, which keeps two cycles from overlapping. If that ever
   changes, this needs a compare-and-delete.
7. The marker is read within one cron cycle of being written, because the widened candidate
   selection above puts the re-targeted trunk in the classified set as soon as its graph commit
   stops matching the remote head. There is no per-repository sync to submit:
   `GIT_REPOSITORIES_SYNC` is a single cron flow with `concurrency_limit=1` and `CANCEL_NEW`.
8. **A marker whose branch never becomes a candidate is still deleted at the end of the cycle.**
   A re-point can leave the graph commit and the worktree both equal to the remote head, for
   example when the remote default branch is renamed without moving and `default_branch` is edited
   to match. The branch then enters no candidate set, nothing reads the marker, and for the rest of
   its hour it would turn a genuine trunk rewrite into a `RETARGET`: reset, no record, no trunk
   webhook. Sweeping the repository's remaining markers when the cycle finishes with it bounds
   every marker to one cycle.

> The recorder must not be the reader. It writes nothing unless the classification is already
> `REWRITE`, so on a `RETARGET` it would return before reaching the marker and leave it to survive
> its full hour and suppress the next genuine rewrite of that branch.

### How the read-write marker gets read

A `default_branch` edit **moves no git ref**, so `compare_local_remote` reports nothing for it.
There is no per-repository sync to submit either: `GIT_REPOSITORIES_SYNC` is one cron flow over
every repository, with `concurrency_limit=1` and `CANCEL_NEW`, so a submission would either be
cancelled or re-run the whole fleet.

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
2. When either has diverged, compare the **graph commit** for that branch against the remote head
   as well. The two answers mean different things:

| Worktree | Graph commit | Action |
|---|---|---|
| Diverged | also diverged | **Refuse.** The rewrite is unrecorded, and merging would erase it. |
| Diverged | matches the remote | **Reset the worktree and merge.** The rewrite is already recorded; only this clone is behind. |

3. A refusal raises a typed error naming a divergent remote history. The message never says
   "conflict" (FR-003, FR-017).
4. Never reset a branch whose **graph commit** is stale and then merge it (FR-005c). That is the
   case where the merge commit would hide the rewrite.
5. A worktree ahead of its remote has been rewound. It is reset before the merge, like any other.

### Why it refuses instead of reconciling

`InfrahubRepository.merge` pushes the merge commit **before** it records it on the destination. So
a reset-then-merge puts the merge commit on the remote and in the graph, the next cycle finds the
graph and the remote in agreement, and the branch classifies `UNCHANGED`. The rewrite is then never
recorded, the trunk signal never fires, and the rewritten content is never re-imported. Resetting
the source is worse: it merges objects the graph never imported.

Reconciliation has one owner. The synchronisation cycle resets, records, signals and re-imports,
under the repository lock. A refused merge fails loudly, the next cycle reconciles, and the retry
succeeds.

**That is why a stale clone alone is not a refusal.** The cron heals whichever worker runs it, not
the worker the merge lands on, so refusing on a stale worktree with a current graph commit would
refuse again on every retry. Resetting is safe there: nothing is lost, because the rewrite is
already recorded.

### Accepted residual risk

The remote can be rewritten between this guard's fetch and the push that follows the merge. The
guard narrows that window and does not close it, so FR-005b is best-effort rather than guaranteed.
Closing it would need the remote to reject the push, which is branch protection on the remote and
outside this work.
