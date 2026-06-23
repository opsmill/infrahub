# Contract: Health section of the anonymous telemetry payload

This is an **outbound** contract: the anonymous telemetry payload Infrahub POSTs to the OpsMill ingestion endpoint (`config.SETTINGS.main.telemetry_endpoint`) and stores locally in `TelemetrySnapshot.data`. It is not a REST/GraphQL API surface — the REST snapshot endpoints expose `data` as an opaque object, so the OpenAPI schema is unchanged.

## Envelope (unchanged except `payload_format`)

```json
{
  "kind": "community",
  "payload_format": "20260618",
  "data": { "...": "existing fields", "health": { } },
  "checksum": "<sha256 of data>"
}
```

- `payload_format` bumps `"20250318"` → `"20260618"` to flag the additive `data.health` field (FR-007).
- `checksum` is the sha256 of the serialized `data` object, computed after `health` is included (existing logic, no change needed).

## `data.health` object

| Field | Type | Notes |
|---|---|---|
| `status` | enum `healthy` \| `unhealthy` | Overall; `healthy` iff every check is `up`. |
| `timestamp` | RFC3339 datetime (UTC) | When the checks ran. |
| `checks` | array of objects (ordered) | One entry per dependency; see below. Order: `database`, `message_bus`, `cache`, `task_manager`, `task_manager_db`. |

### `checks[]` entry

| Field | Type | Notes |
|---|---|---|
| `name` | enum | `database` \| `message_bus` \| `cache` \| `task_manager` \| `task_manager_db` |
| `status` | enum | `up` \| `down` |
| `error` | enum | `none` \| `timeout` \| `connection_refused` \| `connection_closed` \| `not_initialized` \| `unknown_error`. `none` when `up`. |

## Guarantees

- **Presence (FR-001/002)**: A new-`payload_format` payload includes `data.health` whenever health gathering succeeds, with one entry per dependency the live `/api/health` endpoint checks.
- **Omission (FR-006 / clarification Q2)**: If health gathering fails entirely, `data.health` is absent / `null`. Consumers MUST treat absence in a new-`payload_format` payload as "not reported this cycle", not as healthy.
- **No internal details (FR-008 / SC-005)**: `error` is one of the fixed categories above. The payload never contains raw exception text, stack traces, hostnames, connection strings, or credentials.
- **Backward compatibility**: The field is purely additive. Consumers on the old `payload_format` ignore it; consumers MUST tolerate the field's presence keyed off `payload_format >= "20260618"`.

## Consumer coordination (release gate)

The OpsMill-side ingestion service is outside this repository. Before release, confirm with the telemetry-ingestion owners that the additive, version-flagged `data.health` field is accepted by their validator (spec Assumptions). The local-store path works regardless of the remote outcome.
