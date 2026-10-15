# Implementation Plan: Licensing Resource-Allocation Telemetry

**Branch**: `resource-telemetry-infp-631` | **Date**: 2026-07-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/infp-631-resource-telemetry/spec.md`

## Summary

Extend the daily telemetry payload to report logical CPU cores (available + assigned) and memory (total + available) for the **database** (in place, on its existing `system_info`), the **task workers** (a new `task_workers` section), and the **API server** (a new `server` section), each new section with its own process count, the number of processes that share a container (`processes_per_container`) and a `per_container` object, all using the existing `processor_*`/`memory_*` field names, so a deployment can be audited against its contracted tier from a single snapshot — including offline/air-gapped deployments.

Technical approach: reuse the existing telemetry gatherer, the `safe_metric` degradation boundary, the existing database JMX query, and the existing worker keys in the cache. The database row is derived from the JMX system-info the payload already collects. The server and worker figures are self-reported by each process into the cache, and the gatherer uses the readings of the active workers and reports, for each of the two components, one container's figures, undivided, with the number of processes that share that container. CPU/RAM figures come from `psutil` (promoted from a dev-only to a production runtime dependency — research D1) plus stdlib `/sys/fs/cgroup` reads for the enforced allocation limit. Because several `api_server` processes share one container/cgroup, each reading carries how many processes share its container: gunicorn's worker count for an API server process, which the gunicorn worker class puts in the process's environment, and 1 for any other process. The container's figures times the block's `active` count, divided by that number, is the component's total (research D19). No new third-party package — but `psutil` moves from a dev-only pin to a production runtime dependency, which is an Ask-First gate in its own right (Constraints, Governance). No database schema change, no branch-scoped data.

**Worker counts.** `workers` is unchanged: `total`/`active` count every worker process. Each new block describes one component, counts and resources alike: `server` the API server, `task_workers` the git_agent processes. `server.total + task_workers.total` equals `workers.total`, except for a process known only by its generic presence key, usually one that stopped about two hours earlier, which only `workers` counts (research D17).

## Technical Context

**Language/Version**: Python 3.14 (backend)

**Primary Dependencies**: Pydantic 2.12 (typed payload models), Prefect 3.8.6 (gather flow/tasks), `psutil==6.1.0` (promoted from dev-only to a production runtime dependency — host logical CPU count, CPU affinity, memory), stdlib `os` (the number of processes per container, from the environment), `pathlib`, `math`, `logging`, and `dataclasses` + `/sys/fs/cgroup` and `/proc/self/cgroup` reads (enforced cgroup limit), Neo4j driver (existing JMX for the database row), Redis-backed `InfrahubCache` (existing worker keys)

**Storage**: telemetry snapshot persisted via the existing snapshot repository; per-process resource readings transit through the cache, each kept for 2 hours (research D18), never persisted separately

**Testing**: pytest — unit (`backend/tests/unit/telemetry/`: cgroup parsing and path resolution, the per-container figures, the database setting parse; `backend/tests/unit/serve/`: the number of processes per container read from the environment; `backend/tests/unit/services/`: component attribution, storing the resource reading and keeping only the active workers' readings, the schedule registration) + component (`backend/tests/component/telemetry/`: end-to-end gather against the testcontainers Neo4j with synthesized worker heartbeats, and the reader against real kernel control groups in containers)

**Target Platform**: Linux server (containers). cgroup reads are Linux-only. Without them (e.g. developer macOS), memory falls back to psutil's whole-host figures and `processor_available` to the host's count, capped by CPU affinity where it is readable; only `processor_assigned` is `null`, which is acceptable because `assigned` is only meaningful where a limit is enforced

**Project Type**: Single backend service; changes localized to the telemetry module and the component/heartbeat service

**Performance Goals**: Cold daily path; cost is negligible. The existing `workers:*` key scan, plus a separate `workers:resources:*` key scan and a multi-get of those values (one per live process), plus a handful of local file reads per process every 5 minutes

**Constraints**: MUST NOT block or fail the snapshot; each source this feature reads degrades independently to `null` (the existing database JMX gather is not guarded and still aborts the snapshot on failure); payload changes are additive only and no existing field changes meaning (research D17), with the version bump gated on receiving-service confirmation rather than made this phase; **no new third-party package**, though `psutil` is promoted from a dev-only pin to a production runtime dependency (research D1, an Ask-First gate); cgroup v2 primary with a v1 fallback, psutil's whole-host figures where neither is present (only `processor_assigned` is then `null`)

**Scale/Scope**: A few components and a small number of workers per deployment (default `replicas: 2`). Trivial scale

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Notes |
|-----------|---------|-------|
| I. Schema-Driven Integrity | ✅ Pass | The telemetry payload is not Infrahub graph data; no node/attribute/relationship or generated-schema change. |
| II. Branch-Safe by Default | ✅ Pass | Resource figures are deployment-level, not branch-scoped. Where the gather touches the graph (existing node counts) it already runs on the default branch; no cross-branch writes, no merge semantics. |
| III. Type Safety & Explicit Contracts | ✅ Pass | New/extended resource fields are typed Pydantic (`int \| None`), never untyped dicts — extending `TelemetryDatabaseSystemInfoData` and adding `TelemetryComponentData` and `TelemetryContainerData`. |
| IV. Test Discipline | ✅ Pass | Unit tests for cgroup parsing, the per-container figures and the number of processes per container; component test for end-to-end gather incl. the FR-005 partial-report and FR-003 unlimited→`null` edges. Test files mirror source, except `test_cgroup_kernels.py`, which has no same-named source and runs `resources.py` against real kernel control groups. |
| V. Query Performance & Efficiency | ✅ Pass | Reuses the existing JMX call and the existing `workers:*` cache scan; adds one new lightweight `SHOW SETTINGS` read for `processor_assigned` and one `workers:resources:*` key scan with a single multi-get. No N+1, no large result sets. |
| VI. Security & Input Boundaries | ✅ Pass | Reads only local, trusted `/sys/fs/cgroup` and `/proc/self/cgroup` files, and one environment variable that the gunicorn worker class sets, which is used only when it is a positive whole number and otherwise counts as 1 — no user input, no injection surface. Cores/RAM are not PII; transmission remains gated by the existing opt-out. |
| VII. Simplicity & Maintainability | ✅ Pass (1 justified complexity) | Reuses `safe_metric`, the worker keys and active-worker set, and the JMX path; no new third-party package, though `psutil` is promoted to a production runtime dependency (Governance gate below). Reporting how many processes share a container, which the gunicorn worker class passes to each API server process, is the one non-obvious element — justified in Complexity Tracking. |

**Governance Ask-First gates**: New dependency — **none added**, but `psutil` is promoted from dev-only to a production runtime dependency (Ask-First confirmed, research D1). DB schema/migration — **none**. Auth — **none**. GraphQL/REST schema — **none** (telemetry payload is an internal contract with the receiving service, coordinated cross-team, not an Infrahub API). CI/CD — **none**.

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-631-resource-telemetry/
├── spec.md              # the input to this plan
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions + rationale
├── data-model.md        # Phase 1 output — Pydantic models + per-container rules
├── quickstart.md        # Phase 1 output — validation guide
├── contracts/
│   └── telemetry-resources.md   # payload contract for the receiving service
├── tasks.md             # Phase 2 output (/speckit-tasks)
├── alignment-check.md   # spec-to-plan alignment record
├── checklists/
│   └── requirements.md  # requirement-quality checklist
├── critiques/
│   └── critique-20260721-121437.md   # pre-implementation critique + erratum
└── opsmill-implement-report.md       # implementation record
```

