---
description: "Task list for INFP-742: find the slow component of an Infrahub instance"
---

# Tasks: Find the Slow Component of an Infrahub Instance

**Input**: Design documents from `specs/infp-742-find-slow-component/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required. The constitution (Principle IV) requires tests for every feature, and the spec
names tests (FR-008, SC-005, SC-007). Write each test task before the implementation task it covers,
and check that it fails first.

**Organization**: Tasks are grouped by user story. Story phases follow the priorities of the spec, with
one change of order inside P1: story 2 (masking) comes before story 1 (one trace), because FR-011
requires the single sign-on fixes to ship before tracing is turned on for more operators.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: The user story of the spec (US1 to US6)

## Conventions for every task

- **The draft**: branch `dp-20261008-diagnose-slow-instance-infp-611-for-testing`. "Port from the
  draft" means: read the file with `git show <draft>:<path>`, copy only what the task names, and change
  it where the task says. Never merge or cherry-pick the draft: it contains out-of-scope work (Redis
  exporter, Grafana MCP server) and differs from the spec (`***` instead of `[MASKED]`).
- **Out of scope, never port**: `development/grafana-mcp/`, the `infrahub-grafana-mcp` and
  `infrahub-redis-exporter` services, the Redis scrape in `development/alloy/config.alloy`, the "Redis"
  row of `infrahub_monitoring.json`, and the changelog fragments `+grafana-mcp-server.added.md` and
  `+observability-chart-version.fixed.md`.
- **Code style**: load `dev/guidelines/backend/python.md`, `dev/guidelines/backend/testing.md` and
  `dev/guidelines/code-doc-style.md` before writing backend code or tests.
- **Changelog**: one Towncrier fragment per user-visible change in `changelog/`, written with the
  `creating-changelog-entries` skill. SDK fragments go in `python_sdk/changelog/`.
- **Submodule pointer**: while the SDK branches are not merged, `python_sdk` shows as modified in
  `git status`. Never stage it in an Infrahub commit before T086.
- **Push and pull requests**: push a branch or open a pull request only when Daniel asks.

---

## Phase 1: Setup

**Purpose**: Prepare the branches and confirm the starting point.

- [ ] T001 Check that the Infrahub branch is `dp-20261014-find-slow-component-infp-742` and that the draft branch `dp-20261008-diagnose-slow-instance-infp-611-for-testing` exists locally (`git rev-parse --verify`)
- [ ] T002 In `python_sdk/`, run `git fetch origin infrahub-develop` and create the branch `dp-20261015-trace-context-ifc-3419` from `origin/infrahub-develop` (IFC-3419; research R3)
- [ ] T003 [P] In `python_sdk/`, run `uv sync --all-groups --all-extras`, then `uv run pytest tests/unit/` to record that the SDK unit tests pass before any change
- [ ] T004 [P] Run `uv run pytest backend/tests/unit/test_trace.py backend/tests/unit/test_log.py backend/tests/unit/test_lock.py` to record that these backend tests pass before any change

---

## Phase 2: Foundational

**Purpose**: Test helpers that several stories use.

- [ ] T005 [P] Port `backend/tests/helpers/trace.py` from the draft (in-memory span exporter and tracer provider fixtures for tests)
- [ ] T006 [P] Port `backend/tests/helpers/metrics.py` from the draft (helpers that read metric samples from the Prometheus registry)

**Checkpoint**: Test helpers exist; story phases can start.

---

## Phase 3: User Story 2 - Spans and logs hold no secrets or personal data (Priority: P1)

**Goal**: Before a span or a log line leaves the API server or a task worker, tokens, user names,
email addresses, client IP addresses and URL query strings read `[MASKED]`; single sign-on records no
token, code, state or user name (FR-009 to FR-013a; [contracts/masking.md](contracts/masking.md)).

**Independent Test**: With tracing on, log in through single sign-on and send requests with query
strings; search the trace store and the log store for the secrets (quickstart, manual check 4).

### Tests for User Story 2

- [ ] T007 [P] [US2] Write unit tests for the masking rules in `backend/tests/unit/test_masking.py`: each rule of [data-model.md](data-model.md) "Masking rule" gives `[MASKED]` and keeps the key; a URL keeps its path and gets `?[MASKED]`; a URL without a query string is unchanged; nested mappings and lists are masked; the input mapping is not changed; Cypher text (`query`) and `query_name` are unchanged; a free-text message that contains a URL with a query string gets the query string replaced
- [ ] T008 [P] [US2] Write a unit test in `backend/tests/unit/test_masking.py` that lists the attribute and field keys Infrahub sets on its own spans and log lines (start from the draft keys: `query`, `query_name`, `rows`, `provider_name`, `sso_group_count`, `account_id`, `request_id`, `trace_id`, `branch`, `groups`) and fails when a masking rule would mask one of them (critique E1)
- [ ] T009 [P] [US2] Port the masking exporter tests from the draft `backend/tests/unit/test_trace.py` (tests of `mask_span` and `MaskingSpanExporter`) into `backend/tests/unit/test_trace.py`, with `[MASKED]` as the expected value, and add a test: an exception event whose `exception.message` contains `https://idp.example.com/token?code=abc&state=xyz` is exported with `https://idp.example.com/token?[MASKED]` (FR-012, spec story 2 scenario 7)
- [ ] T010 [P] [US2] Port the log masking tests from the draft `backend/tests/unit/test_log.py` (structlog processor `mask_personal_data`, `LogMaskingFilter` on a standard logging record with `msg`, `args` and `extra`) into `backend/tests/unit/test_log.py`, with `[MASKED]`, and add tests: a log line whose message or exception text contains a URL with `code` and `state` shows `?[MASKED]` (FR-013, story 2 scenario 9); a record that reaches a handler registered like the Prefect API handler is masked (story 2 scenario 8, critique E5)
- [ ] T011 [P] [US2] Port `backend/tests/component/api/test_sso_token_telemetry.py` from the draft: after an OIDC and an OAuth2 login, no span contains the token response or the user information, the token endpoint span has the path and no `code` or `state`, and the login log line has `account_id` and no user name (FR-009, FR-010)

