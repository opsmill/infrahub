# Internal interfaces

These are the components that this feature adds or changes inside the back end. The later tasks of
the epic (progress, staging, ordered replay, core schema update) use or extend them, so their
contracts are written here. Signatures are indicative; the behaviour is the contract.

New code is in `backend/infrahub/core/schema_change/`. Each component receives its collaborators
as required constructor arguments, as `dev/guidelines/backend/component-design.md` asks. A
component with more than one entry method says why. The components are built in
`factory.py` ("Where the components are built", below).

## `SchemaOperationBuilder`

Builds the operations of a schema load. No database access.

```python
@dataclass(frozen=True)
class SchemaOperationBuildResult:
    operations: list[SchemaOperation]
    direct_load_schema: SchemaBranch


class SchemaOperationBuilder:
    def build(
        self,
        *,
        branch_schema: SchemaBranch,
        schema_root: SchemaRoot,
        default_branch_schema: SchemaBranch,
    ) -> SchemaOperationBuildResult: ...
```

- `direct_load_schema` is the schema that a direct load builds: the file laid over a copy of the
  branch schema, then processed. The builder calculates it to find the operations. It is
  returned so that the candidate builder compares it with the schema that the applier builds from
  the operations.
- `operations` is empty when the file changes nothing after processing.
- Never changes `branch_schema`.
- Each operation follows [data-model.md](../data-model.md), "SchemaChangeOperation".
- Raises the errors that `SchemaBranch.load_schema` and `SchemaBranch.process` raise today, so the
  load and the check return the same refusals as before.

## `SchemaChangeApplier`

Applies operations to a schema in memory. No database access.

```python
class SchemaChangeApplier:
    def apply(
        self,
        *,
        target_schema: SchemaBranch,
        operations: Sequence[SchemaOperation],
        default_branch_schema: SchemaBranch,
    ) -> SchemaBranch: ...
```

- Returns a processed copy. Never changes `target_schema`.
- Applies the operations in order, rewrites the paths in `uniqueness_constraints`,
  `human_friendly_id`, `display_labels`, `order_by` and `default_filter` for the renames and
  removals, then runs `process`.
- Clears no stored value: a property that no operation names keeps the value it has in
  `target_schema` before processing.
- Raises `SchemaOperationTargetNotFoundError` when an operation names a kind, attribute or
  relationship that the schema does not have at that step. The message names the operation
  (position and type) and the missing element.
- Raises `SchemaOperationTargetExistsError` when a `node_add` or an `element_add` adds a kind,
  attribute or relationship that the schema already has at that step. The message names the
  operation and the existing element. Skipping such an add is left to the ordered replay task.
  It raises the same error when a `node_rename` names a kind that the schema already has, and
  when, after the last operation, a rename leaves two attributes or relationships of a kind with
  the same name.
- While a chain or a swap of renames runs, two elements of a kind can share a name. An operation
  then finds the element that no earlier operation renamed; renamed elements are tracked by ID.
- Given the same target and the same operations, it returns a schema with the same hash each time.
- The seven operation types are a closed set. The applier selects the handling of an operation with
  an exhaustive `match` on `SchemaOperationType` that ends with `typing.assert_never`, so a type
  added with a later format version fails the type check until the applier handles it.

## `SchemaCandidateComparer`

Compares two processed schemas. No database access, and it writes no log. The candidate builder
uses it in `from_schema_root`.

```python
class SchemaCandidateComparer:
    def differing_kinds(
        self, *, direct_load_schema: SchemaBranch, applied_schema: SchemaBranch
    ) -> list[str]: ...
```

- Returns the sorted kinds whose content differs between the two schemas, including a kind that
  only one of them has. Returns an empty list when the two are the same.
- A kind whose stored hash differs is parsed again into the class of each attribute kind, as a
  schema read from the database is, and is returned only when the hash of that content still
  differs. An attribute held in another Python class with the same values, such as an attribute
  that a node extension adds, is not a difference.
- A kind that cannot be parsed again in either schema is returned. The validation error is not
  raised.
- Never changes either schema.

## `SchemaCandidateBuilder`

The one way to build a candidate schema from user input.

