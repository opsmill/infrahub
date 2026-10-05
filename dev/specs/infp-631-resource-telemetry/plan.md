# Implementation Plan: Licensing Resource-Allocation Telemetry

**Branch**: `resource-telemetry-infp-631` | **Date**: 2026-07-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/infp-631-resource-telemetry/spec.md`

## Summary

Extend the daily telemetry payload to report logical CPU cores (available + assigned) and memory (total + available) for the **database** (in place, on its existing `system_info`), the **task workers** (a new `task_workers` section), and the **API server** (a new `server` section), each new section with its own process count and a `per_worker` object, all using the existing `processor_*`/`memory_*` field names, so a deployment can be audited against its contracted tier from a single snapshot — including offline/air-gapped deployments.

Technical approach: reuse the existing telemetry gatherer, the `safe_metric` degradation boundary, the existing database JMX query, and the existing worker-heartbeat cache channel. The database row is derived from the JMX system-info the payload already collects. The server and worker figures are self-reported by each process into its heartbeat, and the gatherer reports one worker's share of its container for each of the two components. CPU/RAM figures come from `psutil` (promoted from a dev-only to a production runtime dependency — research D1) plus stdlib `/sys/fs/cgroup` reads for the enforced allocation limit. Because several `api_server` processes share one container/cgroup, the gatherer divides that container's figures by the number of processes that reported from it, so the share times the block's `active` count is the component's total (research D16). No new third-party package — but `psutil` moves from a dev-only pin to a production runtime dependency, which is an Ask-First gate in its own right (Constraints, Governance). No database schema change, no branch-scoped data.

**Worker counts.** `workers` is unchanged: `total`/`active` count every worker process. Each new block describes one component, counts and resources alike: `server` the API server, `task_workers` the git_agent processes. `server.total + task_workers.total` equals `workers.total`, except for a process known only by its generic presence key, usually one that stopped about two hours earlier, which only `workers` counts (research D17).

## Technical Context

**Language/Version**: Python 3.14 (backend)

**Primary Dependencies**: Pydantic 2.12 (typed payload models), Prefect 3.8.6 (gather flow/tasks), `psutil==6.1.0` (promoted from dev-only to a production runtime dependency — host logical CPU count, CPU affinity, memory), stdlib `socket`, `pathlib`, `math`, `logging`, and `dataclasses` + `/sys/fs/cgroup` and `/proc/self/cgroup` reads (enforced cgroup limit), Neo4j driver (existing JMX for the database row), Redis-backed `InfrahubCache` (existing heartbeat channel)

**Storage**: telemetry snapshot persisted via the existing snapshot repository; per-process resource readings transit through the cache heartbeat (TTL-bound), never persisted separately

**Testing**: pytest — unit (`backend/tests/unit/telemetry/`: cgroup parsing and path resolution, the per-worker share, the database setting parse; `backend/tests/unit/services/`: component attribution, the heartbeat's resource write, the schedule registration) + component (`backend/tests/component/telemetry/`: end-to-end gather against the testcontainers Neo4j with synthesized worker heartbeats, and the reader against real kernel control groups in containers)

**Target Platform**: Linux server (containers). cgroup reads are Linux-only. Without them (e.g. developer macOS), memory falls back to psutil's whole-host figures and `processor_available` to the host's count, capped by CPU affinity where it is readable; only `processor_assigned` is `null`, which is acceptable because `assigned` is only meaningful where a limit is enforced

**Project Type**: Single backend service; changes localized to the telemetry module and the component/heartbeat service

**Performance Goals**: Cold daily path; cost is negligible. The existing `workers:*` key scan, plus a separate `workers:resources:*` key scan and a multi-get of those values (one per live process), plus a handful of local file reads per process every 10 seconds

**Constraints**: MUST NOT block or fail the snapshot; each source this feature reads degrades independently to `null` (the existing database JMX gather is not guarded and still aborts the snapshot on failure); payload changes are additive only and no existing field changes meaning (research D17), with the version bump gated on receiving-service confirmation rather than made this phase; **no new third-party package**, though `psutil` is promoted from a dev-only pin to a production runtime dependency (research D1, an Ask-First gate); cgroup v2 primary with a v1 fallback, psutil's whole-host figures where neither is present (only `processor_assigned` is then `null`)

**Scale/Scope**: A few components and a small number of workers per deployment (default `replicas: 2`). Trivial scale

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Notes |
|-----------|---------|-------|
| I. Schema-Driven Integrity | ✅ Pass | The telemetry payload is not Infrahub graph data; no node/attribute/relationship or generated-schema change. |
| II. Branch-Safe by Default | ✅ Pass | Resource figures are deployment-level, not branch-scoped. Where the gather touches the graph (existing node counts) it already runs on the default branch; no cross-branch writes, no merge semantics. |
| III. Type Safety & Explicit Contracts | ✅ Pass | New/extended resource fields are typed Pydantic (`int \| None`, and `float \| None` for the per-worker processor share), never untyped dicts — extending `TelemetryDatabaseSystemInfoData` and adding `TelemetryComponentData` and `TelemetryPerWorkerData`. |
| IV. Test Discipline | ✅ Pass | Unit tests for cgroup parsing and the per-worker share; component test for end-to-end gather incl. the FR-005 partial-report and FR-003 unlimited→`null` edges. Test files mirror source, except `test_cgroup_kernels.py`, which has no same-named source and runs `resources.py` against real kernel control groups. |
| V. Query Performance & Efficiency | ✅ Pass | Reuses the existing JMX call and the existing `workers:*` cache scan; adds one new lightweight `SHOW SETTINGS` read for `processor_assigned` and one `workers:resources:*` key scan with a single multi-get. No N+1, no large result sets. |
| VI. Security & Input Boundaries | ✅ Pass | Reads only local, trusted `/sys/fs/cgroup` and `/proc/self/cgroup` files — no user input, no injection surface. Cores/RAM are not PII; transmission remains gated by the existing opt-out. |
| VII. Simplicity & Maintainability | ✅ Pass (1 justified complexity) | Reuses `safe_metric`, the heartbeat channel, and the JMX path; no new third-party package, though `psutil` is promoted to a production runtime dependency (Governance gate below). Dividing a container's figures between the processes that share it is the one non-obvious element — justified in Complexity Tracking. |

**Governance Ask-First gates**: New dependency — **none added**, but `psutil` is promoted from dev-only to a production runtime dependency (Ask-First confirmed, research D1). DB schema/migration — **none**. Auth — **none**. GraphQL/REST schema — **none** (telemetry payload is an internal contract with the receiving service, coordinated cross-team, not an Infrahub API). CI/CD — **none**.

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-631-resource-telemetry/
├── spec.md              # the input to this plan
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions + rationale
├── data-model.md        # Phase 1 output — Pydantic models + per-worker share rules
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
├── models.py            # extend TelemetryDatabaseSystemInfoData (processor_assigned);
│                        #   add TelemetryPerWorkerData, TelemetryComponentData, and the
│                        #   server and task_workers fields on TelemetryData
├── resources.py         # NEW: read logical cores, CPU affinity + memory (psutil) and the
│                        #   cgroup limit (stdlib); WorkerResourceReading (the per-process
│                        #   reading the cache carries) and ProcessResources (the reader)
├── database.py          # add processor_assigned to system_info via
│                        #   server.cypher.parallel.worker_limit (SHOW SETTINGS) — confirmed
│                        #   with the backend owner as the intended knob (research D3), and
│                        #   since adopted by the infrahub-enterprise chart presets as the
│                        #   Neo4j CPU budget (infrahub-helm#93); it caps the parallel
│                        #   runtime's workers, not Neo4j's total CPU use;
│                        #   existing
│                        #   processor_available/memory_* already cover DB cores + RAM
└── tasks.py             # gather: counts each component's processes into the new server and
                         #   task_workers blocks and fills their per_worker through
                         #   _per_worker_share() from read_worker_resources()

backend/infrahub/services/
├── component.py         # InfrahubComponent.refresh_resources() reads this process's
│                        #   resources and publishes them to LATEST_RESOURCE_READING; the
│                        #   liveness heartbeat writes that reading beside its active key;
│                        #   the gatherer reads them back through the new
│                        #   read_worker_resources() scan; WorkerInfo gains a component
│                        #   attribute, set by add_key from the process's own keys
└── scheduler.py         # registers the 10-second resource_refresh schedule on the main loop

backend/infrahub/tasks/
└── recurring.py         # trigger_resource_refresh(), the schedule's function, which calls
                         #   InfrahubComponent.refresh_resources()

backend/tests/unit/telemetry/
├── test_resources.py    # NEW: cgroup v2/v1 parsing, path resolution, unlimited→null,
│                        #   quota and affinity caps, host detection
├── test_tasks.py        # NEW: the per-worker share (parametrized test_per_worker_share)
└── test_database.py     # NEW: the worker_limit setting parse

backend/tests/unit/services/
├── test_component.py    # NEW: component attribution; the heartbeat's resource write
└── test_scheduler.py    # extended: resource_refresh is registered for worker processes

backend/tests/component/telemetry/
├── test_resources.py    # NEW: end-to-end gather with synthesized worker heartbeats;
│                        #   + regression: the new resources heartbeat key must NOT change
│                        #     the existing workers.total / workers.active counts
└── test_cgroup_kernels.py  # NEW: the reader against real kernel control groups
```

