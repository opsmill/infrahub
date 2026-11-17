"""A schema migration that runs a second time on the same branch leaves the graph unchanged.

Each case builds one load's migrations by hand, runs them, reads the whole graph, runs them again on the same
branch and compares. The comparison covers every vertex and edge, the global branch included, so a second run
that rewrites an edge, bumps metadata or closes a global edge fails the test.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, HashableModelState, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.migrations.schema.attribute_kind_update import AttributeKindUpdateMigration
from infrahub.core.migrations.schema.attribute_name_update import AttributeNameUpdateMigration
from infrahub.core.migrations.schema.attribute_supports_generated_schema import (
    AttributeSupportsGeneratedSchemaMigration,
)
from infrahub.core.migrations.schema.node_attribute_add import NodeAttributeAddMigration
from infrahub.core.migrations.schema.node_attribute_remove import NodeAttributeRemoveMigration
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.schema.node_relationship_remove import NodeRelationshipRemoveMigration
from infrahub.core.migrations.schema.node_remove import NodeRemoveMigration
from infrahub.core.migrations.schema.node_uniqueness_constraints_update import (
    NodeUniquenessConstraintsUpdateMigration,
)
from infrahub.core.migrations.schema.tasks import get_derived_schema_pairs
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, GenericSchema, SchemaRoot
from infrahub.core.schema.definitions.core.template import core_object_component_template, core_object_template
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.database.validation import GraphValidationError
from tests.component.core.migrations.schema.second_run_helpers import (
    AGNOSTIC_BRANCH_KINDS,
    BRANCH_KINDS,
    FIRST_RUN_USER_ID,
    SECOND_RUN_USER_ID,
    BranchKind,
    assert_graph_unchanged,
    assert_second_run_changes_nothing,
    changed_vertex_uuids,
    get_migration_branch,
    read_graph_state,
    register_candidate,
    run_migrations,
)
from tests.helpers.agnostic_edges import create_gadget, create_widget
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_RETIREMENT_SCHEMA, BEACON_KIND, WIDGET_KIND

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.migrations.shared import DerivedSchemaPair, SchemaMigration
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

type SchemaChange = Callable[[MainSchemaTypes], None]
type CandidateChange = Callable[[SchemaBranch], None]
type MigrationBuilder = Callable[[InfrahubDatabase, Branch], Awaitable[list[SchemaMigration]]]


class MigrationClass(Protocol):
    def __call__(
        self,
        *,
        previous_node_schema: MainSchemaTypes,
        new_node_schema: MainSchemaTypes,
        derived_schemas: list[DerivedSchemaPair],
        schema_path: SchemaPath,
    ) -> SchemaMigration: ...


SEATS_IN_CONSTRAINT = [["name__value", "nbr_seats__value"]]
NAME_ONLY_CONSTRAINT = [["name__value"]]
GENERIC_INHERITING_KINDS = ["TestElectricCar", "TestGazCar"]


# ---------------------------------------------------------------------------
# Data, created on the default branch before the migration branch exists
# ---------------------------------------------------------------------------


@dataclass
class CarData:
    person: Node
    cars: list[Node]
    profile: Node
    template_person: Node
    template_car: Node


def register_car_schema(default_branch: Branch, schema: SchemaRoot) -> SchemaBranch:
    registry.schema.register_schema(
        schema=SchemaRoot(generics=[core_object_template, core_object_component_template]), branch=default_branch.name
    )
    for node in schema.nodes:
        node.generate_template = True
    return registry.schema.register_schema(schema=schema, branch=default_branch.name)


def car_schema_variant(
    schema: SchemaRoot,
    unique: bool = False,
    read_only: bool = False,
    uniqueness_constraints: list[list[str]] | None = None,
) -> SchemaRoot:
    variant = deepcopy(schema)
    car = next(node for node in variant.nodes if node.name == "Car")
    seats = next(attribute for attribute in car.attributes if attribute.name == "nbr_seats")
    seats.unique = unique
    seats.read_only = read_only
    if uniqueness_constraints is not None:
        car.uniqueness_constraints = uniqueness_constraints
    return variant


async def create_car_data(
    db: InfrahubDatabase, default_branch: Branch, seats_on_profile: bool = True, seats_on_template: bool = True
) -> CarData:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)

    cars = []
    for name, nbr_seats, color in (("accord", 5, "#111111"), ("camry", 4, "#222222")):
        car = await Node.init(db=db, schema="TestCar", branch=default_branch)
        await car.new(
            db=db, name=name, nbr_seats=nbr_seats, color=color, is_electric=False, owner=person, driver=person
        )
        await car.save(db=db)
        cars.append(car)

    profile = await Node.init(db=db, schema="ProfileTestCar", branch=default_branch)
    if seats_on_profile:
        await profile.new(db=db, profile_name="car-profile", color="#333333", is_electric=True, nbr_seats=3)
    else:
        await profile.new(db=db, profile_name="car-profile", color="#333333", is_electric=True)
    await profile.save(db=db)

    template_person = await Node.init(db=db, schema="TemplateTestPerson", branch=default_branch)
    await template_person.new(db=db, template_name="person-template")
    await template_person.save(db=db)
    template_car = await Node.init(db=db, schema="TemplateTestCar", branch=default_branch)
    if seats_on_template:
        await template_car.new(
            db=db,
            template_name="car-template",
            color="#444444",
            is_electric=True,
            owner=template_person,
            nbr_seats=2,
        )
    else:
        await template_car.new(
            db=db, template_name="car-template", color="#444444", is_electric=True, owner=template_person
        )
    await template_car.save(db=db)

    return CarData(
        person=person, cars=cars, profile=profile, template_person=template_person, template_car=template_car
    )


@pytest.fixture
async def car_data(db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot) -> CarData:
    register_car_schema(default_branch=default_branch, schema=car_person_schema_unregistered)
    return await create_car_data(db=db, default_branch=default_branch)


@pytest.fixture
async def car_data_unique_seats(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> CarData:
    register_car_schema(
        default_branch=default_branch, schema=car_schema_variant(schema=car_person_schema_unregistered, unique=True)
    )
    return await create_car_data(db=db, default_branch=default_branch, seats_on_profile=False, seats_on_template=False)


@pytest.fixture
async def car_data_read_only_seats(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> CarData:
    register_car_schema(
        default_branch=default_branch, schema=car_schema_variant(schema=car_person_schema_unregistered, read_only=True)
    )
    return await create_car_data(db=db, default_branch=default_branch, seats_on_profile=False, seats_on_template=False)


@pytest.fixture
async def car_data_seats_in_constraint(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> CarData:
    register_car_schema(
        default_branch=default_branch,
        schema=car_schema_variant(schema=car_person_schema_unregistered, uniqueness_constraints=SEATS_IN_CONSTRAINT),
    )
    return await create_car_data(db=db, default_branch=default_branch, seats_on_profile=False)


@dataclass
class AgnosticData:
    gadgets: list[Node]
    widgets: list[Node]
    widget_profile: Node
    beacons: list[Node]


@pytest.fixture
async def agnostic_data(db: InfrahubDatabase, default_branch: Branch) -> AgnosticData:
    schema = deepcopy(AGNOSTIC_RETIREMENT_SCHEMA)
    widget = next(node for node in schema.nodes if node.kind == WIDGET_KIND)
    widget.attributes.append(
        AttributeSchema(name="notes", kind="Text", optional=True, branch=BranchSupportType.AGNOSTIC)
    )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)

    gadgets = [await create_gadget(db=db, branch=default_branch, name=f"gadget-{index}") for index in range(2)]
    widgets = [
        await create_widget(
            db=db, branch=default_branch, name=f"widget-{index}", serial=index, notes=f"note-{index}", gadget=gadget
        )
        for index, gadget in enumerate(gadgets)
    ]
    widget_profile = await Node.init(db=db, schema=f"Profile{WIDGET_KIND}", branch=default_branch)
    await widget_profile.new(db=db, profile_name="widget-profile", serial=10, notes="profile-note")
    await widget_profile.save(db=db)
    beacons = []
    for index in range(2):
        beacon = await Node.init(db=db, schema=BEACON_KIND, branch=default_branch)
        await beacon.new(db=db, name=f"beacon-{index}", serial=index)
        await beacon.save(db=db)
        beacons.append(beacon)
    return AgnosticData(gadgets=gadgets, widgets=widgets, widget_profile=widget_profile, beacons=beacons)


@pytest.fixture
async def generic_profiles(
    db: InfrahubDatabase, default_branch: Branch, car_person_generics_data: dict[str, Node]
) -> list[Node]:
    profiles = []
    for index, kind in enumerate(GENERIC_INHERITING_KINDS):
        profile = await Node.init(db=db, schema=f"Profile{kind}", branch=default_branch)
        await profile.new(db=db, profile_name=f"profile-{kind}", nbr_seats=index + 2, color=f"#00000{index}")
        await profile.save(db=db)
        profiles.append(profile)
    return profiles


# ---------------------------------------------------------------------------
# Schema changes and the migrations a load creates for them
# ---------------------------------------------------------------------------


def attribute_path(kind: str, name: str) -> SchemaPath:
    return SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name=name)


def relationship_path(kind: str, name: str) -> SchemaPath:
    return SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind=kind, field_name=name)


def constraints_path(kind: str) -> SchemaPath:
    return SchemaPath(
        path_type=SchemaPathType.NODE,
        schema_kind=kind,
        field_name="uniqueness_constraints",
        property_name="uniqueness_constraints",
    )


def add_attribute(attribute: AttributeSchema) -> SchemaChange:
    def change(schema: MainSchemaTypes) -> None:
        schema.attributes.append(attribute)

    return change


def remove_attribute(name: str) -> SchemaChange:
    def change(schema: MainSchemaTypes) -> None:
        schema.get_attribute(name=name).state = HashableModelState.ABSENT

    return change


def remove_relationship(name: str) -> SchemaChange:
    def change(schema: MainSchemaTypes) -> None:
        schema.get_relationship(name=name).state = HashableModelState.ABSENT

    return change


def rename_attribute(name: str, new_name: str) -> SchemaChange:
    def change(schema: MainSchemaTypes) -> None:
        schema.get_attribute(name=name).name = new_name

    return change


def change_attribute_kind(name: str, kind: str) -> SchemaChange:
    def change(schema: MainSchemaTypes) -> None:
        schema.get_attribute(name=name).kind = kind

    return change


def change_attribute(
    name: str,
    unique: bool | None = None,
    read_only: bool | None = None,
    optional: bool | None = None,
    uniqueness_constraints: list[list[str]] | None = None,
) -> SchemaChange:
    def change(schema: MainSchemaTypes) -> None:
        attribute = schema.get_attribute(name=name)
        if unique is not None:
            attribute.unique = unique
        if read_only is not None:
            attribute.read_only = read_only
        if optional is not None:
            attribute.optional = optional
        if uniqueness_constraints is not None:
            schema.uniqueness_constraints = uniqueness_constraints

    return change


def set_uniqueness_constraints(constraints: list[list[str]]) -> SchemaChange:
    def change(schema: MainSchemaTypes) -> None:
        schema.uniqueness_constraints = constraints

    return change


def inherit_asset_generic(schema: MainSchemaTypes) -> None:
    assert isinstance(schema, NodeSchema)
    schema.inherit_from = [*schema.inherit_from, "TestAsset"]


def add_asset_generic(candidate: SchemaBranch) -> None:
    candidate.set(
        name="TestAsset",
        schema=GenericSchema(
            name="Asset",
            namespace="Test",
            branch=BranchSupportType.AWARE,
            attributes=[AttributeSchema(name="status", kind="Text", default_value="active", optional=True)],
        ),
    )


def remove_person_relationships(*names: str) -> CandidateChange:
    def change(candidate: SchemaBranch) -> None:
        person = candidate.get_node(name="TestPerson", duplicate=True)
        for name in names:
            person.get_relationship(name=name).state = HashableModelState.ABSENT
        candidate.set(name="TestPerson", schema=person)

    return change


async def change_schema(
    db: InfrahubDatabase,
    branch: Branch,
    kind: str,
    change: SchemaChange,
    attribute_with_id: str | None = None,
    also: CandidateChange | None = None,
) -> tuple[MainSchemaTypes, MainSchemaTypes, list[DerivedSchemaPair]]:
    """Change one kind in a candidate schema and store it on the branch.

    Returns the kind before and after, and its profile and template kinds before and after, as a load passes them.
    """
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get(name=kind, duplicate=True)
    candidate = schema_branch.duplicate()
    changed = candidate.get(name=kind, duplicate=True)
    if attribute_with_id is not None:
        # A schema registered in memory has no IDs, and these migrations need one to match the attribute.
        attribute_id = str(uuid.uuid4())
        previous.get_attribute(name=attribute_with_id).id = attribute_id
        changed.get_attribute(name=attribute_with_id).id = attribute_id
    change(changed)
    candidate.set(name=kind, schema=changed)
    if also is not None:
        also(candidate)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    new = candidate.get(name=kind)
    derived = get_derived_schema_pairs(
        previous_schema_branch=schema_branch,
        new_schema_branch=candidate,
        previous_node_schema=previous,
        new_node_schema=new,
    )
    return previous, new, derived


def one_migration(
    migration_class: MigrationClass,
    schema_path: SchemaPath,
    change: SchemaChange,
    attribute_with_id: str | None = None,
    also: CandidateChange | None = None,
) -> MigrationBuilder:
    async def build(db: InfrahubDatabase, branch: Branch) -> list[SchemaMigration]:
        previous, new, derived = await change_schema(
            db=db,
            branch=branch,
            kind=schema_path.schema_kind,
            change=change,
            attribute_with_id=attribute_with_id,
            also=also,
        )
        return [
            migration_class(
                previous_node_schema=previous, new_node_schema=new, derived_schemas=derived, schema_path=schema_path
            )
        ]

    return build


def node_removal(kind: str, also: CandidateChange | None = None) -> MigrationBuilder:
    async def build(db: InfrahubDatabase, branch: Branch) -> list[SchemaMigration]:
        schema_branch = registry.schema.get_schema_branch(name=branch.name)
        previous = schema_branch.get(name=kind, duplicate=True)
        candidate = schema_branch.duplicate()
        candidate.delete(name=kind)
        if also is not None:
            also(candidate)
        await register_candidate(db=db, branch=branch, candidate=candidate)
        return [
            NodeRemoveMigration(
                previous_node_schema=previous,
                new_node_schema=None,
                schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind=kind),
            )
        ]

    return build


def car_kind_rename(namespace: str, name: str, field_name: str) -> MigrationBuilder:
    """Replace TestCar with a kind of the given namespace and name, and point the person's peers at it."""

    async def build(db: InfrahubDatabase, branch: Branch) -> list[SchemaMigration]:
        schema_branch = registry.schema.get_schema_branch(name=branch.name)
        previous = schema_branch.get(name="TestCar", duplicate=True)
        candidate = schema_branch.duplicate()
        car = candidate.get_node(name="TestCar", duplicate=True)
        candidate.delete(name="TestCar")
        car.namespace = namespace
        car.name = name
        candidate.set(name=car.kind, schema=car)
        person = candidate.get_node(name="TestPerson", duplicate=True)
        for relationship in person.relationships:
            if relationship.peer == "TestCar":
                relationship.peer = car.kind
        candidate.set(name="TestPerson", schema=person)
        await register_candidate(db=db, branch=branch, candidate=candidate)
        new = candidate.get(name=car.kind)
        return [
            NodeKindUpdateMigration(
                previous_node_schema=previous,
                new_node_schema=new,
                derived_schemas=get_derived_schema_pairs(
                    previous_schema_branch=schema_branch,
                    new_schema_branch=candidate,
                    previous_node_schema=previous,
                    new_node_schema=new,
                ),
                schema_path=attribute_path(kind=car.kind, name=field_name),
            )
        ]

    return build


