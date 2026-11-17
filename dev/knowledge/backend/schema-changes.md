# Schema Changes

> Part of: `dev/knowledge/backend/` | Related: [database-schema.md](database-schema.md), [query-pattern.md](query-pattern.md), [graphql-execution.md](graphql-execution.md), [async-tasks.md](async-tasks.md)

Every schema load and every dropdown or enum mutation that changes the schema of a branch stores a
schema change: the list of operations it made, the time Infrahub applied it to the branch, and the
status of each migration it ran. The `InfrahubSchemaChange` GraphQL query returns them, one branch
at a time. The code is in `backend/infrahub/core/schema_change/`, the Cypher in
`backend/infrahub/core/query/schema_change.py`, and the GraphQL types, loaders and resolvers in the
`schema_change.py` modules of `backend/infrahub/graphql/`.

## The records and their edges

The four records are `StandardNode` vertices (`core/schema_change/models.py`). Each one has the
`IS_PART_OF` edge to `Root` that every `StandardNode` has. They are not schema nodes: the generic
node API does not read them and a branch does not version them.

```text
(SchemaChange)-[:SCHEMA_CHANGE_HAS_OPERATION]->(SchemaChangeOperation)
(SchemaChange)-[:SCHEMA_CHANGE_HAS_APPLICATION]->(SchemaChangeApplication)
(SchemaChange)-[:SCHEMA_CHANGE_HAS_PARENT]->(SchemaChange)
(SchemaChangeApplication)-[:SCHEMA_APPLICATION_HAS_MIGRATION]->(SchemaChangeMigration)
```

- `SchemaChange`: the branch name as a `branch` property, the status, the version, the summary,
  the operation format version, and `applied_at`. The name, `<version in five digits>_<summary>`,
  is calculated when the query reads it, and is the summary alone without a version.
- `SchemaChangeOperation`: one operation, at a `position` from 0. `value` and `previous_value` are
  JSON text, so the JSON value `null` stays apart from a field that is not set (`StandardNode`
  stores `None` as the text `NULL`). No field holds a vertex ID.
- `SchemaChangeApplication`: one time the schema change was applied to a branch, with `at`, the
  timestamp of every graph write of the load, and `error` when it failed.
- `SchemaChangeMigration`: one migration of the application, identified by its `position` in the
  list of migrations, because two migrations of one load can have the same name and schema path.
  The schema path is stored as its parts, without the schema ID.

`SchemaChangeRepository` writes the records and reads the version; `SchemaChangeHistoryReader`
holds the paged reads of the query. Neither deletes records.

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

## How a load, a check and a mutation build their schema

All three build a `SchemaCandidate` (operations, processed schema, `SchemaUpdateValidationResult`)
with `SchemaCandidateBuilder`, which `core/schema_change/factory.py::build_schema_candidate_builder`
builds.

- A schema load and a schema check call `from_schema_root` through
  `api/schema.py::build_candidate_from_schemas`. `SchemaOperationBuilder` lays the merged file over a
  copy of the branch schema, processes it once, diffs it against the branch schema, and keeps each
  path of that diff that the file states as an operation. The candidate schema is that processed
  copy, validated with that diff. The applier does not run, so a load processes the schema once, as
  before the operations existed. The check returns the diff and stores nothing.
- A dropdown or enum mutation (`graphql/mutations/schema.py::apply_attribute_property_change`)
  builds one `element_property` operation on `choices` or `enum`, with the list read from the branch
  schema inside the schema lock as its previous value, and calls `from_operations`.
  `SchemaChangeApplier` applies it to a copy of the branch schema and processes the copy.

## Where the applier runs and where the tests check the operations

In production, the applier runs only for the dropdown and enum mutations. A load stores operations
that nothing has replayed.

`from_schema_root` calls a `SchemaOperationsCheck` with the branch schema, the operations and the
processed copy. `build_schema_candidate_builder` takes `config.OVERRIDE.schema_operations_check` when
it is set, and `NoSchemaOperationsCheck`, which checks nothing, otherwise. There is no setting or
environment variable for it.

The session-scoped autouse fixture `_schema_operations_rebuild_the_schema` in
`backend/tests/conftest.py` sets the override to `ReplaySchemaOperationsCheck`
(`backend/tests/helpers/schema_change.py`). It applies the operations with the applier, compares the
result with the processed copy with `SchemaCandidateComparer`, and raises
`SchemaOperationsRebuildError`, an `AssertionError`, naming the differing kinds or the operation the
applier refused. Every test whose process loads a schema through `build_schema_candidate_builder`
therefore fails when the operations miss a change of the file. The check checks nothing when the
file gives a kind of the branch schema an ID that the branch schema does not hold: a load replaces
that kind whole, without the IDs of its attributes and relationships, which no operation holds, and
the load is refused when it writes the kind to the database. A server or task worker started in a
container by the docker or e2e suites does not run the check, because the fixture sets it in the
test process only. `backend/tests/benchmark/conftest.py` clears the override so that the benchmark
measures the production builder.

## How a load records its schema change

