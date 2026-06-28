# Contract: Telemetry Payload (Phase 1 additions)

The contract is the **daily telemetry payload** Infrahub emits to the remote endpoint and
stores locally. This document defines the additive changes. The consumer (cloud processor +
data mart) is forward-compatible: it ignores unknown fields, so additive changes are safe.

## Envelope (unchanged shape, bumped version)

```jsonc
{
  "kind": "community",
  "payload_format": "20260628",   // BUMPED from "20250318"
  "data": { /* TelemetryData — see below */ },
  "checksum": "<sha256 of data>"
}
```

- `payload_format` advances to `"20260628"` (FR-007). Convention: `YYYYMMDD`.
- A consumer keying on `payload_format` must tolerate the new value (GR-001 confirmation gate).

## `data` additions

```jsonc
{
  // ... all existing fields unchanged ...

  "branches": {
    "total": 12,          // unchanged
    "active": 4           // NEW: open non-system branches; int | null
  },

  "accounts": {           // NEW object
    "active": 7,          // int | null
    "groups": 3           // int | null
  },

  "database": {
    // ...
    "node_count": {
      "total": 154233,    // unchanged: raw vertex total
      "corenode": 4821,   // NEW key: managed-node count; int | null
      // ... existing graph-label keys unchanged ...
    }
  },

  "activity_24h": {       // NEW object — trailing 24h window
    "logins": 19,                   // int | null
    "unique_logins": 6,             // int | null
    "webhooks_fired_success": 41,   // int | null
    "webhooks_fired_failure": 2     // int | null
  }
}
```

## Field semantics

| Path | Source | Window | Empty | Failure |
|------|--------|--------|-------|---------|
| `branches.active` | registry: `branch.values()` minus `is_default`/`is_global` | current | `0` | `null` |
| `accounts.active` | `NodeManager.count(CoreAccount, status=ACTIVE)` | current | `0` | `null` |
| `accounts.groups` | `NodeManager.count(CoreAccountGroup)` | current | `0` | `null` |
| `database.node_count.corenode` | `NodeManager.count(CoreNode)` | current | `0` | `null` |
| `activity_24h.logins` | Prefect `account.logged_in` events, windowed | trailing 24h | `0` | `null` |
| `activity_24h.unique_logins` | Prefect count-by-resource on login events, windowed | trailing 24h | `0` | `null` |
| `activity_24h.webhooks_fired_success` | Prefect `webhook-process` flow runs, `COMPLETED` | trailing 24h | `0` | `null` |
| `activity_24h.webhooks_fired_failure` | Prefect `webhook-process` flow runs, `FAILED`/`CRASHED`/`TIMEDOUT` | trailing 24h | `0` | `null` |

## Invariants the consumer can rely on

1. **Additive only.** No existing field changes name, type, or meaning. (`node_count` value
   type widens to allow `null` only on the new `corenode` key; existing keys stay `int`.)
2. **`null` means failure, `0` means empty.** A field is `null` iff its source raised during
   gathering; `0` iff the source succeeded with nothing to count. (FR-010, SC-001)
3. **Payload always ships.** One failing metric never drops the payload; the rest is gathered,
   stored, and sent. (SC-001)
4. **24h fields are exact to the window.** No leakage from retained-but-out-of-window records.
   (SC-002)
5. **`corenode` is branch/temporal-correct** and matches an independent fixture count exactly.
   (SC-003)

## Internal interface contracts (producer side)

These are the new/changed producer-side function contracts (full signatures land in `tasks.md`):

- `gather_account_information(db) -> TelemetryAccountData` — both fields via `NodeManager.count`,
  each degradable to `null`.
- `gather_database_information(db) -> TelemetryDatabaseData` — extended to set
  `node_count["corenode"]` via `NodeManager.count(CoreNode)`, degradable to `null`, without
  touching `node_count["total"]` or the graph-label keys.
- `gather_activity_24h(client) -> TelemetryActivity24hData` — windowed login count, windowed
  unique-login (count-by-resource) count, and `webhook-process` flow-run success/failure split,
  each field degradable to `null`.
- `gather_prefect_events(client)` — **UNCHANGED** (existing unwindowed tally; FR-007).
- A degradation helper in `tasks.py`: runs a metric coroutine, returns its value or `null` on
  exception (logged). Serves all new metrics.

## Governance (GR-001)

Before shipping: confirm the cloud processor and BigQuery/Metabase data mart (a) tolerate the
`payload_format` bump, (b) ignore unknown fields, and (c) tolerate `null` values on the new
fields — including a `null` on the `corenode` key inside `node_count`, the only place a
previously all-integer map can now carry a `null`. Additive design means a forward-compatible
consumer keeps working; this is a release gate, not a code dependency.
