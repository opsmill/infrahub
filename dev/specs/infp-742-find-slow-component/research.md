# Research: Find the Slow Component of an Infrahub Instance

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-10-14

## Sources

- The design document [Diagnose a slow Infrahub instance](https://app.notion.com/p/opsmill/Diagnose-a-slow-Infrahub-instance-3f2228b8302581a08eeaf9fc23a7f2de),
  read in full on 2026-10-14. Decisions D1 to D9 and bugs B1 to B13 refer to it.
- The local draft on branch `dp-20261008-diagnose-slow-instance-infp-611-for-testing` (2 commits on
  top of `develop` at `179ec037a`). The card says it was tested on a development stack on 2026-10-13
  and 2026-10-14. It covers more than this feature: it also has the Redis exporter (D7) and the
  Grafana MCP server container (D10), which are out of scope here.
- The code on `develop` at `5ad35cd98`.

The INFP-611 plan, research and contracts were in `dev/specs/infp-611-diagnose-slow-instance/` as
files that were never committed. They were no longer on disk on 2026-10-14, so this research does
not use them.

## R1. Reuse the local draft

- **Decision**: Port the draft to this branch file by file, without the out-of-scope parts, and
  correct it where it differs from the spec.
- **Rationale**: The draft already implements most of the backend requirements, with tests. The table
  below lists what it has and what is missing.
- **Alternatives considered**: Merge the draft branch as it is. Rejected, because it contains D7 and
  D10, writes `***` instead of `[MASKED]` and lacks B10 and B13.

| Requirement | In the draft | Gap |
|-------------|--------------|-----|
| FR-003, FR-004 trace ID in task worker logs | `infrahub.log::add_trace_id` adds it | Writes `hex()`: `0x`, no leading zeros. FR-004 needs 32 characters |
| FR-005 trace and log links | No | `development/grafana/provisioning/datasources/datasource.yml` unchanged (B10) |
| FR-006, FR-007 default ratio, parent-based | `infrahub.trace::RatioSampler` in `ParentBased`, `TraceSettings.sample_ratio` | None |
| FR-008 query spans under the request span | `tests/component/api/test_trace_spans.py` | None |
| FR-009, FR-010 single sign-on | `infrahub.api.oidc`, `infrahub.api.oauth2` no longer record the token response or user info; log line has `account_id` | None |
| FR-012, FR-013, FR-013a masking | `infrahub.masking`, `infrahub.trace::MaskingSpanExporter`, `infrahub.log::LogMaskingFilter` and `mask_personal_data` | Marker is `***`; FR-013a needs `[MASKED]`. `infrahub.trace::mask_span` copies span events unchanged, so exception messages are not masked (critique E4). Log messages and exception text are not searched for URLs (critique E10) |
| FR-035 log line when a process applies a ratio | `infrahub.message_bus.operations.refresh.settings::trace_sample_ratio` logs "Set the temporary trace sampling ratio" and "Cleared the temporary trace sampling ratio" | None |
| FR-014, FR-015 buckets | Database, HTTP, lock and connection wait buckets | None |
| FR-016 API and GraphQL requests in HTTP metrics (B13) | No | The draft has no fix; fixed by upgrading `starlette-exporter` (R4) |
| FR-017 pool size, connection wait | `infrahub.database.connection_metrics::instrument_connection_pool` | None |
| FR-018 metric values kept across worker restarts (B9) | `infrahub.serve.gunicorn_config::on_starting`, `child_exit`; `multiprocess_mode` on gauges | None |
| FR-019 admission panel names (B5) | Dashboard JSON, test in `test_grafana_dashboards.py` | None |
| FR-020, FR-021 task worker saturation | `infrahub.workers.metrics`, used by `InfrahubWorkerAsync` | None |
| FR-022 to FR-025 dashboards | Dashboard JSON for Infrahub, Neo4j, both Prefect dashboards; Alloy drops the Neo4j target when empty | Check that every dashboard rule is met (R6) |
| FR-026 to FR-031 ratio without restart | `GET`, `PUT`, `DELETE /api/troubleshooting/trace-sample-ratio`, message `RefreshSettingsTraceSampleRatio`, event `TraceSampleRatioUpdatedEvent` | `infrahubctl` command is in the SDK (R3) |
| FR-032 Compose with the stack turns tracing on | No | R2 |
| FR-034 documentation | `dev/knowledge/backend/observability.md`, `metrics.mdx`, `observability-stack.mdx` | No page "Send Infrahub telemetry to your own monitoring" |

## R2. How Compose with the stack turns tracing on (FR-032)

- **Decision**: Add to `development/docker-compose-observability.yml` an `environment` block for the
  `infrahub-server` and `task-worker` services that sets `INFRAHUB_TRACE_ENABLE=true`,
  `INFRAHUB_TRACE_EXPORTER_TYPE=otlp`, `INFRAHUB_TRACE_EXPORTER_PROTOCOL=grpc` and
  `INFRAHUB_TRACE_EXPORTER_ENDPOINT=http://infrahub-tempo:4317`, so a Compose file that includes the
  stack overrides the defaults of `docker-compose.yml` (`INFRAHUB_TRACE_ENABLE` defaults to `false`).
  Regenerate `docker-compose-observability-standalone.yml` with
  `development/convert_compose_standalone.py`.
- **Rationale**: Section 3 of the design document. The root `docker-compose.yml` must keep tracing off,
  so an instance without the stack is unchanged.
- **Not known**: The file served at `https://infrahub.opsmill.io/?observability=true` is built by a
  service outside this repository. It is not known whether it merges the standalone file into the
  services of `docker-compose.yml` (so the override applies) or appends it. This must be checked with
  the owner of that service before FR-032 is considered done; a task records it. The owner is not
  known. The quickstart checks the file downloaded from that address, not only the files in
  `development/`.
- **Alternatives considered**: Turn tracing on in the root `docker-compose.yml`. Rejected: it would
  trace on every Compose instance, which FR-032 forbids.

## R3. Work in other repositories

- **Decision**: Two changes are in [infrahub-sdk-python](https://github.com/opsmill/infrahub-sdk-python)
  and are dependencies, each with its own pull request on the branch `infrahub-develop`:
  - The W3C `traceparent` header on every request when OpenTelemetry is installed (FR-001, D1):
    [IFC-3419](https://opsmill.atlassian.net/browse/IFC-3419). Not started.
  - An `infrahubctl` command to read, set and clear the temporary ratio (FR-026):
    [IFC-3420](https://opsmill.atlassian.net/browse/IFC-3420). Not started; not in the draft.
  - Both tickets were created on 2026-10-15 and implement INFP-742.
- **Rationale**: Root `AGENTS.md`: a submodule change merges upstream first, and the `python_sdk`
  pointer moves after.
- **Decided on 2026-10-15**: both changes are done in this feature, in the `python_sdk` submodule, one
  branch and one pull request each (the submodule is detached at `7ed9b39`, which
  `origin/infrahub-develop` contains). The branches are stacked: the IFC-3420 branch starts from the
  IFC-3419 branch, so one checkout of the submodule has both changes. Two independent branches would
  need a local branch that merges both for tests; IFC-3420 comes after IFC-3419 in the delivery order
  anyway. Both pull requests merge before the manual test. The SDK declares no OpenTelemetry dependency:
  it imports OpenTelemetry only when the caller's process has it, because its `AGENTS.md` asks before
  any new dependency and the ticket asks for the header only "when OpenTelemetry is installed". The
  header is added in `infrahub_sdk.client::BaseClient._request_headers`, which both the async and the
  sync client inherit. Not checked: that every request path of the SDK (GraphQL, REST, file upload)
  builds its headers there; a task checks it before the change.
- **Effect on this plan**: Stories 2 to 6 do not depend on the SDK. Story 1 scenarios 1, 3 and 8, and
  the `infrahubctl` part of story 6, cannot pass until the SDK change merges.

## R4. Why the HTTP metrics record no API or GraphQL request (B13)

- **Decision**: Upgrade `starlette-exporter` from 0.23 to 0.24, which supports FastAPI 0.137 and later.
  The pin in `pyproject.toml` becomes `>=0.24,<0.25`. Daniel approved this dependency change on
  2026-10-16 (`AGENTS.md`, "Ask First"). It is done in layer IFC-3428. `uv.lock` was regenerated with
  `uv` 0.11.8, the version CI uses (`.github/workflows/define-versions.yml`), and changes only
  `starlette-exporter`; `uv lock --check` passes with 0.11.8 and with 0.13.1.
- **Cause** (found on 2026-10-16): FastAPI 0.137 changed how `include_router` stores the routes of an
  included router ([fastapi#15745](https://github.com/fastapi/fastapi/pull/15745)). Before, the
  application router held a flat list of routes. Since 0.137, it holds one internal `_IncludedRouter`
  entry per included router, and that entry has no `path` attribute. Infrahub moved to FastAPI 0.141.1
  in commit `7e35e67b7`. After each response, `starlette_exporter` 0.23
  (`starlette_exporter.middleware::get_matching_route_path`) walks `router.routes` to find the route of
  the request. For a route of an included router, the matching entry is an `_IncludedRouter`, so the
  lookup returns no path. `PrometheusMiddleware` then drops the request, because its option
  `filter_unhandled_paths` is `True` by default. The `/api` router and the GraphQL router are both
  included with `include_router`, so none of their requests is recorded. Routes declared on the
  application itself, such as `/metrics` and the frontend route `/{rest_of_path:path}`, are recorded.
  The admission middleware and the other middlewares are not involved.
- **Evidence**: with the current code, `get_matching_route_path` returns `None` for `GET /api/config`
  and `POST /graphql/main`, and `/metrics` for `GET /metrics`. The two cases of
  `test_request_is_recorded_with_its_route_as_path` fail: the request count for `/api/config` and for
  `/graphql/{branch_name:path}` stays at 0.
- **Upstream fix**: `starlette-exporter` 0.24.0, released on 2026-07-29, "Support for FastAPI versions
  0.137.0 and up" ([release notes](https://github.com/stephenhillier/starlette_exporter/releases/tag/v0.24.0),
  [pull request #108](https://github.com/stephenhillier/starlette_exporter/pull/108),
  [issue #107](https://github.com/stephenhillier/starlette_exporter/issues/107)). It reads the routes
  through `iter_route_contexts`, which FastAPI 0.137.2 added for third-party tools. Checked after the
  upgrade: the two cases of `test_request_is_recorded_with_its_route_as_path` pass, so 0.24.0 also finds
  the routes of the `/api` routers, which are included in another included router.
- **Alternatives considered**: set `filter_unhandled_paths=False`. Rejected: the requests are then
  recorded with their raw path, one series per branch name or node ID. Measure requests with a new
  Infrahub middleware. Rejected: the upstream fix exists.

## R5. The trace ID format (FR-004)

- **Decision**: Change `infrahub.trace::get_traceid` and `infrahub.log::add_trace_id` to write
  `format(trace_id, "032x")`: 32 lowercase hexadecimal characters, no `0x`.
- **Rationale**: Tempo and Grafana use this form. With `hex()`, about 1 trace in 16 starts with a zero
  and a text search between the two forms fails (design document, B10).
- **Effect**: The API server log field `trace_id` changes format. The Loki data source matches both
  forms, so lines written before the upgrade still link (FR-005). This is a breaking change for
  operators who query or alert on `trace_id`. It gets its own `changed` fragment that starts with
  `**Breaking:**`, as the existing changelog entries do, gives the old and the new form, and tells the
  operator to update their queries. The upgrade notes repeat it.

## R6. The dashboard rule

- **Decision**: Keep the draft test `backend/tests/unit/test_grafana_dashboards.py`, which fails when a
  panel query has a fixed `job`, `instance` or `container` value, and when a panel has a misleading
  admission title. Extend it to check that no panel reads the old highest buckets (`le="1"` for
  database queries, `le="0.5"` for HTTP) as a limit (FR-015).
- **Not known**: The Prefect CPU and memory panels (B2) can only be checked on a Linux host: on Docker
  Desktop for macOS, cAdvisor sends no container names (design document, B2).

## R7. Task workers receive the ratio change

- **Decision**: Use the existing broadcast of `refresh.settings.*` messages, as the response delay
  does.
- **Checked**: `infrahub.services.adapters.message_bus::InfrahubMessageBus.event_bindings` contains
  `refresh.settings.*`, so every process that opens the events queue receives the message.
- **Not checked**: That a task worker process opens the events queue. The draft test
  `tests/unit/message_bus/test_operations.py` checks the handler, not the delivery. A component test
  must check delivery to a task worker before SC-004 is claimed.

## R8. Masked value (FR-013a)

- **Decision**: Change `infrahub.masking::MASKED_VALUE` from `***` to `[MASKED]`. Keep the key, and
  for URLs replace only the query string (`infrahub.masking::replace_url_query`).
- **Rationale**: Clarification of 2026-10-14.

## R9. The cost of tracing (SC-006)

- **Decision**: Measure before tracing is turned on for more operators, as a task with a recorded
  result, not as an automated test. Same load with tracing off and at ratio 0.1, compare API p95 and
  CPU. If either is above 5 %, lower the default in `TraceSettings.sample_ratio` and the Compose
  files.
- **Load**: chosen for this plan, not from a source. On the same host and the same data, run three
  times: 1,000 GraphQL queries of the same kind from 10 parallel clients, then one generator run that
  sends queries through the SDK. Record the host (CPU, memory), the Infrahub commit and the results in
  `specs/infp-742-find-slow-component/measurements.md`, so the measurement can be repeated.
- **Configurations to compare**:
  - `develop` before this feature (no masking, tracing off): the baseline.
  - This feature with tracing off: the cost of log masking alone, which runs on every instance.
  - This feature with tracing on at ratio 0.1: the cost SC-006 limits.
- **Note**: The design document notes that each query produces two spans today, which doubles the span
  count.

## R10. The Helm chart starts gunicorn with the Infrahub configuration (FR-018)

- **Checked on 2026-10-15**: in [infrahub-helm](https://github.com/opsmill/infrahub-helm), branch
  `stable`, the default `values.yaml` of both charts (`charts/infrahub` and
  `charts/infrahub-enterprise`) start the API server with `gunicorn --config
  …/backend/infrahub/serve/gunicorn_config.py`. So the gunicorn hooks that fix B9 also run on
  Kubernetes, as they do in Compose.
- **Not covered**: an operator who overrides `infrahubServer.args` without `--config`. Then the metric
  folder is not cleaned at start and stopped workers are not marked as stopped. The documentation of
  B9 names the `--config` option as required.

## R11. The log audit (FR-013)

- **Decision**: The masking rules use key names. Fields that the audit in
  [INFP-745](https://opsmill.atlassian.net/browse/INFP-745) lists are added to
  `infrahub.masking::MASKING_RULES` when it is done. This feature does not wait for it.

## R12. How other tools change the sampling ratio without a restart

Damien Garros asked on 2026-10-15 whether a runtime endpoint is industry practice, how other
applications do it, and why a normal setting is not enough
([Slack](https://opsmillworkspace.slack.com/archives/C08075KCU3A/p1792049481147779?thread_ts=1792048837.114539&cid=C08075KCU3A)).

- **Decision**: Keep both. `INFRAHUB_TRACE_SAMPLE_RATIO` is the normal setting and the default (D3).
  A public administration endpoint under `/api/troubleshooting` changes the ratio for a limited time
  (D4, FR-036).
- **Rationale**: The normal setting is the standard way, and Infrahub keeps it: OpenTelemetry SDKs read
  the ratio from configuration at startup, so a change needs a restart (design document, section 3).
  During an incident, a restart can remove the slow behaviour the operator wants to record. The
  endpoint covers only that case, and the end time brings the default back.
- **What other tools do** (searched on 2026-10-15):
  - **Central sampling server.** The SDK polls a sampling strategy from a central service, using the
    Jaeger remote sampling protocol. The OpenTelemetry Collector and Grafana Alloy can serve it
    ([Jaeger sampling](https://www.jaegertracing.io/docs/sampling/),
    [Alloy `otelcol.extension.jaeger_remote_sampling`](https://grafana.com/docs/alloy/next/reference/components/otelcol/otelcol.extension.jaeger_remote_sampling.md)).
    Go has a sampler for it. In the OpenTelemetry Python repositories, a code search found only an
    experimental configuration model (`ExperimentalJaegerRemoteSampler` in `opentelemetry-configuration`),
    no sampler that polls. Infrahub would have to write one, and every operator would have to run the
    extension in their collector.
  - **Vendor control panel.** Datadog changes sampling rates by service from its interface, without a
    redeploy, for users with a dedicated permission
    ([Datadog resource-based sampling](https://docs.datadoghq.com/tracing/guide/resource_based_sampling/)).
    Elastic describes a Java agent that changes the sampling ratio without a restart, and calls its
    first implementation experimental
    ([Elastic](https://www.elastic.co/observability-labs/blog/opentelemetry-java-agent-telemetry-policy)).
    Both need the vendor's own agent and backend.
  - **Management protocol.** OpAMP, the OpenTelemetry protocol to manage agents, may later change SDK
    settings such as sampling; the sources found say it is focused on the collector today
    ([OpenTelemetry blog](https://opentelemetry.io/blog/2022/opamp/)).
  - **Administration endpoint in the application.** Spring Boot Actuator changes a log level at runtime
    with `POST /actuator/loggers/<name>`, behind access control
    ([Spring Boot reference](https://docs.spring.io/spring-boot/4.2-SNAPSHOT/reference/actuator/loggers.html)).
    This is the closest precedent found for the Infrahub approach, for log levels rather than sampling.
    Infrahub already uses the same pattern for the response delay.
- **Alternatives considered**: A central sampling server (rejected: no Python sampler, and a new
  requirement on every operator's collector). A setting only (rejected: drops the card's must-have,
  raise the ratio without a restart). Tail sampling in the collector (rejected in D3: every span is
  still produced and sent).
- **Not checked**: Whether Kubernetes components offer a runtime endpoint for log verbosity; the search
  did not confirm it, so it is not used as an example.
- **Long-term solution, to track** (Damien Garros, 2026-10-15): a central sampling server, once the
  Python implementation of OpenTelemetry supports it. Tracked in
  [IFC-3423](https://opsmill.atlassian.net/browse/IFC-3423) (Draft). Status on 2026-10-15:
  - Feature request [opentelemetry-python-contrib#4774](https://github.com/open-telemetry/opentelemetry-python-contrib/issues/4774),
    "Jaeger remote sampler", opened on 2026-07-08, no comment.
  - Pull request [opentelemetry-python-contrib#4775](https://github.com/open-telemetry/opentelemetry-python-contrib/pull/4775)
    adds a package `opentelemetry-sampler-jaeger-remote`. Open, review required, marked stale by a bot
    once, last updated on 2026-10-12. Not merged, not released.
  - An older request, [opentelemetry-python-contrib#636](https://github.com/open-telemetry/opentelemetry-python-contrib/issues/636)
    (2021), asks for the same sampler in the SDK configuration. Open.
  - The OpenTelemetry specification defines the sampler with three settings: the endpoint, the
    polling interval, and the initial sampler used before the first configuration arrives
    ([specification](https://opentelemetry.io/docs/specs/otel/trace/sdk/#jaegerremotesampler)).
