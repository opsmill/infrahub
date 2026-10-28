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
- Every value must be at least 1 day and at most 36,500 days (100 years, a safety bound far below the roughly 739,000 days at which Prefect's cutoff date overflows), or the process refuses to start. A `prefect_own_events` longer than `activity_log` also stops the process, because Prefect deletes every event older than the activity log retention anyway, so lowering `activity_log` below 7 days needs a `prefect_own_events` no longer than it.
- Invalid values stop the task manager and the background-services command with: `Invalid task manager retention: <key> <reason>`.
- The standalone task manager reads only the `task_manager` section of `infrahub.toml` and the `INFRAHUB_TASK_MANAGER_*` variables, so an invalid value in another section does not stop it. A configuration file it cannot read or parse still stops it. In distributed mode the task manager also loads the whole configuration, as it did before.
- A Prefect variable already set in the environment to a value that is not empty (`PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED`, `PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD`, `PREFECT_SERVER_EVENTS_RETENTION_PERIOD`, `PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES`) takes precedence; the task manager logs `PREFECT_<NAME> is set and overrides task_manager.retention.<key>` for each one. An empty or blank variable, such as a compose file passes for an unset host variable, does not count as set: the task manager removes it and writes its own value with no warning.
- The values are read by the task manager, the background-services command, `infrahub tasks flush flow-runs` and `infrahub upgrade`. The server and workers do not need them, but setting them everywhere is harmless and is what the Helm chart and compose files do.
- Names are final once the configuration reference is regenerated; the design doc marks them "not final".
