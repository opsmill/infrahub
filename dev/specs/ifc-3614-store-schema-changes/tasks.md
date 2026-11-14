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
- When a task changes a value that another file of this directory states (a field, a status, an
  order, a page size), update every file of `dev/specs/ifc-3614-store-schema-changes/` that
  states it, in the same commit.

---

## Phase 1: Setup

**Purpose**: the packages and the constants that every later task imports.

- [ ] T001 [P] Create the package `backend/infrahub/core/schema_change/` with an empty
      `__init__.py`, and the test packages `backend/tests/unit/core/schema_change/`,
      `backend/tests/component/core/schema_change/` and `backend/tests/functional/schema_change/`,
      each with an empty `__init__.py`.
- [ ] T002 Create `backend/infrahub/core/schema_change/constants.py`, with constant values only.
      Load `dev/guidelines/constants.md` first. It holds:
      - `SchemaChangeStatus`: `staged`, `running`, `applied`, `failed`;
      - `SchemaChangeApplicationStatus`: `running`, `applied`, `failed`, `rolled_back`, `skipped`;
      - `SchemaChangeMigrationStatus`: `waiting`, `running`, `applied`, `failed`, `rolled_back`;
      - `SchemaOperationType`: `node_add`, `node_remove`, `node_property`, `element_add`,
        `element_remove`, `element_property`;
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

- [ ] T003 [P] Write the unit tests of the operation model in
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
- [ ] T004 Create `backend/infrahub/core/schema_change/operations.py` with `SchemaOperation`, a
      Pydantic model with the fields `operation_type`, `kind`, `node_type`, `section`,
      `element_name`, `property_name`, `value` and `previous_value`, a model validator for the
      rules of T003, and two functions that build the summary of a list of operations and the
      name from a version and a summary ([research.md](research.md), R4 and R10). Make T003 pass.
- [ ] T005 [P] Add `SchemaOperationTargetNotFoundError` to `backend/infrahub/exceptions.py`. Its
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

- [ ] T006 [US1] Create the helpers of the suite in
      `backend/tests/unit/core/schema_change/conftest.py`:
      - a function that builds a processed `SchemaBranch` from the internal schema, the core
        schema and a `SchemaRoot`, with an ID on every node, attribute and relationship
        (`SchemaRoot.generate_uuid`), as `_load_processed_branch` does in
        `backend/tests/unit/core/schema/test_schema_branch.py`;
      - a reference function that builds the result of a direct load with `SchemaBranch` calls
        only: `duplicate`, `load_schema`, `process`, `diff`, `validate_node_deletions`,
        `validate_update`. It must not call `SchemaCandidateBuilder`
        ([research.md](research.md), R14);
      - a function that compares two results: the hash of every node, generic, profile and
        template kind (`SchemaBranch.to_dict`), the migrations as a sorted list of migration name
        and schema path, and the constraints in the same form.

      Reuse the schemas of `backend/tests/helpers/schema/` and the fixtures of
      `backend/tests/unit/conftest.py` before defining a new schema.
- [ ] T007 [US1] Write the cases that the first spike covered in
      `backend/tests/unit/core/schema_change/test_applier_equivalence.py`. Each case builds the
      operations from a schema file with `SchemaOperationBuilder`, applies them with
      `SchemaChangeApplier`, and compares the result with the reference of T006:
      - adding an attribute to a generic;
      - turning on `generate_profile`;
      - making an attribute unique;
      - removing an attribute;
      - renaming an attribute on a node, and on a generic;
      - adding a node.
- [ ] T008 [P] [US1] Write the relationship cases in
      `backend/tests/unit/core/schema_change/test_applier_equivalence_relationships.py`: adding a
      relationship, removing one, renaming one, and changing `peer`, `cardinality`, `optional`
      and `kind`.
- [ ] T009 [P] [US1] Write the kind cases in
      `backend/tests/unit/core/schema_change/test_applier_equivalence_kinds.py`: renaming a kind,
      changing its namespace, adding a generic to `inherit_from`, and removing a generic.
