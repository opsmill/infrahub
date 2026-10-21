# Manual checks: layer 4, IFC-3470 (one trace, ratio without a restart, close out)

- **Branch:** `dp-20261021-one-trace-sample-ratio-close-out-ifc-3470`
- **Base:** `dp-20261016-portable-dashboards-ifc-3429` (the layer below)
- **Head at start:** `dbb5fab45` ("docs(observability): add the observability knowledge page [IFC-3470]")
- **Uncommitted changes at start:** the customer docs (`metrics.mdx`, `observability-stack.mdx`,
  `reference/metrics.mdx`, new `own-monitoring.mdx`, `sidebars.ts`); the `python_sdk` pointer, on the
  merged IFC-3419 change (`79997aa6`)
- **Started:** 2026-10-21
- **Environment:** the root `docker-compose.yml` with
  `development/docker-compose-observability-standalone.yml`, image built from this branch
  (`VERSION=local`), project `infrahub-check`

## Checks

| # | Check | What changed | Source | Outcome |
|---|-------|--------------|--------|---------|
| 1 | Tracing is on with the stack | The stack's Compose file turns tracing on for the API server and the task workers; the root file alone keeps it off | `e7fb4fb82`; FR-032; quickstart check 1 | pass |
| 2 | Default sampling ratio | 0.1 traces about 1 request in 10; 1 traces every request | `24880806d`; FR-006, FR-007 | pass |
| 3 | One trace from a task to its queries | A flow run, its SDK calls and their database queries are in one trace | `24880806d`, SDK `traceparent`; story 1; quickstart check 2 | pass |
| 4 | Links between traces and logs | 32-character `trace_id` in server and task worker logs; "Logs for this span" and "View trace in Tempo" | `24880806d`; FR-003 to FR-005; quickstart check 3 | bug |
| 5 | Ratio change without a restart | `PUT`, `GET`, `DELETE` on `/api/troubleshooting/trace-sample-ratio`; one log line per process; the event | `7bc1f5a87`; story 6; FR-026 to FR-030, FR-035; quickstart check 8 | pass |
| 6 | Refused requests | 403 without `super_admin`; 400 with the documented error when tracing is off | `7bc1f5a87`; FR-029, FR-031 | pass |
| 7 | Endpoints in the API docs | The 3 endpoints in `/api/docs` with a summary and a description | `7bc1f5a87`; FR-036 | pass |
| 8 | Customer docs | The 4 pages render; "Your own monitoring" after "Metrics" in the sidebar | uncommitted docs; T087 to T090 | pass |
| 9 | Automated tests | Unit, component and RabbitMQ integration tests of this layer | all commits | pass |

Not covered: the file downloaded from `https://infrahub.opsmill.io/?observability=true` (needs the
answer to T036; release check T094).

## Results

### Check 1: pass

Project `infrahub-check` (root `docker-compose.yml` with the standalone file, image `local` built from
this branch): `infrahub-server` and `task-worker` have `INFRAHUB_TRACE_ENABLE=true`,
`INFRAHUB_TRACE_EXPORTER_TYPE=otlp`, `INFRAHUB_TRACE_EXPORTER_ENDPOINT=http://infrahub-tempo:4317`,
`INFRAHUB_TRACE_SAMPLE_RATIO=0.1`. Grafana Explore, Tempo: traces for `infrahub-server` and
`infrahub-task-worker` (Tempo search: at least 50 and 3). `docker compose -f docker-compose.yml config`
alone gives only `"INFRAHUB_TRACE_ENABLE": "false"`.

### Check 2: pass

100 requests to `/api/info` (all `200`): at `INFRAHUB_TRACE_SAMPLE_RATIO=0.1`, Tempo holds 8 traces for
`GET /api/info`; after recreating the stack with `INFRAHUB_TRACE_SAMPLE_RATIO=1`, 100 traces for the
next 100 requests. No error in the server log. The first loop typed into the app's command input did
not run (the input turned `;` into `\;`), so the agent sent the read-only requests; Daniel checked the
traces in Grafana.

### Check 3: pass

