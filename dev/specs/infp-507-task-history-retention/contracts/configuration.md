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
- The standalone task manager reads only the `task_manager` section of `infrahub.toml` and the `INFRAHUB_TASK_MANAGER_*` variables, so an invalid value in another section does not stop it. A configuration file it cannot read or parse still stops it. An invalid `INFRAHUB_LOG_LEVEL` (such as `verbose`) or `INFRAHUB_PRODUCTION` (such as `maybe`) also stops it, because the task manager reads these two variables to set up its logging. In distributed mode the task manager also loads the whole configuration, as it did before.
- A Prefect retention setting that the task manager already has (`PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD`, `PREFECT_SERVER_EVENTS_RETENTION_PERIOD`, `PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES`) takes precedence, whether it comes from an environment variable that is not empty or from Prefect's `.env` file, `prefect.toml`, the `[tool.prefect]` table of `pyproject.toml` or active profile. The task manager writes no variable for it, because an environment variable would replace the value from a file, and logs one warning for each:
  - Set in the environment: `PREFECT_<NAME> is set and overrides task_manager.retention.<key>`, naming the variable found, which can be a legacy or lower-case name that Prefect accepts.
  - Set in a file or the profile: `PREFECT_<NAME> is set in a Prefect settings file or profile and overrides task_manager.retention.<key>`.
- A `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` already set, in the environment or in one of Prefect's settings files or the profile, is also kept, but with no such warning, because it turns Prefect's cleanups on or off and replaces no retention: `task_history` still sets how long task runs are kept unless `PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD` is set. After applying the variables, the task manager reads the switch as Prefect parses it and logs a warning for each cleanup it turns off:
  - Without `flow_runs` (for example `false`, which Prefect reads as `events` only): `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on flow_runs, so old task runs are not deleted and task_manager.retention.task_history is not applied`.
  - Without `events`: `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on events, so old events are not deleted and task_manager.retention.activity_log and task_manager.retention.prefect_own_events are not applied`.
  - With a vacuum type Prefect does not accept: `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED is not valid: <Prefect's error>`. The task manager does not stop on it; Prefect raises the same error when it schedules its background services.
- An empty or blank `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED`, such as a compose file passes for an unset host variable, does not count as set, because Prefect reads it as `false`, which deletes no task runs. The task manager removes it, in any letter case, before it checks which settings are set. When Prefect's `.env` file, `prefect.toml`, the `[tool.prefect]` table of `pyproject.toml` or the active profile sets the switch, that value applies, with the warnings above for each cleanup it turns off. Otherwise the task manager writes `events,flow_runs` and logs no warning.
- An empty or blank value of one of the three retention variables, under any name Prefect accepts for it, stops the task manager before it reads `task_manager.retention`, as it did before this feature. Prefect refuses the value when the task manager imports Prefect: the two retention periods fail with a `time_delta_parsing` validation error and the per-type overrides with a `SettingsError`. Every `infrahub` command stops on it in the same way, because the command line also imports Prefect when it starts. So neither the task manager nor a command can remove such a variable before Prefect reads it.
- At startup the task manager logs `Task manager retention: <PREFECT_VARIABLE>=<value>` for each of the four Prefect settings, with the value Prefect parsed after the refresh, whatever its source. The per-type overrides are logged as a count of event types per retention, such as `P3D for <count> event types`, or as `{}` when there is none. With the default retention there is none, because the task manager writes the overrides only when `prefect_own_events` is shorter than `activity_log` or the event retention is already set.
- The values are read by the task manager, the background-services command, `infrahub tasks flush flow-runs` and `infrahub upgrade`. The server and workers do not need them, but setting them everywhere is harmless and is what the Helm chart and compose files do.
- Names are final once the configuration reference is regenerated; the design doc marks them "not final".
