# Quickstart: Validate "Find the Slow Component"

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

This guide lists how to prove each user story works. Automated tests run first; the manual checks run
on a development stack with the observability stack. Contracts:
[metrics](contracts/metrics.md), [masking](contracts/masking.md),
[trace and log links](contracts/trace-log-links.md), [REST](contracts/rest-trace-sample-ratio.md).

## Prerequisites

- Docker running (component tests use testcontainers).
- `uv sync --all-groups` done.
- For story 1 scenarios 1, 3 and 8: the `python_sdk` submodule points at an SDK commit that sends
  `traceparent` ([research.md](research.md) R3).
- For the Prefect CPU and memory panels (B2): a Linux host. On Docker Desktop for macOS, cAdvisor sends
  no container names.

## Automated tests

```bash
uv run pytest backend/tests/unit/test_trace.py backend/tests/unit/test_log.py backend/tests/unit/test_lock.py backend/tests/unit/test_server_metrics.py backend/tests/unit/test_metrics_multiprocess.py backend/tests/unit/test_grafana_dashboards.py backend/tests/unit/config backend/tests/unit/database backend/tests/unit/message_bus backend/tests/unit/serve backend/tests/unit/workers
```

```bash
uv run pytest backend/tests/component/api/test_trace_sample_ratio.py backend/tests/component/api/test_trace_spans.py backend/tests/component/api/test_sso_token_telemetry.py
```

Expected: all pass. The tests must cover, at least:

| Story | Test proves |
|-------|-------------|
| 1 | Query spans are children of the request span; the sampler follows a sampled parent; ratio 0.5 records about half of new root traces; `trace_id` has 32 characters with leading zeros; task worker lines carry it |
| 2 | Span attributes and log fields for each rule read `[MASKED]`; a URL keeps its path; Cypher text and query names are unchanged; single sign-on spans have no token or user info; the login line has `account_id`; an exception event whose message has a URL with `code` and `state` shows `?[MASKED]`; a flow run log line with a token reaches the Prefect API handler masked; a log line whose message or exception text has a URL with `code` and `state` shows `?[MASKED]`; the attribute and field keys Infrahub sets on its own spans and log lines are compared with an expected list, so a harmless key that a rule would mask fails the test |
| 3 | Each new bucket limit appears as an `le` label; a 30 s query is counted in `le="30"`; a second gunicorn worker keeps the first worker's values; a stopped worker is not shown on pool gauges; a GraphQL and an `/api/…` request appear in `infrahub_request_duration_seconds` (B13) |
| 4 | Start delay equals start time minus expected start time; runs in progress rise and fall; a `high` run is counted with `queue="high"` |
| 5 | Panel identifiers are unique in each dashboard; no dashboard query has a fixed `job`, `instance` or `container`; no misleading admission title; no panel reads `le="1"` or `le="0.5"` as the highest limit |
| 6 | The three endpoints are listed in `schema/openapi.json` under `/api/troubleshooting/trace-sample-ratio`, with a description; super admin required; error when tracing is off; duration outside 1 s to 24 h rejected; set then clear; a new change replaces the active one; a process started after the change uses the default; event failure does not fail the request; a task worker receives the change ([research.md](research.md) R7) |

## Manual checks on the development stack

Start the stack with the observability services (see `development/docker-compose-observability.yml`),
then:

1. **Tracing is on with the stack (FR-032).** Without setting any `INFRAHUB_TRACE_*` variable, open
   Grafana, Explore, Tempo: traces of the API server and task workers appear. Without the
   observability file, `INFRAHUB_TRACE_ENABLE` is `false`. Required before release: repeat with the
   file downloaded from `https://infrahub.opsmill.io/?observability=true` once it is built from this
   branch ([research.md](research.md) R2).
2. **One trace (story 1).** Run a generator that sends named queries through the SDK. In Tempo, open
   its flow run trace: the SDK calls and their queries are in the same trace, with `query_name`.
3. **Trace and log links (story 1).** From a task worker span, open "Logs for this span": only that
   trace's lines appear. From one of those lines in Loki, open the trace link. Repeat with a trace ID
   that starts with `0`.
4. **Masking (story 2).** Log in through single sign-on, then search Tempo and Loki for the access
   token, the `code` and `state` values, the user name and the email address: none is found;
   `[MASKED]` appears where they were.
5. **Durations and pool (story 3).** Run a query that lasts more than 30 s. On "Infrahub Monitoring",
   the query duration panel shows about 30 s, and the pool row shows usage against size and the wait
   time.
6. **Priority queues (story 4).** Start more flow runs than the workers can run at once on each queue.
   The "Priority queues" row shows the start delay p95 and the runs in progress per queue.
7. **Any Grafana (story 5). Required before release.** Import each dashboard into a Grafana with only a Prometheus data source
   and Infrahub's metrics: Infrahub panels show data.
8. **Ratio without restart (story 6).** As a super admin:

   ```bash
   curl -X PUT -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H "Content-Type: application/json" -d '{"ratio": 1.0, "duration_seconds": 120}' http://localhost:8000/api/troubleshooting/trace-sample-ratio
   ```

   Expected: within 10 seconds, every API server and task worker writes the log line "Set the
   temporary trace sampling ratio" (search for it in Loki, FR-035), and every new request is traced
   (SC-004); after 120 seconds, `GET` on the
   same path shows `temporary_ratio: null`; the event `infrahub.trace.sample_ratio_updated` is in the
   event list with the account.

## Cost of tracing (SC-006)

Before tracing is turned on for more operators, run the load and the three configurations of
[research.md](research.md) R9, and compare the API p95 response time and CPU use. Record the host, the
commit and the results in `measurements.md` in this feature directory. If tracing at ratio 0.1 adds
more than 5 %, lower the default of `INFRAHUB_TRACE_SAMPLE_RATIO` and measure again. Report the cost of
log masking alone (tracing off) next to it.
