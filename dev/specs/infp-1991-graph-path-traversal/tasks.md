# Tasks: Graph Path Traversal

**Input**: Design documents from `/specs/infp-1991-graph-path-traversal/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install new dependencies and create directory scaffolding

- [x] T001 Install frontend dependencies: `cd frontend/app && npm install @xyflow/react dagre @types/dagre`
- [x] T002 [P] Create backend query module file `backend/infrahub/core/query/path.py` with module docstring and imports
- [x] T003 [P] Create backend GraphQL query module file `backend/infrahub/graphql/queries/path.py` with module docstring and imports
- [x] T004 [P] Create frontend feature directory structure `frontend/app/src/entities/path-traversal/` with `domain/` and `ui/` subdirectories

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core Cypher query class and GraphQL registration that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Implement `PathTraversalQuery` class in `backend/infrahub/core/query/path.py` — extend `Query` base class from `backend/infrahub/core/query/__init__.py`. Use `allShortestPaths` with variable-length `[:IS_RELATED*2..N]` matching. Apply `Branch.get_query_filter_path()` via `all(r IN relationships(path) WHERE ...)`. Accept `source_id`, `destination_id`, `max_depth` (default 20, translated to `max_depth * 2` edges), `max_paths` (default 10). Use `db.render_list_comprehension()` for Neo4j/Memgraph portability. Reference `NodeGetHierarchyQuery` in `backend/infrahub/core/query/node.py` for the pattern.
- [x] T006 Add typed result extraction method `get_paths()` to `PathTraversalQuery` in `backend/infrahub/core/query/path.py` — return frozen dataclasses `PathData`, `PathNodeData`, `PathRelationshipData` with fields matching `data-model.md` (id, kind, display_label for nodes; id, name, direction for relationships). Extract node metadata from path results, skip intermediate Relationship vertices, determine direction relative to traversal.
- [x] T007 Implement input validation in `PathTraversalQuery.__init__()` in `backend/infrahub/core/query/path.py` — validate `source_id != destination_id`, `1 <= max_depth <= 50`, `1 <= max_paths <= 100`. Raise `ValueError` with descriptive messages for invalid inputs.
- [x] T008 Define GraphQL response types in `backend/infrahub/graphql/queries/path.py` — create `PathNodeType(ObjectType)` with fields `id`, `kind`, `display_label`; `PathRelationshipType(ObjectType)` with `id`, `name`, `direction`; `PathResultType(ObjectType)` with `nodes`, `relationships`, `depth`; `PathTraversalResultType(ObjectType)` with `paths`, `source`, `destination`, `total_paths_found`. Follow the pattern in `backend/infrahub/graphql/queries/search.py`.
- [x] T009 Define GraphQL input type in `backend/infrahub/graphql/queries/path.py` — create `PathTraversalInput(InputObjectType)` with fields `source_id` (ID, required), `destination_id` (ID, required), `max_depth` (Int, default 20), `max_paths` (Int, default 10), `node_filter` (List of String), `relationship_filter` (List of String). Follow the pattern of other InputObjectType usages in the graphql layer.
- [x] T010 Implement `path_traversal_resolver` async function in `backend/infrahub/graphql/queries/path.py` — extract `GraphqlContext` from `info.context` for `db`, `branch`, `at`. Validate source and destination nodes exist using `NodeManager.get_one()`. Instantiate and execute `PathTraversalQuery`. Transform results to GraphQL response structure. Handle node-not-found with descriptive error. Export `InfrahubPathTraversal = Field(PathTraversalResultType, data=PathTraversalInput(required=True), resolver=path_traversal_resolver, required=True)`.
- [x] T011 Export `InfrahubPathTraversal` in `backend/infrahub/graphql/queries/__init__.py` — add import and add to `__all__` list
- [x] T012 Register `InfrahubPathTraversal` in `InfrahubBaseQuery` class in `backend/infrahub/graphql/schema.py` — add import and add field assignment following existing pattern

**Checkpoint**: Backend API is functional. `InfrahubPathTraversal` GraphQL query is available and returns path data. Can be tested via GraphiQL.

---

## Phase 3: User Story 1 - Query Path Between Two Nodes (Priority: P1) MVP

**Goal**: Users can query paths between two nodes via GraphQL and receive ordered sequences of nodes and relationships

**Independent Test**: Execute `InfrahubPathTraversal` GraphQL query with two known connected node UUIDs and verify response contains correct intermediate nodes and relationships in order

### Implementation for User Story 1

- [x] T013 [US1] Add edge case handling to `path_traversal_resolver` in `backend/infrahub/graphql/queries/path.py` — return empty paths list with `total_paths_found: 0` when no path exists (not an error). Return error when source or destination node not found. Return error when `source_id == destination_id`.
- [x] T014 [US1] Add unit tests for `PathTraversalQuery` Cypher generation in `backend/tests/unit/core/query/test_path.py` — test that generated Cypher includes `allShortestPaths`, branch filter parameters, depth limit, parameterized source/destination UUIDs. Test validation rejects same source/destination, out-of-range depth/paths. Follow test patterns in `backend/tests/unit/core/query/`.
- [x] T015 [US1] Add unit tests for GraphQL types and resolver in `backend/tests/unit/graphql/queries/test_path.py` — test `PathTraversalInput` validation, test response type construction, test resolver error handling for missing nodes. Follow test patterns in `backend/tests/unit/graphql/`.

**Checkpoint**: User Story 1 complete. Path traversal query works end-to-end via GraphQL. Returns correct paths with node/relationship metadata, handles all edge cases (no path, missing nodes, same node).

---

## Phase 4: User Story 2 - Visualize Path Results (Priority: P2)

**Goal**: Users see an interactive visual graph of path results using React Flow with dagre layout

**Independent Test**: Navigate to path traversal page, select two nodes, verify React Flow canvas renders nodes as labeled boxes connected by directed edges, with zoom/pan working

### Implementation for User Story 2

- [x] T016 [P] [US2] Create query key factory in `frontend/app/src/entities/path-traversal/domain/path-traversal.query-keys.ts` — export `pathTraversalKeys` object with `all`, `traverse(params)` methods following the pattern in existing `*.query-keys.ts` files
- [x] T017 [P] [US2] Create GraphQL fetch function in `frontend/app/src/entities/path-traversal/domain/get-path-traversal.ts` — build `InfrahubPathTraversal` query using `json-to-graphql-query`, accept `sourceId`, `destinationId`, optional `maxDepth`, `maxPaths`. Return typed `PathTraversalResponse`. Follow pattern in `frontend/app/src/entities/nodes/object/domain/get-objects.ts`.
- [x] T018 [US2] Create React Query hook in `frontend/app/src/entities/path-traversal/domain/path-traversal.query.ts` — export `useGetPathTraversal(params)` hook using `useQuery` with `pathTraversalKeys.traverse(params)` and the fetch function from T017. Follow pattern in existing `*.query.ts` files.
- [x] T019 [P] [US2] Create custom React Flow node component in `frontend/app/src/entities/path-traversal/ui/infra-node.tsx` — render infrastructure node as a styled box with `kind` as a subtitle and `displayLabel` as the main label. Use Tailwind classes. Accept `NodeProps` from `@xyflow/react`. Include source and target handles.
- [x] T020 [P] [US2] Create custom React Flow edge component in `frontend/app/src/entities/path-traversal/ui/path-edge.tsx` — render directed edge with arrow marker showing relationship `name` as label. Support `highlighted` vs `dimmed` state via data prop. Use `BaseEdge` and `EdgeLabelRenderer` from `@xyflow/react`.
- [x] T021 [US2] Create dagre layout utility in `frontend/app/src/entities/path-traversal/ui/path-flow-graph.tsx` — implement `getLayoutedElements(nodes, edges)` function that uses `dagre` to compute hierarchical left-to-right positions. Convert `PathTraversalResponse` to React Flow `Node[]` and `Edge[]` arrays. Create `PathFlowGraph` component wrapping `ReactFlow` with `nodeTypes` (infra-node) and `edgeTypes` (path-edge), `fitView`, and controls. Support multiple paths by rendering all path edges with the selected path highlighted.
- [x] T022 [US2] Create node selector component in `frontend/app/src/entities/path-traversal/ui/node-selector.tsx` — two search/select inputs for source and destination nodes. Use existing node search patterns (reference `InfrahubSearchAnywhere` or node list queries). Include a "Find Paths" button that triggers the query. Show loading state during query.
- [x] T023 [US2] Create path traversal page component in `frontend/app/src/entities/path-traversal/ui/path-traversal-page.tsx` — compose `NodeSelector` and `PathFlowGraph` components. Use `ResizablePanelGroup` for layout (selector panel + visualization panel). Show empty state when no query has been run. Show "No paths found" when query returns empty results. Show path count and allow selecting individual paths when multiple exist.
- [x] T024 [US2] Create route page in `frontend/app/src/pages/path-traversal/page.tsx` — wrap `PathTraversalPage` component. Register route in the application router (find router configuration and add entry).

**Checkpoint**: User Story 2 complete. Users can select two nodes, click "Find Paths", and see an interactive React Flow graph with labeled nodes and directed edges. Zoom, pan, and path selection work.

---

## Phase 5: User Story 3 - Filter Path Traversal by Node or Relationship Type (Priority: P3)

**Goal**: Users can constrain traversal to specific node kinds and relationship types

**Independent Test**: Execute path query with `nodeFilter: ["InfraDevice"]` and verify only paths through InfraDevice nodes are returned; execute with `relationshipFilter: ["interfaces"]` and verify only those relationship types are traversed

### Implementation for User Story 3

- [x] T025 [US3] Add node kind filtering to `PathTraversalQuery` in `backend/infrahub/core/query/path.py` — accept `node_filter: list[str]` parameter. When non-empty, add `WHERE all(n IN nodes(path) WHERE n.kind IN $node_filter OR n.uuid IN [$source_uuid, $target_uuid])` clause to Cypher query. Add `$node_filter` to params.
- [x] T026 [US3] Add relationship name filtering to `PathTraversalQuery` in `backend/infrahub/core/query/path.py` — accept `relationship_filter: list[str]` parameter. When non-empty, add filter on Relationship vertex `name` property along the path. Add `$relationship_filter` to params.
- [x] T027 [US3] Update `path_traversal_resolver` in `backend/infrahub/graphql/queries/path.py` — pass `node_filter` and `relationship_filter` from `PathTraversalInput` through to `PathTraversalQuery`. Validate filter values against schema registry (node kinds must exist, relationship names must exist).
- [x] T028 [US3] Add filter unit tests in `backend/tests/unit/core/query/test_path.py` — test Cypher generation includes node kind filter when provided, includes relationship filter when provided, omits filters when empty lists. Test that both filters work together.
- [x] T029 [US3] Add filter controls to node selector in `frontend/app/src/entities/path-traversal/ui/node-selector.tsx` — add multi-select dropdowns for "Node Kinds" and "Relationship Types". Populate options from schema (use existing schema query hooks). Pass selected filters to the GraphQL query. Collapsible "Advanced Filters" section to keep the UI clean by default.
- [x] T030 [US3] Update `get-path-traversal.ts` in `frontend/app/src/entities/path-traversal/domain/get-path-traversal.ts` — add `nodeFilter` and `relationshipFilter` optional parameters to the GraphQL query builder and the fetch function type signature.

**Checkpoint**: User Story 3 complete. Users can filter path traversal by node kind and relationship type from both GraphQL and the UI.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and cross-story improvements

- [ ] T031 [P] Add changelog fragment in `changelog/` — create Towncrier fragment describing the new Graph Path Traversal feature (user-facing description)
- [ ] T032 [P] Add user documentation in `docs/` — document the `InfrahubPathTraversal` GraphQL query with examples, parameters, and response format. Include UI screenshots/description of the path visualization page.
- [x] T033 Run `uv run invoke format` and `cd frontend/app && npm run biome:fix` — ensure all new code passes formatting and linting
- [x] T034 Run `uv run invoke lint` and verify zero lint errors in new files
- [ ] T035 Run full test suite: `uv run invoke backend.test-unit` and `cd frontend/app && npm run test` — verify no regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2)
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2) and User Story 1 (Phase 3) — needs working GraphQL query
- **User Story 3 (Phase 5)**: Depends on Foundational (Phase 2) — can run in parallel with US2 if desired
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 — no dependencies on other stories
- **User Story 2 (P2)**: Depends on US1 — needs the GraphQL query to exist and return data for visualization
- **User Story 3 (P3)**: Can start after Phase 2 — backend filtering is independent of visualization. Frontend filter UI (T029-T030) depends on US2 being complete.

### Within Each User Story

- Models/query classes before services/resolvers
- Backend before frontend (frontend consumes backend API)
- Core implementation before integration and edge cases

### Parallel Opportunities

- **Phase 1**: T002, T003, T004 can all run in parallel (different files)
- **Phase 2**: T008 and T009 can run in parallel (both in same file but independent types); T011 and T012 can run in parallel (different files)
- **Phase 4 (US2)**: T016, T017 in parallel; T019, T020 in parallel (different component files)
- **Phase 6**: T031, T032 in parallel (docs vs changelog)

---

## Parallel Example: User Story 2

```bash
# Launch domain layer tasks together:
Task: "Create query key factory in frontend/app/src/entities/path-traversal/domain/path-traversal.query-keys.ts"
Task: "Create GraphQL fetch function in frontend/app/src/entities/path-traversal/domain/get-path-traversal.ts"

# Launch custom component tasks together:
Task: "Create custom React Flow node component in frontend/app/src/entities/path-traversal/ui/infra-node.tsx"
Task: "Create custom React Flow edge component in frontend/app/src/entities/path-traversal/ui/path-edge.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test `InfrahubPathTraversal` GraphQL query via GraphiQL
5. Backend is usable via API even without frontend

### Incremental Delivery

1. Complete Setup + Foundational → Backend API scaffolding ready
2. Add User Story 1 → Test via GraphQL → Backend MVP complete
3. Add User Story 2 → Test UI visualization → Full feature usable
4. Add User Story 3 → Test filters → Feature complete with power-user capabilities
5. Polish → Documentation, linting, changelog → Ready for PR

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- The Cypher query in T005 is the most critical task — reference `NodeGetHierarchyQuery` in `backend/infrahub/core/query/node.py` lines 2311-2481 for the exact pattern
- React Flow requires `@xyflow/react` CSS import in the visualization component
