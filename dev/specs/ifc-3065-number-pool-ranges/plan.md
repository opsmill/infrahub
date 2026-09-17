# Implementation Plan: Number Pools P1 — Weighted Ranges

**Branch**: `pmi-number-pools-part1` | **Date**: 2026-09-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-3065-number-pool-ranges/spec.md`

## Summary

A number pool gains a set of weighted ranges stored as a new branch-agnostic core kind, `CoreNumberPoolRange`, linked to the pool by a `ranges` relationship. One pure-Python effective-space calculator turns the range set and the attribute's domain into ordered allocation segments and a size, and feeds allocation, utilization and fullness. The read queries filter on a range list; the free-number gap walk stays in Cypher, run per segment. `start_range` / `end_range` stay as a deprecated, optional shorthand mirrored from the range set. Schema-created pools declare `parameters.ranges`; the upserter materialises range nodes, the synchronizer reconciles them, the attribute checker refuses schema changes that leave held values outside every range, and both GraphQL write surfaces refuse direct edits. Deprecation reaches GraphQL introspection by propagating the schema `deprecation` field generally. A data migration gives every existing pool one range. Design decisions and their rationale are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.9 (frontend tolerance changes only)

**Primary Dependencies**: FastAPI, graphene 3.4.3 / graphql-core 3.2.8, Pydantic 2.12, Neo4j driver 6.2, Prefect (schema pool sync flow)

**Storage**: Neo4j graph; new node kind `CoreNumberPoolRange`; data migration `m079`

**Testing**: pytest (unit, component with testcontainers, functional, integration), pytest-benchmark, Vitest for the frontend guard

**Target Platform**: Infrahub server and task worker

**Project Type**: Web service (backend feature with contract regeneration; SDK submodule change)

**Performance Goals**: allocation on a fully allocated 4094-number multi-range pool measured and not regressing against the single-span walk (SC-005); memory held during allocation independent of the number of records (FR-012)

**Constraints**: no change to the GraphQL type of `start_range` / `end_range`; existing single-range pools report identical figures after migration (SC-003); ranges and the pool are branch-agnostic

**Scale/Scope**: pools of a few ranges each; VLAN-sized spaces (thousands of numbers); one migration over every existing pool

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Schema-Driven Integrity | New kind and relationship defined in `core/schema/definitions/core/resource_pool.py`; generated files regenerated, not edited; migration preserves every allocation and figure | Pass |
| II. Branch-Safe by Default | Range and relationship agnostic like the pool; read queries stay `branch_agnostic=True`; cross-branch effect (a range edit applies everywhere) documented in spec principle 2 and tested | Pass |
| III. Type Safety & Explicit Contracts | Calculator exposes frozen dataclasses; queries return typed `get_data()`; GraphQL and parameter contracts written before code (`contracts/`) | Pass |
| IV. Test Discipline | Unit tests for the calculator and parameters; component tests for queries, mutations, upserter, synchronizer, checker, migration, GraphQL manager; functional tests for allocation and schema pools; integration test for the migration and schema lifecycle; no user-facing UI so no new E2E | Pass |
| V. Query Performance | Parameterised Cypher with `$ranges`; gap detection in the database; one query per segment worst case; benchmark added | Pass |
| VI. Security & Input Boundaries | Range bounds validated at the mutation and parameters boundary under the pool lock; refusal messages name ranges and objects, not internals | Pass |
| VII. Simplicity | One calculator replaces three exclusion computations; existing gap query reused instead of new Cypher; no shared weight helper extracted for IP pools (one caller) | Pass |

Post-design re-check: no violation introduced; Complexity Tracking stays empty.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3065-number-pool-ranges/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── graphql-schema-changes.md
│   └── number-pool-parameters.md
├── checklists/requirements.md
├── critiques/
└── tasks.md
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/
│   ├── constants/infrahubkind.py                 # NUMBERPOOLRANGE
│   ├── schema/definitions/core/resource_pool.py  # CoreNumberPoolRange, ranges rel, deprecated shorthand
│   ├── schema/attribute_parameters.py            # NumberPoolParameters.ranges, effective_ranges()
│   ├── schema/__init__.py                        # gather_warnings: shorthand deprecation warning
│   ├── schema/schema_branch.py                   # process_deprecations log scope
│   ├── node/resource_manager/number_pool.py      # get_next over segments, sync_shorthand_from_ranges
│   ├── query/resource_manager.py                 # $ranges on used/allocated/taken
│   ├── validators/enum.py, validators/__init__.py# ranges constraint identifier + registration
│   ├── validators/attribute/number_pool.py       # checker over a range set
│   ├── migrations/graph/m079_number_pool_ranges/ # bootstrap kind + one range per pool
│   └── graph/__init__.py                         # GRAPH_VERSION = 79
├── pools/
│   ├── number_ranges.py                          # EffectiveSpace calculator (new)
│   ├── number.py                                 # NumberUtilizationGetter over the space
│   ├── schema_number_pool_upserter.py            # materialise ranges
│   └── schema_number_pool_synchronizer.py        # reconcile ranges
└── graphql/
    ├── manager.py                                # deprecation_reason propagation, mutation_map entry
    ├── mutations/resource_manager.py             # pool + range mutation classes
    └── queries/resource_manager.py               # per-range utilization edges

backend/tests/
├── unit/pools/test_number_ranges.py
├── unit/core/schema/test_number_pool_parameters.py
├── component/core/resource_manager/test_number_pool.py, test_number_pool_query.py
├── component/core/migrations/graph/m079_number_pool_ranges/
├── component/core/constraint_validators/test_attribute_numberpool_constraints.py
├── component/pools/test_schema_number_pool_upserter.py, test_schema_number_pool_synchronizer.py
├── component/graphql/resource_manager/test_resource_manager.py, test_number_pool_range.py
├── component/graphql/test_manager.py
├── functional/pools/test_numberpool_ranges.py
├── integration/schema_lifecycle/test_attribute_parameters_update.py
└── query_benchmark/test_number_pool_allocation.py

tasks/backend.py                                  # SDK contract families
python_sdk/                                       # regenerated models (separate SDK PR first)
frontend/app/src/entities/schema/ui/attribute-display.tsx
frontend/app/src/shared/api/{graphql,rest}/       # regenerated
docs/docs/schema/number-pool.mdx, docs/docs/resource-manager/allocate-number.mdx
changelog/                                        # fragments listed in spec
```

