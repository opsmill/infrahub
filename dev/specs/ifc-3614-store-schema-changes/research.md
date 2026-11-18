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

## R1. The records are frozen dataclasses, read and written through a repository

**Decision**: four record types are frozen dataclasses in `core/schema_change/models.py`: a schema
change, a schema change operation, an application and a migration record.
`core/schema_change/record_serializer.py::SchemaChangeRecordSerializer` turns a record into the
properties that a query writes, and the properties that a query returns back into a record. Two
classes take `db` and the serializer in their constructor:

- `SchemaChangeRepository` (`repository.py`) holds the writes, the version reads and the deletion
  of a branch's records, with the `Query` classes it runs in the same module. The recorder, the
  migration recorder and the branch deletion use it.
- `SchemaChangeHistoryReader` (`history_reader.py`) holds the paged reads, with their `Query`
  classes. The history query uses it.

The ID of each record is its `uuid`, a time-ordered UUID that the repository generates. No query
reads a Neo4j element ID. See [data-model.md](data-model.md).

**Rationale**: the component guideline asks for a repository with query classes and says not to
add persistence methods to a model. A repository and its queries change together, so they are in
one module. The classes are split by consumer, so that the code that records a load does not depend
on the reads of the GraphQL query.

The records were first `StandardNode` subclasses, as the design document names them. That gave
each record two forms, the model and a dataclass that the reads returned, and a new field had to
be added to the model, the dataclass, its parser, the reader's mapper and the Cypher. `StandardNode`
also stores `None` as the text `NULL` and reads that text back as `None`, so a kind, an element name
or an error whose text is `NULL` came back as `None`. With one dataclass and one serializer, a
field that is `None` is a property that is not set, and any text is kept.

The repository creates operations and migration records in bulk with one query each, because a
schema change can hold many of them.

**Alternatives rejected**:

- A core kind: the task excludes it. A core kind would also be versioned by branch and copied by a
  merge.
- `StandardNode` subclasses: the two forms and the text `NULL` above.
- Neo4j element IDs as record IDs: Neo4j can reuse an element ID after its vertex is deleted, so
  an ID that the repository generates is the one that stays the same.

## R2. Records are linked by edges that have no `branch` property

**Decision**: four new edge types link the records. None has a `branch`, `from`, `to` or `status`
property.

| Edge | From | To |
| --- | --- | --- |
| `SCHEMA_CHANGE_HAS_OPERATION` | schema change | operation |
| `SCHEMA_CHANGE_HAS_APPLICATION` | schema change | application |
| `SCHEMA_CHANGE_HAS_PARENT` | schema change | its parent schema change |
| `SCHEMA_APPLICATION_HAS_MIGRATION` | application | migration record |

No record has an edge to `Root`: every query reaches an operation or a migration record through
its schema change or application, so such an edge would only double the edges written.

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

## R3. Three indexes, added by a graph migration

**Decision**: three range indexes in `core/graph/index.py`, chosen from the properties that the
queries start from. The graph migration `core/migrations/graph/m084_schema_change_indexes.py` adds
them to an existing database, and `GRAPH_VERSION` is 84.

| Index | Queries that start from it |
| --- | --- |
| `SchemaChange(uuid)` | mark applied, mark failed, the parent, the operation and application pages |
| `SchemaChange(branch)` | the highest version of a branch, the list and the count of the history query, the deletion of a branch's records |
| `SchemaChangeApplication(uuid)` | creating the migration records, setting their status, the migration pages |

**Rationale**: without an index, each of these lookups scans every vertex of the label. Main's
records are never deleted, so their number grows over the life of an instance. Operations and
migration records have no index, because every query reaches them through the edge from their
schema change or application. An existing database with no records needs no other change: main's
version is 0.

**Alternative rejected**: no index, with a label scan, as `Preference` and `TelemetrySnapshot`
have. Every load writes and reads these records, so the scan grows with every load.

## R4. The format of an operation

**Decision**: an operation is one of six types. It names its target by kind and name only.

