# Quickstart / Validation: Licensing Resource-Allocation Telemetry

How to prove the feature works end-to-end. Shapes and rules are in [data-model.md](data-model.md) and [contracts/telemetry-resources.md](contracts/telemetry-resources.md); this file is the run guide, not the implementation.

## Prerequisites

- Backend dev environment (`uv sync --all-groups`).
- Docker available for the component test (testcontainers Neo4j). Export the docker socket if needed: `DOCKER_HOST=unix://$HOME/.docker/run/docker.sock`.

## Scenario 1 — Unit: cgroup + host reading (`backend/tests/unit/telemetry/test_resources.py`)

No services. Point the reader at fixture cgroup files.

- **cgroup v2, limited**: `cpu.max = "400000 100000"` → `cores_assigned == 4`. `memory.max = "8589934592"` → `ram_available == 8589934592`.
- **cgroup v2, unlimited**: `cpu.max = "max 100000"` → `cores_assigned is None` (no fallback to `cores_available`).
- **cgroup v1, limited**: `cpu.cfs_quota_us = 200000`, `cpu.cfs_period_us = 100000` → `cores_assigned == 2`.
- **cgroup v1, unlimited**: `cpu.cfs_quota_us = -1` → `None`; `memory.limit_in_bytes` at the near-`INT64_MAX` sentinel → `None`.
- **Fractional**: `cpu.max = "150000 100000"` → `cores_assigned == 2` (rounded up).
- **Non-Linux / missing files**: reader returns `None` for `cores_assigned`/cgroup fields, and host figures still come from psutil.

**Expected**: all cases pass; `cores_available` is always logical (`os.cpu_count()`), never physical.

## Scenario 2 — Unit: aggregation (`backend/tests/unit/telemetry/test_aggregation.py`)

Feed synthetic per-process readings; assert the fleet aggregate.

- **Dedup**: 8 api_server readings, all `host="c1"`, `cores_available=4` → `server.cores_available == 4` (counted once).
- **Sum across hosts**: 2 git_agent readings `host="w1"` and `host="w2"`, each `cores_available=4` → `workers.cores_available == 8`, `workers.count == 2`.
- **Undercount (FR-005)**: 3 active git_agent processes, only 2 reported readings → aggregate sums the 2, `workers.count == 3` (gap detectable).
- **Null-vs-zero (FR-003/D9)**: one contributing host `cores_assigned=None` (unlimited) → aggregate `cores_assigned is None`. Zero active workers → `count == 0`, aggregate fields `== 0`.

## Scenario 3 — Component: end-to-end gather (`backend/tests/component/telemetry/test_resources.py`)

Run the gather against the testcontainers Neo4j with synthesized heartbeat keys in the cache.

```bash
DOCKER_HOST=unix://$HOME/.docker/run/docker.sock \
  uv run pytest backend/tests/component/telemetry/test_resources.py -q
```

- Seed `workers:active:git_agent:worker:*` + matching `workers:resources:git_agent:worker:*` for two hosts, and api_server keys for one host.
- Call the gather; inspect `TelemetryData.resources`.

**Expected**:
- `resources.database` populated from JMX: `cores_available` > 0, `ram_available` > 0, `cores_assigned is None`.
- `resources.server` reflects the one api_server host (not multiplied by process count).
- `resources.workers.count == 2` and aggregates equal the host sum.
- Force one metric source to raise → only that field is `None`; the snapshot is still produced (FR-006).

## Scenario 4 — Opt-out still stores locally (FR-006/FR-007)

With `telemetry_optout = true`, run the flow; confirm the locally stored snapshot still contains a fully-formed `resources` block and nothing is transmitted.

## Scenario 5 — Backward compatibility (SC-005)

Assert `payload_format` is the new value and that every previously-emitted key in `data` is still present and unchanged; `resources` is purely additive.

## Full suite

```bash
uv run invoke backend.test-unit                          # scenarios 1–2
DOCKER_HOST=unix://$HOME/.docker/run/docker.sock \
  uv run pytest backend/tests/component/telemetry -q      # scenarios 3–5
```

Do not trigger the real `send_telemetry_push` flow against the production endpoint during validation — it POSTs to the live telemetry receiver. Opt out first, or exercise the gather directly.
