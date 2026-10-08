# Internal interfaces: Git remote writeback failure handling

**Feature**: `dev/specs/ifc-3220-writeback-failure-handling`
**Date**: 2026-10-02, revised after [critiques/critique-20261002-1500.md](../critiques/critique-20261002-1500.md)

The signatures below are the contract between the components. Bodies are left out. Every component
follows `dev/guidelines/backend/component-design.md`: collaborators are required constructor
parameters, per-run values are entry-point arguments, and each flow builds the graph at its top.

---

## 1. Package layout

```text
backend/infrahub/git/writeback/          # NEW
├── __init__.py
├── constants.py     # retry bounds, enqueue retries, barrier read retries, Git timeouts,
│                    # STALE_AFTER, cache time to live and size bound
├── models.py        # DeliveryQueue, PendingMerge, HeldRegeneration, AbandonmentRecord,
│                    # RevertedDelivery, WritebackIntent, DeliveryFailure, DeliveryAttemptResult, Actor
├── classifier.py    # classify_delivery_failure, scrub_credentials
├── ports.py         # DeliveryStatePort, DeliveryGitPort, RegenerationReleasePort, DeliveryRunQuery
├── store.py         # WritebackIntentStore, the only read and write path
├── git_adapter.py   # RepositoryDeliveryGitAdapter, the only Git code here
├── runs.py          # delivery_run_tags, PrefectDeliveryRunQuery, the only orchestrator query here
├── service.py       # RepositoryWritebackService
├── abandoner.py     # WritebackAbandoner
├── recovery.py      # DeliveryRecoveryCheck
└── factory.py       # build_writeback_service, build_writeback_abandoner, build_recovery_check

backend/infrahub/core/merge/
├── regeneration_barrier.py   # NEW: RegenerationBarrier, OwnedRegeneration, NarrowedHoldCache
└── regeneration_release.py   # NEW: HeldRegenerationReleaser
```

`models.py`, `classifier.py`, `service.py`, `abandoner.py` and `recovery.py` import no Git library
and no database code, so their tests need neither. `recovery.py` reads the orchestrator only through
`DeliveryRunQuery`, so its tests need no orchestrator either.

---

## 2. `DeliveryStatePort` and `WritebackIntentStore`

```python
class DeliveryStatePort(Protocol):
    async def read(self, *, repository_id: str) -> WritebackIntent: ...
    async def pending_repository_ids(self) -> frozenset[str]: ...
    async def references_source_branch(self, *, repository_id: str, git_branch: str) -> bool: ...

    async def enqueue(self, *, repository_id: str, entry: PendingMerge, widen: bool) -> WritebackIntent: ...
    async def start_attempt(self, *, repository_id: str) -> WritebackIntent: ...
    async def record_failure(
        self, *, repository_id: str, failure: DeliveryFailure, final: bool, retry_due_at: datetime | None
    ) -> None: ...
    async def owe_import(self, *, repository_id: str, commit: str) -> None: ...
    async def settle_import(self, *, repository_id: str, commit: str, snapshot: WritebackIntent) -> bool: ...
    async def request_branch_deletion(self, *, repository_id: str, git_branch: str) -> bool: ...
    async def progress(self, *, repository_id: str) -> None: ...
    async def hold(self, *, repository_id: str, held: HeldRegeneration) -> HoldReceipt | None: ...
    async def settle_delivery(
        self, *, repository_id: str, snapshot: WritebackIntent, delivered_commit: str | None
    ) -> ReleaseLease | None: ...
    async def abandon(
        self, *, repository_id: str, queue_version: int, record: AbandonmentRecord, actor: Actor
    ) -> tuple[WritebackIntent, ReleaseLease | None]: ...
    async def lease_owed_release(self, *, repository_id: str) -> ReleaseLease | None: ...
    async def renew_lease(self, *, repository_id: str, lease_id: str) -> None: ...
    async def expire_lease(self, *, repository_id: str, lease_id: str) -> None: ...
    async def clear_released(self, *, repository_id: str, lease_id: str) -> None: ...
    async def touch(self, *, repository_id: str) -> None: ...
    async def record_reverted(self, *, repository_id: str, reverted: RevertedDelivery) -> None: ...


class WritebackIntentStore:  # implements DeliveryStatePort
    def __init__(self, db: InfrahubDatabase, lock_registry: InfrahubLockRegistry, default_branch: Branch) -> None: ...
```