```python
@dataclass(frozen=True)
class SchemaCandidate:
    operations: list[SchemaOperation]
    schema: SchemaBranch
    validation: SchemaUpdateValidationResult


class SchemaCandidateBuilder:
    def __init__(
        self,
        operation_builder: SchemaOperationBuilder,
        applier: SchemaChangeApplier,
        comparer: SchemaCandidateComparer,
    ) -> None: ...

    def from_schema_root(
        self, *, branch_schema: SchemaBranch, schema_root: SchemaRoot, default_branch_schema: SchemaBranch
    ) -> SchemaCandidate: ...

    def from_operations(
        self, *, branch_schema: SchemaBranch, operations: Sequence[SchemaOperation], default_branch_schema: SchemaBranch
    ) -> SchemaCandidate: ...
```

- `from_schema_root`: raises `SchemaNotFoundError` when the file gives a kind of the branch
  schema an ID that the branch schema does not hold, and `SchemaNameReusedError` (HTTP 422) when
  the file renames a kind and states a kind without an ID under its old name, before it builds any
  operation. It then builds the operations, and raises `SchemaNameReusedError` when they free an
  attribute name, including one that a generic frees or takes for the kinds that inherit from it,
  or a kind, and give it to another owner (spec, FR-017) before it applies any. It then applies them to `branch_schema` with the applier, and compares the result
  with `direct_load_schema` with the comparer. It raises `SchemaOperationsRebuildError` (HTTP 422)
  when the applier raises `SchemaOperationTargetNotFoundError`,
  `SchemaOperationTargetExistsError` or a `ValueError`, or when the comparer returns kinds; the
  message says that the error is in Infrahub, not in the file, and names the kinds (for a
  `ValueError`, every kind that the operations name). Otherwise `schema` is the applier's
  result and `validation.diff` is the diff between `branch_schema` and it. The schema is processed
  twice: once by the operation builder and once by the applier (spec, decision 8).
- `from_operations`: `schema` is the applier's result, and `validation.diff` is the diff between
  `branch_schema` and it. It does not compare, and the errors of the applier reach the caller.
- `validation.migrations` and `validation.constraints` are calculated from `validation.diff`,
  after processing. Both methods run `validate_node_deletions` on `schema` with that diff.
- It has two entry methods because a candidate is built from a schema file or from operations,
  and both end with the same validation.
- `api/schema.py::build_candidate_from_schemas` replaces `evaluate_candidate_schemas`. It takes
  the candidate builder, the branch schema, the default branch schema and the schema files of the
  request. It merges the files, calls `from_schema_root`, and raises `SchemaNotValidError` for a
  `ValueError` and for the errors of the validation. The schema load and the schema check both
  call it, so the files are merged and the errors translated in one place.
- `graphql/mutations/schema.py::apply_attribute_property_change` replaces `update_registry`. It
  receives the kind, the attribute, the property (`choices` or `enum`) and the new list. Inside
  the schema lock it reads the list before the change from the branch schema, builds the one
  operation, and calls `from_operations`.
  It reads the schema and the diff from the candidate, and runs none of the migrations or
  constraints that the candidate lists. No caller applies operations with `SchemaChangeApplier`
  directly.

## `SchemaChangeRepository`

The writes, the version reads and the deletion of the records, in `repository.py`, with the
`Query` classes it runs. The recorder, the version resolver, the migration recorder and the branch
deletion use it.