- [ ] T010 [P] [US1] Write the remaining cases of FR-024 in
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
- [ ] T011 [P] [US1] Write the four known-bug cases of FR-025 in
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
- [ ] T012 [P] [US1] Write the tests of the operation builder in
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
      - the operations come in the order of [research.md](research.md), R5, whatever the order of
        the file;
      - every operation survives a JSON round trip: dump the list to JSON, load it, apply it, and
        get a schema with the same hash.
- [ ] T013 [P] [US1] Write the tests of the applier in
      `backend/tests/unit/core/schema_change/test_applier.py`:
      - an operation on a kind, an attribute or a relationship that the target does not have
        raises `SchemaOperationTargetNotFoundError`, and the message names the operation and the
        element (FR-023);
      - the target schema is unchanged after `apply`;
      - a property that no operation names keeps its value (FR-020);
      - the same target and operations give the same hash twice.
- [ ] T014 [P] [US1] Write the tests on a target that changed, in
      `backend/tests/unit/core/schema_change/test_applier_changed_target.py`. Record the
      operations against one schema, then apply them to a schema that changed separately:
      - "add an attribute to a generic", applied to a target that gained a kind that inherits the
        generic: the new kind has the attribute, and the migrations include it;
      - "change the label of an attribute", applied to a target where another property of the
        same kind changed: the target's own change is kept (FR-011).

### Implementation

- [ ] T015 [US1] Create `SchemaOperationBuilder` in
      `backend/infrahub/core/schema_change/operation_builder.py`, following
      [research.md](research.md), R5, and its contract in
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md). It lays the file over
      a copy of the branch schema, keeps that schema before processing, processes it, and keeps
      each path of the processed diff that the file states. Values are read from the schema before
      processing, previous values from the branch schema, and the name before a rename by the
      element's ID. It emits the operations in the order of R5.
- [ ] T016 [US1] Create `SchemaChangeApplier` in `backend/infrahub/core/schema_change/applier.py`,
      following [research.md](research.md), R6, and its contract. It duplicates the target,
      applies each operation in order, calls `BaseNodeSchema.apply_schema_path_updates` for each
      kind with the removed names and the map of renamed names, then runs `SchemaBranch.process`.
      `node_remove` sets the state of the kind to absent, as a load does.
- [ ] T017 [US1] Run `uv run pytest backend/tests/unit/core/schema_change/` and make T007 to T014
      pass. Each case of FR-025 passes or is a strict expected failure. When a case needs a change
      to the format of the operations, change `operations.py`, [data-model.md](data-model.md),
      [research.md](research.md) R4 to R6 and the GraphQL contract in the same commit. When the
      case of R6 shows that the path rewrite must run before the values are set, change the
      applier and R6. **This task is the gate for phases 4 to 8.**
- [ ] T018 [US1] Create `SchemaCandidate` and `SchemaCandidateBuilder` in
      `backend/infrahub/core/schema_change/candidate.py`, following the contract. `from_schema_root`
      and `from_operations` return the operations, the applier's schema and the
      `SchemaUpdateValidationResult` calculated from the diff between the branch schema and the
      applier's schema. `from_schema_root` logs a warning that names the kinds whose hash differs
      between the processed schema of the laid-over file and the applier's result. Add unit tests
      in `backend/tests/unit/core/schema_change/test_candidate.py`: both methods give the same
      diff, migrations and constraints for the same change, and a file that changes nothing gives
      an empty diff and no operation.
- [ ] T019 [US1] Change `api/schema.py::evaluate_candidate_schemas` to call
      `SchemaCandidateBuilder.from_schema_root` and keep its return type and the errors it raises
      (`SchemaNotValidError` for a `ValueError` and for validation errors). Change
      `api/schema.py::load_schema` to call the builder directly and keep the `SchemaCandidate`,
      so that phase 4 can store its operations. `check_schema` returns the diff of the applier's
      result (FR-021).