| Type | Target | Holds |
| --- | --- | --- |
| `node_add` | a kind | the full definition as written, and whether it is a node or a generic |
| `node_remove` | a kind | nothing else |
| `node_property` | a property of a kind | the new value and the value before |
| `element_add` | an attribute or a relationship of a kind | the full definition as written, with the order weight that processing gave it when the file sets none |
| `element_remove` | an attribute or a relationship of a kind | nothing else |
| `element_property` | a property of an attribute or a relationship | the new value and the value before |

- A property can be nested, such as `parameters.regex`. The name is the dotted path that
  `core/models.py::SchemaUpdateValidationResult` already uses for nested properties.
- An added definition never holds `id` or `parameters.number_pool_id`.
- An added attribute or relationship also holds `order_weight`. When the file sets none, it is the
  weight that processing gave the element in the schema of step 2 of R5. Processing numbers an
  element without a weight by its place in the list of the kind, and a load puts the new elements
  after the elements that the file leaves out, so the applier cannot calculate the same weight
  from the operation alone.
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
operations and the processed schema of step 2, which the candidate builder compares with the
schema that the applier builds from the operations (R7).

1. Lay the file over a copy of the branch schema with `SchemaBranch.load_schema`, as a load does
   today, and keep that schema before processing.
2. Process it and calculate the diff with the branch schema, as a load does today.
3. Keep each path of the processed diff that the file states. The value of the operation is read
   from the schema of step 1, before processing. The value before the change is read from the
   branch schema.

"The file states a path" means: the kind is in the file's nodes, generics or extensions, the
attribute or relationship is in the file under that kind, and the property is not `None` in the
file's model. A field of a nested property, such as `parameters.start_range`, is also stated when
the file sets another field of that property, because a load can clear the fields that the file
leaves out (`core/schema/attribute_parameters.py::NumberPoolParameters.update` replaces the
`start_range` and `end_range` pair and the `ranges` list with each other).

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
- A processed diff that is not empty can still give no operation, when every changed path is one
  that the file does not state. The runner then applies the candidate without a record, as a
  merge does, and logs a warning that names the branch: the stored history misses that change.
  Since every load applies the operations (R7), this happens when processing calculates a value
  that differs from the stored schema, for example after an upgrade that changed processing: the
  file changed nothing, but the saved schema changes. A merge loses nothing, because the ordered
  replay processes the schema of main again.

**Order of the operations** in one schema change:

1. removals of kinds, each preceded by the other changes that the file states for that kind, then
   additions of kinds, generics before nodes, each group by kind name;
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

**What the equivalence suite showed** (T017): one rule covers every case in the list, with these
details:

- A path whose value in the schema of step 1 equals its value in the branch schema gives no
  operation. Processing can change a path that the file states with the value it already had.
- A nested property gives one operation for each changed field, such as `parameters.regex`. When
  the two values are of different models, the operation holds the whole property. A file that
  declares a number pool by `ranges` where the branch schema has `start_range` and `end_range`
  gives three operations: `ranges` set, and `start_range` and `end_range` set to `null`.
- `state: absent` on an attribute or a relationship that a node overrides from its generic gives
  an `element_remove`. The diff reports that element as changed, not removed, because processing
  inherits it again from the generic.
- `state: absent` on a node gives a `node_remove`. A load keeps the removed kind in the schema with
  the other changes that the file states for it merged in, such as the attributes and
  relationships that the file also marks absent. So the operations of those changes come first,
  in the order of a changed kind, without a change of `state`, `name` or `namespace`, and the
  `node_remove` comes last.
- An added definition holds the fields that the file sets, without `id` and
  `parameters.number_pool_id`, and the order weight of R4.
- A load keeps the class of an attribute as the file holds it. An attribute that a node
  extension adds is parsed as the base attribute class, and the applier builds the class of its
  kind, as a load does for an attribute of a node definition. The two schemas then differ in the
  stored hash of that kind until the schema is read again from the database. The comparer that
  the candidate builder uses (R7) does not name the kind, because it compares the content of a kind parsed into the class of each
  attribute kind. The suite writes that attribute with the class of its kind.
- A rename of an attribute on a generic, `unique` turned off on an attribute that a calculated
  uniqueness constraint holds, a relationship kind changed to Component without `on_delete`, and
  an attribute kind changed on a generic alone keep today's result: the four cases of FR-025 are
  strict expected failures.

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

