# Observability

> Part of: `dev/knowledge/backend/` | Related: [API Backpressure](api-backpressure.md), [Task Workers](task-workers.md), [Message Bus](message-bus.md), [Grafana dashboards](../../../development/grafana/AGENTS.md)

How the API server and the task workers produce traces, logs and Prometheus metrics, how a trace
follows one operation from an API request into the flow runs it starts and back, and which rules keep
the metrics correct when one API server runs several worker processes. Read it before adding a span,
a log field or a metric, or before changing how the processes start.

The three signals answer different questions about a slow instance:

- Traces: where the time of one request or flow run went, down to each database query.
- Logs: what one process did, joined to its trace by the `trace_id` field.
- Metrics: how much load the whole instance carries, and which pool, lock or queue is the limit.

The metric names, labels and buckets are listed for operators in
[Metrics](../../../docs/docs/deploy-manage/run-observe/metrics.mdx). This page does not repeat them.

## Traces

### Configuration

Tracing is off by default. `backend/infrahub/config.py::TraceSettings` (`INFRAHUB_TRACE_*`) holds the
switch, the exporter (console, or OTLP over gRPC or HTTP), the TLS options of the OTLP connection and
`sample_ratio`, the share of new traces to record (default 0.1). The API server
(`backend/infrahub/server.py::app_initialization`) and the task worker
(`backend/infrahub/workers/infrahub_async.py::InfrahubWorkerAsync.setup`) both call
`backend/infrahub/trace.py::configure_trace` when the switch is on. Each process builds its own
tracer provider, with the resource attributes `service.name`, `service.version` and `worker.id` (the
random identity of the process, also used as a metric label).

The Compose file of the observability stack, `development/docker-compose-observability-standalone.yml`,
turns tracing on for `infrahub-server` and `task-worker`. These settings come from
`development/docker-compose-observability-tracing.yml`, which `development/convert_compose_standalone.py`
adds to the standalone file. They are not in `development/docker-compose-observability.yml`, because
the development stack always loads that file and names its API service `server`: a block for
`infrahub-server` there creates a service with no image, and Compose rejects the project. The
development stack therefore does not turn tracing on; set the `INFRAHUB_TRACE_*` variables to trace it.

The API server instruments FastAPI, except `/metrics`, so every request gets a server span. Code adds
its own spans with `trace.get_tracer(__name__).start_as_current_span(...)`: each database query gets
an `execute_db_query_with_metadata` span with the query name and the row count, and GraphQL execution,
resolvers, diff computation and some mutations have named spans.

### How a trace crosses processes

A trace is one tree of spans with one trace ID. It crosses a process boundary only when the caller
sends its context, the W3C `traceparent` value, and the receiver starts its span under it.

```text
API request ──► API server span
                  └─ starts a flow run ──► Prefect stores the context in the
                                           `__OTEL_TRACEPARENT` label of the flow run
task worker ◄── reads the label when it starts the flow run span
  └─ SDK call back to the API ──► `traceparent` header ──► API server span in the same trace
```

- API server to task worker: Prefect carries the context with no Infrahub code involved. When the API
  server starts a deployment, Prefect writes the current context in the `__OTEL_TRACEPARENT` label of
  the new flow run. When the task worker runs the flow, Prefect starts the flow run span with that
  label as parent, so the flow run and its task runs join the trace of the API request.
- Task worker back to the API server: the Python SDK adds the `traceparent` header to each request
  when `opentelemetry-api` 1.33 or later is installed and a span is active, as in a task worker. The
  FastAPI instrumentation of the API server reads the header, so the request span and its database
  queries join the trace of the flow run.

### Sampling

The tracer provider uses `ParentBased(root=RatioSampler)`:

- A span with a parent follows the decision of the parent. A request that arrives with a sampled
  `traceparent` is recorded, one that arrives with a not-sampled `traceparent` is not, whatever the
  local ratio. So a trace that crosses processes is complete or absent, never partly recorded.
- A new root span is decided by `backend/infrahub/trace.py::RatioSampler`. It delegates to an
  OpenTelemetry `TraceIdRatioBased` sampler built for the ratio in force: the temporary ratio while its
  end time is in the future, the default ratio (`sample_ratio`) otherwise. The decision depends on the
  trace ID only, so two processes with the same ratio take the same decision for one trace ID.

One `RatioSampler` exists per process, in the module variable that
`backend/infrahub/trace.py::create_tracer_provider` sets. The functions `set_temporary_sample_ratio`,
`clear_temporary_sample_ratio` and `get_sample_ratio_state` act on it, and do nothing (or return
`None`) when tracing is off.

### Temporary sampling ratio

A super admin can record more traces for a limited time, for example during an incident, without
restarting any process, because a restart can remove the slow behaviour. The public REST endpoints are
in `backend/infrahub/api/troubleshooting.py`, under `/api/troubleshooting`, and are documented in the
OpenAPI schema. Each one requires the `super_admin` global permission; `PUT` and `DELETE` return an
error when tracing is off.

