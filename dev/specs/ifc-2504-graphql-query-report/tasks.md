# Tasks: GraphQL Query Report Introspection

**Input**: Design documents from `specs/ifc-2504-graphql-query-report/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Component tests are explicitly required by the spec (FR-005, edge case section). Included below.

**Organization**: Tasks are grouped by phase. Both user stories (P1 and P2) share a single implementation — they differ only in which test scenarios they cover. Foundation phase is the implementation; user story phases are the tests.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files or independent functions)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Setup

**Purpose**: Verify project structure is ready.

This feature is purely additive to an existing backend. No new dependencies, no new schema nodes, no project initialization required. The directory `backend/infrahub/graphql/queries/` already exists.

- [x] T001 Confirm `backend/infrahub/graphql/queries/` exists and locate the `InfrahubStatus` pattern in `backend/infrahub/graphql/queries/status.py` for reference

---

## Phase 2: Foundation (Blocking Prerequisites)

**Purpose**: Implement the resolver and wire it into the GraphQL schema. MUST complete before any test can pass.

**⚠️ CRITICAL**: No user story test work can begin until this phase is complete.

- [x] T002 Create `backend/infrahub/graphql/queries/graphql_query_report.py` — define `GraphQLQueryReport(ObjectType)` with `targets_unique_nodes = Field(Boolean, required=True, description=...)`, the async resolver `resolve_graphql_query_report(root, info, query)` that accesses `info.context` for branch, calls `registry.schema.get_schema_branch`, instantiates `InfrahubGraphQLQueryAnalyzer`, catches `GraphQLSyntaxError` on construction and raises `GraphQLError`, checks `analyzer.is_valid` and raises `GraphQLError` on failure, and returns `{"targets_unique_nodes": analyzer.query_report.only_has_unique_targets}`, and the `InfrahubGraphQLQueryReport = Field(GraphQLQueryReport, query=String(required=True, ...), resolver=resolve_graphql_query_report, required=True)` export
- [x] T003 [P] Add `from .graphql_query_report import InfrahubGraphQLQueryReport` import and `"InfrahubGraphQLQueryReport"` to `__all__` in `backend/infrahub/graphql/queries/__init__.py`
- [x] T004 [P] Add `from .queries import ..., InfrahubGraphQLQueryReport` import and `InfrahubGraphQLQueryReport = InfrahubGraphQLQueryReport` class attribute to `InfrahubBaseQuery` in `backend/infrahub/graphql/schema.py`

**Checkpoint**: `InfrahubGraphQLQueryReport` is visible in the root GraphQL schema. T003 and T004 can run in parallel after T002 completes.

---

## Phase 3: User Story 1 — Validate Query Before Defining Artifact (Priority: P1) 🎯 MVP

**Goal**: Users can submit any GraphQL query string and receive an accurate `targets_unique_nodes` boolean.

**Independent Test**: Execute `InfrahubGraphQLQueryReport(query: "...")` via GraphQL and verify the field returns the correct boolean for queries with and without unique filters.

### Component Tests for User Story 1

- [x] T005 [P] [US1] Write `test_targets_unique_nodes_true_with_ids_filter` in `backend/tests/component/graphql/queries/test_graphql_query_report.py` — use `car_person_schema` fixtures + `prepare_graphql_params`, execute the `InfrahubGraphQLQueryReport` query with a query string that uses a required `ids` argument, assert response `data.InfrahubGraphQLQueryReport.targets_unique_nodes == True`
- [x] T006 [P] [US1] Write `test_targets_unique_nodes_false_no_filter` in `backend/tests/component/graphql/queries/test_graphql_query_report.py` — execute with a query string that returns all nodes of a type without any unique filter, assert `targets_unique_nodes == False`
- [x] T007 [P] [US1] Write `test_targets_unique_nodes_true_with_uniqueness_constraint` in `backend/tests/component/graphql/queries/test_graphql_query_report.py` — execute with a query that uses a field matching the model's uniqueness constraints as a required argument, assert `targets_unique_nodes == True`
- [x] T008 [P] [US1] Write `test_branch_context_resolved_automatically` in `backend/tests/component/graphql/queries/test_graphql_query_report.py` — verify the query executes correctly without a branch argument in the query string itself (branch is resolved from request context)

**Checkpoint**: User Story 1 is fully functional — `InfrahubGraphQLQueryReport` returns correct results for all valid query inputs.

---

## Phase 4: User Story 2 — Debug Unexpected Full Regenerations + Error Edge Cases (Priority: P2)

**Goal**: Users receive explicit errors for invalid inputs (empty string, malformed GraphQL, non-existent types) rather than silent incorrect results.

**Independent Test**: Submit invalid query strings to `InfrahubGraphQLQueryReport` and confirm each returns a GraphQL error (not a null result or `false`).

### Component Tests for User Story 2 + FR-005 Edge Cases

- [x] T009 [P] [US2] Write `test_error_on_empty_query_string` in `backend/tests/component/graphql/queries/test_graphql_query_report.py` — execute `InfrahubGraphQLQueryReport(query: "")`, assert response contains a GraphQL error and `data` is null or absent
- [x] T010 [P] [US2] Write `test_error_on_invalid_graphql_syntax` in `backend/tests/component/graphql/queries/test_graphql_query_report.py` — execute with `query: "not valid graphql {"`, assert response contains a GraphQL error
- [x] T011 [P] [US2] Write `test_error_on_nonexistent_node_type` in `backend/tests/component/graphql/queries/test_graphql_query_report.py` — execute with a syntactically valid query referencing a type that does not exist in the current schema (e.g. `{ NonExistentType123 { id } }`), assert response contains a GraphQL error

**Checkpoint**: All error edge cases return explicit GraphQL errors. Both user stories are independently verifiable.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Changelog, formatting, and lint compliance.

- [x] T012 Create changelog fragment `changelog/IFC-2504.added.md` with content: `Added InfrahubGraphQLQueryReport introspection query to report whether a GraphQL query targets unique nodes for artifact regeneration.`
- [x] T013 [P] Run `uv run invoke format` from repo root and fix any formatting issues in modified files
- [x] T014 [P] Run `uv run invoke lint` from repo root and fix any ruff or mypy errors in modified files
- [x] T015 Run `uv run pytest backend/tests/component/graphql/queries/test_graphql_query_report.py -v` and confirm all tests pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundation)**: Depends on Phase 1 — **BLOCKS all test phases**
  - T002 must complete first
  - T003 and T004 can run in parallel after T002
- **Phase 3 (US1 tests)**: Depends on Phase 2 completion
- **Phase 4 (US2 tests)**: Depends on Phase 2 completion — can run in parallel with Phase 3
- **Phase 5 (Polish)**: Depends on all test phases passing

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependency on US2
- **US2 (P2)**: Can start after Phase 2 — no dependency on US1

### Parallel Opportunities

- T003 and T004 can run in parallel (different files, both depend only on T002)
- All test tasks within Phase 3 (T005–T008) can be written in parallel (different test functions, same file)
- All test tasks within Phase 4 (T009–T011) can be written in parallel
- Phase 3 and Phase 4 can be worked in parallel after Phase 2 completes
- T013 and T014 (format and lint) can run in parallel

---

## Parallel Example: Phase 2

```bash
# T002 must complete first (single file creation):
Task: "Create backend/infrahub/graphql/queries/graphql_query_report.py"