### Source Code (repository root)

```text
backend/infrahub/telemetry/
├── models.py            # extend TelemetryDatabaseSystemInfoData (processor_assigned,
│                        #   memory_assigned);
│                        #   add TelemetryContainerData, TelemetryComponentData, and the
│                        #   server and task_workers fields on TelemetryData
├── resources.py         # NEW: read logical cores, CPU affinity + memory (psutil) and the
│                        #   cgroup limit (stdlib); WorkerResourceReading (the per-process
│                        #   reading the cache carries, with the number of processes per
│                        #   container) and ProcessResources (the reader)
├── database.py          # add processor_assigned to system_info via
│                        #   server.cypher.parallel.worker_limit (SHOW SETTINGS) — confirmed
│                        #   with the backend owner as the intended knob (research D3), and
│                        #   since adopted by the infrahub-enterprise chart presets as the
│                        #   Neo4j CPU budget (infrahub-helm#93); it caps the parallel
│                        #   runtime's workers, not Neo4j's total CPU use;
│                        #   add memory_assigned, heap max plus page cache (SHOW SETTINGS),
│                        #   research D20; existing processor_available/memory_* cover
│                        #   DB cores + RAM
└── tasks.py             # gather: counts each component's processes into the new server and
                         #   task_workers blocks and fills their processes_per_container and
                         #   per_container through _component_data() from
                         #   read_worker_resources()

backend/infrahub/services/
├── component.py         # InfrahubComponent.new() requires the reader;
│                        #   InfrahubComponent.refresh_resources() reads this process's
│                        #   resources and stores them for 2 hours; the gatherer reads
│                        #   the active workers' readings back through the new
│                        #   read_worker_resources() scan; WorkerInfo gains a component
│                        #   attribute, set by add_key from the process's own keys
└── scheduler.py         # registers the 5-minute resource_refresh schedule on the main loop

backend/infrahub/serve/
├── processes.py         # NEW: processes_per_container() reads the number of processes per
│                        #   container from INFRAHUB_INTERNAL_PROCESSES_PER_CONTAINER, 1 when
│                        #   it is missing or not a positive whole number
└── worker.py            # the InfrahubUvicorn gunicorn worker class sets that variable to
                         #   gunicorn's worker count before the app loads

backend/infrahub/workers/
└── dependencies.py      # build_component() builds ProcessResources with that number and
                         #   passes it to InfrahubComponent.new()

backend/infrahub/tasks/
└── recurring.py         # trigger_resource_refresh(), the schedule's function, which calls
                         #   InfrahubComponent.refresh_resources()

backend/tests/unit/telemetry/
├── test_resources.py    # NEW: cgroup v2/v1 parsing, path resolution, unlimited→null,
│                        #   quota and affinity caps, the machine's figures without a limit
├── test_tasks.py        # NEW: the per-container figures (parametrized test_component_data)
└── test_database.py     # NEW: the worker_limit setting parse

backend/tests/unit/serve/
└── test_processes.py    # NEW: the number of processes per container read from the environment

backend/tests/unit/services/
├── test_component.py    # NEW: component attribution; storing the reading and reading
│                        #   back only the given workers'; liveness written first;
│                        #   a read that keeps failing leaves a warning and keeps the
│                        #   last stored reading
└── test_scheduler.py    # extended: resource_refresh is registered for worker processes

backend/tests/component/telemetry/
├── test_resources.py    # NEW: end-to-end gather with synthesized worker heartbeats
└── test_cgroup_kernels.py  # NEW: the reader against real kernel control groups
```

