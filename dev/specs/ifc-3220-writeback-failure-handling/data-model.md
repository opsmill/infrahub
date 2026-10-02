# Data Model: Git remote writeback failure handling

**Feature**: `dev/specs/ifc-3220-writeback-failure-handling`
**Date**: 2026-10-02

> **Governance**: the "Schema changes" section is an "Ask First" change under `AGENTS.md`. It is a
> database schema change, and the attributes and two mutations change the GraphQL schema. The
> design is complete, but it needs a maintainer's sign-off before implementation.

---

## Schema changes

### Eight attributes on `CoreRepository`

Declared in `backend/infrahub/core/schema/definitions/core/repository.py`, on `CoreRepository`
only. `CoreReadOnlyRepository` and `CoreGenericRepository` are unchanged.

Every attribute has these settings in common:

| Setting | Value | Why |
|---|---|---|
| `branch` | `BranchSupportType.LOCAL` | Never in a diff, never merged, never a conflict (FR-019). |
| `read_only` | `True` | Left out of the generated create, update and upsert inputs (FR-009). |
| `optional` | `True` | No backfill, no `GRAPH_VERSION` bump. |
| `default_value` | none | A null value means "never used". |
| `display` | `extra` | Kept out of the main and list views. The repository page renders them in a section of its own, read from the default branch (FR-025). |
| `allow_override` | `NONE` | A user schema cannot redefine them. |

| Name | Kind | Label | Meaning |
|---|---|---|---|
| `delivery_status` | `Dropdown` | Push to remote | The required action. See "Status" below. A null value reads as `none`. |
| `delivery_failure_cause` | `Dropdown` | Push failure cause | Why the last attempt failed. Null when nothing failed. |
| `delivery_error` | `TextArea` | Push error | The remote's message of the last failed attempt, verbatim. |
| `delivery_queue` | `JSON` | Pending pushes | The queue. See `DeliveryQueue`. |
| `delivery_held_regeneration` | `JSON` | Held regeneration | The held set. See `HeldRegeneration`. |
| `delivery_last_abandonment` | `JSON` | Last abandoned push | See `AbandonmentRecord`. |
| `delivery_last_delivered_commit` | `Text` | Last pushed commit | The commit of the last delivery that pushed. |
| `delivery_reverted` | `JSON` | Reverted push | See `RevertedDelivery` (FR-021). |

Order weights place them after `sync_status`, in the order above. Each description ends with "Live
on the default branch only; another branch holds a copy from its fork point."

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
a function of the cause, so the frontend derives it, and no ninth attribute stores it.

| Value | Label | Retried automatically | Required action |
|---|---|---|---|
| `remote-unreachable` | Remote unreachable | yes | Wait, or retry once the remote is reachable. |
| `remote-advanced` | Remote moved during the push | yes | Wait, or retry. |
| `record-failed` | Pushed, not recorded | yes | Wait, or retry. The remote has the content. |
| `certificate` | Certificate verification failed | no | Fix the certificate configuration, then retry. |
| `credentials` | Credentials rejected | no | Fix the credential, then retry. |
| `permission` | Push refused by the remote | no | Grant push permission or lift the branch protection, then retry. |
| `import-failed` | Import of the remote content failed | no | Fix the content on the remote, then retry. |
| `replay-conflict` | A pending merge conflicts with the remote | no | Abandon. |
| `source-discarded` | A source commit is no longer on the remote | no | Abandon. |
| `destination-rewritten` | The remote branch history was rewritten | no | Abandon. |
| `unclassified` | Unclassified failure | no | Read the message, then retry or abandon. |

The last three named causes, together with `replay-conflict`, are the "unreplayable" causes. FR-020
names `source-discarded`. FR-022 names `destination-rewritten`.

---

## JSON values

Each JSON attribute holds one Pydantic model, serialised with `model_dump(mode="json")` and parsed
with `model_validate`. Each model has a `format` field, `1` today, so a later shape can be read
next to an old one. The models live in `backend/infrahub/git/writeback/models.py`. Principle III
forbids untyped dictionaries for this data.

### `DeliveryQueue`

| Field | Type | Meaning |
|---|---|---|
| `format` | `Literal[1]` | |
| `version` | `int` | Increases by one at every change. An abandonment names it. |
| `entries` | `tuple[PendingMerge, ...]` | In merge order. |

### `PendingMerge`

| Field | Type | Meaning |
|---|---|---|
| `entry_id` | `str` | A UUID. Unique in the queue. |
| `source_branch` | `str` | The Infrahub branch that merged. It can be deleted afterwards. |
| `source_git_branch` | `str` | The remote branch that holds the source commit. |
| `source_commit` | `str` | The commit Infrahub imported on the source branch. |
| `merged_at` | `datetime` | The merge time. |

Validation: `source_commit` is a full 40-character hexadecimal SHA. `source_git_branch` is never the
destination branch.

### `HeldRegeneration`

| Field | Type | Meaning |
|---|---|---|
| `format` | `Literal[1]` | |
| `artifact_definition_ids` | `tuple[str, ...]` | Sorted, unique. |
| `generator_definition_ids` | `tuple[str, ...]` | Sorted, unique. |
| `python_attributes` | `tuple[HeldPythonAttribute, ...]` | `(kind, attribute)` pairs. Sorted, unique. |
| `widen` | `bool` | Release as a full regeneration (R9, R10). |

