# Observability

> Part of: `dev/knowledge/backend/` | Related: [Task Workers](task-workers.md), [Outbound TLS](tls.md), [Telemetry](telemetry.md)

How the API server and the task workers produce traces, metrics and logs, and how the local
development stack collects them. Read this before adding a span or a metric, before changing how a
process sets up tracing, or before upgrading FastAPI, Prefect or an OpenTelemetry package: each one
can add or remove spans without any Infrahub code changing. Anonymous usage telemetry is a separate
system, described in [Telemetry](telemetry.md).

## Traces

Tracing uses OpenTelemetry and is off by default. With `INFRAHUB_TRACE_ENABLE=true`, the API server
and each task worker set a global tracer provider when they start, through
`backend/infrahub/trace.py::configure_trace`:

- API server: during application startup, once per server process, with `service.name` set to
  `infrahub-server`.
- Task worker: during worker setup, with `service.name` set to `infrahub-task-worker`.
- Task manager (the Prefect server): never. Infrahub does not set up tracing in that container, and
  Prefect does not set a tracer provider of its own, so it records no spans.

Every span carries the resource attributes `service.name`, `service.version` and `worker.id`, plus
any `key=value` pairs from `OTEL_RESOURCE_ATTRIBUTES`. Spans leave the process in batches, so a span
reaches the collector a few seconds after it ends.

### Settings

| Setting | Default | Effect |
|---------|---------|--------|
| `INFRAHUB_TRACE_ENABLE` | `false` | Set up tracing at startup |
| `INFRAHUB_TRACE_EXPORTER_TYPE` | `console` | `console` prints spans to stdout, `otlp` sends them to a collector |
| `INFRAHUB_TRACE_EXPORTER_PROTOCOL` | `grpc` | `grpc` or `http/protobuf` for the OTLP exporter |
| `INFRAHUB_TRACE_EXPORTER_ENDPOINT` | none | Collector address, required with `otlp` |
| `INFRAHUB_TRACE_INSECURE`, `INFRAHUB_TRACE_TLS_CA_BUNDLE`, `INFRAHUB_TRACE_TLS_INSECURE` | | TLS to the collector, see [Outbound TLS](tls.md) |
| `OTEL_TRACES_SAMPLER`, `OTEL_TRACES_SAMPLER_ARG` | `parentbased_always_on` | Read by the OpenTelemetry SDK, which picks the sampler from them |

The full descriptions are in `docs/docs/reference/configuration.mdx`, generated from
`backend/infrahub/config.py::TraceSettings`.

### What records spans

- API requests: the OpenTelemetry contrib package `opentelemetry-instrumentation-fastapi` wraps the
  API when `backend/infrahub/server.py` is imported. Each request records one server span plus
  internal `http receive` and `http send` spans, all in the scope
  `opentelemetry.instrumentation.fastapi`. `/metrics` is excluded, and every request span carries a
  `worker` attribute.
- Infrahub code: spans opened with `trace.get_tracer(__name__).start_as_current_span(...)`, around
  GraphQL execution (`execute_graphql`), the GraphQL resolvers, `Query.execute`, each database query
  (`execute_db_query_with_metadata`, with the Cypher text in the `query` attribute), diff
  calculation, branch creation and SSO sign-in. Their scope is the module name, such as
  `infrahub.core.query`.
- Prefect runs on task workers: Prefect records a span for each flow and task run in the scope
  `prefect`, such as `Sync Git Repositories`, through the global provider.
- Prefect's health check on task workers: covered in the next section.

The trace ID also reaches other signals. API request logs carry it as `trace_id`, and each database
transaction carries the current span ID as `infrahub_id` in its Neo4j transaction metadata, so a
query seen in Neo4j can be matched to the span that ran it.

### FastAPI's built-in telemetry stays off

Since 0.142.0, FastAPI traces every request of every FastAPI app in a process that has a tracer
provider: one span for the request and, for a route declared with FastAPI, one span for each step
inside it (`fastapi.dependencies`, `fastapi.endpoint` and, when the endpoint returns data to
serialize, `fastapi.serialization`).