### Implementation for User Story 2

- [ ] T012 [US2] Create `backend/infrahub/masking.py` from the draft, with `MASKED_VALUE = "[MASKED]"` (research R8); keep `MaskingRule`, `MASKING_RULES`, `mask_value`, `mask_nested`, `mask_mapping`, `replace_url_query`; add a function that replaces the query string of every URL found in a free-text string, for use on exception messages and log messages
- [ ] T013 [US2] In `backend/infrahub/trace.py`, port `mask_span` and `MaskingSpanExporter` from the draft and wrap the exporter in `create_tracer_provider`; extend `mask_span` so the attributes of every span event are masked with the same rules and URL query strings inside `exception.message` are replaced (FR-012; critique E4)
- [ ] T014 [US2] In `backend/infrahub/log.py`, port `LogMaskingFilter`, `add_log_masking_filter`, `install_log_masking_filter` and the structlog processor `mask_personal_data` from the draft, and register them as the draft does; extend both so the message and the exception text of every line have URL query strings replaced (FR-013)
- [ ] T015 [US2] In `backend/infrahub/workers/infrahub_async.py`, port the call `add_log_masking_filter(api_handler)` from the draft, so flow run logs sent to the Prefect server are masked (FR-013)
- [ ] T016 [P] [US2] In `backend/infrahub/api/oidc.py` and `backend/infrahub/api/oauth2.py`, port the draft changes: no `token_request_data` or `account_name` span attribute with the provider responses; record `provider_name` and `sso_group_count`; the "SSO user authenticated" log line has `account_id` and `groups`, not `user_name` (FR-009, FR-010)
- [ ] T017 [P] [US2] Add changelog fragments: port `changelog/+sso-secrets-in-traces.security.md`, `changelog/+log-field-masking.security.md` and `changelog/+trace-attribute-masking.added.md` from the draft and correct them to say `[MASKED]`, span events, and URL query strings in log messages
- [ ] T018 [US2] Run T007 to T011 and `uv run invoke format lint`; all pass

**Checkpoint**: Story 2 is complete and testable on its own. FR-011 is met: masking can ship before
tracing is turned on for more operators.

---

## Phase 4: User Story 1 - Follow a slow background task to its queries in one trace (Priority: P1) 🎯 MVP

**Goal**: A flow run, its SDK calls and their database queries form one trace; task worker logs carry
the trace ID; Grafana links traces and logs; Compose with the observability stack turns tracing on at
the default ratio (FR-001 to FR-008, FR-032; [contracts/trace-log-links.md](contracts/trace-log-links.md)).

**Independent Test**: With tracing on, run a generator that sends named queries through the SDK; open
its trace and its task worker logs in Grafana (quickstart, manual checks 1 to 3).

### SDK change (IFC-3419), in `python_sdk/` on branch `dp-20261015-trace-context-ifc-3419`

- [ ] T019 [US1] In `python_sdk/`, check that every request path of the SDK (GraphQL queries, REST calls, file uploads, async and sync) builds its headers with `infrahub_sdk.client::BaseClient._request_headers` or `_merge_request_headers`; list any path that does not, in the commit message of T022 (research R3, not checked yet)
- [ ] T020 [P] [US1] Write unit tests in `python_sdk/tests/unit/sdk/test_trace_context.py`: with OpenTelemetry importable and a recording span, the request headers contain a valid `traceparent` for that span; with no active span, no `traceparent`; with OpenTelemetry not importable (patch the import), no `traceparent` and no error; same for the async and the sync client
- [ ] T021 [US1] In `python_sdk/infrahub_sdk/client.py`, add the `traceparent` header in `BaseClient._request_headers` (and in any path found in T019) through the OpenTelemetry global propagator, importing OpenTelemetry only when it is installed; add no dependency to `python_sdk/pyproject.toml` (FR-001)
- [ ] T022 [US1] In `python_sdk/`, add a changelog fragment in `python_sdk/changelog/` ("The SDK sends the W3C `traceparent` header when OpenTelemetry is installed"), run `uv run invoke format lint-code` and `uv run pytest tests/unit/`, then commit on `dp-20261015-trace-context-ifc-3419` with a conventional message ending in `[IFC-3419]`
- [ ] T023 [US1] Ask Daniel whether to push `dp-20261015-trace-context-ifc-3419` and open its pull request on `infrahub-develop` in `opsmill/infrahub-sdk-python` now, so the review runs while the Infrahub work continues (plan, delivery order step 7)

