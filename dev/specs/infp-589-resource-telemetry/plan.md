# Implementation Plan: Licensing Resource-Allocation Telemetry

**Branch**: `resource-telemetry-infp-589` | **Date**: 2026-07-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/infp-589-resource-telemetry/spec.md`

## Summary

Extend the daily telemetry payload **in place** to report logical CPU cores (available + assigned) and memory (total + available) for the **database** (on its existing `system_info`), the **worker fleet** (on the existing `workers` section), and the **API server** (a new `server` section), all using the existing `processor_*`/`memory_*` field names, so a deployment can be audited against its contracted tier from a single snapshot — including offline/air-gapped deployments.

Technical approach: reuse the existing telemetry gatherer, the `safe_metric` degradation boundary, the existing database JMX query, and the existing worker-heartbeat cache channel. The database row is derived from the JMX system-info the payload already collects. The server and worker rows are self-reported by each process into its heartbeat and aggregated by the gatherer. CPU/RAM figures come from `psutil` (already a direct dependency) plus stdlib `/sys/fs/cgroup` reads for the enforced allocation limit. Because multiple `api_server` processes share one container/cgroup, the aggregation deduplicates by host before summing. No new dependency, no database schema change, no branch-scoped data.

## Technical Context

**Language/Version**: Python 3.14 (backend)

**Primary Dependencies**: Pydantic 2.12 (typed payload models), Prefect 3.7 (gather flow/tasks), `psutil==6.1.0` (already a direct dependency — host logical CPU count + memory), stdlib `os`/`socket` + `/sys/fs/cgroup` reads (enforced cgroup limit), Neo4j driver (existing JMX for the database row), Redis-backed `InfrahubCache` (existing heartbeat channel)

**Storage**: telemetry snapshot persisted via the existing snapshot repository; per-process resource readings transit through the cache heartbeat (TTL-bound), never persisted separately

**Testing**: pytest — unit (`backend/tests/unit/telemetry/`: cgroup parsing, host-dedup aggregation, null/undercount rules) + component (`backend/tests/component/telemetry/`: end-to-end gather against the testcontainers Neo4j with synthesized worker heartbeats)

**Target Platform**: Linux server (containers). cgroup reads are Linux-only and degrade to `null` on non-Linux (e.g. developer macOS), which is acceptable because `assigned` is only meaningful where a limit is enforced

**Project Type**: Single backend service; changes localized to the telemetry module and the component/heartbeat service

**Performance Goals**: Cold daily path; cost is negligible. Reads are O(active workers) cache keys (already scanned today) plus a handful of local file reads per process at heartbeat time

**Constraints**: MUST NOT block or fail the snapshot; each metric degrades independently to `null`; payload changes are additive with a version bump; **no new third-party dependency**; cgroup v2 primary with a v1 fallback, `null` where neither is present

**Scale/Scope**: A few components and a small number of workers per deployment (default `replicas: 2`). Trivial scale

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Notes |
|-----------|---------|-------|
| I. Schema-Driven Integrity | ✅ Pass | The telemetry payload is not Infrahub graph data; no node/attribute/relationship or generated-schema change. |
| II. Branch-Safe by Default | ✅ Pass | Resource figures are deployment-level, not branch-scoped. Where the gather touches the graph (existing node counts) it already runs on the default branch; no cross-branch writes, no merge semantics. |
| III. Type Safety & Explicit Contracts | ✅ Pass | New/extended resource fields are typed Pydantic (`int \| None`), never untyped dicts — extending `TelemetryDatabaseSystemInfoData`/`TelemetryWorkerData` and adding `TelemetryServerData`. |
| IV. Test Discipline | ✅ Pass | Unit tests for cgroup parsing + aggregation; component test for end-to-end gather incl. the FR-005 partial-report and FR-003 unlimited→`null` edges. Test files mirror source. |
| V. Query Performance & Efficiency | ✅ Pass | No new DB query — reuses the existing JMX call and the existing `workers:*` cache scan. No N+1, no large result sets. |
| VI. Security & Input Boundaries | ✅ Pass | Reads only local, trusted `/sys/fs/cgroup` files — no user input, no injection surface. Cores/RAM are not PII; transmission remains gated by the existing opt-out. |
| VII. Simplicity & Maintainability | ✅ Pass (1 justified complexity) | Reuses `safe_metric`, the heartbeat channel, and the JMX path; zero new deps. Host-dedup aggregation is the one non-obvious element — justified in Complexity Tracking. |

**Governance Ask-First gates**: New dependency — **none** (psutil already direct; cgroup reads are stdlib). DB schema/migration — **none**. Auth — **none**. GraphQL/REST schema — **none** (telemetry payload is an internal contract with the receiving service, coordinated cross-team, not an Infrahub API). CI/CD — **none**.

## Project Structure

### Documentation (this feature)

```text
specs/infp-589-resource-telemetry/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions + rationale
├── data-model.md        # Phase 1 output — Pydantic models + aggregation rules
├── quickstart.md        # Phase 1 output — validation guide
├── contracts/
│   └── telemetry-resources.md   # payload contract for the receiving service
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/infrahub/telemetry/
├── models.py            # extend TelemetryDatabaseSystemInfoData (processor_assigned) +
│                        #   TelemetryWorkerData (processor_*/memory_* fields); add
│                        #   TelemetryServerData + server field on TelemetryData
├── constants.py         # bump TELEMETRY_VERSION (payload_format)
├── resources.py         # NEW: read logical cores + memory (psutil) and the cgroup limit
│                        #   (stdlib); host identifier; per-process ComponentResources
├── database.py          # add processor_assigned to system_info via
│                        #   server.cypher.parallel.worker_limit (SHOW SETTINGS); existing
│                        #   processor_available/memory_* already cover DB cores + RAM
└── tasks.py             # gather: aggregate hosts → extended workers fields + new server block

backend/infrahub/services/
└── component.py         # heartbeat self-reports this process's resources;
                         # WorkerInfo captures component type + resource value + host

backend/tests/unit/telemetry/
├── test_resources.py    # NEW: cgroup v2/v1 parsing, unlimited→null, host detection
└── test_aggregation.py  # NEW: host-dedup sum, undercount, null-vs-zero rules

backend/tests/component/telemetry/
└── test_resources.py    # NEW: end-to-end gather with synthesized worker heartbeats;
                         #   + regression: the new resources heartbeat key must NOT change
                         #     the existing workers.total / workers.active counts
```

**Structure Decision**: Single backend project. All changes are confined to `backend/infrahub/telemetry/` (a new `resources.py` reader, three new Pydantic models, gather wiring, a version bump) and one existing collaborator, `backend/infrahub/services/component.py` (heartbeat self-report + `WorkerInfo` extension). No new top-level package, no cross-cutting refactor. This honors Principle VII and the backend-component-design rule (the reader is a small, injectable unit; the gatherer already follows the DI/builder pattern established in the parent telemetry work).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Host-dedup aggregation (each process reports a host identifier; the fleet figure sums over *distinct* hosts, not processes) | `api_server` runs multiple gunicorn processes in **one** container sharing **one** cgroup, while `git_agent` runs **one** process per container (`replicas: N`). A per-deployment core total must count each container's cores once. | Summing per process over-counts the server row by the gunicorn worker count (e.g. 4 cores × 8 workers = 32). Using only the elected primary api_server under-counts when the API is scaled to multiple containers. Dedup-by-host is the minimal rule correct for both components. |
