# Quickstart / Validation: Licensing Resource-Allocation Telemetry

How to prove the feature works end-to-end. Shapes and rules are in [data-model.md](data-model.md) and [contracts/telemetry-resources.md](contracts/telemetry-resources.md); this file is the run guide, not the implementation. All figures use the `processor_*` / `memory_*` field names (uniform with the existing `system_info`).

## Prerequisites

- Backend dev environment (`uv sync --all-groups`).
- Docker available for the component tests. `test_resources.py` uses testcontainers Neo4j; `test_cgroup_kernels.py` additionally needs the daemon's host to run cgroup v2 (it skips itself otherwise) and network access on first run, since its probe image build pulls a base image and installs into it — so the full component suite does not run offline. Export the docker socket if needed: `DOCKER_HOST=unix://$HOME/.docker/run/docker.sock`.

## Scenario 1 — Unit: cgroup + host reading (`backend/tests/unit/telemetry/test_resources.py`)

No services. Point the reader at fixture cgroup files.

- **cgroup v2, CPU limited**: `cpu.max = "400000 100000"` → `processor_assigned == 4`.
- **cgroup v2, CPU unlimited**: `cpu.max = "max 100000"` → `processor_assigned is None` (no fallback to `processor_available`).
- **cgroup v2, memory limited**: `memory.max = "8589934592"` → `memory_total == 8589934592`; `memory.current` → `memory_available == max(0, memory_total − current)` (clamped, since a limit lowered below current usage would otherwise go negative).
- **cgroup v2, memory unlimited**: `memory.max = "max"` → `memory_total` falls back to `psutil.virtual_memory().total` (capacity is never `None` on a normal host).
- **cgroup v1, CPU limited**: `cpu.cfs_quota_us = 200000`, `cpu.cfs_period_us = 100000` → `processor_assigned == 2`.
- **cgroup v1, unlimited**: `cpu.cfs_quota_us = -1` → `processor_assigned is None`.
- **Fractional**: `cpu.max = "150000 100000"` → `processor_assigned == 2` (the cap, rounded up) and `processor_available == 1` (the usable figure, rounded down, floor 1).
- **Missing cgroup files** (the `missing_files` CPU case and the `missing_files_fall_back_to_host` memory case, standing in for non-Linux): `processor_assigned is None`; `processor_available` and `memory_*` still come from psutil. This exercises the fallback path itself, not an actual non-Linux platform. Two guards skip by platform: `needs_host_cores` skips the `processor_available` cases where psutil reports no logical CPU count, and `test_cgroup_kernels.py` skips without a Docker daemon on a cgroup v2 host.
- **CPU-affinity cap without a quota** (the `cpuset_without_quota_caps_available_by_affinity` real-kernel case in `backend/tests/component/telemetry/test_cgroup_kernels.py`, mirrored by the `affinity_narrower_than_host_and_quota` case in `backend/tests/unit/telemetry/test_resources.py`): a `cpuset` restriction with no CPU-time quota configured still caps `processor_available` to the pinned CPU count.

**Expected**: all cases pass; `processor_available` is logical, never physical, and equals the host's `psutil.cpu_count(logical=True)` capped by the tightest of the CPU quota rounded down (floor 1) and the process's CPU-affinity mask (a `cpuset` restriction can cap it even with no quota configured) — `cpu.max = "100000 100000"` → `processor_available == 1` on any host.

## Scenario 2 — Unit: per-worker share (`backend/tests/unit/telemetry/test_tasks.py`)

Feed synthetic per-process readings to `_per_worker_share()`; assert one worker's share of its container (the four figures). Each case is a `SHARE_CASES` entry of the parametrized `test_per_worker_share`:

- `one_process_per_container_keeps_the_container_figures`: readings from hosts `w1` and `w2`, each `processor_available=4` → `processor_available == 4.0`, the container's own figures.
- `processes_of_one_container_split_it_evenly`: 4 readings from host `api` with 4 CPUs and 8 GB → `processor_available == 1.0`, `memory_total == 2_000_000_000`.
- `an_uneven_split_rounds_processors_to_two_decimals`: 3 readings from one host with 4 CPUs → `processor_available == 1.33`; memory divided by floor division.
- `more_processes_than_processors_gives_a_fraction`: 4 readings from one host with 2 CPUs → `processor_available == 0.5`.
- `a_failed_read_is_not_counted_as_a_sharer`: 2 healthy readings and 1 `WorkerResourceReading.failed()` → divided by 2, not 3.
- `the_most_complete_reading_is_used_and_partial_ones_still_share`: a reading missing `memory_total` and a complete one from the same host → the complete one's figures, divided by 2.
- `no_readings_reports_nothing` and `only_failed_reads_reports_nothing`: every figure `None`.

## Scenario 3 — Component: end-to-end gather (`backend/tests/component/telemetry/test_resources.py`)

Run the gather against the testcontainers Neo4j with synthesized heartbeat keys in the cache.

```bash
DOCKER_HOST=unix://$HOME/.docker/run/docker.sock \
  uv run pytest backend/tests/component/telemetry/test_resources.py -q
```

- Seed `workers:active:git_agent:worker:*` + matching `workers:resources:git_agent:worker:*` for two hosts, api_server keys for three processes on one host, and one process known only by its presence key (`workers:worker:*`), standing in for a process that stopped recently.
- Call the gather; inspect the built `TelemetryData` (`database.system_info`, `workers`, and the new `server` and `task_workers` blocks).

**Expected**:

- `database.system_info`: `processor_available` > 0, `memory_total` > 0, and the new `processor_assigned is None`, since the test Neo4j leaves `server.cypher.parallel.worker_limit` at its default.
- `server.per_worker` is a third of the api_server container's figures, since three processes share it.
- `task_workers` counts the two git_agent processes (2 total, 2 active) and `server` the three api_server ones (3 total, 3 active). `workers` counts every worker process (6 total, 5 active), including the process known only by its presence key, which neither new block counts.
- `task_workers.per_worker` equals one git_agent container's figures.
- Force the database `worker_limit` read to fail → only `database.system_info.processor_assigned` is `None`; the snapshot is still produced (FR-006). This holds for that read only, which is guarded on its own; a failure of the JMX read behind the other `system_info` figures aborts the snapshot.

## Scenario 4 — Opt-out still stores locally (FR-006/FR-007)

With `telemetry_optout = true`, run the flow; confirm the locally stored snapshot still carries the new resource fields (`task_workers.per_worker`, `server.per_worker`, `system_info.processor_assigned`) and nothing is transmitted.

## Scenario 5 — Backward compatibility (SC-005)

Assert `payload_format` is **unchanged** (`20260628` — the bump is deferred, research D13), every previously-emitted key in `data` is still present with its type unchanged, and the new fields are purely additive. `workers` has exactly its earlier keys, `total` and `active`, which still count every worker process; the only new top-level keys are `server` and `task_workers` (research D17).

## Full suite

```bash
uv run invoke backend.test-unit                          # scenarios 1–2
DOCKER_HOST=unix://$HOME/.docker/run/docker.sock \
  uv run pytest backend/tests/component/telemetry -q      # scenarios 3–5
```

Do not trigger the real `send_telemetry_push` flow against the production endpoint during validation — it POSTs to the live telemetry receiver. Opt out first, or exercise the gather directly.