| Method and path | Effect |
|---|---|
| `GET /api/troubleshooting/trace-sample-ratio` | Returns the default ratio, the temporary ratio, its end time and the ratio in force, as seen by the process that handles the request |
| `PUT /api/troubleshooting/trace-sample-ratio` | Sets `ratio` (0 to 1) for `duration_seconds` (1 second to one day) on every process |
| `DELETE /api/troubleshooting/trace-sample-ratio` | Removes the temporary ratio on every process |

A `PUT` or a `DELETE` does three things:

1. It applies the change to the process that handles the request first, so the response already shows
   it.
2. It broadcasts `RefreshSettingsTraceSampleRatio` on the routing key
   `refresh.settings.trace_sample_ratio`. Every API server process and every task worker has its own
   queue bound to `refresh.settings.*`, and the handler
   `backend/infrahub/message_bus/operations/refresh/settings.py::trace_sample_ratio` applies or clears
   the ratio there and logs "Set the temporary trace sampling ratio" or "Cleared the temporary trace
   sampling ratio". An operator searches for these lines to check that every process applied the
   change. The message carries the end time, not the duration, so every process stops at the same
   moment.
3. It sends `TraceSampleRatioUpdatedEvent` (`infrahub.trace.sample_ratio_updated`) as an audit record,
   with the previous and the new ratio in force. A failure to send the event is logged and does not
   fail the request, because every process already received the change.

The temporary ratio lives in memory only. A process that starts or restarts while it is in force did
not receive the broadcast and uses the default ratio, and `GET` on that process shows the default.
Nothing in the database records the temporary ratio; the event is the only record of it.

### Masking span attributes

Spans can carry personal data and secrets: client IP addresses, URL query strings, account names and
tokens. Masking replaces each such value with `[MASKED]` and keeps the attribute name. Two places do
it, with the rules of `backend/infrahub/masking.py::MASKING_RULES`:

- `backend/infrahub/trace.py::MaskingSpanExporter` wraps the real exporter and masks the attributes of
  every span and of its events when the span is exported, in the background thread of the batch
  processor, so only sampled spans pay for it. In exception events, a URL query string inside
  `exception.message` and `exception.stacktrace` is replaced too. Masking at export is required
  because the HTTP instrumentation sets some attributes again after the span has started.
- The request hook that the API server passes to the FastAPI instrumentation
  (`backend/infrahub/server.py::server_request_hook`) masks the request span while it is still
  recording, so the single sign-on `code` and `state` URL parameters do not stay in the span in memory.

The rules:

- Client address keys (`net.peer.ip`, `client.address`, `client_ip`), `url.query` and `account_name`:
  the whole value is replaced.
- URL keys (`http.url`, `http.target`, `url.full`, `url`): the query string is replaced; the scheme,
  the hostname and the path stay readable.
- Any key whose lower-case name contains `token`, `password`, `secret`, `email`, `user_name` or
  `username`: the value is replaced.

The rules match on key names. A value placed under an unrelated key, or inside a span name, is not
masked, so do not put personal data in a span attribute in the first place. To mask a new kind of key,
add a rule to `MASKING_RULES`.

## Logs

`backend/infrahub/log.py::configure_logging` sets up structlog for every process. Its shared
processors run for structlog loggers and, through the formatter's `foreign_pre_chain`, for standard
library loggers that reach the root handler.

`add_trace_id` adds the trace ID of the current span as `trace_id` when the span is recording and the
line has no `trace_id` yet, so a line written during a sampled request or flow run can be joined to
its trace. A line written outside a recorded span has none. The API server's logging middleware also
sets `trace_id` in the log context of each request. Both write the ID as 32 lowercase hexadecimal
characters with leading zeros, the form Tempo and Grafana use.

Log lines are not masked. Masking every line costs time on every request, and the known leak, the user
name in the single sign-on login line, is fixed where the line is written: the line records the account
ID. Fix any other personal data or secret in a log line where the line is written; do not add a log
filter.

Prefect sends the records of its run loggers (`prefect.flow_runs` and `prefect.task_runs`) to the
Prefect API through its own handler, which does not run the structlog processors. These records do not
get a `trace_id`: the log lines shown in the Prefect UI cannot be joined to a trace.

## Metrics

### One scrape for several worker processes

The API server runs gunicorn with several Uvicorn worker processes
(`backend/infrahub/serve/gunicorn_config.py`). Each process holds its own metric values. When
`PROMETHEUS_MULTIPROC_DIR` is set, as the Infrahub image does, `prometheus_client` writes each value to
a file in that directory, and `/metrics` uses a `MultiProcessCollector` that reads the files of all
processes and combines them into one response. Without the variable, each process serves only its own
values, and a scrape reaches whichever process accepts the connection.

Two gunicorn hooks keep the directory consistent:

- `on_starting` deletes the files of the previous run once, in the master process, before any worker
  starts. A worker that cleared the directory at its own start would delete the values of the workers
  already running.
- `child_exit` calls `multiprocess.mark_process_dead` for a worker that stopped, which removes its
  values from the gauges in a `live*` mode.

The hooks run only when gunicorn starts with `--config backend/infrahub/serve/gunicorn_config.py`, as
the Compose files and the Helm charts do. A command line without `--config` keeps the files of stopped
workers. Counters and histograms are summed over all processes, including stopped ones, which is
correct for values that only grow.