Every method except the first three runs under the delivery-state lock (30-second time to live,
10-second bounded acquire). A timed-out acquire raises `DeliveryStateUnavailableError`.

| Method | Contract |
|---|---|
| `read` | A consistent snapshot of one node on the default branch. |
| `pending_repository_ids` | One query on the scalar `delivery_status`: every `CoreRepository` on the default branch whose status is not `none`. The barrier's fast path. An owed import implies a non-empty queue, so the status covers it. |
| `references_source_branch` | The guard of FR-011. |
| `enqueue` | Appends unless the id is present, in `removed_entry_ids`, or in the last abandonment record. Bumps the version. Sets `pending` and `last_progress_at`. Idempotent. The refusals are the second guard of FR-005b. The first guard is the flag `pending_merge_enqueued` of section 10. With `widen=True`, and only when it appends, the same save holds a `widen` marker of scope `all`, with the reason `UNHELD_FOLLOW_UP` and the next hold sequence, as `hold` does. `merge_git_repository` passes `True`, and the dispatcher passes `False` (`research.md` R3). `widen` has no default, so a caller cannot forget it. |
| `start_attempt` | Returns the snapshot. Stamps `attempt_started_at` and `last_progress_at`, and clears `retry_due_at`. Sets `pending` only when the queue is non-empty. Keeps the cause, so a waiting retry still shows the last failure. |
| `record_failure` | Writes the cause, the scrubbed message, `last_progress_at`, and `retry_due_at`. With a non-empty queue, `final=True` sets `action-required` and clears `retry_due_at`. With an empty queue it never changes the status. |
| `progress` | Moves `last_progress_at` at a step boundary. |
| `owe_import` | Sets `import_owed_commit`. Called before the commit is recorded. |
| `settle_import` | Clears `import_owed_commit` when it still names `commit` **and** the queue did not grow past the snapshot. Returns whether it cleared it. |
| `request_branch_deletion` | Sets `delete_source_git_branch` on every entry that names the branch. Returns whether any did. |
| `hold` | Returns `None` and writes nothing when the queue is empty. Otherwise adds or refreshes the items with the next sequence, and returns a `HoldReceipt`: the new sequence and, for every refreshed item, its previous sequence. |
| `settle_delivery` | Called under the repository lock. Removes the snapshot's entries into `removed_entry_ids` and bumps the version, writes `delivered_commit` when it is not `None`, sets the status from what remains, and adds a lease that names each held item that no live lease covers and whose `hold_seq` is not above the snapshot's highest, with that `hold_seq`. One save. Returns the lease, or `None` when no item was uncovered. |
| `abandon` | Called under the repository lock. Refuses with `DeliveryQueueChangedError` when `queue_version` is not the current version, and with `NothingPendingError` when the queue is empty. Otherwise removes every entry into `removed_entry_ids`, bumps the version, clears the owed import, writes the record, sets `none`, and adds a lease that names every held item that no live lease covers, with no sequence bound, in one save that passes `actor.account_id` as `user_id`. |
| `lease_owed_release` | For a held-only run, which needs an empty queue: adds a lease that names every held item that no live lease covers, with no sequence bound, or returns `None` and writes nothing when a live lease covers them all. |
| `renew_lease` | Moves the lease's `expires_at`. |
| `expire_lease` | Sets the lease's `expires_at` to now, and keeps the items of its window held. The lease then protects nothing, the same as the lease of a dead worker (`research.md` R10, rules 3 and 4). The next lease takes those items, and they move to it. The run that took the lease calls it when its release fails. Does nothing when the lease is gone. |
| `clear_released` | Removes each item that the lease names and that still has the named `hold_seq`, then the lease itself. An item held again after the lease was taken has a higher `hold_seq`, so it stays. Does nothing when the lease is gone, because a newer lease then owns its items. |
| `touch` | Moves `last_progress_at`. The recovery check calls it after it submits. |
| `record_reverted` | Overwrites `delivery_reverted`. |

Every method that adds or clears a lease also cleans up the expired leases in the same save
(`research.md` R10, rule 5):

- When the new lease takes an item that an expired lease names, the item moves to the new lease.
- An expired lease drops each item that the held set no longer holds at the named `hold_seq`.
- An expired lease that names no item any more is removed.

The store is the only code that writes the nine attributes. A test asserts that no other module
names them in a write.

---

## 3. The classifier

