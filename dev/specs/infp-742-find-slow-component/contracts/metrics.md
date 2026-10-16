# Contract: Prometheus Metrics

**Requirements**: FR-014, FR-016 to FR-018, FR-020 | **Source**: design document D5, D6, B9, B13

Metric names, labels and buckets are a public interface: operators build panels and alerts on them,
and the shipped dashboards read them. A rename is a breaking change for the operator.

## New metrics

| Metric | Type | Labels | Buckets (s) | Multiprocess mode | Recorded by |
|--------|------|--------|-------------|-------------------|-------------|
| `infrahub_db_connection_pool_size` | Gauge | `address` | - | `liveall` | API server and task worker, when the driver is created |
| `infrahub_db_connection_wait_seconds` | Histogram | none | 0.001, 0.01, 0.1, 0.5, 1, 5, 10, 30, 60 | - | Each connection acquisition |
| `infrahub_task_flow_run_start_delay_seconds` | Histogram | `flow`, `queue` | 1, 5, 15, 30, 60, 120, 300, 600, 1800, 3600 | - | Task worker, when it starts a flow run |
| `infrahub_task_flow_runs_in_progress` | Gauge | `flow`, `queue` | - | `livesum` | Task worker, while a flow run is in progress |

`queue` is `high`, `medium`, `low`, or `unknown` when the flow run has no work queue. `flow` is the
flow name, never a run ID.

## Changed buckets

| Metric | Highest bucket before | Buckets added (s) |
|--------|-----------------------|-------------------|
| `infrahub_db_query_execution_seconds` | 1 | 2.5, 5, 10, 30, 60, 120, 300 |
| `infrahub_request_duration_seconds` | 0.5 | 1, 2.5, 5, 10, 30, 60, 120, 300, 600, 1200 |
| `infrahub_lock_acquire_seconds` | 5 | 30, 60, 120, 300 |
| `infrahub_lock_reserved_duration_seconds` | 10 | 30, 60, 120, 300 |

Every new limit appears as an `le` label; a 30-second query is counted in `le="30"` (design document,
tests for D6).

## Changed multiprocess modes

With `PROMETHEUS_MULTIPROC_DIR` set, the API server combines the values of its gunicorn workers. Each
gauge declares how (FR-018):

| Metric | Mode | Why |
|--------|------|-----|
| `infrahub_db_last_connection_pool_usage`, `infrahub_db_connection_pool_size` | `liveall` | One pool per process; a stopped process no longer shows a value |
| `infrahub_info` | `liveall` | One series per live worker |
| `infrahub_admission_in_flight`, `infrahub_admission_waiters`, `infrahub_admission_max_concurrency` | `livesum` | Usage is compared with capacity summed over live workers |
| `infrahub_admission_sustained_load_seconds` | `liveall` | Each worker has its own clock |

gunicorn removes the metric files of a previous run once, when it starts, and marks a stopped worker as
dead. A worker no longer deletes the files of the others when it starts (B9).

## HTTP request metrics (B13)

After the fix, `infrahub_request_duration_seconds` and `infrahub_requests_total` count `/graphql/…`
and `/api/…` requests with their route as `path` (`group_paths=True`). The cause of the current gap is
not known ([research.md](../research.md) R4).