```python
@dataclass(frozen=True)
class CreatedSchemaChange:
    schema_change_id: str
    application_id: str


@dataclass(frozen=True)
class AppliedSchemaChangeVersion:
    schema_change_id: str
    version: int


class SchemaChangeRepository:
    def __init__(self, db: InfrahubDatabase, serializer: SchemaChangeRecordSerializer) -> None: ...

    async def create_schema_change(
        self, *, branch: str, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> CreatedSchemaChange: ...

    async def mark_applied(
        self,
        *,
        schema_change_id: str,
        application_id: str,
        version: int,
        parent_id: str | None,
        applied_at: Timestamp,
        user_id: str,
    ) -> bool: ...

    async def mark_failed(self, *, schema_change_id: str, application_id: str, error: str, user_id: str) -> bool: ...

    async def create_migration_records(
        self, *, application_id: str, migrations: Sequence[SchemaUpdateMigrationInfo]
    ) -> None: ...

    async def set_migration_records_status(
        self,
        *,
        application_id: str,
        positions: Sequence[int],
        status: SchemaChangeMigrationStatus,
        nbr_migrations_executed: int | None,
        errors: Sequence[str],
    ) -> None: ...

    async def get_highest_applied_version(self, *, branch: str) -> AppliedSchemaChangeVersion | None: ...

    async def get_highest_applied_version_at(
        self, *, branch: str, at: Timestamp
    ) -> AppliedSchemaChangeVersion | None: ...

    async def delete_branch_schema_changes(self, *, branch: str, batch_size: int) -> int: ...
```

- The ID of every record is its `uuid`, a time-ordered UUID that the repository generates, as
  text. No method reads or returns a Neo4j element ID. `set_migration_records_status` selects the
  records of an application by their positions.
- The records are frozen dataclasses (`models.py`). `SchemaChangeRecordSerializer`
  (`record_serializer.py`) turns them into the properties that a query writes; a field that is
  `None` is a property that is not set.
- Each write is one statement. Outside a transaction, a write that Neo4j rejects with a transient
  error runs again, with the retry settings of the database (`retry_db_transaction`). Inside a
  transaction it runs once, because a failed statement aborts the transaction of the caller.
- `create_schema_change` creates the schema change with the status `running`, no version, the
  summary of the operations and the format version 1, one operation record for each operation
  with its index as `position`, and one application with the status `running`, the branch and
  `at`.
- `mark_applied` sets the schema change and the application to `applied`, and stores the version,
  `applied_at` and the `SCHEMA_CHANGE_HAS_PARENT` edge when `parent_id` is set. It returns whether
  it changed them, which is false when the schema change, its application or the parent is no
  longer stored.
- `mark_failed` sets both to `failed`, stores the error on the application, and closes the
  migration records of the application in the same statement: an `applied` record becomes
  `rolled_back`, a `waiting` one `cancelled`, and a `running` one `failed` with the error added to
  its errors; a `failed` one keeps its status. It returns whether it changed them, which is false
  when the schema change or its application is no longer stored, for example because the branch
  was deleted during the load.
- `mark_failed_if_running` sets the schema change and the application to `failed` with the error
  only while the schema change is `running`, and returns whether it changed them. It leaves the
  migration records as they are, because it is called for a cancelled load, whose migrations keep
  running and write their own statuses.
- `create_migration_records` raises `QueryError` when the application is not stored.
- `delete_branch_schema_changes` deletes the schema changes of the branch with their operations,
  applications and migration records, and returns the number of schema changes deleted. It runs
  outside a transaction, because its query commits each batch of `batch_size` records on its own
  ([research.md](../research.md), R13).
- `get_highest_applied_version_at` returns the applied schema change with the highest version
  among those of the branch whose `applied_at` is at or before `at`.
- A schema change with the status `running` or `failed` is never returned by the two version
  reads.

## `SchemaChangeHistoryReader`

The paged reads of the history query, in `history_reader.py`. Each result holds the records of
`models.py`, built from the rows of the `Query` classes.