- [ ] T020 [US1] Change `graphql/mutations/schema.py::update_registry` and its four callers so
      that the mutation builds one `element_property` operation on `choices` or `enum`, with the
      list before the change as the previous value, and gets its schema from
      `SchemaChangeApplier` in place of `tmp_schema.set` and `tmp_schema.process`. The checks,
      the save and the event are unchanged (FR-002, FR-021).
- [ ] T021 [US1] Run the existing tests and confirm SC-002. Run each command on its own:
      `uv run invoke backend.test-unit`,
      `uv run pytest backend/tests/component/api/test_40_schema.py`,
      `uv run pytest backend/tests/component/core/schema_manager/`,
      `uv run pytest backend/tests/component/core/constraint_validators/`,
      `uv run pytest backend/tests/component/pools/test_schema_number_pool_scope.py`,
      `uv run pytest backend/tests/integration/schema_lifecycle/`,
      `uv run pytest backend/tests/functional/schemas/ backend/tests/functional/api/test_load_schema.py`.
      A test may change only when it asserts one of the four known bugs and the applier fixes it.
      For any other failure, fix the builder or the applier and add the case to the suite.
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

- [ ] T023 [P] [US2] Write the component tests of the repository in
      `backend/tests/component/core/schema_change/test_repository.py`, against Neo4j:
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
- [ ] T024 [P] [US2] Write the component tests of the recorder in
      `backend/tests/component/core/schema_change/test_recorder.py`:
      - `start` creates a schema change with the status `running`, no version and no parent, and
        an application with the status `running` and the timestamp given;
      - `complete` sets both to `applied`, assigns the version, the parent and `applied_at`;
      - three changes completed on main get the versions 1, 2 and 3, each with the one before as
        its parent, and the first with no parent (FR-030, FR-034);
      - a branch created when main was at version 2 gets 3 for its first schema change, with
        main's version 2 as its parent, and 4 for the next (FR-031);
      - two branches created from the same version of main each get that version plus 1;
      - main loads a schema, then a branch is created with a `branched_from` after the timestamp
        of that load: the branch's first schema change gets main's version plus 1
        ([research.md](research.md), R10);
      - a branch created with a `branched_from` before that timestamp gets main's version;
      - a `running` schema change on the branch does not change the next version (FR-032);
      - `record_applied` creates an applied schema change and an applied application in one call;
      - `start` and `record_applied` raise when the list of operations is empty (FR-003).
- [ ] T025 [P] [US2] Write the component tests of the migration recorder in
      `backend/tests/component/core/schema_change/test_migration_recorder.py`:
      - `register` creates the records with the status `waiting` (FR-052);
      - `batch_started` sets the records of the batch to `running`;
      - `migration_ended` with a result without error sets the record at that position to
        `applied` and stores `nbr_migrations_executed`, including the value 0 (FR-053);
      - `migration_ended` with errors sets the record to `failed` and stores the errors;
      - two migrations with the same name and path are updated separately, by position;
      - `NoRecordMigrationRecorder` writes nothing.
- [ ] T026 [P] [US2] Write the component tests of the query in
      `backend/tests/component/graphql/queries/test_schema_change.py`, in the style of
      `backend/tests/component/graphql/queries/test_branch.py`:
      - the query returns the schema changes of the branch of the request only;
      - `count` and `edges` follow `limit` and `offset`, and a page holds at most `limit` items
        (FR-072);
      - `name`, `version`, `status`, `created_at`, `updated_at`, `applied_at` and `parent` have
        the values of the contract;
      - `operations(limit, offset)` returns pages in the order of `position` with the count;
      - `applications` returns each application with its migrations, each with its path, name,
        status, result and errors (FR-070);
      - a request without a logged-in account is refused (FR-073);
      - a `limit` below 1 or above the maximum, and an `offset` below 0, are refused;
      - a branch with no schema change returns an empty page and a count of 0;
      - a page of several schema changes runs a fixed number of queries, whatever the number of
        schema changes on it. Count them with `CountingInfrahubDatabase` from
        `backend/tests/helpers/db_query_counter.py`.