- The API turns it off: `FastAPI(telemetry={"tracing": False, "metrics": False, "logs": False})`.
  FastAPI also skips its tracing when it finds the contrib package's middleware in the app, but the
  explicit setting does not depend on that detection. `backend/tests/unit/test_server.py` fails if
  FastAPI records any span for an API request, including when the contrib middleware is missing.
- The task worker cannot turn it off for Prefect's health-check server. `prefect worker start
  --with-healthcheck` runs a plain FastAPI app that Prefect creates, answering `GET /health` in the
  worker process. With the worker's global provider set, each health check would record three spans
  (`GET /health`, `fastapi.dependencies` and `fastapi.endpoint`).
  `backend/infrahub/trace.py::ExcludeServerPathsSampler` drops them. It drops the request span for
  `/health` and every span whose parent in the same process was not sampled, and leaves every other
  decision to the sampler chosen from `OTEL_TRACES_SAMPLER`. Without the parent check, samplers
  that ignore the parent's decision, such as `always_on` and `traceidratio`, would still record the
  inner spans, each without its request span.

The sampler matches the path text Prefect uses. If Prefect renamed the route, health checks would
record spans again.

### Adding a span

Open a span with the module's tracer, and use the helpers in `backend/infrahub/trace.py` to add
attributes, events or an exception to the current span:

```python
from opentelemetry import trace

from infrahub.trace import set_span_data


@trace.get_tracer(__name__).start_as_current_span("branch_create")
async def create_branch(name: str) -> None:
    set_span_data(key="branch", value=name)
```

### Testing span output

Tests that count spans install a `TracerProvider` with an in-memory exporter. The global provider can
only be set once per process, so the fixture in `backend/tests/unit/test_server.py` resets the SDK's
set-once guard with `monkeypatch` and rebuilds the API's middleware stack. Copy that fixture rather
than calling `configure_trace` from a test.

## Metrics

Metrics use the Prometheus client, independent of the trace settings:

- API server: `starlette_exporter` middleware records request counts and durations with the prefix
  `infrahub`, grouped by route and skipping `/health`, served at `/metrics`. The server processes
  share their samples through `PROMETHEUS_MULTIPROC_DIR`, which the image sets.
- Task worker: worker setup starts a separate metrics endpoint on `INFRAHUB_METRICS_PORT`
  (default `8000`).
- Infrahub's own metrics are module-level `prometheus_client` objects, for example in
  `backend/infrahub/database/metrics.py`, `backend/infrahub/graphql/metrics.py` and
  `backend/infrahub/api/admission/metrics.py`.

## Logs

Logs are written to standard error through structlog. Each API request binds `request_id`, `app`,
`worker` and, when tracing is on, `trace_id` to every log line written while handling it.

## Local observability stack

The development compose files carry the collectors behind two profiles, in
`development/docker-compose-observability.yml`:

- `INFRAHUB_DEBUG=true` adds the `debug` profile: Grafana on port 3500, Prometheus on 9090, Loki on
  3100, Alloy on 12345, a Prefect exporter on 4201, node-exporter and cAdvisor. Alloy scrapes the
  server, the task workers, the message queue, the database and the exporters, writes the samples to
  Prometheus, and ships the logs of the stack's containers to Loki.
- `INFRAHUB_DEBUG_TRACE=true`, together with `INFRAHUB_DEBUG=true`, adds the `trace` profile: Tempo
  on port 3200. It also sets the `INFRAHUB_TRACE_*` variables so the server and the task workers
  send spans to Tempo over OTLP gRPC.

Grafana has Prometheus, Loki and Tempo data sources and the dashboards under
`development/grafana/provisioning/dashboards/`; see `development/grafana/AGENTS.md` before editing
them. Without Grafana, Tempo's HTTP API lists spans directly: `GET /api/search` with
`tags=service.name=<service>` finds traces, and `GET /api/traces/<trace id>` returns one.

The deployment guide for operators is `docs/docs/deploy-manage/install-configure/install/observability-stack.mdx`.