```python
def classify_delivery_failure(*, error: BaseException, stage: DeliveryStage) -> DeliveryFailure: ...
def scrub_credentials(*, text: str) -> str: ...
```

Pure. The table of `research.md` R5 is the full contract of `classify_delivery_failure`. A
`RepositoryPushRejectedError` gives its `remote_message` and ref summary as the message. Any other
error gives its typed message, never raw stderr. Every message passes through `scrub_credentials`,
which removes `user:password@` and `user@` from every URL it finds.

---

## 4. Ports

```python
class DeliveryGitPort(Protocol):
    async def fetch(self) -> None: ...
    def remote_head(self, *, git_branch: str) -> str | None: ...
    def is_ancestor(self, *, ancestor: str, descendant: str) -> bool: ...
    def replay(self, *, base: str, commits: Sequence[str]) -> ReplayResult: ...
    async def push(self) -> None: ...
    def reset(self, *, commit: str) -> None: ...
    async def record(self, *, commit: str) -> None: ...
    async def import_at(self, *, commit: str) -> None: ...
    async def broadcast(self, *, commit: str) -> None: ...
    async def delete_remote_branch(self, *, git_branch: str) -> None: ...
    async def notify_branch_deleted(self, *, git_branch: str) -> None: ...


class RegenerationReleasePort(Protocol):
    async def release(
        self, *, repository_id: str, held: HeldRegeneration, renew: Callable[[], Awaitable[None]]
    ) -> None: ...


class DeliveryRunQuery(Protocol):
    async def has_queued_run(self, *, repository_id: str) -> bool: ...
```

`held` holds the window of one lease: the items that it names, each with the named `hold_seq`,
under which the release reads the narrowed cache. `renew` moves that lease's expiry.

`ReplayResult` is a frozen dataclass: `head: str`, or `conflicting_commit: str` when a merge
conflicted. `replay` resets to `base` first, and on a conflict aborts the merge and resets to
`base` again.

`fetch` raises `RepositoryError` on a clone with no `origin`. `InfrahubRepositoryBase.fetch` returns
`False` there, and the adapter never treats that as a fetch. The message names the repository and
says that the clone on this worker has no `origin`, with no path. The service classifies it as
`unclassified` (`research.md` R5).

`is_ancestor` returns `True` for equal commits. It returns `False` when the answer is no, or when
either object is missing locally. It raises `RepositoryError` for every other failure, which the
service classifies as `unclassified`. The same contract binds IFC-3210's gateway.

Every port method that runs Git bounds each of its Git commands with GitPython's
`kill_after_timeout` (`research.md` R6):

- `fetch` by `FETCH_TIMEOUT_SECONDS`, and `push` and `delete_remote_branch` by
  `PUSH_TIMEOUT_SECONDS`. A timeout of `fetch` or `push` raises `RepositoryConnectionError`, because
  `_raise_enriched_error_static` maps GitPython's "process killed because it timed out" text to it
  (section 10).
- `remote_head`, `is_ancestor`, `replay`, `reset` and `record` by `LOCAL_GIT_TIMEOUT_SECONDS`, for
  each local command. `remote_head` reads with `git rev-parse`, not through GitPython's object
  database. A timeout raises `RepositoryError`, with a message that names the command and the bound
  but not the arguments, which can name worker paths. After a killed local command, the adapter
  removes a left-over `index.lock` of the worktree before it raises. `reset` never raises: a killed
  reset is logged like any failed reset.

`import_at` has no bound (`research.md` R6). `delete_remote_branch` treats a branch that is already
gone as deleted. The service logs a failed deletion at warning level and never fails the attempt
for it. `notify_branch_deleted` only sends `RefreshGitRepositoryBranchDeleted`.

`RepositoryDeliveryGitAdapter` implements `DeliveryGitPort` over one `InfrahubRepository` and its
destination worktree. `HeldRegenerationReleaser` implements `RegenerationReleasePort`. Both are
shapes the service defines, so neither the Git adapter nor the merge layer is imported by
`service.py`.

`has_queued_run` returns whether the orchestrator holds a delivery run of the repository that waits
to start: a run that carries both delivery tags and has a state of type `SCHEDULED` or `PENDING`
(`research.md` R20, condition 5). It raises when the orchestrator does not answer.
`PrefectDeliveryRunQuery`, in `runs.py`, implements `DeliveryRunQuery` with one `read_flow_runs`
call with `limit=1`, over a client that implements
`task_manager/flow_run/prefect_client.py::FlowRunQuerying`. The filter is
`FlowRunFilterTags(all_=delivery_run_tags(repository_id))` and
`FlowRunFilterStateType(any_=[SCHEDULED, PENDING])`. It is the only orchestrator query of the
package, so the recovery check's unit tests use a fake.

