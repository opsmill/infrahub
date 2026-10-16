# Implementation Plan: Find the Slow Component of an Infrahub Instance

**Branch**: `dp-20261014-find-slow-component-infp-742` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/infp-742-find-slow-component/spec.md`

## Summary

An operator must be able to name the slow component of an Infrahub instance from its metrics, traces
and logs (Jira [INFP-742](https://opsmill.atlassian.net/browse/INFP-742), phases 1 to 4 and 6 of the
design document). The work changes the telemetry Infrahub produces, so it works with any monitoring
system, and fixes the dashboards OpsMill ships:

- One trace from a flow run to its SDK calls and database queries, with the trace ID in task worker
  logs and links between traces and logs in Grafana.
- A default sampling ratio, and a temporary ratio that an administrator sets through the API without a
  restart.
- Masking of secrets and personal data in spans and logs, with the fixed marker `[MASKED]`.
- Longer duration buckets, connection pool size and connection wait, task worker start delay and runs
  in progress per priority queue, and metric values kept across API worker restarts.
- Dashboards that work in any Grafana.

Technical approach: port the local draft on branch
`dp-20261008-diagnose-slow-instance-infp-611-for-testing` without its out-of-scope parts, correct it
where it differs from the spec, and add what it lacks (B10, B13, FR-032, the documentation page).
[research.md](research.md) R1 lists each requirement against the draft.

## Technical Context

**Language/Version**: Python 3.14 (backend); Python 3.10 to 3.13 (SDK, `python_sdk/`); JSON (Grafana dashboards); YAML (Compose, Grafana data
sources); Alloy configuration

**Primary Dependencies**: FastAPI 0.131, OpenTelemetry SDK (already a dependency), `prometheus_client`
(multiprocess mode), `starlette_exporter`, `structlog`, Neo4j Python driver 6.2, Prefect (task
workers), `httpx` and Typer (SDK). One dependency upgrade: `starlette-exporter` 0.23 to 0.24, for B13 (research R4, approved by Daniel on
2026-10-16). No new dependency: the SDK imports OpenTelemetry only when the
caller's process has it (FR-001).

**Storage**: None. The temporary ratio is kept in the memory of each process (FR-028). No database
migration (FR-033).

**Testing**: pytest unit tests (`backend/tests/unit/`), component tests with testcontainers
(`backend/tests/component/`), SDK unit tests (`python_sdk/tests/unit/`), and the manual checks in [quickstart.md](quickstart.md) on a Compose
stack.

**Target Platform**: Linux containers: the API server (gunicorn with several workers, shared
`PROMETHEUS_MULTIPROC_DIR`) and the task workers, in Docker Compose or Kubernetes.

**Project Type**: Web service (backend) plus shipped monitoring configuration.

**Performance Goals**: At the default ratio 0.1, tracing adds at most 5 % to API p95 and to CPU (SC-006,
not measured yet: [research.md](research.md) R9). A ratio change applies in every process within
10 seconds (SC-004).

**Constraints**: The connection wait is measured by wrapping a private method of the Neo4j driver
pool; a failure to record never fails a query. A metric label is never a run ID. A span or log line
leaves the process already masked.

**Scale/Scope**: About 30 backend files, 4 dashboards, 1 Grafana data source file, 2 Compose files,
1 Alloy file, 4 documentation pages (see the draft file list in [research.md](research.md) R1).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | Pass | No schema change. Generated reference docs (`configuration.mdx`, `infrahub-events/`, `message-bus-events.mdx`) are regenerated with `uv run invoke docs.generate`, never edited. |
| II. Branch-Safe by Default | Pass | No database query is added. The ratio is one value per instance, not per branch. The event carries the branch of the request, as other events do. |
| III. Type Safety & Explicit Contracts | Pass | Pydantic models at the REST boundary and for the message; frozen dataclasses for the sampler state. The REST contract is in [contracts/rest-trace-sample-ratio.md](contracts/rest-trace-sample-ratio.md) before implementation. |
| IV. Test Discipline | Pass with one exception | Unit and component tests for each requirement (see [quickstart.md](quickstart.md)). E2E tests: the feature has no web interface page, so pytest-playwright tests do not apply; see Complexity Tracking. |
| V. Query Performance & Efficiency | Pass | No new query. The ratio change uses one broadcast message, no polling. |
| VI. Security & Input Boundaries | Pass | The ratio endpoints require super admin. Input is validated (ratio 0 to 1, duration 1 s to 24 h). Masking removes secrets before export. Error messages name only the setting to change. The upgrade of `starlette-exporter` to 0.24 (B13) was reviewed and approved by Daniel on 2026-10-16; it adds no new package. |
| VII. Simplicity & Maintainability | Pass with one exception | Reuses the response delay pattern (message bus broadcast) and existing exporters. The private Neo4j pool method is wrapped; see Complexity Tracking. |
| Ask First (root `AGENTS.md`, `backend/AGENTS.md`) | Pass | The new REST endpoints and event type are API changes. The approval was requested on 2026-10-15 from the engineering and architect approvers of the design document. Damien Garros answered the same day: no hidden endpoint, full documentation, a troubleshooting area of the API, the right permission, and a comparison with other tools. All are applied (spec FR-036, [research.md](research.md) R12). He approved on 2026-10-15 ([Slack](https://opsmillworkspace.slack.com/archives/C08075KCU3A/p1792057541808779?thread_ts=1792048837.114539&cid=C08075KCU3A)). |

## Project Structure

### Documentation (this feature)

```text
specs/infp-742-find-slow-component/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── rest-trace-sample-ratio.md
│   ├── metrics.md
│   ├── masking.md
│   └── trace-log-links.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/infrahub/
├── config.py                         # TraceSettings.sample_ratio (FR-006)
├── trace.py                          # RatioSampler, MaskingSpanExporter, get_traceid format (FR-004, FR-006, FR-007, FR-012)
├── masking.py                        # New: shared masking rules, MASKED_VALUE = "[MASKED]" (FR-012, FR-013, FR-013a)
├── log.py                            # add_trace_id, mask_personal_data, LogMaskingFilter (FR-003, FR-004, FR-013)
├── server.py                         # HTTP buckets, sample_ratio (FR-014)
├── worker.py                         # multiprocess_mode on infrahub_info (FR-018)
├── lock.py                           # Lock buckets (FR-014)
├── api/
│   ├── __init__.py                   # Includes the troubleshooting router
│   ├── troubleshooting.py            # New: public router /troubleshooting; GET/PUT/DELETE /trace-sample-ratio (FR-026 to FR-031, FR-036)
│   ├── oidc.py, oauth2.py            # No token response or user info in spans; account ID in log (FR-009, FR-010)
│   └── admission/metrics.py          # multiprocess_mode on gauges (FR-018)
├── database/
│   ├── __init__.py                   # Calls instrument_connection_pool
│   ├── connection_metrics.py         # New: pool size gauge, connection wait (FR-017)
│   └── metrics.py                    # Buckets, pool gauges (FR-014, FR-017, FR-018)
├── events/trace_action.py            # New: TraceSampleRatioUpdatedEvent (FR-030)
├── core/constants/__init__.py        # Event name constant
├── message_bus/
│   ├── messages/refresh_settings_trace_sample_ratio.py   # New message (FR-027)
│   └── operations/refresh/settings.py                    # Handler and its log line (FR-027, FR-028, FR-035)
├── serve/
│   ├── gunicorn_config.py            # New: on_starting, child_exit (FR-018)
│   └── worker.py                     # Remove per-worker metric file deletion (FR-018)
└── workers/
    ├── metrics.py                    # New: start delay, runs in progress (FR-020)
    └── infrahub_async.py             # Records the two metrics; masking filter on the Prefect API handler

