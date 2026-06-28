# Implementation Plan: Phase 1 Telemetry Collection

**Branch**: `telemetry-collection-infp-589` | **Date**: 2026-06-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/telemetry-collection-infp-589/spec.md`

## Summary

Extend Infrahub's daily anonymous telemetry payload with additive, backwards-compatible
metrics: account adoption (`accounts.active`, `accounts.groups`), open-branch count
(`branches.active`), a branch/temporal-correct managed-node count
(`database.node_count.corenode`), and a new calendar-day-windowed `activity_24h` object
(`logins`, `unique_logins`, `checks_started/passed/failed`, `artifacts_created/updated`,
`branches_created/merged/deleted`, `webhooks_fired_success`, `webhooks_fired_failure`). The
check/artifact/branch-lifecycle metrics are derived from events that already flow today,
harvested cheaply on the same windowed path.

Technical approach: add the new fields to the existing Pydantic payload models; add gather
functions that use the standard branch-safe `NodeManager.count` path for node-based metrics
and a NEW windowed Prefect query path for event/flow-run metrics (the existing unwindowed
`gather_prefect_events` output is left untouched). Bump `TELEMETRY_VERSION`. Introduce a
per-metric graceful-degradation wrapper so a single failing source yields `null` for that
field while the rest of the payload is still gathered, stored, and sent; a source that
succeeds with nothing to count yields `0`.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: Pydantic 2.12 (payload models), Prefect (flow orchestration +
events/flow-run API), Neo4j driver 6.2 (via `InfrahubDatabase` / `NodeManager`)

**Storage**: Neo4j (node/branch counts via `NodeManager.count`); Prefect event & flow-run
store (24h activity metrics — the graph DB is not an event log, per ADR 0002)

**Testing**: pytest 9.0 — component tests (TestContainers) for DB-backed counts and the
gather flow; unit tests for windowing/degradation logic where no DB is required

**Target Platform**: Linux server (Infrahub backend task-worker)

**Project Type**: Web service backend (single backend package; no frontend work this phase)

**Performance Goals**: Daily batch job; each metric is a single aggregate query
(`NodeManager.count` / Prefect count-by). No per-node iteration, no N+1.

**Constraints**: Additive only — no existing field changes meaning/type/name. Per-metric
isolation: one failing source must not drop the payload. Event metrics must reflect exactly a
24h window anchored to a deterministic calendar boundary (previous full UTC day), not to
job-execution time, so daily snapshots tile with no overlap/gap despite the jittered cron.

**Scale/Scope**: ~16 new payload fields across 2 new sub-models + 2 extended sub-models;
~3 new gather functions; 1 windowed-event counter (reused for logins + 8 check/artifact/branch
metrics); 1 degradation helper; 1 constant bump. Producer-only.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Schema-Driven Integrity | No schema/generated-file edits; reads through schema-aware `NodeManager`. | ✅ Pass — read-only, no schema changes. |
| II. Branch-Safe by Default | Node/account counts run on the default branch through the standard `NodeManager.count` path (branch + temporal filters applied). Raw `count_nodes(label=...)` is explicitly avoided for `corenode`. | ✅ Pass. |
| III. Type Safety & Explicit Contracts | New Pydantic models with explicit `int \| None` fields; gather functions fully type-hinted; `str \| None` style. | ✅ Pass. |
| IV. Test Discipline | Component tests for SC-001/002/003; tests mirror source under `tests/component/telemetry/` and `tests/unit/telemetry/`; adapter/fixture patterns, no `unittest.mock`. | ✅ Pass. |
| V. Query Performance & Efficiency | Each metric = one aggregate query; no N+1; windowed Prefect queries bounded to 24h. | ✅ Pass. |
| VI. Security & Input Boundaries | No new user input; telemetry is anonymous and opt-out-aware; no secrets; existing endpoint/auth untouched. | ✅ Pass. |
| VII. Simplicity & Maintainability | No new entities, no new dependencies; one small degradation helper justified by ≥2 callers; follows existing `telemetry/*.py` gather-module pattern. | ✅ Pass. |

**Initial gate: PASS.** No violations; Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/telemetry-collection-infp-589/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── telemetry-payload.md   # Payload contract (new/changed fields + degradation rules)
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
backend/infrahub/telemetry/
├── constants.py         # BUMP TELEMETRY_VERSION
├── models.py            # ADD TelemetryAccountData, TelemetryActivity24hData;
│                        #   EXTEND TelemetryBranchData (+active), node_count value type;
│                        #   ADD accounts + activity_24h to TelemetryData
├── tasks.py             # ADD gather_account_information, branches.active wiring,
│                        #   degradation helper; wire accounts/activity_24h into
│                        #   gather_anonymous_telemetry_data
├── database.py          # ADD node_count["corenode"] via NodeManager.count (degradable)
└── task_manager.py      # ADD windowed event path + gather_activity_24h
                         #   (leave gather_prefect_events untouched)

backend/tests/
├── component/telemetry/
│   ├── test_datatabase.py     # EXTEND: corenode count correctness (SC-003)
│   ├── test_task_manager.py   # EXTEND: 24h windowing (SC-002), unique_logins, webhooks
│   └── test_tasks.py          # NEW: gather flow presence + degradation (SC-001)
└── unit/telemetry/
    └── test_degradation.py    # NEW: null-on-failure vs 0-on-empty helper logic
```

**Structure Decision**: Single backend package, extending the existing `telemetry/` module.
Each metric source keeps its home: DB counts in `database.py`, Prefect/event metrics in
`task_manager.py`, account counts + orchestration + degradation in `tasks.py`. This mirrors
the current separation and adds no new top-level structure (Constitution VII).

## Complexity Tracking

> No constitution violations. Section intentionally empty.

## Phase Notes

- **Governance gate (GR-001)**: Before merge/release, confirm with the cloud-processor and
  data-mart owners that the `payload_format` bump + new fields are tolerated (consumer
  ignores unknown fields). This is a release checklist item carried into `tasks.md`, not a
  code dependency — every change is additive.
- **Parked**: `database.node_count.user` (IFC-2825) is out of scope; the contract doc notes
  the three-way distinction (`total` raw / `corenode` managed / `user` future) without
  implementing `user`.
