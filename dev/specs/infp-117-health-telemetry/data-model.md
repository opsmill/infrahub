# Phase 1 Data Model: Health-Status Telemetry

## Reused value types (from `backend/infrahub/health.py`, unchanged)

- `DependencyName` (StrEnum): `database`, `message_bus`, `cache`, `task_manager`, `task_manager_db`
- `DependencyStatus` (StrEnum): `up`, `down`
- `ErrorCategory` (StrEnum): `none`, `timeout`, `connection_refused`, `connection_closed`, `not_initialized`, `unknown_error`
- `OverallStatus` (StrEnum): `healthy`, `unhealthy`
- `DependencyHealth` (BaseModel): `name: DependencyName`, `status: DependencyStatus`, `error: ErrorCategory = NONE`

These are the single source of truth for the dependency set and status semantics (FR-004) and are shared with `/api/health`.

## New model (`backend/infrahub/telemetry/models.py`)

```python
class TelemetryHealthData(BaseModel):
    status: OverallStatus
    checks: list[DependencyHealth]
    timestamp: datetime
```

- **Fields**:
  - `status` — overall health computed by `DefaultHealthStatusEvaluator` (HEALTHY only when every dependency is UP).
  - `checks` — ordered list of per-dependency records (D2 / clarification Q1). Order matches the shared core: database, message_bus, cache, task_manager, task_manager_db.
  - `timestamp` — when the checks ran (UTC), distinct from the surrounding telemetry `execution_time`.
- **Validation**: structural only (enums constrain values). No free-form strings (FR-008 / SC-005): `error` is an `ErrorCategory`, never raw exception text.
- **Reuse note**: `TelemetryHealthData` mirrors `HealthResponse` but is owned by the telemetry payload contract so the two can be versioned independently. It reuses `DependencyHealth`/`OverallStatus` rather than redefining them.

## Modified model (`TelemetryData`, same file)

Add one optional field (additive; default `None` keeps existing `TelemetryData(...)` construction and `test_snapshot.py` valid — SC-006):

```python
class TelemetryData(BaseModel):
    ...                                  # existing fields unchanged
    health: TelemetryHealthData | None = None
```

- **State / lifecycle**: point-in-time only. No persistence beyond the existing `TelemetrySnapshot.data` dict. No aggregation (FR-010).
- **Absence semantics** (D3 / clarification Q2): `health = None` ⇒ omitted from the JSON payload (or serialized as `null`); in a new-`payload_format` payload this means "health not reported this cycle" (gather failed). It is **not** the same as "all healthy".

## Serialized example (within the telemetry `data` object)

```json
"health": {
  "status": "unhealthy",
  "timestamp": "2026-06-18T09:15:04.512Z",
  "checks": [
    {"name": "database",        "status": "up",   "error": "none"},
    {"name": "message_bus",     "status": "up",   "error": "none"},
    {"name": "cache",           "status": "down", "error": "timeout"},
    {"name": "task_manager",    "status": "up",   "error": "none"},
    {"name": "task_manager_db", "status": "up",   "error": "none"}
  ]
}
```

## Payload version (`backend/infrahub/telemetry/constants.py`)

- `TELEMETRY_VERSION`: `"20250318"` → `"20260618"` (D5 / FR-007). Flows through to both `TelemetrySnapshot.payload_format` and the outbound POST body's `payload_format`.
- `TELEMETRY_KIND` unchanged (`"community"`).
