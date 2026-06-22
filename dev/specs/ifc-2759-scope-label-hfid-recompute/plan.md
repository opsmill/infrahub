# Implementation Plan: Scope display label and HFID recompute on schema updates

**Branch**: `scope-label-hfid-recompute-ifc-2759` | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/ifc-2759-scope-label-hfid-recompute/spec.md`

## Summary

On a schema update, display label and HFID backfill re-sweep every node of every kind whose definition differs from the default branch, with no dependency check. The computed-attribute work (PR #9467, now on `develop`) already solved this: it carries the changed-element set on `SchemaUpdatedEvent`, derives each computed attribute's dependency set, and intersects the two to recompute only impacted attributes. Display labels and HFIDs were left out and still sweep on any schema change.

This feature brings display labels and HFIDs to parity. Technical approach:

1. **Extract the scoping core to a shared module.** Move `DependencySet`, `ChangedElementSet`, `RecomputeScoper`, `RecomputeScopingReport`, `SkippedAttribute`, and a generalized candidate/deriver protocol out of `backend/infrahub/computed_attribute/scoping.py` into `backend/infrahub/core/schema/recompute_scoping.py`. `computed_attribute`, `display_labels`, and `hfid` all import from `core`. This is a behavior-preserving refactor; the existing computed-attribute unit + component scoping tests are the regression guard and must pass unchanged.
2. **Add a display-label deriver and an HFID deriver.** Each maps its existing dependency metadata (`TemplateLabel` / `HFIDDefinition`: `attributes`, `relationships`, `relationship_fields`, inverse relationship triggers) into a `DependencySet`. The set includes the owner kind's own definition property (`display_labels` / `human_friendly_id`) so an edit to the definition itself recomputes the kind. When a read resolves to a derived value (a peer's `display_label`/`hfid`, or a computed attribute on the read kind), the deriver sets `depends_on_everything=True` (conservative; never skips a needed recompute).
3. **Thread `changed_elements` into the setup flows.** Add the `changed_elements` Jinja parameter to `TRIGGER_DISPLAY_LABELS_ALL_SCHEMA` and `TRIGGER_HFID_ALL_SCHEMA` (mirroring `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA`); add `changed_elements: ChangedElementsPayload | None = None` to `display_labels_setup_jinja2` and `hfid_setup`; resolve it via the shared helper.
4. **Scope before the existing sweep.** In each setup flow, build candidates for the branch, call `RecomputeScoper.scope(...)`, and proceed with the existing per-kind hash check + node sweep only for selected kinds. When `changed_elements is None`, fall back to today's full behavior.
5. **Observability.** Log, at info level, the scoping decision: selected count, total candidate count, and whether the run was a full-recompute fallback — matching the computed-attribute log line.

Recompute remains asynchronous and branch-aware; the per-node sweep within a selected kind is unchanged (per-node short-circuiting is IFC-2762, out of scope).

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: FastAPI, Prefect (workflows/triggers), Neo4j 2026.05 (driver 6.2), Pydantic 2.12
**Storage**: Neo4j (graph) — no new persisted data model; dependency sets are derived in-memory from the active `SchemaBranch`
**Testing**: pytest 9.0 — unit (`backend/tests/unit/display_labels/`, `backend/tests/unit/hfid/`, `backend/tests/unit/computed_attribute/`), component (`backend/tests/component/display_labels/`, `backend/tests/component/hfid/`), functional (`backend/tests/functional/display_labels/`, `backend/tests/functional/hfid/`), integration_docker
**Target Platform**: Linux server (backend task workers / Prefect)
**Project Type**: Web service backend (single backend project; no frontend change)
**Observability**: Recompute task logs — info-level summary distinguishing precise scoping from full-recompute fallback (selected count / total candidates / `fallback_full_recompute`). No new metric/event channel.
**Performance Goals**: Display-label/HFID recompute after a scoped schema update scales with the number of impacted kinds, not the total number of kinds defining a display label or HFID (SC-002). A change touching unrelated elements produces zero recompute for unaffected kinds (SC-001).
**Constraints**: Asynchronous / eventually consistent. Correctness over optimization — never skip a needed recompute; mark imprecise and recompute when a dependency cannot be determined (FR-005). Branch isolation preserved. Behavior-preserving on the `changed_elements is None` fallback path (SC-005).
**Scale/Scope**: Branches may hold thousands of nodes across many kinds; the defect is most visible on large datasets. Change is confined to a new shared scoping module under `core/schema/`, the `display_labels` and `hfid` packages, and their triggers — plus a behavior-preserving move of the existing scoping core out of `computed_attribute`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Gates derived from `.specify/memory/constitution.md` (v1.0.0). Frontend principles are **N/A** (backend-only feature, no UI surface).

| Principle | Gate | Status |
|-----------|------|--------|
| I. Schema-Driven Integrity | Dependency sets derived read-only from the active `SchemaBranch`; no manual edits to generated files; derived values still flow through the schema layer. | PASS — read-only schema use; no generated-file edits. |
| II. Branch-Safe by Default | Scoping must remain branch-aware; the no-change-set fallback (merge/rebase/git paths) must preserve today's behavior; no cross-branch broadening. | PASS *with required coverage* — fallback path preserved (FR-006); a test MUST assert the `changed_elements is None` path is unchanged and that scoping does not broaden across branches. Merge/rebase emitting a change set is explicitly out of scope (IFC-2758/IFC-2761). |
| III. Type Safety & Explicit Contracts | Type hints on all new code; frozen dataclasses for internal data (candidate, dependency set, report); `str \| None` style; no untyped dicts for structured data. | PASS — contracts defined as frozen dataclasses (see `contracts/`). |
| IV. Test Discipline | Display-label/HFID + triggered-action work requires component coverage; integration_docker is required for triggered-action/computed paths. Reuse existing fixtures; tests mirror source. | PASS — unit (derivers + generic scoper), component (setup-flow scoping for both subsystems mirroring `test_scoped_recompute_jinja2.py`), and an integration_docker assertion that a scoped schema change refreshes only affected kinds. Existing full-sweep optimization tests retained as the fallback guard. |
| V. Query Performance & Efficiency | The feature reduces submitted jobs/queries; no new N+1; derivation is in-memory over already-loaded schema. | PASS — fewer recompute submissions; deriver work is in-memory lookups. |
| VI. Security & Input Boundaries | No new external input surface; the schema and template/path text consulted is operator-authored and already in the system. | PASS — no new injection surface; no auth change. |
| VII. Simplicity & Maintainability | Reuse the existing scoper rather than building a parallel one (the extraction is justified because a third + fourth caller now exist — clears the "two callers" bar). Follow DI / single-entry-point component design. Keep the per-node sweep untouched. | PASS — extraction now serves ≥2 callers; new derivers are the minimal additions; no premature abstraction. |

No violations. **Required-coverage note (Principle II):** the `changed_elements is None` fallback-equivalence test and a no-cross-branch-broadening assertion are mandatory for completion; `tasks.md` must carry them. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2759-scope-label-hfid-recompute/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── recompute-scoping.md
├── checklists/
│   └── requirements.md  # /speckit-specify output
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/schema/
│   ├── recompute_scoping.py            # NEW — shared scoping core (moved from computed_attribute/scoping.py)
│   ├── schema_branch_display.py        # existing — TemplateLabel / DisplayLabels dependency metadata (read)
│   ├── schema_branch_hfid.py           # existing — HFIDDefinition / HFIDs dependency metadata (read)
│   └── schema_branch_computed/
│       └── python_transform.py         # existing — IMPRECISE_READ_FIELDS (may relocate to core)
├── computed_attribute/
│   ├── scoping.py                      # CHANGED — keeps Jinja2/Python derivers; imports core for moved types
│   ├── tasks.py                        # unchanged behavior (imports follow the move)
│   └── triggers.py                     # unchanged
├── display_labels/
│   ├── scoping.py                      # NEW — DisplayLabelDependencyDeriver + candidate builder
│   ├── tasks.py                        # CHANGED — display_labels_setup_jinja2 gains changed_elements + scoper call
│   └── triggers.py                     # CHANGED — TRIGGER_DISPLAY_LABELS_ALL_SCHEMA threads changed_elements
└── hfid/
    ├── scoping.py                      # NEW — HFIDDependencyDeriver + candidate builder
    ├── tasks.py                        # CHANGED — hfid_setup gains changed_elements + scoper call
    └── triggers.py                     # CHANGED — TRIGGER_HFID_ALL_SCHEMA threads changed_elements

backend/tests/
├── unit/
│   ├── computed_attribute/test_scoping.py        # existing — regression guard for the move
│   ├── display_labels/test_scoping.py            # NEW — DisplayLabelDependencyDeriver + scoper cases
│   └── hfid/test_scoping.py                       # NEW — HFIDDependencyDeriver + scoper cases
├── component/
│   ├── computed_attribute/test_scoped_recompute_*.py   # existing — template to mirror
│   ├── display_labels/test_scoped_recompute.py   # NEW — setup-flow scoping via WorkflowRecorder
│   └── hfid/test_scoped_recompute.py             # NEW — setup-flow scoping via WorkflowRecorder
├── functional/
│   ├── display_labels/test_display_label_task_optimization.py  # existing — fallback guard
│   └── hfid/test_hfid_task_optimization.py                     # existing — fallback guard
└── integration_docker/                            # scoped-refresh assertion (affected kinds only)
```

**Structure Decision**: Single backend project. The scoping core moves to `core/schema/recompute_scoping.py` so all three feature packages depend inward on `core` rather than on each other. Each feature package gets its own `scoping.py` holding only its deriver + candidate construction, mirroring how `computed_attribute` is organized after the move.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
