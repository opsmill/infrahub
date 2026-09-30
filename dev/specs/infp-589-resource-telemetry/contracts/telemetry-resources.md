# Contract: resource fields in the telemetry payload

**Consumer**: the telemetry-receiving cloud processor + data mart (cross-team).
**Producer**: Infrahub `send_telemetry_push` flow.
**Change type**: **additive, in place** — no new top-level `resources` block. DB resources extend `database.system_info`, worker resources extend `workers`, and a single new `server` block is added for the api_server. No existing field is renamed, removed, or retyped.

**Naming**: every component uses the **same field names as the existing `system_info`** — `processor_available`, `processor_assigned`, `memory_total`, `memory_available` — so DB, server, and worker figures are directly comparable. Memory usage is derived as `memory_total − memory_available` (the representation the DB already uses; there is no `*_used` field).

**Version**: `payload_format` is **not** incremented this phase; the new fields ship additively under the existing version (`20260628`). The bump is a gated follow-up once the receiving service confirms tolerance (research D13). A consumer pinned to the old shape keeps working.

## Shape (only the additions shown; everything else unchanged)

`database.system_info` is `null` as a whole when the database is unreachable or is not Neo4j, so a consumer checks the block before its fields. `server` and the `workers` resource fields are always present.

```jsonc
// Illustrative deployment: Neo4j on a 32-core node with the `large` enterprise preset's
// 16-worker parallel runtime limit, one API server container running 4 gunicorn processes,
// limited to 4 CPUs / 4 GiB, and two task-worker containers limited to 4 CPUs / 4 GiB each.
{
  "payload_format": "20260628",              // UNCHANGED this phase
  "data": {
    "database": {
      // ... existing database fields ...
      "system_info": {                       // null as a whole when the DB is unreachable or not Neo4j
        "processor_available": 32,           // existing — CPUs the DB can use (JVM, quota-aware)
        "processor_assigned": 16,            // NEW — server.cypher.parallel.worker_limit; null where unset
        "memory_total": 67435982848,         // existing — bytes
        "memory_available": 47034888192      // existing — free bytes
      }
    },
    "workers": {
      "total": 2,                            // existing key, now task-worker PROCESSES only
      "active": 2,                           // existing key, same scope as total
      "processor_available": 8,              // NEW — fleet TOTAL, not per worker: 4 + 4 over the 2 task-worker hosts
      "processor_assigned": 8,               // NEW — fleet TOTAL of enforced quotas; null if any host is unbounded
      "memory_total": 8589934592,            // NEW — fleet TOTAL: 4 GiB + 4 GiB
      "memory_available": 6442450944         // NEW — fleet TOTAL free: 3 GiB + 3 GiB
    },
    "server": {                              // NEW block — the API server
      "total": 4,                            // NEW — API server PROCESSES: 4 gunicorn workers in one container
      "active": 4,                           // NEW — same scope as total
      "processor_available": 4,              // one container counted once, not once per gunicorn process
      "processor_assigned": 4,
      "memory_total": 4294967296,            // 4 GiB
      "memory_available": 2684354560         // 2.5 GiB free
    }
    // ... all other existing fields unchanged ...
  }
}
```

Each block describes one component only: `workers` is the task-worker fleet and `server` the API server, counts and resources alike. A consumer that wants every worker process sums `workers.total + server.total` (6 above), the figure `workers.total` alone used to carry.

Every resource figure is a **fleet total** summed over distinct hosts, never a per-worker value. `server` shows why the count and the resources still differ in unit: its four gunicorn processes share one container, so it counts 4 processes but reports that container's 4 CPUs once, not 16. Task-workers run one process per container in the documented deployment shape, so there the process count and the host count coincide.

## Field semantics

