# Data Model: Licensing Resource-Allocation Telemetry

All payload types are Pydantic `BaseModel` (Principle III) in `backend/infrahub/telemetry/models.py`; the per-process reading that transits the cache is a Pydantic model in `backend/infrahub/telemetry/resources.py`. Every new figure may be `None`: `None` = source failed / not applicable / unbounded; a number = measured. The new database figure, the figures of the per-process reading and of `per_container`, and the payload's `processes_per_container` are `int | None`; the reading's own `processes_per_container` is a required `int`, and the three existing database figures stay plain `int`. The design **extends the database's `system_info` in place**, adds new `server` and `task_workers` blocks, leaves `workers` unchanged, and reuses the existing `system_info` field naming (`processor_*` / `memory_*`) for every component, so DB, server, and task-worker resources carry the same field names and units. The server and task-worker figures are one container's, undivided, so they are comparable with the database's after multiplying by the block's `active` count and dividing by its `processes_per_container`. Even then they differ under a fractional CPU quota, where `processor_available` rounds down for the server and task workers and up for the database (see the per-process table below).

## Field naming (uniform, matches the existing `system_info`)

Every component reports the same four fields — the database on `system_info`, the server and task workers inside the `per_container` object of their block:

| Field | Meaning |
|-------|---------|
| `processor_available` | The CPUs the component can use: the smallest of the machine's CPU count, the container's CPU limit and the CPUs the process is pinned to. For the server and workers a fractional limit is rounded down (2.5 counts as 2, never below 1); Neo4j rounds it up for the database. |
| `processor_assigned` | The CPU limit someone set: the container limit rounded up for the server and workers, the parallel query engine setting for the database. `None` when no limit is set or it cannot be read; never filled in from the machine. |
| `memory_total` | Memory in bytes: the container's memory limit when one is set, otherwise the machine's memory. |
| `memory_available` | Free memory in bytes under that limit, or the machine's free memory. Memory used is `memory_total − memory_available`, as the database already reports it. |

