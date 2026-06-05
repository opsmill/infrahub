# Implementation Plan: Schema-level `order_by` for node metadata and direction

**Branch**: `infp-530-schema-order-by-metadata` | **Date**: 2026-05-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `dev/specs/infp-530-order-by-metadata-direction/spec.md`

## Summary

Extend the schema `order_by` field to accept two new entry shapes — `node_metadata__<field>` and any entry suffixed with `__asc` / `__desc` — and honor both consistently across the top-level node list, relationship-peer list, and hierarchy list paths. The wire shape (`list[str] | None`) is preserved. A new central parser produces a typed `ParsedOrderByEntry` that the validator and the three query paths share, eliminating today's three independent split-sites. Direction is propagated from parse into each path's outer `ORDER BY` clause; node-metadata entries reuse the existing top-level metadata-subquery pattern, extended to the peer and hierarchy paths. A UUID tiebreaker is appended whenever schema `order_by` is in effect, fixing today's inconsistency where only the top-level path appends one. Query-time ordering arguments fully replace the schema default (no stacking) — a deliberate behavior change called out in the spec.

## Technical Context

**Language/Version**: Python 3.12 (backend); no frontend changes (spec Assumptions).
**Primary Dependencies**: FastAPI 0.131.0, GraphQL via graphene, Pydantic>=2.12,<2.13, Neo4j Python driver 6.0.3.
**Storage**: Neo4j 5.28. No schema migration required; no data backfill.
**Testing**: pytest 9.0 with the existing unit / component / functional / integration_docker layering. New tests at the component layer for the validator and the three query paths.
**Target Platform**: Linux backend service.
**Project Type**: web-service (this feature is backend-only — schema layer + query layer).
**Performance Goals**: No regression vs. today on the top-level path (adds a direction token); relationship-peer and hierarchy paths gain at most one additional metadata subquery per metadata entry, comparable to the existing top-level metadata subquery cost.
**Constraints**: Must remain branch-safe and temporally aware (Principle II); all queries already include branch/from filters and this change does not touch that surface. Must preserve every existing `order_by` entry's behavior (FR-012). Single named breaking change: schemas literally using `node_metadata` as an attribute or relationship name (FR-005).
**Scale/Scope**: Touches ~6 backend modules (schema validator, schema constants, three query classes, one new helper module). New component tests across the three paths and the validator. One changelog fragment.

## Constitution Check

### Frontend principles

Not applicable. The feature is backend-and-schema only; the frontend consumes backend-ordered results unchanged (spec Assumptions).

### Backend principles

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | PASS | This is a schema-layer feature. Validator rejects malformed entries at schema load (FR-004, FR-005, FR-006, FR-007). No bypass of schema enforcement. |
| II. Branch-Safe by Default | PASS | All affected queries already include branch + temporal filters. Direction tokens and UUID tiebreakers do not alter the filter set. No cross-branch side effects introduced. |
| III. Type Safety & Explicit Contracts | PASS | New `ParsedOrderByEntry` frozen dataclass + `OrderByTargetKind` / `OrderByMetadataField` enums replace ad-hoc `entry.split("__")` at four call sites. Direction is already an `OrderDirection` enum. |
| IV. Test Discipline | PASS | New tests at the component layer: validator success/failure cases, top-level list ordering (extend existing), relationship-peer ordering (new metadata coverage), hierarchy ordering (new direction + metadata coverage). Functional/integration tests not required (no async pipelines or distributed components touched). |
| V. Query Performance & Efficiency | PASS | Parameterized cypher throughout. No N+1. Each new direction adds one keyword. Metadata subqueries on relationship-peer and hierarchy mirror the existing top-level subquery cost. |
| VI. Security & Input Boundaries | PASS | Schema is authored by administrators and validated at load. No user input reaches Cypher unparameterized. |
| VII. Simplicity & Maintainability | PASS | Centralizing the parser is justified by four existing call sites — meets the "two existing callers" bar in Principle VII. No new dependencies; reuses existing `OrderDirection`, `METADATA_*` constants, `SchemaAttributePath`. |

