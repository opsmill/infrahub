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
  returned so that no caller processes the file again.
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
- Given the same target and the same operations, it returns a schema with the same hash each time.
- The six operation types are a closed set. The applier selects the handling of an operation with
  an exhaustive `match` on `SchemaOperationType` that ends with `typing.assert_never`, so a type
  added with a later format version fails the type check until the applier handles it.

## `SchemaCandidateComparer`

Compares two processed schemas. No database access, and it writes no log.

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

- `validation.diff` is the diff between `branch_schema` and the applier's result.
  `validation.migrations` and `validation.constraints` are calculated from that diff, after
  processing.
- Runs `validate_node_deletions` on the applier's result.
- `from_schema_root` passes the `direct_load_schema` of the operation builder and the applier's
  result to the comparer, and logs a warning that names the kinds the comparer returns. It does not
  refuse the load, and it processes the schema twice in all: once in the operation builder and
  once in the applier.
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

## `SchemaChangeVersionResolver`

Calculates the version and the parent of the next applied schema change of a branch
([research.md](../research.md), R10). It reads through `SchemaChangeRepository` and writes
nothing.

```python
@dataclass(frozen=True)
class SchemaChangeVersion:
    version: int
    parent_id: str | None


class SchemaChangeVersionResolver:
    def __init__(self, repository: SchemaChangeRepository, default_branch_name: str) -> None: ...

    async def resolve_next(self, *, branch: Branch) -> SchemaChangeVersion: ...
```

- When the branch has an applied schema change, the version is its highest version plus 1, and
  the parent is the schema change with that highest version.
- Otherwise, for a branch that is not main, the base is the highest version among main's schema
  changes whose `applied_at` is at or before the branch's `branched_from`. The version is the
  base plus 1, and the parent is main's schema change with the base version.
- Otherwise the version is 1 and there is no parent.
- A schema change with the status `running` or `failed` never changes the result (FR-032).
- The caller holds the schema lock, so the value is still correct when the caller writes it.

## `SchemaChangeRecorder`

Owns the statuses of the records. Uses `SchemaChangeRepository` for the writes and
`SchemaChangeVersionResolver` for the version and the parent.

```python
@dataclass(frozen=True)
class SchemaChangeRecording:
    schema_change_id: str
    application_id: str


class SchemaChangeRecorder:
    def __init__(self, repository: SchemaChangeRepository, version_resolver: SchemaChangeVersionResolver) -> None: ...

    async def start(
        self, *, branch: Branch, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> SchemaChangeRecording: ...

    async def complete(self, *, recording: SchemaChangeRecording, branch: Branch, user_id: str) -> None: ...

    async def fail(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> None: ...

    async def record_applied(
        self, *, branch: Branch, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> SchemaChangeRecording: ...
```

| Method | Schema change | Application | Migration records |
| --- | --- | --- | --- |
| `start` | created, `running`, no version | created, `running` | none yet |
| `complete` | `applied`, version, parent, `applied_at` | `applied` | unchanged |
| `fail` | `failed` | `failed`, with the error | `applied` becomes `rolled_back`; the others are unchanged |
| `record_applied` | created, `applied`, version, parent, `applied_at` | created, `applied` | none |

- It has four entry methods because they are the steps of one schema change, and each needs the
  `SchemaChangeRecording` that an earlier one returned.
- `start` and `record_applied` raise when `operations` is empty.
- `complete` and `record_applied` take `branch` because they assign the version, and the
  resolver reads the name and the `branched_from` of the branch. `fail` assigns no version and
  takes no branch.
- `SchemaChangeRecording` holds two IDs and no `Branch`, so that it can be built again from
  stored records. The caller passes to `complete` the branch that it passed to `start`.
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

## `SchemaChangeApplicationRunner`

Applies a candidate schema to a branch and keeps the records in step with the result.

