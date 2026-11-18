"""A schema migration that runs a second time on the same branch leaves the graph unchanged.

Each case changes the schema the way one schema load does, builds the migrations that load creates, runs them,
reads the whole graph, runs them again on the same branch and compares. The comparison covers every vertex and
edge, the global branch included, so a second run that rewrites an edge, bumps metadata or closes a global edge
fails the test.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
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
    SecondRunChangedGraphError,
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


class MigrationClass(Protocol):
    def __call__(
        self,
        *,
        previous_node_schema: MainSchemaTypes,
        new_node_schema: MainSchemaTypes | None,
        derived_schemas: list[DerivedSchemaPair],
        schema_path: SchemaPath,
    ) -> SchemaMigration: ...


SEATS_IN_CONSTRAINT = [["name__value", "nbr_seats__value"]]
NAME_ONLY_CONSTRAINT = [["name__value"]]
GENERIC_INHERITING_KINDS = ["TestElectricCar", "TestGazCar"]
CONSTRAINTS_KEY = ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value


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


def register_car_schema(default_branch: Branch, schema: SchemaRoot) -> None:
    registry.schema.register_schema(
        schema=SchemaRoot(generics=[core_object_template, core_object_component_template]), branch=default_branch.name
    )
    for node in schema.nodes:
        node.generate_template = True
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


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


@pytest.fixture
async def agnostic_data(db: InfrahubDatabase, default_branch: Branch) -> None:
    schema = deepcopy(AGNOSTIC_RETIREMENT_SCHEMA)
    widget = next(node for node in schema.nodes if node.kind == WIDGET_KIND)
    widget.attributes.append(
        AttributeSchema(name="notes", kind="Text", optional=True, branch=BranchSupportType.AGNOSTIC)
    )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)

    gadgets = [await create_gadget(db=db, branch=default_branch, name=f"gadget-{index}") for index in range(2)]
    for index, gadget in enumerate(gadgets):
        await create_widget(
            db=db, branch=default_branch, name=f"widget-{index}", serial=index, notes=f"note-{index}", gadget=gadget
        )
    widget_profile = await Node.init(db=db, schema=f"Profile{WIDGET_KIND}", branch=default_branch)
    await widget_profile.new(db=db, profile_name="widget-profile", serial=10, notes="profile-note")
    await widget_profile.save(db=db)
    for index in range(2):
        beacon = await Node.init(db=db, schema=BEACON_KIND, branch=default_branch)
        await beacon.new(db=db, name=f"beacon-{index}", serial=index)
        await beacon.save(db=db)


@pytest.fixture
async def generic_data(db: InfrahubDatabase, default_branch: Branch, car_person_generics_data: dict[str, Node]) -> None:
    for index, kind in enumerate(GENERIC_INHERITING_KINDS):
        profile = await Node.init(db=db, schema=f"Profile{kind}", branch=default_branch)
        await profile.new(db=db, profile_name=f"profile-{kind}", nbr_seats=index + 2, color=f"#00000{index}")
        await profile.save(db=db)


# ---------------------------------------------------------------------------
# Schema edits and the migrations a load creates for them
# ---------------------------------------------------------------------------


def attribute_path(kind: str, name: str, property_name: str | None = None) -> SchemaPath:
    return SchemaPath(
        path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name=name, property_name=property_name
    )


def relationship_path(kind: str, name: str) -> SchemaPath:
    return SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind=kind, field_name=name)


def node_path(kind: str, name: str | None = None) -> SchemaPath:
    return SchemaPath(path_type=SchemaPathType.NODE, schema_kind=kind, field_name=name, property_name=name)


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


def change_attribute(
    name: str,
    kind: str | None = None,
    unique: bool | None = None,
    read_only: bool | None = None,
    optional: bool | None = None,
    inherited: bool | None = None,
) -> SchemaChange:
    def change(schema: MainSchemaTypes) -> None:
        attribute = schema.get_attribute(name=name)
        if kind is not None:
            attribute.kind = kind
        if unique is not None:
            attribute.unique = unique
        if read_only is not None:
            attribute.read_only = read_only
        if optional is not None:
            attribute.optional = optional
        if inherited is not None:
            attribute.inherited = inherited

    return change


def set_uniqueness_constraints(constraints: list[list[str]]) -> SchemaChange:
    def change(schema: MainSchemaTypes) -> None:
        schema.uniqueness_constraints = constraints

    return change


def inherit_asset_generic(schema: MainSchemaTypes) -> None:
    assert isinstance(schema, NodeSchema)
    schema.inherit_from = [*schema.inherit_from, "TestAsset"]


def edit_kind(kind: str, *changes: SchemaChange) -> CandidateChange:
    def edit(candidate: SchemaBranch) -> None:
        schema = candidate.get(name=kind, duplicate=True)
        for change in changes:
            change(schema)
        candidate.set(name=kind, schema=schema)

    return edit


def edit_kinds(kinds: Sequence[str], *changes: SchemaChange) -> CandidateChange:
    def edit(candidate: SchemaBranch) -> None:
        for kind in kinds:
            edit_kind(kind, *changes)(candidate)

    return edit


def combine(*edits: CandidateChange) -> CandidateChange:
    def edit(candidate: SchemaBranch) -> None:
        for each in edits:
            each(candidate)

    return edit


def delete_kind(kind: str) -> CandidateChange:
    def edit(candidate: SchemaBranch) -> None:
        candidate.delete(name=kind)

    return edit


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


def rename_car_kind(namespace: str, name: str) -> CandidateChange:
    """Replace TestCar with a kind of the given namespace and name, and point the person's peers at it."""

    def edit(candidate: SchemaBranch) -> None:
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

    return edit


