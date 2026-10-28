# Task Manager Retention

> Part of: `dev/knowledge/backend/` | Related: [Asynchronous Tasks](async-tasks.md),
> [Events System](events.md)

The task manager's database holds two kinds of records that grow with use: task history (flow runs
with their task runs, states, logs and artifacts) and events (Infrahub's activity log plus Prefect's
own events). Infrahub bounds both with three settings that it translates into the settings of
Prefect's own cleanup services. The retention code adds no tables, indexes or extensions to Prefect's
database: it sets Prefect settings, deletes rows in Prefect's existing tables, and rewrites those tables.

## Behaviour

| Situation | What happens |
|---|---|
| The task manager or `infrahub tasks background-services` starts | Infrahub reads the `task_manager` section of the configuration file and the environment, refuses to start when a retention is not a number of days or an ISO 8601 duration, or is outside 1 to 36,500 days (the error names the setting), removes an empty vacuum switch, sets the derived `PREFECT_*` variables whose setting no Prefect source sets, refreshes Prefect's settings, and logs each warning and the value Prefect applies for each setting. The task manager reads the file `INFRAHUB_CONFIG` names, else `infrahub.toml`; `background-services` reads its `CONFIG_FILE` argument, else the same files |
| `infrahub tasks background-services` gets a `CONFIG_FILE` argument that is not an existing file | It prints `Configuration file not found: <path>` and exits 1 before the services start; without the argument, a missing file leaves the settings to the environment |
| A Prefect retention setting is already set, by an environment variable under any name Prefect accepts, by Prefect's `.env` file, `prefect.toml` or `pyproject.toml`, or by its active profile | The setting wins, and one warning per setting names the Infrahub setting it hides |
| `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` is already set | It is kept, and one warning per cleanup it turns off (`flow_runs`, `events`) names the retention that is not applied; an empty or blank value is removed first, because Prefect reads it as `false` |
| `prefect_own_events` is longer than `activity_log` | Every process that loads the configuration refuses to start: the task manager and `background-services`, and the API server, the task workers and the CLI commands that load the whole configuration, because `config.py::Settings` includes the `task_manager` section. A retention outside its range stops the same processes |
| `PREFECT__SERVER_WEBSERVER_ONLY` is set | The task manager logs at INFO that this process does not run Prefect's background services and names `infrahub tasks background-services` |
| Every hour | Prefect deletes finished top-level runs older than `task_history` with their logs and artifacts, events older than `activity_log`, and listed Prefect event types older than `prefect_own_events` |
| A Prefect event type is missing from `PREFECT_EVENT_TYPES` | It is kept for `activity_log`: it costs disk, and no Infrahub event is ever deleted early |
| `infrahub tasks flush flow-runs [--rewrite]` | Runs the cleanup job in the task manager with the rewrite mode `never`, or `if_freed` with `--rewrite`, and prints the runs deleted and the tables rewritten, left as mostly live, still locked, stopped at the time limit and failed with a database error; the task manager refuses it with `403`, and the CLI exits 1, when Prefect's vacuum switch does not turn on `flow_runs` |
| `infrahub upgrade` | Deletes nothing; in its task manager step it prints the task history size and the count of old runs from `GET /infrahub/task-history/size` and the command, or the reason instead of the command when Prefect's vacuum switch keeps old task runs, or why it has no size and the command when the size does not come within 10 s |
| The task manager has no cleanup route (an older release) | The CLI prints that the cleanup is not provided, deletes nothing and exits 0 |
| A retention is lowered | The next hourly run deletes the older records; disk space returns only with `flush flow-runs --rewrite`, which rewrites each task history and activity log table that is mostly free space |
| A run stays RUNNING or PENDING | Nothing deletes it until `infrahub tasks flush stale-runs` marks it CRASHED; see [Stuck runs](#stuck-runs) |
| A branch is deleted | `branch-purge-tasks` deletes the finished runs tagged with the branch, independently of the retention |
| Tests on the Prefect harness | `backend/tests/helpers/constants.py` sets `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` to `[]`, which takes precedence, so Prefect's vacuum stays off, the task manager logs both turned-off-cleanup warnings, and an event query that sets no start reads 180 days back |

## Settings and their translation

`prefect_server/retention_settings.py::TaskManagerRetentionSettings`, which `config.py` re-exports,
is the `task_manager.retention` section, with the `INFRAHUB_TASK_MANAGER_RETENTION_` environment
prefix. `prefect_server/retention.py` turns it into Prefect variables:

| Prefect variable | Value |
|---|---|
| `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` | `events,flow_runs` (Prefect's default turns on `events` only) |
| `PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD` | `task_history` |
| `PREFECT_SERVER_EVENTS_RETENTION_PERIOD` | `activity_log` |
| `PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES` | `prefect_own_events` for every type in `PREFECT_EVENT_TYPES` when it is shorter than `activity_log` or a Prefect source sets the event retention; otherwise `{}`, which also replaces Prefect's default override for heartbeats |

- Apply the translation through `prefect_server/app.py::apply_infrahub_settings_to_prefect`, before
  Prefect's app or services start. Prefect builds its settings from the environment once, at
  import, so the function writes `os.environ` and then calls
  `prefect.context.refresh_global_settings_context`. `create_infrahub_prefect` and
  `cli/tasks.py::run_background_services`, which the `background-services` command runs, call it.
- `prefect_retention_already_set` reads, before any variable is written, which settings a Prefect
  source already sets: Prefect marks a field as set when the environment, under any name Prefect
  accepts including legacy aliases such as `PREFECT_EVENTS_RETENTION_PERIOD`, a `.env` file,
  `prefect.toml`, the `[tool.prefect]` table of `pyproject.toml` or the active profile supplies it.
  `apply_prefect_retention_env` leaves those settings alone and names the variable in its warning
  from the accepted names in Prefect's settings models, so a renamed alias in a Prefect upgrade is
  picked up without a code change.
- `remove_blank_vacuum_switch` runs first: a compose file passes an unset host variable as an empty
  value, which Prefect reads as `false`, so no task runs would be deleted. A vacuum switch that is
  set replaces no retention, so `turned_off_cleanup_warnings` warns for each cleanup it turns off.
- The startup lines (`prefect_retention_in_effect`) give the value Prefect applies for each of the
  four settings, whatever source set it. The overrides are counted per retention, such as
  `P1D for <n> event types`, or shown as `{}`.
- Durations are written in days (`P30D`), never in months or years, whose length differs between ISO
  8601 readers.
- The cleanup job takes its cutoff from Prefect's `server.services.db_vacuum.retention_period` inside
  the task manager. The configuration of the process that runs the CLI never sets the cutoff.

## Task history cleanup job

Prefect's flow-run vacuum deletes the hourly increment well, but it deletes a large backlog roughly
18 times slower than set-based deletes, and it slows down as it goes. The cleanup job deletes the
backlog with set-based SQL inside the task manager, the only process connected to Prefect's
database, and can then rewrite the tables to return the disk space.

- **Routes**: `POST /infrahub/task-history/cleanup` starts a job, `GET
  /infrahub/task-history/cleanup/{id}` reads it, and `GET /infrahub/task-history/size` answers the
  disk space of the six task history tables with their indexes (`pg_total_relation_size`, no table
  data read; `null` on SQLite) and the runs that a cleanup would delete now, counted up to
  `_OLD_RUNS_COUNT_LIMIT` (100,000) so the count stays fast, in `prefect_server/task_history.py`.
  They have no authentication, like the existing events route and Prefect's own API. When
  Prefect's vacuum switch, as Prefect parses it, does not turn on `flow_runs`, the start answers
  `403` with the reason and the size gives it as `deletion_off_reason`
  (`retention.py::task_run_deletion_off_reason`): Prefect's own cleanup then deletes no old task
  runs, so a job would delete runs that the hourly cleanup keeps.
- **Deletes**: `TaskHistoryTables.delete_runs` uses the conditions of Prefect's
  `vacuum_old_flow_runs` (top-level, terminal state, `end_time` before the cutoff). The job works one
  day of end times at a time, from the oldest, with at most 1,000 runs per transaction
  (`_RUNS_PER_TRANSACTION`), the earliest ended first, and moves to the next day once a transaction
  deletes fewer, which leaves only runs that other sessions hold locked. It deletes the runs first,
  so task runs and states follow by cascade, then the logs and artifacts of the deleted IDs. Keep
  that order and `FOR UPDATE SKIP LOCKED`: they match Prefect's vacuum, so the two can run at the
  same time without deadlocking. Passes repeat until one deletes nothing, which catches subflows
  that became top-level when their parent was deleted.
- **Equivalence guard**: `backend/tests/component/task_manager/test_task_history_cleanup.py` runs
  Prefect's `vacuum_old_flow_runs` and the job on copies of the same data and compares what is left.
  It fails when a Prefect upgrade changes the vacuum's rules.
- **Rewrite**: `CleanupRewrite` is `never` or `if_freed`, which `--rewrite` sends. With
  `if_freed` the job rewrites each of `flow_run`, `flow_run_state`, `task_run`, `task_run_state`,
  `log`, `artifact`, `events` and `event_resources` whose live rows take less than half of its size
  on disk (main data and TOAST, without indexes), whoever deleted the rows and when. Prefect's vacuum
  deletes old runs every hour and old events after their retention, so after an upgrade or a lowered
  retention the job deletes little, and a rule on its own deletes would skip the rewrite exactly when
  the disk must come back. The live size sums `pg_column_size` per column plus 28 bytes a row, so no
  value stored out of line is read; `PostgresTableRewriter.space` reads a table of up to
  `_EXACT_MEASURE_PAGES` (10,000) pages whole and estimates a larger one from `TABLESAMPLE SYSTEM`
  over about that many random pages, so a mostly live event table of hundreds of GB is not read
  whole only to be left as it is. A small table usually counts as mostly free, because space is
  counted in whole pages and the upgrade replaces Prefect's scheduled runs, and is rewritten in
  milliseconds. The rewrite is `VACUUM FULL`, on PostgreSQL only, in autocommit, with a 3-second
  `lock_timeout` and up to 4 retries 20 seconds apart, a 60-second `statement_timeout` per
  `VACUUM FULL`, a non-blocking `VACUUM (ANALYZE)` of each rewritten table, and a pause before the
  next table so that Prefect catches up on the writes that waited: ten times as long as the
  previous table was locked, up to 60 seconds, so a table rewritten in milliseconds adds no wait.
  A `VACUUM FULL` waiting for its lock makes every
  later query on the table queue behind it, hence the short lock timeout; a cancelled `VACUUM FULL`
  leaves the table as it was, so the statement timeout only bounds how long the table stays locked.
  A table whose rewrite always takes longer than the timeout is never rewritten by the job: each run
  locks it for the full 60 seconds and is stopped again, and the limit has no setting, so the
  operator docs give a manual `VACUUM FULL` during a maintenance window.
  The job lists the tables in `rewritten`, `mostly_live` (left because their live rows take at
  least half of their size), `not_rewritten` (still locked after the retries), `timed_out`
  (stopped at the statement timeout) and `failed` (another error from the database server, such as
  no free disk for the copy, after which the server has rolled back that rewrite alone), and the CLI
  prints one line per list. Each rewritten table is listed as soon as its rewrite ends, so a failed
  job still shows the tables finished before the failure. `rewrite_error_outcome` tells the errors
  apart by SQLSTATE: `55P03` (lock not available) is a locked attempt, `57014` (query cancelled) is
  `timed_out`, and any other SQLSTATE is `failed`. The rewrite goes on with the next table after
  each of these; a lost connection, or an error without a SQLSTATE, fails the job.
- **Database pool**: the deletes, the measurements, the rewrites and the cleanup lock use a small pool
  of their own (2 connections and 1 overflow) with a 24-hour statement timeout, which outlasts any
  maintenance statement. Prefect 3.8.6 caches its engines by timeout, so this timeout also keeps the
  pool apart from the engines of Prefect's API and of Prefect's own cleanup. Each delete transaction
  sets a 60-second `lock_timeout` for itself only (`_DELETE_LOCK_TIMEOUT`), because only the runs
  are selected with `SKIP LOCKED`: the cascaded task runs and states, the subflows whose parent is
  set to null, and the logs and artifacts would otherwise wait on a stuck session until the 24-hour
  timeout, holding the cleanup lock all along. A job that reaches it fails with `The runs that ended
  on <day> stayed locked by another session for more than 60 seconds, so the cleanup stopped`.
- **One job at a time**: `CleanupJobs` keeps the job of this process, and a PostgreSQL advisory lock,
  held by a dedicated autocommit connection that is invalidated on release, covers every replica.
  Another replica answers `409`. Every 30 seconds (`_CLEANUP_LOCK_CHECK_INTERVAL`), that
  connection reads `pg_locks` to check that its session still holds the lock, which also keeps the
  session from sitting idle past an idle timeout. When a check fails, finds the lock gone, or gets
  no answer within 30 seconds, in which case the connection is closed without waiting for the
  server, the job cancels its current step and fails with `The cleanup stopped, because it could not
  confirm that it holds the cleanup lock; start it again`: the deletes not committed roll back, and a
  rewrite in progress leaves its table as it was. A connection pooler in transaction mode can run
  the check on a session other than the one that took the lock, so the job stops there. The same
  replica returns its running job and raises its mode to a stronger request's (`never` < `if_freed`). The job decides about the rewrite once its deletes end,
  decides again when `if_freed` arrives after a decision with `never`, and never rewrites twice. The mode change and the job's final check take the registry's
  start lock, so a request either reaches the job before that check or starts a new job.
- **State in memory**: a task-manager restart loses the job (`GET` answers `404`) but not the
  deletes already committed; a new job continues from the oldest remaining run.
- **Models**: the request and job models are in `prefect_server/task_history_models.py`, which
  imports neither Prefect's database layer nor its driver, so the CLI client can use them; a unit test
  checks it.
- **Client**: `task_manager/flow_run/cleanup.py::run_task_history_cleanup` polls every 2 seconds. A
  `404` to a `POST` means a task manager without the cleanup and returns `None`. A `403` raises
  `TaskHistoryCleanupError` with the task manager's reason. A `409` on a `POST`, a `404` on a `GET`,
  or, after the task manager has answered once, a transport error or a `502`, `503` or `504` (a
  proxy in front of a restarting task manager) means waiting and posting again; each wait is
  reported when it starts, when its reason changes and when it starts again after a job showed, and
  the client gives up 3 hours after it last saw a job, naming the last reason. An answer that holds
  no job raises `TaskHistoryCleanupError` with the status and the validation errors on one line. The
  client returns a `FollowedCleanup`: the job, plus the runs that each job the task manager lost had
  deleted when the client last saw it. The CLI adds them to the job's and prints `at least`, because
  a lost job may have deleted more. A failed job comes back in `TaskHistoryCleanupFailedError`, so
  the CLI prints what it and the lost jobs had deleted and the tables it finished rewriting.
  `cli/tasks.py::flow_runs` calls it through `cli/tasks.py::flush_old_flow_runs`.
- **Upgrade hint**: `cli/upgrade.py::_upgrade_execute` calls `cli/tasks.py::task_history_size_hint`
  in its task manager step. The hint reads the size route through
  `task_manager/flow_run/cleanup.py::read_task_history_size` within 10 seconds and prints the size
  and the count of old runs (`more than 100,000` past the limit) with the command, or with the
  `deletion_off_reason` instead of the command; a late answer, an error answer (`404` from a task manager without the route) or
  an answer without a size gets a line that names the error type, then the command, so the hint
  never fails or holds up the upgrade.
  The upgrade runs no cleanup: operators of existing instances with a lot of task history run the
  command once after it, with the instance running.

## Stuck runs

The hourly vacuum deletes only runs in a terminal state with an end time, so a run left RUNNING or
PENDING by a dead worker stays. Two mechanisms move such runs to CRASHED, and Prefect's global
policy then records an end time, after which the vacuum deletes them like any other finished run:

- The `crash-zombie-flows` automation crashes a run whose heartbeats stop; see
  [Liveness and zombie detection](async-tasks.md#liveness-and-zombie-detection).
- `infrahub tasks flush stale-runs` calls `FlowRunRetention.purge(delete=False)` through Prefect's
  API: RUNNING or PENDING runs whose start time is older than `--days-to-keep` (2 by default) are
  forced to CRASHED. Prefect's start-time filter falls back to the expected start time, so a PENDING
  run that never started is matched by the time it was expected to start. Nothing schedules it, and
  a run legitimately running longer than the threshold is crashed too.

Runs stuck in SCHEDULED, LATE, PAUSED or CANCELLING are not covered by either.

## Event retention

Prefect deletes every event older than its global event retention, which is set to `activity_log`,
and deletes the types listed in its per-type overrides after `prefect_own_events`. Prefect matches an
override by exact event name and applies the shorter of the type's retention and the global one, so
an override that is not shorter changes nothing: Infrahub writes the overrides only when
`prefect_own_events` is shorter than `activity_log`, or when a Prefect source sets the event
retention, and refuses a `prefect_own_events` longer than `activity_log`. Related resources are
deleted with their event.

- `prefect_server/retention.py::PREFECT_EVENT_TYPES` lists Prefect's own event types for the pinned
  Prefect release: the flow-run and task-run state events for every built-in state name, the
  heartbeat, the flow-run pull-step events, and the runner, workspace transfer, worker, flow,
  deployment, work pool, work queue, automation, block, variable, concurrency limit, artifact and
  asset events. It never lists an `infrahub.` type, so no
  Infrahub event is deleted before `activity_log`.
- `backend/tests/unit/prefect_server/test_prefect_event_types.py` reads the installed Prefect's
  source with `ast`. It fails when Prefect builds an event name from an f-string pattern that the
  test does not know, and when one of these has no listed event: a literal `prefect.*` event name, a
  deployment, work pool or work queue status, an automation trigger state, a kind of record with
  lifecycle events, or a state name that Prefect defines or sets.
  `backend/tests/integration_docker/test_prefect_event_types.py` runs a workload on the full stack,
  including failed and cancelled flows and a worker restart, and fails on any stored non-`infrahub.`
  type that is missing. Update the list when either fails after a Prefect upgrade, and when an
  Infrahub flow introduces a custom state name, which creates a new state event type.
- Neither test sees an event name that Prefect builds in a way the source scan does not read, or a
  custom state name that the workload does not reach. So once Prefect's startup has
  migrated the database, `prefect_server/app.py::create_infrahub_prefect` reads each stored event
  type, one index lookup per type through `prefect_server/database.py::read_stored_event_types`,
  and logs a warning naming every stored `prefect.*` type that has no per-type retention in the
  overrides Prefect applies, with the event retention that keeps them as an ISO 8601 duration. A
  type appears from the first start after Prefect stored an event of it.
- The check reads nothing when Prefect deletes no events (the vacuum switch leaves out `events`, or
  the event persister is off), or when no per-type retention is shorter than the event retention,
  as with the default retentions, because every type is then kept for the same time
  (`retention.py::event_types_with_retention_override`). On PostgreSQL the read has a 5-second
  `statement_timeout`, local to its transaction, so a locked `events` table, as during a rewrite,
  delays the start by at most 5 seconds. Any error of the read is logged as a warning with its
  traceback, and the task manager starts without the check. The check runs in each web server
  process, so a task manager with several processes logs the warning once in each.
- Prefect's per-type vacuum deletes roughly 20 times fewer rows per second than its time-based
  vacuum. That is acceptable because the first run after an upgrade has little to delete and later
  runs delete one hour of events.
- Lowering `activity_log` deletes the older events, and PostgreSQL reuses their space without
  shrinking the files; `infrahub tasks flush flow-runs --rewrite` rewrites `events` and
  `event_resources` when their live rows take less than half of their size, like the task history
  tables.

## Key Locations

| Component | Location |
|-----------|----------|
| Settings | `backend/infrahub/prefect_server/retention_settings.py::TaskManagerRetentionSettings`, re-exported by `backend/infrahub/config.py` |
| Translation, event-type list | `backend/infrahub/prefect_server/retention.py` |
| Startup wiring | `backend/infrahub/prefect_server/app.py::apply_infrahub_settings_to_prefect` |
| Cleanup job, size and routes | `backend/infrahub/prefect_server/task_history.py` |
| Cleanup client | `backend/infrahub/task_manager/flow_run/cleanup.py` |
| CLI commands, upgrade hint | `backend/infrahub/cli/tasks.py`, `backend/infrahub/cli/upgrade.py::_upgrade_execute` |
| Stale-run marking | `backend/infrahub/task_manager/flow_run/retention.py::FlowRunRetention` |
