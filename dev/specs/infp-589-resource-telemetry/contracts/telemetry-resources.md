# Contract: resource fields in the telemetry payload

**Consumer**: the telemetry-receiving cloud processor + data mart (cross-team).
**Producer**: Infrahub `send_telemetry_push` flow.
**Change type**: **additive, in place** — no new top-level `resources` block. DB resources extend `database.system_info`, worker resources extend `workers`, and a single new `server` block is added for the api_server. No existing field is renamed, removed, or retyped.

**Naming**: every component uses the **same field names as the existing `system_info`** — `processor_available`, `processor_assigned`, `memory_total`, `memory_available` — so DB, server, and worker figures are directly comparable. Memory usage is derived as `memory_total − memory_available` (the representation the DB already uses; there is no `*_used` field).

**Version**: `payload_format` is **not** incremented this phase; the new fields ship additively under the existing version (`20260628`). The bump is a gated follow-up once the receiving service confirms tolerance (research D13). A consumer pinned to the old shape keeps working.

## Shape (only the additions shown; everything else unchanged)

```jsonc
{
  "payload_format": "20260628",              // UNCHANGED this phase
  "data": {
    "database": {
      // ... existing database fields ...
      "system_info": {
        "processor_available": 32,           // existing — CPUs the DB can use (JVM, quota-aware)
        "processor_assigned": null,          // NEW — worker_limit; null today
        "memory_total": 67435982848,         // existing — bytes
        "memory_available": 47034888192      // existing — free bytes
      }
    },
    "workers": {
      "total": 2,                            // existing — ALL workers (api_server + git_agent); do not divide processor_* by this
      "active": 2,                           // existing — same scope as total
      "processor_available": 8,              // NEW — usable CPUs, git_agent fleet ONLY, sum over hosts
      "processor_assigned": null,            // NEW — cgroup quota; null if unbounded
      "memory_total": 8589934592,            // NEW — bytes
      "memory_available": 6442450944         // NEW — free bytes
    },
    "server": {                              // NEW block (api_server)
      "processor_available": 8,
      "processor_assigned": null,
      "memory_total": 8589934592,
      "memory_available": 5368709120
    }
    // ... all other existing fields unchanged ...
  }
}
```

## Field semantics

- **Units**: `processor_*` are logical CPUs (vCPUs); `memory_*` are bytes. **Usage** = `memory_total − memory_available`, uniformly across all three components.
- **`processor_available`** is the logical CPUs the component can actually use: the host's count capped by any enforced CPU quota — the JVM's rule for the database figure, applied to server and workers too — so the figure is comparable across components. For `server` and `workers`, it is further capped by the process's own CPU-affinity mask (a `cpuset` restriction can pin fewer CPUs than any configured quota, or apply with no quota configured at all). Without a quota **and** without an affinity restriction, it is the whole host's count. **`processor_assigned`** is the enforced quota itself and may exceed `processor_available` when set above the host's count.
- **`null`** means "not measured / not applicable / unbounded" — NOT zero. Treat `null` distinctly from `0`.
  - `processor_assigned = null` ⇒ either no enforced/configured CPU limit (unlimited), or the read failed/was unavailable. The two are indistinguishable from this field alone.
- **`database.system_info.processor_assigned` is `null` in this release** — Infrahub does not configure the Neo4j `server.cypher.parallel.worker_limit` setting itself, so the DB always reads its default (`0`/auto → `null`) until per-tier enforcement (a later phase) sets it. **`server.processor_assigned` and `workers.processor_assigned` are not gated on anything** — they are live cgroup CPU-quota reads, so a deployment already running with a configured container CPU limit reports a finite value today, before any enforcement work lands. All three fields self-populate with no payload-shape change as their respective limits become configured.
- **`workers.total` / `active`** keep their existing meaning: all worker processes (api_server + git_agent). The new `workers.processor_*` / `memory_*` are the **git_agent (task-worker) fleet** aggregate; api_server resources are in the `server` block. So `workers.total` and the `workers` resource fields are scoped differently by design.
  - **Do not** compute `workers.processor_available / workers.total` as a per-worker average — `total` counts api_server + git_agent, `processor_available` covers git_agent only, so the result mixes two different fleets. A per-block host/worker count, so each block is self-describing, is a candidate for the next gated `payload_format` bump (research D13); not added this phase.
- **Aggregates** (`workers.*`, `server.*`) are summed over **distinct hosts**, so multiple processes in one container are counted once. The per-process host identifier used for that dedup is internal and never emitted.
- **Undercount signal**: if fewer hosts contributed than there are active workers, the git_agent resource fields undercount; `workers.total`/`active` (unchanged) expose the discrepancy.

## Backward/forward compatibility

- Additive only: no existing key renamed or removed (FR-008, SC-005). Same `payload_format`.
- Every new figure may be `null` in any snapshot; the consumer MUST accept `null` for all of them.
- The additions are present even when the deployment opted out of remote transmission — but then only in the locally stored snapshot, never transmitted.