def generic_load(
    migration_class: MigrationClass,
    change: SchemaChange,
    schema_path: Callable[[str], SchemaPath],
    change_inheriting_kinds: bool,
) -> MigrationBuilder:
    """Change the generic TestCar and build the migration a load creates for the generic, then for each kind."""

    async def build(db: InfrahubDatabase, branch: Branch) -> list[SchemaMigration]:
        schema_branch = registry.schema.get_schema_branch(name=branch.name)
        candidate = schema_branch.duplicate()
        kinds = ["TestCar", *GENERIC_INHERITING_KINDS]
        for kind in kinds if change_inheriting_kinds else kinds[:1]:
            changed = candidate.get(name=kind, duplicate=True)
            change(changed)
            candidate.set(name=kind, schema=changed)
        await register_candidate(db=db, branch=branch, candidate=candidate)
        migrations: list[SchemaMigration] = []
        for kind in kinds:
            previous = schema_branch.get(name=kind, duplicate=True)
            new = candidate.get(name=kind)
            derived = get_derived_schema_pairs(
                previous_schema_branch=schema_branch,
                new_schema_branch=candidate,
                previous_node_schema=previous,
                new_node_schema=new,
            )
            migrations.append(
                migration_class(
                    previous_node_schema=previous,
                    new_node_schema=new,
                    derived_schemas=derived,
                    schema_path=schema_path(kind),
                )
            )
        return migrations

    return build


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecondRunCase:
    name: str
    migration_map_key: str
    data: str
    """The fixture that creates the data on the default branch before the migration branch exists."""
    build: MigrationBuilder
    branch_kinds: Sequence[BranchKind] = tuple(BRANCH_KINDS)
    first_run_changes: bool = True
    expected_failures: Mapping[BranchKind, pytest.MarkDecorator] = field(default_factory=dict)


