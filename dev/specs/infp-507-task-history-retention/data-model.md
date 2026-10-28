# Data Model: Task History and Activity Log Retention

No graph schema, GraphQL schema or database schema changes. The feature adds one configuration section, reads and deletes rows in Prefect's existing tables, and changes how Activities filters are expressed.

## Retention settings (new configuration section)

| Field | Type | Default | Validation |
|---|---|---|---|
| `task_history` | duration | 30 days | ≥ 1 day, ≤ 36,500 days |
| `activity_log` | duration | 7 days | ≥ 1 day, ≤ 36,500 days |
| `prefect_own_events` | duration | 7 days | ≥ 1 day, ≤ 36,500 days, ≤ `activity_log` |

- Owned by the Infrahub configuration, as a section of the main settings with its own environment prefix (names final in the configuration contract).
- Same values in every edition, with no edition limit. The 36,500-day (100-year) maximum is a technical safety bound, far below the roughly 739,000 days at which Prefect's cutoff date overflows.
- Validated when the task manager or the background-services command starts; an invalid value stops the process with an error naming the setting.

### Derived Prefect settings

| Prefect setting | Value |
|---|---|
| `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` | `events,flow_runs` |
| `PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD` | `task_history` |
| `PREFECT_SERVER_EVENTS_RETENTION_PERIOD` | `activity_log` |
| `PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES` | `{}` when Infrahub sets the event retention and `prefect_own_events` equals `activity_log`; otherwise `{type: prefect_own_events for type in PREFECT_EVENT_TYPES}` |

A Prefect setting that one of Prefect's sources already sets is left as is: the task manager writes no variable for it, because an environment variable takes precedence over every other source. The sources are an environment variable that is not empty, a `.env` file, `prefect.toml`, the `[tool.prefect]` table of `pyproject.toml` and the active profile. A preset retention setting comes with a warning naming the setting it overrides. A preset `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` replaces no retention, so it gets no such warning; instead the task manager warns for each of `flow_runs` and `events` that the switch leaves off, naming the retention that is then not applied. An empty or blank vacuum switch in the environment is removed first, so it does not count as set; an empty switch in Prefect's `.env` file is not removed and counts as set. An empty or blank retention variable that Prefect reads (the main name, or a legacy name when the main name is not set) stops the task manager before it reads its configuration, because Prefect refuses the value when it is imported. The startup log shows each of the four values as Prefect parsed it after the refresh, whatever its source.

## Prefect event types list (new constant)

- A fixed list of the event types the pinned Prefect release sends (flow-run and task-run state events for every state name Prefect defines or sets, heartbeat, worker, automation, deployment, work pool, work queue, block and workspace transfer events).
- Changes only with a Prefect upgrade; guarded by unit tests over the event names, name patterns, statuses, lifecycle record kinds and state names in the pinned Prefect's source, and by an integration-docker test on a real workload.
- Infrahub event types (prefix `infrahub.`) are never in it.

## Existing Prefect records touched

| Record | Table(s) | Lifecycle after this feature |
|---|---|---|
| Flow run (task history) | `flow_run`, `flow_run_state`, `task_run`, `task_run_state` | Deleted when top-level, in a terminal state (COMPLETED, FAILED, CANCELLED, CRASHED), and `end_time` older than `task_history`. Runs RUNNING or PENDING are not deleted. `infrahub tasks flush stale-runs` moves those whose start time, or expected start time for a run that never started, is more than `--days-to-keep` days old (default 2) to CRASHED with an end time, so the cleanup deletes them once that end time is older than `task_history`. |
| Log, artifact | `log`, `artifact` | Deleted with their flow run; orphans removed daily by Prefect. |
| Infrahub event | `events`, `event_resources` | Deleted when older than `activity_log`, with its related items. |
| Prefect event | `events`, `event_resources` | Deleted when older than `prefect_own_events` if its type is in the list, otherwise when older than `activity_log`. |

## Cleanup job (new, in-memory in the task manager)

| Field | Meaning |
|---|---|
| `id` | Job identifier returned to the caller |
| `state` | `running`, `completed`, `failed` |
| `rewrite` | Whether to rewrite tables after the deletes: `never` or `if_freed`; a request for `if_freed` raises a running job's `never` |
| `cutoff` | End-time cutoff derived from `task_history` at start |
| `deleted_runs` | Runs deleted so far |
| `current_day` | Day of end times being deleted (progress) |
| `size_before`, `size_after` | Total size of the tables the job may rewrite (the six task-history tables and the two activity log tables), when the database reports it |
| `rewritten` | Tables rewritten |
| `mostly_live` | Tables left as they are, because their live rows hold at least half of their disk space |
| `not_rewritten` | Tables whose rewrite still hit the lock timeout after its retries |
| `timed_out` | Tables whose rewrite was stopped at its statement timeout, which leaves them as they were |
| `failed` | Tables whose rewrite failed with a database error, which leaves them as they were |
| `error` | Message when `failed` |

