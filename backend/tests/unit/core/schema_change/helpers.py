from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, override

from neo4j import Record
from neo4j.exceptions import TransientError

from infrahub.core.constants import DEFAULT_NAME_MAX_LENGTH, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import (
    AttributeSchema,
    DropdownChoice,
    GenericSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaExtension,
    SchemaRoot,
)
from infrahub.core.schema.derived_kinds import get_object_template_kind, get_profile_kind
from infrahub.core.schema_change.application_runner import ApplicationRecorder, SchemaUpdateExecutor
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder, SchemaOperationBuildResult
from infrahub.core.schema_change.recorder import SchemaChangeRecording, SchemaChangeRecordStore
from infrahub.core.schema_change.version_resolver import AppliedVersionReader
from infrahub.database import InfrahubDatabase, InfrahubDatabaseMode
from infrahub.exceptions import DatabaseError
from tests.constants import TestKind
from tests.helpers.schema import DEVICE, INTERFACE, INTERFACE_HOLDER, PHYSICAL_INTERFACE, SFP, TAG, VIRTUAL_INTERFACE

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Mapping, Sequence

    from pydantic import JsonValue

    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.core.models import SchemaDiff, SchemaUpdateMigrationInfo, SchemaUpdateValidationResult
    from infrahub.core.query import QueryType
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema.update_coordinator import MigrationExecutor, SchemaUpdateFinalStep
    from infrahub.core.schema_change.enums import SchemaChangeMigrationStatus, SchemaChangeSource
    from infrahub.core.schema_change.operations import SchemaOperation
    from infrahub.core.schema_change.repository import AppliedSchemaChangeVersion, CreatedSchemaChange
    from infrahub.core.timestamp import Timestamp

TAG_STATUS_ATTRIBUTE = "status"
DEVICE_SPARE_SFPS_RELATIONSHIP = "spare_sfps"


def _device_definition() -> NodeSchema:
    device = DEVICE.duplicate()
    device.relationships.append(
        RelationshipSchema(
            name=DEVICE_SPARE_SFPS_RELATIONSHIP,
            peer=TestKind.SFP,
            kind=RelationshipKind.GENERIC,
            cardinality=RelationshipCardinality.MANY,
            optional=True,
        )
    )
    return device


def _tag_definition() -> NodeSchema:
    tag = TAG.duplicate()
    tag.generate_profile = False
    tag.order_by = ["name__value"]
    tag.attributes.append(
        AttributeSchema(
            name=TAG_STATUS_ATTRIBUTE,
            kind="Dropdown",
            optional=True,
            choices=[
                DropdownChoice(name="active", color="#2e7d32"),
                DropdownChoice(name="reserved", color="#f9a825"),
                DropdownChoice(name="retired", color="#c62828"),
            ],
        )
    )
    return tag


BASE_NAMESPACE = "Testing"
COUNTER_KIND = f"{BASE_NAMESPACE}Counter"
BOUNDS_POOL_ATTRIBUTE = "bounds_number"
RANGES_POOL_ATTRIBUTE = "ranges_number"
BOUNDS_POOL_PARAMETERS: dict[str, JsonValue] = {"start_range": 50, "end_range": 1200}
RANGES_POOL_PARAMETERS: dict[str, JsonValue] = {"ranges": [{"start": 1, "end": 10}, {"start": 100, "end": 200}]}


def counter_definition(
    *,
    namespace: str = BASE_NAMESPACE,
    bounds_parameters: dict[str, JsonValue] = BOUNDS_POOL_PARAMETERS,
    ranges_parameters: dict[str, JsonValue] = RANGES_POOL_PARAMETERS,
) -> NodeSchema:
    """Return a node that holds one number pool declared by range bounds and one declared by ranges."""
    return NodeSchema(
        name="Counter",
        namespace=namespace,
        label="Counter",
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(
                name=BOUNDS_POOL_ATTRIBUTE, kind="NumberPool", read_only=True, parameters=bounds_parameters
            ),
            AttributeSchema(
                name=RANGES_POOL_ATTRIBUTE, kind="NumberPool", read_only=True, parameters=ranges_parameters
            ),
        ],
    )


_BASE_DEFINITIONS: dict[str, Callable[[], NodeSchema | GenericSchema]] = {
    TestKind.INTERFACE: INTERFACE.duplicate,
    TestKind.INTERFACE_HOLDER: INTERFACE_HOLDER.duplicate,
    TestKind.DEVICE: _device_definition,
    TestKind.PHYSICAL_INTERFACE: PHYSICAL_INTERFACE.duplicate,
    TestKind.VIRTUAL_INTERFACE: VIRTUAL_INTERFACE.duplicate,
    TestKind.SFP: SFP.duplicate,
    TestKind.TAG: _tag_definition,
    COUNTER_KIND: counter_definition,
}

