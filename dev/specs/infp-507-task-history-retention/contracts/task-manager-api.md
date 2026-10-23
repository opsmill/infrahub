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
{"id": "<job id>", "state": "running", "rewrite": "never", "cutoff": "2026-09-04T00:00:00Z", "deleted_runs": 0, "current_day": null, "size_before": null, "size_after": null, "rewritten": [], "mostly_live": [], "not_rewritten": [], "error": null}
```

- Starts a cleanup job in the task manager, or returns the running job if this replica runs one. A request whose `rewrite` is stronger than the running job's (`never` < `if_freed`) raises the job's to it; a weaker or equal one changes nothing. The response shows the job's `rewrite` after the request.
- Response `409` `{"detail": "a cleanup is running elsewhere"}` when another replica holds the cleanup lock.
- The only input is `rewrite`; any other field is refused with `422`. The cutoff is now minus the task history retention read from the task manager's own configuration; nothing about the cutoff is taken from the request.
- No authentication, like Infrahub's existing task-manager route and Prefect's own API; this is a recorded constitution deviation (see plan.md).

## `GET /infrahub/task-history/cleanup/{id}`

Response `200`: the job, same shape as above, with `state` `running`, `completed` or `failed`. `404` `{"detail": "the cleanup is unknown to this task manager"}` when the job is unknown (for example after a task-manager restart).

- `rewrite` is the job's mode: the one it was started with, raised by a request for `if_freed` while it runs. On Postgres, with `if_freed`, the job rewrites each of `flow_run`, `flow_run_state`, `task_run`, `task_run_state`, `log`, `artifact`, `events` and `event_resources` whose live rows hold less than half of its disk space, whoever deleted its rows and when: rows that Prefect's own cleanup deleted before the job started count too. A table's disk space is its main data and TOAST without indexes, and its live size the sum of `pg_column_size` per column plus 28 bytes a row, measured on a random sample of its pages above 10,000 pages. With `never`, and on SQLite, nothing is rewritten.
- The job decides about the rewrite with the mode it holds once its deletes end. When `if_freed` arrives after a decision with `never`, the job decides again before it completes. A job rewrites at most once.
- `rewritten` lists the tables rewritten, `mostly_live` the tables left because their live rows hold at least half of their disk space, and `not_rewritten` the tables whose rewrite still hit the lock timeout after its retries; all three are empty until the rewrite ran, with `never`, and on SQLite.
- `size_before` (before the deletes) and `size_after` (at the end) are the total size of the eight tables the job may rewrite, and `null` on SQLite.
- `current_day` is the day of end times being deleted, and once the deletes end the last such day; `null` before the first.
- `error` names the exception type and points to the task manager log, which holds the details.

## `GET /infrahub/task-history/size`

Response `200`:

```json
{"size": 23400000000}
```

- `size` is the disk space in bytes of the six task-history tables with their indexes, from `pg_total_relation_size`, which reads no table data; `null` on SQLite.
- The upgrade prints it with the command that returns the space. A task manager without this route answers `404`.

## `POST /infrahub/events/filter` (changed)

Request gains:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `include_total` | bool | `true` | Compute `total`; otherwise `total` is `null` (field added by PR #10379, kept under its name and default) |
| `retention_seconds` | int | Prefect's event retention, which the task manager sets from the activity log retention | Widest time window |

Behaviour changes:

- Events are read newest first, through the time windows 1 h, 1 d, 7 d, 30 d, then the retention, counted back from the filter's `occurred.until` or now, stopping at the first window that fills the page (or at the retention).
- With `offset`, a window counts as full only when it holds `offset + limit` matches, so position paging returns the same events as reading the whole retention.
- A filter that sets `occurred.since` is read from that start instead of the retention; the Infrahub server leaves `since` out of the request when the caller did not set it.
- A filter in ascending order is read in one query over the whole range.
- Every query runs with a plan per query (PR #10379).
- Response `total` becomes nullable.

## GraphQL `InfrahubEvent` (no schema change)

- `count` is computed only when selected.
- `branches`, `account__ids`, `primary_node__ids`, `parent__ids` and the branch-name `event_type_filter` keep their arguments and results; their matching changes as described in data-model.md.
- The Activities page passes `until` instead of `offset` for "load more"; it already does not select `count`.
