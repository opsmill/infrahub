# Research: Local Telemetry Storage

**Feature**: `fac-001-local-telemetry-storage` | **Date**: 2026-02-16

## Research Tasks & Findings

### R-001: Storage Model — StandardNode vs Schema-Governed Node

**Decision**: Use `StandardNode` subclass for `TelemetrySnapshot`

**Rationale**:
- Telemetry snapshots are operational/system data, not user-managed infrastructure data. They do not belong in the schema layer.
- `StandardNode` is the established pattern for system-level entities: `Branch` (`backend/infrahub/core/branch/models.py`) and `Root` (`backend/infrahub/core/root.py`) both use it.
- `StandardNode` provides built-in CRUD operations (`save`, `create`, `update`, `delete`, `get`, `get_list`), Neo4j persistence via `StandardNodeCreateQuery` (which creates an `IS_PART_OF` relationship to Root), and automatic UUID generation.
- `StandardNode` supports complex field types including dicts, Pydantic models, and lists of Pydantic models — confirmed by test fixtures in `backend/tests/component/core/test_node_standard.py`.
- Data stored as `StandardNode` in Neo4j is automatically included in database backups (neo4j-admin backup captures all nodes), satisfying FR-007.

**Alternatives considered**:
- **Schema-governed Node (NodeSchema)**: Too heavy — requires schema registration, branch support, attribute/relationship edges, and schema migration. Telemetry data is not user-modifiable infrastructure data. Adds unnecessary complexity.
- **Separate PostgreSQL table**: Would break the single-database backup guarantee (FR-007) and add a dependency on the Prefect PostgreSQL instance for non-task data.
- **File-based storage**: Violates FR-008 (container compatibility — no persistent local directories). Also excluded from database backups.

---

### R-002: Workflow Modification — Always-Store Pattern

**Decision**: Restructure `send_telemetry_push` to always gather and store data locally, then conditionally send remotely.

**Rationale**:
- The current workflow (`backend/infrahub/telemetry/tasks.py:96-117`) returns early when `telemetry_optout` is True. The fix is to move the opt-out check to only gate the remote POST, not the data gathering and local storage.
- The `gather_anonymous_telemetry_data()` function already collects the full payload as a `TelemetryData` Pydantic model — no changes needed to data collection.
- The `checksum` and `kind`/`payload_format` fields are currently constructed only in the flow function. These should be computed and stored on the `TelemetrySnapshot` node.
- Local storage failure should be logged but should not prevent remote sending (if enabled). Conversely, remote sending failure should not affect local storage. These are independent operations.

**Alternatives considered**:
- **Separate workflow for local storage**: Creates two workflows for the same data. YAGNI — a single workflow with conditional branching is simpler and ensures data consistency.
- **Pre-send hook**: No hook mechanism exists in the Prefect workflow. Would require new infrastructure.

---

### R-003: Telemetry Payload Serialization

**Decision**: Store the `TelemetryData` payload as a JSON string in a single `data` field on the `TelemetrySnapshot` StandardNode.

**Rationale**:
- `StandardNode.to_db()` automatically serializes Pydantic models to JSON via `model_dump_json()` and deserializes them in `from_db()` via `ujson.loads()`. This is proven by existing test fixtures (`PadanticStdNode` in test_node_standard.py).
- The telemetry payload is ~3-5 KB of JSON. Storing as a single JSON string avoids fragmenting it across multiple Neo4j nodes/relationships.
- The `TelemetryData` model is already well-typed with nested Pydantic models (`TelemetryWorkerData`, `TelemetryBranchData`, `TelemetrySchemaData`, `TelemetryDatabaseData`, `TelemetryPrefectData`).
- Using the existing model type in the StandardNode field enables automatic Pydantic validation on read.

**Alternatives considered**:
- **Separate Neo4j properties per telemetry field**: Would create dozens of properties on the node. Hard to evolve when the telemetry schema changes. Querying individual fields is not a requirement.
- **Binary/compressed storage**: Over-engineering. 5 years of data is ~6-9 MB uncompressed. Compression adds complexity without meaningful benefit.

---

### R-004: Permission Model — telemetry:read

**Decision**: Add `READ_TELEMETRY` to the `GlobalPermissions` enum.

**Rationale**:
- The spec requires a "telemetry:read" permission (FR-010). This maps to a global permission because telemetry data is system-wide, not scoped to a specific object kind or branch.
- `GlobalPermissions` enum (`backend/infrahub/core/constants/__init__.py:100-111`) already contains similar admin-level permissions (`MANAGE_SCHEMA`, `MANAGE_ACCOUNTS`, etc.).
- The permission check follows the established pattern: `permission_manager.raise_for_permission(GlobalPermission(action=GlobalPermissions.READ_TELEMETRY.value, decision=PermissionDecisionFlag.ALLOW_ALL))`.
- Super admins (`SUPER_ADMIN` permission) automatically bypass all permission checks, so they will have access by default.