### Tests for User Story 1 (Infrahub)

- [ ] T024 [P] [US1] Port `backend/tests/component/api/test_trace_spans.py` from the draft: each database query span of an API request is a child of the request span (FR-008)
- [ ] T025 [P] [US1] Port the sampler tests from the draft `backend/tests/unit/test_trace.py` (`RatioSampler` default ratio, parent-based behaviour) and `backend/tests/unit/config/test_trace_settings.py` (`sample_ratio` from 0 to 1, default 0.1, values outside rejected): ratio 0.5 records about half of new root traces; a request with a sampled parent is always recorded (FR-006, FR-007)
- [ ] T026 [P] [US1] Write unit tests in `backend/tests/unit/test_trace.py` and `backend/tests/unit/test_log.py`: `get_traceid` and the task worker `trace_id` field are 32 lowercase hexadecimal characters with leading zeros and no `0x`, including a trace ID that starts with `0` (FR-004); a task worker log line inside a recording span carries `trace_id`, and a line outside a span has none (FR-003)
- [ ] T027 [P] [US1] Write a unit test in `backend/tests/unit/test_grafana_datasources.py` that loads `development/grafana/provisioning/datasources/datasource.yml` and checks: the Loki derived field matches `trace_id=<32 hex>`, `trace_id=0x<hex>` and `"trace_id": "<32 hex>"`; no `RequestID` derived field; the Tempo `tracesToLogsV2` has `spanStartTimeShift: -1h`, `spanEndTimeShift: 1h`, `filterByTraceID: true` and a query with `{job=~".+"}`; `tracesToMetrics` and `traceQuery` have start `-1h` and end `1h` (FR-005)

### Implementation for User Story 1 (Infrahub)

- [ ] T028 [US1] In `backend/infrahub/config.py`, port `TraceSettings.sample_ratio` from the draft (default 0.1, from 0 to 1, with its description) (FR-006)
- [ ] T029 [US1] In `backend/infrahub/trace.py`, port `RatioSampler` and `SampleRatioState` without the temporary ratio methods (those come in T070), use `ParentBased(root=RatioSampler(...))` in `create_tracer_provider`, and add the `sample_ratio` parameter to `create_tracer_provider` and `configure_trace` (FR-006, FR-007)
- [ ] T030 [US1] Pass `sample_ratio=config.SETTINGS.trace.sample_ratio` to `configure_trace` in `backend/infrahub/server.py` (`app_initialization`) and in `backend/infrahub/workers/infrahub_async.py`, as the draft does
- [ ] T031 [US1] In `backend/infrahub/trace.py`, change `get_traceid` to return `format(trace_id, "032x")` (research R5); in `backend/infrahub/log.py`, port the structlog processor `add_trace_id` from the draft with the same format and register it as the draft does (FR-003, FR-004)
- [ ] T032 [US1] In `development/grafana/provisioning/datasources/datasource.yml`, apply the settings of [contracts/trace-log-links.md](contracts/trace-log-links.md) "Grafana data sources" (B10, FR-005)
- [ ] T033 [US1] Declare `INFRAHUB_TRACE_SAMPLE_RATIO: ${INFRAHUB_TRACE_SAMPLE_RATIO:-0.1}` in the `environment:` block of `development/docker-compose.yml`, and update the root `docker-compose.yml` with `uv run invoke release.validate-dockercomposeenv` (backend `AGENTS.md`: Compose forwards only declared variables)
- [ ] T034 [US1] In `development/docker-compose-observability.yml`, add an `environment` block for the `infrahub-server` and `task-worker` services with the five variables of [contracts/trace-log-links.md](contracts/trace-log-links.md) "Tracing in Compose" (FR-032, research R2); keep `INFRAHUB_TRACE_ENABLE` at `false` in the root `docker-compose.yml`
- [ ] T035 [US1] Regenerate `development/docker-compose-observability-standalone.yml` with `development/convert_compose_standalone.py`, and check that the diff contains only the T034 change
- [ ] T036 [US1] Write the question for the owner of the service behind `https://infrahub.opsmill.io/?observability=true` (owner not known; research R2): does it merge the observability file into the services of `docker-compose.yml`, so the T034 override applies? Give the text to Daniel; do not send it
- [ ] T037 [P] [US1] Add changelog fragments in `changelog/`: port `+trace-sample-ratio.added.md` and `+task-worker-log-trace-id.added.md` from the draft; add a `changed` fragment that starts with `**Breaking:**` for the `trace_id` format (old `0x…` form, new 32-character form, update queries and alerts; research R5); add a `fixed` fragment for the trace and log links in Grafana (B10); add a `changed` fragment for tracing turned on in Compose with the observability stack (FR-032)
- [ ] T038 [US1] Run T024 to T027 and `uv run invoke format lint`; with the submodule on `dp-20261015-trace-context-ifc-3419`, run a generator locally and check quickstart manual checks 1 to 3

**Checkpoint**: Story 1 works with the local SDK branch. Scenarios 1, 3 and 8 depend on IFC-3419 being
merged before release.

---

## Phase 5: User Story 3 - Real durations of slow requests and the connection pool load (Priority: P2)

