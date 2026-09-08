# Implementation Plan: Number Pools — Several Weighted Ranges per Pool (P1)

**Branch**: `pmi-number-pools-part1` | **Date**: 2026-09-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/infp-308-number-pool-ranges/spec.md`

## Summary

Move a number pool from a single `[start_range, end_range]` span to a set of weighted ranges (`CoreNumberPoolRange`, inheriting `CoreWeightedPoolResource`), keeping the single-span fields as an optional write-shorthand. Introduce one effective-space calculator — (union of ranges) ∩ `[min_value, max_value]` − intersecting exclusions — as the single source for size, utilization, allocation order, and fullness, replacing three drifting computations and removing a divide-by-zero. Generalise the number-pool read queries to a range set (gap detection stays in Cypher). Migrate every existing pool to a single covering range. Per the maintainer's decoupling decision, P1 **updates** rather than deletes the hand-set-value scan (FR-011), so P1 is independently releasable and the #10180 revert defers to P2.

## Technical Context

**Language/Version**: Python 3.14 (backend).

**Primary Dependencies**: FastAPI, Neo4j (driver 6.2), Pydantic 2.12, graphene; Infrahub core schema + query framework.

**Storage**: Neo4j graph. New core node kind `CoreNumberPoolRange`; new `ranges` relationship on `CoreNumberPool`; unchanged `IS_RESERVED` / `HAS_SOURCE` runtime edges on `-global-`.

**Testing**: pytest — unit (`backend/tests/unit/pools/`), component (`backend/tests/component/core/resource_manager/`, `.../constraint_validators/`, `.../migrations/graph/`), functional (`backend/tests/functional/pools/`). Reuse `backend/tests/helpers/number_pool.py`.

**Target Platform**: Linux server (Infrahub backend).

**Project Type**: Web application backend (this slice is backend-only; frontend deferred with P2/SC-004 bulk attach).

**Performance Goals**: Preserve current allocation cost shape — gap detection stays in the database; no pull-all-values-into-Python path. Range-set filter is `ANY`/`OR` over intervals.

**Constraints**: Backward-compatible upgrade with no operator action (data migration). Published-schema-contract change (nullable scalars + `ranges`) requires review. Branch-agnostic ranges.

**Scale/Scope**: Pools from a handful to tens of thousands of numbers (e.g. a 4094-entry VLAN pool). No change to the branch-agnostic ledger.

## Constitution Check

*GATE: must pass before Phase 0 and re-checked after Phase 1.*

- **I. Schema-Driven Integrity** — PASS. New kind + relationship declared in schema first; protocols/GraphQL regenerated; migration keeps existing data schema-valid. Approval required (new core kind, migration, GraphQL contract) — flagged in spec Dependencies & Risks and the contract doc.
- **II. Branch-Safe by Default** — PASS. Ranges branch-agnostic like the pool; migration and reads respect branch semantics; held-number liveness join unchanged.
- **III. Type Safety & Explicit Contracts** — PASS. GraphQL/REST contract defined before implementation (`contracts/graphql-schema-changes.md`); query results via frozen dataclass `get_data()` (existing pattern in `resource_manager.py`); no untyped dicts for the range set — a typed structure.
- **IV. Test Discipline** — PASS. Component tests for allocation/effective-space/validator/migration, functional for branch-agnostic edits; fixtures reused. Tests written alongside each task.
- **V. Query Performance & Efficiency** — PASS. Parameterised Cypher only; gap detection stays in the DB; range set passed as a parameter list; return only needed properties. `EXPLAIN` the generalised `NumberPoolGetFree` gap walk.
- **VI. Security & Input Boundaries** — PASS. Range inputs validated at the GraphQL boundary (per-range `start <= end`, intra-pool non-overlap); parameter binding only.
- **VII. Simplicity & Maintainability** — PASS. The effective-space calculator *removes* three duplicated computations (net simplification). `CoreNumberPoolRange` reuses the existing weighted-resource generic (second consumer after IP pools). No new dependency.

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/infp-308-number-pool-ranges/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── graphql-schema-changes.md
├── checklists/
│   └── requirements.md
└── tasks.md            # created by /speckit-tasks
```

### Source code (touch points)

