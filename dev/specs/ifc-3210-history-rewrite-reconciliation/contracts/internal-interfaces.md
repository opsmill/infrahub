# Internal contracts: Git history-rewrite reconciliation

**Feature**: `dev/specs/ifc-3210-history-rewrite-reconciliation`
**Date**: 2026-09-29

These are the backend interfaces this feature introduces or changes. They are not user-facing. The
user-facing GraphQL surface is in `repository_rewrite.graphql`.

---

## 1. `RemoteDivergenceDetector`

New. `backend/infrahub/git/divergence/detector.py`.

Classifies one tracked ref's remote head against the commit Infrahub imported. It holds no git
code: a gateway supplies the two commits and answers the ancestry question.

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
| Neither is an ancestor, `target_changed` is false | `REWRITE` |
| Neither is an ancestor, `target_changed` is true | `RETARGET` |
| The ancestry question cannot be answered | `REWRITE` |

**The `LOCAL_AHEAD` row is what keeps this safe without PR #10465.** A branch left ahead of its
remote after a rejected push is a state the product reaches today. Without that row it falls into
"neither is an ancestor", classifies `REWRITE`, and the reset discards the unpushed commit. With
it, the branch resets nothing, records nothing, and keeps exactly today's behaviour.

`REMOTE_ABSENT` likewise keeps current behaviour: a tracked ref that disappeared from the remote is
not a lineage break. `spec.md` names it as an edge case.

### Rules

- The detector never contacts the remote. The caller fetches first.
- The detector never writes. It returns a value.
- The detector runs without a database, so its unit tests need none.
- **`target_changed` is supplied by the caller, and the caller is the only component that touches
  the suppression marker.** It reads the marker, deletes it, and passes the result here. Neither
  the detector nor the recorder reads the cache. See section 8.
- Only `REWRITE` leads to a reset and a record. `LOCAL_AHEAD`, `RETARGET`, `REMOTE_ABSENT`,
  `UNCHANGED` all leave the branch alone.

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
6. Emits `RepositoryHistoryRewrittenEvent` exactly once, and only when `is_default_branch` is true.
7. Runs inside the **same** repository-lock acquisition that applies the branch import, after the
   import has succeeded. See "Where it is called" below.

### Where it is called

`RepositorySyncer.sync` takes the repository lock twice: once around `collect_pending_imports`, and
once per branch around `apply_branch_import`. The recorder runs inside the **second** one, after
`apply_branch_import` returns.

Two things follow, and both are the reason for the placement:

- **The count is safe.** The read-then-increment of step 3 happens under the same lock hold as the
  import. Calling the recorder from `collect_pending_imports` would put it in the *first*
  acquisition, and two workers could then read the same count and write the same value.
- **The record cannot outrun the work it describes.** A record written during collection, followed
  by a failed import, would claim a reconciliation that never completed, and would fire the trunk
  event for it. Writing after the import means a failed import leaves no record and no event, and
  the next cycle classifies the branch `REWRITE` again and retries the whole thing.

The classification is produced during collection and carried to this point on
`ReconciledBranch.divergence`.

### Injected ports

Principle III and `.agents/rules/backend-component-design.md` require the collaborators to be named
protocols passed to the constructor, so the unit tests of T039 need no database and no mocks.

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

Before it pulls, it asks whether the branch worktree head is an ancestor of the remote head. When it
is not, it hard-resets onto the remote head instead of pulling.

### Contract

| Condition | Behaviour |
|---|---|
| No origin | Returns `False`, unchanged. |
| Worktree head equals remote head | Returns `True`, unchanged. |
| Worktree head is an ancestor of remote head | Pulls, unchanged. |
| Worktree head is not an ancestor | Hard-resets onto the remote head and creates the commit worktree. |
| No worktree, `create_if_missing` and a branch id | Creates the worktree, unchanged. |

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
- When the cycle advanced no branch, no message is sent.
- When every branch failed, no message is sent, and the failure is raised as it is today.
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

Changed. Attachment point depends on whether PR #10669 has merged. See `research.md` R10.

| If #10669 has merged | If it has not |
|---|---|
| `backend/infrahub/git/refs_check/checker.py::ReadOnlyRepositoryRefsChecker._detect_movements` already produces `RefMovement(previous_head, new_head)`. Classify each movement and call the recorder. | `backend/infrahub/git/repository.py::InfrahubReadOnlyRepository.update_latest_commit` resolves the same two commits. Classify there and call the recorder. |

### Contract, either way

1. The import proceeds exactly as it does today. Detection changes nothing about it.
2. No reset is ever performed on a read-only repository (FR-009).
3. The record is written when the classification is `REWRITE`.
4. Nothing is recorded when the tracked ref itself changed (FR-002, SC-007). The suppression marker
   carries that, written by the same mutation that changed the ref.
5. A read-only repository never emits the trunk signal, because it has no configured default branch.

---

## 8. Re-target suppression marker

New. Written by `backend/infrahub/graphql/mutations/repository.py::InfrahubRepositoryMutation.mutate_update`.

### Contract

| Trigger | Marker written for |
|---|---|
| `CoreReadOnlyRepository.ref` changes | The branch the mutation ran on |
| `CoreRepository.default_branch` changes | Infrahub's default branch |

1. The marker is written after the update succeeds, and **before** any workflow is submitted. The
   read-only path submits a pull and an import from inside the same mutation. If the marker landed
   after the submission, the import could reach the classification first and record a spurious
   rewrite on a deliberate re-target.
2. It expires after one hour.
3. **Exactly one component reads it: the detector's caller.** It reads and deletes the marker in
   one step, then passes the result to `classify` as `target_changed`. The detector never touches
   the cache, and neither does the recorder. Two callers do this: the sync path in
   `collect_pending_imports`, and the read-only detection path of section 7.
4. The read is destructive, so one marker suppresses one classification. A marker that outlived its
   reconciliation cannot go on suppressing genuine rewrites for the rest of its hour.
5. A lost marker produces one spurious record. The reconciliation is identical either way. This is
   documented in `research.md` R4 and in the knowledge docs.

> An earlier draft had the recorder read the marker. That is incompatible with the recorder writing
> nothing unless the classification is already `REWRITE`: the recorder would return at step 1 and
> never consume the marker, which would then survive its full hour and suppress the next genuine
> rewrite of that branch. One reader, one consumer, and the consumption happens at classification
> time.

### The read-write writer does not exist yet

`InfrahubRepositoryMutation.mutate_update` currently returns to `super().mutate_update` immediately
for any kind other than `CoreReadOnlyRepository`, so there is **no** existing comparison of the old
and new `default_branch`. Only the read-only comparison (`current_ref` against `new_ref`) is
already there. The read-write marker therefore needs that comparison added before the early return.
This is a change to the mutation, not a reuse of something already computed.