```python
def delivery_run_tags(repository_id: str) -> list[str]: ...
```

`delivery_run_tags`, in `runs.py`, returns the repository's node tag,
`WorkflowTag.RELATED_NODE.render(identifier=repository_id)`, and the delivery marker,
`WorkflowTag.REPOSITORY_DELIVERY.render()`. These render as `infrahub.app/node/<repository id>` and
`infrahub.app/repository-delivery`. Every submitter of a delivery run and the adapter use it, so
the tags that a submission writes and the tags that the query reads cannot disagree.

---

## 5. `RepositoryWritebackService`

```python
class RepositoryWritebackService:
    def __init__(
        self,
        repository: RepositoryRef,
        state: DeliveryStatePort,
        git: DeliveryGitPort,
        releaser: RegenerationReleasePort,
        lock_registry: InfrahubLockRegistry,
        clock: Clock,
    ) -> None: ...

    async def deliver(
        self,
        *,
        final_attempt: bool,
        manual: bool,
        entry: PendingMerge | None,
        retry_delay: timedelta | None = None,
    ) -> DeliveryAttemptResult: ...
```

`RepositoryRef` is a frozen dataclass: `id`, `name`, `destination_git_branch`. The factory builds
one service per repository, with the adapter bound to the same repository, so the two cannot
disagree.

`deliver` runs the algorithm of `research.md` R4:

- Step 0, when `entry` is not `None`: `state.enqueue(..., widen=True)`. It comes first, before the
  repository lock and before the `deferred` check below. A failure has the stage `enqueue` and
  records nothing on the repository. On a non-final attempt, it is re-raised as
  `RetryableDeliveryError`. On the final attempt, `deliver` logs at error level the repository,
  `entry.source_branch` and `entry.source_commit`, and returns `failed` (`research.md` R3, R5). A
  refused id is not a failure.
- Steps 1 to 15 under the repository lock, the settle included. Steps 16 and 17, the release and
  the clear, after it is released, under the lease that the settle returned.
- If the release raises, `deliver` calls `state.expire_lease(...)` on its lease first. Then it
  handles the failure as the bullets below say, with the stage `release`. The clear does not run,
  so the held items stay. The task retry takes a new lease over them and releases every one. After
  the final attempt, the run that the recovery check starts does it (`research.md` R10, rule 4).
- A held-only run calls `lease_owed_release` and does nothing when it returns `None`. A live lease
  then covers every held item. The run of a failed release sets its lease's expiry to now, so that
  live lease belongs to a release that still runs. The one exception is an `expire_lease` call
  that failed (`research.md` R10, rule 4).
- When `manual` is `False` and a retry of another chain is due in the future, it returns
  `deferred` at once (one chain per repository). It reads the state for this check after step 0
  and before the repository lock. A chain's own retry starts at or after its recorded due time, so
  it does not defer.
- It never raises for a classified failure that is final: it records it and returns `failed` or
  `unreplayable`. A retryable failure on a non-final attempt is recorded with `retry_due_at`, then
  re-raised as `RetryableDeliveryError`, so the task's `retry_condition_fn` retries it.
- A `DeliveryStateUnavailableError` is re-raised as retryable.

Two flows run the task. The recovery check does not call it itself: it submits the retry flow.

| Flow | Caller |
|---|---|
| `git-repository-merge` (`merge_git_repository`) | first attempt. When `model.pending_merge_enqueued` is `False`, the flow passes `model.pending_merge`, or the entry it builds when that is `None`, as `entry`. Otherwise it passes `None`. Step 0 then enqueues it with `widen=True`, so the same save holds a `widen` marker of scope `all`, and the release after this delivery runs again the regeneration that the follow-ups dispatched without a hold (`research.md` R3). The task retries a failed enqueue with its own retries. |
| `git-repository-delivery-retry` (`retry_repository_delivery`) | manual retry (`manual=True`), and the recovery check (`manual=False`). Always `entry=None`. |

Every submission of a delivery run passes `tags=delivery_run_tags(repository_id)` to
`submit_workflow`: the dispatcher for the `merge_git_repository` run of an `active` repository,
and the retry mutation and the recovery check for the retry flow. The recovery check finds a run that waits in the
queue by these tags (`research.md` R20, R21).