- A job starts only when the vacuum switch, as Prefect parses it, turns on `flow_runs`, so that the job deletes no run that Prefect's own cleanup keeps. Otherwise the start is refused with the reason, before any lock is taken.
- At most one job runs at a time across all task-manager replicas, enforced by a Postgres advisory lock held for the job's run and checked every 30 s; a job that cannot confirm it holds the lock stops and fails. A new request on the same replica returns the running job, raising its `rewrite` to the request's when that is stronger (`never` < `if_freed`); on another replica it is refused with "running elsewhere".
- Each transaction deletes at most 1,000 runs of one day of end times, the earliest ended first, then the logs and artifacts of those runs (Prefect's order), so a job stopped midway leaves a consistent state and a new job continues from the oldest remaining run. On Postgres, each transaction sets a 60 s `lock_timeout` for itself only; a job whose transaction reaches it fails with an `error` that names the day, and nothing of that transaction is deleted.
- The job lives in the task-manager process that runs it; a restart loses its status but not its committed progress.
- The rewrite runs only on Postgres, and only with `if_freed` (the command's rewrite option). It covers `flow_run`, `flow_run_state`, `task_run`, `task_run_state`, `log`, `artifact`, `events` and `event_resources`, and rewrites each table whose live rows hold less than half of its disk space, whoever deleted its rows: deletes made before the job started, such as those of Prefect's own cleanup, count too. A table's disk space is its main data and TOAST, without indexes; its live size is the sum of `pg_column_size` per column plus 28 bytes a row, read whole for a table of up to 10,000 pages and from a random sample of about 10,000 of its pages above that. The job decides once its deletes end, and again before it completes when a request raises its mode to `if_freed` after that; it never rewrites twice. Each table rewrite has a 3 s lock timeout and up to 4 retries 20 s apart, and a 60 s statement timeout; tables still locked after the retries are listed in the job result as `not_rewritten`, tables whose rewrite was stopped at the statement timeout as `timed_out`, and tables whose rewrite failed with another database error, such as no free disk for the copy, as `failed`. The job goes on with the next table after each of these; a lost database connection, or an error during a table's rewrite that did not come from the database server, still fails the job. Each rewritten table then gets a plain `VACUUM (ANALYZE)`, and before the next table the job pauses ten times as long as the previous table was locked, up to 60 s (changed on 27 Oct, from the manual cleanup of OpsMill's production task manager).

## Task history size (new, read by the upgrade)

| Field | Meaning |
|---|---|
| `size` | Disk space in bytes of the six task-history tables with their indexes; `null` on SQLite |
| `old_runs` | Finished top-level runs older than the task history retention, counted up to 100,000 |
| `old_runs_limit_reached` | Whether more runs than `old_runs` are older than the retention |
| `deletion_off_reason` | Why the vacuum switch keeps old task runs (`PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on flow_runs`, or `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED is not valid: <Prefect's error>`); `null` when it turns their deletion on |

- The size is read with `pg_total_relation_size`, which reads no table data. The count selects the runs as the cleanup does and stops at 100,001, so it stays fast on millions of runs.

## Activities filters (changed expression, same results)

| Filter | Today (label, no index) | After (indexed resource ID) |
|---|---|---|
| Account | related `infrahub.resource.id` | related id `infrahub.account.<id>`, role `infrahub.account` |
| Branch | related `infrahub.resource.label = <name>` | related id `infrahub.branch.<branch_id>`, role `infrahub.branch`; name resolved to ID, deleted names through the newest `infrahub.branch.deleted` event |
| Primary node | resource label `infrahub.node.id` | when the request lists event types and none of them is `infrahub.branch.merged`, `infrahub.branch.deleted` or `infrahub.group.auto_created`: resource `prefect.resource.id` in (`infrahub.node.<id>`, `<id>`, `infrahub.account.<id>`, `infrahub.proposed_change.<id>`), which Prefect matches on the event's main related item (indexed), not on the event row (fast only with skip scan), plus today's label on the same item; otherwise today's label only, because those three event types carry the node (a proposed change or a group) only in a label |
| Parent event | related label `infrahub.event_parent.id` | related id `<parent_id>`, role `infrahub.ancestor_event`, plus today's label check for direct children |
| Merged, rebased, migrated by name | resource label `infrahub.branch.name` | resource id `infrahub.branch.<name>` when every listed event type is a branch event; otherwise today's label, which other event types also carry |
| Level, event type, has children | unchanged | unchanged |

The primary node conditions are added to the resource conditions that `event_type_filter` sets (branch name, identity provider, protocol). Before, they replaced them, so a request with both also returned events that matched the primary node but not those conditions.

## Activities page request (changed)

| Field | Today | After |
|---|---|---|
| `count` | Not selected by the page, yet always computed by the task manager | Computed only when selected |
| Paging | `offset` | `until` = time of the oldest event shown (`since` = time of the newest, in ascending order), events already shown dropped by ID; `offset` still accepted for API clients |
| Time window | Prefect's 180-day default | Windows 1 h, 1 d, 7 d, 30 d, then the activity log retention (at least 180 days when the task manager does not delete old events), counted back from `until` or now |
