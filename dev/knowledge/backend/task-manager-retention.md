# Task Manager Retention

> Part of: `dev/knowledge/backend/` | Related: [Asynchronous Tasks](async-tasks.md),
> [Events System](events.md)

The task manager's database holds two kinds of records that grow with use: task history (flow runs
with their task runs, states, logs and artifacts) and events (Infrahub's activity log plus Prefect's
own events). Infrahub bounds both with three settings that it translates into the settings of
Prefect's own cleanup services. The retention code adds no tables, indexes or extensions to Prefect's
database: it sets Prefect settings, and deletes and rewrites rows in Prefect's existing tables.

## Behaviour

| Situation | What happens |
|---|---|
| The task manager or `infrahub tasks background-services` starts | Infrahub loads its configuration, refuses to start when a retention is outside 1 to 36,500 days (the error names the setting), sets the derived `PREFECT_*` variables that the environment does not already set, refreshes Prefect's settings, and logs each warning and the values in effect |
| A Prefect retention variable is already set, under any name Prefect accepts | The variable wins, and one warning per variable names the Infrahub setting it hides |
| `prefect_own_events` is longer than `activity_log` | It is capped to `activity_log`, with a warning |
| Every hour | Prefect deletes finished top-level runs older than `task_history` with their logs and artifacts, events older than `activity_log`, and listed Prefect event types older than `prefect_own_events` |
| A Prefect event type is missing from `PREFECT_EVENT_TYPES` | It is kept for `activity_log`: it costs disk, and no Infrahub event is ever deleted early |
| `infrahub tasks flush flow-runs [--rewrite]` | Runs the cleanup job in the task manager with the rewrite mode `never`, or `always` with `--rewrite` |
| `infrahub upgrade` | Step 6/7 runs the cleanup job with `if_freed`; a failure is reported with the command that finishes it, and the upgrade continues; `--no-task-history-cleanup` skips the step |
| The task manager has no cleanup route (an older release) | The CLI prints that the cleanup is not provided, deletes nothing and exits 0 |
| A retention is lowered | The next hourly run deletes the older records; task history disk space returns only with `flush flow-runs --rewrite`; event tables are never rewritten, and PostgreSQL reuses their space |
| A run stays RUNNING or PENDING | Nothing deletes it until `infrahub tasks flush stale-runs` marks it CRASHED; see [Stuck runs](#stuck-runs) |
| A branch is deleted | `branch-purge-tasks` deletes the finished runs tagged with the branch, independently of the retention |
| Tests on the Prefect harness | `backend/tests/helpers/constants.py` sets `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` to `[]`, which takes precedence, so Prefect's vacuum stays off |

## Settings and their translation

`config.py::TaskManagerRetentionSettings` is the `task_manager.retention` section, with the
`INFRAHUB_TASK_MANAGER_RETENTION_` environment prefix. `prefect_server/retention.py` turns it into
Prefect variables:

| Prefect variable | Value |
|---|---|
| `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` | `events,flow_runs` (Prefect's default turns on `events` only) |
| `PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD` | `task_history` |
| `PREFECT_SERVER_EVENTS_RETENTION_PERIOD` | `activity_log` |
| `PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES` | `min(prefect_own_events, activity_log)` for every type in `PREFECT_EVENT_TYPES` |

- Apply the translation through `prefect_server/app.py::apply_infrahub_settings_to_prefect`, before
  Prefect's app or services start. Prefect builds its settings from the environment once, at
  import, so the function writes `os.environ` and then calls
  `prefect.context.refresh_global_settings_context`. Both `create_infrahub_prefect` and
  `cli/tasks.py::background_services` call it.
- `apply_prefect_retention_env` leaves a variable alone when the environment already sets it under
  any name Prefect accepts, including legacy aliases such as `PREFECT_EVENTS_RETENTION_PERIOD`. It
  reads the accepted names from Prefect's settings models, so a renamed alias in a Prefect upgrade is
  picked up without a code change.
- Durations are written in days (`P30D`), never in months or years, whose length differs between ISO
  8601 readers.
- The cleanup job takes its cutoff from Prefect's `server.services.db_vacuum.retention_period` inside
  the task manager. The configuration of the process that runs the CLI never sets the cutoff.

## Task history cleanup job

Prefect's flow-run vacuum deletes the hourly increment well, but it deletes a large backlog roughly
18 times slower than set-based deletes, and it slows down as it goes. The cleanup job deletes the
backlog with set-based SQL inside the task manager, the only process connected to Prefect's
database, and can then rewrite the tables to return the disk space.

- **Routes**: `POST /infrahub/task-history/cleanup` starts a job and `GET
  /infrahub/task-history/cleanup/{id}` reads it, in `prefect_server/task_history.py`. They have no
  authentication, like the existing events route and Prefect's own API.
- **Deletes**: `TaskHistoryTables.delete_runs` uses the conditions of Prefect's
  `vacuum_old_flow_runs` (top-level, terminal state, `end_time` before the cutoff), one day of end
  times per transaction. It deletes the runs first, so task runs and states follow by cascade, then
  the logs and artifacts of the deleted IDs. Keep that order and `FOR UPDATE SKIP LOCKED`: they match
  Prefect's vacuum, so the two can run at the same time without deadlocking. A second pass catches
  subflows that became top-level when their parent was deleted.
- **Equivalence guard**: `backend/tests/component/task_manager/test_task_history_cleanup.py` runs
  Prefect's `vacuum_old_flow_runs` and the job on copies of the same data and compares what is left.
  It fails when a Prefect upgrade changes the vacuum's rules.
- **Rewrite**: `CleanupRewrite` is `never`, `if_freed` (the runs left are fewer than half of the runs
  counted when the job started, Prefect's concurrent deletes included) or `always`. The rewrite is
  `VACUUM FULL` on `flow_run`, `flow_run_state`, `task_run`, `task_run_state`, `log` and `artifact`,
  on PostgreSQL only, in autocommit with a 60-second `lock_timeout` and 3 retries per table. A
  `VACUUM FULL` waiting for its lock makes every later query on the table queue behind it, hence the
  timeout; a table that still times out is listed in `not_rewritten` and the job moves on.
- **Database pool**: the job uses a small pool of its own with a statement timeout long enough for a
  day of deletes, since Prefect's default statement timeout of a few seconds would cut it short.
- **One job at a time**: `CleanupJobs` keeps the job of this process, and a PostgreSQL advisory lock,
  held by a dedicated autocommit connection that is invalidated on release, covers every replica.
  Another replica answers `409`. The same replica returns its running job and raises its mode to a
  stronger request's (`never` < `if_freed` < `always`). The job decides about the rewrite once its
  deletes end, decides again when a stronger mode arrives after that, against the count taken at
  start, and never rewrites twice. The mode change and the job's final check take the registry's
  start lock, so a request either reaches the job before that check or starts a new job.
- **State in memory**: a task-manager restart loses the job (`GET` answers `404`) but not the days
  already committed; a new job continues from the oldest remaining day.
- **Client**: `task_manager/flow_run/cleanup.py::run_task_history_cleanup` polls every 2 seconds. A
  `404` on the first `POST` means an older task manager and returns `None`. A `409`, a `404` or a
  transport error after the task manager has answered once means waiting and posting again; it gives
  up 3 hours after it last saw a job. `cli/tasks.py::flow_runs` and
  `cli/upgrade.py::upgrade_task_history` call it through `cli/tasks.py::clean_task_history`.

## Stuck runs

The hourly vacuum deletes only runs in a terminal state with an end time, so a run left RUNNING or
PENDING by a dead worker stays. Two mechanisms move such runs to CRASHED, and Prefect's global
policy then records an end time, after which the vacuum deletes them like any other finished run:

- The `crash-zombie-flows` automation crashes a run whose heartbeats stop; see
  [Liveness and zombie detection](async-tasks.md#liveness-and-zombie-detection).
- `infrahub tasks flush stale-runs` calls `FlowRunRetention.purge(delete=False)` through Prefect's
  API: RUNNING or PENDING runs whose `start_time` is older than `--days-to-keep` (2 by default) are
  forced to CRASHED. Nothing schedules it. A PENDING run that never started has no `start_time` and
  is never matched, and a run legitimately running longer than the threshold is crashed too.

Runs stuck in SCHEDULED, LATE, PAUSED or CANCELLING are not covered by either.

## Event retention

Prefect deletes every event older than its global event retention, which is set to `activity_log`,
and deletes the types listed in its per-type overrides after `prefect_own_events`. Prefect matches an
override by exact event name and applies the shorter of the type's retention and the global one,
which is why an own-event retention longer than `activity_log` is capped. Related resources are
deleted with their event.

- `prefect_server/retention.py::PREFECT_EVENT_TYPES` lists Prefect's own event types for the pinned
  Prefect release: the flow-run and task-run state events for every built-in state name, the
  heartbeat, and the runner, worker, flow, deployment, work pool, work queue, automation, block,
  variable, concurrency limit, artifact and asset events. It never lists an `infrahub.` type, so no
  Infrahub event is deleted before `activity_log`.
- Two tests guard the list. `backend/tests/unit/prefect_server/test_prefect_event_types.py` checks
  that every built-in state of the pinned Prefect is listed, and
  `backend/tests/integration_docker/test_prefect_event_types.py` runs a workload on the full stack,
  including failed and cancelled flows and a worker restart, and fails on any stored non-`infrahub.`
  type that is missing. Update the list when either fails after a Prefect upgrade, and when an
  Infrahub flow introduces a custom state name, which creates a new state event type.
- Prefect's per-type vacuum deletes roughly 20 times fewer rows per second than its time-based
  vacuum. That is acceptable because the first run after an upgrade has little to delete and later
  runs delete one hour of events.
- The event tables have no rewrite: lowering `activity_log` deletes the older events, and PostgreSQL
  reuses their space without shrinking the files.

## Key Locations

| Component | Location |
|-----------|----------|
| Settings | `backend/infrahub/config.py::TaskManagerRetentionSettings` |
| Translation, event-type list | `backend/infrahub/prefect_server/retention.py` |
| Startup wiring | `backend/infrahub/prefect_server/app.py::apply_infrahub_settings_to_prefect` |
| Cleanup job and routes | `backend/infrahub/prefect_server/task_history.py` |
| Cleanup client | `backend/infrahub/task_manager/flow_run/cleanup.py` |
| CLI commands | `backend/infrahub/cli/tasks.py`, `backend/infrahub/cli/upgrade.py::upgrade_task_history` |
| Stale-run marking | `backend/infrahub/task_manager/flow_run/retention.py::FlowRunRetention` |