INTERFACE_KINDS: tuple[str, ...] = (
    TestKind.INTERFACE_HOLDER,
    TestKind.INTERFACE,
    TestKind.DEVICE,
    TestKind.PHYSICAL_INTERFACE,
    TestKind.VIRTUAL_INTERFACE,
    TestKind.SFP,
)
TAG_KINDS: tuple[str, ...] = (TestKind.TAG,)


def base_node_definition(kind: str) -> NodeSchema:
    """Return a new copy of a node of the base schema, as a schema file writes it.

    Raises:
        TypeError: When the kind is not a node of the base schema.

    """
    definition = _BASE_DEFINITIONS[kind]()
    if not isinstance(definition, NodeSchema):
        raise TypeError(f"{kind} is not a node of the base schema")
    return definition


def base_generic_definition(kind: str) -> GenericSchema:
    """Return a new copy of a generic of the base schema, as a schema file writes it.

    Raises:
        TypeError: When the kind is not a generic of the base schema.

    """
    definition = _BASE_DEFINITIONS[kind]()
    if not isinstance(definition, GenericSchema):
        raise TypeError(f"{kind} is not a generic of the base schema")
    return definition


def build_base_schema_root() -> SchemaRoot:
    """Return a new copy of the base schema of the equivalence suite, without IDs.

    It has a generic with attributes and a relationship that two nodes inherit, an optional
    relationship without a peer relationship, a dropdown attribute, unique attributes, a node with
    a human friendly ID and a uniqueness constraint, and a node that generates no profile and has
    an order.
    """
    return SchemaRoot(
        generics=[base_generic_definition(kind) for kind in (TestKind.INTERFACE, TestKind.INTERFACE_HOLDER)],
        nodes=[
            base_node_definition(kind)
            for kind in (
                TestKind.DEVICE,
                TestKind.PHYSICAL_INTERFACE,
                TestKind.VIRTUAL_INTERFACE,
                TestKind.SFP,
                TestKind.TAG,
            )
        ],
    )


def schema_element_id(schema: SchemaBranch, kind: str, element_name: str | None = None) -> str:
    """Return the ID of a kind, or of one of its attributes or relationships, in a schema.

    Raises:
        ValueError: When the kind or the element has no ID.

    """
    node = schema.get(name=kind, duplicate=False)
    element = node if element_name is None else node.get_field(name=element_name)
    if element.id is None:
        raise ValueError(f"{kind} {element_name or ''} has no ID in the schema")
    return element.id


@dataclass(frozen=True)
class CaseScope:
    """Copies base kinds into the namespace of one case, so that the changes of several cases can be loaded together."""

    namespace: str

    def kind(self, base_kind: str) -> str:
        """Return the kind that a base kind becomes in the namespace.

        Raises:
            ValueError: When the kind is not a kind of the base schema.

        """
        if base_kind not in _BASE_DEFINITIONS:
            raise ValueError(f"{base_kind} is not a kind of the base schema")
        return f"{self.namespace}{base_kind.removeprefix(BASE_NAMESPACE)}"

    def definition(self, base_kind: str) -> NodeSchema | GenericSchema:
        """Return a new copy of a base kind in the namespace, with its generics and peers moved there too."""
        definition = _BASE_DEFINITIONS[base_kind]()
        definition.namespace = self.namespace
        if isinstance(definition, NodeSchema):
            definition.inherit_from = [self._moved_kind(kind) for kind in definition.inherit_from]
        for relationship in definition.relationships:
            relationship.peer = self._moved_kind(relationship.peer)
            if relationship.identifier is not None:
                # The two sides of a relationship are matched by identifier across every kind of the schema.
                relationship.identifier = f"{self.namespace.lower()}_{relationship.identifier}"
        return definition

    def node(self, base_kind: str) -> NodeSchema:
        """Return a new copy of a base node in the namespace.

        Raises:
            TypeError: When the kind is not a node of the base schema.

        """
        definition = self.definition(base_kind)
        if not isinstance(definition, NodeSchema):
            raise TypeError(f"{base_kind} is not a node of the base schema")
        return definition

    def generic(self, base_kind: str) -> GenericSchema:
        """Return a new copy of a base generic in the namespace.

        Raises:
            TypeError: When the kind is not a generic of the base schema.

        """
        definition = self.definition(base_kind)
        if not isinstance(definition, GenericSchema):
            raise TypeError(f"{base_kind} is not a generic of the base schema")
        return definition

    def schema_root(self, base_kinds: Sequence[str]) -> SchemaRoot:
        definitions = [self.definition(base_kind) for base_kind in base_kinds]
        return SchemaRoot(
            generics=[definition for definition in definitions if isinstance(definition, GenericSchema)],
            nodes=[definition for definition in definitions if isinstance(definition, NodeSchema)],
        )

    def element_id(self, schema: SchemaBranch, base_kind: str, element_name: str | None = None) -> str:
        return schema_element_id(schema, self.kind(base_kind), element_name)

    def _moved_kind(self, kind: str) -> str:
        return self.kind(kind) if kind in _BASE_DEFINITIONS else kind


