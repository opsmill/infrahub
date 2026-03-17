# Tasks: Virtual Relationships

**Input**: Design documents from `/specs/infp-313-virtual-relationships/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Test tasks are included as this feature introduces a new schema construct, query pattern, and UI surface area. Tests are essential for correctness given the branch-aware, multi-hop traversal complexity.

**Organization**: Tasks are grouped by user story. US1 (Define) and US2 (Query) are combined into a single MVP phase since querying is meaningless without definition and vice versa.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Schema model definition and generation infrastructure

- [x] T001 Create `VirtualRelationshipSchema` model definition for code generation in backend/infrahub/core/schema/definitions/virtual_relationship_schema.py — define fields: name, label, description, path, peer, order_weight with types and constraints matching data-model.md
- [x] T002 Run `uv run invoke backend.generate` to generate backend/infrahub/core/schema/generated/virtual_relationship_schema.py base model
- [x] T003 Create `VirtualRelationshipSchema` implementation class in backend/infrahub/core/schema/virtual_relationship_schema.py — extend generated base with methods: `get_path_segments()` (split path on `__`), `get_peer_kind()` (resolve final kind from path), validation helpers

**Checkpoint**: VirtualRelationshipSchema model exists and can be instantiated with valid field values

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Integrate virtual relationships into the schema layer so they can be defined, loaded, and validated

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Add `virtual_relationships: list[VirtualRelationshipSchema]` field to `GeneratedBaseNodeSchema` / `BaseNodeSchema` in backend/infrahub/core/schema/generated/base_node_schema.py (via schema definitions) and regenerate
- [x] T005 Add `virtual_relationships: list[VirtualRelationshipSchema]` to `NodeExtensionSchema` / `BaseNodeExtensionSchema` in backend/infrahub/core/schema/__init__.py to support schema extensions
- [x] T006 Update `SchemaRoot` YAML/JSON loading to parse `virtual_relationships` key on nodes, generics, and extensions in backend/infrahub/core/schema/__init__.py
- [x] T007 Implement path validation in `SchemaBranch` — add `validate_virtual_relationships()` method in backend/infrahub/core/schema/schema_branch.py that walks each path segment against the schema graph, validates segment count (2-10), checks for circular references, and verifies name uniqueness against attributes and relationships
- [x] T008 Register `validate_virtual_relationships()` in `SchemaBranch.process_validate()` in backend/infrahub/core/schema/schema_branch.py
- [x] T009 Implement `process_virtual_relationships()` in `SchemaBranch` in backend/infrahub/core/schema/schema_branch.py — derive and set `peer` kind from path, generate labels if not provided. Register in `process_pre_validation()`
- [x] T010 Add virtual relationship names to `SchemaManager._virtual_relationship_names` tracking or add a parallel mechanism for user-defined virtual relationships in backend/infrahub/core/schema/manager.py
- [x] T011 Write unit tests for schema validation in backend/tests/unit/core/schema/test_virtual_relationship_schema.py — test: valid path parsing, invalid path segment rejection, path too short/long, name conflicts with attributes/relationships, circular reference detection, peer kind derivation

**Checkpoint**: Foundation ready — schemas with virtual_relationships can be loaded and validated. Invalid paths are rejected with clear errors.

---

## Phase 3: User Story 1+2 — Define & Query Virtual Relationships (Priority: P1) MVP

**Goal**: Schema designers can define virtual relationships in YAML, and users can query them via GraphQL to retrieve target nodes through multi-hop traversal.

**Independent Test**: Load a schema with a virtual relationship definition (e.g., Device with `all_interfaces` via `bays__line_cards__modules__interfaces`), create matching data, and verify the GraphQL query returns all target nodes.

### Implementation

- [x] T012 [US1] Create `VirtualRelationshipGetPeersQuery` Cypher query class in backend/infrahub/core/query/virtual_relationship.py — implement multi-hop traversal using parameterized path segments with relationship identifier matching, branch-aware filtering via `all(r IN relationships(path) WHERE branch_filter)`, `reduce()` for branch_level scoring, `DISTINCT` deduplication, and `SKIP`/`LIMIT` pagination
- [x] T013 [US1] Create `VirtualRelationshipCountQuery` Cypher query class in backend/infrahub/core/query/virtual_relationship.py — same traversal as T012 but returns `count(DISTINCT target)` only
- [x] T014 [US2] Create `VirtualRelationshipResolver` in backend/infrahub/graphql/resolvers/virtual_relationship.py — implement `resolve()` method that: extracts fields from GraphQL info, builds path segment identifiers from schema, executes `VirtualRelationshipGetPeersQuery` and `VirtualRelationshipCountQuery`, returns `NestedPaginated` response structure (count + edges with node and node_metadata, no properties)
- [x] T015 [US2] Extend `GraphQLSchemaManager.generate_object_types()` in backend/infrahub/graphql/manager.py — in Pass 4 (relationship field addition), iterate `node_schema.virtual_relationships` and add fields using `NestedPaginated{peer_kind}` type with `VirtualRelationshipResolver` and generated filters from the target kind
- [x] T016 [US2] Generate filters for virtual relationship fields in backend/infrahub/graphql/manager.py — call existing `generate_filters(schema=peer_schema, top_level=False)` and attach as kwargs on the graphene field, consistent with many-cardinality relationship filter generation
- [x] T017 [US1] Write functional test: load schema with virtual relationships, create test data (Device → Bays → LineCards → Modules → Interfaces), query via GraphQL and verify correct interfaces returned in backend/tests/functional/virtual_relationship/test_virtual_relationship.py
- [x] T018 [US1] Write functional test: verify schema validation rejects invalid paths (nonexistent segment, too short, too long, circular) in backend/tests/functional/virtual_relationship/test_virtual_relationship.py
- [x] T019 [US2] Write functional test: verify filtering on virtual relationship results — filtering implemented via NodeManager.query with combined ID + attribute filters in backend/tests/functional/virtual_relationship/test_virtual_relationship.py
- [x] T020 [US2] Write functional test: verify pagination (offset/limit) on virtual relationship results in backend/tests/functional/virtual_relationship/test_virtual_relationship.py
- [x] T021 [US2] Write functional test: verify empty collection returned (not error) when path resolves to zero nodes in backend/tests/functional/virtual_relationship/test_virtual_relationship.py
- [x] T022 [US1] Write functional test: verify deduplication when same target is reachable via multiple intermediate paths in backend/tests/functional/virtual_relationship/test_virtual_relationship.py
- [x] T023 [US2] Write functional test: verify branch-aware resolution — create virtual relationship data on a branch, query on branch vs main, verify different results in backend/tests/functional/virtual_relationship/test_virtual_relationship.py
- [ ] T023a [US2] Write functional test: verify permission filtering — virtual relationship excludes target nodes the user cannot access (FR-008) — requires RBAC fixture setup, deferred to integration tests
- [ ] T023b [US2] Write functional test: verify branch merge behavior — requires merge workflow with prefect, deferred to integration_docker tests

**Checkpoint**: Virtual relationships can be defined in schema YAML and queried via GraphQL with filtering, pagination, deduplication, and branch-awareness. This is the MVP.

---

## Phase 4: User Story 3 — Browse Virtual Relationships in UI (Priority: P2)

**Goal**: Non-technical users can see virtual relationships as tabs on node detail pages and browse collected nodes without writing queries.

**Independent Test**: Navigate to a Device detail page in the UI, verify a virtual relationship tab appears with correct count and node list, and click through to a target node.

### Implementation

- [x] T024 [US3] Extend `getRelationshipsVisibleInTab()` in frontend/app/src/entities/nodes/object/utils/get-relationships-visible-in-tab.ts — add virtual relationships to the tab visibility logic, sourcing them from the schema's `virtual_relationships` list
- [x] T025 [US3] Update `ObjectDetailsTabs` in frontend/app/src/entities/nodes/object/ui/object-details/object-details-tabs.tsx — render virtual relationship tabs with count badges, visually distinguished from regular relationship tabs (e.g., with a computed/virtual indicator)
- [x] T026 [US3] Ensure `useObjectRelationships` hook and `getObjectRelationshipsFromApi` query builder in frontend/app/src/entities/nodes/relationships/ui/queries/ work for virtual relationship fields — the GraphQL field name should map directly since virtual relationships use the same `NestedPaginated` response format
- [x] T027 [US3] Update `RelationshipsButtons` in frontend/app/src/entities/nodes/object-item-details/action-buttons/relationships-buttons.tsx — suppress "Add relationship" button for virtual relationship tabs (they are read-only)
- [x] T028 [US3] Write Playwright E2E test in frontend/app/tests/e2e/virtual-relationships.spec.ts — navigate to a node with virtual relationships, verify tab appears with count, click tab, verify target nodes listed, click through to a target node detail page

**Checkpoint**: Virtual relationships are browsable in the UI with pagination and navigation.

---

## Phase 5: User Story 4 — Cross-Domain Impact Analysis (Priority: P2)

**Goal**: Validate that virtual relationships work across different node kinds and relationship types (e.g., device → interfaces → circuits → containers → services).

**Independent Test**: Define a virtual relationship that crosses domain boundaries, create test data spanning multiple node kinds, and verify the collected target nodes are correct.

### Implementation

- [x] T029 [US4] Write functional test: define a cross-domain virtual relationship (e.g., `ports__circuits__services` on Router) with test data spanning 4 node kinds, verify all reachable target nodes collected with deduplication in backend/tests/functional/virtual_relationship/test_virtual_relationship.py
- [x] T030 [US4] Write functional test: verify one-to-many fan-out at each hop — a router with 2 ports, each connected to different circuits/services including shared service, verify complete collection without duplicates in backend/tests/functional/virtual_relationship/test_virtual_relationship.py

**Checkpoint**: Cross-domain traversal proven to work. No new implementation code expected — this phase validates the mechanism built in Phase 3.

---

## Phase 6: User Story 5 — Bidirectional/Peer Traversal (Priority: P3)

**Goal**: Virtual relationships can traverse peer/lateral relationships (e.g., cable connections) in addition to hierarchical parent-child relationships.

**Independent Test**: Define a virtual relationship on Interface that traverses through a cable to the remote device, verify correct remote device returned.

### Implementation

- [x] T031 [US5] Verify and adjust `VirtualRelationshipGetPeersQuery` in backend/infrahub/core/query/virtual_relationship.py — ensure Cypher query handles bidirectional relationship directions correctly by using the `QueryArrows` system from `RelationshipSchema.get_query_arrows()` for each path segment, not just outbound arrows
- [x] T032 [US5] Update path validation in backend/infrahub/core/schema/schema_branch.py — ensure `validate_virtual_relationships()` correctly resolves peer kinds through bidirectional and inbound relationships, not only outbound
- [ ] T033 [US5] Write functional test: bidirectional cable traversal — requires Generic schema with DcimEndpoint/Connector pattern, deferred to integration tests
- [ ] T034 [US5] Write functional test: empty cable result — deferred with T033

**Checkpoint**: Bidirectional/peer traversal works. Virtual relationships support all relationship direction types.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, edge case hardening, and performance validation

- [x] T035 [P] Add user documentation for virtual relationships in docs/docs/topics/schema/ — document YAML definition format, path notation, GraphQL query examples, and limitations
- [x] T036 [P] Add changelog fragment in changelog/ for the virtual relationships feature
- [ ] T037 [P] Write functional test: verify schema change handling — deferred to integration tests (requires schema reload mid-test)
- [ ] T037a [P] Add benchmark test — deferred (requires large dataset generation and benchmark infrastructure)
- [x] T039 Run `uv run invoke format` and `uv run invoke lint` to ensure all new backend code passes formatting and linting
- [x] T040 Run `cd frontend/app && npm run biome:fix` to ensure all new frontend code passes formatting and linting
- [x] T041 Quickstart validation — feature manually verified against running server with bundle-dc schemas

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (T001-T003) — BLOCKS all user stories
- **US1+US2 (Phase 3)**: Depends on Phase 2 — core MVP
- **US3 (Phase 4)**: Depends on Phase 3 (needs GraphQL fields to exist) — can run in parallel with Phase 5
- **US4 (Phase 5)**: Depends on Phase 3 (tests only, no new code) — can run in parallel with Phase 4
- **US5 (Phase 6)**: Depends on Phase 3 — may require query adjustments
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1+US2 (P1)**: Can start after Phase 2 — no dependencies on other stories
- **US3 (P2)**: Requires US1+US2 complete (GraphQL fields must exist for frontend to query)
- **US4 (P2)**: Requires US1+US2 complete (tests validate existing mechanism)
- **US5 (P3)**: Requires US1+US2 complete (may need Cypher query adjustments for bidirectional)

### Within Each Phase

- Cypher query classes (T012-T013) before resolver (T014)
- Resolver (T014) before GraphQL field generation (T015-T016)
- All implementation before functional tests
- Frontend visibility logic (T024) before tab rendering (T025)

### Parallel Opportunities

- T012 and T013 (Cypher query classes) can run in parallel
- T017-T023 (functional tests) can run in parallel after T012-T016 complete
- T024-T027 (frontend tasks) are sequential but Phase 4 can run in parallel with Phase 5
- T029-T030 (cross-domain tests) can run in parallel
- T035-T038 (polish tasks) can all run in parallel

---

## Parallel Example: Phase 3 (MVP)

```bash
# Step 1: Cypher queries (parallel)
Task: "T012 - VirtualRelationshipGetPeersQuery in backend/infrahub/core/query/virtual_relationship.py"
Task: "T013 - VirtualRelationshipCountQuery in backend/infrahub/core/query/virtual_relationship.py"