```python
@task(
    name="git-repository-deliver",
    cache_policy=NONE,
    retries=DELIVERY_RETRIES,
    retry_delay_seconds=DELIVERY_RETRY_DELAYS_SECONDS,
    retry_condition_fn=is_retryable_delivery_failure,
)
async def deliver_pending_merges(
    service: RepositoryWritebackService, manual: bool, entry: PendingMerge | None
) -> DeliveryOutcome: ...
```

The task computes the wait before its next retry from `task_run.run_count` and its own `retries`
and `retry_delay_seconds`, which are `DELIVERY_RETRIES` and `DELIVERY_RETRY_DELAYS_SECONDS` unless a
test changes them with `with_options`. It passes that wait to `deliver` as `retry_delay`, which sets
`retry_due_at` at the time of the failure, and `final_attempt` is `True` when no retry follows. It
passes `entry` to `deliver` on every attempt. The enqueue is idempotent, so an attempt after one that
enqueued finds the id and writes nothing. The flow sets
its own final state from the outcome (`research.md` R21). `DELIVERY_RETRIES = 3` and
`DELIVERY_RETRY_DELAYS_SECONDS = [30, 120, 300]`. Tests pass shorter delays through
`deliver_pending_merges.with_options(retry_delay_seconds=...)`.

`merge_git_repository` has no path around the task: no repository merges and records locally. A
clone with no `origin` fails the attempt at the fetch. The attempt records nothing and keeps every
entry in the queue (`research.md` R3, R4).

---

## 6. `WritebackAbandoner`

```python
class WritebackAbandoner:
    def __init__(
        self,
        repository: RepositoryRef,
        state: DeliveryStatePort,
        git: DeliveryGitPort,
        releaser: RegenerationReleasePort,
        lock_registry: InfrahubLockRegistry,
        clock: Clock,
    ) -> None: ...

    async def abandon(self, *, queue_version: int, actor: Actor) -> AbandonmentRecord: ...
```

`Actor` comes from the workflow's `InfrahubContext`.

Runs `research.md` R8: under the repository lock, `state.abandon(...)`, then
`git.notify_branch_deleted(...)` for every abandoned entry that carried the deletion flag; then,
with the lock released, `releaser.release(...)` on the lease window, then
`state.clear_released(...)`. If the release raises, it calls `state.expire_lease(...)` on its lease
and re-raises, so the recovery check releases the held items (`research.md` R10, rule 4). It uses
the Git port only for that notification: it changes no Git state, deletes no remote branch and
imports nothing. `DeliveryQueueChangedError` and `NothingPendingError` subclass `ValidationError`,
so the task run fails with the message of the GraphQL contract.

---

## 7. `DeliveryRecoveryCheck` (FR-027)

```python
class DeliveryRecoveryCheck:
    def __init__(
        self,
        state: DeliveryStatePort,
        workflow: InfrahubWorkflow,
        runs: DeliveryRunQuery,
        lock_registry: InfrahubLockRegistry,
        clock: Clock,
        context: InfrahubContext,
    ) -> None: ...

    async def run(self, *, repository: RepositoryRef) -> bool: ...
```

Called from the loop of `git/tasks.py::sync_remote_repositories`, for every repository, before the
bootstrap and whatever the outcome of the sync, under its own guard. It submits
`GIT_REPOSITORY_DELIVERY_RETRY` with a system context and `tags=delivery_run_tags(repository.id)`,
then calls `state.touch(...)`, when:

- the delivery is stale (five conditions, `research.md` R20); or
- the queue is empty, held items that no live lease covers wait, `last_progress_at` is older than
  `STALE_AFTER`, and no delivery run of the repository waits to start.

The second trigger needs an empty queue. A queue with merges is the stale check's case: while it is
`pending`, the first trigger covers it. While it is `action-required`, a submission every
`STALE_AFTER` would retry a policy failure, which FR-004 forbids.