An operation on a kind, attribute or relationship that the target does not have raises
`SchemaOperationTargetNotFoundError`, which names the operation and the missing element (FR-023).
A `node_add` or an `element_add` whose kind, attribute or relationship the target already has
raises `SchemaOperationTargetExistsError`, because `set` would replace the kind and a second
element with the same name would be appended. The ordered replay task decides whether such an add
is skipped instead.

**Rationale**: these are the three steps of the design document. `apply_schema_path_updates` is
the method that today's load reaches through `handle_field_renames_and_deletes`.

**Risk tested**: today's load rewrites the paths first and then lays the file's values over them.
The applier sets the values first and then rewrites. The two orders could differ when a file renames
an attribute and also writes `human_friendly_id` or another path list. The equivalence case for it
passes with the applier's order (T017), because the value that the file writes already names the
new name, so the applier keeps setting the values first.

## R7. One component builds the candidate schema for the load, the check and the mutations

**Decision**: a `SchemaCandidateBuilder` returns the operations, the processed candidate schema
and the `SchemaUpdateValidationResult` (diff, migrations, constraints, errors).

- From a schema file: refuse a file that gives a kind of the branch schema an ID that the branch
  schema does not hold (`SchemaNotFoundError`), build the operations (R5), apply them (R6), and
  compare the applier's result with the processed schema of step 2 of R5, kind by kind. Then
  `diff`, `validate_node_deletions` and `validate_update` on the applier's result.
- From operations: apply them (R6), then `diff`, `validate_node_deletions` and `validate_update`
  on the applier's result.

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

**Every load checks its operations** (spec, decision 8): the builder takes a
`SchemaCandidateComparer` as a required constructor argument. `from_schema_root` raises
`SchemaOperationsRebuildError` when the applier refuses an operation
(`SchemaOperationTargetNotFoundError` or `SchemaOperationTargetExistsError`) or when the comparer
returns kinds. The error has the HTTP code 500, and its message says that the schema change cannot
be stored accurately, that the error is in Infrahub and not in the schema file, and names the
kinds. The load saves nothing, and the check returns the same error.

- Every unit, component, functional and integration test that loads a schema file therefore fails
  on a case where the operations do not rebuild the schema, and so does a server or a task worker
  in a container. No setting, override or test fixture turns the comparison off.
- A file that gives a kind of the branch schema an ID that the branch schema does not hold is
  refused with `SchemaNotFoundError` before the operations are built. Laying it over the branch
  schema would replace the kind whole, which no operation states, and a direct load refused the
  same file with the same error when it wrote the kind.
- A file that gives a new kind, or a new attribute or relationship of an existing kind, an ID loads
  as if it gave none: the operations do not hold instance IDs, the comparison leaves IDs out, and
  saving a schema gives a new kind or element a database ID whatever ID the file set
  (`_create_node_in_db` and the element writes in `core/schema/manager.py` exclude `id`).
- `SchemaCandidateComparer` returns the kinds whose content differs. A kind whose stored hash
  differs is parsed again into the class of each attribute kind, as a schema read from the
  database is, and is returned only when the hash of that content still differs; an attribute
  held in another Python class with the same values is not a difference. A kind that cannot be
  parsed again is returned, and the comparer raises nothing for it.

**Cost**: a load and a check process the schema twice: once to find the operations, as a direct
load does, and once in the applier. The design document measured about 0.16 s to build the internal
and core schema in memory, and says the time on a schema of customer size is not measured.

Measured (T022, then T065): `SchemaCandidateBuilder.from_schema_root`, when it applied the
operations and processed the schema a second time, took **2.00 times** the time of the direct load
of the equivalence suite (`build_direct_load_result` in
`backend/tests/unit/core/schema_change/helpers.py`): median 541.8 ms against 270.3 ms. The branch
schema is the processed internal and core schema, with an ID on every element, and the file is
`DEVICE_SCHEMA`, the largest schema of `backend/tests/helpers/schema/` (two generics and four
nodes, all added). Measured on 2026-11-17, Python 3.12.13, one AMD EPYC 9R45 core, with no other
test run on the machine. The builder that processed the schema once (T065) took 1.00 times. The
present builder, which also compares the two schemas, took 2.00 times on the same benchmark (mean
540.5 ms against 269.7 ms), measured after the review changes. A schema of customer size is still
not measured. Command, from the repository root:

