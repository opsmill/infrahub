Added three settings that control how long the task manager keeps its records: `task_manager.retention.task_history` (30 days by default), `task_manager.retention.activity_log` (7 days) and `task_manager.retention.prefect_own_events` (7 days). Set them in `infrahub.toml` or with the `INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY`, `INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG` and `INFRAHUB_TASK_MANAGER_RETENTION_PREFECT_OWN_EVENTS` environment variables, as a number of days (`30d`) or an ISO 8601 duration (`P30D`), from 1 to 36500 days.

Until now, finished task runs were not deleted automatically by age. The task manager now deletes the finished task runs older than the task history retention every hour, together with their logs and artifacts, and the deletion cannot be undone, so set a longer `task_history` before upgrading if you need older runs.

The activity log is still kept for 7 days by default. To keep it longer, raise `activity_log`, for example to `365d`, while the events the task manager records for its own use are still deleted after `prefect_own_events`.

A `PREFECT_*` variable already set in the task manager environment, such as `PREFECT_SERVER_EVENTS_RETENTION_PERIOD`, takes precedence over the matching setting, and the task manager logs a warning that names it.