@dataclass(frozen=True)
class CombinedLoadCase:
    name: str
    namespace: str
    base_kinds: tuple[str, ...]
    """Every base kind that the case copies into its namespace, including each peer and generic they name."""

    schema_file: Callable[[CaseScope, SchemaBranch], SchemaRoot]
    """Builds a new schema file on each call, because a load changes the file; it reads IDs from the schema."""

    base_file: Callable[[CaseScope], SchemaRoot] | None = None
    """Builds the base of the case when it is not the plain copies of `base_kinds`."""

    @property
    def scope(self) -> CaseScope:
        return CaseScope(namespace=self.namespace)

    def build_base_file(self) -> SchemaRoot:
        """Return the base kinds of the case in its namespace.

        Raises:
            ValueError: When the base kinds name a base kind that `base_kinds` leaves out, when the
                base file defines other kinds than `base_kinds`, or when a kind is too long to name its
                profile and template kinds.

        """
        scope = self.scope
        base_file = scope.schema_root(self.base_kinds) if self.base_file is None else self.base_file(scope)
        definitions = [*base_file.generics, *base_file.nodes]
        declared = {scope.kind(base_kind) for base_kind in self.base_kinds}
        defined = {definition.kind for definition in definitions}
        if defined != declared:
            raise ValueError(f"{self.name}: the base file defines {sorted(defined)}, not {sorted(declared)}")
        # A profile or template kind takes the whole kind it is made from as its name.
        if too_long := sorted(kind for kind in defined if len(kind) > DEFAULT_NAME_MAX_LENGTH):
            raise ValueError(f"{self.name}: {too_long} are longer than {DEFAULT_NAME_MAX_LENGTH} characters")
        moved = {scope.kind(base_kind) for base_kind in _BASE_DEFINITIONS}
        named = {
            kind
            for definition in definitions
            for kind in [
                *(definition.inherit_from if isinstance(definition, NodeSchema) else []),
                *(relationship.peer for relationship in definition.relationships),
            ]
        }
        if missing := (named & moved) - declared:
            raise ValueError(f"{self.name}: base_kinds must also name {sorted(missing)}")
        return base_file

    def owned_kinds(self, *, base_schema: SchemaBranch, result_schema: SchemaBranch) -> frozenset[str]:
        """Return the kinds of the case before and after its change, with the profile and template kinds made from them.

        A kind that the case renames or moves to another namespace keeps its ID, which ties it to the case.
        """
        kinds_before = {
            name
            for name in base_schema.node_names + base_schema.generic_names
            if base_schema.get(name=name, duplicate=False).namespace == self.namespace
        }
        ids_before = {base_schema.get(name=name, duplicate=False).id for name in kinds_before} - {None}
        kinds_after = {
            name
            for name in result_schema.node_names + result_schema.generic_names
            if (node := result_schema.get(name=name, duplicate=False)).namespace == self.namespace
            or node.id in ids_before
        }
        kinds = kinds_before | kinds_after
        return frozenset(
            kinds | {get_profile_kind(kind) for kind in kinds} | {get_object_template_kind(kind) for kind in kinds}
        )


def merge_schema_files(schema_files: Iterable[SchemaRoot]) -> SchemaRoot:
    files = list(schema_files)
    return SchemaRoot(
        generics=[generic for schema_file in files for generic in schema_file.generics],
        nodes=[node for schema_file in files for node in schema_file.nodes],
        extensions=SchemaExtension(
            nodes=[extension for schema_file in files for extension in schema_file.extensions.nodes]
        ),
    )


@dataclass(frozen=True)
class EquivalenceCase:
    name: str
    schema_file: Callable[[SchemaBranch], SchemaRoot]
    """Builds a new schema file on each call; it receives the shared schema to read the IDs that a rename needs."""


