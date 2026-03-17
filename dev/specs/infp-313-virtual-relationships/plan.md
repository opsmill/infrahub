# Implementation Plan: Virtual Relationships

**Branch**: `infp-313-virtual-relationships` | **Date**: 2026-03-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/infp-313-virtual-relationships/spec.md`

## Summary

Implement virtual relationships — schema-level computed relationship definitions that traverse multi-hop paths to collect target nodes. Users define a traversal path (e.g., `bays__line_cards__modules__interfaces`) on a node kind, and the system resolves it at query time via Cypher multi-hop traversal. This bridges the gap between schema correctness and query simplicity without data duplication.

**Technical approach**: Add `VirtualRelationshipSchema` to the schema layer, generate GraphQL fields using existing `NestedPaginated` wrappers with a dedicated resolver, execute multi-hop Cypher queries adapted from the existing hierarchy traversal pattern, and display results in the frontend as relationship tabs.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 (frontend)
**Primary Dependencies**: FastAPI 0.121.1, graphene (GraphQL), neo4j-driver, React 19.2
**Storage**: Neo4j 5.28 (no new data stored — virtual relationships are computed views over existing edges)
**Testing**: pytest 9.0 (backend), Vitest 4.0 (frontend unit), Playwright 1.56 (E2E)
**Target Platform**: Linux server (backend), Web browser (frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Virtual relationship queries return within 2 seconds for 5-hop paths with up to 1,000 target nodes
**Constraints**: Must be branch-aware, must respect access control, no new database schema (no new Neo4j node/edge types)
**Scale/Scope**: Schema definitions with up to 10 virtual relationships per node, traversal paths up to 10 segments (5 logical hops)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | PASS | Virtual relationships are defined in the schema layer. No manual editing of generated files. Schema validation enforces path correctness. |
| II. Branch-Safe by Default | PASS | Traversal queries use existing branch/temporal filters via `Branch.get_query_filter_relationships()`. The `reduce()` scoring pattern for multi-hop branch resolution is already tested in hierarchy queries. |
| III. Type Safety & Explicit Contracts | PASS | `VirtualRelationshipSchema` is a Pydantic model with type hints. GraphQL types are generated, not hand-written. Cypher queries use parameterized `$param` syntax. |
| IV. Test Discipline | PASS | Unit tests for schema validation, functional tests for query resolution, E2E tests for UI display. Test plan defined per story. |
| V. Query Performance & Efficiency | PASS | Parameterized Cypher, bounded traversal depth (max 10 segments), pagination on results. Uses existing `query_size_limit` pattern. |
| VI. Security & Input Boundaries | PASS | Path definitions validated at schema load time. Cypher uses parameter binding. Permission filtering on target nodes. |
| VII. Simplicity & Maintainability | PASS | Follows existing patterns: schema model, GraphQL generation pass, resolver, Cypher query class. No new abstractions. |

### Post-Design Re-Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | PASS | `VirtualRelationshipSchema` added to `NodeSchema.virtual_relationships` list. Validated during `SchemaBranch.process()`. |
| II. Branch-Safe by Default | PASS | Multi-hop Cypher query applies `all(r IN relationships(path) WHERE branch_filter)` — same pattern as hierarchy queries. |
| III. Type Safety & Explicit Contracts | PASS | GraphQL contract defined in `contracts/graphql-api.graphql`. Schema contract in `contracts/schema-definition.yaml`. No untyped dicts. |
| IV. Test Discipline | PASS | Test levels: unit (schema validation), functional (query resolution, GraphQL), E2E (UI tabs). |
| V. Query Performance & Efficiency | PASS | Cypher uses `DISTINCT` for dedup, parameterized queries, pagination via `SKIP`/`LIMIT`. Bounded depth prevents unbounded traversal. |
| VI. Security & Input Boundaries | PASS | Schema paths validated at load time (no user input at query time). Target node permissions respected. |
| VII. Simplicity & Maintainability | PASS | One new schema model, one new query class, one new resolver, one frontend visibility extension. No new abstractions or patterns. |

**Gate result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/infp-313-virtual-relationships/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: Research findings
├── data-model.md        # Phase 1: Data model
├── quickstart.md        # Phase 1: User quickstart guide
├── contracts/           # Phase 1: API contracts
│   ├── schema-definition.yaml
│   └── graphql-api.graphql
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── infrahub/core/schema/
│   ├── generated/
│   │   └── virtual_relationship_schema.py   # Generated base model (via backend.generate)
│   ├── virtual_relationship_schema.py       # VirtualRelationshipSchema implementation
│   ├── schema_branch.py                     # + validation & processing methods
│   ├── manager.py                           # + _virtual_relationship_names extension
│   └── __init__.py                          # + SchemaRoot/NodeSchema updates
├── infrahub/core/query/
│   └── virtual_relationship.py              # Cypher query for multi-hop traversal
├── infrahub/graphql/
│   ├── manager.py                           # + virtual relationship field generation
│   └── resolvers/
│       └── virtual_relationship.py          # VirtualRelationshipResolver
└── tests/
    ├── unit/core/schema/
    │   └── test_virtual_relationship.py     # Schema validation tests
    ├── functional/
    │   └── test_virtual_relationship.py     # Query resolution + GraphQL tests
    └── integration_docker/
        └── test_virtual_relationship.py     # Full stack tests (if needed)

frontend/app/
├── src/entities/nodes/object/utils/
│   ├── get-relationships-visible-in-tab.ts          # + virtual relationship visibility
│   └── get-relationships-visible-in-detailed-view.ts # (no changes needed — virtual rels are many-only)
├── src/entities/nodes/object/ui/object-details/
│   └── object-details-tabs.tsx              # + virtual relationship tab rendering
└── tests/
    └── e2e/
        └── virtual-relationships.spec.ts    # E2E tests for UI display
```

**Structure Decision**: Web application structure. Backend changes span schema layer, query layer, and GraphQL layer — all within existing directory structure. Frontend changes are minimal — extending existing tab visibility logic and adding an E2E test. No new directories needed beyond the new files listed above.

## Complexity Tracking

No constitution violations to justify.
