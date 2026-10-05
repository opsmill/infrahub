# Data Model: Git remote writeback failure handling

**Feature**: `dev/specs/ifc-3220-writeback-failure-handling`
**Date**: 2026-10-02, revised after [critiques/critique-20261002-1500.md](critiques/critique-20261002-1500.md)

> **Governance**: the "Schema changes" section is an "Ask First" change under `AGENTS.md`. It is a
> database schema change, and the attributes and two mutations change the GraphQL schema. The
> design is complete, but it needs a maintainer's sign-off before implementation.

---

## Schema changes

### Nine attributes on `CoreRepository`

Declared in `backend/infrahub/core/schema/definitions/core/repository.py`, on `CoreRepository`
only. `CoreReadOnlyRepository` and `CoreGenericRepository` are unchanged.

Every attribute has these settings in common:

| Setting | Value | Why |
|---|---|---|
| `branch` | `BranchSupportType.LOCAL` | Never in a diff, never merged, never a conflict (FR-019). |
| `read_only` | `True` | Left out of the generated create, update and upsert inputs (FR-009). |
| `optional` | `True` | No backfill, no `GRAPH_VERSION` bump. |
| `default_value` | none | A null value means "never used". |
| `display` | `extra` | Kept out of the main view. The frontend also keeps them out of the "extra" toggle and the column picker, and renders them in a section of their own, read from the default branch (FR-025). |
| `allow_override` | `NONE` | A user schema cannot redefine them. |

| Name | Kind | Label | Meaning |
|---|---|---|---|
| `delivery_status` | `Dropdown` | Push to remote | The required action. See "Status" below. A null value reads as `none`. |
| `delivery_failure_cause` | `Dropdown` | Push failure cause | Why the last attempt failed. Null when nothing failed. |
| `delivery_error` | `TextArea` | Push error | The remote's message of the last failed attempt, verbatim, with credentials removed. |
| `delivery_queue` | `JSON` | Pending pushes | The queue. See `DeliveryQueue`. |
| `delivery_held_regeneration` | `JSON` | Held regeneration | The held set. See `HeldRegeneration`. |
| `delivery_last_abandonment` | `JSON` | Last abandoned push | See `AbandonmentRecord`. |
| `delivery_last_delivered_commit` | `Text` | Last pushed commit | The commit of the last delivery that pushed. |
| `delivery_reverted` | `JSON` | Reverted push | See `RevertedDelivery` (FR-021). |
| `delivery_progress` | `JSON` | Push progress | See `DeliveryProgress`. Kept apart from the queue, so a progress write never rewrites the queue. |

Order weights place them after `sync_status`, in the order above. Each description ends with "Live
on the default branch only." and stays within the 128-character limit of
`AttributeSchema.description`. The rest of the rule, that another branch holds a copy from its fork
point, lives in the GraphQL contract's comment and in this document.

The labels are provisional. INFP-671 owns the status vocabulary, and a label change needs no
migration. The attribute names never carry the label.

#### Status

`delivery_status` choices, backed by a new `RepositoryDeliveryStatus` `StrEnum` in
`core/constants/__init__.py`, beside `RepositorySyncStatus`:

| Value | Label | Colour | Meaning |
|---|---|---|---|
| `none` | Nothing pending | grey | The queue is empty. |
| `pending` | Pending | blue | An attempt runs, an attempt is about to run, or an automatic retry waits. |
| `action-required` | Action required | red | No automatic attempt will run. A user must act. |

#### Failure cause

`delivery_failure_cause` choices, backed by `RepositoryDeliveryFailureCause`. The required action is
a function of the cause, so the frontend derives it, and no attribute stores it. Every required
action while something is pending ends with "Imports from the remote default branch are paused until
the pending pushes clear."

| Value | Label | Retried automatically | Required action |
|---|---|---|---|
| `remote-unreachable` | Remote unreachable | yes | Wait, or retry once the remote is reachable. |
| `remote-advanced` | Remote moved during the push | yes | Wait, or retry. |
| `record-failed` | Pushed, not recorded | yes | Wait, or retry. The remote has the content. |
| `not-found` | Repository not found on the remote | no | Check the location, and that the credential can see the repository, then retry. |
| `certificate` | Certificate verification failed | no | Fix the certificate configuration, then retry. |
| `credentials` | Credentials rejected | no | Fix the credential, then retry. |
| `permission` | Push refused by the remote | no | Grant push permission or lift the branch protection, then retry. |
| `import-failed` | Import of the delivered commit failed | for a database or connection fault | Fix the content on the remote, then retry. |
| `replay-conflict` | A pending merge conflicts with the remote | no | Merge the source branch on the remote by hand, then retry. Or abandon. |
| `source-discarded` | A source commit is no longer on the remote | no | Abandon. |
| `destination-rewritten` | The remote branch history was rewritten | no | Abandon. |
| `unclassified` | Unclassified failure | no | Read the message, then retry or abandon. |

