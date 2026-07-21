# Data Model: Licensing Resource-Allocation Telemetry

All types are Pydantic `BaseModel` (Principle III), placed in `backend/infrahub/telemetry/models.py`. Every figure is `int | None`: `None` = source failed / not applicable / unbounded; a number = measured.

## New models

### `TelemetryComponentResources`

One component's resource reading.

| Field | Type | Meaning |
|-------|------|---------|
| `cores_available` | `int \| None` | Logical CPUs detected/visible to the component. |
| `cores_assigned` | `int \| None` | Enforced cgroup CPU quota (logical cores, rounded up). `None` when unbounded. |
| `ram_available` | `int \| None` | Memory capacity in bytes (cgroup limit when set, else host/JMX total). |
| `ram_used` | `int \| None` | Memory currently consumed, in bytes. |

Defaults: all `None`. A `default()` classmethod returns an all-`None` instance (matches the `TelemetryAccountData.default()` convention) for use when a whole block degrades.

### `TelemetryWorkerResources`

The worker fleet aggregate — `TelemetryComponentResources` plus a count.

| Field | Type | Meaning |
|-------|------|---------|
| `count` | `int` | Number of active `git_agent` worker processes. Always known from the heartbeat scan; default `0`. |
| `cores_available` … `ram_used` | `int \| None` | Fleet aggregate — sum over **distinct hosts** (see rules below). |

### `TelemetryResourcesData`

The payload block.

| Field | Type |
|-------|------|
| `database` | `TelemetryComponentResources` |
| `server` | `TelemetryComponentResources` |
| `workers` | `TelemetryWorkerResources` |

### `TelemetryData` (existing) — additive change

Add one field; nothing else changes (FR-008):

```
resources: TelemetryResourcesData = Field(default_factory=...)
```

No existing field or model is renamed, removed, or retyped — including the `database` block and its `system_info`, which stay exactly as-is. `resources.database` reuses the same JMX numbers in parallel (intentional, minor redundancy), so existing consumers of `database`/`system_info` are unaffected. The only value that changes for existing consumers is `payload_format` (the version bump) — see the contract's compatibility note; keep it additive-only and coordinate the bump with the receiving service.

## Per-process reading (transits the cache, not part of the payload)

Written by each process into `workers:resources:{component}:worker:{WORKER_IDENTITY}` at heartbeat time. Shape:

| Field | Type | Source |
|-------|------|--------|
| `host` | `str` | `socket.gethostname()` (container id). Dedup key. |
| `cores_available` | `int \| None` | `os.cpu_count()`. |
| `cores_assigned` | `int \| None` | cgroup CPU quota (D3/D5). |
| `ram_available` | `int \| None` | cgroup `memory.max` if set, else `psutil.virtual_memory().total`. |
| `ram_used` | `int \| None` | cgroup `memory.current` if readable, else `psutil.virtual_memory().used`. |

This is an internal transport shape (a small typed model in `resources.py`), deliberately **not** the payload model — the payload carries the aggregate, never the per-process rows (FR-004: no per-worker breakdown). The `host` identifier exists only to deduplicate the aggregate and is never emitted in the payload.

Static fields (`host`, `cores_available`, `cores_assigned`, `ram_available`) are read once per process and cached; only `ram_used` is refreshed on each heartbeat (D12).

## Field derivation per component

| Component | cores_available | cores_assigned | ram_available | ram_used |
|-----------|-----------------|----------------|---------------|----------|
| **database** | JMX `AvailableProcessors` (existing) | `server.cypher.parallel.worker_limit` via `SHOW SETTINGS`; `0`/auto → `None` | JMX `TotalMemorySize` | `TotalMemorySize − FreeMemorySize` |
| **server** | dedup-sum of api_server host readings | dedup-sum of cgroup quota; `None` if any host unbounded | dedup-sum | dedup-sum |
| **workers** | dedup-sum of git_agent host readings | dedup-sum of cgroup quota; `None` if any host unbounded | dedup-sum | dedup-sum |

Every `cores_assigned` source is a **live read that returns `None` today** (nothing is enforced yet) and self-populates once a limit is configured — see D3. The reader carries a comment documenting the intended knob (the Neo4j parallel-worker setting for the database; the container CPU quota for server/workers). `assigned` is never derived from `available`. `workers.count` is Pete's "number of workers configured" and is a real value today, separate from the per-worker CPU cap.

## Aggregation rules (server + workers) — D8/D9

Given the active processes of a component type, each with a reading `{host, …}`:

1. **Group by `host`**; keep one reading per host (intra-host readings are identical).
2. For each field, **sum across distinct hosts**.
3. **`count`** (workers only) = number of active `git_agent` **processes** (not hosts).
4. **Null-vs-zero**:
   - no active processes → `count = 0`, all aggregate fields `0`;
   - active processes exist but no host reported field *f* → aggregate *f* = `None`;
   - a contributing host has field *f* = `None` because it is genuinely unbounded (unlimited cgroup) → aggregate *f* = `None` (a fleet with an unbounded node has no finite total);
   - some hosts reported, some did not → sum the reporters (**undercount**), `count` unchanged so the gap is detectable.

## Validation rules

- Byte and core counts are non-negative when present.
- `count >= 0`.
- No field is required beyond `count` (default `0`); every other field defaults to `None`, so partial degradation never fails model construction.
- The block is always present on `TelemetryData`, even if every field is `None` (FR-006, FR-007).
