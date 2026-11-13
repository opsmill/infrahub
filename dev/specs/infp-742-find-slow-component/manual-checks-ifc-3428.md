# Manual checks: layer 2, IFC-3428 (durations, connection pool, task worker saturation)

- **Branch:** `dp-20261016-slow-component-metrics-ifc-3428`
- **Base:** `dp-20261016-mask-telemetry-ifc-3425` (the layer below)
- **Head:** `b9f7c46cb` ("feat(metrics): record long durations, connection pool load and task worker
  saturation [IFC-3428]")
- **Uncommitted changes at start:** none
- **Started:** 2026-10-16
- **Report file:** this file. Layer 1 keeps its own report in `manual-checks.md`.

## Checks

| # | Check | What changed | Source | Outcome |
|---|-------|--------------|--------|---------|
| 1 | The HTTP metrics count `/api/…` and GraphQL requests, with their route as `path` | `starlette-exporter` 0.24 (B13) | Story 3 scenario 4; T040, T045 | pass |
| 2 | The duration histograms have the new upper buckets | Buckets in `server.py`, `database/metrics.py`, `lock.py` | Story 3 scenarios 1 to 3; T041, T046 | pass |
| 3 | The connection pool size and the connection wait are exported, per process | `database/connection_metrics.py`, `database/metrics.py` | Story 3 scenario 5 (metrics part); T042, T047 | pass |
| 4 | Restarting one API worker keeps the other workers' values, and a stopped worker no longer shows on the pool gauges | `serve/gunicorn_config.py`, `serve/worker.py`, `multiprocess_mode` | Story 3 scenarios 7 and 8; T039, T043, T044 | pass |
| 5 | A task worker records the start delay and the runs in progress, per flow and priority queue | `workers/metrics.py`, `workers/infrahub_async.py` | Story 4 scenarios 1 to 4; T051 to T053 | pass |
| 6 | Automated tests | All of the above | T050, T056 | pass |

### Spec scenarios without a manual check in this layer

- Story 3 scenarios 5 and 6 (pool panel and admission panel names on the dashboard) and story 4's
  "Priority queues" row are dashboard changes, tested in layer 3 (IFC-3429).
- A real 30-second query (story 3 scenario 1) and a lock held for 2 minutes (scenario 3) are hard to
  produce by hand; check 2 verifies the bucket limits, and the automated tests count a 30-second value
  in `le="30"`.

## Results

### Check 1: pass

After `GET /api/config` and `POST /graphql/main`, `infrahub_requests_total` shows
`path="/api/config"` (count 102) and `path="/graphql/{branch_name:path}"` (count 3), both with
`status_code="200"`. The GraphQL line uses the route, not the raw path.

### Check 2: pass

`/metrics` shows the new `le` limits: database queries up to `300.0`, HTTP requests up to `1200.0`, and
both lock histograms up to `300.0` (`30.0`, `60.0`, `120.0`, `300.0`).

### Check 3: pass

`infrahub_db_connection_pool_size` = 100.0 and `infrahub_db_last_connection_pool_usage` = 1.0 for each
of the 4 worker processes (pid 11 to 14). `infrahub_db_connection_wait_seconds`: 125 acquisitions, 0.07 s
in total, 117 under 1 ms and all under 1 s; highest limit `le="60.0"`.

### Check 4: pass

Stopped worker pid 14 with `kill -TERM`; gunicorn started pid 1414. The `/api/config` request count went
from 172 to 191 (no drop). `infrahub_db_connection_pool_size` then showed pid 11, 12, 13 and 1414, and
no line for pid 14.

### Check 5: pass

After `BranchCreate` of `manual-check-ifc-3428`: task worker 1 recorded `flow="create-branch"` and task
worker 2 `flow="git-repositories-create-branch"`, both with `queue="high"`, a start delay count of 1 and
runs in progress back to 0. The `medium` and `low` queues were not exercised by hand.

### Check 6: pass

Layer tests: 124 passed, including the 3 HTTP metric tests. Full backend unit suite: 4531 passed. A first
run of the full suite in a terminal with the manual-test `INFRAHUB_TRACE_*` variables exported failed 2
tests of `backend/tests/unit/config/test_trace_settings.py`, which read the environment; without those
variables they pass. CI sets these variables only in the end-to-end job, so CI is not affected. The test
file predates this feature (commit `24ba055d9`).

## Summary

All 6 checks passed on 2026-10-16. No bug and no skipped check. Next step: open the draft pull request
of IFC-3428.