**Alternatives considered**:
- **ObjectPermission on a "Telemetry" kind**: Object permissions are for schema-governed nodes. TelemetrySnapshot is a StandardNode, not a schema kind. Using ObjectPermission would be semantically incorrect.
- **No permission (admin-only)**: The spec explicitly requires a permission that can be assigned to any role (FR-010). Hard-coding to admin violates this.

---

### R-005: CLI Framework — infrahubctl telemetry

**Decision**: Add `telemetry` sub-command group to `infrahubctl` with `export` and `list` commands.

**Rationale**:
- The spec explicitly states "Use infrahubctl" (Dependencies section).
- The infrahubctl CLI uses `AsyncTyper` (`python_sdk/infrahub_sdk/async_typer.py`) with sub-command apps registered via `app.add_typer()` in `python_sdk/infrahub_sdk/ctl/cli_commands.py:63-70`.
- The pattern is well-established: create a new module (`telemetry.py`), create an `AsyncTyper` app, define commands, register in `cli_commands.py`.
- Commands will use `initialize_client()` for authenticated API access and Rich for formatted output (tables for `list`, file writing for `export`).
- The CLI will call the REST API endpoint (FR-009) rather than directly accessing the database, ensuring permission checks are enforced and the CLI works remotely.

**Alternatives considered**:
- **Backend CLI (infrahub command)**: The `infrahub` CLI is for server-side operations (start server, manage DB). Telemetry export is a client-side administrative operation.
- **Direct database access from CLI**: Would bypass permission checks and require database credentials. The SDK client pattern already handles authentication.

---

### R-006: REST API Design — Programmatic Interface

**Decision**: Add a REST API endpoint at `/api/telemetry/snapshots` for retrieving stored telemetry data.

**Rationale**:
- FR-009 requires "a programmatic interface for retrieving stored telemetry data, enabling integration with future tech support bundle tools."
- REST (not GraphQL) is appropriate because this is system/operational data, not user-schema data. The existing system info endpoints (`/api/config`, `/api/info`) use REST.
- The endpoint follows the established FastAPI router pattern (`backend/infrahub/api/`), using dependency injection for auth (`get_current_user`) and permissions (`get_permission_manager`).
- Supports optional `start_date` and `end_date` query parameters for date-range filtering.
- Returns JSON array of snapshot objects, consistent with the CLI export format.

**Alternatives considered**:
- **GraphQL query**: GraphQL is used for schema-governed data. System/operational queries use REST in Infrahub. Adding a GraphQL query for non-schema data would be inconsistent.
- **No API (CLI only)**: Would block future tech support bundle integration (FR-009 explicitly requires programmatic access).

---

### R-007: Date-Range Filtering for StandardNode

**Decision**: Extend `StandardNodeGetListQuery` with a custom subclass that supports `created_at` range filtering.

**Rationale**:
- `StandardNodeGetListQuery` (`backend/infrahub/core/query/standard_node.py:133-193`) supports filtering by `ids` and `name`, plus arbitrary ordering by `created_at`.
- For date-range filtering, a subclass `TelemetrySnapshotGetListQuery` will add `raw_filter` or custom `WHERE` clauses for `n.created_at >= $start_date AND n.created_at <= $end_date`.
- The `StandardNodeGetListQuery` already has a `raw_filter` attribute that can be set for additional filtering criteria — this is the cleanest extension point.
- The `created_at` field on StandardNode is a Timestamp string (ISO format), which supports lexicographic comparison in Cypher.

**Alternatives considered**:
- **Separate dedicated query class**: Over-engineering. The raw_filter mechanism on `StandardNodeGetListQuery` already supports this.
- **Post-query filtering in Python**: Inefficient for large datasets. Database-level filtering is both more efficient and correct.

---

### R-008: Remote Send Status Tracking

**Decision**: Store `remote_send_status` as a string field on `TelemetrySnapshot` with values: `"sent"`, `"skipped"` (opted out), `"failed"`, `"pending"`.

**Rationale**:
- FR-004 requires recording whether each snapshot was successfully sent to the remote endpoint.
- The workflow first stores the snapshot with `remote_send_status="pending"`, then updates to `"sent"` or `"failed"` after the remote POST, or `"skipped"` if opted out.
- Using a string field (not an enum) keeps it simple and avoids adding a new enum for a single field.
- `StandardNode.update()` is available to update the status after the remote send attempt.

**Alternatives considered**:
- **Boolean `was_sent` field**: Too simplistic — doesn't distinguish between "not attempted" (opted out) and "attempted but failed". The spec implies this distinction matters for support workflows.
- **Separate relationship to a "SendAttempt" node**: Over-engineering for a single status field.

---

### R-009: Backup Inclusion Verification

**Decision**: No additional work needed — Neo4j backup automatically includes all StandardNode data.

**Rationale**:
- The Infrahub backup system (`docs/guides/database-backup.mdx`) uses `neo4j-admin database backup` which captures all data in the Neo4j database.
- `StandardNode` instances are stored as Neo4j nodes with `IS_PART_OF` relationship to Root. They are regular graph data.
- Restoration via `neo4j-admin database restore` restores all nodes and relationships.
- This satisfies FR-007 without any additional configuration or code.

**Alternatives considered**: None — this is the only viable approach given the architecture.