```bash
INFRAHUB_LOG_LEVEL=CRITICAL uv run pytest backend/tests/benchmark/test_schema_candidate_builder.py --dist=no -p no:randomly
```

The two benchmarks share one `pytest-benchmark` group, so the table prints the ratio next to
each time.

**Alternative rejected**: processing the schema once and saving the processed schema of the
laid-over file, with the operations checked by a replay in the tests only (T065). It halved the
time of `from_schema_root`, but the production code was shaped to fit the tests: an interface
whose production implementation checked nothing, an override in `config.py` and a session fixture
that installed the check. The saved schema could also differ from what the stored operations
build, which a later replay would expose. The review reverted it on 2026-11-18.

## R8. A load records its schema change in three steps

**Decision**: a `SchemaChangeRecorder` owns the status of the records, and asks a
`SchemaChangeVersionResolver` for the version and the parent (R10). A
`SchemaChangeApplicationRunner` calls it around `SchemaUpdateCoordinator.execute`.

1. **Start**, after the constraint checks pass and before any write: create the schema change with
   the status `running` and no version, its operations, and one application with the status
   `running` and the timestamp that the coordinator uses for every write. When this write fails,
   the load fails before it changes anything.
2. **Migrations**: the flow creates one migration record for each migration with the status
   `waiting`, sets a record to `running` when the task of its migration starts, and sets it to
   `applied` or `failed` when its migration returns (R9).
3. **End**:
   - success: the runner passes `complete` to the coordinator as its final step
     (`SchemaUpdateFinalStep`). The coordinator runs it after the schema is saved and the
     migrations succeed. It assigns the version and the parent (R10), sets the schema change and
     the application to `applied`, and stores the time. When it raises, the coordinator rolls the
     update back as it does for a failed migration, and the load fails;
   - failure: the coordinator has already rolled the graph back when it raises, so the runner
     catches the exception, calls `fail`, and raises the exception again. `fail` sets the schema
     change and the application to `failed`, stores the error on the application, and closes the
     migration records: `applied` becomes `rolled_back`, `waiting` becomes `cancelled`, `running`
     becomes `failed` with the error of the load added to its errors;
   - cancellation (`asyncio.CancelledError`, which is not an `Exception`): the runner calls `fail`
     with the error `The schema load was cancelled before it completed` inside `asyncio.shield`,
     then lets the cancellation go on.

**Which writes must succeed** (spec, decision 9): the schema change and its application are
required records, because the ordered replay at rebase and merge reads them. A load whose schema
change cannot be created or set to `applied` fails and is rolled back. The migration records report
progress and are best effort: a failed write is logged, and the migrations go on. The ordered
replay task decides whether the final status of a migration record joins the required records.

**Retries**: each repository write is one Cypher statement, so it is atomic without an explicit
transaction. Outside a transaction, a write that Neo4j rejects with a transient error runs again,
with the retry settings of the database (`retry_db_transaction`). Inside a transaction, as in a
dropdown or enum mutation (R11), it runs once, because a failed statement aborts the transaction
and only its owner can run it again.

The runner depends on two `Protocol` classes declared beside it, one for the three recorder
methods it calls and one for `execute`. `SchemaChangeRecorder` and `SchemaUpdateCoordinator`
satisfy them. The unit tests of the runner pass a recording and a failing implementation of each,
without a database and without a mock library. The recorder and the version resolver depend in the
same way on a `Protocol` of the repository methods each one calls, so their unit tests pass a
recording repository with manufactured records.

**Rationale**: the design document says that a load creates its schema change with the status
`running` before its migrations run, and that the code that handles a failure updates the records.
The runner is the code that the design lists in B's scope: "code that applies one schema change
from its operations, creates an application and a record for each migration it runs, and updates
their status". The staging task and the replay task apply a schema change that already exists,
so they extend the runner; this feature does not design for them.

**Known limit**: the schema change and its application keep the status `running` when:

- the write that sets them to `failed` raises one of `RECORD_WRITE_ERRORS` (a `DatabaseError`, a
  `QueryError`, a `QueryTimeoutError` or a `Neo4jError`) after its retries. The runner logs it and
  raises the error of the load;
