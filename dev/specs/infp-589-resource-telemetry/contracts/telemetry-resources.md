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
        "processor_available": 32,           // existing — DB cores available (logical)
        "processor_assigned": null,          // NEW — worker_limit; null today
        "memory_total": 67435982848,         // existing — bytes
        "memory_available": 47034888192      // existing — free bytes
      }
    },
    "workers": {
      "total": 2,                            // existing — all worker processes
      "active": 2,                           // existing
      "processor_available": 8,              // NEW — git_agent fleet, sum over hosts
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
- **`null`** means "not measured / not applicable / unbounded" — NOT zero. Treat `null` distinctly from `0`.
  - `processor_assigned = null` ⇒ no enforced/configured CPU limit (unlimited).
- **All `processor_assigned` fields are `null` in this release** — Infrahub does not enforce core limits yet. They are live reads that self-populate once a limit is configured: the DB reads `server.cypher.parallel.worker_limit` (`0`/auto → `null`); server and workers read their container CPU quota (unlimited → `null`). No payload-shape change when they light up.
- **`workers.total` / `active`** keep their existing meaning: all worker processes (api_server + git_agent). The new `workers.processor_*` / `memory_*` are the **git_agent (task-worker) fleet** aggregate; api_server resources are in the `server` block. So `workers.total` and the `workers` resource fields are scoped differently by design.
- **Aggregates** (`workers.*`, `server.*`) are summed over **distinct hosts**, so multiple processes in one container are counted once. The per-process host identifier used for that dedup is internal and never emitted.
- **Undercount signal**: if fewer hosts contributed than there are active workers, the git_agent resource fields undercount; `workers.total`/`active` (unchanged) expose the discrepancy.

## Backward/forward compatibility

- Additive only: no existing key renamed or removed (FR-008, SC-005). Same `payload_format`.
- Every new figure may be `null` in any snapshot; the consumer MUST accept `null` for all of them.
- The additions are present even when the deployment opted out of remote transmission — but then only in the locally stored snapshot, never transmitted.
