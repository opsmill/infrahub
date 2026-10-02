# Internal interfaces: Git remote writeback failure handling

**Feature**: `dev/specs/ifc-3220-writeback-failure-handling`
**Date**: 2026-10-02

The signatures below are the contract between the components. Bodies are left out. Every component
follows `dev/guidelines/backend/component-design.md`: collaborators are required constructor
parameters, per-run values are entry-point arguments, and each flow builds the graph at its top.

---

## 1. Package layout

```text
backend/infrahub/git/writeback/          # NEW
├── __init__.py
├── models.py        # DeliveryQueue, PendingMerge, HeldRegeneration, AbandonmentRecord,
│                    # RevertedDelivery, WritebackIntent, DeliveryFailure, DeliveryAttemptResult
├── classifier.py    # classify_delivery_failure
├── store.py         # WritebackIntentStore, the only read and write path
├── ports.py         # DeliveryGitPort, RegenerationReleasePort
├── git_adapter.py   # RepositoryDeliveryGitAdapter, the only Git code here
├── service.py       # RepositoryWritebackService
├── abandoner.py     # WritebackAbandoner
└── factory.py       # build_writeback_service, build_writeback_abandoner

backend/infrahub/core/merge/
├── regeneration_barrier.py   # NEW: RegenerationBarrier, OwnedRegeneration
└── regeneration_release.py   # NEW: HeldRegenerationReleaser
```

`models.py`, `classifier.py`, `service.py` and `abandoner.py` import no Git library and no database
code, so their tests need neither.

---

## 2. `WritebackIntentStore`

```python
class WritebackIntentStore:
    def __init__(self, db: InfrahubDatabase, lock_registry: InfrahubLockRegistry, default_branch: Branch) -> None: ...

    async def read(self, *, repository_id: str) -> WritebackIntent: ...
    async def pending_repository_ids(self) -> frozenset[str]: ...
    async def references_source_branch(self, *, repository_id: str, git_branch: str) -> bool: ...

    async def enqueue(self, *, repository_id: str, entry: PendingMerge) -> WritebackIntent: ...
    async def start_attempt(self, *, repository_id: str) -> WritebackIntent: ...
    async def record_failure(self, *, repository_id: str, failure: DeliveryFailure, final: bool) -> None: ...
    async def hold(self, *, repository_id: str, held: HeldRegeneration) -> bool: ...
    async def complete_delivery(
        self, *, repository_id: str, snapshot: WritebackIntent, delivered_commit: str | None
    ) -> WritebackIntent: ...
    async def complete_abandonment(
        self, *, repository_id: str, snapshot: WritebackIntent, record: AbandonmentRecord
    ) -> WritebackIntent: ...
    async def record_reverted(self, *, repository_id: str, reverted: RevertedDelivery) -> None: ...
```

| Method | Lock | Contract |
|---|---|---|
| `read` | none | A consistent snapshot of one node on the default branch. |
| `pending_repository_ids` | none | One query: every `CoreRepository` on the default branch whose status is not `none`. The barrier's fast path. |
| `references_source_branch` | none | The guard of FR-011. |
| `enqueue` | state | Appends unless an entry with the same `entry_id` exists. Bumps the version. Sets `pending`. Idempotent. |
| `start_attempt` | state | Returns the snapshot. Sets `pending`. Does not clear the cause, so a waiting retry still shows the last failure. |
| `record_failure` | state | Writes the cause and the message. `final=True` sets `action-required`. |
| `hold` | state | Returns `False` and writes nothing when the queue is empty. Otherwise unions `held` into the held set and returns `True`. |
| `complete_delivery` | state | Removes the snapshot's entries and the snapshot's held identifiers, in one save. Writes `delivered_commit` when it is not `None`. Sets the status from what remains. |
| `complete_abandonment` | state | Refuses with `DeliveryQueueChangedError` when the version moved since the snapshot. Otherwise as `complete_delivery`, plus the record, in one save. |
| `record_reverted` | state | Overwrites `delivery_reverted`. |

The store is the only code that writes the eight attributes. A test asserts that no other module
names them in a write.

---

## 3. `classify_delivery_failure`

```python
def classify_delivery_failure(*, error: BaseException, pushed: bool) -> DeliveryFailure: ...
```

Pure. The table of `research.md` R5 is its full contract. `pushed=True` always gives
`record-failed`, retryable. A `RepositoryPushRejectedError` gives its `remote_message` as the
message, and any other `RepositoryError` gives `str(error)`.

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
    async def import_at(self, *, commit: str) -> None: ...
    async def record(self, *, commit: str) -> None: ...
    async def broadcast(self, *, commit: str) -> None: ...


