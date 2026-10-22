# Contract: Trace Context, Trace ID and Links Between Traces and Logs

**Requirements**: FR-001 to FR-005, FR-032 | **Source**: design document D1, D3, B10, section 3

## Trace context from the SDK (dependency)

The Python SDK sends the W3C `traceparent` header on every request when OpenTelemetry is installed in
the caller's process, through the global OpenTelemetry propagator. The SDK declares no dependency on
OpenTelemetry: it imports it only when it is present. Without OpenTelemetry, it sends nothing new. The
FastAPI instrumentation of the API server already reads the header. This change is in
[infrahub-sdk-python](https://github.com/opsmill/infrahub-sdk-python), tracked in
[IFC-3419](https://opsmill.atlassian.net/browse/IFC-3419).

## Trace ID in log lines

| Process | Field | Format | When |
|---------|-------|--------|------|
| API server | `trace_id` | 32 lowercase hexadecimal characters, leading zeros, no `0x` | When the request span is recording |
| Task worker | `trace_id` | Same | When the current span is recording, unless the line already has one |

Example: `trace_id=0af7651916cd43dd8448eb211c80319c`. Before this change, the API server wrote
`0xaf7651916cd43dd8448eb211c80319c`.

This is a breaking change for operators who query or alert on `trace_id`. The changelog fragment is of
type `changed`, starts with `**Breaking:**`, gives both forms, and tells the operator to update their
queries and alerts.

## Grafana data sources (`development/grafana/provisioning/datasources/datasource.yml`)

| Data source | Setting | Value |
|-------------|---------|-------|
| Loki | Derived field `trace_id` | Matches `trace_id=<value>` in text lines and `"trace_id": "<value>"` in JSON lines, with or without `0x`, and links to the Tempo data source |
| Loki | Derived field `RequestID` | Removed |
| Tempo | `tracesToLogsV2` | `spanStartTimeShift: -1h`, `spanEndTimeShift: 1h`, `filterByTraceID: true`, query `{job=~".+"} \|= "${__trace.traceId}"` |
| Tempo | `tracesToMetrics`, `traceQuery` | Start shift `-1h`, end shift `1h` |

The query uses no label specific to Compose or Helm, so it works with any Loki that holds Infrahub's
logs. The documentation lists these settings for operators who run their own Grafana.

## Tracing in Compose with the observability stack (FR-032)

`development/docker-compose-observability.yml` sets, for `infrahub-server` and `task-worker`:

| Variable | Value |
|----------|-------|
| `INFRAHUB_TRACE_ENABLE` | `true` |
| `INFRAHUB_TRACE_EXPORTER_TYPE` | `otlp` |
| `INFRAHUB_TRACE_EXPORTER_PROTOCOL` | `grpc` |
| `INFRAHUB_TRACE_EXPORTER_ENDPOINT` | `http://infrahub-tempo:4317` |
| `INFRAHUB_TRACE_SAMPLE_RATIO` | `${INFRAHUB_TRACE_SAMPLE_RATIO:-0.1}` |

The root `docker-compose.yml` keeps `INFRAHUB_TRACE_ENABLE` at `false`. Whether the file served at
`https://infrahub.opsmill.io/?observability=true` applies this override is not known
([research.md](../research.md) R2).