```python
class ApplicationRecorder(Protocol):
    async def start(
        self, *, branch: Branch, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> SchemaChangeRecording: ...

    async def complete(self, *, recording: SchemaChangeRecording, branch: Branch, user_id: str) -> None: ...

    async def fail(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> None: ...


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
        application_id: str,
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
  required type, because the runner always has a value for each.
  `SchemaUpdateCoordinator.execute` accepts wider types and has one signature after this feature
  removes its overloads ("Changed contracts"), so it satisfies the protocol.
- The runner passes the `user_id` and the `context` it received to the executor unchanged.
  `load_schema` passes the account of the request and the copy of the context that has the
  priority `HIGH`, as it passes them to the coordinator today. Without `user_id`, the schema
  vertices, the branch and the migrations of a load would be written as the system account.
- Returns the new schema hash.
- Calls `recorder.start`, then `executor.execute` with the application ID, then
  `recorder.complete`.
- When the executor raises, calls `recorder.fail` with the text of the error, then raises the
  same exception. The caller receives the same error as today.
- `run` always creates a new schema change. Applying a schema change that already exists, as the
  staging and replay tasks do, is not in this contract; those tasks extend it.
- When `recorder.fail` itself raises, the original exception is still raised, and the failure of
  the record update is logged.

## `MigrationRecorder`

What the migration flow reports to. An interface with two implementations.

```python
class MigrationRecorder(ABC):
    @abstractmethod
    async def register(self, *, migrations: Sequence[SchemaUpdateMigrationInfo]) -> None: ...

    @abstractmethod
    async def batch_started(self, *, positions: Sequence[int]) -> None: ...

    @abstractmethod
    async def migration_ended(self, *, position: int, result: SchemaMigrationPathResponseData) -> None: ...


class MigrationRecordStore(Protocol):
    async def create_migration_records(
        self, *, application_id: str, migrations: Sequence[SchemaUpdateMigrationInfo]
    ) -> dict[int, str]: ...

    async def set_migration_records_status(
        self,
        *,
        record_ids: Sequence[str],
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
  migration with the status `waiting`, and keeps the ID of each record by its position.
  `batch_started` sets the records at the positions given to `running`. `migration_ended` sets
  one record to `applied` when the result has no error, or to `failed` with the errors, and
  stores `nbr_migrations_executed`.
- `MigrationRecordStore` holds the two methods the recorder calls. `SchemaChangeRepository`
  satisfies it by its signatures. A unit test passes a store that raises on every call.
- The application ID is a constructor argument, because one recorder serves one application for
  the length of one flow run, and the interface is shared with a recorder that has no
  application.
- `position` is the index of the migration in the list of the flow message. Every method
  identifies a migration by its position, because two migrations of one application can have the
  same name and the same schema path.
- The flow splits the migrations of the message into two phases and reads results in the order
  they complete, so it pairs each migration with its position once, from the list of the
  message, in a `PositionedMigration` (`core/migrations/schema/tasks.py`). Both phases and every
  result carry that position.
- `batch_started` receives every position of a phase when the phase starts. The phase of the
  kind updates runs one migration at a time, so its records have the status `running` while
  most of them wait.
- `NoRecordMigrationRecorder`: does nothing. Used when the message has no application ID.
- A failure to write a record does not stop a migration. It is logged, and the record keeps its
  earlier status.

## Where the components are built

`backend/infrahub/core/schema_change/factory.py` holds the functions that build the components.
Each takes `db` and plain values, and reads no setting and no registry. The entry point passes
`registry.default_branch` as `default_branch_name`.

| Function | Returns | Called by |
| --- | --- | --- |
| `build_schema_candidate_builder()` | `SchemaCandidateBuilder` with its operation builder, applier and comparer | `api/schema.py::load_schema` and `api/schema.py::check_schema`, each at its top, and `graphql/mutations/schema.py::apply_attribute_property_change` |
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
| `core/schema/update_coordinator.py::SchemaUpdateCoordinator.execute` | New keyword argument `application_id: str \| None` without a default, passed to the message. The argument `update_registry` and the three overloads are removed, because no caller passes `False`. The callers in `cli/db.py`, `core/branch/tasks.py` and `core/merge/orchestrator.py` pass `application_id=None` |
| `core/migrations/schema/tasks.py::schema_apply_migrations` | Calls `get_database()` once at its top, builds a `MigrationRecorder` with `build_migration_recorder`, and pairs each migration with its position in the message. Return value unchanged |
| `core/migrations/schema/tasks.py::split_migrations_by_phase` and `::_apply_migration_batch` | Take `PositionedMigration` items. `_apply_migration_batch` takes the recorder and the database |
| `api/schema.py::evaluate_candidate_schemas` | Replaced by `build_candidate_from_schemas`. Five calls in three component test modules call the candidate builder directly |
| `api/schema.py::check_schema` | Calls `_validate_migrations` in place of its own copy of the constraint workflow call |
| `graphql/mutations/schema.py::update_registry` | Replaced by `apply_attribute_property_change` |
| `core/branch/data_deleter.py::BranchDataDeleter.delete_branch_data` | Also deletes the schema change records of the branch |
| `POST /api/schema/load` | Request and response unchanged. Stores a schema change when the schema changed |
| `POST /api/schema/check` | Request and response unchanged. Stores nothing |
| `SchemaDropdownAdd`, `SchemaDropdownRemove`, `SchemaEnumAdd`, `SchemaEnumRemove` | Input and payload unchanged. Each stores a schema change when the schema changed |
