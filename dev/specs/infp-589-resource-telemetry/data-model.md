# Data Model: Licensing Resource-Allocation Telemetry

All types are Pydantic `BaseModel` (Principle III) in `backend/infrahub/telemetry/models.py`. Every new figure is `int | None`: `None` = source failed / not applicable / unbounded; a number = measured. The design **extends existing payload sections in place** and reuses the existing `system_info` field naming (`processor_*` / `memory_*`) for every component, so DB, server, and worker resources are byte-for-byte comparable.

## Field naming (uniform, matches the existing `system_info`)

Every component reports the same four fields:

| Field | Meaning |
|-------|---------|
| `processor_available` | Logical CPUs detected/visible (vCPUs). |
| `processor_assigned` | Configured/enforced CPU limit; `None` when unbounded. |
| `memory_total` | Memory capacity in bytes (cgroup limit when set, else host total). |
| `memory_available` | Free memory in bytes. Usage is derived as `memory_total − memory_available` — the same representation the database already uses (no separate `*_used` field). |

## Changes to existing models

### `TelemetryDatabaseSystemInfoData` (extend)

Already carries `memory_total`, `memory_available`, `processor_available`. Add one field:

| Field | Type | Source |
|-------|------|--------|
| `processor_assigned` | `int \| None` (default `None`) | `server.cypher.parallel.worker_limit` via `SHOW SETTINGS`; `0`/auto → `None`. |

The DB gains **only** `processor_assigned` — everything else it already has. Zero duplication.

### `TelemetryWorkerData` (extend)

Already carries `total`, `active` (the worker count — kept as-is). Add the task-worker (git_agent) fleet resources, all `int | None` default `None`:

`processor_available`, `processor_assigned`, `memory_total`, `memory_available` — the fleet aggregate summed over distinct git_agent hosts.

**Scope note**: `total`/`active` retain their existing meaning (all worker processes, api_server + git_agent, by identity). The new resource fields are the **git_agent (task-worker) fleet** specifically; api_server resources live in the new `server` block. This asymmetry is documented in the contract.

## New model

### `TelemetryServerData` (new)

The api_server has no existing representation, so a new block is added (not a duplicate). Same four fields, all `int | None` default `None`: `processor_available`, `processor_assigned`, `memory_total`, `memory_available`.

### `TelemetryData` (extend)

Add one field; nothing existing is renamed, removed, or retyped (FR-008):

```
server: TelemetryServerData = Field(default_factory=TelemetryServerData)
```

`workers` and `database` keep their positions and simply carry additional optional fields. There is **no** parallel `resources` block.

## Per-process reading (transits the cache, not part of the payload)

Written by each process into `workers:resources:{component}:worker:{WORKER_IDENTITY}` at heartbeat time:

| Field | Type | Source |
|-------|------|--------|
| `host` | `str` | `socket.gethostname()` (container id). Dedup key. |
| `processor_available` | `int \| None` | `psutil.cpu_count(logical=True)` (logical CPUs). |
| `processor_assigned` | `int \| None` | cgroup CPU quota (D3/D5); `None` if unbounded. |
| `memory_total` | `int \| None` | cgroup `memory.max` if set, else `psutil.virtual_memory().total`. |
| `memory_available` | `int \| None` | (`memory.max − memory.current`) if cgroup-limited, else `psutil.virtual_memory().available`. |

Internal transport shape (a small typed model in `resources.py`), **not** a payload model — the payload carries only the per-component aggregate, never per-process rows (FR-004). The `host` identifier is dedup-only and never emitted.

Static fields (`host`, `processor_available`, `processor_assigned`, `memory_total`) are read once per process and cached; only `memory_available` (free, which changes with usage) is refreshed on each heartbeat (D12).

## Field derivation per component

| Component → payload location | processor_available | processor_assigned | memory_total | memory_available |
|------------------------------|---------------------|--------------------|--------------|------------------|
| **database** → `database.system_info` | existing JMX | **NEW** (`worker_limit`, `0`→`None`) | existing JMX | existing JMX |
| **server** → new `server` block | dedup-sum api_server hosts | dedup-sum; `None` if any host unbounded | dedup-sum | dedup-sum |
| **workers** → `workers` block (new fields) | dedup-sum git_agent hosts | dedup-sum; `None` if any host unbounded | dedup-sum | dedup-sum |

Every `processor_assigned` is a **live read that returns `None` today** (nothing enforced yet) and self-populates once a limit is configured — see D3. `processor_assigned` is never derived from `processor_available`.

## Aggregation rules (server + workers) — D8/D9

Given the active processes of a component type, each with a reading `{host, …}`:

1. **Group by `host`**; keep one reading per host (intra-host readings are identical).
2. For each field, **sum across distinct hosts**.
3. **Null-vs-undercount**:
   - no host reported field *f* → aggregate *f* = `None`;
   - a contributing host has *f* = `None` because it is genuinely unbounded → aggregate *f* = `None`;
   - some hosts reported, some did not → sum the reporters (**undercount**). `workers.total`/`active` (unchanged) still reflect all workers, so the gap is detectable.

## Validation rules

- Byte and core counts are non-negative when present.
- All new fields default to `None`, so partial degradation never fails model construction.
- The `server` block and the new `workers` / `system_info` fields are always present on a produced snapshot, even if every value is `None` (FR-006, FR-007).
