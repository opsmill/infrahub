# Contract: Retention configuration

Section `task_manager.retention` of `infrahub.toml`, or the matching environment variables.

```toml
[task_manager.retention]
task_history = "30d"
activity_log = "7d"
prefect_own_events = "7d"
```

| Key | Environment variable | Default |
|---|---|---|
| `task_history` | `INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY` | `30d` |
| `activity_log` | `INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG` | `7d` |
| `prefect_own_events` | `INFRAHUB_TASK_MANAGER_RETENTION_PREFECT_OWN_EVENTS` | `7d` |

- Values accept a number of days (`30d`) or an ISO 8601 duration (`P30D`); the configuration reference shows the day form.
- Every value must be at least 1 day, or the process refuses to start. A `prefect_own_events` longer than `activity_log` is capped to `activity_log` with a warning, because Prefect deletes every event older than the activity log retention anyway.
- Invalid values stop the task manager and the background-services command with: `Invalid task manager retention: <key> <reason>`.
- A Prefect variable already set in the environment (`PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED`, `PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD`, `PREFECT_SERVER_EVENTS_RETENTION_PERIOD`, `PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES`) takes precedence; the task manager logs `PREFECT_<NAME> is set and overrides task_manager.retention.<key>` for each one.
- The values are read by the task manager, the background-services command, `infrahub tasks flush flow-runs` and `infrahub upgrade`. The server and workers do not need them, but setting them everywhere is harmless and is what the Helm chart and compose files do.
- Names are final once the configuration reference is regenerated; the design doc marks them "not final".