SECOND_RUN_RENAMES_AGAIN = pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="on the default branch, the second run renames the agnostic attribute again and adds new attribute vertices",
)
AGNOSTIC_RENAME_EDGES_ON_BRANCH = pytest.mark.xfail(
    strict=True,
    raises=GraphValidationError,
    reason="the first run creates the renamed agnostic attribute with its edges on the user branch, not -global-",
)
AGNOSTIC_KIND_UPDATE_EDGE_ON_BRANCH = pytest.mark.xfail(
    strict=True,
    raises=GraphValidationError,
    reason="the first run writes the new HAS_VALUE edge of an agnostic attribute on the migration branch, not -global-",
)

GENERIC_CONSTRAINTS_CASE = SecondRunCase(
    name="node_uniqueness_constraints_update_on_generic",
    migration_map_key=ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value,
    data="generic_profiles",
    build=generic_load(
        migration_class=NodeUniquenessConstraintsUpdateMigration,
        change=set_uniqueness_constraints(SEATS_IN_CONSTRAINT),
        schema_path=constraints_path,
        change_inheriting_kinds=False,
    ),
)
GENERIC_KIND_UPDATE_CASE = SecondRunCase(
    name="attribute_kind_update_on_generic",
    migration_map_key="attribute.kind.update",
    data="generic_profiles",
    build=generic_load(
        migration_class=AttributeKindUpdateMigration,
        change=change_attribute_kind(name="color", kind="TextArea"),
        schema_path=lambda kind: attribute_path(kind=kind, name="color"),
        change_inheriting_kinds=True,
    ),
)

