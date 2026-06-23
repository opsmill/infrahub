# Quickstart: Health-Status Telemetry

How to exercise and verify the feature locally.

## Run the tests

```bash
# Shared core + endpoint (behavior unchanged)
uv run pytest backend/tests/unit/health/test_health.py -q

# Telemetry health gather: shape + failure path
uv run pytest backend/tests/unit/telemetry/ -q
```

## Inspect the payload a deployment would send

The telemetry gather runs as the Prefect flow `anonymous_telemetry_send`. To see the gathered data without sending it, call the gather task directly against a running stack:

```python
# python shell inside the backend env (stack up: db, cache, broker, task-manager)
from infrahub.telemetry.tasks import gather_anonymous_telemetry_data

data = await gather_anonymous_telemetry_data.fn()
print(data.model_dump(mode="json")["health"])
```

Expected (all reachable):

```json
{"status": "healthy", "timestamp": "...", "checks": [
  {"name": "database", "status": "up", "error": "none"},
  {"name": "message_bus", "status": "up", "error": "none"},
  {"name": "cache", "status": "up", "error": "none"},
  {"name": "task_manager", "status": "up", "error": "none"},
  {"name": "task_manager_db", "status": "up", "error": "none"}
]}
```

## Verify degradation is captured

Stop one dependency (e.g. the cache container) and re-run the gather. That dependency should report `status: "down"` with a categorized `error`, and overall `status: "unhealthy"` — while every other field of the payload is still populated.

## Verify telemetry never breaks on health failure

In a unit test, patch the health gather to raise; assert that `gather_anonymous_telemetry_data` still returns a `TelemetryData` with `health is None` and all other fields populated, and that `send_telemetry_push` still stores/sends the snapshot.

## Confirm no generated files drift

```bash
uv run invoke docs.validate     # generated-doc validation
uv run invoke backend.generate  # then `git diff --exit-code` should be clean
```

## Pre-push

```bash
/pre-ci    # format, lint (ruff + mypy), unit tests, generated-file/doc validation
```

Remember the changelog fragment: `changelog/+health-telemetry.added.md`.
