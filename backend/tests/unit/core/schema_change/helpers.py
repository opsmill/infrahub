from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.schema import (
    AttributeSchema,
    DropdownChoice,
    GenericSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
)
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.operations_check import SchemaOperationsCheck
from infrahub.exceptions import DatabaseError
from tests.constants import TestKind
from tests.helpers.schema import DEVICE, INTERFACE, INTERFACE_HOLDER, PHYSICAL_INTERFACE, SFP, TAG, VIRTUAL_INTERFACE

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from pydantic import JsonValue

    from infrahub.core.models import SchemaUpdateMigrationInfo, SchemaUpdateValidationResult
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema_change.constants import SchemaChangeMigrationStatus
    from infrahub.core.schema_change.operations import SchemaOperation

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


_BASE_DEFINITIONS: dict[str, Callable[[], NodeSchema | GenericSchema]] = {
    TestKind.INTERFACE: INTERFACE.duplicate,
    TestKind.INTERFACE_HOLDER: INTERFACE_HOLDER.duplicate,
    TestKind.DEVICE: _device_definition,
    TestKind.PHYSICAL_INTERFACE: PHYSICAL_INTERFACE.duplicate,
    TestKind.VIRTUAL_INTERFACE: VIRTUAL_INTERFACE.duplicate,
    TestKind.SFP: SFP.duplicate,
    TestKind.TAG: _tag_definition,
}


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


def summarize_load_result(result: SchemaLoadResult) -> SchemaLoadSummary:
    return SchemaLoadSummary(
        kind_hashes={
            f"{section}:{kind}": kind_hash
            for section, hashes in result.schema.to_dict().items()
            for kind, kind_hash in hashes.items()
        },
        migrations=sorted(
            (migration.migration_name, migration.path.get_path()) for migration in result.validation.migrations
        ),
        constraints=sorted(
            (constraint.constraint_name, constraint.path.get_path()) for constraint in result.validation.constraints
        ),
    )


def assert_same_load_result(*, expected: SchemaLoadResult, actual: SchemaLoadResult) -> None:
    """Compare the kind hashes, the migrations and the constraints of two results.

    Raises:
        AssertionError: When they differ; the message names what differs.

    """
    expected_summary = summarize_load_result(expected)
    actual_summary = summarize_load_result(actual)

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


CREATE_MIGRATION_RECORDS = "create_migration_records"
SET_MIGRATION_RECORDS_STATUS = "set_migration_records_status"
FAILING_STORE_ERROR = "Unable to connect to the database"


@dataclass(frozen=True)
class MigrationRecordStoreCall:
    method: str
    arguments: dict[str, object]


class FailingMigrationRecordStore:
    """A migration record store that records each call, then raises for the methods named in `failing_methods`.

    A method that does not fail returns the record ID `record-<position>` for each migration.
    """

    def __init__(
        self, failing_methods: frozenset[str] = frozenset({CREATE_MIGRATION_RECORDS, SET_MIGRATION_RECORDS_STATUS})
    ) -> None:
        self.failing_methods = failing_methods
        self.calls: list[MigrationRecordStoreCall] = []

    async def create_migration_records(
        self, *, application_id: str, migrations: Sequence[SchemaUpdateMigrationInfo]
    ) -> dict[int, str]:
        self.calls.append(
            MigrationRecordStoreCall(
                method=CREATE_MIGRATION_RECORDS,
                arguments={"application_id": application_id, "migrations": list(migrations)},
            )
        )
        self._raise_if_failing(CREATE_MIGRATION_RECORDS)
        return {position: f"record-{position}" for position in range(len(migrations))}

    async def set_migration_records_status(
        self,
        *,
        record_ids: Sequence[str],
        status: SchemaChangeMigrationStatus,
        nbr_migrations_executed: int | None,
        errors: Sequence[str],
    ) -> None:
        self.calls.append(
            MigrationRecordStoreCall(
                method=SET_MIGRATION_RECORDS_STATUS,
                arguments={
                    "record_ids": list(record_ids),
                    "status": status,
                    "nbr_migrations_executed": nbr_migrations_executed,
                    "errors": list(errors),
                },
            )
        )
        self._raise_if_failing(SET_MIGRATION_RECORDS_STATUS)

    def _raise_if_failing(self, method: str) -> None:
        if method in self.failing_methods:
            raise DatabaseError(message=FAILING_STORE_ERROR)


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


@dataclass(frozen=True)
class OperationsCheckCall:
    branch_schema: SchemaBranch
    operations: list[SchemaOperation]
    default_branch_schema: SchemaBranch
    direct_load_schema: SchemaBranch


class RecordingSchemaOperationsCheck(SchemaOperationsCheck):
    """An operations check that records each call and checks nothing."""

    def __init__(self) -> None:
        self.calls: list[OperationsCheckCall] = []

    @override
    def check(
        self,
        *,
        branch_schema: SchemaBranch,
        operations: Sequence[SchemaOperation],
        default_branch_schema: SchemaBranch,
        direct_load_schema: SchemaBranch,
    ) -> None:
        self.calls.append(
            OperationsCheckCall(
                branch_schema=branch_schema,
                operations=list(operations),
                default_branch_schema=default_branch_schema,
                direct_load_schema=direct_load_schema,
            )
        )
