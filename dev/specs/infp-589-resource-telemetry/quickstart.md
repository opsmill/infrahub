# Quickstart / Validation: Licensing Resource-Allocation Telemetry

How to prove the feature works end-to-end. Shapes and rules are in [data-model.md](data-model.md) and [contracts/telemetry-resources.md](contracts/telemetry-resources.md); this file is the run guide, not the implementation. All figures use the `processor_*` / `memory_*` field names (uniform with the existing `system_info`).

## Prerequisites

- Backend dev environment (`uv sync --all-groups`).
- Docker available for the component test (testcontainers Neo4j). Export the docker socket if needed: `DOCKER_HOST=unix://$HOME/.docker/run/docker.sock`.

## Scenario 1 — Unit: cgroup + host reading (`backend/tests/unit/telemetry/test_resources.py`)

No services. Point the reader at fixture cgroup files.

- **cgroup v2, CPU limited**: `cpu.max = "400000 100000"` → `processor_assigned == 4`.
- **cgroup v2, CPU unlimited**: `cpu.max = "max 100000"` → `processor_assigned is None` (no fallback to `processor_available`).
- **cgroup v2, memory limited**: `memory.max = "8589934592"` → `memory_total == 8589934592`; `memory.current` → `memory_available == memory_total − current`.
- **cgroup v2, memory unlimited**: `memory.max = "max"` → `memory_total` falls back to `psutil.virtual_memory().total` (capacity is never `None` on a normal host).
- **cgroup v1, CPU limited**: `cpu.cfs_quota_us = 200000`, `cpu.cfs_period_us = 100000` → `processor_assigned == 2`.
- **cgroup v1, unlimited**: `cpu.cfs_quota_us = -1` → `processor_assigned is None`.
- **Fractional**: `cpu.max = "150000 100000"` → `processor_assigned == 2` (rounded up).
- **Non-Linux / missing files**: `processor_assigned is None`; `processor_available` and `memory_*` still come from psutil.

**Expected**: all cases pass; `processor_available` is always logical (`psutil.cpu_count(logical=True)`), never physical.

## Scenario 2 — Unit: aggregation (`backend/tests/unit/telemetry/test_aggregation.py`)

Feed synthetic per-process readings; assert the deduped fleet aggregate (the four fields).

- **Dedup**: 8 readings all `host="c1"`, `processor_available=4` → aggregate `processor_available == 4` (counted once).
- **Sum across hosts**: 2 readings `host="w1"` and `host="w2"`, each `processor_available=4` → aggregate `processor_available == 8`.
- **Undercount (FR-005)**: 3 processes, only 2 distinct hosts reported → aggregate sums the 2 (the caller's `workers.total`, tracked separately, still counts all 3, so the gap is detectable).
- **Null rules (FR-003/D9)**: one contributing host `processor_assigned=None` (unlimited) → aggregate `processor_assigned is None`; no host reported a field → that field is `None`.

## Scenario 3 — Component: end-to-end gather (`backend/tests/component/telemetry/test_resources.py`)

Run the gather against the testcontainers Neo4j with synthesized heartbeat keys in the cache.

```bash
DOCKER_HOST=unix://$HOME/.docker/run/docker.sock \
  uv run pytest backend/tests/component/telemetry/test_resources.py -q
```

- Seed `workers:active:git_agent:worker:*` + matching `workers:resources:git_agent:worker:*` for two hosts, and api_server keys for one host.
- Call the gather; inspect the built `TelemetryData` (`database.system_info`, `workers`, and the new `server` block).

**Expected**:
- `database.system_info`: `processor_available` > 0, `memory_total` > 0, and the new `processor_assigned is None`.
- the new `server` block reflects the one api_server host (not multiplied by gunicorn process count).
- `workers.total == 2` is unchanged; the new `workers.processor_*`/`memory_*` equal the git_agent host sum.
- Force one metric source to raise → only that field is `None`; the snapshot is still produced (FR-006).

## Scenario 4 — Opt-out still stores locally (FR-006/FR-007)

With `telemetry_optout = true`, run the flow; confirm the locally stored snapshot still carries the new resource fields (`workers.processor_*`/`memory_*`, the `server` block, `system_info.processor_assigned`) and nothing is transmitted.

## Scenario 5 — Backward compatibility (SC-005)

Assert `payload_format` is **unchanged** (`20260628` — the bump is deferred, research D13), every previously-emitted key in `data` is still present and unchanged, and the new fields are purely additive.

## Full suite

```bash
uv run invoke backend.test-unit                          # scenarios 1–2
DOCKER_HOST=unix://$HOME/.docker/run/docker.sock \
  uv run pytest backend/tests/component/telemetry -q      # scenarios 3–5
```

Do not trigger the real `send_telemetry_push` flow against the production endpoint during validation — it POSTs to the live telemetry receiver. Opt out first, or exercise the gather directly.
