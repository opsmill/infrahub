# Implementation Plan: Coalesce merge and rebase recompute fan-out

**Branch**: `coalesce-merge-recompute-ifc-2761` | **Date**: 2026-06-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/ifc-2761-coalesce-merge-recompute/spec.md`

## Summary

Replace the per-node recompute fan-out on the merge and rebase path with a single coalesced pass. Today neither merge nor rebase recomputes anything itself: after the graph merge, the post-merge dispatcher (`core/merge/post_merge.py`) for merge, and the rebase flow inline (`core/branch/tasks.py`) for rebase, walk the diff changelog and send one node event per changed node. Prefect matches each event against every recompute automation; each matching automation starts a flow that runs its own reader query and one update per reader. Nothing batches or dedups across nodes or events. The profile (first task on IFC-2761) and the follow-up code analysis (IFC-2761 comments) confirm: the merge call is fixed overhead, and the trailing cross-node recompute is the dominant growing cost (linear, ~11 min at 1000 changed nodes).

The redesign computes, once, from the merge diff the deduplicated set of derived values whose inputs changed (Jinja2 computed attributes, display labels, human-friendly ids), and submits a single batched recompute over only the affected node ids, on the correct branch for the operation. It reuses the existing computed-attribute deriver and builds the display-label/HFID derivation here (no shared one exists), so the merge-time selection cannot drift from the live per-node path. Final derived values are unchanged.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: Prefect (workflows + event automations), Neo4j (driver 6.2), the recompute components (`computed_attribute`, `display_labels`, `hfid`), the computed-attribute scoping/deriver in `backend/infrahub/computed_attribute/scoping.py` (PR #9467), and the schema-branch facades that already record display-label/HFID dependency metadata
**Storage**: Neo4j; no new persisted model (the coalesced target set is in-memory)
**Testing**: component tests for the target-selection logic (schema fixtures, graph DB, no worker); integration_docker for end-to-end correctness on the full stack with a real worker (required for triggered-action paths, Constitution IV); the profiling harness from the first task for before/after performance
**Target Platform**: Linux backend (task workers / Prefect)
**Project Type**: Web service backend (no frontend change)
**Performance Goals**: recompute work after a merge proportional to the number of affected derived values, not the changed-node count times automations; materially shorter trailing recompute window at scale (profile baseline ~11 min at 1000 changed nodes)
**Constraints**: behavior-preserving (FR-010); no missed transitive dependency (FR-002, correctness gate); no small-graph regression (FR-009); reuse the computed deriver and build the display/HFID deriver to the same pattern (FR-007); preserve the per-operation branch (merge→destination, rebase→user, FR-014); target resolution must batch and dedup, not become an N+1 over changed nodes (Constitution V)
**Scale/Scope**: up to ~1000+ changed nodes per merge; both merge and rebase; three families; Python-transform computed attributes deferred

**Branch-base note**: this spec branch is based on the profile branch (older code). On current develop the merge emission lives in `core/merge/post_merge.py` and the Jinja2 full-branch loop is unchunked; the branch must be rebased onto current develop before implementation so the integration points are real.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Gates from `.specify/memory/constitution.md` (v1.0.0). Frontend principles **N/A** (backend-only).

| Principle | Gate | Status |
|-----------|------|--------|
| I. Schema-Driven Integrity | Target selection derives from the schema's dependency metadata; no schema bypass; no generated-file edits. | PASS |
| II. Branch-Safe by Default | Operates on the merge diff and recomputes on the correct branch per operation (merge→destination, rebase→user); keeps branch/temporal filters. | PASS — branch difference is an explicit requirement (FR-014) |
| III. Type Safety & Explicit Contracts | Frozen dataclasses for the change set, affected targets, and coalesced request; full type hints. | PASS |
| IV. Test Discipline | Component tests for the pure selection logic; integration_docker for correctness on the full stack; the profiling harness for performance. Adapter pattern, no mocks. | PASS |
| V. Query Performance & Efficiency | This is the performance fix. The coordinator MUST resolve targets per distinct (kind, fields) signature and dedup, and submit a batched recompute (one query over the union of readers), not one flow + one reader query per changed node. | PASS — no-N+1 design constraint tracked below |
| VI. Security & Input Boundaries | No new external input surface. | PASS |
| VII. Simplicity & Maintainability | Reuses the diff/changelog, the computed deriver, the existing per-family facades and batch pattern. Two new pieces: the coordinator (two callers) and the display/HFID deriver (no shared one exists; built to the computed pattern). | PASS — justified below |

No violations. **Note (Principle VII):** the display-label/HFID deriver is new because IFC-2759 closed without building one; it is built to the existing computed-attribute pattern, not as a parallel design. **Note (Principle V):** an implementation that calls the per-node matcher once per changed node, or lets each target re-query readers, reintroduces the fan-out being removed.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2761-coalesce-merge-recompute/
├── plan.md              # This file
├── research.md          # Phase 0 — design decisions (emission points, deriver build, suppression, redundancy)
├── data-model.md        # Phase 1 — in-memory record shapes
├── contracts/
│   └── coalesced-recompute.md   # coordinator entry point + invariants + reuse table
├── quickstart.md        # Phase 1 — correctness + performance validation
├── checklists/requirements.md   # /speckit-specify output
└── tasks.md             # /speckit-tasks output (next phase)
```