`api/schema.py::load_schema` runs `SchemaChangeApplicationRunner.run` in place of calling
`SchemaUpdateCoordinator.execute`, inside the schema lock, after the constraint checks pass and only
when the diff is not empty. A load refused before that point stores nothing. When the diff is not
empty but the candidate has no operation, the runner calls the coordinator with
`application_id=None`, stores no schema change and logs a warning naming the branch, so the stored
history misses that change; in the tests the operations check reports it.

1. `SchemaChangeRecorder.start` creates the schema change and one application, both `running`, with
   the operations, at the timestamp the coordinator then uses for every write.
2. The coordinator receives the application ID and puts it in `SchemaApplyMigrationData`. The flow
   `core/migrations/schema/tasks.py::schema_apply_migrations` builds a `MigrationRecorder` with
   `build_migration_recorder`, writing through a database session of its own. It creates one record
   for each migration, sets the records of a phase to `running` when the phase starts, and sets each
   record to `applied` or `failed` when its result arrives. A record write that fails is logged and
   does not stop the migrations.
3. On success, `complete` asks `SchemaChangeVersionResolver` for the version and the parent and
   marks both records `applied`, with `applied_at` equal to the application's `at`. A record write
   error of `complete` is logged and the load still returns the new hash. On failure, the
   coordinator has already rolled back; the runner calls `fail` with the error text and raises the
   original exception again.

A merge, a rebase and the core schema update in `cli/db.py` pass `application_id=None`, so their
migrations use `NoRecordMigrationRecorder` and they store no schema change.

A dropdown or enum mutation calls `SchemaChangeRecorder.record_applied` inside its database
transaction, before `update_schema_branch`, because `update_schema_branch` replaces the schema in
the registry of the process before the transaction commits. Its schema change is created `applied`,
and its application has no migration record. A mutation whose diff is empty stores nothing.

## When each status is set

Schema change and application:

- `running`: by `start`, at the beginning of a load.
- `applied`: by `complete` at the end of a load, or directly by `record_applied` for a mutation. Only
  this status gets a version and a parent.
- `failed`: by `fail` (`SchemaChangeMarkFailedQuery`), which also stores the error on the
  application and sets the migration records of the application that are `applied` to
  `rolled_back`, in one query.

Migration record: `waiting` when created, `running` when its phase starts, then `applied` or
`failed` from its result, and `rolled_back` when the load fails after it was applied.

The enumerations also hold `staged` for a schema change, and `rolled_back` and `skipped` for an
application. No code sets them.

## What keeps the status `running`

The three steps of a load are separate writes, not one transaction. A schema change and its
application stay `running` when:

- the API server stops, or the request is cancelled, after `start`: a `CancelledError` is not an
  `Exception`, so the runner does not record a failure;
- `fail` itself raises a record write error, which the runner logs before it raises the error of
  the load;
- `complete` raises a record write error after the update succeeded: the runner logs it and
  returns the new hash, so the load succeeds, the schema is applied and the records stay
  `running`.

A record write error is one of `RECORD_WRITE_ERRORS` (`core/schema_change/record_errors.py`): a
`DatabaseError`, a `QueryError`, a `QueryTimeoutError` or a `neo4j` `Neo4jError`. Another exception
that `fail` or `complete` raises reaches `load_schema`.

A migration record stays `running` or `waiting` when a migration raises an exception, because the
flow stops reading the results that come after it, and when its own record write fails. Records of
the kind-update phase are `running` while they wait, because that phase runs one migration at a
time. No code moves a `running` record on afterwards; the operations are stored, so a later task can
finish or fail it.

## Versions and parents

`SchemaChangeVersionResolver.resolve_next` returns the highest applied version of the branch plus
1, with that schema change as the parent. A branch with no applied schema change starts from the
highest version of the default branch whose `applied_at` is at or before the branch's
`branched_from`, with that schema change as the parent, or from version 1 with no parent.
`applied_at` is the timestamp of the load's writes, not the time it ended, so a branch created while
a load runs its migrations counts that load. The schema lock is held around the resolve and the
write, so two schema changes cannot take the same version.

## Deleting a branch

`core/branch/data_deleter.py::BranchDataDeleter.delete_branch_data` runs
`SchemaChangeDeleteByBranchQuery` in batches of its batch size until a run deletes nothing. The
query selects schema changes by their `branch` property and deletes each one with its operations,
applications and migration records. It does not follow `SCHEMA_CHANGE_HAS_PARENT`, so a schema change
of the default branch that is the parent of the first schema change of the deleted branch stays.
The number that `delete_branch_data` returns counts only the edges of its other steps.

## Reading the history

`graphql/queries/schema_change.py::InfrahubSchemaChange` reads the branch of the request. It lists
applied schema changes by version, then the others by `created_at`, pages them with `limit` (default
10, maximum 50) and `offset`, and reads `edges` and `count` only when the request selects them.
`operations` (default 50, maximum 500) and `applications` resolve through the loaders of
`graphql/loaders/schema_change.py`, one query for all the schema changes of a page, each loader on a
read-only session of its own.

The query is in `graphql/schema.py::QUERIES_REQUIRING_AUTHENTICATION`: it needs a logged-in account
and no other permission, and is refused to an anonymous user even when anonymous read access is on.
The error of an application and the errors of a migration are the text a load returned to its
caller, which can hold the text of a database exception.
