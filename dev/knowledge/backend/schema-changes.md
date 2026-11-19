# Schema Changes

> Part of: `dev/knowledge/backend/` | Related: [database-schema.md](database-schema.md), [query-pattern.md](query-pattern.md), [graphql-execution.md](graphql-execution.md), [async-tasks.md](async-tasks.md)

Every schema load and every dropdown or enum mutation that changes the schema of a branch stores a
schema change: the list of operations it made, the time Infrahub applied it to the branch, and the
status of each migration it ran. The `InfrahubSchemaChange` GraphQL query returns them, one branch
at a time. The code and its Cypher are in `backend/infrahub/core/schema_change/`, and the GraphQL
types, loaders and resolvers in the `schema_change.py` modules of `backend/infrahub/graphql/`.

## The records and their edges

The four records are frozen dataclasses (`core/schema_change/models.py`). They are not schema nodes
and not `StandardNode` vertices: the generic node API does not read them, a branch does not version
them, and no record has an edge to `Root`, because every query reaches a record through its schema
change or its application.

```text
(SchemaChange)-[:SCHEMA_CHANGE_HAS_OPERATION]->(SchemaChangeOperation)
(SchemaChange)-[:SCHEMA_CHANGE_HAS_APPLICATION]->(SchemaChangeApplication)
(SchemaChange)-[:SCHEMA_CHANGE_HAS_PARENT]->(SchemaChange)
(SchemaChangeApplication)-[:SCHEMA_APPLICATION_HAS_MIGRATION]->(SchemaChangeMigration)
```

- `SchemaChange`: the branch name as a `branch` property, the status, the version, the summary,
  the operation format version, and `applied_at`. The name, `<version in five digits>_<summary>`,
  is calculated when the GraphQL resolver reads it, and is the summary alone without a version.
- `SchemaChangeOperation`: one operation, at a `position` from 0. `value` and `previous_value` are
  JSON text, so the JSON value `null` stays apart from a field that is not set. No field holds a
  vertex ID.
- `SchemaChangeApplication`: one time the schema change was applied to a branch, with `at`, the
  timestamp of every graph write of the load, and `error` when it failed.
- `SchemaChangeMigration`: one migration of the application, identified by its `position` in the
  list of migrations, because two migrations of one load can have the same name and schema path.
  The schema path is stored as its parts, without the schema ID.

The ID of every record is its `uuid` property, a time-ordered UUID that the repository generates,
and the GraphQL `id` of the record. No query reads a Neo4j element ID.

`SchemaChangeRecordSerializer` (`record_serializer.py`) turns a record into the properties a query
writes, and the properties a query returns back into a record. A field that is `None` is a property
that is not set, so a text property keeps any text, the text `NULL` included. A new field is added
to the dataclass, the serializer and the Cypher that reads or writes it.

## Indexes

Three range indexes in `core/graph/index.py` cover the property each query starts from. The graph
migration `m084_schema_change_indexes.py` adds them to an existing database.

- `SchemaChange(uuid)`: marking a schema change applied or failed, finding the parent, and the
  pages of operations and applications.
- `SchemaChange(branch)`: the highest version of a branch, the list and the count of the history
  query, and the branch deletion. The records of the default branch are never deleted, so their
  number only grows.
- `SchemaChangeApplication(uuid)`: creating the migration records, setting their status, and the
  pages of migration records.

Operations and migration records have no index, because every query reaches them through the edge
from their schema change or application.

## Why the edges have no `branch` property

The queries that roll back a write, rebase a branch, calculate a diff and delete the data of a
branch select edges by their `branch` property. An edge without one is invisible to them:

- the rollback of a failed load deletes the schema and data it wrote at its timestamp, and leaves
  the records of that load, which then hold the error;
- a merge and a rebase neither copy nor change the records of either branch;
- the branch data deletion loops over `DatabaseEdgeType`, so the four edge types are kept out of it,
  in `core/schema_change/enums.py::SchemaChangeEdgeType`.