### Source Code (repository root, current-develop layout)

```text
backend/infrahub/
├── core/merge/post_merge.py             # CHANGE — merge: build the coalesced recompute from the diff and
│                                        #   submit it on the destination branch instead of per-node fan-out
├── core/branch/tasks.py                 # CHANGE — rebase: same, inline, on the user branch
├── core/merge/recompute_coalescing.py   # NEW — coordinator: diff -> deduplicated affected targets -> batched submit
├── computed_attribute/scoping.py        # REUSE — computed-attribute deriver (PR #9467)
├── display_labels/  hfid/               # CHANGE — build the display-label and HFID derivers here (to the
│                                        #   computed pattern), reading the dependency metadata on the definitions
├── core/schema/schema_branch_display.py, schema_branch_hfid.py  # REUSE — the recorded dependency metadata
└── {computed_attribute,display_labels,hfid}/tasks.py            # REUSE — per-family process/update flows + batch/chunk

backend/tests/
├── component/merge_recompute_coalescing/     # NEW — target-selection correctness (schema fixtures, no worker)
└── integration_docker/                        # NEW — end-to-end correctness vs full recompute on the real stack
```

**Structure Decision**: localized to the merge post-process and rebase paths plus a coordinator and the new display/HFID derivers. No new persisted model. Correctness proven on the full stack; selection logic unit/component-tested; performance measured with the first task's harness.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|------|------------|--------------------------------------|
| Display-label / HFID deriver (new) | No shared deriver exists (IFC-2759 closed); the coalesced scoping needs (kind, field) → affected display-label/HFID targets, built to the computed-attribute pattern from the recorded definition metadata. | Reusing a shared deriver is impossible (none was built); a parallel ad-hoc selection would drift from the live path. |
| Coordinator module | Turning a whole-diff change set into a deduplicated cross-node target set across families is cohesive logic shared by merge and rebase. | Inlining duplicates across merge (post_merge.py) and rebase (tasks.py) and buries non-trivial logic in the flows. |
| Source-branch redundancy trace | The skip optimization (don't re-recompute readers already recomputed on the source branch) needs a trace to be proven safe before design; readers only on the destination branch must always recompute. | Skipping without the trace risks under-recompute (silent stale value); recomputing everything is the safe default but leaves perf on the table. |
| Batched/deduplicated target resolution | Constitution V: per-node resolution or per-target reader re-query re-creates the fan-out. | The per-node loop is the very pattern being removed. |