`replay-conflict`, `source-discarded` and `destination-rewritten` are the "unreplayable" causes.
FR-020 names `source-discarded`. FR-022 names `destination-rewritten`.

#### Actions by status

A delivery is **stale** when its status is `pending`, no retry is due in the future,
`last_progress_at` is older than 15 minutes, and the repository lock is free (`research.md` R20).
Staleness decides what the recovery check does. It no longer gates the user's actions.

| Status | Retry | Abandon |
|---|---|---|
| `none` | refused: nothing pending | refused: nothing pending |
| `pending`, an attempt running or a retry due | allowed. It waits for the lock, and finds nothing if the running attempt delivered. | allowed. It waits for the lock, then checks the version. |
| `pending`, stale | allowed | allowed |
| `action-required` | allowed | allowed |

---

## JSON values

Each JSON attribute holds one Pydantic model, serialised with `model_dump(mode="json")` and parsed
with `model_validate`. Each model has a `format` field, `1` today, so a later shape can be read next
to an old one. The models live in `backend/infrahub/git/writeback/models.py`. Principle III forbids
untyped dictionaries for this data.

### `DeliveryQueue`

| Field | Type | Meaning |
|---|---|---|
| `format` | `Literal[1]` | |
| `version` | `int` | Starts at 0 for an empty queue that was never used. A null `delivery_queue` reads as version 0. Increases by one when an entry is added or removed. A flag change on an entry does not move it. An abandonment names it. |
| `entries` | `tuple[PendingMerge, ...]` | In merge order. |
| `removed_entry_ids` | `tuple[str, ...]` | The last 256 entry ids that left the queue. `enqueue` refuses them, and the ids of `delivery_last_abandonment.entries` too. This is the second guard of FR-005b. The first guard is `GitRepositoryMerge.pending_merge_enqueued`: the merge flow writes an entry only when it is `False`, that is, when no try of the dispatcher's enqueue returned (`research.md` R3). |
| `import_owed_commit` | `str \| None` | A recorded commit whose import has not succeeded yet (FR-023). Set only while the queue is non-empty. |

### `DeliveryProgress`

| Field | Type | Meaning |
|---|---|---|
| `format` | `Literal[1]` | |
| `last_progress_at` | `datetime \| None` | Moves at every enqueue, attempt start, step boundary, recorded failure and recovery touch. Drives staleness. |
| `attempt_started_at` | `datetime \| None` | The start of the last attempt. |
| `retry_due_at` | `datetime \| None` | When a waiting automatic retry is due. Null when none waits. |

### `PendingMerge`

| Field | Type | Meaning |
|---|---|---|
| `entry_id` | `str` | A UUID. Unique in the queue. |
| `source_branch` | `str` | The Infrahub branch that merged. It can be deleted afterwards. |
| `source_git_branch` | `str` | The remote branch that holds the source commit. |
| `source_commit` | `str` | The commit Infrahub imported on the source branch. |
| `merged_at` | `datetime` | The merge time. |
| `delete_source_git_branch` | `bool` | Set by the deletion guard. The delivery deletes the branch (FR-011). |

Validation: `source_commit` is a full 40-character hexadecimal SHA. `source_git_branch` is never the
destination branch.

### `HeldRegeneration`

| Field | Type | Meaning |
|---|---|---|
| `format` | `Literal[1]` | |
| `next_hold_seq` | `int` | The sequence of the next hold. Starts at 1. |
| `artifact_definitions` | `tuple[HeldItem, ...]` | Sorted by id, one item per id. |
| `generator_definitions` | `tuple[HeldItem, ...]` | Sorted by id, one item per id. |
| `python_attributes` | `tuple[HeldPythonAttribute, ...]` | One item per `(kind, attribute)`. |
| `widen` | `HeldWiden \| None` | Set when a blanket regeneration of the repository is owed: by a full-regeneration fallback of the barrier, or by `merge_git_repository` after a failed first write (`research.md` R3, R9, R10). |
| `release_leases` | `tuple[ReleaseLease, ...]` | The releases in progress (`research.md` R10). |

