# Implementation Plan: Branch Merge Locking — Multi-Tier Coordination Between Writes and Merges

**Branch**: `branch-merge-locking-ifc-2562` | **Date**: 2026-05-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/ifc-2562-branch-merge-locking/spec.md`

## Summary

Introduce a `BranchLocker` primitive that gives the merge flow branch-scoped read-write coordination on top of the existing `InfrahubLock` and cache adapter plumbing. The locker exposes two context managers — `acquire_write` (called at write entry points) and `acquire_merge` (called by the merge flow). A merge claims `merge_intent` on its source and target branches, drains in-flight writers (with timeout), then proceeds with the existing `MergeLocker` and `global_graph_lock` still in place underneath. Subsequent writes against either branch fail fast with `BranchLockedError`; writes against unrelated branches are unaffected by the new mechanism. A merge-holder identifier (in-process `ContextVar` and explicit Prefect parameter) lets the merge's own follow-on writes pass through. Crash recovery is achieved via TTL'd cache keys with a heartbeat. Existing fine-grained locks (`get_lock_names_on_object_mutation`) and the middleware's `BranchStatus.MERGING` guard remain unchanged.

The work lands in seven sequential PRs (primitive → merge wiring → GraphQL chokepoint → remaining GraphQL → REST → workflows → cleanup). Initial-rollout invariants — single global merge serialization and the `global_graph_lock` — are preserved; their removal is gated on production validation as a follow-up.

## Technical Context

**Language/Version**: Python 3.14 (backend)
**Primary Dependencies**: FastAPI 0.121.1, Strawberry GraphQL via Graphene-style mutations, Prefect 3 (workflow runtime), Pydantic 2.10, redis.asyncio, nats.aio (cache backends)
**Storage**: Neo4j 5.28 (graph database, untouched by this work); cache backend (Redis or NATS KV) for coordination state
**Testing**: pytest 9.0 — unit (`backend/tests/unit/`), component (`backend/tests/component/`), functional (`backend/tests/functional/`), integration_docker (`backend/tests/integration_docker/`)
**Target Platform**: Linux server (Docker; multi-process Uvicorn workers + Prefect worker pool)
**Project Type**: Backend service feature; no UI surface, no new external API surface (only a new error code on existing endpoints)
**Performance Goals**: Sub-millisecond `acquire_write` overhead on writes against any branch; no measurable degradation in unrelated-branch write throughput vs. pre-feature baseline (SC-001)
**Constraints**: Multi-process / multi-worker (coordination state MUST be visible across processes); cache adapter TTL semantics differ between Redis (per-key) and NATS (bucket-level — current FIXME at `services/adapters/cache/nats.py:34`); existing `MergeLocker.acquire_global_lock()` and `global_graph_lock()` remain in place during this rollout
**Scale/Scope**: ~20 Prefect workflow definitions write to a branch and need wrapping; ~10 GraphQL mutation classes outside the `InfrahubMutationMixin` chokepoint need wrapping; 2 REST write endpoints; 4 sub-flows submitted from inside `_do_merge_branch`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ Pass | No schema changes. Coordination is orthogonal to schema; merge's existing schema-migration step is preserved and runs *inside* the merge's own claim (bypassed via merge holder id). |
| II. Branch-Safe by Default | ✅ Pass — central to the feature | Coordination is per-branch by design. Merge target and source branches are the unit of coordination. Merge-time behavior is the explicit subject of the spec (FR-002, FR-007). |
| III. Type Safety & Explicit Contracts | ✅ Pass | New `BranchLocker` API uses fully typed `async def` context managers (`AsyncIterator[None]` / `AsyncIterator[str]`); `MergeHolder` is a frozen dataclass; cache-adapter calls use the typed cache abstraction. New errors extend the existing exception hierarchy. |
| IV. Test Discipline | ✅ Pass | Unit tests exercise `BranchLocker` against a real cache backend (NATS or Redis fixture). Functional tests cover the wraps; integration_docker tests cover end-to-end merges with concurrent writes and crash recovery. Mocks reserved for time-dependent behavior in heartbeat tests. |
| V. Query Performance & Efficiency | ✅ Pass — non-database | Coordination uses cache backend, not Neo4j. No new queries. The hot path (`acquire_write` against an unmerged branch) is one cache `set(..., not_exists=True)` plus a periodic heartbeat — comparable to existing per-mutation lock acquisitions. |
| VI. Security & Input Boundaries | ✅ Pass | Branch names in coordination keys are not user-supplied free-form text — they are existing branch identifiers already validated upstream. Cache keys use a fixed namespace (`branch.{name}.*`). New `BRANCH_LOCKED` error message reveals only the branch name (already public to the caller) and operation reason — no internal state. |
| VII. Simplicity & Maintainability | ✅ Pass — with one note | Reuses `InfrahubLock` for the gate, the cache adapter for state, and existing GraphQL middleware/mutation chokepoints. The single complexity item is the merge-holder ContextVar + Prefect-parameter dual mechanism — justified by the cross-process requirement (a single mechanism cannot cover both in-process and Prefect sub-flow callers). See Complexity Tracking. |

**Gate decision**: PASS. One justified complexity item logged below.

### Frontend principles

Not applicable — this is a backend coordination feature with no UI surface.

### Shared Components Inventory

Not applicable — backend feature.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2562-branch-merge-locking/
├── spec.md                    # Feature specification (clarified)
├── plan.md                    # This file
├── research.md                # Phase 0 — design decisions, alternatives, factual corrections
├── data-model.md              # Phase 1 — coordination entities, lifecycles, key naming
├── quickstart.md              # Phase 1 — manual smoke test recipe
├── contracts/
│   ├── branch_locker.md       # Internal Python API contract for the new primitive
│   ├── error-response.md      # New BRANCH_LOCKED error code (GraphQL + HTTP) — externally visible
│   └── workflow-parameters.md # `merge_holder_id` parameter convention for writer flows
└── checklists/
    └── requirements.md        # Spec-quality checklist (already satisfied)
```