**Goal**: Duration metrics reach 300 s (queries) and 1200 s (HTTP); API and GraphQL requests are
counted; pool size, pool usage and connection wait are exported and shown; metric values survive an
API worker restart (FR-014 to FR-019; [contracts/metrics.md](contracts/metrics.md)).

**Independent Test**: Run a load that holds connections, a query of more than 30 s, a GraphQL request
and an `/api/…` request; open the Infrahub dashboard (quickstart, manual check 5).

### Tests for User Story 3

- [ ] T039 [P] [US3] Port `backend/tests/unit/serve/__init__.py`, `backend/tests/unit/serve/test_gunicorn_config.py` and `backend/tests/unit/test_metrics_multiprocess.py` from the draft: `on_starting` empties the metric folder once; `child_exit` marks the worker dead; a second worker keeps the values of the first; a dead worker no longer shows on `liveall` gauges (B9, FR-018)
- [ ] T040 [P] [US3] Write a test in `backend/tests/unit/test_server_metrics.py` that sends a GraphQL request and an `/api/…` request through the application and finds both in `infrahub_request_duration_seconds` with their route as `path`; it must fail on `develop` (B13, FR-016, research R4)
- [ ] T041 [P] [US3] Port the bucket tests from the draft `backend/tests/unit/test_server_metrics.py`, `backend/tests/unit/database/test_metrics.py` and `backend/tests/unit/test_lock.py`: every new limit of [contracts/metrics.md](contracts/metrics.md) appears as an `le` label, and a 30-second value is counted in `le="30"` (FR-014)
- [ ] T042 [P] [US3] Port `backend/tests/unit/database/test_connection_metrics.py` from the draft: the pool size gauge is set; each acquisition records its wait; a failure while recording is logged and the acquisition still returns; the test fails if the driver pool has no `acquire` method (FR-017)

### Implementation for User Story 3

- [ ] T043 [US3] Create `backend/infrahub/serve/gunicorn_config.py` hooks `on_starting` and `child_exit` from the draft, keeping the existing settings of that file, and remove the deletion of metric files from `backend/infrahub/serve/worker.py` (B9, FR-018; research R10)
- [ ] T044 [US3] Add `multiprocess_mode` to the gauges listed in [contracts/metrics.md](contracts/metrics.md) "Changed multiprocess modes", in `backend/infrahub/database/metrics.py`, `backend/infrahub/worker.py` and `backend/infrahub/api/admission/metrics.py`, as the draft does, and replace the old multiprocess comment in the admission metrics with the draft's one-sentence comment (FR-018)
- [ ] T045 [US3] Find the cause of B13 in `backend/infrahub/server.py` (the `PrometheusMiddleware` setup and the middlewares around it), record it in [research.md](research.md) R4, and fix it so T040 passes (FR-016)
- [ ] T046 [US3] Change the buckets: `REQUEST_DURATION_BUCKETS` in `backend/infrahub/server.py`, `infrahub_db_query_execution_seconds` in `backend/infrahub/database/metrics.py`, and both lock histograms in `backend/infrahub/lock.py`, with the values of [contracts/metrics.md](contracts/metrics.md) (FR-014)
- [ ] T047 [US3] Port `CONNECTION_POOL_SIZE` and `CONNECTION_WAIT_METRICS` to `backend/infrahub/database/metrics.py`, create `backend/infrahub/database/connection_metrics.py` with `instrument_connection_pool` from the draft, and call it where the draft does in `backend/infrahub/database/__init__.py` (FR-017)
- [ ] T048 [US3] In `development/grafana/provisioning/dashboards/infrahub_monitoring.json`, port the "Connection Pool" row from the draft (pool usage against pool size per process, connection wait p95), the renamed admission panels "Running API Requests vs Admission Limit" and "Admission Limit Usage" with "This is not the Neo4j connection pool" in their descriptions (B5, FR-019), and the duration panels corrected for the new highest buckets (FR-015); do not port the "Redis" row
- [ ] T049 [P] [US3] Add changelog fragments: port `+longer-duration-buckets.changed.md`, `+metric-files-kept-on-worker-start.fixed.md` and `+admission-panel-names.fixed.md` from the draft; port `+connection-pool-and-redis-metrics.added.md` as `+connection-pool-metrics.added.md` without the Redis part; add a `fixed` fragment for API and GraphQL requests in the HTTP metrics (B13)
- [ ] T050 [US3] Run T039 to T042 and `uv run invoke format lint`

**Checkpoint**: Story 3 is complete and testable on its own.

---

## Phase 6: User Story 4 - Task worker saturation per priority queue (Priority: P2)

**Goal**: Each task worker records the start delay and the runs in progress, by flow and priority
queue; the dashboard shows a "Priority queues" row (FR-020, FR-021).

**Independent Test**: Start more flow runs than the workers can run at once on each queue; open the
"Priority queues" row (quickstart, manual check 6).

### Tests for User Story 4

- [ ] T051 [P] [US4] Port `backend/tests/unit/workers/test_metrics.py` from the draft: the delay equals start time minus expected start time and is never negative; no value without an expected start time; the gauge rises and falls, also when the run raises; a run on `high` is counted with `queue="high"`; an empty queue gives `unknown`

### Implementation for User Story 4

