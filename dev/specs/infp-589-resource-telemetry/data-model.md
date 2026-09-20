# Data Model: Licensing Resource-Allocation Telemetry

All types are Pydantic `BaseModel` (Principle III) in `backend/infrahub/telemetry/models.py`. Every new figure is `int | None`: `None` = source failed / not applicable / unbounded; a number = measured. The design **extends existing payload sections in place** and reuses the existing `system_info` field naming (`processor_*` / `memory_*`) for every component, so DB, server, and worker resources are byte-for-byte comparable.

## Field naming (uniform, matches the existing `system_info`)

Every component reports the same four fields:

| Field | Meaning |
|-------|---------|
| `processor_available` | Logical CPUs (vCPUs) the component can use: the host's count capped by the enforced CPU quota, the rule the JVM applies to the database figure. |
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

**Scope note**: `total`/`active` retain their existing meaning (all worker processes, api_server + git_agent, by identity). The new resource fields are the **git_agent (task-worker) fleet** specifically; api_server resources live in the new `server` block. This asymmetry is documented in the contract — a consumer must not average `processor_available` over `total`, since the two fields describe different populations. A per-block host count, so each block is self-describing, is a candidate for the next gated `payload_format` bump (research D13); not added this phase.

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
| `processor_available` | `int \| None` | `psutil.cpu_count(logical=True)` capped by the cgroup CPU quota (D2 correction — psutil alone is not container-aware). |
| `processor_assigned` | `int \| None` | cgroup CPU quota (D3/D5); `None` if unbounded. |
| `memory_total` | `int \| None` | cgroup `memory.max` if set, else `psutil.virtual_memory().total`. |
| `memory_available` | `int \| None` | (`memory.max − memory.current`) if cgroup-limited, else `psutil.virtual_memory().available`. |

Internal transport shape (a small typed model in `resources.py`), **not** a payload model — the payload carries only the per-component aggregate, never per-process rows (FR-004). The `host` identifier is dedup-only and never emitted.

`host`, the resolved cgroup path, and the host's logical CPU count are read once per process and cached — none can change without a container restart. `processor_available`, `processor_assigned`, `memory_total`, and `memory_available` are all re-read on each heartbeat, since a live limit reconfiguration (a `docker update`, a Kubernetes in-place pod resize) changes them without restarting the process (D12).

## Field derivation per component

| Component → payload location | processor_available | processor_assigned | memory_total | memory_available |
|------------------------------|---------------------|--------------------|--------------|------------------|
| **database** → `database.system_info` | existing JMX | **NEW** (`worker_limit`, `0`→`None`) | existing JMX | existing JMX |
| **server** → new `server` block | dedup-sum api_server hosts | dedup-sum; `None` if any host unbounded | dedup-sum | dedup-sum |
| **workers** → `workers` block (new fields) | dedup-sum git_agent hosts | dedup-sum; `None` if any host unbounded | dedup-sum | dedup-sum |

**`database.system_info.processor_assigned` is `null` in this release** — Infrahub does not configure the Neo4j `worker_limit` setting itself, so it self-populates only once per-tier enforcement (a later phase) sets it. **`server.processor_assigned` and `workers.processor_assigned` are not gated on anything** — they are live cgroup CPU-quota reads, so a deployment already running with a configured container CPU limit reports a finite value today, independent of that later enforcement work — see D3. `processor_assigned` is never derived from `processor_available`; the derivation runs the other way only — `processor_available` is capped by the quota that `processor_assigned` reports.

## Aggregation rules (server + workers) — D8/D9

Given the active processes of a component type, each with a reading `{host, …}`:

1. **Group by `host`**; keep one reading per host (intra-host readings are identical).
2. For each field, **sum across distinct hosts**.
3. **Null-vs-undercount**:
   - no host reported field *f* → aggregate *f* = `None`;
   - a contributing host has *f* = `None` because it is genuinely unbounded (`processor_assigned` only) → aggregate *f* = `None`;
   - some hosts reported, some did not — whether a host never reported at all, or a contributing host's read of this one field failed while its other fields succeeded → sum the reporters (**undercount**), *except* `processor_assigned`, which the previous rule already covers exhaustively: any contributing host's `None` there, whether genuine unbounded-ness or a failed read, nulls the whole aggregate rather than being summed as an undercount. `workers.total`/`active` (unchanged) still reflect all workers, so the gap is detectable.

## Validation rules

- Byte and core counts are non-negative when present — enforced via Pydantic `ge=0` constraints.
- All new fields default to `None`, so partial degradation never fails model construction.
- The `server` block and the new `workers` / `system_info` fields are always present on every produced snapshot; `system_info` itself remains `None` when the database is unreachable or not Neo4j, in which case the whole block — including the new `processor_assigned` field — is absent rather than null-valued (FR-006, FR-007).