The lock condition needs the lock registry, and the orchestrator condition needs `runs`. The check
takes both in its constructor. The retry flow requires a context, so the check also takes the
system context that it submits with: the default branch and an anonymous account. It reads the
state and the lock first, and evaluates the first trigger with
`WritebackIntent.is_stale(now, lock_free, run_queued=False)` and the second with
`WritebackIntent.release_waits(now)`. It calls `runs.has_queued_run(...)` last, only when one
trigger holds, and submits only when no run waits. A repository with no work to recover, or with
recent progress, costs no orchestrator query. When `has_queued_run` raises an `httpx.HTTPError` or
an `OSError`, the check submits nothing, does not call `state.touch(...)`, logs the failure at
warning level, and returns `False`. Another error gives the same result, but the guard of `run`
logs it at error level, with its traceback. It returns whether it submitted. It never raises: a
failure is logged and the next cycle checks again.

`build_recovery_check` builds `PrefectDeliveryRunQuery` over
`task_manager/flow_run/prefect_client.py::PrefectClientAdapter`, and the system context with
`InfrahubContext.init(branch=<default branch>, account=AnonymousSession())`.

---

## 8. `RegenerationBarrier`

```python
@dataclass(frozen=True)
class OwnedRegeneration(Generic[RequestT]):
    repository_id: str | None
    held: HeldRegeneration
    request: RequestT


class NarrowedHoldCache:
    def __init__(self, cache: InfrahubCache, ttl_seconds: int, max_bytes: int) -> None: ...

    async def put(self, *, repository_id: str, hold_seq: int, identifier: str, request: BaseModel) -> None: ...
    async def merge_put(
        self,
        *,
        repository_id: str,
        previous_seq: int,
        hold_seq: int,
        identifier: str,
        request: BaseModel,
        union: Callable[[BaseModel, BaseModel], BaseModel],
    ) -> None: ...
    async def get(
        self, *, repository_id: str, hold_seq: int, identifier: str, model: type[ModelT]
    ) -> ModelT | None: ...


class RegenerationBarrier:
    def __init__(
        self,
        state: DeliveryStatePort,
        narrowed: NarrowedHoldCache,
        default_branch_name: str,
        sleep: Callable[[float], Awaitable[None]],
    ) -> None: ...

    async def admit(
        self,
        *,
        branch: str,
        candidates: Sequence[OwnedRegeneration[RequestT]],
        releasing: str | None,
    ) -> list[OwnedRegeneration[RequestT]]: ...
```

Contract of `admit`:

1. `branch` is not the default branch → return every candidate. No read.
2. `pending_repository_ids()` is empty → return every candidate. One read.
3. A candidate whose owner is `releasing`, or is not pending → admitted.
4. A candidate whose owner is pending → `state.hold(...)`. Admitted only if `hold` returns `None`,
   which means the queue settled in between. Otherwise its narrowed request goes to the cache under
   the new sequence: with `put` for a new item, with `merge_put` for a refreshed item. `merge_put`
   writes the union of the previous entry and the new request, or writes nothing when the previous
   entry is missing, expired or above the size bound.
5. A candidate whose owner is `None` → held under every pending repository except `releasing`.
   Admitted as well when every `hold` returned `None`.
6. Candidates of one repository are held in one `hold` call.
7. If a state call raises, or the state lock cannot be acquired → wait for the next delay of
   `BARRIER_STATE_READ_DELAYS_SECONDS`, then apply rules 2 to 6 again from the start, up to
   `BARRIER_STATE_READ_RETRIES` times. A repeated hold of an item only refreshes it (rule 4). If the
   last retry fails too → admit every candidate and log at error level, with the branch and the
   repositories of the candidates (`research.md` R9). A cache write failure is logged, is not
   retried, and does not change the decision.

`sleep` waits between the retries of rule 7. Every builder passes `asyncio.sleep`. A unit test
passes one that records the delays and returns at once.

`releasing` has no default. Every non-release site passes `None` explicitly, so a release site
cannot forget it.

### Call sites

| Site | Candidate request type | Owner |
|---|---|---|
| `PostMergeRegenerationDispatcher.dispatch`, on the built plan | `RequestGeneratorDefinitionRun`, `RequestArtifactDefinitionGenerate` | `generator_definition.repository_id`, `repository_id` |
| `PostMergeRegenerationDispatcher._submit`, after the cascade | `RequestArtifactDefinitionGenerate` | `repository_id` |
| `PostMergeRegenerationDispatcher._full_regeneration`, `_submit_full_terminal_regeneration`, and the flag-off path of `post_process_branch_merge` | a `widen` marker per pending repository, with the reason of the fallback (data model, "New fallback reasons"), then the blanket triggers with `exclude_repository_ids`. In a release, `_submit_full_terminal_regeneration` holds nothing and submits the terminal trigger with `include_repository_ids=[releasing]`, because a release covers only the definitions of its repository (SC-004) | the repository |
| `recompute_coalescing.py::_resolve_python_targets` | `AffectedTarget` of the Python family | `PythonTargetSource.owner_of(kind, attribute)` |
| `computed_attribute/tasks.py::computed_attribute_setup_python`, on the default branch | the selected `(kind, attribute)` pairs | the same owner map |