@dataclass(frozen=True)
class PlannedMigration:
    migration_map_key: str
    migration_class: MigrationClass
    schema_path: SchemaPath
    previous_kind: str | None = None
    """The kind before the load, when the load renames it; defaults to the path's kind."""
    removes_kind: bool = False


@dataclass(frozen=True)
class SecondRunCase:
    name: str
    data: str
    """The fixture that creates the data on the default branch before the migration branch exists."""
    edit: CandidateChange
    migrations: Sequence[PlannedMigration]
    attribute_ids: Sequence[tuple[str, str]] = ()
    """(kind, attribute) pairs that get one shared ID before and after the load, as a stored schema has."""
    branch_kinds: Sequence[BranchKind] = tuple(BRANCH_KINDS)
    first_run_changes: bool = True
    expected_failures: Mapping[BranchKind, pytest.MarkDecorator] = field(default_factory=dict)


async def build_migrations(db: InfrahubDatabase, branch: Branch, case: SecondRunCase) -> list[SchemaMigration]:
    """Apply the case's schema edit on the branch and build the migrations with what a load passes them."""
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    candidate = schema_branch.duplicate()
    previous_schemas = {
        kind: schema_branch.get(name=kind, duplicate=True)
        for kind in {planned.previous_kind or planned.schema_path.schema_kind for planned in case.migrations}
    }
    for kind, attribute_name in case.attribute_ids:
        attribute_id = str(uuid.uuid4())
        previous_schemas[kind].get_attribute(name=attribute_name).id = attribute_id
        edit_kind(kind, change_attribute_id(name=attribute_name, attribute_id=attribute_id))(candidate)
    case.edit(candidate)
    await register_candidate(db=db, branch=branch, candidate=candidate)

    migrations = []
    for planned in case.migrations:
        previous = previous_schemas[planned.previous_kind or planned.schema_path.schema_kind]
        new = None if planned.removes_kind else candidate.get(name=planned.schema_path.schema_kind)
        migrations.append(
            planned.migration_class(
                previous_node_schema=previous,
                new_node_schema=new,
                derived_schemas=get_derived_schema_pairs(
                    previous_schema_branch=schema_branch,
                    new_schema_branch=candidate,
                    previous_node_schema=previous,
                    new_node_schema=new,
                ),
                schema_path=planned.schema_path,
            )
        )
    return migrations