```python
@dataclass(frozen=True)
class SchemaChangeHistoryEntry:
    schema_change: SchemaChange
    parent: SchemaChange | None


@dataclass(frozen=True)
class SchemaChangeHistoryPage:
    count: int
    entries: list[SchemaChangeHistoryEntry]


@dataclass(frozen=True)
class StoredSchemaOperation:
    position: int
    operation: SchemaOperation


@dataclass(frozen=True)
class SchemaOperationPage:
    count: int
    operations: list[StoredSchemaOperation]


@dataclass(frozen=True)
class SchemaChangeApplicationPage:
    count: int
    applications: list[SchemaChangeApplication]


@dataclass(frozen=True)
class SchemaChangeMigrationPage:
    count: int
    migrations: list[SchemaChangeMigration]


class SchemaChangeHistoryReader:
    def __init__(self, db: InfrahubDatabase, serializer: SchemaChangeRecordSerializer) -> None: ...

    async def list_schema_changes(
        self, *, branch: str, limit: int, offset: int, statuses: Sequence[SchemaChangeStatus] | None = None
    ) -> SchemaChangeHistoryPage: ...

    async def count_schema_changes(
        self, *, branch: str, statuses: Sequence[SchemaChangeStatus] | None = None
    ) -> int: ...

    async def list_operations(
        self, *, schema_change_ids: Sequence[str], limit: int, offset: int
    ) -> dict[str, SchemaOperationPage]: ...

    async def list_applications(
        self, *, schema_change_ids: Sequence[str], limit: int, offset: int
    ) -> dict[str, SchemaChangeApplicationPage]: ...

    async def list_migrations(
        self, *, application_ids: Sequence[str], limit: int, offset: int
    ) -> dict[str, SchemaChangeMigrationPage]: ...
```

- `list_schema_changes` orders the schema changes by `created_at`, the most recent first. `count` is the number of schema changes that match on all pages. `statuses` set to
  `None` filters nothing.
- `count_schema_changes` returns the same `count` as `list_schema_changes`, without reading a page.
  The query calls it when the request selects `count` and not `edges`.
- The three other reads return one page for each ID of `schema_change_ids` or `application_ids`
  that names a stored record, with `count`, the number of child records on all pages.
  `list_operations` returns the operations in the order of `position`, `list_applications` the
  applications in the order of `at`, then `uuid`, and `list_migrations` the migration records in
  the order of `position`.
- The ID keys are the `uuid` of each schema change or application, as text.

## `SchemaChangeVersionResolver`

Calculates the version and the parent of the next applied schema change of a branch
([research.md](../research.md), R10). It reads through the protocol `AppliedVersionReader`, which holds the two version reads of
`SchemaChangeRepository`, and writes nothing.

```python
@dataclass(frozen=True)
class SchemaChangeVersion:
    version: int
    parent_id: str | None


class SchemaChangeVersionResolver:
    def __init__(self, repository: AppliedVersionReader, default_branch_name: str) -> None: ...

    async def resolve_next(self, *, branch: Branch) -> SchemaChangeVersion: ...
```

- When the branch has an applied schema change, the version is its highest version plus 1, and
  the parent is the schema change with that highest version.
- Otherwise, for a branch that is not main, the base is the highest version among main's schema
  changes whose `applied_at` is at or before the branch's `branched_from`. The version is the
  base plus 1, and the parent is main's schema change with the base version.
- Otherwise the version is 1 and there is no parent.
- A schema change with the status `running` or `failed` never changes the result (FR-032).
- A branch is main when its name is `default_branch_name`. The resolver reads only the `name` and
  the `branched_from` of the branch, so a unit test builds a `Branch` without a database and
  passes a repository adapter that returns the versions of each case.
- The caller holds the schema lock, so the value is still correct when the caller writes it.

## `SchemaChangeRecorder`

Owns the statuses of the records. Writes through the protocol `SchemaChangeRecordStore`, which
holds `create_schema_change`, `mark_applied` and `mark_failed` of `SchemaChangeRepository`, and
uses `SchemaChangeVersionResolver` for the version and the parent.

```python
@dataclass(frozen=True)
class SchemaChangeRecording:
    schema_change_id: str
    application_id: str
    at: Timestamp


class SchemaChangeRecorder:
    def __init__(self, repository: SchemaChangeRecordStore, version_resolver: SchemaChangeVersionResolver) -> None: ...

    async def start(
        self, *, branch: Branch, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> SchemaChangeRecording: ...

    async def complete(self, *, recording: SchemaChangeRecording, branch: Branch, user_id: str) -> None: ...

    async def fail(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> bool: ...

    async def record_applied(
        self, *, branch: Branch, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> SchemaChangeRecording: ...
```