@dataclass(frozen=True)
class SchemaLoadResult:
    schema: SchemaBranch
    validation: SchemaUpdateValidationResult


@dataclass(frozen=True)
class SchemaLoadSummary:
    kind_hashes: dict[str, str]
    """The hash of each node, generic, profile and template kind, keyed by `<section>:<kind>`."""

    migrations: list[tuple[str, str]]
    """The migrations as sorted pairs of migration name and schema path."""

    constraints: list[tuple[str, str]]
    """The constraints as sorted pairs of constraint name and schema path."""


def validate_candidate_schema(*, branch_schema: SchemaBranch, candidate_schema: SchemaBranch) -> SchemaLoadResult:
    """Calculate the diff, the migrations and the constraints of a processed candidate, as a schema load does.

    Raises:
        ValueError: When the candidate removes a kind that another kind still references.
        AssertionError: When the load would be refused, because a case must describe a load that is accepted.

    """
    diff = branch_schema.diff(other=candidate_schema)
    candidate_schema.validate_node_deletions(diff=diff)
    validation = branch_schema.validate_update(other=candidate_schema, diff=diff)
    assert not validation.errors, f"the load is refused: {[error.to_string() for error in validation.errors]}"
    return SchemaLoadResult(schema=candidate_schema, validation=validation)


def build_direct_load_result(
    *, branch_schema: SchemaBranch, schema_root: SchemaRoot, default_branch_schema: SchemaBranch
) -> SchemaLoadResult:
    """Build the result of laying a schema file over the branch schema, with `SchemaBranch` calls only."""
    candidate_schema = branch_schema.duplicate()
    candidate_schema.load_schema(schema=schema_root)
    candidate_schema.process(default_branch_schema=default_branch_schema)
    return validate_candidate_schema(branch_schema=branch_schema, candidate_schema=candidate_schema)


def schema_content_hashes(schema: SchemaBranch) -> dict[str, str]:
    """Return the hash of every kind, calculated again from the content of its schema object.

    A schema object changed in place keeps its stored hash, so only a hash calculated again shows the change.
    """
    return {name: schema.get(name=name, duplicate=False).get_hash() for name in schema.all_names}


def describe_operation(operation: SchemaOperation) -> dict[str, JsonValue]:
    """Return every field of an operation as JSON values, and whether `value` and `previous_value` are set."""
    return {
        **operation.model_dump(mode="json"),
        "has_value": operation.has_value,
        "has_previous_value": operation.has_previous_value,
    }


def summarize_load_result(result: SchemaLoadResult, kinds: Collection[str] | None = None) -> SchemaLoadSummary:
    """Summarize a load result; when `kinds` is given, keep only those kinds and their migrations and constraints."""
    return SchemaLoadSummary(
        kind_hashes={
            f"{section}:{kind}": kind_hash
            for section, hashes in result.schema.to_dict().items()
            for kind, kind_hash in hashes.items()
            if kinds is None or kind in kinds
        },
        migrations=sorted(
            (migration.migration_name, migration.path.get_path())
            for migration in result.validation.migrations
            if kinds is None or migration.path.schema_kind in kinds
        ),
        constraints=sorted(
            (constraint.constraint_name, constraint.path.get_path())
            for constraint in result.validation.constraints
            if kinds is None or constraint.path.schema_kind in kinds
        ),
    )


def assert_same_load_result(
    *, expected: SchemaLoadResult, actual: SchemaLoadResult, kinds: Collection[str] | None = None
) -> None:
    """Compare the kind hashes, the migrations and the constraints of two results, for `kinds` only when it is given.

    Raises:
        AssertionError: When they differ; the message names what differs.

    """
    expected_summary = summarize_load_result(expected, kinds=kinds)
    actual_summary = summarize_load_result(actual, kinds=kinds)

    differing_kinds = sorted(
        kind
        for kind in expected_summary.kind_hashes.keys() | actual_summary.kind_hashes.keys()
        if expected_summary.kind_hashes.get(kind) != actual_summary.kind_hashes.get(kind)
    )
    assert not differing_kinds, f"kinds with a different hash: {differing_kinds}"
    assert actual_summary.migrations == expected_summary.migrations, (
        f"migrations: expected {expected_summary.migrations}, got {actual_summary.migrations}"
    )
    assert actual_summary.constraints == expected_summary.constraints, (
        f"constraints: expected {expected_summary.constraints}, got {actual_summary.constraints}"
    )