SECOND_RUN_CASES: list[SecondRunCase] = [
    # A branch-aware node with profile and template nodes
    SecondRunCase(
        name="node_attribute_add",
        migration_map_key="node.attribute.add",
        data="car_data",
        build=one_migration(
            migration_class=NodeAttributeAddMigration,
            schema_path=attribute_path(kind="TestCar", name="tag"),
            change=add_attribute(AttributeSchema(name="tag", kind="Text", optional=True, default_value="none")),
        ),
    ),
    SecondRunCase(
        name="node_attribute_remove",
        migration_map_key="node.attribute.remove",
        data="car_data",
        build=one_migration(
            migration_class=NodeAttributeRemoveMigration,
            schema_path=attribute_path(kind="TestCar", name="is_electric"),
            change=remove_attribute("is_electric"),
        ),
    ),
    SecondRunCase(
        name="attribute_name_update",
        migration_map_key="attribute.name.update",
        data="car_data",
        build=one_migration(
            migration_class=AttributeNameUpdateMigration,
            schema_path=attribute_path(kind="TestCar", name="electric"),
            change=rename_attribute(name="is_electric", new_name="electric"),
            attribute_with_id="is_electric",
        ),
    ),
    SecondRunCase(
        name="attribute_kind_update",
        migration_map_key="attribute.kind.update",
        data="car_data",
        build=one_migration(
            migration_class=AttributeKindUpdateMigration,
            schema_path=attribute_path(kind="TestCar", name="color"),
            change=change_attribute_kind(name="color", kind="TextArea"),
        ),
    ),
    SecondRunCase(
        name="node_relationship_remove",
        migration_map_key="node.relationship.remove",
        data="car_data",
        build=one_migration(
            migration_class=NodeRelationshipRemoveMigration,
            schema_path=relationship_path(kind="TestCar", name="driver"),
            change=remove_relationship("driver"),
            also=remove_person_relationships("cars_driven"),
        ),
    ),
    SecondRunCase(
        name="node_remove",
        migration_map_key="node.remove",
        data="car_data",
        build=node_removal(kind="TestCar", also=remove_person_relationships("cars", "cars_driven")),
    ),
    SecondRunCase(
        name="node_inherit_from_update",
        migration_map_key="node.inherit_from.update",
        data="car_data",
        build=one_migration(
            migration_class=NodeKindUpdateMigration,
            schema_path=attribute_path(kind="TestCar", name="inherit_from"),
            change=inherit_asset_generic,
            also=add_asset_generic,
        ),
    ),
    SecondRunCase(
        name="node_name_update",
        migration_map_key="node.name.update",
        data="car_data",
        build=car_kind_rename(namespace="Test", name="Auto", field_name="name"),
    ),
    SecondRunCase(
        name="node_namespace_update",
        migration_map_key="node.namespace.update",
        data="car_data",
        build=car_kind_rename(namespace="Test2", name="Car", field_name="namespace"),
    ),
    SecondRunCase(
        name="attribute_unique_update_on",
        migration_map_key="attribute.unique.update",
        data="car_data",
        build=one_migration(
            migration_class=AttributeSupportsGeneratedSchemaMigration,
            schema_path=attribute_path(kind="TestCar", name="nbr_seats"),
            change=change_attribute(name="nbr_seats", unique=True),
            attribute_with_id="nbr_seats",
        ),
    ),
    SecondRunCase(
        name="attribute_unique_update_off",
        migration_map_key="attribute.unique.update",
        data="car_data_unique_seats",
        build=one_migration(
            migration_class=AttributeSupportsGeneratedSchemaMigration,
            schema_path=attribute_path(kind="TestCar", name="nbr_seats"),
            # Processing a unique attribute adds it to the uniqueness constraints, which turning unique off leaves.
            change=change_attribute(name="nbr_seats", unique=False, uniqueness_constraints=NAME_ONLY_CONSTRAINT),
            attribute_with_id="nbr_seats",
        ),
    ),
    SecondRunCase(
        name="attribute_read_only_update_on",
        migration_map_key="attribute.read_only.update",
        data="car_data",
        build=one_migration(
            migration_class=AttributeSupportsGeneratedSchemaMigration,
            schema_path=attribute_path(kind="TestCar", name="nbr_seats"),
            change=change_attribute(name="nbr_seats", read_only=True),
            attribute_with_id="nbr_seats",
        ),
    ),
    SecondRunCase(
        name="attribute_read_only_update_off",
        migration_map_key="attribute.read_only.update",
        data="car_data_read_only_seats",
        build=one_migration(
            migration_class=AttributeSupportsGeneratedSchemaMigration,
            schema_path=attribute_path(kind="TestCar", name="nbr_seats"),
            change=change_attribute(name="nbr_seats", read_only=False),
            attribute_with_id="nbr_seats",
        ),
    ),
    SecondRunCase(
        name="attribute_optional_update",
        migration_map_key="attribute.optional.update",
        data="car_data",
        build=one_migration(
            migration_class=AttributeSupportsGeneratedSchemaMigration,
            schema_path=attribute_path(kind="TestCar", name="nbr_seats"),
            change=change_attribute(name="nbr_seats", optional=False),
            attribute_with_id="nbr_seats",
        ),
        # Profile and template support depends on read_only and unique, not on optional.
        first_run_changes=False,
    ),
    SecondRunCase(
        name="node_uniqueness_constraints_update_add",
        migration_map_key=ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value,
        data="car_data",
        build=one_migration(
            migration_class=NodeUniquenessConstraintsUpdateMigration,
            schema_path=constraints_path("TestCar"),
            change=set_uniqueness_constraints(SEATS_IN_CONSTRAINT),
        ),
    ),
    SecondRunCase(
        name="node_uniqueness_constraints_update_remove",
        migration_map_key=ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value,
        data="car_data_seats_in_constraint",
        build=one_migration(
            migration_class=NodeUniquenessConstraintsUpdateMigration,
            schema_path=constraints_path("TestCar"),
            change=set_uniqueness_constraints(NAME_ONLY_CONSTRAINT),
        ),
    ),
    # Branch-agnostic fields on a branch-aware node, and an attribute of a branch-agnostic kind
    SecondRunCase(
        name="agnostic_attribute_add",
        migration_map_key="node.attribute.add",
        data="agnostic_data",
        build=one_migration(
            migration_class=NodeAttributeAddMigration,
            schema_path=attribute_path(kind=WIDGET_KIND, name="tag"),
            change=add_attribute(
                AttributeSchema(
                    name="tag", kind="Text", optional=True, default_value="none", branch=BranchSupportType.AGNOSTIC
                )
            ),
        ),
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
    ),
    SecondRunCase(
        name="agnostic_attribute_remove",
        migration_map_key="node.attribute.remove",
        data="agnostic_data",
        build=one_migration(
            migration_class=NodeAttributeRemoveMigration,
            schema_path=attribute_path(kind=WIDGET_KIND, name="serial"),
            change=remove_attribute("serial"),
        ),
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
    ),
    SecondRunCase(
        name="agnostic_attribute_name_update",
        migration_map_key="attribute.name.update",
        data="agnostic_data",
        build=one_migration(
            migration_class=AttributeNameUpdateMigration,
            schema_path=attribute_path(kind=WIDGET_KIND, name="serial_number"),
            change=rename_attribute(name="serial", new_name="serial_number"),
            attribute_with_id="serial",
        ),
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
        expected_failures={
            BranchKind.DEFAULT: SECOND_RUN_RENAMES_AGAIN,
            BranchKind.USER: AGNOSTIC_RENAME_EDGES_ON_BRANCH,
            BranchKind.DEFAULT_WITH_READER_BRANCH: SECOND_RUN_RENAMES_AGAIN,
        },
    ),
    SecondRunCase(
        name="agnostic_attribute_kind_update",
        migration_map_key="attribute.kind.update",
        data="agnostic_data",
        build=one_migration(
            migration_class=AttributeKindUpdateMigration,
            schema_path=attribute_path(kind=WIDGET_KIND, name="notes"),
            change=change_attribute_kind(name="notes", kind="TextArea"),
        ),
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
        expected_failures=dict.fromkeys(AGNOSTIC_BRANCH_KINDS, AGNOSTIC_KIND_UPDATE_EDGE_ON_BRANCH),
    ),
    SecondRunCase(
        name="agnostic_attribute_unique_update_on",
        migration_map_key="attribute.unique.update",
        data="agnostic_data",
        build=one_migration(
            migration_class=AttributeSupportsGeneratedSchemaMigration,
            schema_path=attribute_path(kind=WIDGET_KIND, name="notes"),
            change=change_attribute(name="notes", unique=True),
            attribute_with_id="notes",
        ),
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
    ),
    SecondRunCase(
        name="agnostic_relationship_remove",
        migration_map_key="node.relationship.remove",
        data="agnostic_data",
        build=one_migration(
            migration_class=NodeRelationshipRemoveMigration,
            schema_path=relationship_path(kind=WIDGET_KIND, name="gadget"),
            change=remove_relationship("gadget"),
        ),
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
    ),
    SecondRunCase(
        name="node_remove_with_agnostic_fields",
        migration_map_key="node.remove",
        data="agnostic_data",
        build=node_removal(kind=WIDGET_KIND),
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
    ),
    SecondRunCase(
        name="agnostic_kind_attribute_remove",
        migration_map_key="node.attribute.remove",
        data="agnostic_data",
        build=one_migration(
            migration_class=NodeAttributeRemoveMigration,
            schema_path=attribute_path(kind=BEACON_KIND, name="serial"),
            change=remove_attribute("serial"),
        ),
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
    ),
    # A generic, whose migrations also reach the nodes of the kinds that inherit it
    SecondRunCase(
        name="attribute_unique_update_on_generic",
        migration_map_key="attribute.unique.update",
        data="generic_profiles",
        build=one_migration(
            migration_class=AttributeSupportsGeneratedSchemaMigration,
            schema_path=attribute_path(kind="TestCar", name="nbr_seats"),
            change=change_attribute(name="nbr_seats", unique=True),
            attribute_with_id="nbr_seats",
        ),
    ),
    GENERIC_CONSTRAINTS_CASE,
    GENERIC_KIND_UPDATE_CASE,
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def case_data(request: pytest.FixtureRequest, case: SecondRunCase) -> None:
    """Create the case's data through its fixture during setup, before the migration branch exists."""
    request.getfixturevalue(case.data)


def test_every_migration_class_has_a_second_run_case() -> None:
    covered = {case.migration_map_key for case in SECOND_RUN_CASES}
    assert covered == {key for key, migration_class in MIGRATION_MAP.items() if migration_class is not None}


@pytest.mark.parametrize(
    ("case", "branch_kind"),
    [
        pytest.param(
            case, branch_kind, id=f"{case.name}-{branch_kind.value}", marks=case.expected_failures.get(branch_kind, ())
        )
        for case in SECOND_RUN_CASES
        for branch_kind in case.branch_kinds
    ],
)
async def test_second_run_changes_nothing(
    db: InfrahubDatabase, default_branch: Branch, case_data: None, case: SecondRunCase, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    migrations = await case.build(db, branch)
    await assert_second_run_changes_nothing(
        db=db, branch=branch, migrations=migrations, first_run_changes=case.first_run_changes
    )


@pytest.mark.parametrize("case", [GENERIC_CONSTRAINTS_CASE, GENERIC_KIND_UPDATE_CASE], ids=lambda case: case.name)
@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_kind_migrations_skip_nodes_changed_by_the_generic_migration(
    db: InfrahubDatabase, default_branch: Branch, case_data: None, case: SecondRunCase, branch_kind: BranchKind
) -> None:
    """The inheriting kinds' migrations of one load change none of the generic migration's nodes.

    They may still change nodes the generic's migration cannot reach, such as their own profiles.
    """
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    generic_migration, *kind_migrations = await case.build(db, branch)

    before = await read_graph_state(db=db)
    await run_migrations(
        db=db, branch=branch, migrations=[generic_migration], at=Timestamp(), user_id=FIRST_RUN_USER_ID
    )
    after_generic = await read_graph_state(db=db)
    changed_by_generic = changed_vertex_uuids(before=before, after=after_generic)
    assert changed_by_generic, "the generic's migration changed nothing"
    await run_migrations(db=db, branch=branch, migrations=kind_migrations, at=Timestamp(), user_id=SECOND_RUN_USER_ID)
    changed_by_kinds = changed_vertex_uuids(before=after_generic, after=await read_graph_state(db=db))
    assert changed_by_generic & changed_by_kinds == set()


async def test_graph_state_detects_duplicate_vertex(db: InfrahubDatabase, car_data: CarData) -> None:
    before = await read_graph_state(db=db)
    await db.execute_query(query="CREATE (:AttributeValue {value: 'duplicate', is_default: false})")
    await db.execute_query(query="CREATE (:AttributeValue {value: 'duplicate', is_default: false})")
    with pytest.raises(AssertionError, match=r"vertex_count"):
        assert_graph_unchanged(before=before, after=await read_graph_state(db=db))


async def test_graph_state_detects_changed_property(db: InfrahubDatabase, car_data: CarData) -> None:
    before = await read_graph_state(db=db)
    await db.execute_query(
        query="MATCH (n:Node {uuid: $uuid}) SET n.updated_by = 'another-user'",
        params={"uuid": car_data.cars[0].id},
    )
    with pytest.raises(AssertionError, match=r"another-user"):
        assert_graph_unchanged(before=before, after=await read_graph_state(db=db))


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_changed_vertex_uuids_names_the_changed_node(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    changed_car, other_car = car_data.cars
    before = await read_graph_state(db=db)
    car = await NodeManager.get_one(db=db, id=changed_car.id, branch=branch)
    assert car is not None
    seats = car.get_attribute(name="nbr_seats")
    seats.value = 9
    await car.save(db=db)
    changed = changed_vertex_uuids(before=before, after=await read_graph_state(db=db))
    assert seats.id in changed
    assert {other_car.id, other_car.get_attribute(name="nbr_seats").id} & changed == set()