| Method | Schema change | Application | Migration records |
| --- | --- | --- | --- |
| `start` | created, `running`, no version | created, `running` | none yet |
| `complete` | `applied`, version, parent, `applied_at` | `applied` | unchanged |
| `fail` | `failed` | `failed`, with the error | `applied` becomes `rolled_back`, `waiting` becomes `cancelled`, `running` becomes `failed` with the error; `failed` is unchanged |
| `fail_if_running` | as `fail`, only while `running`; otherwise unchanged, and it returns `False` | as `fail`, only while the schema change is `running` | unchanged |
| `record_applied` | created, `applied`, version, parent, `applied_at` | created, `applied` | none |

- It has five entry methods because they are the steps of one schema change, and each needs the
  `SchemaChangeRecording` that an earlier one returned.
- `start` and `record_applied` raise `ValueError` with the message
  `A schema change needs at least one operation` when `operations` is empty, and store nothing.
- `complete` and `record_applied` take `branch` because they assign the version, and the
  resolver reads the name and the `branched_from` of the branch. `fail` assigns no version and
  takes no branch.
- `SchemaChangeRecording` holds the two IDs and the application's `at`, and no `Branch`, so
  that it can be built again from stored records. `complete` stores its `at` as `applied_at`
  without reading the application again. The caller passes to `complete` the branch that it
  passed to `start`.
- The caller holds the schema lock, so `complete` and `record_applied` can ask the resolver for
  the next version and write it without a second lock.
- The caller calls `record_applied` before `SchemaManager.update_schema_branch` inside the
  transaction. `update_schema_branch` replaces the schema in the registry of the process before
  the commit, so a record write that failed after it would leave the registry ahead of the
  database.
- `record_applied` is for a change that runs no migration and is saved in one transaction. The
  caller builds the repository, the resolver and the recorder with the database handle of that
  transaction.
- `at` is the timestamp of the graph writes. `complete` and `record_applied` store it as the
  schema change's `applied_at`.
- The recorder catches no error of the repository: a failed write of `complete` or `fail` reaches
  the caller. When `mark_applied` returns false, `complete` raises
  `SchemaChangeRecordNotFoundError` (HTTP 422); `fail` and `fail_if_running` return the result of
  the repository.

## `SchemaChangeApplicationRunner`

Applies a candidate schema to a branch and keeps the records in step with the result.

```python
class ApplicationRecorder(Protocol):
    async def start(
        self, *, branch: Branch, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> SchemaChangeRecording: ...

    async def complete(self, *, recording: SchemaChangeRecording, branch: Branch, user_id: str) -> None: ...

    async def fail(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> bool: ...


class SchemaUpdateExecutor(Protocol):
    async def execute(
        self,
        *,
        branch: Branch,
        origin_schema: SchemaBranch,
        rollback_schema: SchemaBranch,
        candidate_schema: SchemaBranch,
        at: Timestamp,
        context: InfrahubContext,
        diff: SchemaDiff,
        migrations: list[SchemaUpdateMigrationInfo],
        limit: list[str],
        user_id: str,
        application_id: str | None,
        final_step: SchemaUpdateFinalStep | None,
    ) -> str: ...


class SchemaChangeApplicationRunner:
    def __init__(self, recorder: ApplicationRecorder, executor: SchemaUpdateExecutor) -> None: ...

    async def run(
        self,
        *,
        branch: Branch,
        origin_schema: SchemaBranch,
        candidate: SchemaCandidate,
        at: Timestamp,
        context: InfrahubContext,
        user_id: str,
    ) -> str: ...
```

- The two `Protocol` classes are declared in `application_runner.py`, beside the runner, and hold
  only what the runner calls. `SchemaChangeRecorder` and
  `core/schema/update_coordinator.py::SchemaUpdateCoordinator` satisfy them by their signatures
  and do not import them. The unit tests of the runner pass a recording and a failing
  implementation of each, from `backend/tests/unit/core/schema_change/helpers.py`.
- The arguments of `SchemaUpdateExecutor.execute` are the ones the runner passes, each with a
  required type, because the runner always has a value for each. `application_id` is `None` for
  a candidate without operations.
  `SchemaUpdateCoordinator.execute` accepts wider types and has one signature after this feature
  removes its overloads ("Changed contracts"), so it satisfies the protocol.