- [ ] T027 [P] [US2] Add component tests of the load and the check to
      `backend/tests/component/api/test_40_schema.py`:
      - a load that changes the schema stores one schema change with the status `applied` and
        the operations of the file;
      - loading the same file a second time stores none (FR-003);
      - a load that only changes a label stores a schema change whose application has no
        migration record (FR-004);
      - a load that is refused for an invalid file, or for a constraint that existing nodes fail,
        stores none (spec, decision 1);
      - a schema check stores none, and returns the diff it returned before (FR-021).
- [ ] T028 [P] [US2] Write the functional test of the history in
      `backend/tests/functional/schema_change/test_schema_change_history.py`, with
      `TestInfrahubApp` and the schemas of `backend/tests/integration/schema_lifecycle/shared.py`
      or `backend/tests/helpers/schema/`. On a branch with nodes, load three files that each
      change the schema, then query `InfrahubSchemaChange` through GraphQL:
      - three applied schema changes with consecutive versions that start after main's version;
      - each name starts with its version in five digits;
      - an attribute added to a generic gives one operation on the generic, and one migration
        record for each migration that ran, with the status `applied`;
      - each schema change after the first has the one before as its parent.

### Records

- [ ] T029 [US2] Create the four `StandardNode` records in
      `backend/infrahub/core/schema_change/models.py`, with exactly the fields of
      [data-model.md](data-model.md):
      - `SchemaChange`: `branch: str`, `status: SchemaChangeStatus`, `version: int | None`,
        `summary: str`, `format_version: int`, `applied_at: str | None`;
      - `SchemaChangeOperation`: `position: int`, `operation_type: SchemaOperationType`,
        `kind: str`, `node_type: str | None`, `section: str | None`, `element_name: str | None`,
        `property_name: str | None`, `value` and `previous_value` as JSON-encoded text or `None`;
      - `SchemaChangeApplication`: `branch: str`, `status: SchemaChangeApplicationStatus`,
        `at: str`, `error: str | None`;
      - `SchemaChangeMigration`: `position: int`, `migration_name: str`, `path_type: str`,
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
      `backend/infrahub/core/schema_change/repository.py` with the methods of
      [data-model.md](data-model.md), "What the repository offers", except the two that phases 5
      and 7 add. It takes `db` in its constructor, converts `SchemaOperation` to and from
      `SchemaChangeOperation`, and returns typed results. Make T023 pass.
- [ ] T033 [US2] Create `SchemaChangeRecorder` and `SchemaChangeRecording` in
      `backend/infrahub/core/schema_change/recorder.py` with `start`, `complete` and
      `record_applied`, following the contract and [research.md](research.md), R8 and R10.
      `complete` and `record_applied` read the base version and the parent, then write the next
      version. `applied_at` is the application's `at`. Make T024 pass.

### Migration records

- [ ] T034 [US2] Create `MigrationRecorder`, `ApplicationMigrationRecorder` and
      `NoRecordMigrationRecorder` in `backend/infrahub/core/schema_change/migration_recorder.py`,
      following the contract. A failure to write a record is logged and does not raise. Load
      `dev/guidelines/backend/exceptions.md` before writing the `try`/`except`. Make T025 pass.
- [ ] T035 [US2] Add `application_id: str | None = None` to
      `core/migrations/schema/models.py::SchemaApplyMigrationData`, and an optional
      `application_id` argument to `core/schema/update_coordinator.py::SchemaUpdateCoordinator.execute`,
      to its three overloads and to `_run_migrations`, which puts it in the message. Load
      `dev/guidelines/backend/prefect-payloads.md` first.
