# REST API Contract: Telemetry Snapshots

**Feature**: `fac-001-local-telemetry-storage` | **Date**: 2026-02-16

## Endpoint: List/Export Telemetry Snapshots

### `GET /api/telemetry/snapshots`

Retrieves stored telemetry snapshots with optional date-range filtering. Requires `READ_TELEMETRY` global permission.

**Authentication**: Required (JWT or API key)
**Permission**: `READ_TELEMETRY` global permission

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | `string` (ISO 8601) | No | None | Include snapshots created on or after this date |
| `end_date` | `string` (ISO 8601) | No | None | Include snapshots created on or before this date |
| `limit` | `integer` | No | 1000 | Maximum number of snapshots to return |
| `offset` | `integer` | No | 0 | Number of snapshots to skip |

#### Response: `200 OK`

```json
{
  "count": 90,
  "snapshots": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2026-02-16T02:15:00+00:00",
      "kind": "community",
      "payload_format": "20250318",
      "deployment_id": "dep-abc123",
      "infrahub_version": "1.2.3",
      "data": {
        "deployment_id": "dep-abc123",
        "execution_time": 12.5,
        "infrahub_version": "1.2.3",
        "infrahub_type": "community",
        "python_version": "3.12.0",
        "platform": "x86_64",
        "workers": {"total": 4, "active": 3},
        "branches": {"total": 5},
        "features": {"CoreArtifact": 10, "CoreRepository": 2},
        "schema_info": {"node_count": 45, "generic_count": 12, "last_update": "2026-02-15T10:00:00"},
        "database": {
          "database_type": "neo4j-enterprise",
          "relationship_count": {"total": 50000},
          "node_count": {"total": 10000},
          "servers": [{"name": "core1", "version": "5.28.0"}],
          "system_info": {"memory_total": 8589934592, "memory_available": 4294967296, "processor_available": 8}
        },
        "prefect": {"events": {}, "automations": {}, "work_pools": []}
      },
      "checksum": "a1b2c3d4e5f6...",
      "remote_send_status": "sent"
    }
  ]
}
```

#### Response Model (Pydantic)

```python
class TelemetrySnapshotResponse(BaseModel):
    id: str                          # UUID
    created_at: str                  # ISO 8601 timestamp
    kind: str                        # Telemetry kind identifier
    payload_format: str              # Format version
    deployment_id: str               # Deployment identifier
    infrahub_version: str            # Product version
    data: dict[str, Any]             # Full telemetry payload
    checksum: str                    # SHA-256 integrity hash
    remote_send_status: str          # "sent" | "skipped" | "failed" | "pending"

class TelemetrySnapshotListResponse(BaseModel):
    count: int                       # Total matching snapshots
    snapshots: list[TelemetrySnapshotResponse]
```

#### Error Responses

| Status | Condition | Body |
|--------|-----------|------|
| `401 Unauthorized` | Missing or invalid authentication | `{"data": null, "errors": [{"message": "...", "extensions": {"code": 401}}]}` |
| `403 Forbidden` | User lacks `READ_TELEMETRY` permission | `{"data": null, "errors": [{"message": "You are not allowed to read telemetry data", "extensions": {"code": 403}}]}` |
| `422 Unprocessable Entity` | Invalid date format in query parameters | `{"data": null, "errors": [{"message": "...", "extensions": {"code": 422}}]}` |

#### Example Requests

```bash
# Get all snapshots
curl -H "Authorization: Bearer $TOKEN" \
  https://infrahub.example.com/api/telemetry/snapshots

# Get snapshots from last 90 days
curl -H "Authorization: Bearer $TOKEN" \
  "https://infrahub.example.com/api/telemetry/snapshots?start_date=2025-11-18T00:00:00Z&end_date=2026-02-16T23:59:59Z"

# Paginate results
curl -H "Authorization: Bearer $TOKEN" \
  "https://infrahub.example.com/api/telemetry/snapshots?limit=50&offset=100"
```

## CLI Commands (infrahubctl)

These commands consume the REST API endpoint above.

### `infrahubctl telemetry export`

Export telemetry snapshots to a JSON file.

```
infrahubctl telemetry export [OPTIONS]

Options:
  --output PATH          Output file path [default: telemetry-export.json]
  --start-date TEXT      Start date filter (ISO 8601, e.g. 2025-01-01)
  --end-date TEXT        End date filter (ISO 8601, e.g. 2026-02-16)
  --branch TEXT          Branch context (not used for filtering, required by SDK)
  --config-file TEXT     Path to infrahubctl config file

Output: JSON file containing array of snapshot objects
Exit codes: 0 (success), 1 (error), 2 (no data found)
```

**Example output file**:
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2026-02-16T02:15:00+00:00",
    "kind": "community",
    "payload_format": "20250318",
    "deployment_id": "dep-abc123",
    "infrahub_version": "1.2.3",
    "data": { ... },
    "checksum": "a1b2c3d4e5f6...",
    "remote_send_status": "sent"
  }
]
```

### `infrahubctl telemetry list`

List telemetry snapshots with summary information.

```
infrahubctl telemetry list [OPTIONS]

Options:
  --start-date TEXT      Start date filter (ISO 8601)
  --end-date TEXT        End date filter (ISO 8601)
  --limit INTEGER        Maximum number of results [default: 50]
  --branch TEXT          Branch context
  --config-file TEXT     Path to infrahubctl config file

Output: Rich table with columns: Date, Version, Type, Deployment ID, Remote Status
```

**Example output**:
```
┌──────────────────────────┬─────────┬───────────┬──────────────┬───────────────┐
│ Date                     │ Version │ Type      │ Deployment   │ Remote Status │
├──────────────────────────┼─────────┼───────────┼──────────────┼───────────────┤
│ 2026-02-16 02:15:00 UTC  │ 1.2.3   │ community │ dep-abc123   │ sent          │
│ 2026-02-15 02:12:00 UTC  │ 1.2.3   │ community │ dep-abc123   │ sent          │
│ 2026-02-14 02:18:00 UTC  │ 1.2.2   │ community │ dep-abc123   │ skipped       │
└──────────────────────────┴─────────┴───────────┴──────────────┴───────────────┘
Showing 3 of 90 total snapshots
```
