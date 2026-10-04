# Contract: Task manager routes

Infrahub's routes on the task manager (`/api/infrahub/...` on the task-manager service), next to the existing `POST /infrahub/events/filter`. Same trust model as the existing route and Prefect's own API (internal network, no extra authentication).

## `POST /infrahub/task-history/cleanup`

Request:

```json
{"rewrite": false}
```

Response `202`:

```json
{"id": "<job id>", "state": "running", "rewrite": false, "cutoff": "2026-09-04T00:00:00Z", "deleted_runs": 0, "current_day": null, "size_before": null, "size_after": null, "not_rewritten": [], "error": null}
```

- Starts a cleanup job in the task manager, or returns the running job if this replica runs one.
- Response `409` `{"detail": "a cleanup is running elsewhere"}` when another replica holds the cleanup lock.
- The only input is `rewrite`; any other field is refused with `422`. The cutoff is now minus the task history retention read from the task manager's own configuration; nothing about the cutoff is taken from the request.
- No authentication, like Infrahub's existing task-manager route and Prefect's own API; this is a recorded constitution deviation (see plan.md).

## `GET /infrahub/task-history/cleanup/{id}`

Response `200`: the job, same shape as above, with `state` `running`, `completed` or `failed`. `404` `{"detail": "the cleanup is unknown to this task manager"}` when the job is unknown (for example after a task-manager restart).

- `rewrite` says whether the tables are rewritten: `false` from the start on SQLite, and `false` at the end when the deletes freed half of the runs or less. `not_rewritten` lists the tables a rewrite skipped.
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