- [ ] T036 [US2] Change `core/migrations/schema/tasks.py::schema_apply_migrations` to build the
      `MigrationRecorder` at its top: `ApplicationMigrationRecorder` with a repository on the
      database of the flow when the message has an application ID, `NoRecordMigrationRecorder`
      otherwise. It calls `register` with all the migrations before the first batch. Change
      `_apply_migration_batch` to take the recorder, call `batch_started`, keep the position of
      each migration it submits, and call `migration_ended` with that position each time a result
      arrives. The return value of the flow is unchanged.

### The load

- [ ] T037 [US2] Create `SchemaChangeApplicationRunner` in
      `backend/infrahub/core/schema_change/application_runner.py` with the success path of the
      contract: `recorder.start`, `SchemaUpdateCoordinator.execute` with the application ID and
      the diff, migrations and `limit` of the candidate, then `recorder.complete`. Phase 5 adds
      the failure path.
- [ ] T038 [US2] Change `api/schema.py::load_schema` to build the repository, the recorder, the
      coordinator and the runner next to where it builds the coordinator today, and to call
      `runner.run` with the `SchemaCandidate` of T019 in place of `coordinator.execute`. The lock,
      the constraint workflow, the early return for an empty diff, the hash refresh, the event
      and the response are unchanged. Make T027 pass.

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
      applications with their migration records for each schema change ID. Each loader runs one
      query for all the IDs of a request.
- [ ] T041 [US2] Create the resolver and the field `InfrahubSchemaChange` in
      `backend/infrahub/graphql/queries/schema_change.py`, in the style of
      `graphql/queries/branch.py::infrahub_branch_resolver`. It reads the branch from the GraphQL
      context, refuses a `limit` below 1 or above the maximum and an `offset` below 0 with
      `ValidationError`, opens its own read-only database session, and reads `edges` and `count`
      only when the request selects them. The `operations` and `applications` fields resolve
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
      `backend/tests/unit/core/schema_change/test_application_runner.py`, with a recorder and a
      coordinator written for the test that record their calls and can raise. No mock library:
      - when the coordinator raises, the runner calls `fail` with the text of the error and
        raises the same exception;
      - when `fail` raises as well, the runner still raises the coordinator's exception;
      - on success the runner calls `start`, then the coordinator with the application ID, then
        `complete`, and returns the hash.
- [ ] T046 [P] [US3] Write the functional test of a failed load in
      `backend/tests/functional/schema_change/test_schema_change_failed_load.py`. Make a
      migration fail as
      `backend/tests/integration/schema_lifecycle/test_schema_load_rollback.py` does, with a
      migration class that returns an error:
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
      `SchemaUpdateCoordinator.execute` raises after its rollback, call `recorder.fail`, log a
      failure of `recorder.fail` itself, and raise the original exception. Load
      `dev/guidelines/backend/exceptions.md` first. Make T045 and T046 pass.

**Checkpoint**: a failed load is in the history with its error.

---

## Phase 6: User Story 4 — a dropdown or enum mutation is part of the history (P2)

**Goal**: each dropdown or enum mutation that changes the schema stores one applied schema change.

**Independent Test**: add a choice to a dropdown attribute through the mutation, then query the
history ([quickstart.md](quickstart.md), section 2).

- [ ] T050 [P] [US4] Write the component tests in
      `backend/tests/component/graphql/mutations/test_schema_dropdown_and_enum_history.py`:
      - `SchemaDropdownAdd` stores one schema change with the status `applied`, one
        `element_property` operation on `choices` with the list before the change, and one
        application with the status `applied` and no migration record;
      - `SchemaDropdownRemove`, `SchemaEnumAdd` and `SchemaEnumRemove` each store one;
      - a mutation that is refused, for a choice that already exists or a value still in use,
        stores none;
      - the schema change gets the next version of the branch and the right parent;
      - `applied_at` equals the timestamp at which the schema was saved.