# Step 2: Resolver + GraphQL (sequential after Step 1)
Task: "T014 - VirtualRelationshipResolver"
Task: "T015 - GraphQL field generation"
Task: "T016 - Filter generation"

# Step 3: Tests (parallel after Step 2)
Task: "T017 - Schema + data + query test"
Task: "T018 - Validation rejection test"
Task: "T019 - Filter test"
Task: "T020 - Pagination test"
Task: "T021 - Empty result test"
Task: "T022 - Deduplication test"
Task: "T023 - Branch-aware test"
```

---

## Implementation Strategy

### MVP First (Phase 1-3 Only)

1. Complete Phase 1: Setup (schema model)
2. Complete Phase 2: Foundational (schema integration + validation)
3. Complete Phase 3: US1+US2 (define + query)
4. **STOP and VALIDATE**: Load a schema with virtual relationships, create data, query via GraphQL
5. Deploy/demo if ready — this delivers the core value proposition

### Incremental Delivery

1. Phase 1-3 → Schema definition + GraphQL queries work (MVP)
2. Phase 4 → UI browsing works (non-technical users unblocked)
3. Phase 5 → Cross-domain validation (confidence in mechanism)
4. Phase 6 → Peer/bidirectional traversal (cable connections work)
5. Phase 7 → Documentation, edge cases, polish

### Parallel Team Strategy

With multiple developers after Phase 2:

- Developer A: Phase 3 backend (Cypher + resolver + GraphQL)
- Developer B: Phase 3 tests (once backend tasks complete)
- Then: Developer A on Phase 6, Developer B on Phase 4, both can work Phase 5 tests

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US1 and US2 are combined in Phase 3 because they are co-dependent P1 stories
- US4 (cross-domain) is test-only — no new implementation code expected
- Virtual relationships use existing `NestedPaginated` GraphQL wrappers — no new GraphQL types needed
- The existing hierarchy multi-hop query pattern (`[:IS_RELATED*2..N]` with `reduce()`) is the foundation for the Cypher query
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
