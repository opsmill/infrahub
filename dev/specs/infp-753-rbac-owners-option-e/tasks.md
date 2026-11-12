---
description: "Task list for owner and source metadata, Community side, storage option E"
---

# Tasks: Owner and source metadata, and extension points for ownership-based permissions (Community side), storage option E

**Input**: Design documents from `dev/specs/infp-753-rbac-owners-option-e/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: included. Each functional requirement of the spec has a check, and the constitution asks for tests with each feature.

**Organization**: tasks are grouped by user story, in the priority order of the spec. No task changes the frontend.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on a task that is not complete)
- **[Story]**: the user story of the task (US1 to US7)
- Each description names the file that the task changes

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: approvals, names and the test data that all later phases need.

- [ ] T001 Get approval for each governance gate of plan.md ("Post-Phase 1 re-check"), and the confirmation of a maintainer that E2E tests through the API meet principle IV of dev/constitution.md and that user story 7 needs no E2E test. Record the results in dev/specs/infp-753-rbac-owners-option-e/plan.md
- [ ] T002 Get the product decisions that the spec lists under "Decisions that product owes": the edition of the owner and source filters (Q-23), the audit of profile changes (D-6), the reference data set and the limits of the success criteria, and the origin node of E-15. Record each answer in dev/specs/infp-753-rbac-owners-option-e/spec.md
- [ ] T003 Get the decision of the engineering review on the rules that are not decided, and update dev/specs/infp-753-rbac-owners-option-e/spec.md and dev/specs/infp-753-rbac-owners-option-e/research.md with each answer: which pairs of owner changes conflict (FR-030, research R-9), the result of two writes at the same time (FR-032, research R-21), the depth limit of the walk to the parents and the result beyond it (E-16, research R-3), and the audit metadata of an owner change (FR-053). Phase 3 does not start before these decisions
- [ ] T004 Get the decision of the engineering review on the design for two branches that create the same `OwnerSet` vertex (research R-21), and record it in dev/specs/infp-753-rbac-owners-option-e/research.md. Phase 3 does not start before this decision
- [ ] T005 Hold the API review of the names in dev/specs/infp-753-rbac-owners-option-e/contracts/graphql-schema.graphql and dev/specs/infp-753-rbac-owners-option-e/contracts/object-file.md, and update both files with the names that the review fixes
- [ ] T006 [P] Create the packages `backend/infrahub/core/ownership/__init__.py`, `backend/tests/unit/core/ownership/__init__.py` and `backend/tests/component/core/ownership/__init__.py`
- [ ] T007 [P] Create the reference data set fixture (10,000 devices with 48 interfaces each, a location hierarchy 5 levels deep, 50 account groups) in backend/tests/query_benchmark/ownership/conftest.py
- [ ] T008 Measure SC-001 and SC-002 on the reference data set before any change, and record the numbers as "today" in dev/specs/infp-753-rbac-owners-option-e/measurements.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the storage of owner states and the read of stored states. All user stories need it.

**CRITICAL**: no user story work can start until this phase is complete.

- [ ] T009 Add the edge types `HAS_NO_OWNER`, `HAS_OWNER_SET`, `HAS_TARGET_OWNER_SET` and `HAS_OWNER_SOURCE` to `DatabaseEdgeType` in backend/infrahub/core/constants/database.py
- [ ] T010 Declare the `OwnerSet` and `NoOwner` vertices and the new edges in backend/infrahub/core/graph/schema.py, next to `GraphNodeRelationships` and `GraphAttributeRelationships` (data-model.md, "Graph structure")
- [ ] T011 Add a range index on `HAS_NO_OWNER(branch)` in backend/infrahub/core/graph/index.py, next to `owner_branch`
- [ ] T012 [P] Create `OwnerState` (`INHERIT`, `OWNERS`, `NO_OWNER`), `OwnerOrigin` (`SELF`, `PROFILE`, `TEMPLATE`, `PARENT`, `OBJECT`), `HolderKind`, `HolderKey` (`kind`, `attribute`, `identifier`, `direction`), `StoredOwnerState`, `StoredNodeOwnership`, `ResolvedOwnership` and `OwnerReference` as frozen dataclasses and enums in backend/infrahub/core/ownership/models.py
- [ ] T013 [P] Create the constants (UUID of the `NoOwner` vertex, depth limit of the parent walk, filter names) in backend/infrahub/core/ownership/constants.py
- [ ] T014 Write the query that reads the stored owner state of the node holder for a list of node IDs, with the branch and time filters, in backend/infrahub/core/ownership/queries.py. No edge is inherit, only `HAS_NO_OWNER` is no owner, one or more `HAS_OWNER` are those owners
- [ ] T015 Write the queries that set a holder to own owners, to no owner and to inherit in backend/infrahub/core/ownership/queries.py, with the edge changes of data-model.md ("State changes"). A write on a branch hides each owner edge that the branch inherits
- [ ] T016 Create the repository that runs the queries and returns frozen dataclasses in backend/infrahub/core/ownership/repository.py
- [ ] T017 Create the writer that applies a parsed owner input to one holder inside the transaction of the caller in backend/infrahub/core/ownership/writer.py
- [ ] T018 Create the input parser in backend/infrahub/core/ownership/input.py. It accepts an owner as `id`, or as `hfid` with `kind`. It refuses the whole input when an owner is not found, is not an account or an account group, has an unknown kind, has neither an ID nor a kind with an HFID, or has an HFID of the wrong length (FR-003)
- [ ] T019 [P] Write unit tests for the five refusal cases of FR-003 and for the three values of D-5 (key left out, `null`, `[]`) in backend/tests/unit/core/ownership/test_input.py
- [ ] T020 [P] Write component tests that set each state on a node on a branch and read it back on that branch and on the default branch in backend/tests/component/core/ownership/test_storage.py (FR-001, FR-002)
- [ ] T021 Take a lock for the node in every mutation that writes owners or sources, with `InfrahubMultiLock` of backend/infrahub/lock.py, in `InfrahubMutationMixin` of backend/infrahub/graphql/mutations/main.py (research R-21)
- [ ] T022 Run the spike before the first pull request. With plain Cypher queries on this storage and the reference data set, as the benchmark of 2026-11-09 did, measure SC-003 to SC-006, and measure SC-009 and SC-010 with a temporary check that reads the owners that apply. Decide how the owner filter meets SC-003 (research R-6), whether the `HAS_NO_OWNER(branch)` index brings the diff query to the cost of option B, and whether the lookup of an `OwnerSet` by its key needs an index. Record the numbers and the decisions in dev/specs/infp-753-rbac-owners-option-e/measurements.md
- [ ] T023 If the spike chose an index of the owners that apply, get approval for the new database structure, and add the tasks for its build, its update at each write and its rebuild to dev/specs/infp-753-rbac-owners-option-e/tasks.md before Phase 3 starts (research R-6)

**Checkpoint**: owner states can be stored and read for a node. User story work can start.

---

## Phase 3: User Story 1 - A platform team gives owners to many devices, and anyone filters by owner (Priority: P1)

**Goal**: several owners per node, inheritance through the parent, the owner filter, and owner changes in the diff, the merge and the activity log.

**Independent Test**: on 3,000 devices with 48 interfaces each, set owners on 1,000 devices, then filter by owner and by "no owner". Compare the counts and the owners that the API returns with the expected values.

### Tests for User Story 1

- [ ] T024 [P] [US1] Write unit tests for the order of sources of a node (own state, then parent; own owners stop the walk; "no owner" stops the walk) in backend/tests/unit/core/ownership/test_resolution.py
- [ ] T025 [P] [US1] Write component tests for the walk to the parents: Parent relationship, hierarchy parent, and a node with both (the Parent relationship wins), and a node at the depth limit and one level beyond it, with the result that the engineering review decided, in backend/tests/component/core/ownership/test_resolver.py (FR-004, D-3, E-16)
- [ ] T026 [P] [US1] Write GraphQL tests for scenarios 1 to 9 and 12 to 14 of user story 1 in backend/tests/component/graphql/metadata/test_graphql_node_owners.py, and a test that changes only the owners of a device and reads `updated_at` and `updated_by` of the device and of one interface (FR-053)
- [ ] T027 [P] [US1] Write component tests for the owner filter and the "no owner" filter with pagination and `count` in backend/tests/component/core/ownership/test_filter.py (FR-018 to FR-020)
- [ ] T028 [P] [US1] Write component tests that show an owner change in the diff with the display labels of the owners added and removed in backend/tests/component/core/diff/merge/test_ownership_diff.py. The diff of an owner change on a device lists one node, and the interfaces show the new owners at the next read (FR-006, FR-029)
- [ ] T029 [P] [US1] Write one merge scenario test for each case of FR-030 that needs node owners only (owners set, an owner added, an owner removed, "no owner" set, a node deleted on the branch, an owner group deleted on the branch, a parent changed on the branch) in backend/tests/component/core/diff/merge/test_ownership_merge.py. Each test reads on the branch, in the diff and on the default branch after the merge
- [ ] T030 [P] [US1] Write scenario tests for a rebase after both sides changed the same owners, and for two branches merged one after the other, in backend/tests/component/core/diff/merge/test_ownership_rebase.py (FR-030)
- [ ] T031 [P] [US1] Write a test that runs two first writes of owners on one node at the same time, and checks that the node has the complete state of one write, in backend/tests/component/core/ownership/test_concurrent_owner_writes.py (FR-032)
- [ ] T032 [P] [US1] Write a test that reads the activity log after a change of owners and again after a rename of the owner group, and compares the display labels of the owners, in backend/tests/component/graphql/queries/test_event_owner_changes.py (FR-031)
- [ ] T033 [P] [US1] Write an E2E test that sets owners on a device, reads the inherited owners of an interface, filters by owner and reads the deprecated `owner` field of an attribute, through the `infrahub_client` fixture on the full stack, in tests/e2e/ownership/test_node_owners.py. The test opens no page (user stories 1 and 5)
- [ ] T034 [P] [US1] Write a component test that changes the kind of a node with owners and reads the owners after the change in backend/tests/component/core/migrations/schema/test_node_kind_update_owners.py (FR-040)

### Implementation for User Story 1

- [ ] T035 [US1] Implement the order of sources of a node as a pure function in backend/infrahub/core/ownership/resolution.py (FR-004)
- [ ] T036 [US1] Implement the batch read of the owners that apply in backend/infrahub/core/ownership/resolver.py: one read of the stored states and the parents of all requested nodes, then the walk through the Parent relationship and the hierarchy parent (FR-004, FR-017)
- [ ] T037 [P] [US1] Create the output types `InfrahubOwnership` and `InfrahubMetadataNode`, the enums `OwnerState` and `OwnerOrigin`, and the input types `MetadataNodeInput` and `NodeMetadataInput` in backend/infrahub/graphql/types/ownership.py, as in contracts/graphql-schema.graphql
- [ ] T038 [US1] Create the field resolvers that collect the nodes of one request and call the resolver one time in backend/infrahub/graphql/resolvers/ownership.py. A read of owners needs no view permission on accounts or account groups (FR-016, FR-017)
- [ ] T039 [US1] Put the resolver on the GraphQL context in backend/infrahub/graphql/initialization.py
- [ ] T040 [US1] Add `ownership` to `node_metadata`, the `node_metadata` input to the create, update and upsert mutations, and the filters `node_metadata__owners__ids` and `node_metadata__owners__isnull` in backend/infrahub/graphql/manager.py
- [ ] T041 [US1] Apply the `node_metadata.owners` input after the node is saved, inside the transaction, in `mutate_create`, `mutate_update_object` and `mutate_upsert` of backend/infrahub/graphql/mutations/main.py (FR-013)
- [ ] T042 [US1] Close the owner edges of a node when the node is deleted in `backend/infrahub/core/node/__init__.py` (E-11)
- [ ] T043 [US1] Implement the owner filter and the "no owner" filter in backend/infrahub/core/ownership/filter.py, with the approach that the spike chose, and call it from `NodeGetListQuery` in backend/infrahub/core/query/node.py so that it applies before pagination (FR-018 to FR-020)
- [ ] T044 [US1] Check that a query without owners in its fields or filters runs no owner query, with a query count test in backend/tests/component/graphql/metadata/test_graphql_node_owners.py (FR-009)
- [ ] T045 [US1] Write the diff query for owner edges with one pattern for each edge type in backend/infrahub/core/diff/query/ownership.py
- [ ] T046 [US1] Build one diff property for each holder, with the sorted list of owner IDs as value, in backend/infrahub/core/diff/ownership_differ.py, and the reserved field names in backend/infrahub/core/diff/ownership_fields.py
- [ ] T047 [US1] Call the owner differ from backend/infrahub/core/diff/calculator.py and backend/infrahub/core/diff/query_parser.py
- [ ] T048 [US1] Merge owner edges as a set for each holder, edge type and owner in backend/infrahub/core/diff/query/bulk_merge.py, backend/infrahub/core/diff/merger/merger.py and backend/infrahub/core/diff/merger/exclusion_plan.py. Keep the `HAS_OWNER` edges to an owner that the branch deleted (FR-008). Close the owner edges of a node that the branch deleted
- [ ] T049 [US1] Report a conflict when the default branch and another branch change the owner state of the same holder, with the rule that the engineering review decided in Phase 1, in backend/infrahub/core/diff/conflicts_extractor.py (FR-030)
- [ ] T050 [US1] Resolve the display label of each owner ID of the list, and mark a deleted owner, in `DiffLabelsEnricher` of backend/infrahub/core/diff/enricher/labels.py (FR-029)
- [ ] T051 [US1] Record owner changes with the old and new owner IDs in the node changelog in backend/infrahub/core/changelog/diff.py, so that one event is sent for the changed node only (FR-031, E-4)
- [ ] T052 [US1] Return the display label of each owner of an owner change, resolved when the log is read, from the activity log query `Events` in backend/infrahub/graphql/queries/event.py (FR-031)
- [ ] T053 [US1] Update `updated_at` and `updated_by` of the node vertex when a mutation changes only the owners or the sources of the node, with the rule of `NodeUpdateMetadataQuery` in backend/infrahub/core/query/node.py, in backend/infrahub/core/ownership/writer.py. The nodes that inherit do not change (FR-053)
- [ ] T054 [US1] Add the new edge types to `GraphNodeRelationships`, and declare `HAS_OWNER` and `HAS_SOURCE` in both directions, in backend/infrahub/core/graph/schema.py. Change `NodeDuplicateQuery` in backend/infrahub/core/migrations/query/node_duplicate.py so that it reads the latest edge for each edge type between the node and each other vertex when a node changes kind (FR-040, research R-11)
- [ ] T055 [US1] Keep the owners of a node in the object conversion in `ConvertObjectType.mutate` of backend/infrahub/graphql/mutations/convert_object_type.py (FR-040)
- [ ] T056 [US1] Regenerate schema/schema.graphql with `uv run invoke schema.generate-graphqlschema` and the frontend GraphQL types with `pnpm codegen` in frontend/app

**Checkpoint**: user story 1 works on its own. A platform team can set, read and filter node owners.

---

## Phase 4: User Story 5 - Existing data, clients and speed stay the same after the upgrade (Priority: P1)

**Goal**: the upgrade changes no result for existing data, and a report lists the data whose meaning changes.

**Independent Test**: run the report on a fixture that contains each listed case. Upgrade the fixture, then run the existing tests and the query benchmarks.

### Tests for User Story 5

- [ ] T057 [P] [US5] Write a migration test on a fixture with repository owners, account group owners and attributes without owners, with a read at a time before the upgrade, in backend/tests/component/core/migrations/graph/test_close_repository_owner_edges.py (FR-036)
- [ ] T058 [P] [US5] Write a migration test for an attribute owner written on a branch before the upgrade in backend/tests/component/core/migrations/graph/test_hide_replaced_branch_attribute_owners.py (FR-037)
- [ ] T059 [P] [US5] Write a test of the report on a fixture with a repository owner, a relationship whose links have owners, and a value with `is_protected` set, in backend/tests/component/cli/test_ownership_report.py (FR-038)
- [ ] T060 [P] [US5] Write GraphQL tests for scenarios 3 to 6 of user story 5 (the `owner` field, the `ownership` block of existing attributes, `is_protected`) in backend/tests/component/graphql/metadata/test_graphql_owner_upgrade.py (FR-015, FR-037, FR-039)
- [ ] T061 [P] [US5] Write query benchmarks for SC-001 and SC-002 on the reference data set in backend/tests/query_benchmark/ownership/test_no_owner_overhead.py

### Implementation for User Story 5

- [ ] T062 [US5] Write the graph migration that closes the `HAS_OWNER` edges from attributes to repositories and deletes nothing, with the next free number, in backend/infrahub/core/migrations/graph/ (FR-036)
- [ ] T063 [US5] Write the graph migration that hides the attribute owner of the default branch that a branch replaced, with the next free number, in backend/infrahub/core/migrations/graph/ (FR-037)
- [ ] T064 [US5] Register both migrations and raise `GRAPH_VERSION` in `backend/infrahub/core/graph/__init__.py`
- [ ] T065 [US5] Refuse every kind other than an account or an account group as owner, on attributes and on links, in backend/infrahub/core/ownership/input.py and in the property write of backend/infrahub/core/attribute.py (D-4)
- [ ] T066 [US5] Write the report queries in backend/infrahub/core/ownership/report.py and the command `infrahub db ownership-report` in backend/infrahub/cli/db.py. The command must run on a database of the release before (FR-038)
- [ ] T067 [US5] Mark `is_protected` and its filter as deprecated, without a change of behaviour, in backend/infrahub/graphql/manager.py (FR-039)
- [ ] T068 [US5] Run the existing permission tests in backend/tests/unit/permissions and backend/tests/component/permissions without changes, and fix every difference (SC-007)

**Checkpoint**: stories 1 and 5 work together (delivery step 1).

---

## Phase 5: User Story 2 - Profiles and object templates give owners to many nodes (Priority: P2)

**Goal**: a profile gives owners that Infrahub reads through the profile. An object template gives owners that the create copies.

**Independent Test**: attach a profile that gives an owner to 3,000 devices. Change the owners that the profile gives, then read the devices, the diff and the activity log. Create a device from an object template, attach a profile, and read the owners of the device.

### Tests for User Story 2

- [ ] T069 [P] [US2] Write unit tests for the full order of a node (own state, profiles by priority, template copy, parent) in backend/tests/unit/core/ownership/test_resolution.py (FR-004, D-6)
- [ ] T070 [P] [US2] Write component tests for scenarios 1, 2 and 7 to 11 of user story 2 (profile owners, priority, a profile changed after nodes use it, a profile removed) in backend/tests/component/core/ownership/test_profile_owners.py
- [ ] T071 [P] [US2] Write component tests for scenarios 3 to 6 of user story 2 (template copy, subtemplates, a template changed after the create) and a test that counts the owner reads for a template with 2 and with 6 components in backend/tests/component/templates/test_template_owners.py (FR-026, FR-027)
- [ ] T072 [P] [US2] Write merge scenario tests for a profile changed on a branch and a template changed on a branch in backend/tests/component/core/diff/merge/test_ownership_merge.py (FR-030)
- [ ] T073 [P] [US2] Write an E2E test that attaches a profile that gives owners to a device, and creates a device from an object template that gives owners, through the `infrahub_client` fixture, in tests/e2e/ownership/test_profile_template_owners.py. The test opens no page

### Implementation for User Story 2

- [ ] T074 [US2] Write the queries that read and write the `OwnerSet` that a profile or an object template gives to its nodes, reached by `HAS_TARGET_OWNER_SET` with no key, in backend/infrahub/core/ownership/queries.py. A write first reuses a set created by any branch
- [ ] T075 [US2] Read the profiles of each requested node with their priority in the batch read of backend/infrahub/core/ownership/repository.py, and apply the order of D-6 in backend/infrahub/core/ownership/resolution.py (FR-025)
- [ ] T076 [US2] Add `target_ownership` to `node_metadata` of profiles and object templates, and the `target_owners` input, in backend/infrahub/graphql/manager.py and backend/infrahub/graphql/types/ownership.py. Refuse `target_owners` on other kinds in backend/infrahub/core/ownership/input.py (FR-012)
- [ ] T077 [US2] Copy the owners that the template and its subtemplates give to the new node and to its components, with a `HAS_OWNER_SOURCE` edge to the template, in the template functions of backend/infrahub/core/node/create.py (`read_template_components`, `read_subtemplates`, `handle_template_relationships`). Read the owners in a fixed number of queries (FR-026, FR-027)
- [ ] T078 [US2] Close the "from template" mark when a user writes owners on the holder, and read a holder with the mark as `INHERIT` with the origin `TEMPLATE`, in backend/infrahub/core/ownership/writer.py and backend/infrahub/core/ownership/models.py (D-7)
- [ ] T079 [US2] Include the `OwnerSet` of profiles and templates in the diff and the merge, under the reserved name `node_metadata__target_owners`, in backend/infrahub/core/diff/ownership_differ.py and backend/infrahub/core/diff/query/bulk_merge.py
- [ ] T080 [US2] Add `HAS_TARGET_OWNER_SET` and `HAS_OWNER_SOURCE` to the kind change test of backend/tests/component/core/migrations/schema/test_node_kind_update_owners.py, for a profile and for a node created from a template (FR-040)

**Checkpoint**: stories 1, 5 and 2 work. Profiles and templates give owners (delivery step 2).

---

## Phase 6: User Story 6 - Infrahub Enterprise restricts changes by owner, and Infrahub Community restricts nothing (Priority: P2)

**Goal**: one change check that every mutation calls inside its transaction, the "applies to" setting, and the permission report of each node. In Community, nothing is refused.

**Independent Test**: on Infrahub Community, run each kind of change on a node that another team owns, and confirm that Infrahub stores it. Then run the same changes with a test implementation of the change check that refuses one field, and confirm that nothing is written and that the response lists each refused item.

### Tests for User Story 6

- [ ] T081 [P] [US6] Write unit tests for the change set collector (fields that the user sent and that changed, both ends of a link, a move, a create, a cascade) in backend/tests/unit/permissions/change_check/test_collector.py (FR-044)
- [ ] T082 [P] [US6] Write a test implementation of the change check that records its calls and refuses chosen items, as a fixture in backend/tests/component/permissions/change_check/conftest.py
- [ ] T083 [P] [US6] Write component tests for scenarios 1 to 8 of user story 6, with the test implementation, in backend/tests/component/permissions/change_check/test_change_check_calls.py (FR-042 to FR-046)
- [ ] T084 [P] [US6] Write component tests for scenarios 9 to 11 of user story 6 (Community refuses to save an Enterprise value, gives no right to one in the database, and reports the decision for the kind) in backend/tests/component/permissions/test_applies_to.py (FR-047 to FR-049)
- [ ] T085 [P] [US6] Write a test that counts the database queries of a mutation with the Community change check, and a benchmark for SC-008, in backend/tests/query_benchmark/ownership/test_change_check_overhead.py (FR-043)
- [ ] T086 [P] [US6] Write a migration test for the `applies_to` migration on a fixture with object permissions on two branches: each permission gets `all_objects`, and its stored human-friendly ID is correct, in backend/tests/component/core/migrations/graph/test_object_permission_applies_to.py (FR-047)
- [ ] T087 [P] [US6] Write an E2E test in which a user with update permission on devices updates a device that another group owns, and an administrator saves an object permission with `applies_to: owned_objects`, through the `infrahub_client` fixture, in tests/e2e/ownership/test_community_restricts_nothing.py. Infrahub stores the update and refuses the permission. The test opens no page

### Implementation for User Story 6

- [ ] T088 [P] [US6] Create `ItemChange`, `LinkChange`, `OwnerChange`, `MoveChange`, `ChangeSet`, `Refusal` and `ItemPermissions` as frozen dataclasses in backend/infrahub/permissions/change_check/models.py, with the fields of contracts/change-check.md
- [ ] T089 [US6] Create the abstract class `ChangeCheck` with the operations `check`, `report`, `validate_permission` and `counted_permissions` in backend/infrahub/permissions/change_check/interface.py
- [ ] T090 [US6] Create `ChangeCheckCommunity` in backend/infrahub/permissions/change_check/community.py. `check` returns no refusal and does no database read. `report` returns the decision for the kind. `validate_permission` refuses `applies_to` other than `all_objects`, the action for changing owners and the global permission to manage ownership, with a message that says that the value needs Infrahub Enterprise
- [ ] T091 [US6] Create the collector that builds a `ChangeSet` from the user input and the node changelog in backend/infrahub/permissions/change_check/collector.py. It leaves out profile values, computed attributes, template components, pool allocations and merges (FR-046)
- [ ] T092 [US6] Build one change check for the process with the `_singletons` pattern in backend/infrahub/workers/dependencies.py, next to `build_ldap_auth_service`
- [ ] T093 [US6] Call the change check at the end of `InfrahubMutationMixin.mutate_update_object`, and in `_delete_obj` with every node that the cascade removes, in backend/infrahub/graphql/mutations/main.py
- [ ] T094 [US6] Call the change check at the end of `_do_create_node`, after the template components, when the mutation passes it to `create_node`, in backend/infrahub/core/node/create.py
- [ ] T095 [P] [US6] Call the change check after the write loop of `RelationshipAdd.mutate` and `RelationshipRemove.mutate`, with both ends of each link, in backend/infrahub/graphql/mutations/relationship.py
- [ ] T096 [P] [US6] Call the change check in `InfrahubIPPrefixMutation.mutate_delete` in backend/infrahub/graphql/mutations/ipam.py, and in `ConvertObjectType.mutate` as a delete and a create in backend/infrahub/graphql/mutations/convert_object_type.py
- [ ] T097 [US6] Raise one error that carries the list of refusals, and give one entry in `errors` for each refused item in `format_graphql_errors` of backend/infrahub/graphql/error_formatter.py, with the pattern of `MultiFieldValidationError` in backend/infrahub/errors/validation.py (FR-045)
- [ ] T098 [US6] Add the enum `PermissionAppliesTo` (`all_objects`, `owned_objects`, `objects_without_owners`), the action for changing owners in `PermissionAction`, and the global permission to manage ownership in `GlobalPermissions`, in `backend/infrahub/core/constants/__init__.py`. The `any` action must not include the action for changing owners
- [ ] T099 [US6] Add the attribute `applies_to` (Text, enum, default `all_objects`) to the object permission, and add it to the human-friendly ID, the uniqueness constraint and the display label (only when it is not `all_objects`), in backend/infrahub/core/schema/definitions/core/permission.py. Then run `uv run invoke backend.generate`
- [ ] T100 [US6] Write the graph migration that sets `applies_to` to `all_objects` on every object permission on every branch and recomputes its stored human-friendly ID, with the next free number, in backend/infrahub/core/migrations/graph/, and update the lookup of the anonymous role permission in backend/infrahub/core/initialization.py
- [ ] T101 [US6] Read `applies_to` in `AccountObjectPermissionQuery` and `AccountRoleObjectPermissionQuery`, with `all_objects` for a missing value, and add the field to `ObjectPermission`, in backend/infrahub/core/account.py
- [ ] T102 [US6] Call `validate_permission` when an object permission or a global permission is created or updated in `CoreObjectPermission` and `CoreGlobalPermission` of backend/infrahub/core/node/permissions.py (FR-048)
- [ ] T103 [US6] Drop the permissions that `counted_permissions` refuses when the permissions of an account load in `PermissionManager` of backend/infrahub/permissions/manager.py, so that a stored Enterprise value gives no right (FR-048)
- [ ] T104 [US6] Add `permissions` to `node_metadata` with the types `InfrahubNodePermissions` and `InfrahubFieldPermission` in backend/infrahub/graphql/types/ownership.py and backend/infrahub/graphql/manager.py, resolved with one `report` call for each page in backend/infrahub/graphql/resolvers/ownership.py (FR-049)

**Checkpoint**: Infrahub Enterprise can supply its own change check. Infrahub Community refuses nothing (delivery step 5).

---

## Phase 7: User Story 3 - A field has its own owners, or no owner (Priority: P3)

**Goal**: own owners and "no owner" on single attributes and relationship fields, from a user, a profile or an object template. The `owner` field of today keeps working.

**Independent Test**: on one server, give own owners to a relationship field without peers, set an attribute to no owner, and reset a field to inherit. Attach a profile that gives owners to one field, and create a server from an object template that gives owners to one field. Read each field in GraphQL and through the `owner` field of today.

### Tests for User Story 3

- [ ] T105 [P] [US3] Write unit tests for the order of sources of a field (own state, profile field owners by priority, template copy, node) in backend/tests/unit/core/ownership/test_resolution.py (FR-005)
- [ ] T106 [P] [US3] Write GraphQL tests for scenarios 1 to 4 and 9 to 11 of user story 3 in backend/tests/component/graphql/metadata/test_graphql_field_owners.py, with a count of the database queries for a page of 50 devices with the `ownership` of `interfaces` (FR-010, FR-011)
- [ ] T107 [P] [US3] Write GraphQL tests for scenarios 5 to 8 of user story 3 (read and write of the deprecated `owner` field with zero, one and two own owners, and `properties { owner }` on links) in backend/tests/component/graphql/metadata/test_graphql_owner_field.py (FR-014, FR-015, FR-007)
- [ ] T108 [P] [US3] Write migration tests that rename and remove an attribute and a relationship that have owners, on the default branch and on a branch that is then merged, in backend/tests/component/core/migrations/schema/test_owner_field_migrations.py (FR-041)
- [ ] T109 [P] [US3] Write a merge test for two branches that each set the first owners of the same relationship field in backend/tests/component/core/diff/merge/test_ownership_merge.py (FR-032, E-12)
- [ ] T110 [P] [US3] Add a case to backend/tests/integration_docker/test_schema_migration.py that renames an attribute with owners and changes the kind of a node with owners on the full stack, then reads the owners (FR-040, FR-041)
- [ ] T111 [P] [US3] Write an E2E test that sets own owners on a relationship field without peers, sets an attribute to no owner and resets a field to inherit, through the `infrahub_client` fixture, in tests/e2e/ownership/test_field_owners.py. The test opens no page

### Implementation for User Story 3

- [ ] T112 [US3] Write the queries that read and write the `OwnerSet` of a relationship field, reached by `HAS_OWNER_SET` with the key `identifier` and `direction`, in backend/infrahub/core/ownership/queries.py. A write first reuses a set with the same key under the same node, created by any branch
- [ ] T113 [US3] Store several `HAS_OWNER` edges and the `HAS_NO_OWNER` edge on an attribute vertex in backend/infrahub/core/query/attribute.py and backend/infrahub/core/attribute.py
- [ ] T114 [US3] Implement the order of sources of a field in backend/infrahub/core/ownership/resolution.py, and read the field holders in the batch read of backend/infrahub/core/ownership/repository.py (FR-005)
- [ ] T115 [US3] Add `ownership` to every attribute type and every relationship field type in backend/infrahub/graphql/manager.py
- [ ] T116 [US3] Return the `ownership` of a relationship without a read of the peers, also when the relationship has no peer, in backend/infrahub/graphql/resolvers/many_relationship.py and backend/infrahub/graphql/resolvers/single_relationship.py (FR-011)
- [ ] T117 [US3] Add the `field_owners` and `target_field_owners` inputs to `NodeMetadataInput` in backend/infrahub/graphql/types/ownership.py, the `owners` input next to `value` in backend/infrahub/graphql/mutations/attribute.py, and `target_field_ownership(fields:)` in backend/infrahub/graphql/manager.py. Refuse a field name that is not an attribute or a relationship of the kind in backend/infrahub/core/ownership/input.py
- [ ] T118 [US3] Write the queries for the owners that a profile or an object template gives to one field (an `OwnerSet` with the key `attribute`, or `identifier` and `direction`) in backend/infrahub/core/ownership/queries.py, and copy the field owners of a template at the create in backend/infrahub/core/node/create.py
- [ ] T119 [US3] Return the own owner from the deprecated `owner` field when the attribute has exactly one, else null, and replace the own owners on a write, in backend/infrahub/core/attribute.py and backend/infrahub/graphql/mutations/attribute.py. Set the deprecation reason in backend/infrahub/graphql/manager.py (FR-014)
- [ ] T120 [US3] Search for every reader of the latest `HAS_OWNER` edge (known: backend/infrahub/core/query/attribute.py, backend/infrahub/core/diff/enricher/labels.py, backend/infrahub/core/changelog/diff.py; to check: backend/infrahub/core/query/node.py, backend/infrahub/core/query/relationship.py, backend/infrahub/core/query/subquery.py, backend/infrahub/core/query/resource_manager.py) and make each one handle several owners
- [ ] T121 [US3] Show field owners in the diff under the reserved names `<relationship>__owners` and `<field>__target_owners` in backend/infrahub/core/diff/ownership_fields.py and backend/infrahub/core/diff/ownership_differ.py
- [ ] T122 [US3] Update or remove the `attribute` key of the sets that profiles and templates give, in backend/infrahub/core/migrations/query/owner_set_attribute.py, called from backend/infrahub/core/migrations/schema/attribute_name_update.py and backend/infrahub/core/migrations/schema/node_attribute_remove.py. Close the edges of the `OwnerSet` of a removed relationship in backend/infrahub/core/migrations/schema/node_relationship_remove.py (FR-041)
- [ ] T123 [US3] Add a node whose node owners and `interfaces` field owners include the same account group to the kind change test of backend/tests/component/core/migrations/schema/test_node_kind_update_owners.py (FR-040)

**Checkpoint**: single fields have their own owner state (delivery step 3).

---

## Phase 8: User Story 7 - A member of a subgroup gets the roles of its parent groups (Priority: P3)

**Goal**: a setting, off by default, that makes a member of a subgroup count as a member of every group above it. A report lists the users who gain roles.

**Independent Test**: build a group tree with a role on the parent group. Run the report, turn the setting on, and compare what a member of the subgroup can do before and after.

### Tests for User Story 7

- [ ] T124 [P] [US7] Write component tests for scenarios 1 to 3 and 5 of user story 7 in backend/tests/component/permissions/test_account_group_tree.py, and run the existing permission tests with groups that have parents (FR-051)
- [ ] T125 [P] [US7] Write a test of the report on a fixture with a parent group that has a role in backend/tests/component/cli/test_account_group_tree_report.py (FR-052)

### Implementation for User Story 7

- [ ] T126 [US7] Add the group tree setting, off by default, to `SecuritySettings` in backend/infrahub/config.py
- [ ] T127 [US7] With the setting on, start the permission queries from the direct groups of the account and add the groups above them, in `AccountGlobalPermissionQuery` and `AccountObjectPermissionQuery` of backend/infrahub/core/account.py. Membership counts downward only (FR-051)
- [ ] T128 [US7] Give the account ID and the group IDs of the user, with the groups above them when the setting is on, to the change check in backend/infrahub/permissions/manager.py
- [ ] T129 [US7] Write the command `infrahub db account-group-tree-report` in backend/infrahub/cli/db.py. It lists the users who would gain roles, and the roles, and it works with the setting off (FR-052)
- [ ] T130 [US7] Regenerate the reference docs with `uv run invoke docs.generate` for the new setting in docs/docs/reference/configuration.mdx

**Checkpoint**: the group tree counts when an administrator turns the setting on (delivery step 6).

---

## Phase 9: User Story 4 - Nodes record their sources (Priority: P4)

**Goal**: several sources per node, on each branch, with a filter by source.

**Independent Test**: create devices with a source, filter devices by that source, and compare the count and the sources that the API returns with the expected values.

### Tests for User Story 4

- [ ] T131 [P] [US4] Write GraphQL tests for scenarios 1 to 5 of user story 4 in backend/tests/component/graphql/metadata/test_graphql_node_sources.py (FR-033 to FR-035)
- [ ] T132 [P] [US4] Write a merge test that sets two sources on a branch and reads them on the default branch after the merge in backend/tests/component/core/diff/merge/test_sources_merge.py (FR-033)
- [ ] T133 [P] [US4] Write an E2E test that creates a device with two sources and filters devices by one source, through the `infrahub_client` fixture, in tests/e2e/ownership/test_node_sources.py. The test opens no page

### Implementation for User Story 4

- [ ] T134 [US4] Write the read, the write and the filter of node sources as `HAS_SOURCE` edges from the node vertex in backend/infrahub/core/ownership/sources.py. A source is an account, an account group, a repository, a resource pool, a profile or an object template (FR-033)
- [ ] T135 [US4] Add `sources` to `node_metadata`, the `sources` input, and the filter `node_metadata__sources__ids` in backend/infrahub/graphql/manager.py and backend/infrahub/graphql/types/ownership.py. A user with update permission on the kind can change sources (FR-034, D-10)
- [ ] T136 [US4] Apply the source filter before pagination in `NodeGetListQuery` of backend/infrahub/core/query/node.py (FR-020)
- [ ] T137 [US4] Include node sources in the diff, the merge and the changelog under the reserved name `node_metadata__sources` in backend/infrahub/core/diff/ownership_differ.py, backend/infrahub/core/diff/query/bulk_merge.py and backend/infrahub/core/changelog/diff.py (FR-029, FR-031)
- [ ] T138 [US4] Copy the `HAS_SOURCE` edges of a node in the kind change and the object conversion. Add two cases to backend/tests/component/core/migrations/schema/test_node_kind_update_owners.py: a node that has the same account group as owner and as source, and a node whose template is the origin of its owners and one of its sources. The node keeps both edges after the change (FR-040, research R-11)

**Checkpoint**: all user stories work (delivery step 4).

---

## Phase 10: Object files (FR-028)

**Purpose**: owners and sources in object files. This phase needs the API review of Phase 1 and changes the Python SDK repository first.

- [ ] T139 Accept `node_metadata` (`owners`, `sources`, `target_owners`) and field `owners` in the object file parser of python_sdk/infrahub_sdk/spec/object.py, with the rules of contracts/object-file.md. Open the pull request on the SDK repository against `infrahub-develop`
- [ ] T140 Refuse a plain name that matches both an account and an account group, and resolve the typed form `{kind, name}`, in backend/infrahub/core/ownership/input.py
- [ ] T141 Write a test that loads a file with each form of contracts/object-file.md and compares the stored states in backend/tests/component/core/ownership/test_object_files.py
- [ ] T142 Write a test that loads an object file with three nodes, with a test implementation of the change check that refuses the second node. The load stops, the first node is stored and the third node is not, in backend/tests/component/core/ownership/test_object_files.py (FR-045)
- [ ] T143 Move the `python_sdk` submodule pointer to the merged SDK commit, as its own commit

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: measurements, docs and generated files.

- [ ] T144 [P] Write query benchmarks for SC-003 to SC-006 on the reference data set in backend/tests/query_benchmark/ownership/test_owner_queries.py, with `EXPLAIN` and `PROFILE` checks of each new query, and record the numbers in dev/specs/infp-753-rbac-owners-option-e/measurements.md
- [ ] T145 [P] Measure SC-009 and SC-010 again, through the change check, with a test implementation that reads owners. Compare the numbers with the numbers of the spike in dev/specs/infp-753-rbac-owners-option-e/measurements.md
- [ ] T146 [P] Describe the owner edges, the `OwnerSet` and `NoOwner` vertices and the node sources in dev/knowledge/backend/database-schema.md
- [ ] T147 [P] Describe the change check, "applies to" and the group tree setting in dev/knowledge/backend/permissions.md, and the call sites of the change check in dev/knowledge/backend/mutations.md
- [ ] T148 [P] Write the user documentation for owners, sources, the deprecations of `owner` and `is_protected`, the upgrade report and the group tree setting in docs/docs/, and run `uv run invoke docs.generate`
- [ ] T149 [P] Add one Towncrier fragment for each user-visible change in changelog/ (owners and sources added, `owner` and `is_protected` deprecated, repositories refused as owners, the new setting), with the `creating-changelog-entries` skill
- [ ] T150 Regenerate schema/schema.graphql, schema/openapi.json, the backend generated files and the frontend GraphQL types, and run `uv run invoke docs.validate`
- [ ] T151 Run `uv run invoke format` and `uv run invoke lint`, then run the E2E tests of tests/e2e/ownership and the scenarios of dev/specs/infp-753-rbac-owners-option-e/quickstart.md on a local stack

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 (Setup): no dependency. The approvals and the API review block the pull requests, not the local work. Each decision task blocks the phase that it names.
- Phase 2 (Foundational): needs Phase 1. It blocks all user stories. The spike ends before the first pull request.
- Phase 3 (US1) and Phase 4 (US5): need Phase 2 and the decisions of Phase 1.
- Phase 5 (US2): needs Phase 3.
- Phase 6 (US6): needs Phase 3 for the owners that a create reports. The "applies to" tasks and the change check tasks need only Phase 2.
- Phase 7 (US3): needs Phase 3 and Phase 5.
- Phase 8 (US7): needs Phase 6 for the identity that the change check receives. The setting and the report need no other phase.
- Phase 9 (US4): needs Phase 3 for the diff and merge path.
- Phase 10 (object files): needs the API review, Phases 3, 5, 7 and 9 for the full contract, and Phase 6 for the test of a refused node.
- Phase 11 (Polish): needs the phases that it documents and measures.

### User Story Dependencies

- US1 (P1): no dependency on another story.
- US5 (P1): no dependency on another story. Released with US1.
- US2 (P2): needs the storage and the API read of US1.
- US6 (P2): needs the owners of US1.
- US3 (P3): needs US1, and US2 for the owners that profiles and templates give to a field.
- US7 (P3): independent of the owner stories, apart from the identity for the change check.
- US4 (P4): independent of US2 and US3.

### Within Each User Story

- Write the tests first, and confirm that they fail before the implementation.
- Queries before the repository, the repository before the resolver and the writer, then the GraphQL layer.
- Tasks that change the same file run one after the other.

### Parallel Opportunities

- The tasks marked [P] in one phase change different files.
- After Phase 3: US5, US2, US6 and US4 can run at the same time with separate developers. Each one changes `graphql/manager.py`, so merge often.
- US7 can run at any time after Phase 2, apart from its change check task.

## Parallel Example: User Story 1

```text
Task: "Write unit tests for the order of sources of a node in backend/tests/unit/core/ownership/test_resolution.py"
Task: "Write component tests for the walk to the parents in backend/tests/component/core/ownership/test_resolver.py"
Task: "Write component tests for the owner filter in backend/tests/component/core/ownership/test_filter.py"
Task: "Write component tests for owner changes in the diff in backend/tests/component/core/diff/merge/test_ownership_diff.py"
```

## Pull Request Split

The pull requests follow the layers, not the phases. plan.md ("Pull requests") gives the content of each pull request and the reasons. Each task is in one line of this list.

- **No pull request**: T001 to T005, T008, T022, T023, T145. These are the decisions, the API review, the spike and the measures.
- **1. Database layer**: T006, T007, T009 to T020, T024, T025, T027, T035, T036, T042, T043, T053, T061, T069 to T071, T074, T075, T077, T078, T105, T112 to T114, T118, T120, T134, T136, T144, T146
- **2. Branch layer**: T028 to T030, T045 to T051, T072, T079, T109, T121, T132, T137
- **3. Upgrade**: T034, T054, T057 to T059, T062 to T066, T080, T108, T122, T123, T138
- **4. GraphQL layer**: T021, T026, T031 to T033, T037 to T041, T044, T052, T055, T056, T060, T067, T068, T073, T076, T106, T107, T110, T111, T115 to T117, T119, T131, T133, T135
- **5. Permission layer**: T081 to T104, T147
- **6. Account group tree**: T124 to T130
- **7. Object files**: T139 to T143
- **8. User documentation**: T148
- **Every pull request**: T149, T150, T151
  - T149: one Towncrier fragment in each pull request that users can notice.
  - T150: the generated files that the pull request changes.
  - T151: format and lint in each pull request. The E2E tests and the scenarios of quickstart.md run when the API exists.

Order:

- Pull requests 2 and 3 need pull request 1. Pull request 4 needs both.
- Pull request 5 needs pull request 4. Pull requests 6 and 7 need pull request 5.
- Pull requests 2 and 3 can be in review at the same time. So can pull requests 6 and 7.
- Inside one pull request, do the tasks in the order of their numbers.

The lock (T021) and its test (T031) are in the GraphQL layer, because the mutation takes the lock.

## Implementation Strategy

### Delivery by layer

1. Complete the decision tasks and the API review of Phase 1, and the spike of Phase 2.
2. Open the pull requests in the order of "Pull Request Split". Each one holds one layer for all user stories.
3. After the GraphQL layer, stop and validate: run the tests of user stories 1 to 5, the query benchmarks and the GraphQL scenarios of quickstart.md for these stories.
4. After the permission layer and the account group tree, run the scenarios of quickstart.md for user stories 6 and 7.

### Order of the user stories

The task numbers follow the priorities of the user stories. Inside one pull request, this is the order of the work:

1. US1 and US5: node owners and the upgrade (delivery step 1).
2. US2: profiles and object templates (delivery step 2).
3. US6: the change check and "applies to" (delivery step 5).
4. US3: field owners (delivery step 3).
5. US7: the group tree (delivery step 6).
6. US4: node sources (delivery step 4).
7. Object files, then the polish phase.

Each pull request leaves `stable` and `develop` releasable.

## Notes

- The option E prototype on the dev VM already holds code for many tasks of Phases 2, 3, 5 and 7 (plan.md, files marked "P"). It is not committed. Review each file against the task before reuse.
- The file names of new tests and new modules are proposals. Keep the names of existing files.
- The phases follow the priorities of the user stories. plan.md ("Delivery order") gives the same order. The delivery step numbers of the spec are not in sequence.
- The E2E tests run through the API and open no page. User story 7 has no E2E test, because its setting needs its own stack.
- Graph migration numbers are the next free numbers when the work starts.
- This task list holds no frontend task (spec, "Out of scope"). `pnpm codegen` only regenerates files.
- Commit after each task or logical group. Do not edit generated files by hand.