```text
backend/infrahub/
├── core/
│   ├── schema/
│   │   ├── definitions/core/resource_pool.py     # CoreNumberPoolRange kind; start_range/end_range → optional; ranges rel
│   │   ├── definitions/core/__init__.py          # register new kind
│   │   └── attribute_parameters.py               # NumberPoolParameters: defaults→None, ranges list, validator, get_pool_size
│   ├── protocols.py                              # (generated) CoreNumberPoolRange protocol
│   ├── node/resource_manager/number_pool.py      # get_next: effective-space calc, skip_excluded, get_taken hook (kept)
│   ├── query/resource_manager.py                 # NumberPoolGetFree/Used/Allocated/Reserved/Taken → range set
│   ├── validators/attribute/number_pool.py       # AttributeNumberPoolChecker over a range set (FR-039)
│   └── migrations/graph/
│       ├── m0NN_number_pool_single_range.py      # data migration (ArbitraryMigration, per m066)
│       └── __init__.py                           # register Migration0NN
├── pools/number.py                               # effective-space calculator; total_pool_size + utilization (no ZeroDivision)
└── graphql/mutations/resource_manager.py         # per-range guard, overlap refusal
backend/tests/
├── component/core/resource_manager/test_number_pool.py, test_number_pool_query.py
├── component/core/constraint_validators/test_attribute_numberpool_constraints.py
├── component/core/migrations/graph/test_0NN_number_pool_single_range.py
├── functional/pools/test_numberpool_branch.py, test_numberpool_lifecycle.py
└── helpers/number_pool.py                        # fixtures (reuse/extend)
changelog/                                        # P1 fragments (utilization sensitivity; nullable shorthand read)
schema/schema.graphql, schema/openapi.json        # (generated) regenerate + commit
frontend/app/.../generated                         # (generated) codegen + commit
dev/knowledge/backend/                             # ranges model + effective-space calculator
```

**Structure Decision**: Backend-only change within the existing resource-manager/pool modules and the schema-definitions/migrations framework. No new top-level package. The one new module-level abstraction — the effective-space calculator — lives in the existing `backend/infrahub/pools/number.py`, replacing three duplicated computations; it is justified by two-plus existing callers (`get_next`, `total_pool_size`/`utilization`, and the read-query range set), satisfying Principle VII.

## Sequencing & de-risking (from critique)

- **De-risk first (must-address E1/X1)**: The very first implementation task is a fail-fast schema-load spike proving that an `AGNOSTIC` node (`CoreNumberPoolRange`) can inherit the `AWARE` generic `CoreWeightedPoolResource` and that `allocation_weight` materialises correctly (research D2). If it fails, apply the recorded fallback — make `CoreWeightedPoolResource` branch-neutral for inheritance rather than storing ranges branch-aware — before building the queries, migration, or mutation on top.
- **Range-validity on every write path (must-address E2)**: Enforce `start ≤ end` and intra-pool non-overlap (FR-004) in **both** the GraphQL mutation (`InfrahubNumberPoolMutation`) and the schema-created path (`NumberPoolParameters` validation), each with its own test. Cross-pool overlap stays allowed.
- **Benchmark the gap walk (E3/E4)**: `EXPLAIN` the generalised `NumberPoolGetFree` range-set gap walk and add one at-scale allocation benchmark (a fully-allocated multi-range pool, e.g. a 4094-entry VLAN pool) to guard against regression versus the single-span walk.
- **Migration re-run safety (E5)**: The data migration is forward-only (per the `ArbitraryMigration` framework) and MUST be idempotent — running it against a pool that already has a covering range must not create a second one. Assert this in the migration test.
- **Consumer tolerance for nullable reads (P1/X2)**: Verify existing frontend/API consumers tolerate a null `start_range`/`end_range`; the changelog upgrade note must address API consumers, not only pool authors.

## Phase notes

- **Phase 0 (research)**: complete → `research.md` (decisions D1–D12; branch-inheritance point D2 now sequenced as the first fail-fast task above).
- **Phase 1 (design)**: complete → `data-model.md`, `contracts/graphql-schema-changes.md`, `quickstart.md`; agent context updated.
- **Post-design constitution re-check**: PASS — no new violations introduced by the design; the effective-space consolidation is a net reduction in complexity.

## Complexity Tracking

No constitution violations to justify.
