# Implementation Plan: Graph Path Traversal

**Branch**: `infp-1991-graph-path-traversal` | **Date**: 2026-03-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/infp-1991-graph-path-traversal/spec.md`

## Summary

Add a graph path traversal feature that allows users to select two infrastructure nodes and discover all paths connecting them through the graph. The backend uses Neo4j's native variable-length path matching with branch-aware edge validation. The frontend provides a visual representation of discovered paths. Exposed as a top-level GraphQL query following the `InfrahubSearchAnywhere` pattern.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 (frontend)
**Primary Dependencies**: FastAPI, Graphene (GraphQL), Neo4j async driver, React 19, TanStack React Query, react-aria-components, @xyflow/react, dagre
**Storage**: Neo4j 5.28 (existing graph, no schema changes)
**Testing**: pytest (backend unit/functional), Vitest (frontend unit), Playwright (E2E)
**Target Platform**: Linux server (backend), Web browser (frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Path discovery < 5 seconds for graphs up to 100K nodes
**Constraints**: Must respect branch/temporal filtering; max 5 hops default; upper limit 20; parameterized Cypher only
**Scale/Scope**: Typical infrastructure graphs (1K-100K nodes), up to 10 paths returned per query. Dependencies query for fan-out discovery

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | PASS | Read-only feature; no schema modifications required |
| II. Branch-Safe by Default | PASS | Uses `Branch.get_query_filter_path()` for all traversal queries |
| III. Type Safety & Explicit Contracts | PASS | Frozen dataclasses for query results; GraphQL types defined; no `any` in frontend |
| IV. Test Discipline | PASS | Unit tests for query building, functional tests for path discovery, E2E for UI |
| V. Query Performance & Efficiency | PASS | Parameterized Cypher; depth limits prevent unbounded traversal; pagination via max_paths |
| VI. Security & Input Boundaries | PASS | Input validated via Pydantic/GraphQL types; parameterized queries prevent injection |
| VII. Simplicity & Maintainability | PASS | Follows existing Query class and GraphQL Field patterns; no new abstractions |

**Post-Phase 1 Re-check**: All gates still pass. `@xyflow/react` + `dagre` are the only new frontend dependencies, justified by the need for interactive graph visualization with zoom/pan/layout. Query class follows established patterns exactly.

## Project Structure

### Documentation (this feature)

```text
specs/infp-1991-graph-path-traversal/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research findings
├── data-model.md        # Query input/response structures
├── quickstart.md        # Getting started guide
├── contracts/           # GraphQL schema contract
│   └── graphql-schema.graphql
├── checklists/          # Validation checklists
│   └── requirements.md
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── infrahub/
│   ├── core/
│   │   └── query/
│   │       ├── path.py              # PathTraversalQuery + namespace/kind exclusion
│   │       └── dependencies.py      # DependencyQuery (fan-out discovery)
│   └── graphql/
│       ├── queries/
│       │   ├── path.py              # GraphQL types, resolvers for both queries
│       │   └── __init__.py          # exports
│       └── schema.py                # InfrahubBaseQuery registration
│   └── menu/
│       └── menu.py                  # Navigation menu entry
└── tests/
    └── unit/core/
        └── test_path_traversal_query.py

frontend/app/
├── src/
│   ├── entities/
│   │   └── path-traversal/
│   │       ├── domain/
│   │       │   ├── path-traversal.query-keys.ts
│   │       │   ├── path-traversal.query.ts
│   │       │   ├── get-path-traversal.ts
│   │       │   ├── get-dependencies.ts
│   │       │   └── dependencies.query.ts
│   │       └── ui/
│   │           ├── path-traversal-page.tsx   # Main page with Path/Dependencies modes
│   │           ├── path-flow-graph.tsx       # React Flow graph visualization
│   │           ├── infra-node.tsx            # Custom node with tooltips, context menu
│   │           ├── path-edge.tsx             # Custom edge with glow animation
│   │           ├── node-selector.tsx         # Path mode: source + destination pickers
│   │           ├── node-picker.tsx           # Kind-first search or UUID input
│   │           ├── dependency-selector.tsx   # Dependencies mode: source + target kinds
│   │           └── utils.ts                 # Colors, formatting, hidden namespaces
│   ├── pages/
│   │   └── path-traversal/index.tsx
│   └── app/router.tsx                       # Route registration
```

**Structure Decision**: Follows the existing web application layout with Feature-Sliced Design for the frontend. Backend additions mirror existing query and GraphQL patterns exactly. Two new frontend dependencies: `@xyflow/react` for graph visualization and `dagre` for hierarchical layout computation.

## Complexity Tracking

| New dependency: @xyflow/react | Interactive graph visualization with zoom/pan/layout needed for path display | Custom SVG rejected because it requires reimplementing zoom, pan, node interaction, and layout from scratch |
| New dependency: dagre | Hierarchical layout for source-to-destination path rendering | Manual positioning rejected because paths need automatic layout that adapts to varying depths |