- The runner passes the `user_id` and the `context` it received to the executor unchanged.
  `load_schema` passes the account of the request and the copy of the context that has the
  priority `HIGH`, as it passes them to the coordinator today. Without `user_id`, the schema
  vertices, the branch and the migrations of a load would be written as the system account.
- Returns the new schema hash.
- Calls `recorder.start`, then `executor.execute` with the application ID and a final step that
  calls `recorder.complete`. The coordinator runs the final step after it saved the schema and the
  migrations succeeded, and rolls the update back when it raises, so a schema change that cannot be
  recorded as `applied` fails the load (spec, decision 9). A failure of `recorder.start` reaches
  the caller before anything is written.
- When the candidate has no operation, calls only `executor.execute`, with
  `application_id=None` and no final step, and logs the warning
  `Applying a schema change that has no operation, without recording it` with `branch` and
  `diff`. No schema change is stored, and the migrations write no record.
- When the executor raises an `Exception`, the final step's included, calls `recorder.fail` with
  the text of the error, then raises the same exception. The caller receives the same error as
  today.
- When the load is cancelled (`asyncio.CancelledError`), calls `recorder.fail_if_running` with the
  error `The schema load was cancelled before it completed` inside `asyncio.shield`, then lets the
  cancellation go on. A schema change that the final step already recorded as `applied` keeps that
  status, and the runner logs a warning. The coordinator does not roll back a cancelled update
  ([research.md](../research.md), R8). When the cancellation arrives during `recorder.start`, the
  runner records nothing, and the schema change stays `running`.
- `run` always creates a new schema change. Applying a schema change that already exists, as the
  staging and replay tasks do, is not in this contract; those tasks extend it.
- When `recorder.fail` raises a `DatabaseError`, a `QueryError`, a `QueryTimeoutError` or a
  `neo4j` `Neo4jError` (`RECORD_WRITE_ERRORS`), the event
  `Could not record the failure of a schema change` is logged with `schema_change_id` and
  `application_id`, and the original exception is still raised. Any other exception that `recorder.fail` raises reaches the caller in place of the
  original one. When `recorder.fail` returns false, the records were deleted during the load, and
  the runner logs the warning
  `The records of the schema change were deleted before its failure could be recorded`, without a
  stack trace.

## `MigrationRecorder`

What the migration flow reports to. An interface with two implementations.

```python
class MigrationRecorder(ABC):
    @abstractmethod
    async def register(self, *, migrations: Sequence[SchemaUpdateMigrationInfo]) -> None: ...

    @abstractmethod
    async def migration_started(self, *, position: int) -> None: ...

    @abstractmethod
    async def migration_ended(self, *, position: int, result: SchemaMigrationPathResponseData) -> None: ...


class MigrationRecordStore(Protocol):
    async def create_migration_records(
        self, *, application_id: str, migrations: Sequence[SchemaUpdateMigrationInfo]
    ) -> None: ...

    async def set_migration_records_status(
        self,
        *,
        application_id: str,
        positions: Sequence[int],
        status: SchemaChangeMigrationStatus,
        nbr_migrations_executed: int | None,
        errors: Sequence[str],
    ) -> None: ...
```

- Modules: `migration_recorder.py` holds the `MigrationRecorder` interface and
  `NoRecordMigrationRecorder`, and imports nothing that reaches the database.
  `application_migration_recorder.py` holds `ApplicationMigrationRecorder` and
  `MigrationRecordStore`. The flow imports the interface; only `factory.py` imports both.
- `ApplicationMigrationRecorder(store, application_id)`: `register` creates one record for each
  migration with the status `waiting`, and keeps the positions it created.
  `migration_started` sets the record at its position to `running`. `migration_ended` sets
  one record to `applied` when the result has no error, or to `failed` with the errors, and
  stores `nbr_migrations_executed`. When `register` could not create the records, the two other
  methods write nothing for the positions that have no record.
- `MigrationRecordStore` holds the two methods the recorder calls. `SchemaChangeRepository`
  satisfies it by its signatures. The unit tests pass a store that records each call and raises
  for the methods named.
- The migrations run concurrently and the database session of the store runs one query at a time,
  so the recorder makes its writes one after the other behind a lock.