Outside `backend/`, the feature also touches:

- `pyproject.toml`/`uv.lock`: the `psutil` promotion.
- `docs/`: the FAQ entry.
- One Towncrier fragment, `changelog/+resource-telemetry.added.md`, covering the whole feature.

**Structure Decision**: Single backend project. The behaviour lives in `backend/infrahub/telemetry/` (a new `resources.py` reader, three new Pydantic models — `TelemetryComponentData` and `TelemetryPerWorkerData` in `models.py`, `WorkerResourceReading` in `resources.py` — and gather wiring) and three existing modules: `backend/infrahub/services/component.py` (resources read by `refresh_resources()` and written by the liveness heartbeat, read back by the new `read_worker_resources()` scan; `WorkerInfo` gains a `component` attribute), `backend/infrahub/services/scheduler.py` (registers the resource schedule), and `backend/infrahub/tasks/recurring.py` (the schedule's function). Alongside it the feature promotes `psutil` in `pyproject.toml`, and updates the docs and changelog. No new top-level package, no cross-cutting refactor. It follows the backend-component-design rule only in part. The reader is a defaulted `Factory(ProcessResources)` attribute on the existing `InfrahubComponent`, which is constructed at many call sites: the rule's transitional compromise for existing code, not its target shape of a required collaborator. The reading reaches the heartbeat thread through the module-level `LATEST_RESOURCE_READING`, built at import inside `component.py`, which `refresh_resources()` publishes to directly and `refresh_worker_heartbeat()` takes as a defaulted parameter. The rule asks for a process-global built on first use in its own registry module, so this deviates from it. The gatherer itself follows the DI/builder pattern established in the parent telemetry work.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Per-worker share (each process reports a host identifier; the gatherer divides one container's figures by the number of processes that reported from it) | `api_server` runs multiple gunicorn processes in **one** container sharing **one** cgroup, while `git_agent` runs **one** process per container (`replicas: N`). `per_worker × active` must give the component's total for both. | Reporting each worker's raw container figures overstates the server by its process count once multiplied by `active` (e.g. 4 cores × 4 processes = 16). Summing over distinct hosts (research D8/D9, superseded by D16) needed per-host deduplication, two null rules, and an undercount whenever a host stayed silent. Counting the processes that share a host is the minimal rule correct for both components. |
