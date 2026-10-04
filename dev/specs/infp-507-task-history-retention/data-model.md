# Data Model: Task History and Activity Log Retention

No graph schema, GraphQL schema or database schema changes. The feature adds one configuration section, reads and deletes rows in Prefect's existing tables, and changes how Activities filters are expressed.

## Retention settings (new configuration section)

| Field | Type | Default | Validation |
|---|---|---|---|
| `task_history` | duration | 30 days | ≥ 1 day |
| `activity_log` | duration | 7 days | ≥ 1 day |
| `prefect_own_events` | duration | 7 days | ≥ 1 day; above `activity_log`, capped to it with a warning |

- Owned by the Infrahub configuration, as a section of the main settings with its own environment prefix (names final in the configuration contract).
- Same values in every edition, no upper limit.
- Validated when the task manager or the background-services command starts; an invalid value stops the process with an error naming the setting.

### Derived Prefect settings

| Prefect setting | Value |
|---|---|
| `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` | `events,flow_runs` |
| `PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD` | `task_history` |
| `PREFECT_SERVER_EVENTS_RETENTION_PERIOD` | `activity_log` |
| `PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES` | `{type: prefect_own_events for type in PREFECT_EVENT_TYPES}` |

A Prefect variable already set in the environment is left as is, with a warning.

## Prefect event types list (new constant)

- A fixed list of the event types the pinned Prefect release emits for Infrahub's workload (flow-run and task-run state events, heartbeat, worker, automation, deployment, work pool, work queue, block events).
- Changes only with a Prefect upgrade; guarded by a unit test over Prefect's built-in states and an integration-docker test on a real workload.
- Infrahub event types (prefix `infrahub.`) are never in it.

## Existing Prefect records touched

| Record | Table(s) | Lifecycle after this feature |
|---|---|---|
| Flow run (task history) | `flow_run`, `flow_run_state`, `task_run`, `task_run_state` | Deleted when top-level, in a terminal state (COMPLETED, FAILED, CANCELLED, CRASHED), and `end_time` older than `task_history`. Runs RUNNING or PENDING are never deleted; the stuck-runs command moves them to CRASHED with an end time. |
| Log, artifact | `log`, `artifact` | Deleted with their flow run; orphans removed daily by Prefect. |
| Infrahub event | `events`, `event_resources` | Deleted when older than `activity_log`, with its related items. |
| Prefect event | `events`, `event_resources` | Deleted when older than `prefect_own_events` if its type is in the list, otherwise when older than `activity_log`. |

## Cleanup job (new, in-memory in the task manager)

| Field | Meaning |
|---|---|
| `id` | Job identifier returned to the caller |
| `state` | `running`, `completed`, `failed` |
| `rewrite` | Whether the tables are rewritten after the deletes |
| `cutoff` | End-time cutoff derived from `task_history` at start |
| `deleted_runs` | Runs deleted so far |
| `current_day` | Day of end times being deleted (progress) |
| `size_before`, `size_after` | Total size of the six task-history tables, when the database reports it |
| `not_rewritten` | Tables whose rewrite still hit the lock timeout after its retries |
| `error` | Message when `failed` |

- At most one job runs at a time across all task-manager replicas, enforced by a Postgres advisory lock held for the job's run. A new request on the same replica returns the running job; on another replica it is refused with "running elsewhere".
- Each day of end times is committed separately, deleting the runs and then the logs and artifacts of those runs (Prefect's order), so a job stopped midway leaves a consistent state and a new job continues from the oldest remaining day.
- The job lives in the task-manager process that runs it; a restart loses its status but not its committed progress.
- The rewrite runs only when the deletes freed most of the tables (more than half of the runs the tables held). Each table rewrite has a 60 s lock timeout and up to 3 retries; tables that still time out are listed in the job result as `not_rewritten`.

## Activities filters (changed expression, same results)

| Filter | Today (label, no index) | After (indexed resource ID) |
|---|---|---|
| Account | related `infrahub.resource.id` | related id `infrahub.account.<id>`, role `infrahub.account` |
| Branch | related `infrahub.resource.label = <name>` | related id `infrahub.branch.<branch_id>`, role `infrahub.branch`; name resolved to ID, deleted names through the newest `infrahub.branch.deleted` event |
| Primary node | resource label `infrahub.node.id` | resource `prefect.resource.id` in (`infrahub.node.<id>`, `<id>`), which Prefect matches on the event's main related item (indexed), not on the event row (fast only with skip scan) |
| Parent event | related label `infrahub.event_parent.id` | related id `<parent_id>`, role `infrahub.ancestor_event`, plus today's label check for direct children |
| Merged, rebased, migrated by name | resource label `infrahub.branch.name` | resource id `infrahub.branch.<name>` |
| Level, event type, has children | unchanged | unchanged |

## Activities page request (changed)

| Field | Today | After |
|---|---|---|
| `count` | Not selected by the page, yet always computed by the task manager | Computed only when selected |
| Paging | `offset` | `until` = time of the oldest event shown; `offset` still accepted for API clients |
| Time window | Prefect's 180-day default | Windows 1 h, 1 d, 7 d, 30 d, then the activity log retention, counted back from `until` or now |
