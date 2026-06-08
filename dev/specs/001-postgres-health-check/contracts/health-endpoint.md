# Contract: `GET /api/health` — `task_manager_db` dependency

This feature does not add or change any endpoint, status code, or top-level response shape. It adds one member to the reported dependency set. The endpoint contract is otherwise unchanged from the current PR.

## Endpoint (unchanged)

- **Method/Path**: `GET /api/health`
- **Auth**: none
- **`200`**: overall status `healthy` (all dependencies `up`)
- **`503`**: overall status `unhealthy` (any dependency `down`)
- **Body**: `HealthResponse` (`status`, `checks[]`, `timestamp`)

## Contract change

`components.schemas.DependencyName` gains the value `task_manager_db`. The `checks` array now contains **5** entries; `task_manager_db` is always present.

### Example — healthy (HTTP 200)

```json
{
  "status": "healthy",
  "checks": [
    { "name": "database",        "status": "up", "error": "none" },
    { "name": "message_bus",     "status": "up", "error": "none" },
    { "name": "cache",           "status": "up", "error": "none" },
    { "name": "task_manager",    "status": "up", "error": "none" },
    { "name": "task_manager_db", "status": "up", "error": "none" }
  ],
  "timestamp": "2026-06-08T12:00:00Z"
}
```

### Example — backing store down (HTTP 503)

Backing store unreachable; the Prefect application also degrades. `task_manager_db` names the root cause.

```json
{
  "status": "unhealthy",
  "checks": [
    { "name": "database",        "status": "up",   "error": "none" },
    { "name": "message_bus",     "status": "up",   "error": "none" },
    { "name": "cache",           "status": "up",   "error": "none" },
    { "name": "task_manager",    "status": "down", "error": "timeout" },
    { "name": "task_manager_db", "status": "down", "error": "connection_refused" }
  ],
  "timestamp": "2026-06-08T12:00:00Z"
}
```

### Example — URL not configured for the API server (HTTP 503)

```json
{
  "status": "unhealthy",
  "checks": [
    { "name": "database",        "status": "up",   "error": "none" },
    { "name": "message_bus",     "status": "up",   "error": "none" },
    { "name": "cache",           "status": "up",   "error": "none" },
    { "name": "task_manager",    "status": "up",   "error": "none" },
    { "name": "task_manager_db", "status": "down", "error": "not_initialized" }
  ],
  "timestamp": "2026-06-08T12:00:00Z"
}
```

## Contract tests (must exist before/with implementation)

- `task_manager_db` is present on every response (unit: `HealthChecker.report()` returns 5 checks).
- Reachable probe → `up`/`none`; unreachable → `down` with classified error; unresolvable URL → `down`/`not_initialized`.
- A `down` `task_manager_db` yields overall `unhealthy` → HTTP `503`.
- No connection string, credentials, host, port, or database name appears in the serialized body (extend the existing no-internal-details assertions with backing-store-specific tokens).
- Generated artifacts (`schema/openapi.json`, frontend REST types) include `task_manager_db` and are regenerated, not hand-edited.