`HeldItem` is `id: str`, `hold_seq: int`. `HeldPythonAttribute` is `kind: str`, `attribute: str`,
`hold_seq: int`. A repeated hold of the same identifier keeps one item and raises its `hold_seq`.
`HeldWiden` is `scope: Literal["all", "terminals"]`, `hold_seq: int`; a wider scope replaces a
narrower one. Scope `all` covers every definition and Python attribute of the repository. Scope
`terminals` covers only its artifact definitions, so the held generator items and Python items stay
owed. The barrier sets either scope. `merge_git_repository` sets scope `all` in the save that
writes an entry that the dispatcher could not write (`research.md` R3). `ReleaseLease` is
`lease_id: str`, `from_seq: int`, `up_to_seq: int`, `expires_at: datetime`.

`HeldRegeneration.with_hold(...)` adds or refreshes items with the next sequence, and reports the
previous sequence of each refreshed item. `lease_window(now)` returns the items that no live lease
covers. `without_window(lease)` removes the items of a lease's window, and the lease, and keeps the
rest. A lease is live until its `expires_at`. When its release fails, its run sets `expires_at` to
now and keeps the items, so the next lease covers them (`research.md` R10, rule 4).

No member, target or node id is stored (FR-014). The set grows with the number of definitions that
the queued merges touched, not with the data.

### `AbandonmentRecord`

| Field | Type | Meaning |
|---|---|---|
| `format` | `Literal[1]` | |
| `abandoned_at` | `datetime` | |
| `account_id` | `str` | The account that requested it. |
| `account_name` | `str` | Its name at that time. |
| `queue_version` | `int` | The version the request named. |
| `recorded_commit` | `str` | The commit the default branch kept. |
| `import_owed_commit` | `str \| None` | An import that was still owed and was dropped with the queue. |
| `entries` | `tuple[PendingMerge, ...]` | What was dropped. |

Earlier records stay readable through the temporal history of the node.

### `RevertedDelivery`

| Field | Type | Meaning |
|---|---|---|
| `format` | `Literal[1]` | |
| `delivered_commit` | `str` | The delivered commit that a rewrite discarded. |
| `new_head` | `str` | The head the reconciliation moved to. |
| `detected_at` | `datetime` | |

---

## The narrowed-selection cache

Not persisted in the graph (FR-014). Written by the barrier at a hold, read by the release.

| Property | Value |
|---|---|
| Key | `repository-delivery:held:<repository id>:<hold_seq>:<identifier>` |
| Value | The narrowed request model of the candidate, serialised: `RequestArtifactDefinitionGenerate`, `RequestGeneratorDefinitionRun`, or the coalesced Python submission. |
| Time to live | `NARROWED_HOLD_TTL_SECONDS`, derived from the retry delays and the fetch and push timeouts: about 45 minutes (`research.md` R9). |
| Size bound | 512 KiB. A larger value is not written, and the release then uses the identifier alone. |
| Repeated hold | The new entry holds the union of the previous entry and the new request. When the previous entry is missing, expired or too large, no new entry is written. |
| Miss | The release dispatches the identifier with no narrowing. A miss over-executes and never skips. |

---

## State transitions

```text
                 enqueue                       attempt fails (not retryable, or last retry)
   none ───────────────────────▶ pending ─────────────────────────────▶ action-required
    ▲                             │  ▲                                     │
    │ queue empty after a         │  │ attempt fails (retryable),          │ retry submitted,
    │ delivery or an abandonment  │  │ retry waits                         │ or a new merge enqueued
    └─────────────────────────────┘  └──────────── attempt starts ◀────────┘
```

The status follows the queue only. A run with an empty queue, a held-only run for example, writes
its progress timestamps and never changes the status.

