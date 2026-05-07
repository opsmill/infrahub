# Phase 1 — Data Model

This feature does not change the Neo4j graph schema. It introduces coordination state that lives in the existing cache backend (Redis or NATS KV via `infrahub.services.adapters.cache`). All entities below are runtime/transient — they are not persisted to the database, do not appear on any branch, and do not participate in branch versioning.

## Entities

### MergeHolder *(in-process Python object; module-level ContextVar value)*

Identifies the merge that currently holds a branch claim. Created by `acquire_merge` and stored in a module-level `ContextVar[MergeHolder | None]` for the duration of the merge.

| Field | Type | Notes |
|---|---|---|
| `holder_id` | `str` (UUID) | Generated at merge entry. Stored in the cache as the value of `merge_intent` keys. Returned to the caller of `acquire_merge` so it can be passed as a Prefect parameter to sub-flows. |
| `source_branch` | `str` | Source branch name (the branch being merged from). |
| `target_branch` | `str` | Target branch name (typically `main`). |

Frozen dataclass. Immutable for the merge's lifetime.

### Coordination key: `branch.{name}.gate`

Single-mutex `InfrahubLock` per branch. Used as a brief critical section inside `acquire_write` (read merge_intent; if clear, register writer key) and inside `acquire_merge` (set merge_intent on both branches; enumerate writer keys).

| Aspect | Value |
|---|---|
| Lock primitive | `InfrahubLock` via `lock.registry.get(name=f"branch.{name}.gate")` |
| Held during | The check-and-claim step only — never during the actual write or the merge body |
| Acquisition order in `acquire_merge` | `sorted([source, target])` to avoid deadlock between concurrent merges |
| Lifetime | Acquired and released within milliseconds |

### Coordination key: `branch.{name}.merge_intent`

Per-branch flag indicating that a merge is holding the branch. When present, new writes against the branch are rejected (unless the writer presents the matching `holder_id`).

| Aspect | Value |
|---|---|
| Cache backend | Redis: `SET branch.{name}.merge_intent <holder_id> EX <ttl>` (per-key TTL). NATS: `kv.put` into the `FIVE_MINUTES` bucket (bucket-level TTL). |
| Value | The merge's `holder_id` (UUID string). |
| Default TTL | 300 s (configurable via `config.merge.intent_ttl_seconds`) |
| Heartbeat | Every 75 s (TTL / 4) by the heartbeat task in `acquire_merge`. The TTL/4 fraction (rather than TTL/2) gives ~3.75 minutes of slack against a starved heartbeat task — see Heartbeat Robustness note below. |
| Created by | `acquire_merge`, atomically inside the gate critical section, on both source and target branches |
| Cleared by | `acquire_merge`'s exit path (graceful or timeout). On crash, the TTL expires the key. |

### Coordination key: `branch.{name}.writers.{writer_id}`

Per-active-writer key indicating that a write is in progress on `{name}`. The merge enumerates these keys to determine whether the branch has drained.

| Aspect | Value |
|---|---|
| Cache backend | Redis: `SET branch.{name}.writers.{writer_id} 1 EX <ttl>`. NATS: `kv.put` into the `TWO_MINUTES` bucket. |
| `writer_id` | UUID generated per `acquire_write` call. |
| Value | Sentinel (`"1"` or empty) — the *existence* of the key is what matters. |
| Default TTL | 120 s (configurable via `config.merge.writer_ttl_seconds`) |
| Heartbeat | Every 30 s (TTL / 4) by the heartbeat task in `acquire_write`. |
| Created by | `acquire_write` after the gate sees no `merge_intent` (or finds the holder_id matches). |
| Removed by | `acquire_write`'s exit path; or TTL expiry on crash. |
| Enumerated by | `acquire_merge`'s drain loop via `cache.list_keys("branch.{name}.writers.*")` |

## Lifecycle

### Writer lifecycle

```
1. caller enters `async with branch_locker.acquire_write(branch_name, holder_id=...)`
2. ContextVar check: is there a MergeHolder in the ContextVar whose source/target matches branch_name? → bypass (no writer key)
3. holder_id check (cross-process): does caller pass holder_id? Read merge_intent for branch_name; if value matches, bypass.
4. acquire branch.{name}.gate
5. read branch.{name}.merge_intent
   - if set (and not bypassing): release gate; raise BranchLockedError
   - else: write branch.{name}.writers.{writer_id} with TTL; release gate
6. spawn heartbeat task that re-writes the writer key every TTL/4 seconds
7. yield to caller — caller does its write
8. on exit (success or exception):
   - cancel heartbeat
   - delete writer key
```

### Merge lifecycle