@dataclass(frozen=True)
class CombinedLoad:
    """The changes of several cases, loaded together over a base that holds the kinds of every case."""

    base: SchemaBranch
    expected: SchemaLoadResult
    """The result of the direct load of the schema files of every case."""

    actual: SchemaLoadResult
    """The result of applying the operations built from the same schema files."""


CREATE_MIGRATION_RECORDS = "create_migration_records"
SET_MIGRATION_RECORDS_STATUS = "set_migration_records_status"
FAILING_STORE_ERROR = "Unable to connect to the database"


@dataclass(frozen=True)
class MigrationRecordStoreCall:
    method: str
    arguments: dict[str, object]


class FailingMigrationRecordStore:
    """A migration record store that records each call, then raises `error` for the methods named in `failing_methods`."""

    def __init__(
        self,
        failing_methods: frozenset[str] = frozenset({CREATE_MIGRATION_RECORDS, SET_MIGRATION_RECORDS_STATUS}),
        error: Exception | None = None,
    ) -> None:
        self.failing_methods = failing_methods
        self.error = error or DatabaseError(message=FAILING_STORE_ERROR)
        self.calls: list[MigrationRecordStoreCall] = []

    async def create_migration_records(
        self, *, application_id: str, migrations: Sequence[SchemaUpdateMigrationInfo]
    ) -> None:
        self.calls.append(
            MigrationRecordStoreCall(
                method=CREATE_MIGRATION_RECORDS,
                arguments={"application_id": application_id, "migrations": list(migrations)},
            )
        )
        self._raise_if_failing(CREATE_MIGRATION_RECORDS)

    async def set_migration_records_status(
        self,
        *,
        application_id: str,
        positions: Sequence[int],
        status: SchemaChangeMigrationStatus,
        nbr_migrations_executed: int | None,
        errors: Sequence[str],
    ) -> None:
        self.calls.append(
            MigrationRecordStoreCall(
                method=SET_MIGRATION_RECORDS_STATUS,
                arguments={
                    "application_id": application_id,
                    "positions": list(positions),
                    "status": status,
                    "nbr_migrations_executed": nbr_migrations_executed,
                    "errors": list(errors),
                },
            )
        )
        self._raise_if_failing(SET_MIGRATION_RECORDS_STATUS)

    def _raise_if_failing(self, method: str) -> None:
        if method in self.failing_methods:
            raise self.error


CREATE_SCHEMA_CHANGE = "create_schema_change"
MARK_APPLIED = "mark_applied"
MARK_FAILED = "mark_failed"
MARK_FAILED_IF_RUNNING = "mark_failed_if_running"
GET_HIGHEST_APPLIED_VERSION = "get_highest_applied_version"
GET_HIGHEST_APPLIED_VERSION_AT = "get_highest_applied_version_at"


@dataclass(frozen=True)
class SchemaChangeRepositoryCall:
    method: str
    arguments: dict[str, object]


class RecordingSchemaChangeRepository(SchemaChangeRecordStore, AppliedVersionReader):
    """A schema change repository that records each call and returns the records it was given.

    `create_schema_change` returns the items of `created` in turn. The version reads return the
    version given for the branch, or None. `mark_applied` and `mark_failed` return `stored`, and
    `mark_failed_if_running` returns `running`.
    """

    def __init__(
        self,
        created: Sequence[CreatedSchemaChange] = (),
        highest_versions: Mapping[str, AppliedSchemaChangeVersion] | None = None,
        highest_versions_at: Mapping[str, AppliedSchemaChangeVersion] | None = None,
        running: bool = True,
        stored: bool = True,
    ) -> None:
        self._created = list(created)
        self.running = running
        self.stored = stored
        self.highest_versions = dict(highest_versions or {})
        self.highest_versions_at = dict(highest_versions_at or {})
        self.calls: list[SchemaChangeRepositoryCall] = []

    @override
    async def create_schema_change(
        self,
        *,
        branch: str,
        operations: Sequence[SchemaOperation],
        at: Timestamp,
        user_id: str,
        source: SchemaChangeSource,
    ) -> CreatedSchemaChange:
        self._record(
            CREATE_SCHEMA_CHANGE, branch=branch, operations=list(operations), at=at, user_id=user_id, source=source
        )
        return self._created.pop(0)

    @override
    async def mark_applied(
        self,
        *,
        schema_change_id: str,
        application_id: str,
        version: int,
        parent_id: str | None,
        applied_at: Timestamp,
        user_id: str,
    ) -> bool:
        self._record(
            MARK_APPLIED,
            schema_change_id=schema_change_id,
            application_id=application_id,
            version=version,
            parent_id=parent_id,
            applied_at=applied_at,
            user_id=user_id,
        )
        return self.stored

    @override
    async def mark_failed(self, *, schema_change_id: str, application_id: str, error: str, user_id: str) -> bool:
        self._record(
            MARK_FAILED, schema_change_id=schema_change_id, application_id=application_id, error=error, user_id=user_id
        )
        return self.stored

    @override
    async def mark_failed_if_running(
        self, *, schema_change_id: str, application_id: str, error: str, user_id: str
    ) -> bool:
        self._record(
            MARK_FAILED_IF_RUNNING,
            schema_change_id=schema_change_id,
            application_id=application_id,
            error=error,
            user_id=user_id,
        )
        return self.running

    @override
    async def get_highest_applied_version(self, *, branch: str) -> AppliedSchemaChangeVersion | None:
        self._record(GET_HIGHEST_APPLIED_VERSION, branch=branch)
        return self.highest_versions.get(branch)

    @override
    async def get_highest_applied_version_at(self, *, branch: str, at: Timestamp) -> AppliedSchemaChangeVersion | None:
        self._record(GET_HIGHEST_APPLIED_VERSION_AT, branch=branch, at=at)
        return self.highest_versions_at.get(branch)

    def _record(self, method: str, **arguments: object) -> None:
        self.calls.append(SchemaChangeRepositoryCall(method=method, arguments=arguments))