Outside `backend/`, the feature also touches:

- `pyproject.toml`/`uv.lock`: the `psutil` promotion.
- `docs/`: the FAQ entry.
- One Towncrier fragment, `changelog/+resource-telemetry.added.md`, covering the whole feature.

**Structure Decision**: Single backend project. The behaviour lives in `backend/infrahub/telemetry/` (a new `resources.py` reader, three new Pydantic models — `TelemetryComponentData` and `TelemetryContainerData` in `models.py`, `WorkerResourceReading` in `resources.py` — and gather wiring), a new `backend/infrahub/serve/processes.py` (`processes_per_container()`), and five existing modules: `backend/infrahub/services/component.py` (resources read and stored by `refresh_resources()`, read back for the active workers by the new `read_worker_resources()` scan; `WorkerInfo` gains a `component` attribute), `backend/infrahub/services/scheduler.py` (registers the resource schedule), `backend/infrahub/tasks/recurring.py` (the schedule's function), `backend/infrahub/serve/worker.py` (the gunicorn worker class puts gunicorn's worker count in the environment) and `backend/infrahub/workers/dependencies.py` (`build_component()` builds the reader with that count). Alongside it the feature promotes `psutil` in `pyproject.toml`, and updates the docs and changelog. No new top-level package, no cross-cutting refactor. It follows the backend-component-design rule only in part. `build_component()` reads the number of processes per container, builds the reader with it and passes it to `InfrahubComponent.new()`, which requires it, so the production path takes the reader as a required collaborator. The attribute itself keeps a defaulted `Factory(ProcessResources)` with a count of 1, because tests construct `InfrahubComponent` directly at many call sites: the rule's transitional compromise for existing code, not its target shape. The gatherer itself follows the DI/builder pattern established in the parent telemetry work.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Processes per container (the gunicorn worker class puts gunicorn's worker count in each API server process's environment; each reading carries it, and the payload reports it next to one container's undivided figures) | `api_server` runs multiple gunicorn processes in **one** container sharing **one** cgroup, while `git_agent` runs **one** process per container (`replicas: N`). `per_container × active ÷ processes_per_container` must give the component's total for both. | Reporting each container's figures without the count overstates the server by its process count once multiplied by `active` (e.g. 4 cores × 4 processes = 16). Dividing one container's figures among the processes that reported from it (research D16, superseded by D19) needed a container name built from the hostname and the PID namespace, a rule for failed reads and decimal CPU shares, and it hid each container's size. Summing over distinct hosts (research D8/D9, superseded by D16) needed per-host deduplication, two null rules, and an undercount whenever a host stayed silent. Taking the count from gunicorn's own setting is the minimal rule correct for both components. |