```
1. caller enters `async with branch_locker.acquire_merge(source, target, drain_timeout=...)`
2. generate holder_id (UUID)
3. acquire gates in canonical order (sorted([source, target]))
4. write merge_intent on source and target with TTL, value = holder_id
5. set ContextVar to MergeHolder(holder_id, source, target)
6. release both gates
7. spawn heartbeat task that re-writes both merge_intent keys every TTL/4
8. drain loop: poll branch.{source}.writers.* and branch.{target}.writers.* until both empty
   - on timeout: cancel heartbeat; clear merge_intent on both; reset ContextVar; raise MergeWriteDrainTimeoutError
9. yield holder_id to caller — caller does the merge body
10. on exit (success, exception, or timeout):
    - cancel heartbeat
    - clear merge_intent on source and target
    - reset ContextVar token
```

## State transitions

The branch's `merge_intent` cell has three states:

```
EMPTY  ── set by acquire_merge ──▶  HELD (value = holder_id, TTL active)
HELD   ── deleted by acquire_merge exit  ──▶  EMPTY
HELD   ── TTL expires (heartbeat stopped) ──▶  EMPTY
HELD   ── re-written by heartbeat ──▶  HELD (TTL window reset)
```

A writer key has a similar set of transitions:

```
ABSENT ── written by acquire_write ──▶ ALIVE (TTL active)
ALIVE  ── deleted by acquire_write exit ──▶ ABSENT
ALIVE  ── TTL expires ──▶ ABSENT
ALIVE  ── heartbeat re-write ──▶ ALIVE (TTL reset)
```

## Configuration values

Added to `backend/infrahub/config.py` under a new `MergeSettings` section (or extending the existing one if present):

| Setting | Default | Range | Notes |
|---|---|---|---|
| `merge.write_drain_timeout_seconds` | 30 | 0 – 600 | Max time `acquire_merge` waits for writers to drain. |
| `merge.intent_ttl_seconds` | 300 | 60 – 3600 | TTL of `merge_intent` keys. Heartbeat is at half this interval. |
| `merge.writer_ttl_seconds` | 120 | 30 – 600 | TTL of writer keys. Heartbeat is at half this interval. |

The TTL values bind to the available cache TTL buckets on NATS:
- `intent_ttl_seconds = 300` → `KVTTL.FIVE_MINUTES` (new — added by this work)
- `writer_ttl_seconds = 120` → `KVTTL.TWO_MINUTES` (new — added by this work)

If a deployment overrides the TTL to a value not represented by an existing bucket, the NATS adapter must be extended to register the corresponding bucket. Redis routes any TTL value through `EX` directly.

## Validation rules

- `holder_id` is generated server-side (UUID4); no caller-supplied identity. Prevents spoofing of the bypass mechanism.
- `branch.{name}` keys use `name` as a literal. Branch names are validated upstream (existing concern); no further sanitization is applied at the cache layer beyond the cache adapter's own key handling.
- `writer_ttl < intent_ttl` is required (config-load-time validation): a writer must not outlive an intent it is contending with.
- `drain_timeout < intent_ttl` is required: the drain wait must not exceed the lifetime of the intent it just claimed.
- Heartbeat interval = TTL / 4 (computed, not configured). The TTL/4 fraction provides slack against transient heartbeat starvation: with the default `intent_ttl_seconds = 300`, a heartbeat task could miss up to three consecutive scheduled wake-ups (e.g., because the merge body executed a CPU-bound section that did not yield to the event loop) before the cache key would be at risk of TTL expiry. This is the primary safety margin protecting a healthy long-running merge from being falsely evicted (FR-011, SC-003).

### Heartbeat Robustness

The heartbeat is an `asyncio.Task` running on the same event loop as the merge body (or write body). It only runs when the loop yields. The dominant risk is a CPU-bound section in the merge body that does not `await` for longer than the TTL — this is uncommon in async-first code but possible when, e.g., processing a large in-memory diff result. The chosen TTL/4 fraction gives the heartbeat three "scheduled wake-up" attempts before a missed deadline becomes a missed key-refresh, and the merge body's typical Cypher work is server-side (the Python side awaits, so the loop runs the heartbeat). A unit test (T010 sub-bullet h) deliberately injects a synchronous block longer than TTL/2 to verify the heartbeat survives.

## Cardinality and scope

- One `MergeHolder` ContextVar exists per process (module-level). It carries at most one merge holder at any time within that process — consistent with the single-merge invariant (FR-015).
- Up to one `merge_intent` key per branch at any time.
- Up to N writer keys per branch, where N is the number of in-flight writers across all backend processes. There is no system-imposed limit; in practice it is bounded by request concurrency.
