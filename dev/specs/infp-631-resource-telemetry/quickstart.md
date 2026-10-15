# Quickstart / Validation: Licensing Resource-Allocation Telemetry

How to prove the feature works end-to-end. Shapes and rules are in [data-model.md](data-model.md) and [contracts/telemetry-resources.md](contracts/telemetry-resources.md); this file is the run guide, not the implementation. All figures use the `processor_*` / `memory_*` field names (uniform with the existing `system_info`).

## Prerequisites

- Backend dev environment (`uv sync --all-groups`).
- Docker available for the component tests. `test_resources.py` uses testcontainers Neo4j; `test_cgroup_kernels.py` also starts its containers through testcontainers, and additionally needs the daemon's host to run cgroup v2 (it skips itself otherwise) and network access on first run, since its probe image build pulls a Python base image matching the test interpreter and installs the locked `psutil` and `pydantic` versions into it — so the full component suite does not run offline. Export the docker socket if needed: `DOCKER_HOST=unix://$HOME/.docker/run/docker.sock`.

## Scenario 1 — Unit: cgroup + host reading (`backend/tests/unit/telemetry/test_resources.py`)

No services. Point the reader at fixture cgroup files.

- **cgroup v2, CPU limited**: `cpu.max = "400000 100000"` → `processor_assigned == 4`.
- **cgroup v2, CPU unlimited**: `cpu.max = "max 100000"` → `processor_assigned is None` (no fallback to `processor_available`).
- **cgroup v2, memory limited**: `memory.max = "8589934592"` → `memory_total == 8589934592`; `memory.current` → `memory_available == max(0, memory_total − current)` (clamped, since a limit lowered below current usage would otherwise go negative).
- **cgroup v2, memory unlimited**: `memory.max = "max"` → `memory_total` falls back to `psutil.virtual_memory().total` (capacity is never `None` on a normal host).
- **cgroup v1, CPU limited**: `cpu.cfs_quota_us = 200000`, `cpu.cfs_period_us = 100000` → `processor_assigned == 2`.
- **cgroup v1, unlimited**: `cpu.cfs_quota_us = -1` → `processor_assigned is None`.
- **Fractional**: `cpu.max = "150000 100000"` → `processor_assigned == 2` (the cap, rounded up) and `processor_available == 1` (the usable figure, rounded down, floor 1).
- **Missing cgroup files** (the `missing_files_report_the_machine` CPU case and the `missing_files_fall_back_to_the_machine` memory case, standing in for non-Linux): `processor_assigned is None`; `processor_available` and `memory_*` come from the machine, which is psutil in production and a fixed test machine (18 CPUs, 64 GiB, 48 GiB free) in the unit tests. This exercises the fallback path itself, not an actual non-Linux platform. `test_cgroup_kernels.py` skips without a Docker daemon on a cgroup v2 host.
- **CPU-affinity cap without a quota** (the `cpuset_without_quota_caps_available_by_affinity` real-kernel case in `backend/tests/component/telemetry/test_cgroup_kernels.py`, mirrored by the `pinning_without_a_limit_caps_available` case in `backend/tests/unit/telemetry/test_resources.py`): a `cpuset` restriction with no CPU-time quota configured still caps `processor_available` to the pinned CPU count.

**Expected**: all cases pass; `processor_available` is logical, never physical, and equals the host's `psutil.cpu_count(logical=True)` capped by the tightest of the CPU quota rounded down (floor 1) and the process's CPU-affinity mask (a `cpuset` restriction can cap it even with no quota configured) — `cpu.max = "100000 100000"` → `processor_available == 1` on any host.

## Scenario 2 — Unit: per-container figures and the process count (`backend/tests/unit/telemetry/test_tasks.py`, `backend/tests/unit/serve/test_processes.py`)

Feed a component's workers and synthetic per-process readings to `_component_data()`; assert the whole block: `total`, `active`, `processes_per_container` and `per_container`. Each case is a `COMPONENT_CASES` entry of the parametrized `test_component_data`:

- `a_shared_container_is_reported_whole_with_its_process_count`: 3 active workers, each with a reading of a container shared by 3 processes, with 6 CPUs, 12 GB and 9 GB free → `processes_per_container == 3` and the container's figures undivided.
- `the_most_complete_reading_is_used`: a reading missing `memory_total` and a reading that has it → the second one's figures.
- `a_reading_without_figures_still_gives_the_process_count`: a reading with only its count → `processes_per_container == 1`, every figure `None`.
- `no_reading_leaves_the_figures_and_the_process_count_unknown`: 1 active and 1 inactive worker and no reading → `total == 2`, `active == 1`, `processes_per_container` and every figure `None`.

