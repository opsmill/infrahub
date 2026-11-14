# Internal interfaces

These are the components that this feature adds or changes inside the back end. The later tasks of
the epic (progress, staging, ordered replay, core schema update) call them, so their contracts are
written here. Signatures are indicative; the behaviour is the contract.

New code is in `backend/infrahub/core/schema_change/`. Each component receives its collaborators in
its constructor and has one entry method, as `dev/guidelines/backend/component-design.md` asks.

## `SchemaOperationBuilder`

Builds the operations of a schema load. No database access.

```python
class SchemaOperationBuilder:
    def build(
        self,
        *,
        branch_schema: SchemaBranch,
        schema_root: SchemaRoot,
        default_branch_schema: SchemaBranch,
    ) -> list[SchemaOperation]: ...
```

- Returns an empty list when the file changes nothing after processing.
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

## `SchemaCandidateBuilder`

The one way to build a candidate schema from user input.

```python
@dataclass(frozen=True)
class SchemaCandidate:
    operations: list[SchemaOperation]
    schema: SchemaBranch
    validation: SchemaUpdateValidationResult


class SchemaCandidateBuilder:
    def __init__(self, operation_builder: SchemaOperationBuilder, applier: SchemaChangeApplier) -> None: ...

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
- `from_schema_root` logs a warning that names the kinds whose hash differs between the processed
  schema of the laid-over file and the applier's result. It does not refuse the load.
- `api/schema.py::evaluate_candidate_schemas` calls `from_schema_root` and keeps its return type.

## `SchemaChangeRecorder`

Owns the statuses of the records. Uses `SchemaChangeRepository`.

```python
@dataclass(frozen=True)
class SchemaChangeRecording:
    schema_change_id: str
    application_id: str


class SchemaChangeRecorder:
    def __init__(self, repository: SchemaChangeRepository, default_branch_name: str) -> None: ...

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

- `start` and `record_applied` raise when `operations` is empty.
- The caller holds the schema lock, so `complete` and `record_applied` can read the highest
  version and write the next one without a second lock.
- `record_applied` is for a change that runs no migration and is saved in one transaction. The
  caller builds the repository with the database handle of that transaction.
- `at` is the timestamp of the graph writes. `complete` and `record_applied` store it as the
  schema change's `applied_at`.

## `SchemaChangeApplicationRunner`

Applies a candidate schema to a branch and keeps the records in step with the result.

```python
class SchemaChangeApplicationRunner:
    def __init__(self, recorder: SchemaChangeRecorder, coordinator: SchemaUpdateCoordinator) -> None: ...

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

- Returns the new schema hash.
- Calls `recorder.start`, then `SchemaUpdateCoordinator.execute` with the application ID, then
  `recorder.complete`.
- When the coordinator raises, calls `recorder.fail` with the text of the error, then raises the
  same exception. The caller receives the same error as today.
- When `recorder.fail` itself raises, the original exception is still raised, and the failure of
  the record update is logged.

## `MigrationRecorder`

What the migration flow reports to. An interface with two implementations.

```python
class MigrationRecorder(ABC):
    @abstractmethod
    async def register(self, *, migrations: Sequence[SchemaUpdateMigrationInfo]) -> None: ...

    @abstractmethod
    async def batch_started(self, *, migrations: Sequence[SchemaUpdateMigrationInfo]) -> None: ...

    @abstractmethod
    async def migration_ended(self, *, position: int, result: SchemaMigrationPathResponseData) -> None: ...
```

- `ApplicationMigrationRecorder(repository, application_id)`: `register` creates one record for
  each migration with the status `waiting`. `batch_started` sets the records of the batch to
  `running`. `migration_ended` sets one record to `applied` when the result has no error, or to
  `failed` with the errors, and stores `nbr_migrations_executed`.
- `position` is the index of the migration in the list of the flow message. The flow keeps the
  position of each migration it submits and passes it with the result.
- `NoRecordMigrationRecorder`: does nothing. Used when the message has no application ID.
- A failure to write a record does not stop a migration. It is logged, and the record keeps its
  earlier status.

## Changed contracts

| Component | Change |
| --- | --- |
| `core/migrations/schema/models.py::SchemaApplyMigrationData` | New optional field `application_id: str \| None`, default `None` |
| `core/schema/update_coordinator.py::SchemaUpdateCoordinator.execute` | New optional argument `application_id: str \| None`, default `None`, passed to the message |
| `core/migrations/schema/tasks.py::schema_apply_migrations` | Builds a `MigrationRecorder` at its top. Return value unchanged |
| `core/branch/data_deleter.py::BranchDataDeleter.delete_branch_data` | Also deletes the schema change records of the branch |
| `POST /api/schema/load` | Request and response unchanged. Stores a schema change when the schema changed |
| `POST /api/schema/check` | Request and response unchanged. Stores nothing |
| `SchemaDropdownAdd`, `SchemaDropdownRemove`, `SchemaEnumAdd`, `SchemaEnumRemove` | Input and payload unchanged. Each stores a schema change when the schema changed |