- The runner and the migration recorder catch the same errors of a record write, the tuple
  `RECORD_WRITE_ERRORS` of `core/schema_change/record_errors.py`.
- The application ID is a constructor argument, because one recorder serves one application for
  the length of one flow run, and the interface is shared with a recorder that has no
  application.
- `position` is the index of the migration in the migrations of the flow message sorted by schema
  path, then by migration name (`core/migrations/schema/tasks.py::position_migrations`). The diff
  lists the migrations in the order of a set, so the sort keeps the positions the same between two
  runs of one load. Every method identifies a migration by its position, because two migrations
  of one application can have the same name and the same schema path.
- The flow splits the migrations into two phases and reads results in the order they complete, so
  it pairs each migration with its position once, in a `PositionedMigration`. Both phases and
  every result carry that position, and `register` receives the sorted list.
- `migration_started` is called by the task of one migration when it starts
  (`_migrate_schema_path_at_position`), so a record is `running` only while its migration runs.
- `NoRecordMigrationRecorder`: does nothing. Used when the message has no application ID.
- The values `ApplicationMigrationRecorder` passes to `set_migration_records_status`:
  - `migration_started`: the application ID, the position in a list of one, the status `running`,
    `nbr_migrations_executed=None` and no error;
  - `migration_ended`: the application ID, the position in a list of one, the status `applied` with no error when the
    result has no error, or `failed` with the errors of the result, and the
    `nbr_migrations_executed` of the result in both cases.
- A failure to write a record does not stop a migration: the migration records report progress
  and are best effort. It is logged after the retries of the repository, and the record keeps its
  earlier status. The recorder catches the `DatabaseError`, the `QueryError` (raised when the
  application does not exist), the `QueryTimeoutError` and the `neo4j` `Neo4jError` (which covers
  a transient error such as a deadlock) that the store raises, and logs a warning with `get_logger()` and `exc_info=True`, with these events and fields:

  | Method | Event | Fields |
  | --- | --- | --- |
  | `register` | `Could not create the migration records of an application` | `application_id` |
  | `migration_started` | `Could not set the migration record of a migration to running` | `application_id`, `position` |
  | `migration_ended` | `Could not update the migration record of a migration` | `application_id`, `position` |

## The seeding function of the tests

`backend/tests/helpers/schema_change.py` creates a history through `SchemaChangeRepository`, so no
test module writes these records by hand. It does not use the version resolver, so the tests of
the resolver can use it.

```python
async def seed_schema_change_history(
    *, db: InfrahubDatabase, branches: Sequence[BranchHistorySeed], user_id: str = SYSTEM_USER_ID
) -> SeededSchemaChangeHistory: ...
```

- `BranchHistorySeed(branch, changes, nbr_operations=1, migrations=(), first_version=1, first_parent_id=None)`:
  `changes` lists the status of each schema change of the branch (`applied`, `failed` or
  `running`) in the order they are created, so the counts of each status and the order of
  `created_at` are both set. `migrations` is a list of `MigrationSeed(migration, status,
  nbr_migrations_executed, errors)`, the migrations of the application of each schema change.
- An applied schema change gets `first_version`, then the next versions, through `mark_applied`,
  with `applied_at` equal to the timestamp of its application. The first one gets
  `first_parent_id` as its parent, the next ones the applied schema change before them. A seed for
  a branch passes the ID of main's schema change as `first_parent_id`.
- A failed schema change gets its error through `mark_failed`, after its migration records got
  their statuses.
- Each operation sets `label` on the attribute `color` of `TestCar`, with the value
  `Color <position>`. A schema change with one operation has the summary `testcar_color_update`.
- The result lists every `SeededSchemaChange` in the order of creation, with the IDs, the
  version, the parent ID, the timestamp `at` and the operations.

## Where the components are built

`backend/infrahub/core/schema_change/factory.py` holds the functions that build the components.
Each takes `db` and plain values, and reads no setting and no registry. The entry point passes
`registry.default_branch` as `default_branch_name`.