### Every gauge declares how processes are combined

A gauge with no `multiprocess_mode` uses `all`: one series per process ID, kept after the process
stops. After a few worker restarts, a dashboard sums the last value of dead processes with the live
ones. Every gauge therefore declares its mode, and `backend/tests/unit/test_metrics_multiprocess.py`
fails when a gauge does not, or when a module defines a gauge and is not in the test's list.

Choose the mode from what the value means:

| Mode | Combined value | Use it for | Gauges that use it |
|---|---|---|---|
| `livesum` | Sum over live processes | A count or a capacity that adds up across processes | Admission `in_flight`, `waiters`, `max_concurrency`; task worker `flow_runs_in_progress` |
| `liveall` | One series per live process, labelled with its process ID | A value that belongs to one process and means nothing when added | Connection pool size and usage (one pool per process), admission `sustained_load_seconds` (one clock per process), `infrahub_info` |
| `min`, `max` | Lowest or highest value over all processes | The best or the worst process | Stress signal floor and window minimum (`min`), stress ratio (`max`) |

The `min` and `max` modes also read the files of stopped processes, so they can show a stopped
worker's last value until the API server restarts.

### Database metrics

`backend/infrahub/database/metrics.py` defines the database metrics, and
`backend/infrahub/database/__init__.py` records them:

- `infrahub_db_query_execution_seconds` per query name, recorded for each query.
- `infrahub_db_last_connection_pool_usage`: the number of connections in use, read from the driver's
  pool when a query starts. It is the last known value of each process, not a continuous measurement.
- `infrahub_db_connection_pool_size`: the configured maximum pool size of each process, set once when
  the driver is created, so usage can be compared with size on one panel.
- `infrahub_db_connection_wait_seconds`: the time each connection acquisition takes.

The neo4j driver (6.x) has no public hook for the acquisition time.
`backend/infrahub/database/connection_metrics.py::instrument_connection_pool` replaces the `acquire`
method of the driver's private pool (`driver._pool`) with a wrapper that measures the call: the wait
for a free connection and, when the pool has room, the time to open a new one. A failure inside the
wrapper is logged and never fails the acquisition. Check the wrapper when you upgrade the neo4j driver:
`backend/tests/unit/database/test_connection_metrics.py` builds a real driver and fails if its pool no
longer has an `acquire` method.

The stress signal gauges (`infrahub_db_reference_query_*`) are described in
[API Backpressure](api-backpressure.md#metrics).

### Duration buckets

A histogram counts a value above its highest bucket only in `+Inf`, so a percentile computed from it
cannot exceed that bucket. The buckets of the database query and lock durations reach 300 seconds,
those of the HTTP request and GraphQL query durations 1200 seconds, and the task worker start delay one
hour. When you change buckets, add bounds above the highest one and keep the existing lower bounds:
dashboards and alert rules select buckets by their `le` label, such as `le="0.5"`.

### Task worker metrics

The task worker serves its metrics on its own HTTP port (`INFRAHUB_METRICS_PORT`, 8000 by default).
`backend/infrahub/workers/metrics.py` defines two metrics, recorded when the worker starts a flow run:

- `infrahub_task_flow_run_start_delay_seconds` per flow and queue: the time between the expected start
  time of the flow run and the moment the worker starts it. A worker claims runs due within its
  prefetch window, so a run can start slightly early; a negative delay is recorded as 0.
- `infrahub_task_flow_runs_in_progress` per flow and queue: incremented when the flow run starts and
  decremented when it ends, including when it raises.

Together they show whether flow runs wait because the workers are busy or because nothing claims them;
see [Task Workers](task-workers.md) for how runs are claimed. A run with no queue name is labelled
`unknown`.

## Renaming a metric, a span or a dashboard UID

The bundled Grafana dashboards under `development/grafana/provisioning/dashboards/` query metrics,
span names and dashboard UIDs by name. When you rename or remove one of them, update the dashboards in
the same change, or their queries return nothing without an error. The editing rules for the
dashboards, including how to regenerate the standalone observability Compose file, are in
[development/grafana/AGENTS.md](../../../development/grafana/AGENTS.md). Also update the operator page
[Metrics](../../../docs/docs/deploy-manage/run-observe/metrics.mdx) when a metric or a bucket changes.

## Where to change what

| To change | Edit |
|---|---|
| Default sampling ratio or exporter options | `backend/infrahub/config.py::TraceSettings`, then regenerate the configuration reference |
| How new root traces are sampled | `backend/infrahub/trace.py::RatioSampler` |
| Tracing in the Compose file of the observability stack | `development/docker-compose-observability-tracing.yml`, then regenerate the standalone file |
| Which span attributes are masked | `backend/infrahub/masking.py::MASKING_RULES` |
| Log processors | `backend/infrahub/log.py::configure_logging` |
| How API server processes share metric files | `backend/infrahub/serve/gunicorn_config.py` |
| A new gauge | Its module, with a `multiprocess_mode`, and the module list in `backend/tests/unit/test_metrics_multiprocess.py` |