class RegenerationReleasePort(Protocol):
    async def release(self, *, repository_id: str, held: HeldRegeneration) -> None: ...
```

`ReplayResult` is a frozen dataclass: `head: str`, or `conflicting_commit: str` when a merge
conflicted. `replay` resets to `base` first, and on a conflict aborts the merge and resets to
`base` again.

`is_ancestor` returns `True` for equal commits, and `False` when either object is missing locally.

`RepositoryDeliveryGitAdapter` implements `DeliveryGitPort` over one `InfrahubRepository` and the
destination worktree. `HeldRegenerationReleaser` implements `RegenerationReleasePort`. Both are
shapes the service defines, so neither the Git adapter nor the merge layer is imported by
`service.py`.

---

## 5. `RepositoryWritebackService`

```python
class RepositoryWritebackService:
    def __init__(
        self,
        store: WritebackIntentStore,
        git: DeliveryGitPort,
        releaser: RegenerationReleasePort,
        lock_registry: InfrahubLockRegistry,
    ) -> None: ...

    async def deliver(self, *, repository: RepositoryRef) -> DeliveryAttemptResult: ...
```

`RepositoryRef` is a frozen dataclass: `id`, `name`, `destination_git_branch`.

`deliver` runs the algorithm of `research.md` R4 under the repository lock. It never raises for a
classified failure: it records the failure and returns `failed` or `unreplayable`. It re-raises a
retryable failure as `RetryableDeliveryError` after it recorded it, so the task's
`retry_condition_fn` can retry it.

The same instance shape serves both callers (FR-007):

| Flow | Caller |
|---|---|
| `git-repository-merge` (`merge_git_repository`) | first attempt, after it re-enqueues `model.pending_merge` |
| `git-repository-delivery-retry` (`retry_repository_delivery`) | manual retry |

Both call one task:

```python
@task(
    name="git-repository-deliver",
    cache_policy=NONE,
    retries=DELIVERY_RETRIES,
    retry_delay_seconds=DELIVERY_RETRY_DELAYS_SECONDS,
    retry_condition_fn=is_retryable_delivery_failure,
)
async def deliver_pending_merges(service: RepositoryWritebackService, repository: RepositoryRef) -> None: ...
```

`DELIVERY_RETRIES = 3` and `DELIVERY_RETRY_DELAYS_SECONDS = [30, 120, 300]` live in
`git/writeback/constants.py`. Before the last attempt, `record_failure` is called with
`final=False`. On the last attempt the task records `final=True`. The task reads the attempt number
from the Prefect run context, the way `webhook/log_formatter.py` reads it.

---

## 6. `WritebackAbandoner`

```python
class WritebackAbandoner:
    def __init__(
        self,
        store: WritebackIntentStore,
        git: DeliveryGitPort,
        releaser: RegenerationReleasePort,
        lock_registry: InfrahubLockRegistry,
    ) -> None: ...

    async def abandon(self, *, repository: RepositoryRef, queue_version: int, actor: Actor) -> AbandonmentRecord: ...
```

`Actor` is a frozen dataclass: `account_id`, `account_name`, taken from the workflow's
`InfrahubContext`.

Runs `research.md` R8 under the repository lock. Raises `DeliveryQueueChangedError` when the version
moved, and `NothingPendingError` when the queue is empty. Both subclass `ValidationError`, so the
task run fails with the message of the GraphQL contract.

---

## 7. `RegenerationBarrier`

```python
@dataclass(frozen=True)
class OwnedRegeneration(Generic[RequestT]):
    repository_id: str | None
    held: HeldRegeneration
    request: RequestT


class RegenerationBarrier:
    def __init__(self, store: WritebackIntentStore, default_branch_name: str) -> None: ...

    async def admit(
        self,
        *,
        branch: str,
        candidates: Sequence[OwnedRegeneration[RequestT]],
        releasing: str | None,
    ) -> list[OwnedRegeneration[RequestT]]: ...