# Then T003 and T004 run in parallel:
Task: "Edit backend/infrahub/graphql/queries/__init__.py"
Task: "Edit backend/infrahub/graphql/schema.py"
```

## Parallel Example: User Story 1 Tests

```bash
# All can run in parallel (different test functions):
Task: "test_targets_unique_nodes_true_with_ids_filter"
Task: "test_targets_unique_nodes_false_no_filter"
Task: "test_targets_unique_nodes_true_with_uniqueness_constraint"
Task: "test_branch_context_resolved_automatically"
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Complete Phase 1: Setup (trivial)
2. Complete Phase 2: Foundation — create and wire the resolver
3. Complete Phase 3: US1 tests — verify happy path
4. **STOP and VALIDATE**: Run `pytest backend/tests/component/graphql/queries/test_graphql_query_report.py -v`
5. Feature is usable

### Incremental Delivery

1. Phase 1 + Phase 2 → Query is registered and accessible
2. Phase 3 → Happy path validated (US1 complete)
3. Phase 4 → Error handling validated (US2 + edge cases complete)
4. Phase 5 → Ready for PR

---

## Notes

- All test tasks write into the same new file `backend/tests/component/graphql/queries/test_graphql_query_report.py` — coordinate if working in parallel
- Key fixture to use: `car_person_schema` (provides `TestCar` with known uniqueness constraints), `prepare_graphql_params`, `db`, `default_branch`
- The `InfrahubGraphQLQueryReport` query must be executed through the full GraphQL stack (via `graphql()` or HTTP client) in component tests, not by calling the resolver directly
- Refer to `backend/tests/component/graphql/queries/test_status.py` for the exact test invocation pattern
