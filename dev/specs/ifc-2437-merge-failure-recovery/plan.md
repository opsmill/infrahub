# Implementation Plan: Merge Failure Recovery

**Branch**: `ifc-2437-merge-failure-recovery` | **Date**: 2026-04-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `dev/specs/ifc-2437-merge-failure-recovery/spec.md`

## Summary

Detect and automatically roll back branch merges that fail catastrophically (process kill, OOM, worker crash) before the API serves traffic again. The mechanism is a pair of new transient `BranchStatus` values — `MERGING_GRAPH` (narrow, scanned by recovery) and `MERGING` (broad, blocks writes during migrations and repo merges) — plus a `merge_started_at` timestamp on the source branch. A startup recovery scan calls the existing `DiffMergeRollbackQuery` with the persisted `at` timestamp; the broader status keeps source/target branches read-only for the entire merge.

> **Architecture context**: The merge code path was rewritten on this branch — `DiffMerger.merge_graph` is now five bulk Cypher queries (each a retried transaction) plus a metadata pass, all writing to `branch=$target_branch` and stamped with a single `$at`. The existing `DiffMergeRollbackQuery` is keyed on that same `$at` and target branch and operates globally on edges with that timestamp, so it cleanly undoes any partial subset of the bulk merges given just `(target_branch, at)` + a UUID list (which `DiffRepository.get_affected_node_uuids(...)` produces statelessly). This makes the recovery design strictly simpler than it would have been on the pre-rewrite code.

Phase 0 research resolved: marker placement (two new transient `BranchStatus` values — `MERGING_GRAPH` for the narrow recovery-relevant window inside `merge_graph`, `MERGING` for the broad write-block window covering migrations and repo merges — plus one supplementary `merge_started_at` field on `Branch`; target is always the default branch and is not persisted), recovery insertion point (after `initialize_registry()` in `initialization.py`), restart-safe rollback (extend `DiffMerger.rollback` to accept a pre-computed UUID list from `DiffRepository.get_affected_node_uuids`), worker coordination (existing lock registry keyed on the source branch name), and write-block enforcement (extend the existing `BranchStatusChecker` with a `check_merging_status` method that gates on both new statuses, in line with the existing `MERGED`/`NEED_REBASE` gates).

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 (frontend — no changes expected for v1).
**Primary Dependencies**: FastAPI 0.121, Pydantic 2.10, Neo4j 5.28 driver, Prefect 3 (existing merge workflow), existing distributed `lock.registry` (Redis or NATS depending on cache driver).
**Storage**: Neo4j. Adds `BranchStatus.MERGING` and `BranchStatus.MERGING_GRAPH` to the existing status enum and one supplementary scalar field (`merge_started_at`) on the `:Branch` node. The merge target is always `registry.default_branch`, so it does not need to be persisted. The persisted enriched diff in `DiffRepository` is read by `get_affected_node_uuids` during recovery; no new diff persistence is required.
**Testing**: pytest + pytest-asyncio. Component tests in `backend/tests/component/` for the recovery logic; integration_docker test in `backend/tests/integration_docker/` for the cross-process SIGKILL flow.
**Target Platform**: Linux server (Infrahub backend, runs in Docker).
**Project Type**: Web service backend (FastAPI + Prefect workers).
**Performance Goals**: Recovery scan adds ≤500 ms to API startup when no partial merges exist (SC-003). Recovery rollback time bounded by the size of the persisted diff (no new work beyond existing rollback query).
**Constraints**: Must not regress merge happy-path performance materially. API readiness is gated on recovery completion — recovery must fail-closed, not silently skip.
**Scale/Scope**: A single Infrahub instance has at most one active merge at a time today (`MergeLocker.acquire_global_lock`). Recovery scan handles 0–N markers; N is bounded by the number of branches.

## Constitution Check

The Infrahub Constitution (`.specify/memory/constitution.md`, v1.0.0) gates apply as follows:

| Principle | Gate | Status |
|---|---|---|
| I. Schema-Driven Integrity | Branch model change must go through the Pydantic model and Cypher write paths, not bypass them. | **Pass** — new fields added to `Branch` Pydantic model, persisted via existing `Branch.save()` Cypher. |
| II. Branch-Safe by Default | Recovery must operate correctly across branches; markers are per-branch; mutation entry points already branch-aware. | **Pass** — design tracks marker per source branch and per target; write-block helper consults branch context. |
| III. Type Safety & Explicit Contracts | New fields and new module use type hints; new helpers expose explicit signatures (see `contracts/internal-api.md`). | **Pass** |
| IV. Test Discipline | Both component and integration_docker tests required; integration_docker is mandatory for cross-process restart behavior. | **Pass** — research.md R7 specifies both. |
| V. Query Performance & Efficiency | New Cypher (marker set/clear, scan) must be parameterized, return only required props. Recovery scan runs once per startup. | **Pass** — design uses parameterized queries; scan is `MATCH (b:Branch {status: "MERGING_GRAPH"}) RETURN b.name, b.merge_started_at`. |
| VI. Security & Input Boundaries | No new external input surfaces. Internal recovery logic does not consume user input. | **Pass** — recovery scan reads Neo4j-internal state. |
| VII. Simplicity & Maintainability | No new entity, no new lock infrastructure, no new external dependency. Reuses existing rollback Cypher. | **Pass** — see research.md alternatives sections justifying rejected complexity. |

