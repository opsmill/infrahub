# Contract — `BranchLocker` (internal Python API)

This is the new internal API for the coordination primitive. Lives at `backend/infrahub/core/branch/branch_locker.py`. Consumers import it from there.

## Class

```python
class BranchLocker:
    def __init__(
        self,
        *,
        cache: CacheService,
        lock_registry: InfrahubLockRegistry,
        config: MergeSettings,
    ) -> None: ...
```

Constructed once per process; injected via the existing service container. No global singleton.

## `acquire_write`

```python
@asynccontextmanager
async def acquire_write(
    self,
    branch_name: str,
    *,
    merge_holder_id: str | None = None,
) -> AsyncIterator[None]:
    ...
```

**Pre-conditions**:
- `branch_name` is a valid existing branch name (validation responsibility lies upstream).
- The caller is performing a write operation against `branch_name` and wraps that write in this context manager.

**Behavior**:
- If a `MergeHolder` ContextVar is set in the current task and its `source_branch` or `target_branch` matches `branch_name`: bypass (yield without registering a writer key).
- Else if `merge_holder_id` is provided and matches the current `merge_intent` value for `branch_name`: bypass (yield without registering a writer key).
- Else: acquire the branch gate, read `merge_intent`; if set, release gate and raise `BranchLockedError`. Otherwise create the writer key (with TTL), release gate, spawn heartbeat task, then yield.
- On exit (regardless of how): cancel heartbeat task and delete writer key.

**Raises**: `BranchLockedError` if a merge holds the branch and the caller is not bypassing.

**Yields**: `None`.

## `acquire_merge`

```python
@asynccontextmanager
async def acquire_merge(
    self,
    source_branch: str,
    target_branch: str,
    *,
    drain_timeout: float | None = None,
) -> AsyncIterator[str]:
    ...
```

**Pre-conditions**:
- `source_branch` and `target_branch` are distinct, valid existing branches.
- Caller has already acquired `MergeLocker.acquire_global_lock()` (existing global merge serialization is preserved during this rollout).

**Behavior**:
- Generates a `holder_id` (UUID4).
- Acquires the gates for `[source_branch, target_branch]` in sorted name order.
- Writes `merge_intent` on both branches with the configured TTL and value = `holder_id`.
- Sets the module-level `MergeHolder` ContextVar.
- Releases both gates.
- Spawns a heartbeat task to renew both `merge_intent` keys.
- Polls writer keys on both branches until empty; raises `MergeWriteDrainTimeoutError` after `drain_timeout` (default = `config.merge.write_drain_timeout_seconds`).
- Yields `holder_id` to the caller. The caller's `async with` body runs the merge.
- On exit (success, exception, or drain timeout): cancels heartbeat, clears `merge_intent` on both branches, resets ContextVar token.

**Raises**:
- `MergeWriteDrainTimeoutError` if writers do not drain within `drain_timeout`.
- Any exception raised by the merge body propagates after cleanup.

**Yields**: `holder_id: str` — the caller passes this as `merge_holder_id` to any Prefect sub-flow it submits while in the body.

## Exceptions

```python
class BranchLockedError(InfrahubError):
    """Branch is currently held by an in-progress merge."""
    HTTP_STATUS = 409
    GRAPHQL_CODE = "BRANCH_LOCKED_FOR_MERGE"

    def __init__(self, branch_name: str) -> None:
        super().__init__(
            message=f"Branch '{branch_name}' is currently being merged; retry once the merge completes.",
        )
        self.branch_name = branch_name


class MergeWriteDrainTimeoutError(InfrahubError):
    """A merge timed out waiting for in-flight writes on its branches to complete."""
    HTTP_STATUS = 503

    def __init__(self, branches: list[str], timeout_seconds: float) -> None:
        super().__init__(
            message=(
                f"Merge could not start: writes on {branches} did not complete within "
                f"{timeout_seconds:.0f}s. Branches have been released; retry the merge."
            ),
        )
        self.branches = branches
        self.timeout_seconds = timeout_seconds
```

Both extend the existing `InfrahubError` hierarchy at `backend/infrahub/exceptions.py`.

## `MergeHolder`

```python
@dataclass(frozen=True, slots=True)
class MergeHolder:
    holder_id: str
    source_branch: str
    target_branch: str
```

Module-level `ContextVar`:

```python
_MERGE_HOLDER: ContextVar[MergeHolder | None] = ContextVar("infrahub_merge_holder", default=None)
```

Set/reset only by `acquire_merge`. Read only by `acquire_write`.

## Thread/coroutine safety

- `BranchLocker` is safe to share across coroutines in a single process.
- All internal state is per-call (writer_id is generated per `acquire_write` invocation; holder_id per `acquire_merge`).
- The ContextVar is correctly isolated per task by Python's `contextvars` semantics.

## Performance contract

- `acquire_write` against a branch with no merge in progress: one cache `set(... not_exists=True)` (or equivalent on NATS), plus the gate acquire/release. Target: under 1 ms p99 on a healthy cache.
- `acquire_write` while a merge holds the branch: one cache `get`, raises immediately. Sub-millisecond.
- `acquire_merge` happy path with no in-flight writers: gate acquire ×2, set ×2, list ×2, release. Sub-100 ms.
- Heartbeat overhead: one cache `set` per heartbeat interval per active writer/merge. Negligible at production scale.