The [contract](contracts/telemetry-resources.md#where-the-api-server-and-task-worker-figures-come-from) explains in plain terms when the container limit is used and when the machine's figures are.

## Changes to existing models

### `TelemetryDatabaseSystemInfoData` (extend)

Already carries `memory_total`, `memory_available`, `processor_available`. Add one field:

| Field | Type | Source |
|-------|------|--------|
| `processor_assigned` | `int \| None` (default `None`) | `server.cypher.parallel.worker_limit` via `SHOW SETTINGS`; `0`/auto → `None`. |

The DB gains **only** `processor_assigned` — everything else it already has. Zero duplication.

### `TelemetryWorkerData` (unchanged)

Keeps exactly its existing fields, `total` and `active`, with their existing meaning: they count every worker process, API server processes and task workers together (research D17). This feature adds nothing to it.

**Worker counts**: the new `server` and `task_workers` blocks break `workers` down by component. `server.active + task_workers.active` always equals `workers.active`. `server.total + task_workers.total` equals `workers.total`, except for a process known only by its generic presence key, which names no component: `workers` counts it and the new blocks do not. That is a process that stopped about two hours earlier: the keys naming its component have expired, but its 2-hour presence key has not yet, normally for at most the last 5 minutes or so before Infrahub forgets it; research D17 lists when it lasts longer, such as when the process's reads failed. Each process is matched to its component by the component name its own cache keys carry.

**Tracking note**: INFP-589 (Phase 1) shipped the event-window and node-count work and explicitly deferred worker cores and RAM to INFP-631 (Phase 2). The resource figures and the `server` and `task_workers` blocks are that Phase 2 licensing part, split out ahead of the rest of INFP-631 so the licensing work is not blocked behind its unrelated items. The pull request, its branch and this folder are named for INFP-631; the work was first opened against INFP-589 in #10003, which carries its earlier review history. The product question INFP-631 records — whether a tier is defined by database resources alone or also by app-worker resources — remains open and does not gate collection, since all three components are reported either way (spec Assumptions, "Reported components").

## New models

### `TelemetryContainerData` (new)

The CPU and memory of one container of a component, undivided, carried as `per_container` by the `server` and `task_workers` blocks (`TelemetryComponentData`). Every process in the container shares these figures. No field carries a constraint; the figures are copied from a reading already validated on its way out of the cache.

| Field | Type |
|-------|------|
| `processor_available` | `int \| None` (default `None`) |
| `processor_assigned` | `int \| None` (default `None`) |
| `memory_total` | `int \| None` (default `None`), bytes |
| `memory_available` | `int \| None` (default `None`), bytes |

### `TelemetryComponentData` (new)

One component's processes and resources. `TelemetryData` uses it twice: `server` for the API server and `task_workers` for the task workers (git_agent). Its fields, in this order:

- `total`/`active` (`int | None`, default `None`): that component's processes, counted the same way `workers` counts every worker process. For the API server this is one per gunicorn process. `None` only on a block that was never gathered, such as one deserialized from a snapshot that predates it.
- `processes_per_container` (`int | None`, default `None`): how many processes share the container that `per_container` describes, taken from the same reading. `None` when the component has no reading.
- `per_container: TelemetryContainerData`: one of the component's containers, undivided.

The component's total is `per_container × active ÷ processes_per_container` (research D19).

### `TelemetryData` (extend)

Add two fields; nothing existing is renamed, removed, retyped, or given a new meaning (FR-008):

```python
server: TelemetryComponentData = Field(default_factory=TelemetryComponentData)
task_workers: TelemetryComponentData = Field(default_factory=TelemetryComponentData)
```

`workers` is unchanged. `database` keeps its position and gains one defaulted field, `database.system_info.processor_assigned`. There is **no** parallel `resources` block.

## Per-process reading (transits the cache, not part of the payload)

Read by each process at startup and every 5 minutes, on a separate thread its main loop starts, and written by that read into `workers:resources:{component}:worker:{WORKER_IDENTITY}` with a 2-hour expiry. The gatherer reads back only the readings of the workers that are active when it counts them (research D18):

| Field | Type | Source |
|-------|------|--------|
| `processes_per_container` | `int`, required, at least 1 (`ge=1`) | How many processes share the container. For an API server process started by gunicorn it is gunicorn's worker count, which the gunicorn worker class puts in the `INFRAHUB_INTERNAL_PROCESSES_PER_CONTAINER` environment variable before the app loads; it is 1 for any other process, and when the value is missing or is not a positive whole number. It is given to the reader when the reader is built, not read from the container (D19). |
| `processor_available` | `int \| None` | `psutil.cpu_count(logical=True)` capped by the cgroup CPU quota **and** by the process's CPU-affinity mask, i.e. `min(host, max(1, floor(quota)), affinity)`, each cap applied only when known (D2 correction — psutil alone is not container-aware, and a `cpuset` restriction sets no quota; the quota rounds **down** here and **up** for `processor_assigned`). |
| `processor_assigned` | `int \| None` | cgroup CPU quota rounded up (D3/D5); `None` if unbounded. Both CPU figures are `None` when a CPU limit file exists but yields no usable limit. |
| `memory_total` | `int \| None` | The most restrictive cgroup `memory.max` across every enforcing level — an ancestor's limit is charged against its whole subtree, so it binds even when the process's own level is unset; else `psutil.virtual_memory().total`. Both memory figures are `None` when a memory limit file exists but yields no usable limit, or when the host capacity read fails. |
| `memory_available` | `int \| None` | Smallest `max(0, memory.max − memory.current)` across every level that enforces a limit (an ancestor's limit is charged against its whole subtree, so it can bind first); else `psutil.virtual_memory().available`. Clamped at zero, since a limit lowered below current usage would otherwise go negative. `None` on its own, leaving `memory_total` standing, when a usage file or the host free-memory read fails. |

Internal transport shape (`WorkerResourceReading`, a small typed model in `resources.py`), **not** a payload model — the payload carries the figures and the count of one reading per component, never per-process rows (FR-004). The four figures are bounded non-negative (`ge=0`) and the count is at least 1 (`ge=1`), so a corrupted cache entry fails to parse and is skipped by the scan rather than reaching the payload. A read that fails after its retries stores nothing, so the process's last stored reading stays until it expires, 2 hours after it was stored (D19). A reading whose CPU and memory pairs were both nulled field by field is stored like any other, and still gives the count.

The resolved cgroup path and the host's logical CPU count are read once per process and cached — neither can change without a container restart. The count of processes per container is given when the reader is built. `processor_available`, `processor_assigned`, `memory_total`, and `memory_available` are all re-read every 5 minutes, since a live limit reconfiguration (a `docker update`, a Kubernetes in-place pod resize) changes them without restarting the process (D12).

## Field derivation per component

| Component → payload location | processor_available | processor_assigned | memory_total | memory_available |
|------------------------------|---------------------|--------------------|--------------|------------------|
| **database** → `database.system_info` | existing JMX | **NEW** (`worker_limit`, `0`→`None`) | existing JMX | existing JMX |
| **server** → `server.per_container` | chosen api_server reading, undivided | same; `None` when the chosen reading has none | same | same |
| **task workers** → `task_workers.per_container` | chosen git_agent reading, undivided | same; `None` when the chosen reading has none | same | same |

`server.processes_per_container` and `task_workers.processes_per_container` are the count of the same chosen reading.

**`database.system_info.processor_assigned` reports `server.cypher.parallel.worker_limit`**, `null` where it is unset. The `infrahub-enterprise` chart presets set it to the preset's Neo4j CPU request (4, 8 or 16, infrahub-helm#93), so those installs report their sized database cores today; the community chart and the compose file leave it unset. It caps the Cypher parallel runtime's worker threads, not Neo4j's total CPU use. **`server.per_container.processor_assigned` and `task_workers.per_container.processor_assigned`** come from live cgroup CPU-quota reads, so a deployment running with a configured container CPU limit reports a finite value — see D3. `processor_assigned` is never derived from `processor_available`; the derivation runs the other way only — `processor_available` is capped by the quota that `processor_assigned` reports.

## Per-container rules (server + task_workers) — D19

Given the readings the scan returns for a component type (one per active process that has a stored reading, research D18):

1. **No reading**: `processes_per_container` and every `per_container` figure are `None`. `total` and `active` still count the component's processes.
2. **Choose the most complete reading**: the one with the most non-`None` figures; on a tie, the first one the scan returned. The count does not take part in the choice.
3. **Report it undivided**: its four figures go into `per_container` as they are, and its count into `processes_per_container`. A `None` figure stays `None`, and a reading with no figures still gives the count.

A task worker has its container to itself, so its count is 1. The API server's gunicorn processes share one container, so its count is gunicorn's worker count. `per_container × active ÷ processes_per_container` is the component's total on the assumption that every replica runs with the same configuration. An API server that runs several processes in one container but is not started through gunicorn with Infrahub's worker class reports a count of 1, which overstates its total (research D19). The contract lists the consumer-facing consequences.

## Validation rules

- The per-process reading's four figures are non-negative when present (Pydantic `ge=0`), and its `processes_per_container` is required and at least 1 (`ge=1`), so a corrupted cache entry fails to parse and is skipped.
- `database.system_info.processor_assigned` carries `ge=0`; its reader already maps a non-positive setting to `None`.
- The three existing `system_info` figures (`memory_total`, `memory_available`, `processor_available`) stay plain `int` with no constraint: the database gather is not guarded, so a value failing a constraint would abort the whole snapshot rather than being stored as read.
- `TelemetryContainerData` and the payload's `processes_per_container` carry no constraint; they are copied from a reading already validated.
- All new payload fields default to `None`, so partial degradation never fails model construction. The reading's `processes_per_container` is the one required field, and the reader always sets it.
- The `server` and `task_workers` blocks, each with its `per_container` object, are always present on every produced snapshot. `database.system_info` is the exception: it stays `None` when the database is not Neo4j, in which case the whole block — including the new `processor_assigned` field — is absent rather than null-valued (FR-006, FR-007). An unreachable database aborts the snapshot instead, since the database gather is not guarded.