- [ ] T052 [US4] Create `backend/infrahub/workers/metrics.py` from the draft (`FLOW_RUN_START_DELAY`, `FLOW_RUNS_IN_PROGRESS`, `observe_start_delay`, `track_flow_run`) (FR-020)
- [ ] T053 [US4] In `backend/infrahub/workers/infrahub_async.py`, port the calls to `observe_start_delay` and `track_flow_run` around the flow run, as the draft does (FR-020)
- [ ] T054 [US4] In `development/grafana/provisioning/dashboards/infrahub_monitoring.json`, port the "Priority Queues" row from the draft (start delay p95 and runs in progress per queue) (FR-021); this file is also changed by T048 and T062, so do not run these tasks in parallel
- [ ] T055 [P] [US4] Port `changelog/+task-worker-queue-metrics.added.md` from the draft
- [ ] T056 [US4] Run T051 and `uv run invoke format lint`

**Checkpoint**: Story 4 is complete and testable on its own.

---

## Phase 7: User Story 5 - Shipped dashboards work in any Grafana (Priority: P2)

**Goal**: Every shipped dashboard uses Infrahub's metric names and template variables; Prefect panels
count runs; Neo4j Community panels are explained (FR-022 to FR-025).

**Independent Test**: Import each dashboard into a Grafana with only a Prometheus data source and
Infrahub's metrics (quickstart, manual check 7, required before release).

### Tests for User Story 5

- [ ] T057 [P] [US5] Port `backend/tests/unit/test_grafana_dashboards.py` from the draft (no fixed `job`, `instance` or `container` in panel queries; no misleading admission title) and add: panel identifiers are unique in each dashboard (critique X3); no panel reads `le="1"` for database queries or `le="0.5"` for HTTP as the highest limit (FR-015, research R6)

### Implementation for User Story 5

- [ ] T058 [P] [US5] In `development/grafana/provisioning/dashboards/prefect_flow_run_overview.json`, port the draft changes: run counts with `sum(...)` instead of `count(...)`, no `flow_run_name` variable, no run time panels that read `prefect_flow_runs_total_run_time_total`, `namespace` read from Loki (B12, FR-023), and CPU and memory panels on the stack's own metrics or removed (B2, FR-024)
- [ ] T059 [P] [US5] In `development/grafana/provisioning/dashboards/prefect_platform_overview.json`, port the same draft changes (B2, B12)
- [ ] T060 [P] [US5] In `development/grafana/provisioning/dashboards/neo4j_monitoring.json`, port the draft changes: template variables for job and instance, and a text panel that says the server panels need Neo4j Enterprise (B3, FR-025)
- [ ] T061 [P] [US5] In `development/alloy/config.alloy`, port the draft `discovery.relabel "database"` that drops the Neo4j target when `NEO4J_METRICS_TARGET` is empty, and in `development/docker-compose-database-neo4j.yml` port the variable that sets it for Enterprise; do not port the Redis scrape (B3, FR-025)
- [ ] T062 [US5] In `development/grafana/provisioning/dashboards/infrahub_monitoring.json`, port the draft template variables for job, instance and container, each defaulting to today's value (FR-022); run after T048 and T054
- [ ] T063 [P] [US5] Port `changelog/+dashboard-template-variables.fixed.md`, `changelog/+prefect-dashboard-resources.fixed.md` and `changelog/+neo4j-community-metrics.fixed.md` from the draft
- [ ] T064 [US5] Run T057 and `uv run invoke format lint`; on a Linux host, check the Prefect CPU and memory panels (research R6)

**Checkpoint**: Story 5 is complete and testable on its own.

---

## Phase 8: User Story 6 - Record more traces during an incident, without a restart (Priority: P3)

**Goal**: A super admin sets a temporary ratio for at most 24 hours through public endpoints under
`/api/troubleshooting` or `infrahubctl`; every process applies it within seconds and logs it; an event
records the change (FR-026 to FR-031, FR-035, FR-036;
[contracts/rest-trace-sample-ratio.md](contracts/rest-trace-sample-ratio.md)). Approved by Damien
Garros on 2026-10-15. Needs Phase 4 (the default ratio).

**Independent Test**: With tracing on, set the ratio to 1.0 for 2 minutes; every new request is
traced; the default applies after 2 minutes (quickstart, manual check 8).

### Tests for User Story 6 (Infrahub)

- [ ] T065 [P] [US6] Port the temporary ratio tests from the draft `backend/tests/unit/test_trace.py` (set, replace, clear, expiry by the clock, `state()`) into `backend/tests/unit/test_trace.py`
- [ ] T066 [P] [US6] Port the message tests from the draft `backend/tests/unit/message_bus/test_operations.py` and `backend/tests/unit/message_bus/test_mappings.py`: the handler sets and clears the ratio and writes one log line each time (FR-035); `ratio` and `expires_at` are set together or both empty
- [ ] T067 [P] [US6] Port `backend/tests/component/api/test_trace_sample_ratio.py` and the fixtures in `backend/tests/component/api/conftest.py` from the draft, with the path `/api/troubleshooting/trace-sample-ratio`, and add: a new change replaces the active one; the three endpoints are in the OpenAPI schema with a description (FR-036)
- [ ] T068 [P] [US6] Write a component test in `backend/tests/component/` that starts a task worker process with the message bus and checks that it applies a ratio change (research R7, critique E8); if a task worker cannot be started in a component test, record why in [research.md](research.md) R7 and cover it with quickstart manual check 8
- [ ] T069 [P] [US6] Port the change in `backend/tests/component/api/test_50_internals.py` from the draft, if it still applies after the endpoints move out of `internal.py`