- [ ] T051 [US4] Change `graphql/mutations/schema.py::update_registry` to take one `Timestamp`,
      pass it to `registry.schema.update_schema_branch` as `at`, and, inside the same
      `db.start_transaction()` block, call `SchemaChangeRecorder.record_applied` with the
      operation of T020, built on a repository that uses the database handle of the transaction
      ([research.md](research.md), R11). Nothing is stored when the diff is empty. Make T050 pass,
      and run the existing tests of these four mutations in
      `backend/tests/component/graphql/mutations/test_schema.py`.

**Checkpoint**: every way of changing a schema from user input is in the history.

---

## Phase 7: User Story 5 — deleting a branch deletes its records (P3)

**Goal**: the records of a deleted branch are deleted, and no other record changes.

**Independent Test**: load schema changes on a branch, including one that fails, delete the
branch, and count the records ([quickstart.md](quickstart.md), sections 2 and 3).

- [ ] T052 [P] [US5] Write the component tests in
      `backend/tests/component/core/schema_change/test_delete_by_branch.py`, with
      `BranchDataDeleter(db=db, batch_size=5)` as `backend/tests/component/core/test_branch.py`
      does:
      - after `delete_branch_data`, no schema change, operation, application or migration record
        of the branch remains, including those of a failed schema change (FR-081);
      - the records of main and of a second branch are unchanged, including main's schema change
        that is the parent of the deleted branch's first schema change (FR-082);
      - more records than the batch size are all deleted;
      - a second call deletes nothing and raises nothing.
- [ ] T053 [US5] Add the query that deletes the records of a branch to
      `backend/infrahub/core/query/schema_change.py`. It selects up to a batch of schema changes
      by their `branch` property, deletes each with its operations, applications and migration
      records, and returns the number of schema changes deleted. Add the repository method in
      `backend/infrahub/core/schema_change/repository.py`.
- [ ] T054 [US5] Add a step to `core/branch/data_deleter.py::BranchDataDeleter.delete_branch_data`
      that runs the query of T053 with the deleter's batch size until a run deletes nothing, in
      the way `_delete_edges` loops. Make T052 pass.
- [ ] T055 [P] [US5] Add a functional test to
      `backend/tests/functional/schema_change/test_schema_change_history.py`: delete the branch
      through the `BranchDelete` mutation, then confirm that the history of main is unchanged and
      that no record of the branch remains.

**Checkpoint**: all five user stories work.

---

## Phase 8: Documentation and polish

- [ ] T056 [P] Write the functional test that the records are outside the branch-aware graph, in
      `backend/tests/functional/schema_change/test_schema_change_records_untouched.py`. Take a
      snapshot of the records of main and of a branch, then run a rebase of the branch and a
      merge of the branch. After each one, the records, their fields and their edges are the same
      (FR-008, FR-080).
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
- **Phase 4 (US2)** blocks phases 5, 6 and 7, which use the repository and the recorder.
- **Phases 5 (US3), 6 (US4) and 7 (US5)** do not depend on each other.
- **Phase 8** comes last. T056 needs phase 4. T057 needs phase 4. T058 to T060 need all stories.

Inside phase 3: T006 before T007 to T014. T015 and T016 before T017. T017 before T018. T018 before
T019 and T020. T021 and T022 after T020.

Inside phase 4: T029 before T030 and T031. T030 and T031 before T032. T032 before T033 and T034.
T035 before T036 and T037. T033, T034, T036 and T037 before T038. T039 before T040 and T041.
T041 before T042. T042 before T043.

## Parallel opportunities

- T003 and T005 in phase 2.
- T008 to T014 in phase 3, after T006: seven test modules in seven files.
- T023 to T028 in phase 4: six test modules. T039 can start while T029 to T038 are in progress.
- T044, T045 and T046 in phase 5.
- Phases 5, 6 and 7 can run at the same time after phase 4, with one exception: T047 and T053
  both change `core/query/schema_change.py` and `repository.py`.
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