`HeldRegeneration.merge(other)` is a union. It never removes an identifier. `without(other)` removes
the identifiers of a released snapshot and keeps the rest.

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

## State transitions

```text
                 enqueue                       attempt fails (not retryable)
   none ───────────────────────▶ pending ─────────────────────────────▶ action-required
    ▲                             │  ▲                                     │
    │ queue empty after a         │  │ attempt fails (retryable),          │ retry submitted,
    │ delivery or an abandonment  │  │ retry waits                         │ or a new merge enqueued
    └─────────────────────────────┘  └──────────── attempt starts ◀────────┘
```

| From | Event | To | Writes |
|---|---|---|---|
| any | enqueue | `pending` | append entry, bump version |
| `pending` | attempt starts | `pending` | nothing else |
| `pending` | retryable failure, retries left | `pending` | cause, error |
| `pending` | not retryable, or last retry failed | `action-required` | cause, error |
| `action-required` | retry flow starts | `pending` | nothing else |
| `pending` | barrier holds | unchanged | union into the held set |
| any | delivery clears the snapshot | `none`, or `pending` if entries remain | remove snapshot entries, remove released held ids, last delivered commit, clear cause and error when `none` |
| any | abandonment | `none`, or `pending` if entries remain | remove snapshot entries, abandonment record, remove released held ids, clear cause and error when `none` |
| any | rewrite discards the last delivered commit (FR-021) | unchanged | `delivery_reverted` |

### Invariants

1. The status is `none` if and only if the queue is empty.
2. A non-empty held set implies a non-empty queue. The queue removal and the held-set removal are
   one save, so no crash can leave held work behind an empty queue.
3. The queue version only increases.
4. Entries leave the queue only by a delivery that observed them on the remote, or by an
   abandonment that writes its record in the same save (FR-009, SC-006).
5. Every read and write happens on Infrahub's default branch, under the delivery-state lock.
6. No write emits a node mutation event (FR-026).

---

## New in-process types

These carry no persistence of their own. They live in `backend/infrahub/git/writeback/models.py`
unless stated otherwise.

| Type | Kind | Fields | Meaning |
|---|---|---|---|
| `WritebackIntent` | frozen dataclass | `repository_id`, `status`, `cause`, `error`, `queue`, `held`, `last_delivered_commit` | The whole state of one repository, as the store reads it. |
| `DeliveryFailure` | frozen dataclass | `cause`, `retryable: bool`, `message` | The classifier's output. |
| `DeliveryOutcome` | `StrEnum` | `nothing-pending`, `delivered`, `observed`, `failed`, `unreplayable` | What one attempt did. |
| `DeliveryAttemptResult` | frozen dataclass | `outcome`, `commit: str \| None`, `failure: DeliveryFailure \| None` | The service's return value. |
| `PushRejectionReason` | `StrEnum`, in `git/models.py` | `policy`, `non-fast-forward`, `unknown` | Carried on `RepositoryPushRejectedError`. |
| `OwnedRegeneration` | frozen dataclass, in `core/merge/regeneration_barrier.py` | `repository_id: str \| None`, `held: HeldRegeneration`, `request: object` | One barrier candidate: what to hold, who owns it, and the request to dispatch if admitted. |

### New exceptions

In `backend/infrahub/exceptions.py`:

| Class | Parent | Extra fields | Message |
|---|---|---|---|
| `RepositoryPushRejectedError` | `RepositoryError` | `reason: PushRejectionReason`, `remote_message: str` | Today's per-ref rejection wording, unchanged. |
| `RepositoryTLSError` | `RepositoryConnectionError` | none | Today's TLS wording, unchanged. |

`InfrahubRepositoryBase._raise_enriched_error` maps `RepositoryTLSError` to `ERROR_CONNECTION`, as
the parent type maps today.

---

## Payload changes

Every new field is optional with a default, so a run queued by the previous code still validates.

| Model | Module | Field | Type |
|---|---|---|---|
| `GitRepositoryMerge` | `git/models.py` | `pending_merge` | `PendingMerge \| None = None` |
| `RequestArtifactDefinitionGenerate` | `git/models.py` | `repository_id` | `str \| None = None` |
| `generate_artifact_definition` flow | `git/tasks.py` | `exclude_repository_ids` | `list[str] \| None = None` |
| `run_generator_definition` flow | `generators/tasks.py` | `exclude_repository_ids` | `list[str] \| None = None` |
| `GitRepositoryDeliveryRetry` | `git/models.py`, new | `repository_id`, `repository_name` | `str` |
| `GitRepositoryDeliveryAbandon` | `git/models.py`, new | `repository_id`, `repository_name`, `queue_version` | `str`, `str`, `int` |

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
| `sync_status` | Delivery failures are not folded into it, so INFP-671 can redefine it. |
| `commit` | It is still written only once the remote holds the commit (FR-001). |
| `CoreReadOnlyRepository`, `CoreGenericRepository` | A read-only repository never delivers. |
| `NodeMutationOrigin` | No new member. The store emits no node events at all (R2). |
| `EventType` | No new member. The abandonment record lives on the repository (R8). |
| `GRAPH_VERSION` | Optional attributes are added by the schema migration of `infrahub upgrade`. |