### Implementation for User Story 6 (Infrahub)

- [ ] T070 [US6] In `backend/infrahub/trace.py`, port from the draft the temporary ratio of `RatioSampler` (`set_temporary_ratio`, `clear_temporary_ratio`, `state`, `_temporary_in_force`) and the module functions `set_temporary_sample_ratio`, `clear_temporary_sample_ratio`, `get_sample_ratio_state` ([data-model.md](data-model.md) "Sampler state")
- [ ] T071 [P] [US6] Create `backend/infrahub/message_bus/messages/refresh_settings_trace_sample_ratio.py` from the draft, and register `refresh.settings.trace_sample_ratio` in `backend/infrahub/message_bus/messages/__init__.py`
- [ ] T072 [US6] In `backend/infrahub/message_bus/operations/refresh/settings.py`, port the handler `trace_sample_ratio` with its two log lines, and register it in `backend/infrahub/message_bus/operations/__init__.py` (FR-027, FR-035)
- [ ] T073 [P] [US6] Create `backend/infrahub/events/trace_action.py` with `TraceSampleRatioUpdatedEvent` from the draft, export it in `backend/infrahub/events/__init__.py`, and add `TRACE_SAMPLE_RATIO_UPDATED` in `backend/infrahub/core/constants/__init__.py` (FR-030)
- [ ] T074 [US6] Create `backend/infrahub/api/troubleshooting.py` with `router = APIRouter(prefix="/troubleshooting", tags=["troubleshooting"])` and the three endpoints `GET`, `PUT` and `DELETE /trace-sample-ratio`, ported from the draft `backend/infrahub/api/internal.py` (`TraceSampleRatioAPI`, `TraceSampleRatioUpdateAPI`, the super admin check, the error when tracing is off, the event that never fails the request); remove `include_in_schema=False`; give each endpoint a summary and a description that says why it exists (FR-026 to FR-031, FR-036)
- [ ] T075 [US6] Include the troubleshooting router in `backend/infrahub/api/__init__.py`; move the shared super admin permission constant so `internal.py` and `troubleshooting.py` both use it without duplication; leave `POST /api/response-delay` unchanged
- [ ] T076 [US6] Regenerate `schema/openapi.json` with `uv run invoke schema.generate-jsonschema` and the frontend REST types with `cd frontend/app && pnpm codegen`; regenerate the reference docs with `uv run invoke docs.generate` (event and message bus pages, configuration)
- [ ] T077 [P] [US6] Port `changelog/+trace-sample-ratio-without-restart.added.md` from the draft and correct it to the public path `/api/troubleshooting/trace-sample-ratio`
- [ ] T078 [US6] Run T065 to T069 and `uv run invoke format lint`

### SDK change (IFC-3420), in `python_sdk/` on branch `dp-20261015-trace-sample-ratio-command-ifc-3420`

- [ ] T079 [US6] In `python_sdk/`, create the branch `dp-20261015-trace-sample-ratio-command-ifc-3420` from `dp-20261015-trace-context-ifc-3419` (stacked; plan, delivery order step 7)
- [ ] T080 [P] [US6] Write unit tests in `python_sdk/tests/unit/ctl/test_troubleshooting_app.py`: the get, set and clear commands call `GET`, `PUT` (with `ratio` and `duration_seconds`) and `DELETE` on `/api/troubleshooting/trace-sample-ratio`; the error "Tracing is not enabled on this instance; set `INFRAHUB_TRACE_ENABLE`" is printed unchanged (FR-031); a ratio outside 0 to 1 or a duration outside 1 to 86400 is rejected
- [ ] T081 [US6] Create `python_sdk/infrahub_sdk/ctl/troubleshooting.py` with an `AsyncTyper` app and the commands of T080, following `python_sdk/infrahub_sdk/ctl/AGENTS.md` (`catch_exception`, `CONFIG_PARAM`, `initialize_client`, Rich output), and register it in `python_sdk/infrahub_sdk/ctl/cli_commands.py` as `troubleshooting`; propose the final command names to Daniel before T083
- [ ] T082 [US6] In `python_sdk/`, run `uv run invoke docs-generate` and add a changelog fragment in `python_sdk/changelog/`
- [ ] T083 [US6] In `python_sdk/`, run `uv run invoke format lint-code` and `uv run pytest tests/unit/`, then commit on `dp-20261015-trace-sample-ratio-command-ifc-3420` with a conventional message ending in `[IFC-3420]`
- [ ] T084 [US6] Ask Daniel whether to push `dp-20261015-trace-sample-ratio-command-ifc-3420` and open its pull request with base `dp-20261015-trace-context-ifc-3419`; if IFC-3419 changed during its review, rebase this branch on it first

**Checkpoint**: Story 6 works with the local SDK branch, which has both SDK changes.

---

## Phase 9: Polish, documentation, SDK merge and release checks

**Purpose**: Documentation for every story, the submodule pointer, the manual test and the release
checks.