### Source Code (repository root)

```text
backend/
├── infrahub/
│   ├── core/
│   │   └── branch/
│   │       ├── branch_locker.py            # NEW — BranchLocker, MergeHolder, error types
│   │       └── tasks.py                    # MODIFIED — wire acquire_merge into merge_branch / _do_merge_branch
│   ├── core/
│   │   └── merge/
│   │       └── merge_locker.py             # UNCHANGED — kept under the new locker
│   ├── exceptions.py                       # MODIFIED — add BranchLockedError, MergeWriteDrainTimeoutError
│   ├── config.py                           # MODIFIED — add merge.write_drain_timeout_seconds and TTL settings
│   ├── graphql/
│   │   ├── mutations/
│   │   │   ├── main.py                     # MODIFIED — wrap InfrahubMutationMixin.mutate() body
│   │   │   ├── relationship.py             # MODIFIED — wrap RelationshipAdd / RelationshipRemove
│   │   │   ├── schema.py                   # MODIFIED — wrap dropdown/enum schema mutations
│   │   │   ├── profile.py                  # COVERED via main.py (extends mixin); explicit wrap on InfrahubProfilesRefresh
│   │   │   ├── computed_attribute.py       # MODIFIED — wrap UpdateComputedAttribute, RecomputeComputedAttribute
│   │   │   ├── ipam.py                     # COVERED via main.py (extends mixin)
│   │   │   ├── diff_conflict.py            # MODIFIED — wrap ResolveDiffConflict
│   │   │   ├── hfid.py                     # MODIFIED — wrap UpdateHFID
│   │   │   ├── display_label.py            # MODIFIED — wrap UpdateDisplayLabel
│   │   │   └── proposed_change.py          # MODIFIED — wrap ProposedChangeReview (already checks MERGING)
│   ├── api/
│   │   ├── schema.py                       # MODIFIED — wrap POST /schema/load
│   │   └── artifact.py                     # MODIFIED — wrap POST /artifact/generate
│   ├── workflows/
│   │   ├── catalogue.py                    # MODIFIED — extend writer flow parameter models with optional merge_holder_id
│   │   └── models.py                       # If a shared base parameter model exists — add the field there
│   ├── schema/tasks.py                     # MODIFIED — wrap schema_updated flow body
│   ├── generators/tasks.py                 # MODIFIED — wrap generator runs
│   ├── git/tasks.py                        # MODIFIED — wrap repository sync flows
│   ├── branch/tasks.py                     # MODIFIED — wrap branch_merged consumer (this is the messaging-layer module, distinct from core/branch/tasks.py)
│   └── services/adapters/cache/nats.py     # POTENTIALLY MODIFIED — new bucket TTLs (TWO_MINUTES, FIVE_MINUTES) — see research.md decision
└── tests/
    ├── unit/
    │   └── core/
    │       └── branch/
    │           └── test_branch_locker.py   # NEW — primitive unit tests
    ├── functional/
    │   └── merge/
    │       └── test_branch_locker_wraps.py # NEW — wraps under realistic merge flow
    └── integration_docker/
        └── test_branch_merge_coordination.py # NEW — multi-process drain/reject/crash-recovery scenarios
```

**Structure Decision**: This is a backend-only coordination feature; the established repository layout (`backend/infrahub/`, with `tests/{unit,functional,integration_docker}/` mirroring source structure) applies as-is. The new primitive lives under `backend/infrahub/core/branch/branch_locker.py` to keep it adjacent to `core/branch/tasks.py` (which calls it) and the existing branch-status enums. No new top-level packages.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Dual merge-holder mechanism (ContextVar **and** explicit Prefect parameter) | The merge submits sub-flows via `submit_workflow`; those run in a different process and cannot inherit a `ContextVar` from the merge's coroutine tree. A `ContextVar` alone covers the in-process case but not cross-process; an explicit parameter alone forces every in-process sub-call (including library code that the merge calls into) to thread the holder id through every signature. Both together let in-process callers skip plumbing and cross-process callers carry it explicitly. | A single mechanism cannot satisfy both requirements simultaneously. Threading `holder_id` through every internal call signature is a wider blast radius than a single `ContextVar`; relying on `ContextVar` alone would silently break cross-process bypasses (the merge would deadlock on its own claim from inside a sub-flow). |
| New cache TTL buckets (TWO_MINUTES, FIVE_MINUTES) on NATS | Existing NATS bucket TTLs are `ONE`, `TEN`, `FIFTEEN`, `ONE_MINUTE`, `TWO_HOURS`. Writer keys need ~2 min and merge intent ~5 min. Reusing `TWO_HOURS` strands a crashed-writer claim for two hours; reusing `ONE_MINUTE` is shorter than a safe heartbeat interval. | Per-key TTL on NATS is not currently supported (FIXME at `services/adapters/cache/nats.py:34`); fixing that is out of scope for this work. Adding two bucket constants is the minimal change. |

Both are documented in research.md with the alternatives evaluated.