```

Contract:

1. `branch` is not the default branch → return every candidate. No read.
2. `pending_repository_ids()` is empty → return every candidate. One read.
3. A candidate whose owner is `releasing`, or is not pending → admitted.
4. A candidate whose owner is pending → `store.hold(...)`. Admitted only if `hold` returns `False`,
   which means the queue cleared in between.
5. A candidate whose owner is `None` → held under every pending repository except `releasing`.
   Admitted as well when every `hold` returned `False`.
6. Candidates of one repository are held in one `hold` call.

`releasing` has no default. Every non-release site passes `None` explicitly, so a release site
cannot forget it.

### Call sites

| Site | Candidate request type | Owner |
|---|---|---|
| `PostMergeRegenerationDispatcher.dispatch`, on the built plan | `RequestGeneratorDefinitionRun`, `RequestArtifactDefinitionGenerate` | `generator_definition.repository_id`, `repository_id` |
| `PostMergeRegenerationDispatcher._submit`, after the cascade | `RequestArtifactDefinitionGenerate` | `repository_id` |
| `PostMergeRegenerationDispatcher._full_regeneration` and the flag-off path of `post_process_branch_merge` | a `widen` marker per pending repository | the repository |
| `recompute_coalescing.py::_resolve_python_targets` | `AffectedTarget` of the Python family | `PythonTargetSource.owner_of(kind, attribute)` |

`PostMergeRegenerationDispatcher`, `MergeRecomputeCoordinator` and `RecomputeChainSubmitter` each
gain a required `barrier: RegenerationBarrier` constructor parameter. The rebase builder and every
test pass one too: on a non-default branch it admits everything without a read.

---

## 8. `HeldRegenerationReleaser`

```python
class HeldRegenerationReleaser:
    def __init__(
        self,
        dispatcher: PostMergeRegenerationDispatcher,
        python_submitter: CoalescedRecomputeSubmitter,
        definitions: HeldDefinitionResolver,
        default_branch_name: str,
        context: InfrahubContext,
    ) -> None: ...

    async def release(self, *, repository_id: str, held: HeldRegeneration) -> None: ...
```

`HeldDefinitionResolver` loads the held definitions by id on the default branch, with the same
queries the selectors use (`GATHER_ARTIFACT_DEFINITIONS`, `client.filters(kind=CoreGeneratorDefinition)`).

Contract:

1. Resolve every held identifier. If any does not resolve, or `held.widen` is set, run a full
   regeneration with reason `HELD_SET_UNRESOLVED` and stop.
2. Build a `SelectiveRegenerationPlan` from the resolved definitions, with no member or target
   narrowing, and dispatch it through `PostMergeRegenerationDispatcher` with
   `releasing=repository_id`. The cascade runs as on a merge.
3. Submit each held Python attribute as a whole-kind recompute, `coalesced=True`, `widened=True`.
4. Raise on a dispatch failure. The caller has not cleared anything yet, so the next clearing
   releases again (`research.md` R10).

---

## 9. Changes to existing components

| Component | Change |
|---|---|
| `git/repository.py::InfrahubRepository.push` | Passes a `RemoteProgress`. A per-ref rejection raises `RepositoryPushRejectedError` with the reason and the joined `remote:` lines. Message wording unchanged. |
| `git/base.py::InfrahubRepositoryBase._raise_enriched_error_static` | Raises `RepositoryTLSError` for the TLS markers. |
| `git/base.py::InfrahubRepositoryBase._raise_enriched_error` | Maps `RepositoryTLSError` to `ERROR_CONNECTION`. |
| `git/repository.py::InfrahubRepository.collect_pending_imports` | Skips the default branch while `store.read(...)` is not `none` (`research.md` R11). Takes the store as a parameter from the sync flow. |
| `git/tasks.py::merge_git_repository` | The default path builds the service and calls `deliver_pending_merges`. The read-only and staging paths are unchanged. |
| `git/tasks.py::git_branch_delete` | Skips the remote deletion when `references_source_branch` is true. |
| `core/merge/repository_merge_dispatcher.py::RepositoryMergeDispatcher.merge_core_repositories` | Builds the `PendingMerge`, enqueues it (unless the source commit equals the recorded commit), passes it in the model, and passes the merge's `context`. |
| `core/merge/regeneration_dispatcher.py::PostMergeRegenerationDispatcher` | Consults the barrier at the three sites of section 7. |
| `core/merge/python_target_sources.py::GatheredPythonReadSets` | Keeps the repository id per attribute and exposes `owner_of`. |
| `core/merge/selective_regen/definition_selector/artifact_selector.py::ArtifactSelector._build_request` | Fills `repository_id`. |
| `git/tasks.py::generate_artifact_definition`, `generators/tasks.py::run_generator_definition` | Accept `exclude_repository_ids`. |
| `graphql/mutations/repository.py::ProcessRepository` | Refuses on the default branch while a delivery is pending. |
| IFC-3210's reconciliation | Calls `store.record_reverted` when the condition of `research.md` R13 holds. Gated on IFC-3210. |
