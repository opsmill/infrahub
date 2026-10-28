# Contract: Task manager routes

Infrahub's routes on the task manager (`/api/infrahub/...` on the task-manager service), next to the existing `POST /infrahub/events/filter`. Same trust model as the existing route and Prefect's own API (internal network, no extra authentication).

## `POST /infrahub/task-history/cleanup`

Request:

```json
{"rewrite": "never"}
```

`rewrite` is `never` (default) or `if_freed`.

Response `202`:

```json
{"id": "<job id>", "state": "running", "rewrite": "never", "cutoff": "2026-09-04T00:00:00Z", "deleted_runs": 0, "current_day": null, "size_before": null, "size_after": null, "rewritten": [], "mostly_live": [], "not_rewritten": [], "timed_out": [], "failed": [], "error": null}
```

- Starts a cleanup job in the task manager, or returns the running job if this replica runs one. A request whose `rewrite` is stronger than the running job's (`never` < `if_freed`) raises the job's to it; a weaker or equal one changes nothing. The response shows the job's `rewrite` after the request.
- Response `409` `{"detail": "a cleanup is running elsewhere"}` when another replica holds the cleanup lock.
- Response `403` `{"detail": "Old task runs are not deleted, because PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on flow_runs"}` when the vacuum switch, as Prefect parses it, does not turn on `flow_runs`, so Prefect's own cleanup deletes no old task runs. For a vacuum type that Prefect does not accept, the detail is `Old task runs are not deleted, because PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED is not valid: <Prefect's error>`. No job starts and no lock is taken.
- The only input is `rewrite`; any other field is refused with `422`. The cutoff is now minus the task history retention read from the task manager's own configuration; nothing about the cutoff is taken from the request.
- No authentication, like Infrahub's existing task-manager route and Prefect's own API; this is a recorded constitution deviation (see plan.md).

## `GET /infrahub/task-history/cleanup/{id}`

Response `200`: the job, same shape as above, with `state` `running`, `completed` or `failed`. `404` `{"detail": "the cleanup is unknown to this task manager"}` when the job is unknown (for example after a task-manager restart).

- `rewrite` is the job's mode: the one it was started with, raised by a request for `if_freed` while it runs. On Postgres, with `if_freed`, the job rewrites each of `flow_run`, `flow_run_state`, `task_run`, `task_run_state`, `log`, `artifact`, `events` and `event_resources` whose live rows hold less than half of its disk space, whoever deleted its rows and when: rows that Prefect's own cleanup deleted before the job started count too. A table's disk space is its main data and TOAST without indexes, and its live size the sum of `pg_column_size` per column plus 28 bytes a row, measured on a random sample of its pages above 10,000 pages. With `never`, and on SQLite, nothing is rewritten.
- The job decides about the rewrite with the mode it holds once its deletes end. When `if_freed` arrives after a decision with `never`, the job decides again before it completes. A job rewrites at most once.
- `rewritten` lists the tables rewritten, `mostly_live` the tables left because their live rows hold at least half of their disk space, `not_rewritten` the tables whose rewrite still hit the lock timeout after its retries, `timed_out` the tables whose rewrite was stopped at its statement timeout, which leaves them as they were, and `failed` the tables whose rewrite failed with a database error, such as no free disk for the copy, which leaves them as they were; after each table in the last three lists the job goes on with the next table, and a lost database connection or an error that did not come from the database server fails the job; each table joins its list as soon as its rewrite ends, so a failed job lists the tables its rewrite finished; all five are empty with `never` and on SQLite.
- `size_before` (before the deletes) and `size_after` (at the end) are the total size of the eight tables the job may rewrite, and `null` on SQLite.
- `current_day` is the day of end times being deleted, and once the deletes end the last such day; `null` before the first.
- `error` names the exception type and points to the task manager log, which holds the details. Two cases differ: a job that could not confirm it still holds the cleanup lock, which it checks every 30 s, stops its current step, and its `error` is "The cleanup stopped, because it could not confirm that it holds the cleanup lock; start it again"; a job whose delete transaction waited more than 60 s for a lock that another session holds rolls that transaction back, and its `error` is "The runs that ended on <day> stayed locked by another session for more than 60 seconds, so the cleanup stopped".

## `GET /infrahub/task-history/size`

Response `200`:

```json
{"size": 23400000000, "old_runs": 1234, "old_runs_limit_reached": false, "deletion_off_reason": null}
```

- `size` is the disk space in bytes of the six task-history tables with their indexes, from `pg_total_relation_size`, which reads no table data; `null` on SQLite.
- `old_runs` is the number of finished top-level runs older than the task history retention, the runs a cleanup would delete now, counted up to 100,000; `old_runs_limit_reached` is `true` when there are more. The count works on SQLite too.
- `deletion_off_reason` is `null` when the vacuum switch, as Prefect parses it, turns on `flow_runs`. Otherwise it says why old task runs are not deleted, as the `403` of the cleanup start does after `because`, for example `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on flow_runs`. The count of old runs does not change with it.
- The upgrade prints the size and the count with the command that returns the space, or with the reason when `deletion_off_reason` is set. A task manager without this route answers `404`.

## `POST /infrahub/events/filter` (changed)

Request gains:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `include_count` | bool | `false` | Compute `total`; otherwise `total` is `null` |
| `retention_seconds` | int | activity log retention of the task manager | Widest time window |

Behaviour changes:

- Events are read newest first, through the time windows 1 h, 1 d, 7 d, 30 d, then the retention, counted back from the filter's `occurred.until` or now, stopping at the first window that fills the page (or at the retention).
- With `offset`, a window counts as full only when it holds `offset + limit` matches, so position paging returns the same events as reading the whole retention.
- Every query runs with a plan per query (PR #10379).
- Response `total` becomes nullable.

## GraphQL `InfrahubEvent` (no schema change)

- `count` is computed only when selected.
- `branches`, `account__ids`, `primary_node__ids`, `parent__ids` and the branch-name `event_type_filter` keep their arguments and results; their matching changes as described in data-model.md.
- The Activities page passes `until` instead of `offset` for "load more"; it already does not select `count`.