| From | Event | To | Writes |
|---|---|---|---|
| any | enqueue | `pending` | append entry, bump version, `last_progress_at` |
| any | enqueue by `merge_git_repository`, after a failed first write | `pending` | as enqueue, plus a `widen` marker of scope `all` with the next sequence, in the same save; nothing when the id is refused (`research.md` R3) |
| `pending`, `action-required` | attempt with entries starts | `pending` | `attempt_started_at`, `last_progress_at`, clear `retry_due_at` |
| `pending` | step boundary of an attempt | unchanged | `last_progress_at` |
| `pending` | retryable failure, not the final attempt | `pending` | cause, error, `retry_due_at`, `last_progress_at` |
| `pending` | not retryable, or final attempt | `action-required` | cause, error, `last_progress_at`, clear `retry_due_at` |
| `pending` | an import becomes owed | unchanged | `import_owed_commit` |
| `pending` | the owed import succeeds | unchanged | clear `import_owed_commit` |
| any but `none` | barrier holds | unchanged | items with the next sequence |
| any but `none` | delivery settles, under the repository lock | `none`, or `pending` if entries remain | remove snapshot entries into `removed_entry_ids`, bump version, last delivered commit, a release lease over the uncovered held items up to the snapshot's highest sequence, clear cause and error when `none` |
| any but `none` | abandonment, under the repository lock | `none` | remove every entry into `removed_entry_ids`, bump version, clear the owed import, the abandonment record, a release lease over the uncovered held items |
| any | release renews | unchanged | the lease's `expires_at` |
| any | release fails, so the lease expires | unchanged | the lease's `expires_at`, set to now; the items of its window stay held for the next lease (`research.md` R10, rule 4) |
| any | release clears | unchanged | remove the items of the lease's window, and the lease |
| any | recovery check submits | unchanged | `last_progress_at` |
| any | rewrite discards the last delivered commit (FR-021) | unchanged | `delivery_reverted` |
| any | guard refuses a branch deletion | unchanged | `delete_source_git_branch` on every entry that names the branch; the version does not move |

### Invariants

1. The status is `none` if and only if the queue is empty.
2. Held items that no live lease covers, behind an empty queue, mean a release is owed. The
   recovery check of `research.md` R20 starts a delivery flow for it. No path clears a held item
   without a release that covered it.
3. The queue version only increases, and only when an entry is added or removed.
4. Entries leave the queue only by a delivery that observed them on the remote, or by an
   abandonment that writes its record in the same save (FR-009, SC-006). Both happen under the
   repository lock.
5. An entry id that left the queue is never appended again. The merge flow appends only when
   `pending_merge_enqueued` is `False`, that is, when no try of the dispatcher's enqueue returned.
   The entry is then not in the queue, except in one case: a try's write committed, but its call
   raised, and every later try raised too. For that case, `enqueue` refuses an id that is still in
   `entries`, and an id that left the queue and is in `removed_entry_ids` or in the last abandonment
   record.
6. Every read and write happens on Infrahub's default branch, under the delivery-state lock.
7. A hold recorded above a release's bound survives that release's clear (FR-015). For a delivery
   the bound is the attempt's snapshot, so a hold for a merge that is still queued waits for that
   merge's delivery.
8. `import_owed_commit` is saved before the commit it names is recorded (`research.md` R4 step 9).
9. An owed import implies a non-empty queue.
10. Two live leases never cover the same held item.
11. No write emits a node mutation event (FR-026).
12. An entry that `merge_git_repository` appends comes with a `widen` marker of scope `all` in the
    same save. The follow-ups of that merge ran without a hold, so the release after the delivery
    runs their work again (`research.md` R3).

---

## New in-process types

These carry no persistence of their own. They live in `backend/infrahub/git/writeback/models.py`
unless stated otherwise.

| Type | Kind | Fields | Meaning |
|---|---|---|---|
| `WritebackIntent` | frozen dataclass | `repository_id`, `status`, `cause`, `error`, `queue`, `held`, `progress`, `last_delivered_commit` | The whole state of one repository, as the store reads it. Exposes `is_stale(now, lock_free)` and `has_work(now)`. |
| `DeliveryStage` | `StrEnum` | `fetch`, `push`, `record`, `import`, `replay`, `release` | Where an attempt failed. An input of the classifier. |
| `DeliveryFailure` | frozen dataclass | `cause`, `retryable: bool`, `message` | The classifier's output. `message` is already scrubbed. |
| `DeliveryOutcome` | `StrEnum` | `nothing-pending`, `delivered`, `observed`, `released`, `failed`, `unreplayable`, `deferred` | What one attempt did. `deferred` means a retry chain was already due. |
| `DeliveryAttemptResult` | frozen dataclass | `outcome`, `commit: str \| None`, `failure: DeliveryFailure \| None` | The service's return value. |
| `Actor` | frozen dataclass | `account_id`, `account_name` | Who requested an abandonment. |
| `HoldReceipt` | frozen dataclass | `hold_seq: int`, `previous_seqs: Mapping[str, int]` | What `hold` did: the new sequence, and the previous sequence of every refreshed item, for the cache union. |
| `PushRejectionReason` | `StrEnum`, in `git/models.py` | `policy`, `non-fast-forward`, `unknown` | Carried on `RepositoryPushRejectedError`, from the `PushInfo` flags. |
| `OwnedRegeneration` | frozen dataclass, in `core/merge/regeneration_barrier.py` | `repository_id: str \| None`, `held: HeldRegeneration`, `request: RequestT` | One barrier candidate: what to hold, who owns it, and the narrowed request to dispatch if admitted. |