`PostMergeRegenerationDispatcher`, `MergeRecomputeCoordinator`, `RecomputeChainSubmitter` and the
schema-scoped recompute each gain a required `barrier: RegenerationBarrier` constructor parameter.
The rebase builder and every test pass one too: on a non-default branch it admits everything without
a read.

---

## 9. `HeldRegenerationReleaser`

```python
class HeldRegenerationReleaser:
    def __init__(
        self,
        dispatcher: PostMergeRegenerationDispatcher,
        python_submitter: CoalescedRecomputeSubmitter,
        definitions: HeldDefinitionResolver,
        narrowed: NarrowedHoldCache,
        default_branch_name: str,
        context: InfrahubContext,
    ) -> None: ...

    async def release(
        self, *, repository_id: str, held: HeldRegeneration, renew: Callable[[], Awaitable[None]]
    ) -> None: ...
```

`HeldDefinitionResolver` loads the held definitions by id on the default branch, with the same
queries the selectors use (`GATHER_ARTIFACT_DEFINITIONS`, `client.filters(kind=CoreGeneratorDefinition)`).

Contract:

1. If `held.widen` has scope `all`, run the full `widen` release of the repository, log the
   marker's own `reason`, and stop. Else, if any held identifier does not resolve, run the same
   release, log `HELD_SET_UNRESOLVED`, and stop. `HELD_SET_UNRESOLVED` is only for an identifier
   that does not resolve. A held generator definition that exists but no longer runs after a merge
   resolves: the release logs it and runs nothing for it. The full release submits both blanket
   triggers with `include_repository_ids=[repository_id]`, plus a whole-kind recompute of every
   Python computed attribute whose transform the repository owns. It covers every held item, so the
   other steps have nothing to dispatch.
2. If `held.widen` has scope `terminals`, log the marker's `reason`, submit the artifact trigger
   with `include_repository_ids=[repository_id]`, then continue at step 3. The trigger covers the
   artifact items of the window, so steps 3 and 4 skip them. It does not cover the generator items or the
   Python items, so steps 3 to 5 still dispatch them. If the release stopped here, the clear would
   remove those items without a dispatch (FR-016).
3. For each held item, take the narrowed request from the cache under its `hold_seq`, or build the
   request with no member or target narrowing when the cache misses.
4. Dispatch the generator and artifact requests through `PostMergeRegenerationDispatcher`, with
   `releasing=repository_id`, so the cascade runs as on a merge and every dispatch passes through the
   barrier.
5. Submit each Python attribute: the cached narrowed submission, or a whole-kind recompute with
   `coalesced=True` and `widened=True`.
6. Renew the lease after each awaited step, through a callback the caller passes.
7. Raise on a dispatch failure. The releaser only raises. Its caller, the service or the
   abandoner, sets the lease's expiry to now through `expire_lease`, then handles the failure.
   The caller has not cleared anything yet, so the items stay held, and the next run releases them
   under a new lease (`research.md` R10, rule 4).

---

## 10. Changes to existing components