backend/tests/
├── unit/  (test_trace.py, test_log.py, test_lock.py, test_server_metrics.py, test_metrics_multiprocess.py,
│           test_grafana_dashboards.py, config/, database/, message_bus/, serve/, workers/)
└── component/api/  (test_trace_sample_ratio.py, test_trace_spans.py, test_sso_token_telemetry.py)

development/
├── docker-compose-observability.yml            # Tracing on for infrahub-server and task-worker (FR-032)
├── docker-compose-observability-standalone.yml # Regenerated
├── docker-compose.yml                          # INFRAHUB_TRACE_SAMPLE_RATIO
├── alloy/config.alloy                          # Neo4j target only when set (FR-025)
└── grafana/provisioning/
    ├── datasources/datasource.yml              # Trace and log links (FR-005)
    └── dashboards/*.json                       # Infrahub, Neo4j, Prefect x2 (FR-015, FR-017, FR-019, FR-021 to FR-025)

python_sdk/  (submodule, infrahub-sdk-python; one branch and pull request per ticket, from origin/infrahub-develop)
├── infrahub_sdk/client.py            # BaseClient._request_headers adds traceparent when OpenTelemetry is present (IFC-3419, FR-001)
├── infrahub_sdk/ctl/<new module>.py  # infrahubctl command for /api/troubleshooting/trace-sample-ratio (IFC-3420, FR-026, FR-031)
├── infrahub_sdk/ctl/cli_commands.py  # Registers the command's Typer app (IFC-3420)
├── tests/unit/                       # Header present and absent; command calls and error output
├── docs/                             # Regenerated with uv run invoke docs-generate (IFC-3420)
└── changelog/                        # One SDK fragment per pull request

pyproject.toml, uv.lock                         # starlette-exporter 0.23 to 0.24: the B13 fix (FR-016)
docker-compose.yml                              # INFRAHUB_TRACE_SAMPLE_RATIO (generated by release.validate-dockercomposeenv)
schema/openapi.json                             # Regenerated: uv run invoke schema.generate-jsonschema (FR-036)
frontend/app/src/shared/api/rest/types.generated.ts  # Regenerated: pnpm codegen (FR-036)
dev/knowledge/backend/observability.md          # New knowledge page
docs/docs/deploy-manage/run-observe/metrics.mdx # Updated
docs/docs/deploy-manage/install-configure/install/observability-stack.mdx  # Updated
docs/docs/deploy-manage/run-observe/<new page>  # "Send Infrahub telemetry to your own monitoring"
changelog/                                      # One fragment per user-visible change; the trace_id format is a `changed` fragment marked **Breaking:**
```

**Structure Decision**: Backend changes stay in the modules that already own tracing (`trace.py`),
logging (`log.py`), metrics (`database/metrics.py`, `server.py`) and settings messages
(`message_bus/`). `masking.py` is new because both `trace.py` and `log.py` use the rules, and `log.py`
must not import the trace exporters. Out of scope from the draft and not ported: the Redis exporter,
its Alloy scrape and dashboard row (D7), the Grafana MCP container and `development/grafana-mcp/`
(D10), and their changelog fragments. The Redis exporter, the Redis dashboards and the Prefect event
stream panels belong to [INFP-743](https://opsmill.atlassian.net/browse/INFP-743), and their alert
rules to [INFP-746](https://opsmill.atlassian.net/browse/INFP-746). This plan must not change the
"Redis" row of `infrahub_monitoring.json` or the Redis scrape in `config.alloy`, so the two cards do
not edit the same lines. Both cards still add rows to `infrahub_monitoring.json`, and Grafana stores
the position and the identifier of each panel in the file, so the two branches conflict even without
editing the same panel. Proposed order, to agree with Wim Van Deun, the assignee of INFP-743: INFP-742
merges first, because its dashboard changes already exist in the draft, and INFP-743 rebases and
places its rows below. A test in `test_grafana_dashboards.py` fails when two panels of a dashboard
share an identifier.

## Delivery order

Each phase ships on its own, in the order of the design document.

1. **Phase 1, fix what is shipped** (stories 2 and 5): masking, single sign-on, dashboard rule, B2,
   B3, B5, B12. Masking (FR-009 to FR-013a) ships before phase 3 turns tracing on for more operators
   (FR-011).
2. **Phase 2, show what is recorded** (story 3): B9 first, then B13, then buckets, pool size and
   connection wait.
3. **Phase 3, one trace** (story 1):
   - In parallel, the SDK `traceparent` change, [IFC-3419](https://opsmill.atlassian.net/browse/IFC-3419),
     on SDK branch `dp-20261015-trace-context-ifc-3419`. Story 1 scenarios 1, 3 and 8 need it; until it
     merges, they are tested against the local submodule.
   - `sample_ratio`, trace ID format, task worker trace ID, data source links.
   - Compose turns tracing on (FR-032), and a check with the owner of the service behind
     `infrahub.opsmill.io` that the downloaded file applies it ([research.md](research.md) R2).
   - The cost measurement ([research.md](research.md) R9) before release.
   - A `changed` changelog fragment for the `trace_id` format, marked `**Breaking:**`, and an upgrade
     note ([research.md](research.md) R5).
4. **Phase 4, task worker saturation** (story 4).
5. **Phase 6, ratio without restart** (story 6):
   - Public endpoints under `/api/troubleshooting` with their OpenAPI description (FR-036), message,
     event, and the log line of FR-035. Regenerate `schema/openapi.json` and the frontend REST types.
     Approved by Damien Garros on 2026-10-15 (see Constitution Check).
   - The SDK `infrahubctl` command, [IFC-3420](https://opsmill.atlassian.net/browse/IFC-3420), on SDK
     branch `dp-20261015-trace-sample-ratio-command-ifc-3420`, after the endpoints exist. Its name and
     options follow the SDK's CLI guide (`infrahub_sdk/ctl/AGENTS.md`).
6. **Documentation** for each phase, the new page for operators with their own monitoring, and the
   operator steps of FR-034: raise the ratio, check every process applied it, reduce the cost of
   tracing.
7. **SDK pull requests and the submodule pointer**:
   - The SDK branches are stacked: `dp-20261015-trace-context-ifc-3419` starts from
     `origin/infrahub-develop`, and `dp-20261015-trace-sample-ratio-command-ifc-3420` starts from the
     IFC-3419 branch. Their pull requests target `infrahub-develop` and the IFC-3419 branch; GitHub moves
     the second one to `infrahub-develop` when the first merges. If IFC-3419 changes during review, the
     IFC-3420 branch is rebased on it. The submodule stays on the IFC-3420 branch, which has both
     changes.
   - Each SDK branch passes `uv run invoke format lint-code`, `uv run pytest tests/unit/` and, for
     IFC-3420, `uv run invoke docs-generate`, and gets an SDK changelog fragment.
   - While the SDK branches are not merged, `python_sdk` shows as modified in Infrahub. Infrahub
     commits leave the submodule pointer out until both SDK pull requests merge.
   - Both SDK pull requests merge before the manual test (step 8). Then the Infrahub branch moves
     `python_sdk` to `origin/infrahub-develop` (root `AGENTS.md`, "Submodules").
   - Pushing and opening pull requests happen only when Daniel asks.
8. **Manual test**: after the implementation and after both SDK pull requests merge, Daniel runs the
   `opsmill-dev-guiding-manual-tests` skill on the Infrahub branch, with `python_sdk` on
   `origin/infrahub-develop`. It uses the checks of [quickstart.md](quickstart.md).
9. **Before release**: quickstart manual check 7 (each dashboard imported into a Grafana with only
   Prometheus) and the check of the downloaded Compose file are required, not optional.

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
  unmerged one below it.
- Review: a layer is marked ready for review when the layer below it is approved (decided by Daniel on
  2026-10-16). The spec layer and IFC-3425 merge together, so both were marked ready at once. Each
  pull request shows only its own diff, so several layers can be under review at the same time.
  Before marking a layer ready, run `gh stack sync` and check that its CI passes.
- A fix in a lower layer is made in that layer, then `gh stack rebase --upstack` replays the layers
  above. Each layer ticks its own tasks in this file and records its own spec updates.
- A2 is tested with `python_sdk` on the S1 branch; it does not wait for S1 to merge. Only C1 commits
  the `python_sdk` pointer, after S1 and S2 merge. Then Daniel runs `opsmill-dev-guiding-manual-tests`
  (T093).
- Each pull request opens as a draft (`gh stack submit --auto`), after Daniel's manual test of the
  layer. Force-pushing commands
  (`gh stack sync`, `gh stack rebase`) run only while it is a draft, or after its review has landed.
  Push and open pull requests only when Daniel asks.
- IFC-3425 also fixes [IFC-3330](https://opsmill.atlassian.net/browse/IFC-3330).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Wrap the private `acquire` method of the Neo4j driver pool (Principle VII: follow established patterns) | The driver 6.2 has no public hook for the time a query waits for a connection (FR-017). Infrahub already reads the same private pool for `infrahub_db_last_connection_pool_usage`. | Measure around each query: misses reads that run outside a transaction, and includes query time. A unit test fails if a driver upgrade removes the method, and a recording failure is logged, never raised. |
| No pytest-playwright E2E test (Principle IV) | The feature changes telemetry, settings and a REST endpoint; it adds no page to the web interface. | An E2E test would only drive Grafana, which is not Infrahub's interface. Component tests cover the REST endpoint; [quickstart.md](quickstart.md) covers the Grafana views. |
