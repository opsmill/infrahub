# Research: store schema changes and query the schema change history of a branch

Each entry gives the decision, the reason and the alternatives that were rejected. Code is named by
module and symbol. Paths are relative to `backend/infrahub/` unless they start with another
directory.

Sources: [spec.md](spec.md), the Jira task
[IFC-3614](https://opsmill.atlassian.net/browse/IFC-3614), the design document
[INFP-719](https://app.notion.com/p/opsmill/INFP-719-Make-schema-migrations-visible-402228b830258193b43ed097d965f633)
(section B), and the code on this branch.

## How a schema changes today

Three paths change the schema of a branch from user input. They do not share one way of building
the schema.

| Path | Builds the schema | Checks and migrations | Saves | On failure |
| --- | --- | --- | --- | --- |
| `POST /api/schema/load` (`api/schema.py::load_schema`) | `evaluate_candidate_schemas`: duplicate the branch schema, `SchemaBranch.load_schema`, `process`, `diff`, `validate_node_deletions`, `validate_update` | Constraint workflow, then migrations through `core/schema/update_coordinator.py::SchemaUpdateCoordinator` | `SchemaManager.update_schema_branch` with the diff, at one timestamp | The coordinator rolls the graph back at that timestamp and restores the registry |
| `POST /api/schema/check` (`api/schema.py::check_schema`) | The same helper | Constraint workflow only | Nothing | Nothing to roll back |
| Dropdown and enum mutations (`graphql/mutations/schema.py::update_registry`) | Duplicate the branch schema, `set` the changed kind, `process`, `diff` | None. The remove mutations run their own "still in use" query | `update_schema_branch` with `limit`, inside one database transaction | The transaction rolls back |

A Git repository imports a schema through the SDK, which calls `POST /api/schema/load`, so it uses
the first path.

The migrations of a load run in the Prefect flow
`core/migrations/schema/tasks.py::schema_apply_migrations`. The flow returns only a list of error
strings. The result of each migration (`SchemaMigrationPathResponseData`: migration name, schema
path, errors, number of migrations executed) is dropped inside `_apply_migration_batch`.

## R1. The records are `StandardNode` vertices, read and written through a repository

**Decision**: four record types subclass `core/node/standard.py::StandardNode`: a schema change, a
schema change operation, an application and a migration record. Two classes take `db` in their
constructor and use the `Query` classes of `core/query/schema_change.py`:

- `SchemaChangeRepository` holds the writes and the version read. The recorder and the migration
  recorder use it.
- `SchemaChangeHistoryReader` holds the three paged reads. The history query uses it.

The deletion of a branch's records is not a method of either class.
`core/branch/data_deleter.py::BranchDataDeleter` runs that query itself, as it runs its other
queries (R13). See [data-model.md](data-model.md).

**Rationale**: the task asks for `StandardNode` vertices, not a core kind. `core/preferences/` is
the closest example: a `StandardNode` model, a repository and query classes with typed results.
The component guideline asks for that shape and says not to add persistence methods to a model.
The classes are split by consumer, so that the code that records a load does not depend on the
reads of the GraphQL query, and a change to what the query returns does not change the class that
the migration flow uses.
The repository creates operations and migration records in bulk with one query each, because a
schema change can hold many of them.

**Alternatives rejected**:

- A core kind: the task excludes it. A core kind would also be versioned by branch and copied by a
  merge.
- Calling `StandardNode.save()` for each record: one query for each operation and each migration.

## R2. Records are linked by edges that have no `branch` property

**Decision**: four new edge types link the records. None has a `branch`, `from`, `to` or `status`
property.

| Edge | From | To |
| --- | --- | --- |
| `SCHEMA_CHANGE_HAS_OPERATION` | schema change | operation |
| `SCHEMA_CHANGE_HAS_APPLICATION` | schema change | application |
| `SCHEMA_CHANGE_HAS_PARENT` | schema change | its parent schema change |
| `SCHEMA_APPLICATION_HAS_MIGRATION` | application | migration record |

Every record also gets the `IS_PART_OF` edge to `Root` that every `StandardNode` gets.

**Rationale**: the queries that rebase a branch, roll back a write, calculate a diff and delete a
branch's data select edges by their `branch` property (`core/query/branch.py::RebaseBranchQuery`,
`core/query/rollback.py`, `core/query/diff.py`). An edge without that property is not selected, so
a rollback of a failed load leaves the records in place, which FR-061 needs. The design document
says that no `StandardNode` class stores a link to another one today and that links by edges are
not tested. The diff records (`DiffRoot`, `DiffNode`) are the existing example of internal records
linked by their own edge types.

**Alternatives rejected**:

- ID properties instead of edges: the task asks for edges. The second spike used ID properties.
- Reusing `IS_RELATED` or another existing edge type: those are in
  `core/constants/database.py::DatabaseEdgeType`, and the branch deletion loops over that list.

## R3. No index and no graph migration

**Decision**: this feature adds no index, no constraint and no graph migration. `GRAPH_VERSION`
does not change.

**Rationale**:

- `Preference` and `TelemetrySnapshot` were added without a migration, an index or a change to
  `core/graph/schema.py`.
- The history query selects schema changes by the `branch` property with a label scan. The number
  of schema changes is the number of schema loads ever made, which is small next to the number of
  nodes.
- The migration flow updates the records it created a moment earlier. It selects them by element
  ID, which needs no index.
- An existing database needs no change: with no records, main's version is 0.

A new index needs approval first (`backend/AGENTS.md`, "Ask First"). An index on the `branch`
property of schema changes becomes worth asking for if the history query shows up in slow-query
logs.

## R4. The format of an operation

**Decision**: an operation is one of six types. It names its target by kind and name only.

| Type | Target | Holds |
| --- | --- | --- |
| `node_add` | a kind | the full definition as written, and whether it is a node or a generic |
| `node_remove` | a kind | nothing else |
| `node_property` | a property of a kind | the new value and the value before |
| `element_add` | an attribute or a relationship of a kind | the full definition as written |
| `element_remove` | an attribute or a relationship of a kind | nothing else |
| `element_property` | a property of an attribute or a relationship | the new value and the value before |

- A property can be nested, such as `parameters.regex`. The name is the dotted path that
  `core/models.py::SchemaUpdateValidationResult` already uses for nested properties.
- An added definition never holds `id` or `parameters.number_pool_id`.
- A rename is a property operation on `name` (or `namespace` for a kind). It names the element by
  the name it had before the load.
- The format has a version, `1`, stored on each schema change.

**Rationale**: this is the format of the design document, section B, which the first spike tested
in memory. The design document says that the format stays open until the equivalence test suite
passes, so the suite is the first work in `tasks.md` and no workflow uses the applier before it
passes.

**Alternatives rejected**, both tested by the first spike and recorded in the design document:

- Recording processed values: missed migrations on kinds that main added after branching.
- Recording the user's full definition of each changed kind: reverted main's changes to that kind.

## R5. How operations are built from a schema load

**Decision**: a `SchemaOperationBuilder` builds the operations in three steps. It returns the
operations and the processed schema of step 2, so that the candidate builder can compare that
schema with the applier's result without processing the file again (R7).

1. Lay the file over a copy of the branch schema with `SchemaBranch.load_schema`, as a load does
   today, and keep that schema before processing.
2. Process it and calculate the diff with the branch schema, as a load does today.
3. Keep each path of the processed diff that the file states. The value of the operation is read
   from the schema of step 1, before processing. The value before the change is read from the
   branch schema.

"The file states a path" means: the kind is in the file's nodes, generics or extensions, the
attribute or relationship is in the file under that kind, and the property is not `None` in the
file's model.

**Rationale**:

- The design document defines operations as "the paths in the processed diff that exist in the
  payload the user loaded, with the user's values".
- Reading the value from the schema before processing gives the user's value for every way a load
  sets a value (`core/models.py::HashableModel.update`): a scalar is replaced, a list of plain
  values is replaced whole, a list of dropdown choices is merged by name, and an empty string
  clears an optional text field (`core/schema/basenode_schema.py::BaseNodeSchema.update`).
- A path that processing produced is not stated in the file under that kind, so it is left out:
  the inherited copy of an attribute on each kind, a profile kind, a `human_friendly_id` calculated
  from a unique attribute.
- A rename is found by ID, as today. The diff keys a renamed element by its new name, so the
  builder reads the name before the load from the branch schema, by the element's ID
  (`SchemaBranch.get_by_id`, and the attribute and relationship maps of `BaseNodeSchema`).
- A file that changes nothing gives an empty processed diff, so no operation and no schema change
  (FR-003).

**Order of the operations** in one schema change:

1. removals of kinds, then additions of kinds, generics before nodes, each group by kind name;
2. then each changed kind, by kind name. Inside a kind: removals of attributes and relationships,
   additions, property changes other than a rename, renames of attributes and relationships, and
   last the rename of the kind itself.

Every operation that comes before a rename names the element by the name it had before the load.
The order is fixed so that the applier resolves each name against one schema, the summary of a
schema change does not depend on the order of the file, and a later task can follow a rename
through the operations after it.

**Alternative rejected**: the diff between the branch schema and the schema of step 1, without
processing. It would record a change that processing reverts, for example `unique: false` on an
attribute that a uniqueness constraint keeps unique, so loading the same file twice would store a
second schema change.

**Not known**: whether one rule covers every case in the equivalence list. The suite decides.

## R6. The applier

**Decision**: a `SchemaChangeApplier` takes a target `SchemaBranch` and a list of operations, and
returns a processed copy of the target.

1. Duplicate the target schema.
2. Apply each operation in order.
   - `node_add`: build the node or generic from the definition and `set` it.
   - `node_remove`: set the state of the kind to absent, as a load does for `state: absent`. The
     diff then reports the kind as removed, and `SchemaManager.update_schema_to_db` deletes it.
   - `node_property`: set the property. For `name` or `namespace`, delete the old kind and set the
     new one, as `SchemaBranch.load_schema` does for a renamed kind.
   - `element_add`, `element_remove`, `element_property`: change the list of attributes or
     relationships of the kind. The element keeps its ID, so the diff still reports a rename as a
     change of `name`.
3. For each kind, collect the names that the operations removed and the old-to-new map of the
   names they renamed, and call `BaseNodeSchema.apply_schema_path_updates`. That method takes
   names, not IDs.
4. Run `SchemaBranch.process` with the default branch schema.

An operation on a kind, attribute or relationship that the target does not have raises an error
that names the operation and the missing element (FR-023).

**Rationale**: these are the three steps of the design document. `apply_schema_path_updates` is
the method that today's load reaches through `handle_field_renames_and_deletes`.

**Risk to test**: today's load rewrites the paths first and then lays the file's values over them.
The applier sets the values first and then rewrites. The two orders differ when a file renames an
attribute and also writes `human_friendly_id` or another path list. The equivalence suite has a
case for it. If the results differ, the applier rewrites first.

## R7. One component builds the candidate schema for the load, the check and the mutations

**Decision**: a `SchemaCandidateBuilder` returns the operations, the processed candidate schema
and the `SchemaUpdateValidationResult` (diff, migrations, constraints, errors).

- From a schema file: build the operations (R5), apply them (R6), then `diff`,
  `validate_node_deletions` and `validate_update` on the applier's result.
- From operations: apply them, then the same three calls.

`api/schema.py::build_candidate_from_schemas` replaces `evaluate_candidate_schemas`. It takes the
candidate builder and the two schemas as arguments, merges the files of the request, calls the
builder and translates the errors to `SchemaNotValidError`. `load_schema` and `check_schema` both
call it, so neither holds a second copy of the merge or of the translation. Three component test
modules called `evaluate_candidate_schemas` for its schema and its validation result, not for the
translation; their five calls now call the builder directly, with the same expected results.
`check_schema` also calls `_validate_migrations`, which it copied before.
`graphql/mutations/schema.py::apply_attribute_property_change`, which replaces `update_registry`,
receives the kind, the attribute, the property and the new list. Inside the schema lock it reads
the list before the change from the branch schema, builds one
`element_property` operation on `choices` or `enum` and calls the builder with it ("From
operations" above). It reads the schema and the diff from the result. The mutation keeps its own
checks and its own save, and runs none of the migrations or constraints that the result lists.
`choices` and `enum` are constraint properties, so `validate_update` returns no error for them.
The diff then runs from the branch schema to the candidate, as a load's does; today's mutation
calculates it in the other direction.

**A difference is logged**: the builder holds two processed schemas, the one of the laid-over
file, which the operation builder returns, and the applier's result. A `SchemaCandidateComparer`
returns the kinds whose hash differs, and the builder logs a warning that names them. The
comparison is a component of its own, so that the candidate builder changes only when the way a
candidate is built changes. The builder does not refuse the load: the applier's result is the one
that is saved, and a known-bug case can differ on purpose. The equivalence suite covers the listed
cases; the warning reports any other case in production.

**Cost**: a load and a check now process the schema twice, once to find the operations and once in
the applier. The design document measured about 0.16 s to build the internal and core schema in
memory, and says the time on a schema of customer size is not measured. A task measures both
passes on the largest schema fixture in the repository.

**Alternative rejected**: saving the schema that step 2 of R5 already processed. FR-021 requires
the saved schema to come from the applier, so that a load and a later replay cannot differ.

## R8. A load records its schema change in three steps

**Decision**: a `SchemaChangeRecorder` owns the status of the records, and asks a
`SchemaChangeVersionResolver` for the version and the parent (R10). A
`SchemaChangeApplicationRunner` calls it around `SchemaUpdateCoordinator.execute`.

1. **Start**, after the constraint checks pass and before any write: create the schema change with
   the status `running` and no version, its operations, and one application with the status
   `running` and the timestamp that the coordinator uses for every write.
2. **Migrations**: the flow creates one migration record for each migration with the status
   `waiting`, sets a batch to `running` when it starts, and sets each record to `applied` or
   `failed` when its migration returns (R9).
3. **End**:
   - success: assign the version and the parent (R10), set the schema change and the application
     to `applied`, and store the time;
   - failure: set the schema change and the application to `failed`, store the error on the
     application, and set the migration records that were `applied` to `rolled back`.

The coordinator has already rolled the graph back when it raises, so the runner catches the
exception, records the failure and raises it again.

The runner depends on two `Protocol` classes declared beside it, one for the three recorder
methods it calls and one for `execute`. `SchemaChangeRecorder` and `SchemaUpdateCoordinator`
satisfy them. The unit tests of the runner pass a recording and a failing implementation of each,
without a database and without a mock library.

**Rationale**: the design document says that a load creates its schema change with the status
`running` before its migrations run, and that the code that handles a failure updates the records.
The runner is the code that the design lists in B's scope: "code that applies one schema change
from its operations, creates an application and a record for each migration it runs, and updates
their status". The staging task and the replay task apply a schema change that already exists,
so they extend the runner; this feature does not design for them.

**Known limit**: the write of the last step is not in the same transaction as the load. If it
fails, if the worker stops, or if the request is cancelled, the schema change keeps the status
`running`. Its operations are
stored, so a later recovery task can finish or fail it. Recovery after a worker stops during a
load is out of scope in the design document.

## R9. The migration flow writes the migration records

**Decision**: `core/migrations/schema/models.py::SchemaApplyMigrationData` gets an optional
application ID. `schema_apply_migrations` builds a migration recorder at its top and passes it to
`_apply_migration_batch`.

Three facts of the existing code shape this:

- `SchemaApplyMigrationData.serialize_model` returns six keys written by hand. A new field would
  be dropped when the message is serialized for a task worker, the flow would use the recorder
  that does nothing, and the load would end as `applied` with no migration record and no error.
  The tests that run the flow in the same process would not show it. The serializer is replaced
  by field serializers, and its test rebuilds the message from JSON.
- The flow splits the migrations into the kind updates and the others
  (`split_migrations_by_phase`) and runs `_apply_migration_batch` once for each list.
  `InfrahubBatch.execute` yields results in the order they complete. An index inside one list is
  therefore not the position in the message, and a result does not say which migration it
  belongs to. The flow pairs each migration with its position once (`PositionedMigration`), and
  each entry of the batch returns its position with its result.
- `_apply_migration_batch` calls `get_database()` for each migration. The flow now calls it once
  at its top and passes the database to the recorder factory and to the helper.

- With an application ID, the recorder creates the records, and updates one record each time a
  migration returns, from its `SchemaMigrationPathResponseData`.
- A record is identified by the position of its migration in the list of the message. The flow
  passes positions when a batch starts and with each result, because two migrations of one
  application can have the same name and the same schema path.
- The recorder that writes records depends on a `Protocol` with the two store methods it calls,
  which `SchemaChangeRepository` satisfies. A unit test passes a store that raises, to prove that
  a failed record write does not stop a migration.
- The interface is in a module that imports nothing that reaches the database. The recorder that
  writes records is in a second module, and `factory.py` selects the implementation from the
  application ID.
- Without one, a recorder that does nothing is used. A merge, a rebase and the core schema update
  have no application until their own tasks add one.

`SchemaUpdateCoordinator.execute` takes the application ID as a keyword argument without a
default and puts it in the message. The merge, the rebase and the core schema update pass `None`,
so each call shows that it records no migration. The same change removes the argument
`update_registry` and the three overloads of `execute`: no caller passes `False`, and one
signature is simpler to match with the `SchemaUpdateExecutor` protocol.

**Rationale**:

- The flow is the only place that receives each result as it completes.
- The application ID is a small identifier, which the Prefect payload guideline allows as a flow
  parameter.
- The progress task ([IFC-3619](https://opsmill.atlassian.net/browse/IFC-3619)) names the flow as
  the one writer of status and result. Writing each result when it arrives gives that task its
  live status without another change to the flow.
- The component guideline asks for an interface with a second implementation that does nothing,
  not an optional collaborator.

**Alternative rejected**: returning every result from the flow and writing the records in the API
server. The flow return value is persisted by Prefect and should stay small, and the records would
change only after the whole flow ends.

## R10. Versions, parents and names

**Decision**:

- The version is assigned when the schema change becomes `applied`: the highest version of the
  applied schema changes of the branch, plus 1.
- For the first schema change of a branch that is not main, the base is the highest version among
  main's schema changes whose `applied_at` is at or before the branch's `branched_from`, or 0.
- `applied_at` is the timestamp of the graph writes of the application, not the time the load
  ended. A load writes the schema at one timestamp taken when it starts. A branch created after
  that timestamp reads main's schema with the change in it, even while the load is still running
  its migrations, so the change is part of what the branch started from.
- The parent is the schema change that gave the base version. Main's first schema change, and a
  branch's first schema change when main has none, have no parent.
- The summary is stored. It comes from the first operation: the kind in lower case, the attribute,
  relationship or property name when there is one, and `add`, `remove` or `update`. With more
  operations it ends with `_and_<n>_more`.
- The name is not stored. It is `<version, five digits>_<summary>`, or the summary alone when the
  schema change has no version.

**Where the rule is**: a `SchemaChangeVersionResolver` takes a branch and returns the next
version and the ID of the parent. The recorder calls it when a schema change becomes `applied`.
It is a component of its own because the task that applies schema changes in order at rebase
assigns versions without creating a schema change, and because the rule can then be tested with a
few records.

**Rationale**: schema loads and the dropdown and enum mutations run inside
`lock.registry.global_schema_lock()`, so two schema changes cannot take the same version. A name
calculated from the version stays correct when a later task changes the version at rebase.

**Not in the sources**: the text of the count in the summary. The design document gives one
example, `00008_dcimgenericdevice_serial_add`, and says "with a count when there are more
operations".

## R11. A dropdown or enum mutation stores its records in its own transaction

**Decision**: `apply_attribute_property_change` stores the schema change, its operation and its
application, all with the status `applied`, inside the database transaction that saves the
schema. It calls the recorder first in the transaction, before
`SchemaManager.update_schema_branch`.

**Rationale**:

- These mutations run no migration: `choices` and `enum` are `validate_constraint` properties, and
  the mutation does not run the migration flow. The status `running` exists so that a client can
  follow migrations.
- In the database, either the schema and its records are saved, or neither is. A retry of the
  mutation after a database error (`retry_db_transaction`) leaves no failed record.
- The registry of the process is not part of the transaction. `update_schema_branch` replaces the
  branch schema in the registry before the commit. The recorder is called before it, so a failed
  record write leaves the registry unchanged. A failure of `update_schema_branch`, of the branch
  save or of the commit still leaves the registry ahead of the database, as today (R16).
- The list before the change is read from the branch schema inside the schema lock, not from the
  copy of the kind that each mutation reads before the lock.
- The save keeps `update_schema_branch(limit=...)`, which writes each listed kind again, although
  the mutation now holds a diff in the direction of a load (R16).
- The mutation takes one timestamp and passes it to `update_schema_branch` and to the recorder.
  Today the save takes no timestamp and uses the current time.

This differs from the design document, which says that a mutation also creates its schema change
with the status `running`. The spec records it as decision 7.

## R12. The history query

**Decision**: one GraphQL query, `InfrahubSchemaChange`, on the branch of the request. The
contract is in [contracts/schema-change-history.graphql](contracts/schema-change-history.graphql).

- Shape: `count` and `edges { node }`, with `limit` and `offset`, as
  `graphql/queries/branch.py::infrahub_branch_resolver` does. The `Preference` queries that the
  task names are not paginated; `InfrahubBranch` is the paginated query over `StandardNode`
  records.
- Order: applied schema changes by version, then the others by the time they were created.
- The resolver fetches `edges` and `count` only when the request selects them, and opens its own
  read-only database session.
- `operations` is a nested connection with its own `limit` and `offset`. `applications` is a list,
  each with its `migrations`.
- Nested fields are loaded with data loaders (`graphql/loaders/`), one query for the operations of
  every schema change on the page and one for their applications and migrations.
- Access: the query is added to `graphql/schema.py::QUERIES_REQUIRING_AUTHENTICATION`, as the
  `Preference` queries are. It needs a logged-in account and no other permission.
- A `limit` below 1 or above the maximum, or an `offset` below 0, is refused with a validation
  error.

**Page sizes**, as named constants:

| Constant | Value |
| --- | --- |
| Default number of schema changes | 10 |
| Maximum number of schema changes | 50 |
| Default number of operations | 50 |
| Maximum number of operations | 500 |

The sources give no page size. The maximum bounds the work of the nested loaders. `InfrahubEvent`
caps its page at 50 in the same way.

**Why a logged-in account**: the application error and the migration errors are the strings that
the load returns to its caller today. They can hold the text of a database exception. Anonymous
read access is on by default, and the constitution does not allow internal error detail in what a
user receives. With this rule, every logged-in user can read that text, where today only the
account that ran the load receives it.

## R13. Deleting a branch

**Decision**: `core/branch/data_deleter.py::BranchDataDeleter.delete_branch_data` runs one more
step. A `Query` deletes the schema changes whose `branch` is the deleted branch, with their
operations, applications and migration records, in batches of the deleter's batch size, until a
run deletes nothing.

**Rationale**: `delete_branch_data` is also called for a branch that was left in the status
`DELETING`, so the records of such a branch are deleted when the deletion is finished. Each query
there commits on its own, which lets a deletion that failed run again. The deleter builds its
queries itself, so the new step needs no new constructor argument.

**Alternative rejected**: a trigger on `BranchDeletedEvent`. The deletion would run later, in
another flow, and a failure there would leave the records with no branch.

## R14. Tests

| Tier | Location | Proves |
| --- | --- | --- |
| Unit | `backend/tests/unit/core/schema_change/` | The equivalence suite (FR-024, FR-025), the operation builder, the applier's refusals, the summary and the name |
| Component | `backend/tests/component/core/schema_change/` | The repository, the history reader and the recorder against Neo4j: create, read in pages, order, version and parent, statuses, deletion by branch |
| Component | `backend/tests/component/graphql/queries/` | The history query |
| Component | `backend/tests/component/graphql/mutations/` | A dropdown or enum mutation stores what the spec says |
| Functional | `backend/tests/functional/schema_change/` | What a load and a check store, several loads with data, a failed migration, a branch deletion, a merge and a rebase that leave the records unchanged |
| Integration Docker | `backend/tests/integration_docker/test_schema_migration.py` | A load whose migrations run on a separate worker updates the records |

- The equivalence suite is a unit test. It works on `SchemaBranch` objects in memory, as
  `backend/tests/unit/core/schema/test_schema_branch.py` does.
- The suite builds its reference result with `SchemaBranch` calls only: `duplicate`,
  `load_schema`, `process`, `diff` and `validate_update`. It does not call
  `SchemaCandidateBuilder` for the reference, so the reference and the result under test do not
  come from the same code.
- A component test covers the timing of R10: main loads a schema, a branch is created with a
  `branched_from` after the timestamp of that load's writes, and the branch's first schema change
  gets main's version plus 1 and main's schema change as its parent.
- A failed migration is produced as
  `backend/tests/integration/schema_lifecycle/test_schema_load_rollback.py` does it, with a
  migration class that always returns an error.
- The unit suite builds the internal schema, the core schema and its base schema once, in a
  session-scoped fixture. The cases share that processed schema, which is safe because the
  operation builder and the applier never change their input. The cases are parametrized
  dataclass test cases.
- The component tests of the records request no schema fixture, because the records are not
  schema nodes. One seeding function in `backend/tests/helpers/schema_change.py` creates a
  history through the repository. Cases that only read are methods of one class with a
  class-scoped history.
- The refusal of a request without a logged-in account is enforced by the GraphQL application
  (`graphql/api/dependencies.py`), not by the resolver, so its test sends the query through the
  HTTP client of the functional class.
- The functional tests share one base class with a class-scoped data set (base schema, nodes,
  branch). One ordered class covers the loads, the check, the history query, the failed load, the
  corrected load and the branch deletion, because each is the next step of one branch's history.
  The rebase and merge test is a second class, because a merge changes main. A failure in an
  early method of the ordered class can hide the later ones.
- There is no Playwright test, because this feature has no user interface.

**Added to the equivalence list from reading the code**: a file that renames an attribute and
writes `human_friendly_id` in the same load (R6), and a file that clears an optional text field
with an empty string (R5). A second group applies recorded operations to a target schema that
gained a kind after the operations were recorded, to test FR-011 on the risk that the task names.

## R15. Generated files and documentation

- `schema/schema.graphql`: `uv run invoke schema.generate-graphqlschema`.
- Front-end GraphQL types: `cd frontend/app && pnpm codegen`. CI fails when they are out of date,
  including for a pull request that changes only the back end.
- A changelog fragment of type `added`.
- User documentation in `docs/docs/schema/` for the history query.
- `dev/knowledge/backend/`: a document on stored schema changes, linked from `backend/AGENTS.md`.
- No new setting, no SDK change and no CLI change.

## R16. Refactoring options not taken in this feature

A review of the existing code found these options. Each changes code that this feature does not
need to change, and none corrects the plan.

| Option | Why it is left for later |
| --- | --- |
| The mutation saves with the diff, as a load does, and not with `limit` | It changes the graph writes of the four mutations, where SC-002 asks for the same results. `pools/schema_number_pool_synchronizer.py` also saves with `limit`, so the second way of saving stays in any case |
| A `SchemaMigrationRunner` class holds the two phases of the migration flow | It needs a `Protocol` around `schema_path_migrate` with one production implementation. `PositionedMigration` corrects the positions without it |
| The migration map is passed to the code that runs migrations, so that a test does not replace an entry of `MIGRATION_MAP` | `SchemaBranch.validate_update` reads the same global, so the change would have to reach it. The fixture saves and restores the map, which the testing guideline allows |
| `SchemaUpdateCoordinator` receives one object that runs the migrations, in place of an enumeration and an optional workflow service | Four production constructors and two test constructors change. This feature only adds a field to the message |
| `apply_attribute_property_change` restores the registry and the branch hash when its transaction fails | Today's behaviour, outside this feature |
