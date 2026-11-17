# Manual checks: layer 3, IFC-3429 (dashboards in any Grafana)

- **Branch:** `dp-20261016-portable-dashboards-ifc-3429`
- **Base:** `dp-20261016-slow-component-metrics-ifc-3428` (the layer below)
- **Head at start:** `ddbd65c29` ("fix(dashboards): make the shipped dashboards correct and portable to any
  Grafana [IFC-3429]")
- **Uncommitted changes at start:** none
- **Started:** 2026-10-16
- **Environment:** local stack on Docker Desktop for macOS, Neo4j Enterprise, 4 API workers, 2 task
  workers, Grafana at http://localhost:3500

## Checks

| # | Check | What changed | Source | Outcome |
|---|-------|--------------|--------|---------|
| 1 | The Infrahub dashboard looks as before, with template variables for job and container | Template variables in `infrahub_monitoring.json` | Story 5 scenario 2; FR-022; T062 | pass |
| 2 | The "Connection Pool" row shows pool usage against pool size, and the connection wait | New row | Story 3 scenario 5; FR-017; T048 | pass |
| 3 | The admission panels have their new names and say they are not the Neo4j connection pool | Renamed panels | Story 3 scenario 6; FR-019; T048 | pass |
| 4 | The "Priority Queues" row shows the start delay p95 and the runs in progress per queue | New row | FR-021; T054 | pass |
| 5 | The Prefect dashboards count runs, show log lines, and have no broken panels | `prefect_flow_run_overview.json`, `prefect_platform_overview.json` | Story 5 scenarios 3 to 5; FR-023, FR-024; T058, T059 | pass |
| 6 | The Neo4j dashboard explains the Enterprise panels, and the Neo4j scrape can be turned off | `neo4j_monitoring.json`, `config.alloy`, `docker-compose-observability.yml` | Story 5 scenario 6; FR-025; T060, T061 | pass |
| 7 | A shipped dashboard works in a Grafana with only a Prometheus data source | All dashboard files | Story 5 scenario 1; FR-022; quickstart manual check 7 | bug, fixed in `33995f1b5`, then pass |
| 8 | Automated tests | `test_grafana_dashboards.py` and the full unit suite | T057, T064 | pass |

### Known limits of this environment

- The Prefect CPU and memory panels (story 5 scenario 5) can only be checked on a Linux host: on Docker
  Desktop for macOS, cAdvisor sends no container names (research R6).

## Results

### Check 1: pass

Infrahub Monitoring (`Kn5xm-gZ3`), last hour: visible variables Prometheus, Loki, Application, Container,
percentile; rows Overview, Admission Controller, DB Stress Signal, Details Requests, Details DB
Query/GraphQL, Connection Pool, Priority Queues, Logs; no Redis row; panels have data; no panel error.

### Check 2: pass

Connection Pool row: "Highest Connection Pool Usage" about 1 %; "Connection Pool Usage vs Size (per
process)" with the pool size at 100 and the usage near 1 per process; "Connection Wait (p95)" near 0.

### Check 3: pass

Admission Controller row: "Running API Requests vs Admission Limit" and "Admission Limit Usage", both
descriptions ending with "This is not the Neo4j connection pool."; no old names left. The descriptions
still say "total pool capacity" for the admission slots; Daniel accepted that wording.

### Check 4: pass

Priority Queues row: "Flow Run Start Delay p95 by Queue" shows a `high` series; "Flow Runs in Progress by
Queue" shows a `high` series at 0. Prometheus confirms both `infrahub_task_flow_runs_in_progress` series
(`create-branch`, `git-repositories-create-branch`, `queue="high"`) exist, with a highest value of 0 in
15 minutes while `infrahub_task_flow_run_start_delay_seconds_count` rose by 1 for each flow: the runs
lasted a few seconds and ended between two 15 s collections. Rise and fall are covered by unit tests.

### Check 5: pass

Prefect / Platform Overview and Prefect / Flow Runs Overview: `namespace` list offers `prefect`; run
counts, flow, deployment, work pool and work queue totals show numbers ("Work Queues total" is on
Platform Overview only, value 4); both Platform Overview "Logs" panels show lines; no run time panel and
no `flow_run_name` variable; no panel error. Known empty panels: CPU and memory and "Task workers"
(cAdvisor sends no container names on Docker Desktop for macOS, research R6), and "Flow logs", whose
query looks for a `pod` label that contains the flow name while the local `pod` values are
`prefect-agent`, `prefect-exporter` and `prefect-server`; this query is unchanged by this branch and not
required by FR-023.