**Result**: All gates pass. No entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-2437-merge-failure-recovery/
├── spec.md              # User-facing specification
├── plan.md              # This file
├── research.md          # Phase 0 decisions (R1–R8)
├── data-model.md        # Branch entity extension and lifecycle
├── quickstart.md        # End-to-end verification scenarios
├── contracts/
│   └── internal-api.md  # New/changed Python interfaces
└── tasks.md             # (Phase 2 output of /speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── infrahub/
│   ├── core/
│   │   ├── branch/
│   │   │   ├── enums.py                   # +BranchStatus.MERGING,
│   │   │   │                               # +BranchStatus.MERGING_GRAPH
│   │   │   └── models.py                  # +merge_started_at
│   │   ├── merge/
│   │   │   ├── branch_merger.py           # +_enter_merging(),
│   │   │   │                               # +_exit_merging_to_open(),
│   │   │   │                               # +_enter_merging_graph(),
│   │   │   │                               # +_exit_merging_graph(),
│   │   │   │                               # wired into merge() and called
│   │   │   │                               # from _do_merge_branch
│   │   │   └── recovery.py                # NEW: recover_partial_merges()
│   │   ├── diff/
│   │   │   └── merger/
│   │   │       └── merger.py              # rollback() gains optional node_uuids
│   │   │                                   # param for restart-safe recovery
│   │   └── initialization.py              # +call recover_partial_merges()
│   ├── branch/
│   │   └── status_checker.py              # +check_merging_status(),
│   │                                       # called from check()
│   └── exceptions.py                      # +RecoveryFailedError
│                                           # (BranchStatusError already exists)
└── tests/
    ├── component/
    │   └── core/merge/
    │       └── test_recovery.py           # NEW: recovery logic in-process
    └── integration_docker/
        └── test_merge_kill_recovery.py    # NEW: SIGKILL + restart end-to-end
```

**Structure Decision**: Existing Infrahub web-service layout. All new code lives in `backend/`; no frontend changes required for v1 (operator visibility is via logs and Neo4j inspection). Tests follow the constitution's required levels.

## Implementation Phases (preview — not generated by this command)

Phase 2 (`/speckit-tasks`) will decompose into work items roughly in this order:

1. Add `BranchStatus.MERGING` and `BranchStatus.MERGING_GRAPH` to the enum; add `merge_started_at` field to `Branch`.
2. Implement `BranchMerger._enter_merging` / `_exit_merging_to_open` / `_enter_merging_graph` / `_exit_merging_graph` (idempotent transitions; persist/clear `merge_started_at` only on the graph-window pair).
3. Wire helpers into `BranchMerger.merge` (broad MERGING at entry; narrow MERGING_GRAPH around `merge_graph`; restore on success and on exception). Update `branch/tasks.py:_do_merge_branch` to invoke `_enter_merging` at start (if not already covered by `BranchMerger.merge`'s entry) and `_exit_merging_to_open` on its own failure paths.
4. Extend `DiffMerger.rollback` to accept an optional `node_uuids` parameter; recovery passes UUIDs from `DiffRepository.get_affected_node_uuids`.
5. Implement `recover_partial_merges` (new module `core/merge/recovery.py`) and the per-branch recovery lock. Recovery scans `MERGING_GRAPH` only.
6. Hook recovery into `initialization.py` after `initialize_registry()`.
7. Extend `BranchStatusChecker` with `check_merging_status` (gates on both new statuses, with the default-branch target gate via Cypher) and call it from `check()`. Audit mutation paths that don't currently route through `BranchStatusChecker.check` and update them.
8. Tests: component test of the recovery flow; integration_docker test of SIGKILL + restart; tests confirming write-block coverage during the broad `MERGING` window (e.g., during migrations).
9. Add structured log events per research.md R8.
10. Update `dev/knowledge/backend/` with a section on the merge lifecycle (two transient statuses, recovery, write-block) and the recovery's dependency on bulk-merge query invariants.

## Complexity Tracking

> No constitution gate violations. Section intentionally empty.