- the process stops before the shielded write of `fail` runs.

The coordinator rolls back only on an `Exception`. A cancelled load therefore records its schema
change as `failed`, but the schema and the data that the load wrote before the cancellation are not
rolled back. Rolling back on cancellation is a change to the coordinator, which every schema update
uses, and is not part of this feature.

Their operations are stored, so a later recovery task can finish or fail them. Recovery after a
worker stops during a load is out of scope in the design document.

**Alternative rejected**: recording `applied` after the coordinator returned, and logging a failed
write without failing the load. The load then succeeded with its schema change left `running`,
which the ordered replay would not apply.

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
  at its top, passes the database to the helper, and passes a session started from it to the
  recorder factory. The database that `get_database()` returns serves every flow of the worker
  and keeps the first session a query opens on it, so the recorder writes through a session of
  its own. The migrations of a phase run concurrently and a session runs one query at a time, so
  the recorder makes its writes one after the other behind an `asyncio.Lock`.

- With an application ID, the recorder creates the records, and updates one record each time a
  migration returns, from its `SchemaMigrationPathResponseData`.
- A record is identified by the position of its migration. The task of a migration passes its
  position when it starts (`_migrate_schema_path_at_position`), and the flow passes it with each
  result, because two migrations of one application can have the same name and the same schema
  path.
- The list of the message follows the order of the schema diff. `SchemaBranch.diff` lists the
  changed kinds that keep their ID in the order of a Python set of IDs, so two runs of the same
  load can list the migrations in another order. The flow therefore sorts the migrations by schema
  kind, field name, property name, path type and migration name before it gives them their
  positions (`position_migrations`), so the positions are the same each time a load runs and a
  test compares the records as they are listed.
- The recorder that writes records depends on a `Protocol` with the two store methods it calls,
  which `SchemaChangeRepository` satisfies. A unit test passes a store that raises, to prove that
  a failed record write does not stop a migration. The migration records are best effort (R8): a
  write that fails after the retries of the repository is logged.
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
  operations it ends with `_and_<n>_more`. An `element_property` operation gives the attribute or
  relationship name, not the property name (`dcimgenericdevice_serial_update`); a `node_property`
  operation gives the property name (`dcimgenericdevice_generate_profile_update`).
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
- The resolver reads a page only when the request selects `edges`; the page read also returns
  `count`. When the request selects `count` without `edges`, the resolver only counts. It opens
  its own read-only database session.
- `operations`, `applications` and the `migrations` of an application are nested connections,
  each with its own `limit`, `offset` and `count`. A load with many migrations is read in pages, as
  its operations are.
- Nested fields are loaded with data loaders (`graphql/loaders/`): one loader for each field and
  page of a request, so one query reads the operations, the applications or the migration records
  of every parent on the page that asks for the same page.
- The types do not expose the format version of a schema change, which is internal, or the
  `nbr_migrations_executed` of a migration record, which is the internal counter of a migration
  result and not the node counts that the progress task adds. The database keeps both.
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
| Default number of applications | 10 |
| Maximum number of applications | 50 |
| Default number of migration records | 50 |
| Maximum number of migration records | 500 |

The sources give no page size. The maximum bounds the work of the nested loaders. `InfrahubEvent`
caps its page at 50 in the same way.

**Why a logged-in account**: the application error and the migration errors are the strings that
the load returns to its caller today. They can hold the text of a database exception. Anonymous
read access is on by default, and the constitution does not allow internal error detail in what a
user receives. With this rule, every logged-in user can read that text, where today only the
account that ran the load receives it.

## R13. Deleting a branch

**Decision**: `core/branch/data_deleter.py::BranchDataDeleter.delete_branch_data` runs one more
step, `SchemaChangeRepository.delete_branch_schema_changes`, which the deleter receives as a
constructor argument through the protocol `SchemaChangeRecordDeleter`. Its query,
`SchemaChangeDeleteByBranchQuery`, selects the schema changes whose `branch` is the deleted branch
and deletes, in this order, their migration records, their operations, their applications and the
schema changes. Each group is reached through a fixed pattern from the schema change, and deleted
in `CALL { ... } IN TRANSACTIONS OF $batch_size ROWS`, with the deleter's batch size.