class FailingSchemaChangeRepository(RecordingSchemaChangeRepository):
    """A schema change repository that records each call, and raises a database error from `mark_applied` and `mark_failed`."""

    @override
    async def mark_applied(
        self,
        *,
        schema_change_id: str,
        application_id: str,
        version: int,
        parent_id: str | None,
        applied_at: Timestamp,
        user_id: str,
    ) -> bool:
        await super().mark_applied(
            schema_change_id=schema_change_id,
            application_id=application_id,
            version=version,
            parent_id=parent_id,
            applied_at=applied_at,
            user_id=user_id,
        )
        raise DatabaseError(message=FAILING_STORE_ERROR)

    @override
    async def mark_failed(self, *, schema_change_id: str, application_id: str, error: str, user_id: str) -> bool:
        await super().mark_failed(
            schema_change_id=schema_change_id, application_id=application_id, error=error, user_id=user_id
        )
        raise DatabaseError(message=FAILING_STORE_ERROR)


TRANSIENT_ERROR = "Deadlock detected while trying to acquire locks"


class TransientFailingDatabase(InfrahubDatabase):
    """A database that records the name of each write, and fails the first writes of one query with a transient error.

    The first `nbr_failures` writes named `failing_query_name` raise, and the others return one empty row.
    Skipping the base __init__ leaves it without a driver, so a read fails with AttributeError.
    """

    def __init__(
        self, failing_query_name: str, nbr_failures: int, mode: InfrahubDatabaseMode = InfrahubDatabaseMode.SESSION
    ) -> None:
        self._mode = mode
        self.failing_query_name = failing_query_name
        self.nbr_failures = nbr_failures
        self.write_names: list[str] = []

    @override
    async def execute_query_with_metadata(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        name: str = "undefined",
        context: dict[str, str] | None = None,
        type: QueryType | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[list[Record], dict[str, Any]]:
        self.write_names.append(name)
        if name == self.failing_query_name and self.write_names.count(name) <= self.nbr_failures:
            raise TransientError(TRANSIENT_ERROR)
        return [Record({})], {}


@dataclass(frozen=True)
class ApplierCall:
    target_schema: SchemaBranch
    operations: list[SchemaOperation]
    default_branch_schema: SchemaBranch


class RecordingSchemaChangeApplier(SchemaChangeApplier):
    """An applier that records each call, then applies the operations."""

    def __init__(self) -> None:
        self.calls: list[ApplierCall] = []

    @override
    def apply(
        self,
        *,
        target_schema: SchemaBranch,
        operations: Sequence[SchemaOperation],
        default_branch_schema: SchemaBranch,
    ) -> SchemaBranch:
        self.calls.append(
            ApplierCall(
                target_schema=target_schema, operations=list(operations), default_branch_schema=default_branch_schema
            )
        )
        return super().apply(
            target_schema=target_schema, operations=operations, default_branch_schema=default_branch_schema
        )


class FixedOperationsBuilder(SchemaOperationBuilder):
    """An operation builder that lays the schema file over the branch schema, then returns the given operations."""

    def __init__(self, operations: Sequence[SchemaOperation]) -> None:
        self.operations = list(operations)

    @override
    def build(
        self, *, branch_schema: SchemaBranch, schema_root: SchemaRoot, default_branch_schema: SchemaBranch
    ) -> SchemaOperationBuildResult:
        result = super().build(
            branch_schema=branch_schema, schema_root=schema_root, default_branch_schema=default_branch_schema
        )
        return SchemaOperationBuildResult(operations=self.operations, direct_load_schema=result.direct_load_schema)


RECORDER_START = "start"
RECORDER_COMPLETE = "complete"
RECORDER_FAIL = "fail"
RECORDER_FAIL_IF_RUNNING = "fail_if_running"
EXECUTOR_EXECUTE = "execute"
EXECUTOR_ROLLBACK = "rollback"
RECORDED_SCHEMA_CHANGE_ID = "2f1c9a64-8d3e-4b7a-9c51-0e6d4f3a8b21"
RECORDED_APPLICATION_ID = "7b4e2d19-5a6c-4f08-b3d7-91c2e8a05f63"


@dataclass(frozen=True)
class SchemaApplicationCall:
    method: str
    arguments: dict[str, object]


class RecordingApplicationRecorder(ApplicationRecorder):
    """An application recorder that appends each call to `calls`, which it can share with an executor.

    `start` returns a recording with `RECORDED_SCHEMA_CHANGE_ID` and `RECORDED_APPLICATION_ID`, `fail` returns
    `stored`, and `fail_if_running` returns `running`.
    """

    def __init__(self, calls: list[SchemaApplicationCall], running: bool = True, stored: bool = True) -> None:
        self.calls = calls
        self.running = running
        self.stored = stored

    @override
    async def start(
        self,
        *,
        branch: Branch,
        operations: Sequence[SchemaOperation],
        at: Timestamp,
        user_id: str,
        source: SchemaChangeSource,
    ) -> SchemaChangeRecording:
        self.calls.append(
            SchemaApplicationCall(
                method=RECORDER_START,
                arguments={
                    "branch": branch,
                    "operations": list(operations),
                    "at": at,
                    "user_id": user_id,
                    "source": source,
                },
            )
        )
        return SchemaChangeRecording(
            schema_change_id=RECORDED_SCHEMA_CHANGE_ID, application_id=RECORDED_APPLICATION_ID, at=at
        )

    @override
    async def complete(self, *, recording: SchemaChangeRecording, branch: Branch, user_id: str) -> None:
        self.calls.append(
            SchemaApplicationCall(
                method=RECORDER_COMPLETE, arguments={"recording": recording, "branch": branch, "user_id": user_id}
            )
        )

    @override
    async def fail(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> bool:
        self.calls.append(
            SchemaApplicationCall(
                method=RECORDER_FAIL, arguments={"recording": recording, "error": error, "user_id": user_id}
            )
        )
        return self.stored

    @override
    async def fail_if_running(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> bool:
        self.calls.append(
            SchemaApplicationCall(
                method=RECORDER_FAIL_IF_RUNNING,
                arguments={"recording": recording, "error": error, "user_id": user_id},
            )
        )
        return self.running


class FailingApplicationRecorder(RecordingApplicationRecorder):
    """An application recorder that records each call, and raises a database error from `fail`."""

    @override
    async def fail(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> bool:
        await super().fail(recording=recording, error=error, user_id=user_id)
        raise DatabaseError(message=FAILING_STORE_ERROR)


@dataclass
class FailGate:
    started: asyncio.Event = field(default_factory=asyncio.Event)
    opened: asyncio.Event = field(default_factory=asyncio.Event)
    finished: asyncio.Event = field(default_factory=asyncio.Event)


class GatedFailApplicationRecorder(RecordingApplicationRecorder):
    """An application recorder that records each call; `fail_if_running` sets `gate.started`, waits for `gate.opened`, then records.

    `gate.finished` is set when `fail_if_running` returns or is cancelled.
    """

    def __init__(self, calls: list[SchemaApplicationCall], gate: FailGate) -> None:
        super().__init__(calls=calls)
        self.gate = gate

    @override
    async def fail_if_running(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> bool:
        self.gate.started.set()
        try:
            await self.gate.opened.wait()
            return await super().fail_if_running(recording=recording, error=error, user_id=user_id)
        finally:
            self.gate.finished.set()


class FailingCompleteApplicationRecorder(RecordingApplicationRecorder):
    """An application recorder that records each call, and raises a database error from `complete`."""

    @override
    async def complete(self, *, recording: SchemaChangeRecording, branch: Branch, user_id: str) -> None:
        await super().complete(recording=recording, branch=branch, user_id=user_id)
        raise DatabaseError(message=FAILING_STORE_ERROR)


class RecordingSchemaUpdateExecutor(SchemaUpdateExecutor):
    """A schema update executor that appends each call to `calls`, which it can share, and returns `updated_hash`."""

    def __init__(self, calls: list[SchemaApplicationCall], updated_hash: str) -> None:
        self.calls = calls
        self.updated_hash = updated_hash

    @override
    async def execute(
        self,
        *,
        branch: Branch,
        origin_schema: SchemaBranch,
        rollback_schema: SchemaBranch,
        candidate_schema: SchemaBranch,
        at: Timestamp,
        context: InfrahubContext | None,
        migration_executor: MigrationExecutor,
        diff: SchemaDiff,
        migrations: list[SchemaUpdateMigrationInfo],
        limit: list[str],
        user_id: str,
        application_id: str | None,
        final_step: SchemaUpdateFinalStep | None,
    ) -> str:
        self.calls.append(
            SchemaApplicationCall(
                method=EXECUTOR_EXECUTE,
                arguments={
                    "branch": branch,
                    "origin_schema": origin_schema,
                    "rollback_schema": rollback_schema,
                    "candidate_schema": candidate_schema,
                    "at": at,
                    "context": context,
                    "migration_executor": migration_executor,
                    "diff": diff,
                    "migrations": list(migrations),
                    "limit": list(limit),
                    "user_id": user_id,
                    "application_id": application_id,
                },
            )
        )
        await self._run_final_step(final_step=final_step)
        return self.updated_hash

    async def _run_final_step(self, final_step: SchemaUpdateFinalStep | None) -> None:
        if final_step is None:
            return
        try:
            await final_step()
        except Exception:
            self.calls.append(SchemaApplicationCall(method=EXECUTOR_ROLLBACK, arguments={}))
            raise


class FailingSchemaUpdateExecutor(RecordingSchemaUpdateExecutor):
    """A schema update executor that records each call, then raises `error` instead of running the final step."""

    def __init__(self, calls: list[SchemaApplicationCall], error: BaseException) -> None:
        super().__init__(calls=calls, updated_hash="")
        self.error = error

    @override
    async def execute(
        self,
        *,
        branch: Branch,
        origin_schema: SchemaBranch,
        rollback_schema: SchemaBranch,
        candidate_schema: SchemaBranch,
        at: Timestamp,
        context: InfrahubContext | None,
        migration_executor: MigrationExecutor,
        diff: SchemaDiff,
        migrations: list[SchemaUpdateMigrationInfo],
        limit: list[str],
        user_id: str,
        application_id: str | None,
        final_step: SchemaUpdateFinalStep | None,
    ) -> str:
        await super().execute(
            branch=branch,
            origin_schema=origin_schema,
            rollback_schema=rollback_schema,
            candidate_schema=candidate_schema,
            at=at,
            context=context,
            migration_executor=migration_executor,
            diff=diff,
            migrations=migrations,
            limit=limit,
            user_id=user_id,
            application_id=application_id,
            final_step=None,
        )
        raise self.error


class BlockingSchemaUpdateExecutor(RecordingSchemaUpdateExecutor):
    """A schema update executor that records each call, sets `started`, then waits until it is cancelled."""

    def __init__(self, calls: list[SchemaApplicationCall]) -> None:
        super().__init__(calls=calls, updated_hash="")
        self.started = asyncio.Event()

    @override
    async def execute(
        self,
        *,
        branch: Branch,
        origin_schema: SchemaBranch,
        rollback_schema: SchemaBranch,
        candidate_schema: SchemaBranch,
        at: Timestamp,
        context: InfrahubContext | None,
        migration_executor: MigrationExecutor,
        diff: SchemaDiff,
        migrations: list[SchemaUpdateMigrationInfo],
        limit: list[str],
        user_id: str,
        application_id: str | None,
        final_step: SchemaUpdateFinalStep | None,
    ) -> str:
        await super().execute(
            branch=branch,
            origin_schema=origin_schema,
            rollback_schema=rollback_schema,
            candidate_schema=candidate_schema,
            at=at,
            context=context,
            migration_executor=migration_executor,
            diff=diff,
            migrations=migrations,
            limit=limit,
            user_id=user_id,
            application_id=application_id,
            final_step=None,
        )
        self.started.set()
        await asyncio.Event().wait()
        return self.updated_hash