- [ ] T085 [P] Create `dev/knowledge/backend/observability.md` from the draft without the Redis exporter and the Grafana MCP server, and with: `[MASKED]`, span event masking, URL query strings in log messages, the `trace_id` format, the public `/api/troubleshooting` endpoints, and the `--config` requirement of gunicorn for B9 (research R10); link it in `dev/README.md` and `dev/knowledge/backend/architecture.md`, and port the draft changes to `dev/knowledge/backend/api-backpressure.md`, `backend/AGENTS.md` and `development/grafana/AGENTS.md` without the Grafana MCP content
- [ ] T086 After both SDK pull requests merge on `infrahub-develop`: in `python_sdk/`, check out `origin/infrahub-develop`, check that it contains both SDK commits, and commit the new `python_sdk` pointer on the Infrahub branch (root `AGENTS.md`, "Submodules")
- [ ] T087 [P] Update `docs/docs/deploy-manage/run-observe/metrics.mdx` with the new and changed metrics of [contracts/metrics.md](contracts/metrics.md) and a short "which panel answers which question" section, using the `opsmill-docs-writing-infrahub-docs` skill
- [ ] T088 [P] Update `docs/docs/deploy-manage/install-configure/install/observability-stack.mdx`: tracing on with the stack and `INFRAHUB_TRACE_SAMPLE_RATIO`; the Grafana data source settings of B10; how to raise the ratio during an incident (`infrahubctl` and the REST call); how to check every process applied it from the log line (FR-035); how to reduce the cost of tracing (FR-034); no Grafana MCP or Redis content
- [ ] T089 [P] Create `docs/docs/deploy-manage/run-observe/own-monitoring.mdx`, "Send Infrahub telemetry to your own monitoring" (metrics scraping, traces to any OTLP collector, logs with `trace_id`, the data source settings), and add it to `docs/sidebars.ts` next to "Metrics" (FR-034)
- [ ] T090 Update `docs/docs/reference/metrics.mdx` from the draft (it is not generated) and run `uv run invoke docs.lint` and `uv run invoke docs.validate`
- [ ] T091 Measure the cost of tracing as [research.md](research.md) R9 says (three configurations, the named load) and record the host, the commit and the results in `specs/infp-742-find-slow-component/measurements.md`; if tracing at 0.1 adds more than 5 %, lower the default in `backend/infrahub/config.py` and the Compose files and measure again (SC-006)
- [ ] T092 Run `/pre-ci` and fix every failure
- [ ] T093 Daniel runs the `opsmill-dev-guiding-manual-tests` skill on the Infrahub branch, with `python_sdk` on `origin/infrahub-develop` (needs T086), using the checks of [quickstart.md](quickstart.md)
- [ ] T094 Before release: quickstart manual check 7 (each dashboard in a Grafana with only Prometheus) and manual check 1 repeated with the file downloaded from `https://infrahub.opsmill.io/?observability=true` (needs the answer to T036)

---

## Pull requests and tickets