**Rationale**:

- Each batch commits on its own and holds at most the batch size of records, so the size of a
  transaction does not depend on the number of operations of one schema change.
- The order, from the migration records up to the schema changes, means that a deletion that stops
  part way leaves no record that its schema change does not reach, and running it again deletes
  the rest.
- `delete_branch_data` is also called for a branch that was left in the status `DELETING`, so the
  records of such a branch are deleted when the deletion is finished. The deleter runs its queries
  outside a transaction, which `IN TRANSACTIONS` needs.
- The fixed patterns state the structure of the records, where one variable-length pattern over
  the three edge types would not.

**Alternatives rejected**:

- One run of at most the batch size of schema changes, each with all its records, until a run
  deletes nothing: the size of a run then depends on the number of operations of a schema change.
- A trigger on `BranchDeletedEvent`. The deletion would run later, in another flow, and a failure
  there would leave the records with no branch.

## R14. Tests

| Tier | Location | Proves |
| --- | --- | --- |
| Unit | `backend/tests/unit/core/schema_change/` | The equivalence suite (FR-024, FR-025), the operation builder, the applier's refusals, the summary and the name |
| Unit | `backend/tests/unit/core/schema_change/` | The recorder, the version resolver, the migration recorder and the runner, with recording and failing adapters of the repository and the coordinator |
| Component | `backend/tests/component/core/schema_change/` | The repository and the history reader against Neo4j: what each query writes and reads, the pages and their order, the version reads and the "applied at or before" filter, the closing of the migration records of a failed load, deletion by branch |
| Component | `backend/tests/component/graphql/queries/` | The history query |
| Component | `backend/tests/component/graphql/mutations/` | A dropdown or enum mutation stores what the spec says |
| Functional | `backend/tests/functional/schema_change/` | What a load and a check store, several loads with data, a failed migration, a branch deletion |
| Integration Docker | `backend/tests/integration_docker/test_schema_migration.py` | A load whose migrations run on a separate worker updates the records |

- The equivalence suite is a unit test. It works on `SchemaBranch` objects in memory, as
  `backend/tests/unit/core/schema/test_schema_branch.py` does.
- The suite builds its reference result with `SchemaBranch` calls only: `duplicate`,
  `load_schema`, `process`, `diff` and `validate_update`. It does not call
  `SchemaCandidateBuilder` for the reference, so the reference and the result under test do not
  come from the same code.
- Outside the equivalence suite, every test that loads a schema file fails when the operations of
  the file do not rebuild its schema, because every load applies them and compares (R7).
- The timing of R10 is covered in two tiers: a component test of the repository asserts that the
  highest version of a branch at a time counts the schema changes applied at or before that time,
  the boundary included, and the unit tests of the version resolver assert that a branch without
  a schema change reads main at its `branched_from`.
- A test whose subject uses the repository, such as the recorder, the version resolver or the
  migration recorder, is a unit test with a recording or a failing repository adapter
  (`backend/tests/unit/core/schema_change/helpers.py`). What a query writes or reads in Neo4j is
  asserted in the component tests of the repository and the history reader.
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
  A failure in an early method of the ordered class can hide the later ones. A second class that
  asserted that a rebase and a merge leave the records unchanged was removed, because the ordered
  replay at rebase and merge changes them before this feature is released.
- There is no Playwright test, because this feature has no user interface.

**Added to the equivalence list from reading the code**: a file that renames an attribute and
writes `human_friendly_id` in the same load (R6), and a file that clears an optional text field
with an empty string (R5). A second group applies recorded operations to a target schema that
gained a kind after the operations were recorded, to test FR-011 on the risk that the task names.

## R15. Generated files and documentation

- `schema/schema.graphql`: `uv run invoke schema.generate-graphqlschema`.
- Front-end GraphQL types: `cd frontend/app && pnpm codegen:graphql && pnpm codegen`. CI runs
  `pnpm codegen:graphql` and fails when `graphql-env.d.ts` or `graphql-cache.d.ts` is out of date,
  including for a pull request that changes only the back end. CI does not check `types.ts`, which
  `pnpm codegen` writes.
- No changelog fragment and no user documentation in this feature: the epic changes the history
  query and the records further, so both are written when the epic is complete.
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