**Structure Decision**: backend-centred change following the existing resource-manager layout (`core/node/resource_manager`, `core/query/resource_manager`, `pools/`, `graphql/*/resource_manager`). The only new module is the calculator under `pools/`.

## Phase 0: Research

Complete. See [research.md](research.md): current state table, decisions D1 to D16, resolved unknowns.

## Phase 1: Design

| Artifact | Content |
|----------|---------|
| [data-model.md](data-model.md) | `CoreNumberPoolRange`, `CoreNumberPool` changes, `NumberPoolParameters`, `EffectiveSpace`, invariants, migration shape |
| [contracts/graphql-schema-changes.md](contracts/graphql-schema-changes.md) | New type and mutations, deprecation markers, refusals, utilization edge shape |
| [contracts/number-pool-parameters.md](contracts/number-pool-parameters.md) | Published parameter contract (ADR 0010), SDK families, validation rules, warnings |
| [quickstart.md](quickstart.md) | Runnable checks per user story |

## Delivery order (stacked pull requests)

One `gh stack` of six pull requests, merged bottom to top. Each is green and coherent on its own and maps to one Jira sub-task of IFC-3065. Task identifiers are in [tasks.md](tasks.md).

| PR | Content | Depends on | Frontend |
|----|---------|------------|----------|
| 1 | Range kind, `ranges` relationship, deprecated optional shorthand, `@deprecated` propagation in the generator, one utilization entry per range, regenerated protocols / GraphQL schema / frontend GraphQL types | none | Full GraphQL contract available; work starts against this branch |
| 2 | Migration m079 (one range per pool, kind bootstrap), `GRAPH_VERSION`, shorthand mirror helper | 1 | none |
| 3 | Calculator, range-list queries, `get_next` over segments, utilization getter, exact per-range figures | 2 | Figures become exact |
| 4 | Pool mutation shorthand rules by range count, range mutation class, pool lock, overlap refusals, functional test | 3 | Refusal messages final |
| 5 | `parameters.ranges`, `effective_ranges()`, constraint identifier and checker, upserter, synchronizer, guards on both surfaces, deprecation warnings, SDK contract (separate SDK PR first), openapi / REST types / docs snippet | 4 | REST types and schema parameters |
| 6 | Frontend guard, `process_deprecations` log scope, docs, benchmark, changelog fragments, pre-CI on the stack | 5 | Attribute display renders ranges |

PR 1 exposes the generated range mutations without the schema-pool guard until PR 5; pools created before PR 2 hold zero ranges and keep allocating from the shorthand.

## Operational notes

| Topic | Note |
|-------|------|
| Concurrency | Range and shorthand writes take the pool lock (`resource_pool.<pool_id>`), the lock allocation already holds, so two range writes or a range write and an allocation never interleave. |
| Rollback | m079 adds nodes and is not reversed. A previous release reads the mirrored shorthand and ignores `ranges`, so rollback is safe for every pool that still holds one range. |
| Benchmark | The SC-005 figure is recorded in the PR description for comparison by later slices. |

## Approvals in flight

Database schema and migration, GraphQL schema, published schema contract. Listed in the spec's "Approvals needed"; the PR description must call them out.

## Complexity Tracking

None.