| Component | Change |
|---|---|
| `git/repository.py::InfrahubRepository.push` | Passes a `RemoteProgress` and `kill_after_timeout`. A per-ref rejection raises `RepositoryPushRejectedError`, with the reason from the `PushInfo` flags and the joined `remote:` lines. Message wording unchanged. |
| `git/base.py::InfrahubRepositoryBase.fetch` | Accepts a timeout and passes it as `kill_after_timeout`. |
| `git/base.py::InfrahubRepositoryBase.create_commit_worktree`, `git/base.py::InfrahubRepositoryBase.delete_remote_branch` | Accept a timeout and pass it as `kill_after_timeout` to each Git command they run. Default unchanged. |
| `git/repository.py::InfrahubRepository._reset_to_pre_merge_commit` | Accepts a timeout and passes it as `kill_after_timeout`. Still never raises. |
| `git/base.py::InfrahubRepositoryBase._raise_enriched_error_static` | Raises `RepositoryTLSError` for the TLS markers, `RepositoryNotFoundError` for "Repository not found", and `RepositoryConnectionError` for GitPython's "process killed because it timed out". |
| `git/base.py::InfrahubRepositoryBase._raise_enriched_error` | Resolves the status with `isinstance`, most specific first. |
| `message_bus/operations/git/repository.py::connectivity` | Same `isinstance` resolution. |
| `git/repository.py::InfrahubRepository.collect_pending_imports` | In the active loop, skips the default branch, and every new or updated remote branch that a pending entry names, while the state is not `none`. Takes the state port as a parameter from the sync flow. `_collect_staging_imports` is unchanged. |
| `git/tasks.py::bootstrap_local_repository` | Skips the seed import of the default branch while the state is not `none`. |
| `git/tasks.py::sync_remote_repositories` | Runs `DeliveryRecoveryCheck.run` for every repository in its loop, before the bootstrap and whatever the sync outcome, under its own guard. |
| `git/tasks.py::merge_git_repository` | The default path builds the service and calls `deliver_pending_merges`. The read-only path and the staging path are unchanged. No path merges and records locally: a clone with no `origin` fails the attempt at the fetch and keeps the queue (`research.md` R3). Only when `pending_merge_enqueued` is `False`, the default path passes an entry to the task: `pending_merge`, or, when that is `None`, the entry it builds from the source branch's graph commit, after the content test of `research.md` R3 (no entry for a merge that carries no content). The task enqueues it as step 0 of each attempt, with `widen=True` (section 5): the save that appends the entry also holds a `widen` marker of scope `all`, with the reason `UNHELD_FOLLOW_UP`, because the follow-ups of that merge ran without a hold. When `enqueue` refuses the id, no marker is held. When every attempt fails to enqueue, the run ends `Failed` with an error-level log line. When the flag is `True`, it passes `entry=None` and only delivers (`research.md` R3). |
| `git/tasks.py::git_branch_delete` | When `references_source_branch` is true: calls `request_branch_deletion`, skips the remote deletion, and does not send `RefreshGitRepositoryBranchDeleted`. |
| `core/merge/repository_merge_dispatcher.py::RepositoryMergeDispatcher.merge_core_repositories` | For an `active` repository, on a branch that syncs with Git, whose source commit carries content (`research.md` R3): builds the `PendingMerge`, enqueues it under its own guard with `widen=False`, passes it in the model, and passes the merge's `context`. Retries a failed enqueue `ENQUEUE_RETRIES` times, after the delays of `ENQUEUE_RETRY_DELAYS_SECONDS`. If the last retry fails too, it logs at error level and still submits the merge. Takes two new required constructor parameters: the state port, `state: DeliveryStatePort`, through which it enqueues, and a `sleep` callable, as the barrier does, so a unit test records the delays and returns at once. `core/merge/builder.py` and every test that builds the dispatcher pass both. Sets `pending_merge_enqueued` to `True` only when one of its tries returned. Submits no merge workflow for an `active` repository whose source commit carries no content. Passes `tags=delivery_run_tags(repository_id)` when it submits the merge of an `active` repository, so a run that waits in the queue counts as a waiting delivery run (`research.md` R20). |
| `workflows/constants.py::WorkflowTag` | Gains `REPOSITORY_DELIVERY = "repository-delivery"`, which renders as `infrahub.app/repository-delivery`. It marks a delivery run (`research.md` R20). |
| `core/merge/regeneration_dispatcher.py::PostMergeRegenerationDispatcher` | Consults the barrier at the sites of section 8. `dispatch` and `_dispatch_plan` take `releasing`. |
| `core/merge/python_target_sources.py::GatheredPythonReadSets` | Keeps the repository id per attribute and exposes `owner_of`. |
| `core/merge/selective_regen/definition_selector/artifact_selector.py::ArtifactSelector._build_request` | Fills `repository_id`. |
| `git/tasks.py::generate_artifact_definition`, `generators/tasks.py::run_generator_definition` | Accept `exclude_repository_ids` and `include_repository_ids`. |
| `computed_attribute/tasks.py::computed_attribute_setup_python` | On the default branch, passes the selected pairs through the barrier. |
| `graphql/mutations/repository.py::ProcessRepository` | Refuses on every branch while the state is not `none`. |
| IFC-3210's reconciliation | Calls `state.record_reverted` when the condition of `research.md` R13 holds. Gated on IFC-3210. |