| Function | Returns | Called by |
| --- | --- | --- |
| `build_schema_candidate_builder()` | `SchemaCandidateBuilder` with its operation builder, its applier and its comparer | `api/schema.py::load_schema` and `api/schema.py::check_schema`, each at its top, and `graphql/mutations/schema.py::apply_attribute_property_change` |
| `build_schema_change_repository(db)` | `SchemaChangeRepository` with its serializer | the branch deletion in `core/branch/tasks.py` and in the graph migrations `m032` and `m075`, and the functions below |
| `build_schema_change_history_reader(db)` | `SchemaChangeHistoryReader` with its serializer | the history query and its loaders |
| `build_schema_change_recorder(db, default_branch_name)` | `SchemaChangeRecorder` with its repository and version resolver | `apply_attribute_property_change`, and the function below |
| `build_schema_change_application_runner(db, executor, default_branch_name)` | `SchemaChangeApplicationRunner` | `load_schema`, at its top and before the schema lock. It builds the `SchemaUpdateCoordinator` there and passes it as `executor` |
| `build_migration_recorder(db, application_id)` | `ApplicationMigrationRecorder` when `application_id` is set, `NoRecordMigrationRecorder` otherwise | `core/migrations/schema/tasks.py::schema_apply_migrations`, at its top |

One place builds a component after the work started, and it is deliberate:
`apply_attribute_property_change` calls `build_schema_change_recorder` inside its
`db.start_transaction()` block, because the database handle of the transaction exists only there.

## Changed contracts

| Component | Change |
| --- | --- |
| `core/migrations/schema/models.py::SchemaApplyMigrationData` | New optional field `application_id: str \| None`, default `None`. The hand-written `serialize_model` is replaced by field serializers, because it lists its keys and would drop the new field before the message reaches a task worker |
| `core/schema/update_coordinator.py::SchemaUpdateCoordinator.execute` | New keyword argument `application_id: str \| None` without a default, passed to the message. New keyword argument `final_step: SchemaUpdateFinalStep \| None`, default `None`, which runs after the schema is saved and the migrations succeed; when it raises, the update is rolled back like a failed migration. The argument `update_registry` and the three overloads are removed, because no caller passes `False`. The callers in `cli/db.py`, `core/branch/tasks.py` and `core/merge/orchestrator.py` pass `application_id=None` |
| `core/migrations/schema/models.py::SchemaMigrationPathResponseData` | `migration_name` and `schema_path` are required |
| `core/migrations/schema/tasks.py::schema_apply_migrations` | Calls `get_database()` once at its top, builds a `MigrationRecorder` with `build_migration_recorder` on a session started from that database, sorts the migrations by schema path and pairs each one with its position in that order. Return value unchanged |
| `core/migrations/schema/tasks.py::split_migrations_by_phase` and `::_apply_migration_batch` | Take `PositionedMigration` items. `_apply_migration_batch` takes the recorder and the database |
| `api/schema.py::evaluate_candidate_schemas` | Replaced by `build_candidate_from_schemas`. Five calls in three component test modules call the candidate builder directly |
| `api/schema.py::check_schema` | Calls `_validate_migrations` in place of its own copy of the constraint workflow call |
| `graphql/mutations/schema.py::update_registry` | Replaced by `apply_attribute_property_change` |
| `core/branch/data_deleter.py::BranchDataDeleter` | Takes a `SchemaChangeRecordDeleter`, the protocol of `SchemaChangeRepository.delete_branch_schema_changes`, as a constructor argument. `delete_branch_data` also deletes the schema change records of the branch, in batches of the deleter's batch size. The number of edges it returns does not count the edges of these records |
| `exceptions.py` | New errors `SchemaOperationTargetNotFoundError` and `SchemaOperationTargetExistsError` (HTTP 422), raised by the applier, and `SchemaNameReusedError` (HTTP 422) and `SchemaOperationsRebuildError` (HTTP 422), raised by `from_schema_root` |
| `POST /api/schema/load` | Request and response unchanged. Stores a schema change when the schema changed |
| `POST /api/schema/check` | Request and response unchanged. Stores nothing |
| `SchemaDropdownAdd`, `SchemaDropdownRemove`, `SchemaEnumAdd`, `SchemaEnumRemove` | Input and payload unchanged. Each stores a schema change when the schema changed |