Epic [IFC-3424](https://opsmill.atlassian.net/browse/IFC-3424) implements INFP-742. Each row is one
task and one pull request. The `infrahub` pull requests form **one linear stack**, managed with
`gh stack` (decided by Daniel on 2026-10-16): each layer is created from the layer below it and its
pull request targets it; GitHub moves it to `develop` when the layers below merge. `<date>` is the day
the branch is created, as `YYYYMMDD`.

| Layer | Row | Ticket | Pull request | Branch | Created from | Tasks |
|-------|-----|--------|--------------|--------|--------------|-------|
| 0 | Spec | — (INFP-742) | Add the spec set for finding the slow component | `dp-20261014-find-slow-component-infp-742` | `develop` | — |
| 1 | A1 | [IFC-3425](https://opsmill.atlassian.net/browse/IFC-3425) | Mask secrets and personal data in spans and logs, and fix single sign-on telemetry | `dp-<date>-mask-telemetry-ifc-3425` | Layer 0 | T001, T005, T007–T018 |
| 2 | B1 | [IFC-3428](https://opsmill.atlassian.net/browse/IFC-3428) | Record long durations, connection pool load and task worker saturation | `dp-<date>-slow-component-metrics-ifc-3428` | Layer 1 | T006, T039–T047, T049–T053, T055, T056 |
| 3 | B2 | [IFC-3429](https://opsmill.atlassian.net/browse/IFC-3429) | Fix the shipped dashboards and make them work in any Grafana | `dp-<date>-portable-dashboards-ifc-3429` | Layer 2 | T048, T054, T057–T064 |
| 4 | A2 | [IFC-3426](https://opsmill.atlassian.net/browse/IFC-3426) | Follow a background task to its queries in one trace | `dp-<date>-one-trace-ifc-3426` | Layer 3 | T024–T038 |
| 5 | A3 | [IFC-3427](https://opsmill.atlassian.net/browse/IFC-3427) | Change the trace sampling ratio during an incident without a restart | `dp-<date>-runtime-sample-ratio-ifc-3427` | Layer 4 | T065–T078 |
| 6 | C1 | [IFC-3430](https://opsmill.atlassian.net/browse/IFC-3430) | Measure, document and close out | `dp-<date>-close-out-slow-component-ifc-3430` | Layer 5 | T085–T094 |

The SDK changes are in another repository, so they form a second stack there, in `python_sdk/`:

| Layer | Row | Ticket | Pull request | Branch | Created from | Tasks |
|-------|-----|--------|--------------|--------|--------------|-------|
| 1 | S1 | [IFC-3419](https://opsmill.atlassian.net/browse/IFC-3419) | Send the `traceparent` header when OpenTelemetry is installed | `dp-20261015-trace-context-ifc-3419` | `origin/infrahub-develop` | T002, T019–T023 |
| 2 | S2 | [IFC-3420](https://opsmill.atlassian.net/browse/IFC-3420) | Add the `infrahubctl` command for the trace sampling ratio | `dp-20261015-trace-sample-ratio-command-ifc-3420` | S1 | T079–T084 |

```text
infrahub:            develop ← spec ← A1 ← B1 ← B2 ← A2 ← A3 ← C1
infrahub-sdk-python: infrahub-develop ← S1 ← S2
```

- Why this order: the spec is reviewed in its own layer but lands together with A1, never alone. A1
  comes first because the masking must reach `develop` before tracing reaches more operators (FR-011).
  B1 and B2 depend on nothing else and can merge early. A2 is fully tested only with S1, and A3 is
  fully used only with S2, so a slow SDK review blocks only the top of the stack. C1 is last.
- Merging: bottom up, with `gh stack merge <PR> --yes`, which merges that pull request and every
  unmerged one below it. Reviews of all layers can run at the same time.
- A fix in a lower layer is made in that layer, then `gh stack rebase --upstack` replays the layers
  above. Each layer ticks its own tasks in this file and records its own spec updates.
- A2 is tested with `python_sdk` on the S1 branch; it does not wait for S1 to merge. Only C1 commits
  the `python_sdk` pointer, after S1 and S2 merge. Then Daniel runs `opsmill-dev-guiding-manual-tests`
  (T093).
- Each pull request opens as a draft (`gh stack submit --auto`). Force-pushing commands
  (`gh stack sync`, `gh stack rebase`) run only while it is a draft, or after its review has landed.
  Push and open pull requests only when Daniel asks.
- IFC-3425 also fixes [IFC-3330](https://opsmill.atlassian.net/browse/IFC-3330).

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: after Setup.
- **US2 (Phase 3)**: after Foundational. Must be done before tracing is turned on for more operators
  (FR-011), so before T034 ships.
- **US1 (Phase 4)**: after Foundational. Its SDK part (T019 to T023) can start right after Setup.
- **US3 (Phase 5), US4 (Phase 6), US5 (Phase 7)**: after Foundational; independent of US1 and US2,
  except that T048, T054 and T062 change the same dashboard file and run in that order.
- **US6 (Phase 8)**: after US1 (needs `RatioSampler` and `sample_ratio`, T028 and T029). T079 needs
  the IFC-3419 branch (T022).
- **Polish (Phase 9)**: after the stories it documents. T086 needs both SDK pull requests merged. T093
  needs T086. T094 needs T036 answered.

### Inside each story

- Tests before implementation; check that they fail first.
- Shared modules before their callers (for example T012 before T013 and T014).
- Changelog fragments with the change they describe.

### Parallel opportunities

- T003 and T004; T005 and T006.
- In US2: T007 to T011 together; then T016 and T017 next to T012 to T015.
- In US1: the SDK part (T019 to T023) next to the Infrahub tests T024 to T027.
- US3, US4 and US5 can be worked on in parallel by different people, except the three edits of
  `infrahub_monitoring.json` (T048, T054, T062).
- In US5: T058, T059, T060 and T061 change different files.
- In US6: T065 to T069 together; T071 and T073 next to T070.
- In Phase 9: T085, T087, T088 and T089.

### Parallel example: User Story 2

```text
Task: "T007 Unit tests for the masking rules in backend/tests/unit/test_masking.py"
Task: "T009 Masking exporter tests in backend/tests/unit/test_trace.py"
Task: "T010 Log masking tests in backend/tests/unit/test_log.py"
Task: "T011 Single sign-on telemetry test in backend/tests/component/api/test_sso_token_telemetry.py"
```

---

## Implementation Strategy

### Order of work

The work follows the layers of "Pull requests and tickets", bottom to top, one layer at a time:

1. Layer 0, the spec: commit this folder.
2. Layer 1, A1 (US2, Phase 3, with Phases 1 and 2): masking and single sign-on fixes. This removes the
   secrets that are in the trace store today and unblocks tracing for more operators.
3. Layers 2 and 3, B1 and B2 (US3, US4 and US5): metrics, then all dashboard changes.
4. Layer 4, A2 (US1, Phase 4): one trace from a task to its queries. Start S1 (T019 to T023) before
   it, so A2 can be tested with the S1 branch, and open the S1 pull request early.
5. Layer 5, A3 (US6, Phase 8): the runtime ratio, then S2 (T079 to T084) on top of S1.
6. Layer 6, C1 (Phase 9): documentation, the cost measurement, the submodule pointer after both SDK
   merges, `/pre-ci`, and the manual test.

The first increment that an operator can use is layers 0 and 1. Check quickstart manual check 4
after layer 1, and manual checks 1 to 3 after layer 4.

### Merge order with INFP-743

The plan proposes that INFP-742 merges first and INFP-743 rebases, because both add rows to
`infrahub_monitoring.json`. To agree with Wim Van Deun (plan, "Structure Decision").