Branch `trace-check` created with Sync with Git. Tempo: one trace with the `infrahub-task-worker` flow
run `Create branch 'trace-check' in Git Repositories`, the `infrahub-server` GraphQL request spans
under it, and `execute_db_query_with_metadata` spans under those, all with one trace ID.

### Check 4: bug

- **Expected:** "Logs for this span" shows only log lines whose `trace_id` is the trace ID of the open
  trace.
- **Observed:** for trace `36083100911f941eeeabb42b70f34797` (`trace-check`), Loki returns 15 lines:
  6 Infrahub lines from `task-worker-2` with `trace_id=36083100…` (correct, 32 characters), and 9 lines
  from `infrahub-tempo-1`, Tempo's own access log, which contains the trace ID inside a URL
  (`url="/api/traces/36083100…"`), written when Grafana fetched the trace.
- **Cause:** the `tracesToLogsV2` query `{job=~".+"} |= "${__trace.traceId}"` matches the trace ID as
  plain text in every stream.
- **Also found (no change during the loop):** with `INFRAHUB_PRODUCTION=false`, the raw container
  output has terminal color codes around `trace_id` (`trace_id^[[0m=^[[35m…`). Alloy removes them
  (`stage.decolorize`), so Loki stores `trace_id=<id>` and the links work; a customer's own log agent
  would not, and `own-monitoring.mdx` does not say so (see check 8).

### Check 5: pass

Default ratio 1 (from check 2). `PUT` ratio 0 for 600 s: state with `temporary_ratio` 0.0 and
`expires_at`; one "Set the temporary trace sampling ratio" line per process in Loki; no new
`infrahub-server` trace while it applied; `DELETE`: `temporary_ratio` null, `ratio_in_force` 1.0, and
"Cleared the temporary trace sampling ratio"; two `infrahub.trace.sample_ratio_updated` events with
the previous and new ratio and the admin's `account_id`.

### Check 6: pass

`GET` without a token: 403 "You do not have the following permission: global:super_admin:allow_all";
`PUT` without a token: 401 "Authentication is required"; with tracing off (root file only), `PUT` with
the admin token: 400 "Tracing is not enabled on this instance; set INFRAHUB_TRACE_ENABLE", and `GET`
returns `"enabled": false`. A logged-in account without `super_admin` is covered by
`test_put_requires_super_admin`.

### Check 9: pass

Unit suite 4593 passed; component tests (`test_trace_sample_ratio.py`, `test_trace_spans.py`,
`test_50_internals.py`, `test_sso_token_telemetry.py`) 26 passed; `test_rabbitmq.py` 8 passed, including
`test_task_worker_applies_a_trace_sample_ratio_change`. Run by the agent and again by Daniel.

### Finding outside the checks (found while preparing check 6)

- **Observed:** `docker-compose-observability-tracing.yml` sets `INFRAHUB_TRACE_ENABLE: "true"` as a
  fixed value. With `INFRAHUB_TRACE_ENABLE=false` in the environment, `docker compose config` of the
  root file with the standalone file still gives `true` for `infrahub-server` and `task-worker`.
- **Expected:** FR-034 and the new docs ("set `INFRAHUB_TRACE_ENABLE=false` to turn tracing off")
  say an operator can turn tracing off at the next restart.

### Check 7: pass

`/api/docs`: group `troubleshooting` with `GET` "Get the trace sampling ratio", `PUT` "Set a temporary
trace sampling ratio", `DELETE` "Clear the temporary trace sampling ratio", each with a description.
The request body limits are in the **Schema** view (`ratio` 0 to 1, `duration_seconds` 1 to 86400),
not in the default **Example Value** view.

### Check 8: pass

Docs preview (`npm --prefix docs start`): "Your own monitoring" after "Metrics" under Run & observe; the
4 pages render, tables and code blocks display, links open the right sections. The 2 doc gaps found in
checks 4 and 6 are fixed after the loop.

## Decisions (Daniel, 2026-10-21)

| Issue | Decision |
|---|---|
| Check 4: "Logs for this span" also returns Tempo access log lines | Fix now: match only a `trace_id` field |
| Tracing cannot be turned off with the stack's Compose file | Fix now: `${INFRAHUB_TRACE_ENABLE:-true}` |
| `own-monitoring.mdx` does not mention the color codes of text log lines | Fix the docs now |
