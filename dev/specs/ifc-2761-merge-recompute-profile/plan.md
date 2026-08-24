# Implementation Plan: Profile merge and rebase recompute cost at scale

**Branch**: `merge-recompute-profile-ifc-2761` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/ifc-2761-merge-recompute-profile/spec.md`

## Summary

Measure and attribute the recompute cost of a branch merge and rebase at increasing scale, so the coalescing redesign (separate, follow-up) targets the real bottleneck. The investigation confirmed the mechanism — `merge_branch`/`rebase_branch` emit one node event per changed node, each matched against the per-node computed-attribute, display-label, and HFID automations — but never measured its magnitude.

The plan uses **two complementary harness layers**, because counting and timing cannot be obtained from the same setup:

1. **Counting layer (deterministic, cheap).** Drive a real merge/rebase over a seeded branch with emitted node events captured by the **event-service recorder** (`MemoryInfrahubEvent`, injected via the dependency-provider scope) and `WorkflowRecorder` only neutralizing the merge's own orchestration workflows. It needs the graph database but not a running task worker, so it is fast and deterministic. It records node events by type (≈ the changed-node count by construction) plus a **derived expected-recompute** estimate computed in-process. Note: recompute is dispatched by Prefect automations from the emitted events, so it is not directly observed here — a `BusRecorder` would capture nothing (node events carry no bus messages). This layer is the cheap MVP; the authoritative recompute count is the timing layer's.

2. **Timing layer (realistic, heavy, gated).** Drive the same merge on the full distributed stack with a real task worker, then attribute wall-clock across cost centers: the merge critical path, schema migrations, the database commit, and the trailing asynchronous recompute (summed from Prefect flow-run timings). This answers "where does the time actually go" and separates the in-transaction cost from the degraded-instance window. It runs on demand (like the intensive benchmarks), not in normal CI.

Together the layers produce a findings report (committed under this spec) that names the dominant cost center and classifies growth. No recompute behavior changes — measurement only.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: pytest 9.0, testcontainers, Prefect (workflows/automations/flow-run API), Neo4j 2026.05, `infrahub-sdk`, pytest-benchmark + CodSpeed (microbench portion only)
**Storage**: Neo4j (graph) — synthetic data seeded per run; no new persisted model
**Testing**: counting layer under `backend/tests/component/merge_recompute/` (CI-collected by `test-component`; graph DB via testcontainers, recorders, no worker), with the shared dataset/metrics in `backend/tests/helpers/merge_recompute/`; timing layer under `backend/tests/integration_docker/` (full stack + real task worker); reuse existing adapters and fixtures. Note: `backend/tests/scale/` is a Locust load-test harness and is NOT collected by CI — the counting layer must not live there.
**Target Platform**: Linux server (backend task workers / Prefect)
**Project Type**: Web service backend (single backend project; no frontend change)
**Observability under test**: emitted node events (event-service recorder `MemoryInfrahubEvent`), the merge's own orchestration workflows (`WorkflowRecorder`, neutralized), a derived expected-recompute computed in-process, and — on the real stack — executed recompute counts and Prefect flow-run start/end timings queried through the task-manager flow-run API
**Performance Goals**: not a performance target; the deliverable is a cost attribution and growth classification accurate enough to choose the redesign
**Constraints**: measurement only (no behavior change, FR-010); reuse existing scale/benchmark/adapter infra rather than a parallel harness; absolute timings are stack-relative, so conclusions rest on growth shape and relative attribution, with a stated run-to-run tolerance
**Scale/Scope**: three or more scales (~10, ~100, ~1000+ changed nodes) across kinds carrying computed attributes, display labels, and HFIDs; covers both merge and rebase

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Gates from `.specify/memory/constitution.md` (v1.0.0). Frontend principles **N/A** (backend-only, no UI).

| Principle | Gate | Status |
|-----------|------|--------|
| I. Schema-Driven Integrity | Synthetic schema via fixtures; no generated-file edits; data flows through the normal node/schema layer. | PASS |
| II. Branch-Safe by Default | The harness exercises the real merge and rebase flows rather than bypassing them; measurement is branch-aware and mutates no cross-branch state beyond the merge under test. | PASS |
| III. Type Safety & Explicit Contracts | Type hints throughout; frozen dataclasses for the metrics records (profile run, cost-center timing, recompute counts). | PASS |
| IV. Test Discipline | This is test/measurement infrastructure. No mocks — adapter pattern (`WorkflowRecorder`, `MemoryInfrahubEvent`) plus the real stack for timing. The full-stack timing path is integration_docker, as required for triggered-action paths. Reuses existing fixtures. | PASS |
| V. Query Performance & Efficiency | The point is measurement; the harness adds no production query and no N+1. The counting layer avoids the worker entirely. | PASS |
| VI. Security & Input Boundaries | No new external input surface; synthetic operator-style data only. | PASS |
| VII. Simplicity & Maintainability | Reuses the scale stagers, benchmark fixtures, existing recorders, and the integration_docker wait/introspection patterns rather than a parallel framework. Two layers are justified because counting and timing genuinely cannot come from one setup. | PASS — justified; no parallel infra |

No violations. **Required-coverage note (Principle IV):** the timing layer must run against a real task worker (not the recorder) so wall-clock attribution is real; the counting layer must assert the no-behavior-change invariant (recompute output unchanged) holds. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2761-merge-recompute-profile/
├── plan.md              # This file
├── research.md          # Phase 0 — methodology decisions
├── data-model.md        # Phase 1 — metrics record shapes
├── quickstart.md        # Phase 1 — how to run + validation scenarios
├── contracts/
│   └── profile-harness.md   # harness entry points + report/metrics format
├── checklists/
│   └── requirements.md  # /speckit-specify output
├── findings.md          # PRODUCED BY RUNNING the profile (the deliverable report)
└── tasks.md             # /speckit-tasks output (next phase)
```

### Source Code (repository root)

```text
backend/tests/
├── helpers/
│   └── merge_recompute/                      # NEW — shared, importable by both layers
│       ├── dataset.py                        # Jinja2-only synthetic schema (computed attr + display label + HFID + relationship peer) + async node seeding against the db fixture
│       └── metrics.py                        # frozen dataclasses: ProfileRun, CostCenterTiming, RecomputeCounts, FindingsReport
├── component/
│   └── merge_recompute/
│       └── test_merge_recompute_counts.py    # counting layer (CI-collected): real data-only merge/rebase, MemoryInfrahubEvent recorder, assert counts per scale (no worker)
└── integration_docker/
    └── test_merge_recompute_timing.py        # NEW — timing layer: full stack + real worker; wall-clock; gated (labeled/timeout like intensive benchmarks)
```

**Structure Decision**: Counting and timing live in different trees because they need different stacks. The counting layer sits under `backend/tests/component/merge_recompute/` so it is collected by the `test-component` CI job — the regression-guard role requires this, and `backend/tests/scale/` is a Locust harness CI does not run. The timing layer sits under `backend/tests/integration_docker/` (full stack + real task worker) and runs on demand. Shared dataset seeding and metric dataclasses live in `backend/tests/helpers/merge_recompute/`, imported by both layers. The findings report is written to the spec directory as the deliverable.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
