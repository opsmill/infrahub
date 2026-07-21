# Contract: `resources` block in the telemetry payload

**Consumer**: the telemetry-receiving cloud processor + data mart (cross-team).
**Producer**: Infrahub `send_telemetry_push` flow.
**Change type**: additive. `payload_format` is bumped from `20260628` to the release date.

The receiving service MUST tolerate this before deployments on the new release start transmitting. Existing fields are unchanged; a consumer pinned to the old shape can ignore `resources` without breaking.

## Location

`resources` is a new top-level key inside `data` (sibling of `workers`, `branches`, `database`, `activity_24h`, …).

## Shape

```jsonc
{
  "payload_format": "<release-date>",        // bumped
  "data": {
    // ... all existing fields, unchanged ...
    "resources": {
      "database": {
        "cores_available": 32,               // logical CPUs, int | null
        "cores_assigned": null,              // null today (see note)
        "ram_available": 67435982848,        // bytes, int | null
        "ram_used": 20401094656              // bytes, int | null
      },
      "server": {
        "cores_available": 8,
        "cores_assigned": 4,                 // cgroup quota; null if unlimited
        "ram_available": 8589934592,
        "ram_used": 3221225472
      },
      "workers": {
        "count": 2,                          // active worker processes, int (never null)
        "cores_available": 8,                // fleet aggregate over distinct hosts
        "cores_assigned": 4,
        "ram_available": 8589934592,
        "ram_used": 2147483648
      }
    }
  }
}
```

## Field semantics

- **Units**: cores are logical CPUs (vCPUs); memory is bytes. Consistent across all three components and with the existing `database.system_info` fields.
- **`null`** on any figure means "not measured / not applicable / unbounded" — NOT zero. A consumer MUST treat `null` distinctly from `0`.
  - `cores_assigned = null` ⇒ no enforced/configured CPU limit (unlimited).
  - a `0` core/byte figure ⇒ genuinely measured as empty (e.g. `workers.count = 0`).
- **All `cores_assigned` fields are `null` in this release** because Infrahub does not enforce core limits yet. They are live reads that self-populate once a limit is configured: the database reads the Neo4j `server.cypher.parallel.worker_limit` setting (`0`/auto → `null` today); server and workers read their container CPU quota (unlimited → `null`). A consumer should expect `null` here today and real integers once enforcement ships — no payload-shape change at that point.
- **`workers.count`** is the number of active worker processes and is always an integer. It MAY exceed the number of hosts that contributed to the aggregate (undercount signal): if `count` > contributing hosts, some workers did not report resources this cycle.
- **Aggregates** (`server`, `workers`) are summed over **distinct hosts**, so multiple processes in one container are counted once.

## Backward/forward compatibility

- Additive only: no existing key renamed or removed (FR-008, SC-005).
- A field may be `null` in any snapshot; the consumer MUST accept `null` for every figure except `workers.count`.
- The block is present even when the deployment opted out of remote transmission — but in that case it is only in the locally stored snapshot and never reaches the consumer.