The count each reading carries comes from `processes_per_container()`. Each case of the parametrized `test_processes_per_container` sets or removes `INFRAHUB_INTERNAL_PROCESSES_PER_CONTAINER`:

- `gunicorn_set_the_count`: `"4"` → 4.
- `a_process_gunicorn_did_not_start_runs_alone`: unset → 1.
- `zero_is_not_a_count`, `a_negative_value_is_not_a_count` and `text_is_not_a_count`: `"0"`, `"-2"` and `"four"` → 1.

## Scenario 3 — Component: end-to-end gather (`backend/tests/component/telemetry/test_resources.py`)

Run the gather against the testcontainers Neo4j with synthesized heartbeat keys in the cache.

```bash
DOCKER_HOST=unix://$HOME/.docker/run/docker.sock \
  uv run pytest backend/tests/component/telemetry/test_resources.py -q
```

- Seed `workers:active:git_agent:worker:*` + matching `workers:resources:git_agent:worker:*` for two git_agent processes, each alone in its container, api_server keys for three processes whose readings say three processes share their container, and one process known only by its presence key (`workers:worker:*`), standing in for a process that stopped recently.
- Call the gather; inspect the built `TelemetryData` (`database.system_info`, `workers`, and the new `server` and `task_workers` blocks).

**Expected**:

- `database.system_info`: `processor_available` > 0, `memory_total` > 0, the new `processor_assigned is None`, since the test Neo4j leaves `server.cypher.parallel.worker_limit` at its default, and the new `memory_assigned` is 1610612736, the 1 GiB heap plus the 512 MiB page cache the test Neo4j sets.
- `server.per_container` is the api_server container's figures, undivided, and `server.processes_per_container` is 3, since three processes share it.
- `task_workers` counts the two git_agent processes (2 total, 2 active) and `server` the three api_server ones (3 total, 3 active). `workers` counts every worker process (6 total, 5 active), including the process known only by its presence key, which neither new block counts.
- `task_workers.per_container` equals one git_agent container's figures, and `task_workers.processes_per_container` is 1.
- The gather logs no warning. A failed `worker_limit` read would also leave `processor_assigned` as `None`, and a failed heap and page cache read would leave `memory_assigned` as `None`, so the absence of a warning is what shows both reads worked.
- No figure is written as a whole-number decimal such as `2.0`: every figure is a whole number and goes out as a JSON integer, which the telemetry endpoint's checksum needs.
- Force the database `worker_limit` read to fail → only `database.system_info.processor_assigned` is `None`; force the heap and page cache read to fail → only `database.system_info.memory_assigned` is `None`. Either way the snapshot is still produced (FR-006). This holds for those two reads only, each guarded on its own, which is guarded on its own; a failure of the JMX read behind the other `system_info` figures aborts the snapshot.

## Scenario 4 — Opt-out still stores locally (FR-006/FR-007)

With `telemetry_optout = true`, run the flow; confirm the locally stored snapshot still carries the new resource fields (`task_workers.per_container`, `server.per_container`, the two `processes_per_container` counts, `system_info.processor_assigned`, `system_info.memory_assigned`) and nothing is transmitted. The flow stores the gathered payload unchanged, so no test of its own covers this: the opt-out branch is covered by `TestSendTelemetryPushOptedOut` in `backend/tests/unit/telemetry/test_workflow.py`, and the new fields by Scenario 3.

## Scenario 5 — Backward compatibility (SC-005)

`payload_format` stays `20260628` (the bump is deferred, research D13). Assert every previously-emitted key in `data` is still present and the new fields are purely additive. `workers` has exactly its earlier keys, `total` and `active`, which still count every worker process; the only new top-level keys are `server` and `task_workers` (research D17).

## Full suite

```bash
uv run invoke backend.test-unit                          # scenarios 1–2
DOCKER_HOST=unix://$HOME/.docker/run/docker.sock \
  uv run pytest backend/tests/component/telemetry -q      # scenarios 3 and 5
```

Do not trigger the real `send_telemetry_push` flow against the production endpoint during validation — it POSTs to the live telemetry receiver. Opt out first, or exercise the gather directly.
