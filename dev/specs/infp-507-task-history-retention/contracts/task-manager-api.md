# Contract: Task manager routes

Infrahub's routes on the task manager (`/api/infrahub/...` on the task-manager service), next to the existing `POST /infrahub/events/filter`. Same trust model as the existing route and Prefect's own API (internal network, no extra authentication).

## `POST /infrahub/task-history/cleanup`

Request:

```json
{"rewrite": "never"}
```

`rewrite` is `never` (default), `if_freed` or `always`.

Response `202`:

```json
{"id": "<job id>", "state": "running", "rewrite": "never", "rewritten": false, "cutoff": "2026-09-04T00:00:00Z", "deleted_runs": 0, "current_day": null, "size_before": null, "size_after": null, "not_rewritten": [], "error": null}
```

- Starts a cleanup job in the task manager, or returns the running job if this replica runs one. A request whose `rewrite` is stronger than the running job's (`never` < `if_freed` < `always`) raises the job's to it; a weaker or equal one changes nothing. The response shows the job's `rewrite` after the request.
- Response `409` `{"detail": "a cleanup is running elsewhere"}` when another replica holds the cleanup lock.
- The only input is `rewrite`; any other field is refused with `422`. The cutoff is now minus the task history retention read from the task manager's own configuration; nothing about the cutoff is taken from the request.
- No authentication, like Infrahub's existing task-manager route and Prefect's own API; this is a recorded constitution deviation (see plan.md).

## `GET /infrahub/task-history/cleanup/{id}`

Response `200`: the job, same shape as above, with `state` `running`, `completed` or `failed`. `404` `{"detail": "the cleanup is unknown to this task manager"}` when the job is unknown (for example after a task-manager restart).

- `rewrite` is the job's mode: the one it was started with, raised by any stronger request while it runs. On Postgres the tables are rewritten after the deletes with `always`, never with `never`, and with `if_freed` only when more than half of the tables' disk space is free after the deletes, whoever deleted the runs and when: runs that Prefect's own cleanup deleted before the job started count too. The free space is measured on `flow_run`, whose rows the other tables lose with their runs, as the table's size on disk against the size of its live rows. Nothing is rewritten on SQLite.
- The job decides about the rewrite with the mode it holds once its deletes end. When a stronger mode arrives after that decision, the job decides again before it completes, measuring the free space again. Tables a job already rewrote are not rewritten again.
- `rewritten` says whether the tables were rewritten; `false` until the rewrite ran. `not_rewritten` lists the tables a rewrite skipped.
- `size_before` (before the deletes) and `size_after` (at the end) are `null` on SQLite.
- `current_day` is the day of end times being deleted, and once the deletes end the last such day; `null` before the first.
- `error` names the exception type and points to the task manager log, which holds the details.

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