def change_attribute_id(name: str, attribute_id: str) -> SchemaChange:
    def change(schema: MainSchemaTypes) -> None:
        schema.get_attribute(name=name).id = attribute_id

    return change


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


SECOND_RUN_RENAMES_AGAIN = pytest.mark.xfail(
    strict=True,
    raises=SecondRunChangedGraphError,
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


def supports_generated_schema(key: str, kind: str, name: str, property_name: str) -> PlannedMigration:
    return PlannedMigration(
        migration_map_key=key,
        migration_class=AttributeSupportsGeneratedSchemaMigration,
        schema_path=attribute_path(kind=kind, name=name, property_name=property_name),
    )


def constraints_update(kind: str) -> PlannedMigration:
    return PlannedMigration(
        migration_map_key=CONSTRAINTS_KEY,
        migration_class=NodeUniquenessConstraintsUpdateMigration,
        schema_path=node_path(kind=kind, name="uniqueness_constraints"),
    )


def kind_update(kind: str, name: str) -> PlannedMigration:
    return PlannedMigration(
        migration_map_key="attribute.kind.update",
        migration_class=AttributeKindUpdateMigration,
        schema_path=attribute_path(kind=kind, name=name, property_name="kind"),
    )


def car_kind_rename_case(name: str, key: str, namespace: str, kind_name: str, field_name: str) -> SecondRunCase:
    return SecondRunCase(
        name=name,
        data="car_data",
        edit=rename_car_kind(namespace=namespace, name=kind_name),
        migrations=[
            PlannedMigration(
                migration_map_key=key,
                migration_class=NodeKindUpdateMigration,
                schema_path=node_path(kind=f"{namespace}{kind_name}", name=field_name),
                previous_kind="TestCar",
            )
        ],
    )


# When the kinds declare the attribute themselves, the load also creates a migration for each kind.
GENERIC_KIND_UPDATE_DECLARED_CASE = SecondRunCase(
    name="attribute_kind_update_on_generic_declared_by_kinds",
    data="generic_data",
    edit=combine(
        edit_kind("TestCar", change_attribute(name="color", kind="TextArea")),
        edit_kinds(GENERIC_INHERITING_KINDS, change_attribute(name="color", kind="TextArea", inherited=False)),
    ),
    migrations=[kind_update(kind=kind, name="color") for kind in ["TestCar", *GENERIC_INHERITING_KINDS]],
)
# Turning on unique creates both migrations on the generic, and both remove the attribute from the same profiles.
GENERIC_UNIQUE_CASE = SecondRunCase(
    name="attribute_unique_update_on_generic",
    data="generic_data",
    edit=edit_kind("TestCar", change_attribute(name="nbr_seats", unique=True)),
    migrations=[
        supports_generated_schema(
            key="attribute.unique.update", kind="TestCar", name="nbr_seats", property_name="unique"
        ),
        constraints_update(kind="TestCar"),
    ],
    attribute_ids=[("TestCar", "nbr_seats")],
)

SECOND_RUN_CASES: list[SecondRunCase] = [
    # A branch-aware node with profile and template nodes
    SecondRunCase(
        name="node_attribute_add",
        data="car_data",
        edit=edit_kind(
            "TestCar", add_attribute(AttributeSchema(name="tag", kind="Text", optional=True, default_value="none"))
        ),
        migrations=[
            PlannedMigration(
                "node.attribute.add", NodeAttributeAddMigration, attribute_path(kind="TestCar", name="tag")
            )
        ],
    ),
    SecondRunCase(
        name="node_attribute_remove",
        data="car_data",
        edit=edit_kind("TestCar", remove_attribute("is_electric")),
        migrations=[
            PlannedMigration(
                "node.attribute.remove",
                NodeAttributeRemoveMigration,
                attribute_path(kind="TestCar", name="is_electric"),
            )
        ],
    ),
    SecondRunCase(
        name="attribute_name_update",
        data="car_data",
        edit=edit_kind("TestCar", rename_attribute(name="is_electric", new_name="electric")),
        migrations=[
            PlannedMigration(
                "attribute.name.update",
                AttributeNameUpdateMigration,
                attribute_path(kind="TestCar", name="electric", property_name="name"),
            )
        ],
        attribute_ids=[("TestCar", "is_electric")],
    ),
    SecondRunCase(
        name="attribute_kind_update",
        data="car_data",
        edit=edit_kind("TestCar", change_attribute(name="color", kind="TextArea")),
        migrations=[kind_update(kind="TestCar", name="color")],
    ),
    SecondRunCase(
        name="node_relationship_remove",
        data="car_data",
        edit=combine(
            edit_kind("TestCar", remove_relationship("driver")),
            edit_kind("TestPerson", remove_relationship("cars_driven")),
        ),
        migrations=[
            PlannedMigration(
                "node.relationship.remove",
                NodeRelationshipRemoveMigration,
                relationship_path(kind="TestCar", name="driver"),
            )
        ],
    ),
    SecondRunCase(
        name="node_remove",
        data="car_data",
        edit=combine(
            delete_kind("TestCar"),
            edit_kind("TestPerson", remove_relationship("cars"), remove_relationship("cars_driven")),
        ),
        migrations=[PlannedMigration("node.remove", NodeRemoveMigration, node_path(kind="TestCar"), removes_kind=True)],
    ),
    SecondRunCase(
        name="node_inherit_from_update",
        data="car_data",
        edit=combine(add_asset_generic, edit_kind("TestCar", inherit_asset_generic)),
        migrations=[PlannedMigration("node.inherit_from.update", NodeKindUpdateMigration, node_path(kind="TestCar"))],
    ),
    car_kind_rename_case(
        name="node_name_update", key="node.name.update", namespace="Test", kind_name="Auto", field_name="name"
    ),
    car_kind_rename_case(
        name="node_namespace_update",
        key="node.namespace.update",
        namespace="Test2",
        kind_name="Car",
        field_name="namespace",
    ),
    SecondRunCase(
        name="attribute_unique_update_on",
        data="car_data",
        edit=edit_kind("TestCar", change_attribute(name="nbr_seats", unique=True)),
        migrations=[
            supports_generated_schema(
                key="attribute.unique.update", kind="TestCar", name="nbr_seats", property_name="unique"
            )
        ],
        attribute_ids=[("TestCar", "nbr_seats")],
    ),
    SecondRunCase(
        name="attribute_unique_update_off",
        data="car_data_unique_seats",
        # Processing a unique attribute adds it to the uniqueness constraints, which turning unique off leaves.
        edit=edit_kind(
            "TestCar",
            change_attribute(name="nbr_seats", unique=False),
            set_uniqueness_constraints(NAME_ONLY_CONSTRAINT),
        ),
        migrations=[
            supports_generated_schema(
                key="attribute.unique.update", kind="TestCar", name="nbr_seats", property_name="unique"
            )
        ],
        attribute_ids=[("TestCar", "nbr_seats")],
    ),
    SecondRunCase(
        name="attribute_read_only_update_on",
        data="car_data",
        edit=edit_kind("TestCar", change_attribute(name="nbr_seats", read_only=True)),
        migrations=[
            supports_generated_schema(
                key="attribute.read_only.update", kind="TestCar", name="nbr_seats", property_name="read_only"
            )
        ],
        attribute_ids=[("TestCar", "nbr_seats")],
    ),
    SecondRunCase(
        name="attribute_read_only_update_off",
        data="car_data_read_only_seats",
        edit=edit_kind("TestCar", change_attribute(name="nbr_seats", read_only=False)),
        migrations=[
            supports_generated_schema(
                key="attribute.read_only.update", kind="TestCar", name="nbr_seats", property_name="read_only"
            )
        ],
        attribute_ids=[("TestCar", "nbr_seats")],
    ),
    SecondRunCase(
        name="attribute_optional_update",
        data="car_data",
        edit=edit_kind("TestCar", change_attribute(name="nbr_seats", optional=False)),
        migrations=[
            supports_generated_schema(
                key="attribute.optional.update", kind="TestCar", name="nbr_seats", property_name="optional"
            )
        ],
        attribute_ids=[("TestCar", "nbr_seats")],
        # Profile and template support depends on read_only and unique, not on optional.
        first_run_changes=False,
    ),
    SecondRunCase(
        name="node_uniqueness_constraints_update_add",
        data="car_data",
        edit=edit_kind("TestCar", set_uniqueness_constraints(SEATS_IN_CONSTRAINT)),
        migrations=[constraints_update(kind="TestCar")],
    ),
    SecondRunCase(
        name="node_uniqueness_constraints_update_remove",
        data="car_data_seats_in_constraint",
        edit=edit_kind("TestCar", set_uniqueness_constraints(NAME_ONLY_CONSTRAINT)),
        migrations=[constraints_update(kind="TestCar")],
    ),
    # Branch-agnostic fields on a branch-aware node, and an attribute of a branch-agnostic kind
    SecondRunCase(
        name="agnostic_attribute_add",
        data="agnostic_data",
        edit=edit_kind(
            WIDGET_KIND,
            add_attribute(
                AttributeSchema(
                    name="tag", kind="Text", optional=True, default_value="none", branch=BranchSupportType.AGNOSTIC
                )
            ),
        ),
        migrations=[
            PlannedMigration(
                "node.attribute.add", NodeAttributeAddMigration, attribute_path(kind=WIDGET_KIND, name="tag")
            )
        ],
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
    ),
    SecondRunCase(
        name="agnostic_attribute_add_without_default",
        data="agnostic_data",
        edit=edit_kind(
            WIDGET_KIND,
            add_attribute(AttributeSchema(name="label", kind="Text", optional=True, branch=BranchSupportType.AGNOSTIC)),
        ),
        migrations=[
            PlannedMigration(
                "node.attribute.add", NodeAttributeAddMigration, attribute_path(kind=WIDGET_KIND, name="label")
            )
        ],
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
    ),
    SecondRunCase(
        name="agnostic_attribute_remove",
        data="agnostic_data",
        edit=edit_kind(WIDGET_KIND, remove_attribute("serial")),
        migrations=[
            PlannedMigration(
                "node.attribute.remove", NodeAttributeRemoveMigration, attribute_path(kind=WIDGET_KIND, name="serial")
            )
        ],
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
    ),
    SecondRunCase(
        name="agnostic_attribute_name_update",
        data="agnostic_data",
        edit=edit_kind(WIDGET_KIND, rename_attribute(name="serial", new_name="serial_number")),
        migrations=[
            PlannedMigration(
                "attribute.name.update",
                AttributeNameUpdateMigration,
                attribute_path(kind=WIDGET_KIND, name="serial_number", property_name="name"),
            )
        ],
        attribute_ids=[(WIDGET_KIND, "serial")],
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
        expected_failures={
            BranchKind.DEFAULT: SECOND_RUN_RENAMES_AGAIN,
            BranchKind.USER: AGNOSTIC_RENAME_EDGES_ON_BRANCH,
            BranchKind.DEFAULT_WITH_READER_BRANCH: SECOND_RUN_RENAMES_AGAIN,
        },
    ),
    SecondRunCase(
        name="agnostic_attribute_kind_update",
        data="agnostic_data",
        edit=edit_kind(WIDGET_KIND, change_attribute(name="notes", kind="TextArea")),
        migrations=[kind_update(kind=WIDGET_KIND, name="notes")],
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
        expected_failures=dict.fromkeys(AGNOSTIC_BRANCH_KINDS, AGNOSTIC_KIND_UPDATE_EDGE_ON_BRANCH),
    ),
    SecondRunCase(
        name="agnostic_attribute_unique_update_on",
        data="agnostic_data",
        edit=edit_kind(WIDGET_KIND, change_attribute(name="notes", unique=True)),
        migrations=[
            supports_generated_schema(
                key="attribute.unique.update", kind=WIDGET_KIND, name="notes", property_name="unique"
            )
        ],
        attribute_ids=[(WIDGET_KIND, "notes")],
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
    ),
    SecondRunCase(
        name="agnostic_relationship_remove",
        data="agnostic_data",
        edit=edit_kind(WIDGET_KIND, remove_relationship("gadget")),
        migrations=[
            PlannedMigration(
                "node.relationship.remove",
                NodeRelationshipRemoveMigration,
                relationship_path(kind=WIDGET_KIND, name="gadget"),
            )
        ],
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
    ),
    SecondRunCase(
        name="node_remove_with_agnostic_fields",
        data="agnostic_data",
        edit=delete_kind(WIDGET_KIND),
        migrations=[
            PlannedMigration("node.remove", NodeRemoveMigration, node_path(kind=WIDGET_KIND), removes_kind=True)
        ],
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
    ),
    SecondRunCase(
        name="agnostic_kind_attribute_remove",
        data="agnostic_data",
        edit=edit_kind(BEACON_KIND, remove_attribute("serial")),
        migrations=[
            PlannedMigration(
                "node.attribute.remove", NodeAttributeRemoveMigration, attribute_path(kind=BEACON_KIND, name="serial")
            )
        ],
        branch_kinds=AGNOSTIC_BRANCH_KINDS,
    ),
    # A generic, whose migrations also reach the nodes of the kinds that inherit it
    SecondRunCase(
        name="attribute_kind_update_on_generic",
        data="generic_data",
        # The inheriting kinds must follow the generic's kind; as their attribute is inherited, only the generic migrates.
        edit=edit_kinds(["TestCar", *GENERIC_INHERITING_KINDS], change_attribute(name="color", kind="TextArea")),
        migrations=[kind_update(kind="TestCar", name="color")],
    ),
    GENERIC_KIND_UPDATE_DECLARED_CASE,
    GENERIC_UNIQUE_CASE,
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def case_data(request: pytest.FixtureRequest, case: SecondRunCase) -> None:
    """Create the case's data through its fixture during setup, before the migration branch exists."""
    request.getfixturevalue(case.data)


def test_every_migration_class_has_a_second_run_case() -> None:
    planned = [planned for case in SECOND_RUN_CASES for planned in case.migrations]
    assert {migration.migration_map_key for migration in planned} == {
        key for key, migration_class in MIGRATION_MAP.items() if migration_class is not None
    }
    assert [
        migration.migration_map_key
        for migration in planned
        if MIGRATION_MAP[migration.migration_map_key] is not migration.migration_class
    ] == []


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
    migrations = await build_migrations(db=db, branch=branch, case=case)
    await assert_second_run_changes_nothing(
        db=db, branch=branch, migrations=migrations, first_run_changes=case.first_run_changes
    )


@pytest.mark.parametrize("case", [GENERIC_KIND_UPDATE_DECLARED_CASE, GENERIC_UNIQUE_CASE], ids=lambda case: case.name)
@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_later_migrations_of_a_load_skip_nodes_the_first_changed(
    db: InfrahubDatabase, default_branch: Branch, case_data: None, case: SecondRunCase, branch_kind: BranchKind
) -> None:
    """The later migrations of one load change none of the nodes its first migration changed.

    They may still change nodes the first migration cannot reach, such as the profiles of the inheriting kinds.
    """
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    first_migration, *later_migrations = await build_migrations(db=db, branch=branch, case=case)

    before = await read_graph_state(db=db)
    await run_migrations(db=db, branch=branch, migrations=[first_migration], at=Timestamp(), user_id=FIRST_RUN_USER_ID)
    after_first = await read_graph_state(db=db)
    changed_by_first = changed_vertex_uuids(before=before, after=after_first)
    assert changed_by_first, "the first migration changed nothing"
    await run_migrations(db=db, branch=branch, migrations=later_migrations, at=Timestamp(), user_id=SECOND_RUN_USER_ID)
    changed_by_later = changed_vertex_uuids(before=after_first, after=await read_graph_state(db=db))
    assert changed_by_first & changed_by_later == set()


async def test_graph_state_detects_duplicate_vertex(db: InfrahubDatabase, car_data: CarData) -> None:
    await db.execute_query(query="CREATE (:AttributeValue {value: 'duplicate', is_default: false})")
    before = await read_graph_state(db=db)
    await db.execute_query(query="CREATE (:AttributeValue {value: 'duplicate', is_default: false})")
    with pytest.raises(AssertionError, match=r"vertex 1 -> 2: DbNode\(.*'value': 'duplicate'"):
        assert_graph_unchanged(before=before, after=await read_graph_state(db=db))


async def test_graph_state_detects_changed_property(db: InfrahubDatabase, car_data: CarData) -> None:
    before = await read_graph_state(db=db)
    await db.execute_query(
        query="MATCH (n:Node {uuid: $uuid}) SET n.updated_by = 'another-user'",
        params={"uuid": car_data.cars[0].id},
    )
    with pytest.raises(AssertionError, match=r"vertex 0 -> 1: DbNode\(.*'updated_by': 'another-user'"):
        assert_graph_unchanged(before=before, after=await read_graph_state(db=db))


async def test_graph_state_tells_apart_values_with_equal_hashes(db: InfrahubDatabase, car_data: CarData) -> None:
    await db.execute_query(query="CREATE (:AttributeValue {value: 5, is_default: false})")
    before = await read_graph_state(db=db)
    await db.execute_query(
        query="MATCH (av:AttributeValue {value: 5, is_default: false}) SET av.value = 4, av.is_default = true"
    )
    with pytest.raises(AssertionError, match=r"vertex 1 -> 0: DbNode\(.*'value': 5"):
        assert_graph_unchanged(before=before, after=await read_graph_state(db=db))


async def _vertices_attached_to(db: InfrahubDatabase, node_uuid: str) -> set[str]:
    results = await db.execute_query(
        query="MATCH (:Node {uuid: $uuid})-[]-(v) WHERE v:Attribute OR v:Relationship RETURN DISTINCT v.uuid AS uuid",
        params={"uuid": node_uuid},
    )
    return {row["uuid"] for row in results}


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_changed_vertex_uuids_names_the_changed_node(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    car = await NodeManager.get_one(db=db, id=car_data.cars[0].id, branch=branch)
    assert car is not None
    before = await read_graph_state(db=db)
    seats = car.get_attribute(name="nbr_seats")
    seats.value = 9
    await car.save(db=db)
    changed = changed_vertex_uuids(before=before, after=await read_graph_state(db=db))
    if branch_kind is BranchKind.DEFAULT:
        # Metadata is stamped on the node only on the default branch, which changes every edge of the node.
        assert changed == {car.id} | await _vertices_attached_to(db=db, node_uuid=car.id)
    else:
        assert changed == {seats.id}


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "the rename writes the new attribute's value edge on the migration branch, which outranks the global edge "
        "that an edit of a branch-agnostic attribute writes"
    ),
)
async def test_an_edit_after_an_agnostic_rename_on_a_user_branch_is_read_on_that_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_data: None
) -> None:
    case = next(case for case in SECOND_RUN_CASES if case.name == "agnostic_attribute_name_update")
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=BranchKind.USER)
    migrations = await build_migrations(db=db, branch=branch, case=case)
    await run_migrations(db=db, branch=branch, migrations=migrations, at=Timestamp(), user_id=FIRST_RUN_USER_ID)

    widgets = await NodeManager.query(db=db, schema=WIDGET_KIND, filters={"name__value": "widget-0"}, branch=branch)
    assert len(widgets) == 1
    widgets[0].get_attribute(name="serial_number").value = 42
    await widgets[0].save(db=db)

    reloaded = await NodeManager.get_one(db=db, id=widgets[0].id, branch=branch)
    assert reloaded is not None
    assert reloaded.get_attribute(name="serial_number").value == 42