### New exceptions

In `backend/infrahub/exceptions.py`:

| Class | Parent | Extra fields | Message |
|---|---|---|---|
| `RepositoryPushRejectedError` | `RepositoryError` | `reason: PushRejectionReason`, `remote_message: str` | Today's per-ref rejection wording, unchanged. |
| `RepositoryTLSError` | `RepositoryConnectionError` | none | Today's TLS wording, unchanged. |
| `RepositoryNotFoundError` | `RepositoryConnectionError` | none | Today's connection wording, unchanged. |
| `DeliveryQueueChangedError` | `ValidationError` | none | "The pending pushes of repository <name> changed since version <n>; reload and try again." |
| `NothingPendingError` | `ValidationError` | none | "Repository <name> has nothing pending to push." |

Both operational-status maps (`git/base.py::InfrahubRepositoryBase._raise_enriched_error` and
`message_bus/operations/git/repository.py::connectivity`) resolve the status with `isinstance`, most
specific first, so the two connection subtypes keep `ERROR_CONNECTION`.

---

## Payload changes

Every new field is optional with a default, so a run queued by the previous code still validates.

| Model | Module | Field | Type |
|---|---|---|---|
| `GitRepositoryMerge` | `git/models.py` | `pending_merge` | `PendingMerge \| None = None`. `None` makes the flow build the entry itself. |
| `GitRepositoryMerge` | `git/models.py` | `pending_merge_enqueued` | `bool = False`. The dispatcher sets `True` only when one of its enqueue tries returned. Only `False` makes the flow write the entry, with a `widen` marker of scope `all`. |
| `RequestArtifactDefinitionGenerate` | `git/models.py` | `repository_id` | `str \| None = None` |
| `generate_artifact_definition` flow | `git/tasks.py` | `exclude_repository_ids`, `include_repository_ids` | `list[str] \| None = None` |
| `run_generator_definition` flow | `generators/tasks.py` | `exclude_repository_ids`, `include_repository_ids` | `list[str] \| None = None` |
| `GitRepositoryDeliveryRetry` | `git/models.py`, new | `repository_id`, `repository_name` | `str` |
| `GitRepositoryDeliveryAbandon` | `git/models.py`, new | `repository_id`, `repository_name`, `queue_version` | `str`, `str`, `int` |

The actor of an abandonment comes from the workflow's `InfrahubContext`, not from the payload, so a
caller cannot name another account.

### New workflows

In `backend/infrahub/workflows/catalogue.py`, beside `GIT_REPOSITORIES_MERGE`, with the same shape:
`WorkflowType.CORE`, module `infrahub.git.tasks`, tag `DATABASE_CHANGE`.

| Constant | Name | Function |
|---|---|---|
| `GIT_REPOSITORY_DELIVERY_RETRY` | `git-repository-delivery-retry` | `retry_repository_delivery` |
| `GIT_REPOSITORY_DELIVERY_ABANDON` | `git-repository-delivery-abandon` | `abandon_repository_delivery` |

### New fallback reason

`core/merge/regeneration_dispatcher.py::FullRegenerationReason.HELD_SET_UNRESOLVED`, "Held
regeneration could not be resolved".

---

## What is not changed

| Thing | Why |
|---|---|
| `operational_status` | It describes whether the remote is reachable. A push failure has never written it, and two tests pin that. |
| `sync_status` | Delivery failures are not folded into it, so INFP-671 can redefine it. An import failure of a delivered commit still sets it, as any import failure does. |
| `commit` | It is still written only once the remote holds the commit (FR-001). |
| `CoreReadOnlyRepository`, `CoreGenericRepository` | A read-only repository never delivers. |
| `NodeMutationOrigin` | No new member. The store emits no node events at all (`research.md` R2). |
| `EventType` | No new member. The abandonment record lives on the repository (`research.md` R8). |
| `GRAPH_VERSION` | Optional attributes are added by the schema migration of `infrahub upgrade`. |