The branch of a record is the `branch` property of the `SchemaChange` vertex, and the history query
and the branch deletion select by it.

## The repository and the reader

`repository.py::SchemaChangeRepository` writes the records, reads the versions and deletes the
records of a branch, with the `Query` classes of the same module:

- `SchemaChangeCreateQuery`: a schema change, its operations and one application, in one statement.
- `SchemaChangeMigrationCreateQuery`: the migration records of an application; it raises
  `QueryError` when the application is not stored.
- `SchemaChangeMigrationStatusUpdateQuery`: the status, the result and the errors of the migration
  records at the positions given.
- `SchemaChangeMarkAppliedQuery` and `SchemaChangeMarkFailedQuery`: the final status of a schema
  change and its application, described under [When each status is set](#when-each-status-is-set).
- `SchemaChangeHighestVersionQuery` and `SchemaChangeHighestVersionAtQuery`: the applied schema
  change with the highest version of a branch, the second one among those whose `applied_at` is at
  or before a time.
- `SchemaChangeDeleteByBranchQuery`: described under [Deleting a branch](#deleting-a-branch).

Each write is one statement. Outside a transaction, a write that Neo4j rejects with a transient
error runs again, with the retry settings of the database. Inside a transaction it does not run
again, because a failed statement aborts the transaction and only its owner can run it again.

`history_reader.py::SchemaChangeHistoryReader` holds the paged reads of the history query, with
`SchemaChangeListQuery`, `SchemaChangeCountQuery` and the three subclasses of `RecordPageQuery`
(`SchemaChangeOperationPageQuery`, `SchemaChangeApplicationPageQuery`,
`SchemaChangeMigrationPageQuery`). `core/schema_change/factory.py` builds both.

## How a load, a check and a mutation build their schema

All three build a `SchemaCandidate` (operations, processed schema, `SchemaUpdateValidationResult`)
with `SchemaCandidateBuilder`, which `factory.py::build_schema_candidate_builder` builds. The
candidate schema is always the schema that `SchemaChangeApplier` builds from the operations.

A schema load and a schema check call `from_schema_root` through
`api/schema.py::build_candidate_from_schemas`:

1. When the file gives a kind of the branch schema an ID that the branch schema does not hold, it
   raises `SchemaNotFoundError` before any operation is built. Laying that file over the branch
   schema would replace the kind whole, which no operation states.
2. `SchemaOperationBuilder` lays the merged file over a copy of the branch schema, processes it,
   diffs it against the branch schema, and keeps each path of that diff that the file states as an
   operation. That processed copy is the direct-load schema.
3. The applier applies the operations to a copy of the branch schema and processes it.
4. `SchemaCandidateComparer` compares the applied schema with the direct-load schema, kind by kind,
   without the IDs of the kinds and of their attributes and relationships: saving a schema gives a
   new kind or element a database ID whatever ID the file set, and the operations hold no ID.

When the applier refuses an operation or a kind differs, the builder raises
`SchemaOperationsRebuildError` (HTTP 500), whose message says that the error is in Infrahub, not in
the file, and names the kinds. The load saves nothing, and the check returns the same error. A load
therefore processes the schema twice. A file that gives a new kind, or a new attribute or
relationship of an existing kind, an ID loads as if it gave none.

A dropdown or enum mutation (`graphql/mutations/schema.py::apply_attribute_property_change`) reads
the list of the attribute, validates the change and builds the new list inside the schema lock. It
builds one `element_property` operation on `choices` or `enum` that sets the whole list, with the
list it read as the previous value, and calls `from_operations`, which applies it without a
comparison.

The applier raises `SchemaOperationTargetNotFoundError` for an operation whose kind, attribute or
relationship the schema does not have, and `SchemaOperationTargetExistsError` (HTTP 422) for an add
whose kind, attribute or relationship the schema already has.

### Every load checks its operations

Because every load and check compares the applied schema with the direct-load schema, every test
that loads a schema fails when the operations miss a change of the file. No setting or test fixture
turns the comparison off, and a server or task worker in a container compares the same way.

## How a load records its schema change

`api/schema.py::load_schema` runs `SchemaChangeApplicationRunner.run` in place of calling
`SchemaUpdateCoordinator.execute`, inside the schema lock, after the constraint checks pass and only
when the diff is not empty. A load refused before that point stores nothing.

The schema change and its application are required records, so a load whose schema change cannot
be recorded fails and is rolled back. They are kept for merge and rebase to read in later work;
today neither reads them, and both apply their migrations with `application_id=None`, which records
no migration. The migration records report
progress and are best effort.

1. `SchemaChangeRecorder.start` creates the schema change and one application, both `running`, with
   the operations, at the timestamp the coordinator then uses for every write. When it fails, the
   load fails before it changes anything.
2. The coordinator receives the application ID and puts it in `SchemaApplyMigrationData`. The flow
   `core/migrations/schema/tasks.py::schema_apply_migrations` builds a `MigrationRecorder` with
   `build_migration_recorder`, writing through a database session of its own. It sorts the
   migrations by schema path, then by migration name (`position_migrations`), because the diff gives
   them in the order of a set; the positions are then the same each time a load runs. It creates one
   `waiting` record for each migration, sets a record to `running` when the task of its migration
   starts, and sets it to `applied` or `failed` when its result arrives. A record write that fails
   after its retries is logged, and the migrations go on.
3. `complete` runs as the final step of the coordinator (`SchemaUpdateFinalStep`), after the schema
   is saved and the migrations succeed. It asks `SchemaChangeVersionResolver` for the version and
   the parent and marks both records `applied`, with `applied_at` equal to the application's `at`.
   When it raises, the coordinator rolls the update back as it does for a failed migration, and the
   load fails.
4. When the update raises an `Exception`, the coordinator has already rolled back. The runner calls
   `fail` with the text of the error and raises the same exception again.
5. When the load is cancelled (`asyncio.CancelledError`), the runner calls `fail_if_running` with
   the error `The schema load was cancelled before it completed` inside `asyncio.shield`, then lets
   the cancellation go on. `fail_if_running` changes the schema change only while it is `running`:
   a cancellation can arrive after the final step recorded the schema change as applied, and a
   cancelled load keeps its schema, so that schema change stays `applied` and the runner logs a
   warning.

A failure of `fail` itself is logged when it is one of `RECORD_WRITE_ERRORS`
(`core/schema_change/record_errors.py`: a `DatabaseError`, a `QueryError`, a `QueryTimeoutError` or
a `neo4j` `Neo4jError`), and the error of the load is raised.

When the diff is not empty but the candidate has no operation, the runner calls the coordinator
with `application_id=None`, stores no schema change and logs a warning naming the branch. This
happens when `process()` calculates a value that differs from the stored schema, for example after
an upgrade changed `process()`: the file changed nothing, but the saved schema changes.

A merge, a rebase and the core schema update in `cli/db.py` pass `application_id=None`, so their
migrations use `NoRecordMigrationRecorder` and they store no schema change.

A dropdown or enum mutation calls `SchemaChangeRecorder.record_applied` inside its database
transaction, before `update_schema_branch`, because `update_schema_branch` replaces the schema in
the registry of the process before the transaction commits. A failed record write fails the
mutation. Its schema change is created `applied`, and its application has no migration record. A
mutation whose diff is empty stores nothing.

## When each status is set

Schema change and application:

- `running`: by `start`, at the beginning of a load.
- `applied`: by `complete` at the end of a load, or directly by `record_applied` for a mutation. Only
  this status gets a version and a parent.
- `failed`: by `fail` (`SchemaChangeMarkFailedQuery`), when the update raises or the load is
  cancelled. The same statement stores the error on the application and closes the migration
  records of the application.

Migration record:

- `waiting`: when the records are created, before any migration runs.
- `running`: when the task of its migration starts.
- `applied` or `failed`: from the result of its migration; `failed` when the result holds errors.
- When the load fails, `fail` sets an `applied` record to `rolled_back`, because the rollback
  removes what the migration wrote, a `waiting` record to `cancelled`, and a `running` record to
  `failed` with the error of the load added to its errors. A `failed` record keeps its status.

The enumerations also hold `staged` for a schema change, and `rolled_back` and `skipped` for an
application. No code sets them.

## What can still leave a record `running`

A schema change and its application stay `running` when:

- `fail` raises a record write error after its retries; the runner logs it and raises the error of
  the load;
- the process stops before the shielded write of `fail` runs.

The coordinator rolls back only on an `Exception`, and `asyncio.CancelledError` is not one. A
cancelled load therefore records a running schema change as `failed`, but the coordinator does not roll
back the schema and the data that the load wrote before the cancellation. The rollback on
cancellation belongs to the coordinator, which every schema update uses, not to the records.

A migration record keeps an earlier status when one of its own writes fails after the retries, even
when the load succeeds. After a failed load, `fail` closes every record that is `waiting` or
`running`.

## Versions and parents

`SchemaChangeVersionResolver.resolve_next` returns the highest applied version of the branch plus
1, with that schema change as the parent. A branch with no applied schema change starts from the
highest version of the default branch whose `applied_at` is at or before the branch's
`branched_from`, with that schema change as the parent, or from version 1 with no parent.
`applied_at` is the timestamp of the load's writes, not the time it ended, so a branch created while
a load runs its migrations counts that load. The schema lock is held around the resolve and the
write, so two schema changes cannot take the same version.

After a rebase, the next schema change of a branch takes the version after the branch's own last
one, which can equal a version that the default branch applied after the branch was created. No
code renumbers the schema changes of a branch.

## Deleting a branch

`core/branch/data_deleter.py::BranchDataDeleter.delete_branch_data` calls
`SchemaChangeRepository.delete_branch_schema_changes` once, with its batch size. The query
`SchemaChangeDeleteByBranchQuery` selects the schema changes by their `branch` property and deletes,
in this order, their migration records, their operations, their applications, and the schema
changes, each through a fixed pattern from the schema change, in
`CALL { ... } IN TRANSACTIONS OF $batch_size ROWS`. Each batch commits on its own, so the size of a
transaction does not depend on the number of operations of one schema change. A deletion that stops
part way leaves no record that its schema change does not reach, and running it again deletes the
rest. `IN TRANSACTIONS` needs an auto-commit transaction, which is how the deleter runs its queries.

The query does not follow `SCHEMA_CHANGE_HAS_PARENT`, so a schema change of the default branch that
is the parent of the first schema change of the deleted branch stays. The number that
`delete_branch_data` returns counts only the edges of its other steps.

## Reading the history

`graphql/queries/schema_change.py::InfrahubSchemaChange` reads the branch of the request. It lists
applied schema changes by version, then the others by `created_at`, pages them with `limit` (default
10, maximum 50) and `offset`. A request that selects `edges` runs the list query and the count
query, and a request that selects only `count` runs the count query alone.
Three nested fields are paged the same way, with a `count` of all their records:

- `operations` of a schema change, by position: default 50, maximum 500;
- `applications` of a schema change, by `at`, then `uuid`: default 10, maximum 50;
- `migrations` of an application, by position: default 50, maximum 500.

They resolve through the loaders of `graphql/loaders/schema_change.py`: one loader for each field
and page of a request, so the records of every parent on the page that asks for the same page come
from one query. Each loader opens a read-only session of its own, because graphql-core resolves the
nested fields concurrently. The GraphQL types do not expose `format_version` of a schema change or
`nbr_migrations_executed` of a migration record, which the database holds.

The query is in `graphql/schema.py::QUERIES_REQUIRING_AUTHENTICATION`: it needs a logged-in account
and no other permission, and is refused to an anonymous user even when anonymous read access is on.
The error of an application and the errors of a migration are the text a load returned to its
caller, which can hold the text of a database exception.
