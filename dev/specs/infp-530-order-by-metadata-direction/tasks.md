---
description: "Task list for schema-level order_by for node metadata and direction"
---

# Tasks: Schema-level `order_by` for node metadata and direction

**Input**: Design documents from `dev/specs/infp-530-order-by-metadata-direction/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Tests are REQUIRED. Constitution Principle IV (Test Discipline) mandates tests for every feature, written before or alongside implementation. New backend behavior gets component-level tests; the parser gets unit tests.

**Organization**: Tasks are grouped by user story. US1 is the MVP — once US1 lands, the customer's blocking pain is resolved. US2 piggybacks on US1's direction propagation and is mostly verification. US3 hardens the validator.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no in-flight dependencies)
- **[Story]**: User story label — `[US1]`, `[US2]`, or `[US3]`. Setup/Foundational/Polish phases carry no story label.

## Path Conventions

- Backend source: `backend/infrahub/`
- Backend tests: `backend/tests/unit/`, `backend/tests/component/`
- Changelog: `changelog/`
- Spec: `dev/specs/infp-530-order-by-metadata-direction/`

---

## Phase 1: Setup

**Purpose**: Confirm baseline before changes. No new project scaffolding required — feature lives entirely inside the existing backend.

- [X] T001 Run baseline unit + targeted component tests (`uv run invoke backend.test-unit` and `uv run pytest -x backend/tests/component/core/schema_manager/test_manager_schema.py backend/tests/component/core/test_node_get_list_query.py`); record any pre-existing failures so they aren't attributed to this branch.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Reserve the `node_metadata` name and stand up the central parser + typed entry model. All user-story work consumes these.

**⚠️ CRITICAL**: No user story work may begin until T002–T005 are complete.

- [X] T002 [P] Add the literal `"node_metadata"` to `RESERVED_ATTR_REL_NAMES` in `backend/infrahub/core/constants/__init__.py` (the list defined around lines 28–48). Do not modify `RESERVED_ATTR_GEN_NAMES`. No code comment referencing the spec or ticket.
- [X] T003 [P] Create new module `backend/infrahub/core/schema/order_by.py` that defines:
  - Frozen dataclass `ParsedOrderByEntry` with fields `raw: str`, `kind: OrderByTargetKind`, `direction: OrderDirection`, `schema_path: SchemaAttributePath | None`, `metadata_field: OrderByMetadataField | None`, plus a `target_key` property (see `data-model.md`).
  - String enums `OrderByTargetKind` (`ATTRIBUTE`, `RELATIONSHIP_ATTRIBUTE`, `METADATA`) and `OrderByMetadataField` (`CREATED_AT="created_at"`, `UPDATED_AT="updated_at"`).
  - `parse_order_by_entry(entry: str, node_schema) -> ParsedOrderByEntry` that recognizes the six grammar shapes in `contracts/grammar.md`. Raise `ValueError` with messages matching the templates in `contracts/errors.md` on malformed input; resolve attribute / relationship-attribute paths via the existing `node_schema.parse_schema_path()` helper.
  - Reuse `OrderDirection` from `infrahub.core.constants` and `METADATA_CREATED_AT` / `METADATA_UPDATED_AT` literals where appropriate.
- [X] T004 [P] Create `backend/tests/unit/core/schema/test_order_by_parser.py` with parametrized cases covering: all six grammar shapes (with and without direction); implicit-ascending default; rejection of malformed direction tokens (`__descending`, `__ASC`, empty tail); rejection of unsupported metadata field (`node_metadata__created_by`); rejection of empty string. Each case asserts on `kind`, `direction`, and `target_key`.
- [X] T005 [P] Add a reserved-name component test to `backend/tests/component/core/schema_manager/test_manager_schema.py`: loading a schema whose `NodeSchema.attributes` or `NodeSchema.relationships` contains an item named `node_metadata` raises the standard `SchemaNotValidError` and the message includes the offending node kind plus the literal `'node_metadata'` and the word "reserved".

**Checkpoint**: Parser and reserved name are in place. User-story phases can now proceed in parallel.

---

## Phase 3: User Story 1 — Default newest-first ordering on a relationship list (Priority: P1) 🎯 MVP

**Goal**: Schema authors can declare `order_by: ["node_metadata__created_at__desc"]` (and the rest of the new grammar) and see newest-first results consistently across top-level listings, relationship-peer listings, and hierarchy listings — including the default-ascending behavior when no direction suffix is provided. This is the customer's blocking pain.

**Independent Test**: Per `spec.md` User Story 1 Independent Test — define `Documentation.Note` with `order_by: ["node_metadata__created_at__desc"]`, attach to a `Documentation.Article` parent, fetch through API and confirm newest-first across all three paths; reload with `order_by: ["node_metadata__created_at"]` and confirm oldest-first; verify regular-attribute direction works identically.

### Tests for User Story 1

> Write these tests FIRST; they MUST FAIL before implementation in T012–T018.

- [X] T006 [P] [US1] Add to `backend/tests/component/core/test_node_get_list_query.py` a parametrized test `test_NodeGetListQuery_order_by_metadata_with_direction` covering `order_by` values `node_metadata__created_at__desc`, `node_metadata__created_at`, `node_metadata__updated_at__desc`. Build three nodes with controlled `created_at` / `updated_at` and assert the returned UUID order. Add a separate test that asserts the UUID tiebreaker stabilizes ordering when two nodes share the same `created_at`.
- [X] T007 [P] [US1] Add to (or create) `backend/tests/component/core/test_relationship_get_list_query.py` a test `test_RelationshipGetListQuery_order_by_metadata_with_direction` exercising the same `order_by` values on the peer schema; assert peer UUID order and tiebreaker stability.
- [X] T008 [P] [US1] Add to (or create) `backend/tests/component/core/test_node_get_hierarchy_query.py` a test `test_NodeGetHierarchyQuery_order_by_metadata_with_direction` exercising the same `order_by` values on a hierarchical schema; assert child UUID order and tiebreaker stability.
- [ ] T009 [P] [US1] Add to `backend/tests/component/core/schema_manager/test_manager_schema.py` parametrized success cases for `validate_order_by`: each of the six grammar shapes (attribute + direction, attribute without direction, relationship-attribute + direction, relationship-attribute without direction, metadata + direction, metadata without direction) loads cleanly.
- [ ] T010 [P] [US1] Add to `backend/tests/component/graphql/metadata/test_graphql_query_metadata.py` a test that the schema-level `order_by: ["node_metadata__created_at__desc"]` is honored by the GraphQL relationship-peer field when no query-time `order` argument is provided, and is ignored entirely when an `order` argument is provided (replace-not-stack precedence).
- [ ] T011 [P] [US1] Add to `backend/tests/component/core/test_node_inheritance.py` (create if absent, otherwise the file holding `NodeInheritanceHandler` tests) a test that a generic declaring `order_by: ["node_metadata__created_at__desc"]` is inherited by a concrete kind that has not declared its own; and a test that renaming an attribute on the generic does not corrupt a metadata `order_by` entry.

### Implementation for User Story 1

- [ ] T012 [US1] Wire the parser into `SchemaBranch.validate_order_by()` in `backend/infrahub/core/schema/schema_branch.py` (currently lines 956–971). For each entry, call `parse_order_by_entry(entry, node_schema)`; surface its `ValueError` through the existing `SchemaNotValidError` aggregation. Keep the existing `validate_schema_path` call as the resolver for the attribute / relationship-attribute cases (the parser delegates path resolution to it).
- [X] T013 [US1] Update `NodeInheritanceHandler._update_order_by_for_renamed_attributes` in `backend/infrahub/core/schema/node_inheritance_handler.py` (around lines 104–141) to skip any entry whose parsed `kind == METADATA`. Reuse `parse_order_by_entry` to classify entries.
- [X] T014 [US1] In `backend/infrahub/core/query/node.py`, `NodeGetListQuery`: replace the inline `entry.split("__", maxsplit=1)` at line 2241 with `parse_order_by_entry(...)`. Thread the parsed `direction` into the `FieldAttributeRequirement(order_direction=...)` constructed at lines 2252–2262 (today hardcoded `OrderDirection.ASC` at lines 2249 and 2260). For entries with `kind == METADATA`, feed them through the existing `_add_created_metadata_subquery` / `_add_updated_metadata_subquery` pipeline (lines 1742+) by extending `_get_metadata_order_fields()` (lines 1699–1709) to merge schema-declared metadata entries on top of `requested_order.node_metadata` when `requested_order` is absent.
- [X] T015 [US1] In the same file, change the precedence at lines 1908–1917: when `self.requested_order is not None` and it carries any non-default content (metadata field set or `disable=True`), set `self.schema.order_by` to an effective empty list locally so it does not contribute to `_get_field_requirements`. The query-time argument MUST replace, not stack. Keep the UUID tiebreaker append at line 1953 in place; verify it fires whenever any ordering (schema or query-time) is in effect.
- [X] T016 [US1] In `backend/infrahub/core/query/relationship.py`, `RelationshipGetListQuery` around lines 953–979: replace the inline split with `parse_order_by_entry(entry, peer_schema)`. For `ATTRIBUTE` and `RELATIONSHIP_ATTRIBUTE` entries, continue using `build_subquery_order` but append the result as `f"{subquery_result_name} {parsed.direction.value}"` (today the direction is dropped). For `METADATA` entries, emit a new subquery analogous to `_add_created_metadata_subquery` / `_add_updated_metadata_subquery` but with `node_alias="peer"`; append the resulting alias plus direction. Append `"peer.uuid ASC"` as a final tiebreaker whenever any entry was emitted (currently the `peer.uuid` line at 979 is only the no-order-by fallback).
- [X] T017 [US1] In `backend/infrahub/core/query/node.py`, `NodeGetHierarchyQuery` around lines 2540–2565: apply the same changes as T016 — parser, per-entry direction in the outer `ORDER BY`, metadata subquery support for the `peer` alias, and `"peer.uuid ASC"` final tiebreaker whenever any entry was emitted. Extract the shared peer-metadata-subquery helper into a module-level function if both this and T016 would otherwise duplicate it (do not pre-extract; refactor after both call sites compile).
- [X] T018 [US1] If T016/T017 introduced a shared peer-metadata helper, place it in `backend/infrahub/core/query/subquery.py` next to `build_subquery_order`. Name it `build_subquery_order_metadata(node_alias, metadata_field, ...)`. Keep its signature compatible with the existing `build_subquery_order` return tuple `(subquery, params, result_alias)`.

**Checkpoint**: All US1 tests (T006–T011) pass. Quickstart steps 1–6 and step 8 succeed manually. Customer's blocking pain (newest-first DocumentationNote on parent detail) is resolved.

---

## Phase 4: User Story 2 — Schema designer chooses ascending or descending order on regular attributes (Priority: P2)

**Goal**: Descending order on regular attributes is honored across all three list paths and through multi-field mixed-direction `order_by` declarations. Implementation falls out of US1's direction propagation; this phase is dominated by verification.

**Independent Test**: Per `spec.md` User Story 2 Independent Test — schema with `order_by: ["name__value__desc"]` returns "alpha", "bravo", "charlie" in reverse alphabetical order without per-query ordering arguments.

### Tests for User Story 2

- [ ] T019 [P] [US2] Add to `backend/tests/component/core/test_node_get_list_query.py` a test `test_NodeGetListQuery_order_by_attribute_desc` with three nodes named alpha / bravo / charlie and `order_by: ["name__value__desc"]`; assert charlie / bravo / alpha order.
- [ ] T020 [P] [US2] Add the equivalent test to `backend/tests/component/core/test_relationship_get_list_query.py`.
- [ ] T021 [P] [US2] Add the equivalent test to `backend/tests/component/core/test_node_get_hierarchy_query.py`.
- [ ] T022 [P] [US2] Add a multi-field mixed-direction test to each of the three component files: `order_by: ["status__value__desc", "name__value"]` on a schema with `status` and `name` attributes. Verify primary sort is descending status, secondary sort is ascending name, across two pairs of nodes that share status.

### Implementation for User Story 2

- [ ] T023 [US2] Run T019–T022. If any test fails, investigate whether the multi-field direction propagation in `_get_field_requirements` (`backend/infrahub/core/query/node.py`) preserves the parsed direction per entry. If not, fix the propagation point and re-run. Do not change behavior for ascending entries — they must remain byte-identical to today.

**Checkpoint**: All US2 tests pass; descending and mixed-direction multi-field `order_by` is honored across the three paths. Quickstart step 7 succeeds.

---

## Phase 5: User Story 3 — Strict validation surfaces schema mistakes early (Priority: P3)

**Goal**: Schema-load-time errors for every malformed `order_by` entry, naming the offending node + entry + remediation per the templates in `contracts/errors.md` (FR-011).

**Independent Test**: Per `spec.md` User Story 3 Independent Test — loading a schema with each rejection case raises a descriptive error.

### Tests for User Story 3

- [ ] T024 [P] [US3] Add to `backend/tests/component/core/schema_manager/test_manager_schema.py` parametrized rejection cases for `validate_order_by`:
  - Unsupported metadata field (`node_metadata__created_by`, `node_metadata__deleted_at`).
  - Malformed direction (`name__value__descending`, `name__value__ASC`, `name__value__`).
  - Cardinality-many relationship in `order_by`.
  - Unresolvable attribute path (`nonexistent__value`).
  - Empty string entry (`""`).
  - Non-string entry (handled at Pydantic deserialization — verify the error surfaces).
  Each case asserts that the raised error message contains the node kind, the offending raw entry, and the remediation hint from `contracts/errors.md`.
- [ ] T025 [P] [US3] Add a duplicate-detection test to the same file:
  - Same target twice with identical directions (`["name__value", "name__value__asc"]`).
  - Same target twice with conflicting directions (`["name__value__asc", "name__value__desc"]`).
  - Same metadata target twice (`["node_metadata__created_at", "node_metadata__created_at__desc"]`).
  All three reject with a message containing both offending raw entries.

### Implementation for User Story 3

- [ ] T026 [US3] In `backend/infrahub/core/schema/schema_branch.py`, extend `validate_order_by()` to collect parsed entries into a dict keyed by `target_key` and raise on duplicate `target_key`. Error message template per `contracts/errors.md`: cites the node kind, both raw entries, and "Each target may appear at most once."
- [ ] T027 [US3] In `backend/infrahub/core/schema/order_by.py`, finalize the `parse_order_by_entry` error messages to match `contracts/errors.md` verbatim for each rejection case. The error MUST name the offending raw entry and a remediation hint specific to the failure. The error MUST NOT mention internal types (no `ParsedOrderByEntry`, `OrderByTargetKind`).
- [ ] T028 [US3] Confirm the cardinality-many rejection path lives in `validate_schema_path` (the existing validator already rejects `REL_MANY_*` for `order_by`) and that its error message satisfies FR-011. If the message does not name the offending entry, adjust the wrapping at `validate_order_by` so it does.

**Checkpoint**: All US3 tests pass; every rejection case in `contracts/errors.md` is exercised and yields an actionable, schema-author-facing error.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T029 [P] Run `uv run invoke backend.generate` to regenerate `backend/infrahub/core/schema/generated/` and `backend/infrahub/core/protocols.py`. Confirm the only diff is the field description (if updated) on `order_by` and any byproducts of the reserved-name change. Commit regenerated files as a separate logical change.
- [ ] T030 [P] Add a changelog fragment under `changelog/` using the Towncrier convention (`.feature.md` / `.fix.md` per project guideline; do not embed the Jira ticket ID in the file body). The fragment MUST describe (a) the new metadata + direction `order_by` syntax, (b) the precedence change (query-time replaces schema, no stacking), and (c) the new reserved name `node_metadata`.
- [ ] T031 [P] Run the manual `quickstart.md` walkthrough end-to-end (or codify it as a component test in `backend/tests/component/graphql/` that wires Steps 1–9 into a single test session). Confirm all nine steps produce the expected output.
- [ ] T032 [P] Run `uv run invoke format` and `uv run invoke lint` from the repo root. Address any reported issues. Do not add `# noqa` or `# type: ignore` without justification.
- [ ] T033 [P] Run the full backend unit suite `uv run invoke backend.test-unit` and the targeted component suites touched by this feature (`backend/tests/component/core/schema_manager/`, `backend/tests/component/core/test_node_get_list_query.py`, `backend/tests/component/core/test_relationship_get_list_query.py`, `backend/tests/component/core/test_node_get_hierarchy_query.py`, `backend/tests/component/graphql/metadata/`). All must pass.
- [ ] T034 Update user-facing documentation in `docs/` if the existing schema authoring pages reference `order_by`. Add the new grammar (metadata entries + direction suffix), the implicit-ascending default, and the precedence rule. If no existing page references `order_by`, do not create a new page — work from the documentation backlog separately.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: No dependencies.
- **Phase 2 (Foundational)**: Depends on Phase 1. Blocks every user-story phase. T002 and T003 are parallel (different files). T004 depends on T003. T005 depends on T002.
- **Phase 3 (US1, MVP)**: Depends on Phase 2. T012–T018 each depend on T003. T014/T015 are sequential (same file). T013 is parallel to T012. T016 is parallel to T014/T015 (different file). T017 is sequential with T014/T015 (same file). T018 is sequential with T016/T017.
- **Phase 4 (US2)**: Depends on Phase 3 (US2 implementation lives in US1's direction-propagation code). Verification-heavy.
- **Phase 5 (US3)**: Depends on Phase 2 (parser exists) and is independent of US1/US2 — the validator changes touch `schema_branch.py` and `order_by.py` only.
- **Phase 6 (Polish)**: Depends on all desired user-story phases.

### Within each user story

- Tests (T006–T011 for US1, T019–T022 for US2, T024–T025 for US3) MUST be written and MUST FAIL before the corresponding implementation tasks.
- Per-file edits must be sequential within the file; cross-file edits run in parallel.

### Parallel opportunities

- **Phase 2**: T004 and T005 run in parallel after T002+T003 land. T002 and T003 themselves can run in parallel (different files).
- **Phase 3**: T006, T007, T008, T009, T010, T011 are all parallel (different test files). T013, T016 are parallel with T014/T015 (different source files).
- **Phase 4**: T019–T022 all parallel (different test files).
- **Phase 5**: T024 and T025 are parallel (same test file but different parametrized blocks — coordinate via separate test functions).
- **Phase 6**: T029, T030, T031, T032 all parallel.

---

## Parallel Example: User Story 1 tests

```bash
# Launch all US1 test scaffolds in parallel (different files):
T006  backend/tests/component/core/test_node_get_list_query.py
T007  backend/tests/component/core/test_relationship_get_list_query.py
T008  backend/tests/component/core/test_node_get_hierarchy_query.py
T009  backend/tests/component/core/schema_manager/test_manager_schema.py
T010  backend/tests/component/graphql/metadata/test_graphql_query_metadata.py
T011  backend/tests/component/core/test_node_inheritance.py
```

## Parallel Example: User Story 1 cross-file implementation

```bash
# After T012 (validator) lands, these can proceed in parallel:
T013  backend/infrahub/core/schema/node_inheritance_handler.py
T014+T015 (sequential, same file)  backend/infrahub/core/query/node.py — NodeGetListQuery
T016  backend/infrahub/core/query/relationship.py
# T017 must wait for T014/T015 to finish (same file).
```

---

## Implementation Strategy

### MVP first (US1 only)

1. Finish Phase 1 + Phase 2.
2. Land Phase 3 (US1) — schema authors can declare `node_metadata__<field>__<direction>` and the customer's blocking case works.
3. Stop and validate via `quickstart.md` steps 1–6 and step 8. Demo to customer.

### Incremental delivery

1. Phase 1 + Phase 2 → reserved name + parser landed.
2. Phase 3 (US1) → MVP ships, customer unblocked.
3. Phase 4 (US2) → regular-attribute descending verified (mostly tests).
4. Phase 5 (US3) → validator hardened; previously-silent typos now fail fast at schema load.
5. Phase 6 → polish, changelog, codegen.

### Parallel team strategy

After Phase 2 completes, two developers can split:

- Dev A: Phase 3 (US1) — query paths.
- Dev B: Phase 5 (US3) — validator rejection cases. (Independent of Phase 3 because it touches schema_branch.py / order_by.py only.)
- Both regroup at Phase 4 (verification of US2 by either developer) and Phase 6.

---

## Notes

- `[P]` tasks edit different files. Two `[P]` tasks on the same file must not actually run concurrently.
- The descending behavior tests in Phase 4 will trivially pass if US1's direction propagation is correct. If any fail, treat them as bug reports against US1 implementation, not US2 design.
- Do not embed the Jira ticket ID (`INFP-530`) or any task ID in source code comments, docstrings, or test names — per `dev/rules/code-doc-style.md`. IDs go in commit messages, PR descriptions, and changelog fragments only.
- Commit after each task or logical group (per `dev/guidelines/git-workflow.md`).