- **Units**: `processor_*` are logical CPUs (vCPUs); `memory_*` are bytes. **Usage** = `memory_total − memory_available`, uniformly across all three components.
- **`memory_total`** is the component's memory capacity, not the host's. For `server` and `workers` it is the most restrictive enforced container memory limit when one is configured — the limit *is* the reported total, since memory has no separate `assigned` figure — and the host's total otherwise; the database figure is the JVM-reported physical total. So a memory audit reads `memory_total` directly rather than differencing it against a limit field.
- **`processor_available`** is the logical CPUs the component can actually use: the host's count capped by any enforced CPU quota, for every component, so the figure is comparable across them. The quota cap rounds **down** to a whole core for `server` and `workers` (a fractional quota cannot keep a whole extra core busy; minimum 1), while the database figure comes from the JVM, which rounds **up** — under a fractional quota the two therefore differ by one, the one place the figures are not directly comparable. For `server` and `workers`, it is further capped by the process's own CPU-affinity mask (a `cpuset` restriction can pin fewer CPUs than any configured quota, or apply with no quota configured at all). Without a quota **and** without an affinity restriction, it is the whole host's count. **`processor_assigned`** is the configured limit itself, and may exceed `processor_available` when set above the host's count. For `server` and `workers` it is the container CPU quota, which the kernel enforces. For the database it is the cap on the Cypher parallel runtime's worker threads, which bounds that runtime but not Neo4j's total CPU use: Neo4j can still use more cores for other work, so it is the sized core budget rather than a hard ceiling.
- **`null`** means "not measured / not applicable / unbounded" — NOT zero. Treat `null` distinctly from `0`.
  - `processor_assigned = null` ⇒ either no enforced/configured CPU limit (unlimited), or the read failed/was unavailable. The two are indistinguishable from this field alone.
- **`database.system_info.processor_assigned` reports the Neo4j `server.cypher.parallel.worker_limit` setting**, and `null` where it is unset (its default `0` means auto, not a core count). The `infrahub-enterprise` chart presets set it to the preset's Neo4j CPU request — 4 (`small`), 8 (`medium`, `medium-data`) or 16 (`large`, `large-data`), infrahub-helm#93 — so an install from those presets reports its sized database cores today; the community chart and the compose file leave it unset. **`server.processor_assigned` and `workers.processor_assigned`** are live cgroup CPU-quota reads, so a deployment running with a container CPU limit reports a finite value. Every field self-populates with no payload-shape change as its limit becomes configured.
- **`workers.total` / `active`** count **task-worker (git_agent) processes only**, the same population as the `workers` resource figures. **`server.total` / `active`** count API server processes, one per gunicorn worker. Each block is self-describing; `workers.total + server.total` gives every worker process.
  - This narrows an existing field: before this change `workers.total`/`active` counted API server and task-worker processes together. A snapshot carrying a `server` block — which no earlier release emits — uses the new scoping, so a consumer continuing an all-workers series takes `workers.total + server.total` where `server` is present and `workers.total` where it is not.
  - Summing can fall short of the old figure in one narrow case: an exited process whose component-bearing keys have expired but whose generic presence key has not is counted in neither block. That lasts at most one schema-refresh interval (15 minutes) at the end of its two-hour tail, and never affects `active`.
- **Aggregates** (`workers.*`, `server.*`) are summed over **distinct hosts**, so multiple processes in one container are counted once. The per-process host identifier used for that dedup is internal and never emitted.
- **Undercount signal**: when a task-worker host fails to report, `processor_available`/`memory_total`/`memory_available` undercount by that host's share. The aggregate does not say how many hosts contributed to it, so the gap is not directly computable from one snapshot. The block's count and resources now describe the same population, so `workers.active` still includes the silent host's process, but nothing in the payload says which hosts the sum covers; an exact reporter count remains a candidate for the next gated `payload_format` bump, and until then an undercount shows as a drop against the same deployment's earlier snapshots.
- **`processor_assigned` never undercounts**: it is all-or-null across the fleet. A single contributing host reporting `null` — unbounded, or its quota read failed — makes the whole aggregate `null` rather than a partial sum, so a `null` here means "at least one host is unbounded or unknown", never "hosts are missing".

## Backward/forward compatibility

- No existing key renamed, removed or retyped, and the same `payload_format` (FR-008). One existing field narrows its meaning: `workers.total`/`active` now count task-worker processes only (see Field semantics for how to continue an all-workers series). This is the one deliberate exception to additive-only, recorded in research D15.
- Every new figure may be `null` in any snapshot; the consumer MUST accept `null` for all of them.
- The additions are present even when the deployment opted out of remote transmission — but then only in the locally stored snapshot, never transmitted.