No gate violations. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-530-order-by-metadata-direction/
├── spec.md                  # Feature spec (input)
├── plan.md                  # This file (/speckit-plan)
├── research.md              # Phase 0 decisions
├── data-model.md            # ParsedOrderByEntry + grammar
├── quickstart.md            # Manual end-to-end walkthrough
├── contracts/
│   ├── grammar.md           # Author-facing entry grammar
│   ├── list-paths.md        # Ordering behavior across the 3 paths
│   └── errors.md            # Schema-load-time error templates
├── checklists/              # (existing; spec-time checklists)
└── tasks.md                 # Phase 2 output (created by /speckit-tasks)
```

### Source code touch list

```text
backend/infrahub/core/
├── constants/__init__.py                       # add "node_metadata" to RESERVED_ATTR_REL_NAMES (via NODE_METADATA_PREFIX)
├── schema/
│   ├── order_by.py                              # NEW: parser, ParsedOrderByEntry variants, enums, helpers
│   ├── schema_branch.py                         # use parser in validate_order_by() + duplicate detection
│   └── node_inheritance_handler.py              # guard rename helper to skip METADATA entries
└── query/
    ├── node.py                                  # NodeGetListQuery direction + precedence + UUID tiebreaker;
    │                                            # NodeGetHierarchyQuery direction + metadata + UUID tiebreaker
    ├── relationship.py                          # RelationshipGetListQuery direction + metadata + UUID tiebreaker;
    │                                            # adds requested_order plumbing for the peer path
    └── subquery.py                              # NEW build_subquery_order_metadata helper, shared by peer/hierarchy paths

backend/tests/component/core/
├── schema_manager/test_manager_schema.py        # extend: new validation cases (grammar, duplicates, reserved name)
├── test_node_get_list_query.py                  # extend: direction + metadata + UUID tiebreaker assertions
├── test_relationship_get_list_query.py          # new/extend: peer ordering across all entry kinds
└── test_node_get_hierarchy_query.py             # new/extend: hierarchy ordering across all entry kinds

backend/tests/component/graphql/
├── metadata/test_graphql_query_metadata.py     # extend: schema-default vs query-time precedence
└── queries/                                     # add: relationship-peer + hierarchy default-newest-first

changelog/
└── +order-by-metadata-direction.added.md        # changelog fragment
```

**Structure Decision**: Existing backend layout. The single new file is `backend/infrahub/core/schema/order_by.py`, which owns the parser, the dataclass, and the two new enums. Placing it under `core/schema/` keeps it adjacent to `schema_branch.py` (its primary caller) and follows the project convention of co-locating schema-layer helpers with the validator.

## Phase 2 hand-off

Phase 2 is performed by `/speckit-tasks`. Tasks must cover, in dependency order:

1. Add `node_metadata` to `RESERVED_ATTR_REL_NAMES` + test the reserved-name rejection.
2. Create `core/schema/order_by.py` (parser, dataclass, enums) + unit tests for the parser.
3. Wire the parser into `SchemaBranch.validate_order_by()`; add load-time validation tests covering every rejection case in `contracts/errors.md`.
4. Guard the inheritance rename helper to skip METADATA entries; test that metadata entries survive a generic attribute rename unchanged.
5. Top-level path: propagate parsed direction, switch precedence from OR-stack to replace, verify UUID tiebreaker. Extend `test_node_get_list_query.py`.
6. Relationship-peer path: add direction propagation, metadata subquery support, UUID tiebreaker. Tests.
7. Hierarchy path: same as relationship-peer. Tests.
8. GraphQL precedence: extend `test_graphql_query_metadata.py` to lock in the replace-not-stack behavior.
9. End-to-end smoke via `quickstart.md` scenario (component or functional test).
10. Changelog fragment under `changelog/`.

## Complexity Tracking

No constitutional violations; this section is intentionally empty.