### Check 6: pass

Neo4j dashboard: the "Neo4j Enterprise metrics" note is at the top; `neo4j_*` panels show data on this
Enterprise stack. With `INFRAHUB_NEO4J_METRICS_TARGET=` (empty), Alloy was recreated with
`NEO4J_METRICS_TARGET=` and `count(count_over_time(neo4j_dbms_vm_heap_used[30s]))` returned no result;
the Alloy log had no line about the `database` target. After `INFRAHUB_DEBUG=true uv run invoke
dev.start`, Alloy had `NEO4J_METRICS_TARGET=database:2004` again and the query returned 1.

Observed, not caused by this branch:

- The Alloy log has `failed to decode logfmt` errors from `loki.process.pipeline` (`stage.logfmt` at
  `development/alloy/config.alloy:172`): about 100,000 in a few seconds when Alloy starts and reads the
  container logs again, then about 6 per second. The diff of `config.alloy` has no logfmt change.
- The comment at `development/alloy/config.alloy:309` says `NEO4J_METRICS_TARGET` "is empty unless one is
  enabled", but the default is `database:2004` (this comment is from this branch).

### Check 7: bug

Setup: a second Grafana 11.4.0 on port 3501 (container `grafana-check7`) with one data source, "Other
Prometheus" (uid `other-prometheus`), pointing at the dev Prometheus, and the shipped dashboard files
mounted read-only.

- **Expected:** the Infrahub panels show data with "Other Prometheus"; no panel shows "data source not
  found"; only Loki panels may be empty.
- **Observed:**
  - "Infrahub Monitoring": "Number Slow Queries (>0.5s)" (row "Details DB Query/GraphQL") shows an
    error: the data source was not found.
  - "Neo4j": most panels show the same error.
- **Cause found while preparing the check:** these panels set the data source to the fixed uid
  `localprometheus` instead of `${datasource_prometheus}`:
  - `infrahub_monitoring.json`: 1 panel, "Number Slow Queries (>0.5s)".
  - `neo4j_monitoring.json`: 10 panels ("Neo4j status", "Committed Transaction Speed", "Last Committed
    Write Transaction ID", "Rolled back Transaction Speed", "Memory usage", "Transactions", "Counters of
    Graph Items", "Number Slow Queries (>0.5s)", "Query Response Times", "Query Latency Percentiles").
  - `container_resources.json` ("Docker Containers Monitoring"): the queries of 2 panels, "Network
    Traffic on Node" and "Running Containers".
- The same uids are in the base commit, so this branch did not add them, but FR-022 requires every
  shipped dashboard to work in any Grafana, and `test_grafana_dashboards.py` does not test data source
  uids.

### Check 8: pass

`uv run pytest backend/tests/unit/test_grafana_dashboards.py -q`: 29 passed. Full unit suite, without the
`INFRAHUB_TRACE_*` variables of the developer's shell: 4560 passed.

### Check 7, repeated after `33995f1b5`: pass

Same second Grafana: "Number Slow Queries (>0.5s)" on Infrahub Monitoring, the Neo4j panels and Docker
Containers Monitoring show no "data source not found" error; Infrahub and Neo4j panels show data.

## Decisions

| # | Observation | Decision | Result |
|---|-------------|----------|--------|
| 1 | Check 7: panels and queries use the fixed data source uid `localprometheus` | Fix now and commit | `33995f1b5`; check 7 repeated: pass |
| 2 | The comment at `development/alloy/config.alloy:309` describes the wrong default for `NEO4J_METRICS_TARGET` | Fix now and commit | `33995f1b5` |
| 3 | Alloy logs `failed to decode logfmt` for every log line that is not logfmt | Separate bug on the board | [INBOX-366](https://opsmill.atlassian.net/browse/INBOX-366) |
| 4 | The "Flow logs" panel on "Prefect / Flow Runs Overview" is always empty | Separate bug on the board | [INBOX-367](https://opsmill.atlassian.net/browse/INBOX-367) |

## Final report

- **Head after fixes:** `33995f1b5`.
- Checks 1 to 6 and 8: pass. Check 7: bug, fixed in `33995f1b5`, then pass.
- Open items: none in this layer. INBOX-366 and INBOX-367 are outside INFP-742.
- Next step: open the draft pull request for this layer.
