---

description: "Task list for stored schema changes and the schema change history query (IFC-3614)"
---

# Tasks: Store schema changes and query the schema change history of a branch

**Input**: Design documents from `dev/specs/ifc-3614-store-schema-changes/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Branch**: `ajtmccarty/ifc-3614-store-migrations`, branched from `develop`.

**Tests**: included. The constitution requires them, and the Jira task makes the equivalence test
suite the first task.

**Organization**: grouped by user story, so each story can be implemented and tested on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel with the other `[P]` tasks of the same phase. Different files, no
  dependency on an incomplete task.
- **[Story]**: the user story of [spec.md](spec.md) that the task belongs to.
- Every task names its file. A site inside a file is named by its enclosing symbol.
- Paths that start with `core/`, `api/` or `graphql/` in a description are under
  `backend/infrahub/`.

## Gates

| Gate | Blocks | Who |
| --- | --- | --- |
| The equivalence suite passes (T017) | Phases 4 to 8. No workflow stores a record before it passes | The implementer |
| The GraphQL contract in [contracts/schema-change-history.graphql](contracts/schema-change-history.graphql) is accepted. A new GraphQL query is "Ask First" in `AGENTS.md`; the Jira task asks for this query | T040 to T043 | A maintainer |

## Rules for every task

- Load `dev/guidelines/backend/python.md` before writing back-end Python,
  `dev/guidelines/backend/testing.md` before writing a test, and
  `dev/guidelines/code-doc-style.md` before writing a docstring or a comment.
- Load `dev/guidelines/backend/component-design.md` before adding a class. Each component in
  [contracts/internal-interfaces.md](contracts/internal-interfaces.md) takes its collaborators as
  required constructor arguments.
- Load `dev/knowledge/backend/query-pattern.md` and `dev/knowledge/backend/database-schema.md`
  before writing Cypher. Every query is parameterized and returns a typed result.
- No test name, comment or docstring names a Jira ticket. A known bug is named by its behaviour.
- Tests that read the same data build it once. Put them in a class and build the data in
  `@pytest.fixture(scope="class")` fixtures on the `_scope_class` fixture variants
  (`dev/guidelines/backend/testing.md`, "Share one schema and data load across a class"). A
  class-scoped fixture cannot request a function-scoped one: when a fixture has no
  `_scope_class` variant, add one beside it.
- A component test of the records requests no schema fixture. The records are not schema nodes;
  the test needs `db` and an empty database, and a default branch only when it creates a branch.
- A test implementation of a collaborator (one that records its calls, one that raises) goes in
  `backend/tests/unit/core/schema_change/helpers.py`, not in the test module.
- The components are built with the functions of `core/schema_change/factory.py`
  ([contracts/internal-interfaces.md](contracts/internal-interfaces.md), "Where the components
  are built"). The task that creates a component adds its function there.
- When a task changes a value that another file of this directory states (a field, a status, an
  order, a page size), update every file of `dev/specs/ifc-3614-store-schema-changes/` that
  states it, in the same commit.

---

## Phase 1: Setup

**Purpose**: the packages and the constants that every later task imports.

- [X] T001 [P] Create the package `backend/infrahub/core/schema_change/` with an empty
      `__init__.py`, and the test packages `backend/tests/unit/core/schema_change/`,
      `backend/tests/component/core/schema_change/` and `backend/tests/functional/schema_change/`,
      each with an empty `__init__.py`.
- [X] T002 Create `backend/infrahub/core/schema_change/constants.py`, with constant values only.
      Load `dev/guidelines/constants.md` first. It holds:
      - `SchemaChangeStatus`: `staged`, `running`, `applied`, `failed`;
      - `SchemaChangeApplicationStatus`: `running`, `applied`, `failed`, `rolled_back`, `skipped`;
      - `SchemaChangeMigrationStatus`: `waiting`, `running`, `applied`, `failed`, `rolled_back`;
      - `SchemaOperationType`: `node_add`, `node_remove`, `node_property`, `element_add`,
        `element_remove`, `element_property`;
      - `SchemaOperationNodeType`: `node`, `generic`;
      - `SchemaOperationSection`: `attributes`, `relationships`;
      - the operation format version, `1`;
      - the number of digits of the version in a name, `5`;
      - the four edge type names `SCHEMA_CHANGE_HAS_OPERATION`, `SCHEMA_CHANGE_HAS_APPLICATION`,
        `SCHEMA_CHANGE_HAS_PARENT` and `SCHEMA_APPLICATION_HAS_MIGRATION`;
      - the page sizes of the history query: default 10 and maximum 50 schema changes, default 50
        and maximum 500 operations.

      Use string enumerations, as `InfrahubStringEnum` does, so that `StandardNode` stores each
      value as text.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the in-memory form of an operation. The builder, the applier, the records and the
query all read it.

**Blocks**: every phase from 3 onwards.

- [X] T003 [P] Write the unit tests of the operation model in
      `backend/tests/unit/core/schema_change/test_operations.py`. They cover the rules of
      [data-model.md](data-model.md), "SchemaChangeOperation", that our code enforces:
      - an element type without `section` or `element_name` is refused;
      - a property type without `property_name` is refused;
      - `node_add` without `node_type` is refused;
      - an add type whose `value` holds `id`, or `parameters.number_pool_id`, is refused;
      - the summary of one operation is the kind in lower case, then the attribute, relationship
        or property name when there is one, then `add`, `remove` or `update`. Example:
        `dcimgenericdevice_serial_add`;
      - the summary of several operations ends with `_and_<n>_more`;
      - the name is `<version, five digits>_<summary>`, and the summary alone without a version;
      - a version above 99999 gives a name with more than five digits.
- [X] T004 Create `backend/infrahub/core/schema_change/operations.py` with `SchemaOperation`, a
      Pydantic model with the fields `operation_type`, `kind`,
      `node_type: SchemaOperationNodeType | None`, `section: SchemaOperationSection | None`,
      `element_name`, `property_name`, `value` and `previous_value`, a model validator for the
      rules of T003, and two functions that build the summary of a list of operations and the
      name from a version and a summary ([research.md](research.md), R4 and R10). Make T003 pass.
- [X] T005 [P] Add `SchemaOperationTargetNotFoundError` to `backend/infrahub/exceptions.py`. Its
      message names the position and the type of the operation and the kind, attribute or
      relationship that the schema does not have (FR-023).

**Checkpoint**: `uv run pytest backend/tests/unit/core/schema_change/` passes.

---

## Phase 3: User Story 1 — a schema load gives the same schema and the same migrations as before (P1)

**Goal**: one applier builds the schema for the schema load, the schema check and the dropdown and
enum mutations, with the same result as today. Nothing is stored yet.

**Independent Test**: `uv run pytest backend/tests/unit/core/schema_change/` passes, and the
existing tests of the schema load, the schema check and the mutations pass with the same expected
results ([quickstart.md](quickstart.md), sections 1 and 5).

### The equivalence suite (write first; it must fail before T015 and T016)

- [X] T006 [US1] Create the shared schema and the helpers of the suite.

      In `backend/tests/unit/core/schema_change/conftest.py`, one session-scoped fixture that
      returns a processed `SchemaBranch` built once from the internal schema, the core schema
      and one base `SchemaRoot` for the suite, with an ID on every node, attribute and
      relationship (`SchemaRoot.generate_uuid`), as `_load_processed_branch` does in
      `backend/tests/unit/core/schema/test_schema_branch.py`:
      - design the base `SchemaRoot` so that most cases start from it: a generic with
        attributes and a relationship, two kinds that inherit it, a dropdown attribute, a unique
        attribute, a kind with `generate_profile` off. Reuse the schemas of
        `backend/tests/helpers/schema/` before defining one;
      - every case reads this one schema and never changes it. The operation builder and the
        applier never change their input, and T013 asserts it. A case that needs another
        starting schema derives it with `duplicate()` and `load_schema`, and does not build the
        internal and core schema again;
      - a session-scoped fixture cannot request the function-scoped
        `set_registry_default_branch` of `backend/tests/unit/conftest.py`. If the build reads
        the default branch of the registry, set it inside the fixture and restore it.

      In `backend/tests/unit/core/schema_change/helpers.py`, as plain functions:
      - a reference function that builds the result of a direct load with `SchemaBranch` calls
        only: `duplicate`, `load_schema`, `process`, `diff`, `validate_node_deletions`,
        `validate_update`. It must not call `SchemaCandidateBuilder`
        ([research.md](research.md), R14);
      - a function that compares two results: the hash of every node, generic, profile and
        template kind (`SchemaBranch.to_dict`), the migrations as a sorted list of migration name
        and schema path, and the constraints in the same form. It must not call
        `SchemaCandidateComparer`.
- [X] T007 [US1] Write the cases that the first spike covered in
      `backend/tests/unit/core/schema_change/test_applier_equivalence.py`. Write the cases of
      T007 to T010 as dataclass test cases (`dev/guidelines/backend/testing.md`, "Dataclass Test
      Case Pattern"): a `name` and the schema file to load, in a module-level list, with one
      parametrized test for each module. The test starts from the shared schema of T006, builds
      the operations with `SchemaOperationBuilder`, applies them with `SchemaChangeApplier`, and
      compares the result with the reference of T006:
      - adding an attribute to a generic;
      - turning on `generate_profile`;
      - making an attribute unique;
      - removing an attribute;
      - renaming an attribute on a node, and on a generic;
      - adding a node.
- [X] T008 [P] [US1] Write the relationship cases in
      `backend/tests/unit/core/schema_change/test_applier_equivalence_relationships.py`: adding a
      relationship, removing one, renaming one, and changing `peer`, `cardinality`, `optional`
      and `kind`.
- [X] T009 [P] [US1] Write the kind cases in
      `backend/tests/unit/core/schema_change/test_applier_equivalence_kinds.py`: renaming a kind,
      changing its namespace, adding a generic to `inherit_from`, and removing a generic.
- [X] T010 [P] [US1] Write the remaining cases of FR-024 in
      `backend/tests/unit/core/schema_change/test_applier_equivalence_fields.py`:
      - dropdown choices: adding a choice, removing one with `state: absent`, changing a colour;
      - `state: absent` on a node, on an attribute and on a relationship;
      - a node extension that adds an attribute and a relationship;
      - list fields that a load replaces whole: `human_friendly_id`, `inherit_from`,
        `uniqueness_constraints`, `order_by` and `display_labels`;
      - an attribute kind change within one load;
      - a file that renames an attribute and writes `human_friendly_id` in the same load
        ([research.md](research.md), R6);
      - a file that clears an optional text field with an empty string
        ([research.md](research.md), R5).
- [X] T011 [P] [US1] Write the four known-bug cases of FR-025 in
      `backend/tests/unit/core/schema_change/test_applier_known_bugs.py`. Each case states the
      fixed behaviour as its expected result, written by hand, not taken from the reference:

      | Bug | Fixed behaviour to assert |
      | --- | --- |
      | [IFC-3085](https://opsmill.atlassian.net/browse/IFC-3085) | Changing `unique` from `true` to `false` sets it to `false` and removes the uniqueness constraint that was calculated from it |
      | [IFC-3599](https://opsmill.atlassian.net/browse/IFC-3599) | After a relationship's kind changes to Component and no file set `on_delete`, `on_delete` is `cascade`; a value written in a file is kept |
      | [IFC-3601](https://opsmill.atlassian.net/browse/IFC-3601) | Renaming an attribute on a generic creates a migration that reaches the profile nodes of the kinds that inherit the generic |
      | [IFC-3602](https://opsmill.atlassian.net/browse/IFC-3602) | Changing the kind of an attribute on a generic alone is accepted, and the inheriting kinds' copies follow |

      A case that fails because its bug is not fixed is marked `xfail(strict=True)` with a reason
      that describes the behaviour, not the ticket. A case that passes has no marker (spec,
      decision 2). The table above is the only place that links a case to its ticket.
- [X] T012 [P] [US1] Write the tests of the operation builder in
      `backend/tests/unit/core/schema_change/test_operation_builder.py`:
      - a file that changes nothing gives no operation (FR-003);
      - an attribute added to a generic gives one `element_add` on the generic, and no operation
        on a kind that inherits it (FR-011);
      - turning on `generate_profile` gives no operation on a profile kind;
      - a unique attribute gives no operation on `human_friendly_id` or `uniqueness_constraints`
        that processing calculated, and one when the file writes it (FR-013);
      - a rename by ID gives one `element_property` on `name` that names the element by its name
        before the load, with the new name as the value and the old name as the previous value
        (FR-014, FR-015);
      - no operation holds an `id` or a `parameters.number_pool_id` (FR-012);
      - the `direct_load_schema` of the result has the same hashes as the reference of T006;
      - the operations come in the order of [research.md](research.md), R5, whatever the order of
        the file;
      - every operation survives a JSON round trip: dump the list to JSON, load it, apply it, and
        get a schema with the same hash.
- [X] T013 [P] [US1] Write the tests of the applier in
      `backend/tests/unit/core/schema_change/test_applier.py`:
      - an operation on a kind, an attribute or a relationship that the target does not have
        raises `SchemaOperationTargetNotFoundError`, and the message names the operation and the
        element (FR-023);
      - the target schema is unchanged after `apply`;
      - a property that no operation names keeps its value (FR-020);
      - the same target and operations give the same hash twice;
      - the shared schema of T006 has the same hash after the whole module ran as before it.
- [X] T014 [P] [US1] Write the tests on a target that changed, in
      `backend/tests/unit/core/schema_change/test_applier_changed_target.py`. Record the
      operations against one schema, then apply them to a schema that changed separately:
      - "add an attribute to a generic", applied to a target that gained a kind that inherits the
        generic: the new kind has the attribute, and the migrations include it;
      - "change the label of an attribute", applied to a target where another property of the
        same kind changed: the target's own change is kept (FR-011).

### Implementation

- [X] T015 [US1] Create `SchemaOperationBuilder` in
      `backend/infrahub/core/schema_change/operation_builder.py`, following
      [research.md](research.md), R5, and its contract in
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md). It lays the file over
      a copy of the branch schema, keeps that schema before processing, processes it, and keeps
      each path of the processed diff that the file states. Values are read from the schema before
      processing, previous values from the branch schema, and the name before a rename by the
      element's ID. It emits the operations in the order of R5, and returns a
      `SchemaOperationBuildResult` with the operations and, as `direct_load_schema`, the
      processed schema of the laid-over file.
- [X] T016 [US1] Create `SchemaChangeApplier` in `backend/infrahub/core/schema_change/applier.py`,
      following [research.md](research.md), R6, and its contract. It duplicates the target,
      applies each operation in order, calls `BaseNodeSchema.apply_schema_path_updates` for each
      kind with the removed names and the map of renamed names, then runs `SchemaBranch.process`.
      `node_remove` sets the state of the kind to absent, as a load does. Select the handling
      of an operation with an exhaustive `match` on `SchemaOperationType` that ends with
      `typing.assert_never`.
- [X] T017 [US1] Run `uv run pytest backend/tests/unit/core/schema_change/` and make T007 to T014
      pass. Each case of FR-025 passes or is a strict expected failure. When a case needs a change
      to the format of the operations, change `operations.py`, [data-model.md](data-model.md),
      [research.md](research.md) R4 to R6 and the GraphQL contract in the same commit. When the
      case of R6 shows that the path rewrite must run before the values are set, change the
      applier and R6. **This task is the gate for phases 4 to 8.**
- [ ] T018 [US1] Create `SchemaCandidateComparer` in
      `backend/infrahub/core/schema_change/candidate_comparer.py`, then `SchemaCandidate` and
      `SchemaCandidateBuilder` in `backend/infrahub/core/schema_change/candidate.py`, following
      their contracts. The builder takes the operation builder, the applier and the comparer in
      its constructor. `from_schema_root` and `from_operations` return the operations, the
      applier's schema and the `SchemaUpdateValidationResult` calculated from the diff between
      the branch schema and the applier's schema. `from_schema_root` passes the
      `direct_load_schema` that the operation builder returned and the applier's schema to the
      comparer, and logs a warning that names the kinds it returns. It does not process the
      file a third time.
      Create `backend/infrahub/core/schema_change/factory.py` with
      `build_schema_candidate_builder()`. Add unit tests, on the shared schema of T006:
      - in `backend/tests/unit/core/schema_change/test_candidate_comparer.py`: two equal schemas
        give an empty list; a kind whose property differs, and a kind that only one schema has,
        are returned, in sorted order;
      - in `backend/tests/unit/core/schema_change/test_candidate.py`: both methods give the same
        diff, migrations and constraints for the same change, and a file that changes nothing
        gives an empty diff and no operation.
- [ ] T019 [US1] Replace `api/schema.py::evaluate_candidate_schemas` with one function that the
      load and the check both call:
      `build_candidate_from_schemas(*, candidate_builder, branch_schema, default_branch_schema, schemas) -> SchemaCandidate`.
      It merges the schema files of the request, calls
      `SchemaCandidateBuilder.from_schema_root`, and raises `SchemaNotValidError` for a
      `ValueError` and for the errors of the candidate's validation, as today. It reads no
      registry and builds no component.
      - `load_schema` and `check_schema` each build the candidate builder at their top with
        `build_schema_candidate_builder()`, after the permission checks and, for the load,
        before the schema lock. Each reads the branch schema and the default branch schema from
        the registry where it reads the branch schema today, and passes them.
      - `load_schema` keeps the `SchemaCandidate`, so that phase 4 can store its operations.
      - `check_schema` returns the diff of the applier's result (FR-021). It calls
        `_validate_migrations` with the schema and the constraints of the candidate, in place of
        its own copy of the constraint workflow call.
      - Change the five calls of `evaluate_candidate_schemas` in
        `backend/tests/component/core/constraint_validators/test_number_pool_scope.py`,
        `backend/tests/component/core/constraint_validators/test_number_pool_rename.py` and
        `backend/tests/component/pools/test_schema_number_pool_scope.py` to call
        `build_schema_candidate_builder().from_schema_root(...)` and read `candidate.schema` and
        `candidate.validation`. Their expected results do not change (SC-002).
- [ ] T020 [US1] Replace `graphql/mutations/schema.py::update_registry` with
      `apply_attribute_property_change(*, kind, attribute, property_name, value, db, branch, account_id, service, context)`,
      where `property_name` is `choices` or `enum` and `value` is the new list, and change its
      four callers.
      - Each mutation keeps its checks where they run today. It calculates the new list without
        changing a copy of the kind, and builds no operation.
      - The function builds the candidate builder with `build_schema_candidate_builder()` at its
        top. Inside `lock.registry.global_schema_lock()` it reads the list before the change
        from the branch schema, builds one `element_property` operation with that list as the
        previous value, and calls `SchemaCandidateBuilder.from_operations` in place of
        `tmp_schema.set`, `tmp_schema.process` and `tmp_schema.diff`.
      - It reads the schema and the diff from the `SchemaCandidate` and keeps the candidate, so
        that phase 6 can store its operation. It runs none of the migrations or constraints
        that the candidate lists.
      - The save and the event are unchanged (FR-002, FR-021). The save keeps
        `update_schema_branch(limit=...)` ([research.md](research.md), R11 and R16).
      - The candidate's diff runs from the branch schema to the candidate, where today's code
        calculates it in the other direction: confirm with
        `backend/tests/component/graphql/mutations/test_schema.py` that
        `update_schema_branch(limit=...)` and the `SchemaUpdatedEvent` payload name the same
        elements, and that `validate_update` returns no error for a change of `choices` or
        `enum`.
- [ ] T021 [US1] Run the existing tests and confirm SC-002. Run each command on its own:
      `uv run invoke backend.test-unit`,
      `uv run pytest backend/tests/component/api/test_40_schema.py`,
      `uv run pytest backend/tests/component/core/schema_manager/`,
      `uv run pytest backend/tests/component/core/constraint_validators/`,
      `uv run pytest backend/tests/component/pools/test_schema_number_pool_scope.py`,
      `uv run pytest backend/tests/integration/schema_lifecycle/`,
      `uv run pytest backend/tests/functional/schemas/ backend/tests/functional/api/test_load_schema.py`.
      A test may change only when it asserts one of the four known bugs and the applier fixes it,
      or when it is one of the five calls that T019 changes. For any other failure, fix the
      builder or the applier and add the case to the suite.
- [ ] T022 [US1] Measure the time of `SchemaCandidateBuilder.from_schema_root` against the time
      of the reference function of T006 on the internal and core schema plus the largest schema
      of `backend/tests/helpers/schema/`. Write the result in [research.md](research.md), R7, as a
      ratio, with the command that reproduces it.

**Checkpoint**: user story 1 can be delivered alone. Every schema load, check and mutation builds
its schema with the applier, and nothing is stored.

---

## Phase 4: User Story 2 — a schema owner views the schema change history of a branch (P1)

**Goal**: a schema load stores its schema change, its application and its migration records, and
a GraphQL query returns the history of a branch in pages.

**Independent Test**: on a branch with nodes, load three schema files, then query the history
([quickstart.md](quickstart.md), sections 2 and 3).

### Tests (write first)

- [ ] T023 [US2] Write the seeding function and the component tests of the repository and
      of the history reader, against Neo4j.

      In `backend/tests/helpers/schema_change.py`, one async function that creates a history
      through `SchemaChangeRepository` and returns a dataclass with the IDs and the timestamps
      it created. It takes the number of applied, failed and running schema changes for each
      branch name, the number of operations of each, and the migrations of each application.
      T024, T025, T026 and T052 use it, so no test module creates these records by hand.

      The first five cases below write, so each is a function test in
      `backend/tests/component/core/schema_change/test_repository.py` that requests `db` and
      `empty_database` only. The last three only read, so they are methods of one class in
      `backend/tests/component/core/schema_change/test_history_reader.py`, with one class-scoped
      fixture that requests `empty_database_scope_class` and seeds main, two branches, applied,
      failed and running schema changes, and more operations than one page:
      - creating a schema change with operations and one application stores the operations in
        the order of `position` and links them with the edges of [data-model.md](data-model.md);
      - no edge between records has a `branch` property;
      - `value` and `previous_value` keep a list, a mapping, a boolean, the JSON value `null` and
        the text `NULL` apart from a field that is not set;
      - creating migration records stores one record for each migration with the status
        `waiting`, in order, including two migrations with the same name and path;
      - setting the status of migration records changes only the records named;
      - listing returns applied schema changes by version, then the others by `created_at`, with
        `limit`, `offset`, a status filter and the count of all pages;
      - operations for a set of schema changes come in pages with the count for each one;
      - applications for a set of schema changes come with their migration records.
- [ ] T024 [P] [US2] Write the component tests of the version resolver and of the recorder.
      Neither module requests a schema fixture.

      In `backend/tests/component/core/schema_change/test_version_resolver.py`, as methods of
      one class. The resolver only reads, so one class-scoped fixture on
      `default_branch_scope_class` creates the branches and seeds every case below with the
      function of T023, each case on branches of its own:
      - main with no schema change gives version 1 and no parent;
      - main with applied versions 1, 2 and 3 gives version 4, with version 3 as the parent
        (FR-030, FR-034);
      - a branch created when main was at version 2 gives 3, with main's version 2 as the
        parent; after the branch applied that one, it gives 4, with the branch's version 3 as
        the parent (FR-031);
      - two branches created from the same version of main each give that version plus 1;
      - main has a schema change whose `applied_at` is before the `branched_from` of a branch:
        the branch gives main's version plus 1 ([research.md](research.md), R10);
      - main has a schema change whose `applied_at` is after the `branched_from` of a branch: the
        branch does not count it;
      - a `running` or a `failed` schema change on the branch does not change the result
        (FR-032).

      In `backend/tests/component/core/schema_change/test_recorder.py`, as function tests that
      request `db` and `default_branch`, because each one writes:
      - `start` creates a schema change with the status `running`, no version and no parent, and
        an application with the status `running` and the timestamp given;
      - `complete` sets both to `applied`, and stores the version and the parent that the
        resolver returns and `applied_at`;
      - two changes completed one after the other on main get the versions 1 and 2, and the
        second has the first as its parent;
      - `record_applied` creates an applied schema change and an applied application in one call;
      - `start` and `record_applied` raise when the list of operations is empty (FR-003).
- [ ] T025 [P] [US2] Write the tests of the migration recorder.

      In `backend/tests/component/core/schema_change/test_migration_recorder.py`, as function
      tests that request `db` and `empty_database` only, each on one application created with
      the function of T023:
      - `register` creates the records with the status `waiting` (FR-052);
      - `batch_started` sets the records at the positions given to `running`, and no other;
      - `migration_ended` with a result without error sets the record at that position to
        `applied` and stores `nbr_migrations_executed`, including the value 0 (FR-053);
      - `migration_ended` with errors sets the record to `failed` and stores the errors;
      - two migrations with the same name and path are updated separately, by position;
      - the recorder that `build_migration_recorder` returns for no application ID creates no
        record when its three methods are called.

      In `backend/tests/unit/core/schema_change/test_migration_recorder.py`, without a database.
      Add to `backend/tests/unit/core/schema_change/helpers.py` a `MigrationRecordStore` that
      records each call and then raises:
      - with that store, `register`, `batch_started` and `migration_ended` do not raise. Assert
        the log record of each failure with `caplog`, and that the store received each call.
- [ ] T026 [P] [US2] Write the component tests of the query in
      `backend/tests/component/graphql/queries/test_schema_change.py`, as methods of one class in
      the style of
      `backend/tests/component/graphql/metadata/test_graphql_query_metadata.py::TestMetadataFilters`.
      Every case only reads, so one class-scoped fixture seeds the history once with the
      function of T023: main and two branches, one of them with no schema change, applied and
      failed schema changes, several operations and migrations. It does not load a schema file.
      The class requests `default_branch_scope_class`, the `_scope_class` variants of the schema
      fixtures that `prepare_graphql_params` needs, and `session_admin_scope_class`:
      - the query returns the schema changes of the branch of the request only;
      - `count` and `edges` follow `limit` and `offset`, and a page holds at most `limit` items
        (FR-072);
      - `name`, `version`, `status`, `created_at`, `updated_at`, `applied_at` and `parent` have
        the values of the contract;
      - `operations(limit, offset)` returns pages in the order of `position` with the count;
      - `applications` returns each application with its migrations, each with its path, name,
        status, result and errors (FR-070);
      - a `limit` below 1 or above the maximum, and an `offset` below 0, are refused;
      - a branch with no schema change returns an empty page and a count of 0;
      - a page of several schema changes runs a fixed number of queries, whatever the number of
        schema changes on it. Count them with `CountingInfrahubDatabase` from
        `backend/tests/helpers/db_query_counter.py`.
- [ ] T027 [US2] Create the base class and the data set of the functional tests in
      `backend/tests/functional/schema_change/shared.py`, in the way
      `backend/tests/integration/schema_lifecycle/shared.py::TestSchemaLifecycleBase` does:
      - `TestSchemaChangeBase(TestInfrahubApp)`, with the schema files of the scenario as
        class-scoped fixtures. Reuse the schemas of
        `backend/tests/integration/schema_lifecycle/shared.py` or `backend/tests/helpers/schema/`
        before defining one;
      - one class-scoped fixture that loads the base schema, creates the nodes and creates the
        branch of the scenario, and returns their IDs. Every class of this package uses it, so
        the registry, the base schema and the nodes are set up once for each class and never for
        each test.

      Then create the ordered class `TestSchemaChangeHistory(TestSchemaChangeBase)` in
      `backend/tests/functional/schema_change/test_schema_change_history.py`. Its methods run in
      the order they are defined, and each one continues from the state the one before it left.
      Say so in the docstring of the class. Phases 4, 5 and 7 add methods to it in this order:
      loads and check (this task), history query (T028), failed load and corrected load (T046),
      branch deletion (T055), which stays last.

      The methods of this task, on the branch, each asserting the records through
      `SchemaChangeHistoryReader`:
      - a load that changes the schema stores one schema change with the status `applied` and
        the operations of the file;
      - loading the same file a second time stores none (FR-003);
      - a load that only changes a label stores a schema change whose application has no
        migration record (FR-004);
      - a load that is refused for an invalid file, or for a constraint that the nodes of the
        data set fail, stores none, and the records are the same as before (spec, decision 1);
      - a schema check stores none, and returns the diff between the branch schema and the
        applier's result (FR-021).
- [ ] T028 [US2] Add the history query methods to `TestSchemaChangeHistory` in
      `backend/tests/functional/schema_change/test_schema_change_history.py`, after the methods
      of T027. Load one more file that adds an attribute to a generic, so the branch has three
      applied schema changes, then query `InfrahubSchemaChange` through GraphQL:
      - three applied schema changes with consecutive versions that start after main's version;
      - each name starts with its version in five digits;
      - the attribute added to a generic gives one operation on the generic, and one migration
        record for each migration that ran, with the status `applied`;
      - each schema change after the first has the one before as its parent;
      - the same query sent through the HTTP client without a token is refused, and the same
        query with the token of an account that has no other permission returns the page
        (FR-073). This case is here and not in T026 because the GraphQL application enforces
        `QUERIES_REQUIRING_AUTHENTICATION` (`graphql/api/dependencies.py`), not the resolver.

### Records

- [ ] T029 [US2] Create the four `StandardNode` records in
      `backend/infrahub/core/schema_change/models.py`, with exactly the fields of
      [data-model.md](data-model.md):
      - `SchemaChange`: `branch: str`, `status: SchemaChangeStatus`, `version: int | None`,
        `summary: str`, `format_version: int`, `applied_at: str | None`;
      - `SchemaChangeOperation`: `position: int`, `operation_type: SchemaOperationType`,
        `kind: str`, `node_type: SchemaOperationNodeType | None`,
        `section: SchemaOperationSection | None`, `element_name: str | None`,
        `property_name: str | None`, `value` and `previous_value` as JSON-encoded text or `None`;
      - `SchemaChangeApplication`: `branch: str`, `status: SchemaChangeApplicationStatus`,
        `at: str`, `error: str | None`;
      - `SchemaChangeMigration`: `position: int`, `migration_name: str`,
        `path_type: SchemaPathType` (the existing enum in `infrahub.core.constants`),
        `schema_kind: str`, `field_name: str | None`, `property_name: str | None`,
        `status: SchemaChangeMigrationStatus`, `nbr_migrations_executed: int | None`,
        `errors: list[str]`.

      The models hold data only. They get no query and no persistence method beyond what
      `StandardNode` gives them. Timestamps are text in the format of `Timestamp.to_string()`.
- [ ] T030 [US2] Create the write queries in `backend/infrahub/core/query/schema_change.py`:
      - create a schema change, its operations and one application in one query, each vertex with
        its `IS_PART_OF` edge to `Root` as `StandardNodeCreateQuery` creates it, and the edges of
        [data-model.md](data-model.md);
      - create the migration records of an application in one query, and return the element ID of
        each record with its position;
      - set the status, `nbr_migrations_executed` and `errors` of migration records selected by
        element ID;
      - mark a schema change and its application applied: status, version, `applied_at`, and the
        `SCHEMA_CHANGE_HAS_PARENT` edge when there is a parent.
- [ ] T031 [US2] Create the read queries in `backend/infrahub/core/query/schema_change.py`, each
      with a typed result:
      - the highest version of the applied schema changes of a branch, with the ID of that schema
        change;
      - the highest version among main's schema changes whose `applied_at` is at or before a
        timestamp, with its ID;
      - a page of the schema changes of a branch, ordered by status `applied` first, then
        `version`, then `created_at`, then element ID, with an optional status filter, and its
        count. Page inside the query body before reading the parent, and set `self.limit`, as
        `dev/knowledge/backend/query-pattern.md` says for a query that pages itself;
      - the operations of a set of schema changes, a page for each one, with the count for each;
      - the applications of a set of schema changes, with their migration records in the order
        of `position`.
- [ ] T032 [US2] Create `SchemaChangeRepository` in
      `backend/infrahub/core/schema_change/repository.py` and `SchemaChangeHistoryReader` in
      `backend/infrahub/core/schema_change/history_reader.py`, each with its methods of
      [data-model.md](data-model.md), "What the repository and the history reader offer", except
      the repository method that phase 5 adds. Each takes `db` in its constructor and returns
      typed results. The repository converts `SchemaOperation` to `SchemaChangeOperation`, and
the reader converts it back. Neither has a delete method. Name the two migration record
      methods of the repository `create_migration_records` and `set_migration_records_status`,
      with the signatures of `MigrationRecordStore` in the contract. Make T023 pass.
- [ ] T033 [US2] Create `SchemaChangeVersionResolver` and `SchemaChangeVersion` in
      `backend/infrahub/core/schema_change/version_resolver.py`, following the contract and
      [research.md](research.md), R10. Then create `SchemaChangeRecorder` and
      `SchemaChangeRecording` in `backend/infrahub/core/schema_change/recorder.py` with `start`,
      `complete` and `record_applied`, following the contract and R8. The recorder takes the
      repository and the resolver in its constructor. `complete` and `record_applied` ask the
      resolver for the version and the parent, then write them. `applied_at` is the
      application's `at`. Make T024 pass.

### Migration records

- [ ] T034 [US2] Create the `MigrationRecorder` interface and `NoRecordMigrationRecorder` in
      `backend/infrahub/core/schema_change/migration_recorder.py`, which imports nothing that
      reaches the database. Create `ApplicationMigrationRecorder` and the `MigrationRecordStore`
      protocol in `backend/infrahub/core/schema_change/application_migration_recorder.py`,
      following the contract. `ApplicationMigrationRecorder` takes a `MigrationRecordStore` and
      the application ID in its constructor, and identifies every migration by its position. A
      failure to write a record is logged and does not raise. Load
      `dev/guidelines/backend/exceptions.md` before writing the `try`/`except`. Add
      `build_migration_recorder(db, application_id)` to `factory.py`. Make T025 pass.
- [ ] T035 [US2] Carry the application ID from the coordinator to the migration flow. Load
      `dev/guidelines/backend/prefect-payloads.md` first.
      - In `core/migrations/schema/models.py::SchemaApplyMigrationData`, add
        `application_id: str | None = None`. Replace the hand-written `serialize_model`, which
        returns six keys and would drop the new field before it reaches a task worker, with
        `@field_serializer` functions for the four fields that need one (`branch`,
        `previous_schema`, `new_schema`, `at`). A field added later then serializes by default.
      - Extend
        `backend/tests/component/core/migrations/schema/test_models.py::test_SchemaApplyMigrationData_serializer`:
        build the message with an application ID, dump it to JSON, rebuild it from the JSON, and
        assert the application ID, the user ID and the timestamp on the rebuilt object against
        literal values.
      - In `core/schema/update_coordinator.py::SchemaUpdateCoordinator.execute`, remove the
        argument `update_registry` and the three overloads. No caller passes `False`. `execute`
        always returns `str`, and `_update_schema` always sets the schema in the registry.
      - Add `application_id: str | None` to `execute` as a keyword argument without a default,
        and pass it to `_run_migrations`, which puts it in the message.
      - Change the callers of `execute`: `api/schema.py::load_schema`, `cli/db.py` (core schema
        update), `core/branch/tasks.py` (rebase), `core/merge/orchestrator.py`, and the two
        calls in `backend/tests/component/core/schema_manager/test_schema_rollback.py`. Each
        drops `update_registry=True` where it passes it, and passes `application_id=None`.
        `load_schema` passes the real value from T038 on.
      - Run `backend/tests/component/core/schema_manager/test_schema_rollback.py`,
        `backend/tests/component/core/test_branch_rebase.py` and
        `backend/tests/component/core/merge/test_orchestrator.py`. Their expected results do not
        change.
- [ ] T036 [US2] Change the flow in `core/migrations/schema/tasks.py` so that it reports each
      migration by its position in the message. Today `schema_apply_migrations` splits the
      migrations into two lists, and `_apply_migration_batch` reads results in the order they
      complete, so an index inside that function is not the position in the message.
      - Add a frozen dataclass
        `PositionedMigration(position: int, migration: SchemaUpdateMigrationInfo)`. The flow
        builds the list once from `enumerate(message.migrations)`.
      - `split_migrations_by_phase` takes and returns `PositionedMigration` items.
      - `schema_apply_migrations` calls `get_database()` once at its top, builds the
        `MigrationRecorder` with `build_migration_recorder` from that database and the
        application ID of the message, and calls `register` with all the migrations before the
        first phase. The flow imports the interface only.
      - `_apply_migration_batch` takes the `PositionedMigration` items of one phase, the
        recorder and the database, and no longer calls `get_database()`. It calls
        `batch_started` with the positions of the phase. Each entry of the batch is a small
        typed coroutine function that awaits `schema_path_migrate` and returns the position
        with the result. It calls `migration_ended` with that position each time a result
        arrives.
      - When the recorder reads `migration_name` or `schema_path` of
        `SchemaMigrationPathResponseData`, make both fields required: `schema_path_migrate`
        always sets them.
      - In `backend/tests/unit/core/migrations/schema/test_tasks.py`, change the two tests of
        `split_migrations_by_phase` to the new input type, and add a case: kind-update
        migrations placed between other migrations keep their positions in the message after
        the split.

      The return value of the flow is unchanged.

### The load

- [ ] T037 [US2] Create `SchemaChangeApplicationRunner` in
      `backend/infrahub/core/schema_change/application_runner.py`, with the `ApplicationRecorder`
      and `SchemaUpdateExecutor` protocols of the contract declared beside it.
      `SchemaUpdateExecutor.execute` has the arguments the runner passes, each with a required
      type: `branch`, `origin_schema`, `rollback_schema`, `candidate_schema`, `at`, `context`,
      `diff`, `migrations`, `limit`, `user_id` and `application_id`. The runner takes both
      protocols in its constructor and imports neither `SchemaChangeRecorder` nor
      `SchemaUpdateCoordinator`. Write the success path: `recorder.start`, `executor.execute`
      with the application ID, the `user_id` and the `context` it received, and the diff,
      migrations and `limit` of the candidate, then `recorder.complete`. Phase 5 adds the
      failure path. Add `build_schema_change_recorder(db, default_branch_name)` and
      `build_schema_change_application_runner(db, executor, default_branch_name)` to
      `factory.py`.
- [ ] T038 [US2] Change `api/schema.py::load_schema` to build the coordinator and the runner at
      its top, after the permission checks and before the schema lock, next to the candidate
      builder of T019. It builds the runner with `build_schema_change_application_runner`, and
      passes the coordinator as `executor` and `registry.default_branch` as
      `default_branch_name`. Call `runner.run` with the `SchemaCandidate` of T019 in place of
      `coordinator.execute`, with `user_id=account_session.account_id` and the copy of the
      context that has the priority `HIGH`, as the call to the coordinator has today. The lock,
      the constraint workflow, the early return for an empty diff, the hash refresh, the event
      and the response are unchanged. Make the methods of T027 pass.

### The query

- [ ] T039 [P] [US2] Create the GraphQL types of
      [contracts/schema-change-history.graphql](contracts/schema-change-history.graphql) in
      `backend/infrahub/graphql/types/schema_change.py`. Build the enumerations from the Python
      enumerations with one-line descriptions, as `backend/infrahub/graphql/types/preferences.py`
      does. Use `GenericScalar` from `backend/infrahub/graphql/scalars.py` for `value` and
      `previous_value`.
- [ ] T040 [US2] Create two data loaders in `backend/infrahub/graphql/loaders/schema_change.py`,
      in the style of `backend/infrahub/graphql/loaders/account.py`: one that loads a page of
      operations for each schema change ID, keyed by `limit` and `offset`, and one that loads the
      applications with their migration records for each schema change ID. Each loader reads
      through `SchemaChangeHistoryReader` and runs one query for all the IDs of a request.
- [ ] T041 [US2] Create the resolver and the field `InfrahubSchemaChange` in
      `backend/infrahub/graphql/queries/schema_change.py`, in the style of
      `graphql/queries/branch.py::infrahub_branch_resolver`. It reads the branch from the GraphQL
      context, refuses a `limit` below 1 or above the maximum and an `offset` below 0 with
      `ValidationError`, opens its own read-only database session, builds a
      `SchemaChangeHistoryReader` on it, and reads `edges` and `count` only when the request
      selects them. The `operations` and `applications` fields resolve
      through the loaders of T040.
- [ ] T042 [US2] Export the field from `backend/infrahub/graphql/queries/__init__.py`, add it to
      `InfrahubBaseQuery` in `backend/infrahub/graphql/schema.py`, and add `InfrahubSchemaChange`
      to `QUERIES_REQUIRING_AUTHENTICATION` in the same file. Make T026 and T028 pass.
- [ ] T043 [US2] Regenerate the generated files and commit them: `uv run invoke
      schema.generate-graphqlschema` for `schema/schema.graphql`, then `cd frontend/app && pnpm
      codegen:graphql` for `frontend/app/src/shared/api/graphql/generated/`. Do not edit either
      by hand.

**Checkpoint**: user stories 1 and 2 work together. A load that succeeds is in the history.

---

## Phase 5: User Story 3 — a schema owner views why a schema load failed (P2)

**Goal**: a load that fails after its application started leaves a failed schema change, the
error, and the status of each migration.

**Independent Test**: make one migration of a load fail, then query the history
([quickstart.md](quickstart.md), section 3).

### Tests (write first)

- [ ] T044 [P] [US3] Add component tests of `fail` to
      `backend/tests/component/core/schema_change/test_recorder.py`:
      - `fail` sets the schema change and the application to `failed` and stores the error
        (FR-060);
      - the schema change gets no version and no parent (FR-032);
      - a migration record that was `applied` becomes `rolled_back`, and a record that was
        `failed`, `running` or `waiting` keeps its status (spec, decision 6);
      - the next schema change completed on the branch gets the next version, and its parent is
        the last applied schema change.
- [ ] T045 [P] [US3] Write the unit tests of the runner in
      `backend/tests/unit/core/schema_change/test_application_runner.py`. Add to
      `backend/tests/unit/core/schema_change/helpers.py` an `ApplicationRecorder` and a
      `SchemaUpdateExecutor` that record their calls in order, and one of each that raises. No
      mock library, and no database:
      - when the executor raises, the runner calls `fail` with the text of the error and raises
        the same exception;
      - when `fail` raises as well, the runner still raises the executor's exception, and the
        failure of `fail` is logged;
      - on success the runner calls `start`, then the executor with the application ID, then
        `complete`, in that order, and returns the hash;
      - the executor receives the `user_id` and the `context` that `run` received;
      - `complete` receives the `branch` that `start` received.
- [ ] T046 [US3] Add the failed load methods to `TestSchemaChangeHistory` in
      `backend/tests/functional/schema_change/test_schema_change_history.py`, after the methods
      of T028 and before the deletion. They continue from the three applied schema changes of
      the class and load nothing again. Make a migration fail as
      `backend/tests/integration/schema_lifecycle/test_schema_load_rollback.py` does, with a
      migration class that returns an error and a function-scoped fixture that puts it in
      `MIGRATION_MAP` and restores the map:
      - the branch schema and the data are as they were before the load;
      - the history holds the schema change with the status `failed`, no version, and an
        application with the status `failed` and the error (FR-060, FR-061);
      - the migration records show which migration failed;
      - the query lists the applied schema changes by version, then the failed one (FR-071);
      - a corrected load that succeeds gets the next version, with the last applied schema change
        as its parent;
      - the failed schema change is still listed after that load (FR-062).

### Implementation

- [ ] T047 [US3] Add the query that marks a schema change and its application failed to
      `backend/infrahub/core/query/schema_change.py`: it sets both statuses, stores the error on
      the application, and sets the migration records of the application that are `applied` to
      `rolled_back`, in one query. Add the repository method in
      `backend/infrahub/core/schema_change/repository.py`.
- [ ] T048 [US3] Add `fail` to `SchemaChangeRecorder` in
      `backend/infrahub/core/schema_change/recorder.py`. Make T044 pass.
- [ ] T049 [US3] Add the failure path to `SchemaChangeApplicationRunner.run` in
      `backend/infrahub/core/schema_change/application_runner.py`: catch the exception that
      `executor.execute` raises after its rollback, call `recorder.fail`, log a
      failure of `recorder.fail` itself, and raise the original exception. Load
      `dev/guidelines/backend/exceptions.md` first. Make T045 and T046 pass.

**Checkpoint**: a failed load is in the history with its error.

---

## Phase 6: User Story 4 — a dropdown or enum mutation is part of the history (P2)

**Goal**: each dropdown or enum mutation that changes the schema stores one applied schema change.

**Independent Test**: add a choice to a dropdown attribute through the mutation, then query the
history ([quickstart.md](quickstart.md), section 2).

- [ ] T050 [P] [US4] Write the component tests in
      `backend/tests/component/graphql/mutations/test_schema_dropdown_and_enum_history.py`, as
      one ordered class. Add a `choices_schema_scope_class` fixture beside `choices_schema` in
      `backend/tests/component/conftest.py`, on `node_group_schema_scope_class` and
      `default_branch_scope_class`, with the body of the two fixtures in one shared function.
      The schema and the nodes are then loaded once for the class. The methods run in the order
      they are defined, and each continues from the history the one before it left:
      - `SchemaDropdownAdd` stores one schema change with the status `applied`, version 1, no
        parent, one `element_property` operation on `choices` with the list before the change,
        and one application with the status `applied` and no migration record. The previous
        value of the operation is the list of the branch schema;
      - `SchemaDropdownRemove`, then `SchemaEnumAdd`, then `SchemaEnumRemove` each store one
        more, with the next version and the one before as its parent;
      - a mutation that is refused, for a choice that already exists or a value still in use,
        stores none, and the history is the same as before it;
      - `applied_at` of each schema change equals the timestamp at which the schema was saved.
- [ ] T051 [US4] Change `graphql/mutations/schema.py::apply_attribute_property_change` to take
      one `Timestamp` and to store the records. Inside its `db.start_transaction()` block, build
      the recorder with `build_schema_change_recorder` on the database handle of the
      transaction, and call `SchemaChangeRecorder.record_applied` with the operation of T020
      first, before `registry.schema.update_schema_branch`. `update_schema_branch` replaces the
      schema in the registry of the process before the transaction commits, so a record write
      that failed after it would leave the registry ahead of the database
      ([research.md](research.md), R11). Pass the timestamp to both calls. Nothing is stored
      when the diff is empty. Make T050 pass, and run the existing tests of these four mutations
      in `backend/tests/component/graphql/mutations/test_schema.py`.

**Checkpoint**: every way of changing a schema from user input is in the history.

---

## Phase 7: User Story 5 — deleting a branch deletes its records (P3)

**Goal**: the records of a deleted branch are deleted, and no other record changes.

**Independent Test**: load schema changes on a branch, including one that fails, delete the
branch, and count the records ([quickstart.md](quickstart.md), sections 2 and 3).

- [ ] T052 [P] [US5] Write the component tests in
      `backend/tests/component/core/schema_change/test_delete_by_branch.py`, as one ordered
      class with `BranchDataDeleter(db=db, batch_size=5)`, as
      `backend/tests/component/core/test_branch.py` builds it. One class-scoped fixture requests
      `empty_database_scope_class` and no schema fixture, and seeds with the function of T023:
      main, a branch to delete and a second branch. The branch to delete gets a number of schema
      changes that is derived from the batch size and is not a multiple of it (two batches plus
      one), one of them failed, and its first schema change has a schema change of main as its
      parent. The methods, in order:
      - before the deletion, the records of the three branches are the ones seeded;
      - after `delete_branch_data`, no schema change, operation, application or migration record
        of the branch remains, including those of the failed schema change (FR-081);
      - the records of main and of the second branch are the same as before, including main's
        schema change that was the parent of the deleted branch's first schema change (FR-082);
      - a second call deletes nothing and raises nothing, and the records of main and of the
        second branch are still the same.
- [ ] T053 [US5] Add the query that deletes the records of a branch to
      `backend/infrahub/core/query/schema_change.py`. It selects up to a batch of schema changes
      by their `branch` property, deletes each with its operations, applications and migration
      records, and returns the number of schema changes deleted. Add no repository method: the
      deleter runs the query itself ([research.md](research.md), R1 and R13).
- [ ] T054 [US5] Add a step to `core/branch/data_deleter.py::BranchDataDeleter.delete_branch_data`
      that runs the query of T053 with the deleter's batch size until a run deletes nothing, in
      the way `_delete_edges` loops. The value that `delete_branch_data` returns stays the number
      of edges its existing steps removed; log the number of schema changes deleted. Make T052
      pass.
- [ ] T055 [US5] Add the branch deletion methods to `TestSchemaChangeHistory` in
      `backend/tests/functional/schema_change/test_schema_change_history.py`, as the last
      methods of the class. Read the records of the branch, which include the failed schema
      change of T046, and the records of main. Delete the branch through the `BranchDelete`
      mutation, then confirm that no record of the branch remains and that the records of main
      are the same as before.

**Checkpoint**: all five user stories work.

---

## Phase 8: Documentation and polish

- [ ] T056 [P] Write the functional test that the records are outside the branch-aware graph,
      as a second class `TestSchemaChangeRecordsUntouched(TestSchemaChangeBase)` in
      `backend/tests/functional/schema_change/test_schema_change_records_untouched.py`. It uses
      the data set of T027 and is separate from `TestSchemaChangeHistory` because a merge
      changes main. One class-scoped fixture loads a schema change on main and one on the
      branch. Take a snapshot of the records of main and of the branch, then run a rebase of
      the branch and a merge of the branch. After each one, the records, their fields and their
      edges are the same (FR-008, FR-080).
- [ ] T057 [P] Add an assertion to `backend/tests/integration_docker/test_schema_migration.py`:
      after a load whose migrations run on a task worker, `InfrahubSchemaChange` returns the
      schema change with the status `applied` and its migration records with the status
      `applied`.
- [ ] T058 [P] Add a changelog fragment of type `added` with the `creating-changelog-entries`
      skill. Before writing it, check each claim against the diff: the name of the query, that it
      needs a logged-in account, and what stores a schema change.
- [ ] T059 [P] Document the history query for users in `docs/docs/schema/create-and-load.mdx`, in
      a section on viewing the schema changes of a branch, with the
      `opsmill-product:writing-infrahub-docs` skill when it is installed: what a schema change, an application and a migration are, an example query, and the
      statuses. Run `uv run invoke docs.lint`.
- [ ] T060 [P] Write `dev/knowledge/backend/schema-changes.md`: the records and their edges, why
      the edges have no `branch` property, how a load, a check and a mutation build their schema
      with the applier, when each status is set, and what keeps the status `running`. Load
      `dev/guidelines/documentation.md` first. Add the document to the knowledge list of
      `backend/AGENTS.md`.
- [ ] T061 Run `uv run invoke format`, then `uv run invoke lint`, and fix what they report without
      a new suppression.
- [ ] T062 Run `uv run invoke schema.validate-graphqlschema` and `uv run invoke docs.validate`,
      and confirm that the generated front-end GraphQL types are committed.
- [ ] T063 Run every section of [quickstart.md](quickstart.md) and correct the file where a
      command or an expected result differs from what the code does.
- [ ] T064 Read the diff against every claim in [spec.md](spec.md), [plan.md](plan.md),
      [research.md](research.md), [data-model.md](data-model.md) and [contracts/](contracts/),
      and correct each file where the code differs.

---

## Dependencies

- **Phase 1** then **Phase 2** block everything.
- **Phase 3 (US1)** blocks phases 4 to 8. T017 is the gate.
- **Phase 4 (US2)** blocks phases 5, 6 and 7, which use the repository, the recorder and the
  query module.
- **Phases 5 (US3), 6 (US4) and 7 (US5)** do not depend on each other.
- **Phase 8** comes last. T056 needs phase 4. T057 needs phase 4. T058 to T060 need all stories.

Inside phase 3: T006 before T007 to T014. T015 and T016 before T017. T017 before T018. T018 before
T019 and T020. T021 and T022 after T020.

Inside phase 4: T029 before T030 and T031. T030 and T031 before T032. T032 before T033 and T034.
T035 before T036 and T037. T033, T034, T036 and T037 before T038. T039 before T040 and T041.
T041 before T042. T042 before T043. T023 before T024, T025 and T026. T027 before T028.

Across phases, in `test_schema_change_history.py`: T027, then T028, then T046, then T055. The
methods of one class run in the order they are defined.

## Parallel opportunities

- T003 and T005 in phase 2.
- T008 to T014 in phase 3, after T006: seven test modules in seven files.
- T024 to T026 in phase 4, after T023, which writes the seeding function they use. T027 then
  T028 write one class in one file, in that order. T039 can start while T029 to T038 are in
  progress.
- T044 and T045 in phase 5. T046 adds to the class of T027, after T028.
- Phases 5, 6 and 7 can run at the same time after phase 4, with one exception: T047 and T053
  both change `core/query/schema_change.py`.
- T056 to T060 in phase 8.

## Implementation strategy

1. Phases 1 to 3 first. They change how a schema is built and store nothing. Stop at the
   checkpoint and confirm the gate.
2. Phase 4 adds the records and the query for a load that succeeds.
3. Phases 5 to 7 each add one behaviour to the records.
4. Phase 8 documents and validates the whole.

## Task count

| Phase | Tasks | Count |
| --- | --- | --- |
| 1. Setup | T001 to T002 | 2 |
| 2. Foundational | T003 to T005 | 3 |
| 3. User Story 1 | T006 to T022 | 17 |
| 4. User Story 2 | T023 to T043 | 21 |
| 5. User Story 3 | T044 to T049 | 6 |
| 6. User Story 4 | T050 to T051 | 2 |
| 7. User Story 5 | T052 to T055 | 4 |
| 8. Documentation and polish | T056 to T064 | 9 |
| Total | | 64 |
