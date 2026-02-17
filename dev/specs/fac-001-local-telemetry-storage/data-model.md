# Data Model: Local Telemetry Storage

**Feature**: `fac-001-local-telemetry-storage` | **Date**: 2026-02-16

## Entities

### TelemetrySnapshot (StandardNode)

A single daily telemetry data capture persisted to the Neo4j database. Stored as a `StandardNode` subclass with `IS_PART_OF` relationship to the Root node.

**Location**: `backend/infrahub/telemetry/snapshot.py`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | auto | Neo4j element ID (inherited from StandardNode) |
| `uuid` | `UUID` | auto | Unique identifier (inherited from StandardNode, auto-generated) |
| `created_at` | `str` | auto | Collection timestamp in ISO format (inherited from StandardNode) |
| `created_by` | `str` | auto | Always `SYSTEM_USER_ID` (inherited from StandardNode) |
| `updated_at` | `str` | auto | Last update timestamp (inherited from StandardNode) |
| `updated_by` | `str` | auto | Last updater (inherited from StandardNode) |
| `kind` | `str` | yes | Telemetry kind identifier (e.g., `"community"`) |
| `payload_format` | `str` | yes | Format version string (e.g., `"20250318"`) |
| `deployment_id` | `str` | yes | Deployment identifier from `registry.id` |
| `infrahub_version` | `str` | yes | Product version at collection time |
| `data` | `TelemetryData` | yes | Full telemetry payload (Pydantic model, auto-serialized to JSON) |
| `checksum` | `str` | yes | SHA-256 hash of the JSON-serialized `data` field for integrity verification |
| `remote_send_status` | `str` | yes | Status of remote transmission: `"pending"`, `"sent"`, `"skipped"`, `"failed"` |

**Validation Rules**:
- `kind` must be a non-empty string
- `payload_format` must be a non-empty string
- `checksum` must be a 64-character hex string (SHA-256)
- `remote_send_status` must be one of: `"pending"`, `"sent"`, `"skipped"`, `"failed"`
- `data` must be a valid `TelemetryData` instance

**Neo4j Storage**:
```
(:TelemetrySnapshot {
    uuid: "...",
    created_at: "2026-02-16T02:15:00+00:00",
    kind: "community",
    payload_format: "20250318",
    deployment_id: "...",
    infrahub_version: "1.2.3",
    data: '{"deployment_id": ..., "infrahub_version": ...}',  // JSON string
    checksum: "abc123...",
    remote_send_status: "sent"
})-[:IS_PART_OF]->(:Root)
```

### TelemetryData (Existing — No Changes)

The existing telemetry payload model. Already defined in `backend/infrahub/telemetry/models.py`.

| Field | Type | Description |
|-------|------|-------------|
| `deployment_id` | `str \| None` | Deployment identifier |
| `execution_time` | `float \| None` | Collection time in seconds |
| `infrahub_version` | `str` | Product version |
| `infrahub_type` | `InfrahubType` | `"community"` or `"enterprise"` |
| `python_version` | `str` | Python version |
| `platform` | `str` | Platform architecture |
| `workers` | `TelemetryWorkerData` | Worker counts (total, active) |
| `branches` | `TelemetryBranchData` | Branch count |
| `features` | `dict[str, int]` | Feature usage counts |
| `schema_info` | `TelemetrySchemaData` | Schema statistics |
| `database` | `TelemetryDatabaseData` | Database statistics |
| `prefect` | `TelemetryPrefectData` | Task manager statistics |

## Relationships

```
TelemetrySnapshot --[IS_PART_OF]--> Root
```

This is the standard relationship for all `StandardNode` instances. It anchors the snapshot in the graph and ensures it is included in graph traversals and backups.

## Query Patterns

### Create Snapshot

Uses `StandardNodeCreateQuery` (inherited):
```cypher
MATCH (root:Root)
CREATE (n:TelemetrySnapshot $node_prop)-[r:IS_PART_OF]->(root)
RETURN n
```

### Get Snapshot by ID

Uses `StandardNodeGetItemQuery` (inherited):
```cypher
MATCH (n:TelemetrySnapshot)
WHERE elementId(n) = $node_id OR n.uuid = $node_id
RETURN n
```

### List Snapshots (with date-range filter)

Custom filter via `TelemetrySnapshotGetListQuery`:
```cypher
MATCH (n:TelemetrySnapshot)
WHERE n.created_at >= $start_date AND n.created_at <= $end_date
RETURN n
ORDER BY n.created_at DESC
LIMIT $limit
```

### List All Snapshots (no filter)

Uses `StandardNodeGetListQuery` (inherited):
```cypher
MATCH (n:TelemetrySnapshot)
RETURN n
ORDER BY n.created_at DESC
```

## State Transitions

```
remote_send_status flow:

  [snapshot created] --> "pending"
          |
          v
    (opt-out check)
     /           \
  opted-out     opted-in
     |              |
     v              v
  "skipped"    (POST to endpoint)
                /          \
           success       failure
              |              |
              v              v
           "sent"        "failed"
```

## Data Volume Estimates

| Metric | Value |
|--------|-------|
| Snapshot size (JSON) | ~3-5 KB |
| Snapshots per year | 365 |
| 5-year storage | ~5.5-9.1 MB |
| Neo4j overhead (~2x) | ~11-18 MB |
| Well under 50 MB limit | Yes |
