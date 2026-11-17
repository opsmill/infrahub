"""A schema migration that runs a second time on the same branch leaves the graph unchanged.

Each test builds one migration by hand, runs it, reads the whole graph, runs it again on the same branch
and compares. The comparison covers every vertex and edge, the global branch included, so a second run
that rewrites an edge, bumps metadata or closes a global edge fails the test.
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, HashableModelState, SchemaPathType
from infrahub.core.manager import NodeManager
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
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, GenericSchema, SchemaRoot
from infrahub.core.schema.definitions.core.template import core_object_component_template, core_object_template
from infrahub.core.timestamp import Timestamp
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

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.migrations.shared import SchemaMigration
    from infrahub.core.schema.node_schema import NodeSchema
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
from tests.helpers.agnostic_edges import create_gadget, create_widget
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_RETIREMENT_SCHEMA, BEACON_KIND, WIDGET_KIND


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
async def car_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    return register_car_schema(default_branch=default_branch, schema=car_person_schema_unregistered)


@pytest.fixture
async def car_data(db: InfrahubDatabase, default_branch: Branch, car_schema: SchemaBranch) -> CarData:
    return await create_car_data(db=db, default_branch=default_branch)


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


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_node_attribute_add(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get_node(name="TestCar", duplicate=True)
    candidate = schema_branch.duplicate()
    car = candidate.get_node(name="TestCar", duplicate=True)
    car.attributes.append(AttributeSchema(name="tag", kind="Text", optional=True, default_value="none"))
    candidate.set(name="TestCar", schema=car)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = NodeAttributeAddMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name="TestCar"),
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="tag"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


def attribute_path(kind: str, name: str) -> SchemaPath:
    return SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name=name)


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_node_attribute_remove(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get_node(name="TestCar", duplicate=True)
    candidate = schema_branch.duplicate()
    car = candidate.get_node(name="TestCar", duplicate=True)
    car.get_attribute(name="is_electric").state = HashableModelState.ABSENT
    candidate.set(name="TestCar", schema=car)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = NodeAttributeRemoveMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name="TestCar"),
        schema_path=attribute_path(kind="TestCar", name="is_electric"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_attribute_name_update(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get_node(name="TestCar", duplicate=True)
    attribute_id = str(uuid.uuid4())
    previous.get_attribute(name="is_electric").id = attribute_id
    candidate = schema_branch.duplicate()
    car = candidate.get_node(name="TestCar", duplicate=True)
    renamed = car.get_attribute(name="is_electric")
    renamed.id = attribute_id
    renamed.name = "electric"
    candidate.set(name="TestCar", schema=car)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = AttributeNameUpdateMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name="TestCar"),
        schema_path=attribute_path(kind="TestCar", name="electric"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_attribute_kind_update(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get_node(name="TestCar", duplicate=True)
    candidate = schema_branch.duplicate()
    car = candidate.get_node(name="TestCar", duplicate=True)
    car.get_attribute(name="color").kind = "TextArea"
    candidate.set(name="TestCar", schema=car)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = AttributeKindUpdateMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name="TestCar"),
        schema_path=attribute_path(kind="TestCar", name="color"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_node_relationship_remove(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get_node(name="TestCar", duplicate=True)
    candidate = schema_branch.duplicate()
    car = candidate.get_node(name="TestCar", duplicate=True)
    car.get_relationship(name="driver").state = HashableModelState.ABSENT
    candidate.set(name="TestCar", schema=car)
    person = candidate.get_node(name="TestPerson", duplicate=True)
    person.get_relationship(name="cars_driven").state = HashableModelState.ABSENT
    candidate.set(name="TestPerson", schema=person)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = NodeRelationshipRemoveMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name="TestCar"),
        schema_path=SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestCar", field_name="driver"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_node_remove(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get_node(name="TestCar", duplicate=True)
    candidate = schema_branch.duplicate()
    candidate.delete(name="TestCar")
    person = candidate.get_node(name="TestPerson", duplicate=True)
    for relationship_name in ("cars", "cars_driven"):
        person.get_relationship(name=relationship_name).state = HashableModelState.ABSENT
    candidate.set(name="TestPerson", schema=person)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = NodeRemoveMigration(
        previous_node_schema=previous,
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


def rename_car_kind(candidate: SchemaBranch, namespace: str, name: str) -> str:
    """Replace TestCar with a kind of the given namespace and name, and point the person's peers at it."""
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
    return car.kind


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_node_inherit_from_update(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get_node(name="TestCar", duplicate=True)
    candidate = schema_branch.duplicate()
    generic = GenericSchema(
        name="Asset",
        namespace="Test",
        branch=BranchSupportType.AWARE,
        attributes=[AttributeSchema(name="status", kind="Text", default_value="active", optional=True)],
    )
    candidate.set(name=generic.kind, schema=generic)
    car = candidate.get_node(name="TestCar", duplicate=True)
    car.inherit_from = [*car.inherit_from, generic.kind]
    candidate.set(name="TestCar", schema=car)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = NodeKindUpdateMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name="TestCar"),
        schema_path=attribute_path(kind="TestCar", name="inherit_from"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_node_name_update(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get_node(name="TestCar", duplicate=True)
    candidate = schema_branch.duplicate()
    new_kind = rename_car_kind(candidate=candidate, namespace="Test", name="Auto")
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = NodeKindUpdateMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name=new_kind),
        schema_path=attribute_path(kind=new_kind, name="name"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_node_namespace_update(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get_node(name="TestCar", duplicate=True)
    candidate = schema_branch.duplicate()
    new_kind = rename_car_kind(candidate=candidate, namespace="Test2", name="Car")
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = NodeKindUpdateMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name=new_kind),
        schema_path=attribute_path(kind=new_kind, name="namespace"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


SEATS_IN_CONSTRAINT = [["name__value", "nbr_seats__value"]]
NAME_ONLY_CONSTRAINT = [["name__value"]]


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


async def assert_seats_change_runs_twice_unchanged(
    db: InfrahubDatabase,
    branch: Branch,
    unique: bool | None = None,
    read_only: bool | None = None,
    optional: bool | None = None,
    uniqueness_constraints: list[list[str]] | None = None,
    first_run_changes: bool = True,
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get_node(name="TestCar", duplicate=True)
    # A schema registered in memory has no IDs, and the migration treats an attribute without one as new.
    attribute_id = str(uuid.uuid4())
    previous.get_attribute(name="nbr_seats").id = attribute_id
    candidate = schema_branch.duplicate()
    car = candidate.get_node(name="TestCar", duplicate=True)
    seats = car.get_attribute(name="nbr_seats")
    seats.id = attribute_id
    if unique is not None:
        seats.unique = unique
    if read_only is not None:
        seats.read_only = read_only
    if optional is not None:
        seats.optional = optional
    if uniqueness_constraints is not None:
        car.uniqueness_constraints = uniqueness_constraints
    candidate.set(name="TestCar", schema=car)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name="TestCar"),
        schema_path=attribute_path(kind="TestCar", name="nbr_seats"),
    )
    await assert_second_run_changes_nothing(
        db=db, branch=branch, migrations=[migration], first_run_changes=first_run_changes
    )


async def assert_constraint_change_runs_twice_unchanged(
    db: InfrahubDatabase, branch: Branch, uniqueness_constraints: list[list[str]]
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get_node(name="TestCar", duplicate=True)
    candidate = schema_branch.duplicate()
    car = candidate.get_node(name="TestCar", duplicate=True)
    car.uniqueness_constraints = uniqueness_constraints
    candidate.set(name="TestCar", schema=car)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = NodeUniquenessConstraintsUpdateMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name="TestCar"),
        schema_path=SchemaPath(
            path_type=SchemaPathType.NODE,
            schema_kind="TestCar",
            field_name="uniqueness_constraints",
            property_name="uniqueness_constraints",
        ),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_attribute_unique_update_on(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    await assert_seats_change_runs_twice_unchanged(db=db, branch=branch, unique=True)


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_attribute_unique_update_off(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot, branch_kind: BranchKind
) -> None:
    register_car_schema(
        default_branch=default_branch, schema=car_schema_variant(schema=car_person_schema_unregistered, unique=True)
    )
    await create_car_data(db=db, default_branch=default_branch, seats_on_profile=False, seats_on_template=False)
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    # Processing a unique attribute adds it to the uniqueness constraints, which turning unique off leaves behind.
    await assert_seats_change_runs_twice_unchanged(
        db=db, branch=branch, unique=False, uniqueness_constraints=NAME_ONLY_CONSTRAINT
    )


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_attribute_read_only_update_on(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    await assert_seats_change_runs_twice_unchanged(db=db, branch=branch, read_only=True)


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_attribute_read_only_update_off(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot, branch_kind: BranchKind
) -> None:
    register_car_schema(
        default_branch=default_branch,
        schema=car_schema_variant(schema=car_person_schema_unregistered, read_only=True),
    )
    await create_car_data(db=db, default_branch=default_branch, seats_on_profile=False, seats_on_template=False)
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    await assert_seats_change_runs_twice_unchanged(db=db, branch=branch, read_only=False)


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_attribute_optional_update(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    """Profile and template support depends on read_only and unique, not on optional, so neither run changes data."""
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    await assert_seats_change_runs_twice_unchanged(db=db, branch=branch, optional=False, first_run_changes=False)


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_node_uniqueness_constraints_update_add(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    await assert_constraint_change_runs_twice_unchanged(
        db=db, branch=branch, uniqueness_constraints=SEATS_IN_CONSTRAINT
    )


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_node_uniqueness_constraints_update_remove(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot, branch_kind: BranchKind
) -> None:
    register_car_schema(
        default_branch=default_branch,
        schema=car_schema_variant(schema=car_person_schema_unregistered, uniqueness_constraints=SEATS_IN_CONSTRAINT),
    )
    await create_car_data(db=db, default_branch=default_branch, seats_on_profile=False)
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    await assert_constraint_change_runs_twice_unchanged(
        db=db, branch=branch, uniqueness_constraints=NAME_ONLY_CONSTRAINT
    )


@dataclass
class AgnosticData:
    gadgets: list[Node]
    widgets: list[Node]
    widget_profile: Node | None
    beacons: list[Node]


@pytest.fixture
async def agnostic_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaBranch:
    schema = deepcopy(AGNOSTIC_RETIREMENT_SCHEMA)
    widget = next(node for node in schema.nodes if node.kind == WIDGET_KIND)
    widget.attributes.append(
        AttributeSchema(name="notes", kind="Text", optional=True, branch=BranchSupportType.AGNOSTIC)
    )
    return registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def agnostic_data(db: InfrahubDatabase, default_branch: Branch, agnostic_schema: SchemaBranch) -> AgnosticData:
    gadgets = [await create_gadget(db=db, branch=default_branch, name=f"gadget-{index}") for index in range(2)]
    widgets = [
        await create_widget(
            db=db, branch=default_branch, name=f"widget-{index}", serial=index, notes=f"note-{index}", gadget=gadget
        )
        for index, gadget in enumerate(gadgets)
    ]
    widget_profile = None
    if agnostic_schema.has(name=f"Profile{WIDGET_KIND}"):
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


def candidate_with_node(branch: Branch, kind: str) -> tuple[NodeSchema, SchemaBranch, NodeSchema]:
    """Return the node's current schema, a candidate schema branch and a copy of the node to change in it."""
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous = schema_branch.get_node(name=kind, duplicate=True)
    candidate = schema_branch.duplicate()
    return previous, candidate, candidate.get_node(name=kind, duplicate=True)


@pytest.mark.parametrize("branch_kind", AGNOSTIC_BRANCH_KINDS)
async def test_agnostic_attribute_add(
    db: InfrahubDatabase, default_branch: Branch, agnostic_data: AgnosticData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    previous, candidate, widget = candidate_with_node(branch=branch, kind=WIDGET_KIND)
    widget.attributes.append(
        AttributeSchema(name="tag", kind="Text", optional=True, default_value="none", branch=BranchSupportType.AGNOSTIC)
    )
    candidate.set(name=WIDGET_KIND, schema=widget)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = NodeAttributeAddMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name=WIDGET_KIND),
        schema_path=attribute_path(kind=WIDGET_KIND, name="tag"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.parametrize("branch_kind", AGNOSTIC_BRANCH_KINDS)
async def test_agnostic_attribute_remove(
    db: InfrahubDatabase, default_branch: Branch, agnostic_data: AgnosticData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    previous, candidate, widget = candidate_with_node(branch=branch, kind=WIDGET_KIND)
    widget.get_attribute(name="serial").state = HashableModelState.ABSENT
    candidate.set(name=WIDGET_KIND, schema=widget)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = NodeAttributeRemoveMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name=WIDGET_KIND),
        schema_path=attribute_path(kind=WIDGET_KIND, name="serial"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.xfail(
    strict=True,
    raises=GraphValidationError,
    reason="the first run creates the renamed agnostic attribute with its edges on the migration branch, not -global-",
)
@pytest.mark.parametrize("branch_kind", AGNOSTIC_BRANCH_KINDS)
async def test_agnostic_attribute_name_update(
    db: InfrahubDatabase, default_branch: Branch, agnostic_data: AgnosticData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    previous, candidate, widget = candidate_with_node(branch=branch, kind=WIDGET_KIND)
    attribute_id = str(uuid.uuid4())
    previous.get_attribute(name="serial").id = attribute_id
    renamed = widget.get_attribute(name="serial")
    renamed.id = attribute_id
    renamed.name = "serial_number"
    candidate.set(name=WIDGET_KIND, schema=widget)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = AttributeNameUpdateMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name=WIDGET_KIND),
        schema_path=attribute_path(kind=WIDGET_KIND, name="serial_number"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.xfail(
    strict=True,
    raises=GraphValidationError,
    reason="the first run writes the new HAS_VALUE edge of an agnostic attribute on the migration branch, not -global-",
)
@pytest.mark.parametrize("branch_kind", AGNOSTIC_BRANCH_KINDS)
async def test_agnostic_attribute_kind_update(
    db: InfrahubDatabase, default_branch: Branch, agnostic_data: AgnosticData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    previous, candidate, widget = candidate_with_node(branch=branch, kind=WIDGET_KIND)
    widget.get_attribute(name="notes").kind = "TextArea"
    candidate.set(name=WIDGET_KIND, schema=widget)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = AttributeKindUpdateMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name=WIDGET_KIND),
        schema_path=attribute_path(kind=WIDGET_KIND, name="notes"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.parametrize("branch_kind", AGNOSTIC_BRANCH_KINDS)
async def test_agnostic_attribute_unique_update_on(
    db: InfrahubDatabase, default_branch: Branch, agnostic_data: AgnosticData, branch_kind: BranchKind
) -> None:
    if agnostic_data.widget_profile is None:
        pytest.skip("the widget kind generates no profile kind, so the migration has no profile node to change")
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    previous, candidate, widget = candidate_with_node(branch=branch, kind=WIDGET_KIND)
    attribute_id = str(uuid.uuid4())
    previous.get_attribute(name="notes").id = attribute_id
    notes = widget.get_attribute(name="notes")
    notes.id = attribute_id
    notes.unique = True
    candidate.set(name=WIDGET_KIND, schema=widget)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name=WIDGET_KIND),
        schema_path=attribute_path(kind=WIDGET_KIND, name="notes"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.parametrize("branch_kind", AGNOSTIC_BRANCH_KINDS)
async def test_agnostic_relationship_remove(
    db: InfrahubDatabase, default_branch: Branch, agnostic_data: AgnosticData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    previous, candidate, widget = candidate_with_node(branch=branch, kind=WIDGET_KIND)
    widget.get_relationship(name="gadget").state = HashableModelState.ABSENT
    candidate.set(name=WIDGET_KIND, schema=widget)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = NodeRelationshipRemoveMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name=WIDGET_KIND),
        schema_path=SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind=WIDGET_KIND, field_name="gadget"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.parametrize("branch_kind", AGNOSTIC_BRANCH_KINDS)
async def test_node_remove_with_agnostic_fields(
    db: InfrahubDatabase, default_branch: Branch, agnostic_data: AgnosticData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    previous, candidate, _ = candidate_with_node(branch=branch, kind=WIDGET_KIND)
    candidate.delete(name=WIDGET_KIND)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = NodeRemoveMigration(
        previous_node_schema=previous,
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind=WIDGET_KIND),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.parametrize("branch_kind", AGNOSTIC_BRANCH_KINDS)
async def test_agnostic_kind_attribute_remove(
    db: InfrahubDatabase, default_branch: Branch, agnostic_data: AgnosticData, branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    previous, candidate, beacon = candidate_with_node(branch=branch, kind=BEACON_KIND)
    beacon.get_attribute(name="serial").state = HashableModelState.ABSENT
    candidate.set(name=BEACON_KIND, schema=beacon)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = NodeAttributeRemoveMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_node(name=BEACON_KIND),
        schema_path=attribute_path(kind=BEACON_KIND, name="serial"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


GENERIC_INHERITING_KINDS = ["TestElectricCar", "TestGazCar"]


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


async def assert_kind_migrations_skip_nodes_changed_by_generic(
    db: InfrahubDatabase,
    branch: Branch,
    generic_migration: SchemaMigration,
    kind_migrations: Sequence[SchemaMigration],
) -> None:
    """Run the generic's migration, then assert the inheriting kinds' migrations of the same load change none of its nodes.

    The kinds' migrations may still change nodes the generic's migration cannot reach, such as their own profiles.
    """
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


def generic_candidate(branch: Branch) -> tuple[SchemaBranch, SchemaBranch]:
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    return schema_branch, schema_branch.duplicate()


def generic_constraint_migrations(branch: Branch) -> tuple[SchemaBranch, list[SchemaMigration]]:
    """Add nbr_seats to the generic's uniqueness constraints and build the migration a load creates for each kind."""
    schema_branch, candidate = generic_candidate(branch=branch)
    generic = candidate.get_generic(name="TestCar", duplicate=True)
    generic.uniqueness_constraints = SEATS_IN_CONSTRAINT
    candidate.set(name="TestCar", schema=generic)
    candidate.process()
    migrations: list[SchemaMigration] = [
        NodeUniquenessConstraintsUpdateMigration(
            previous_node_schema=schema_branch.get(name=kind, duplicate=True),
            new_node_schema=candidate.get(name=kind),
            schema_path=SchemaPath(
                path_type=SchemaPathType.NODE,
                schema_kind=kind,
                field_name="uniqueness_constraints",
                property_name="uniqueness_constraints",
            ),
        )
        for kind in ["TestCar", *GENERIC_INHERITING_KINDS]
    ]
    return candidate, migrations


def generic_color_kind_migrations(branch: Branch) -> tuple[SchemaBranch, list[SchemaMigration]]:
    """Change the generic's color to TextArea and build the migration a load creates for the generic and each kind."""
    schema_branch, candidate = generic_candidate(branch=branch)
    generic = candidate.get_generic(name="TestCar", duplicate=True)
    generic.get_attribute(name="color").kind = "TextArea"
    candidate.set(name="TestCar", schema=generic)
    for kind in GENERIC_INHERITING_KINDS:
        node = candidate.get_node(name=kind, duplicate=True)
        node.get_attribute(name="color").kind = "TextArea"
        candidate.set(name=kind, schema=node)
    candidate.process()
    migrations: list[SchemaMigration] = [
        AttributeKindUpdateMigration(
            previous_node_schema=schema_branch.get(name=kind, duplicate=True),
            new_node_schema=candidate.get(name=kind),
            schema_path=attribute_path(kind=kind, name="color"),
        )
        for kind in ["TestCar", *GENERIC_INHERITING_KINDS]
    ]
    return candidate, migrations


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_attribute_unique_update_on_generic(
    db: InfrahubDatabase, default_branch: Branch, generic_profiles: list[Node], branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    schema_branch, candidate = generic_candidate(branch=branch)
    previous = schema_branch.get_generic(name="TestCar", duplicate=True)
    attribute_id = str(uuid.uuid4())
    previous.get_attribute(name="nbr_seats").id = attribute_id
    generic = candidate.get_generic(name="TestCar", duplicate=True)
    seats = generic.get_attribute(name="nbr_seats")
    seats.id = attribute_id
    seats.unique = True
    candidate.set(name="TestCar", schema=generic)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=previous,
        new_node_schema=candidate.get_generic(name="TestCar"),
        schema_path=attribute_path(kind="TestCar", name="nbr_seats"),
    )
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=[migration])


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_node_uniqueness_constraints_update_on_generic_kind_skips_generic_nodes(
    db: InfrahubDatabase, default_branch: Branch, generic_profiles: list[Node], branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    candidate, migrations = generic_constraint_migrations(branch=branch)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    await assert_kind_migrations_skip_nodes_changed_by_generic(
        db=db, branch=branch, generic_migration=migrations[0], kind_migrations=migrations[1:]
    )


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_node_uniqueness_constraints_update_on_generic_twice(
    db: InfrahubDatabase, default_branch: Branch, generic_profiles: list[Node], branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    candidate, migrations = generic_constraint_migrations(branch=branch)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=migrations)


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_attribute_kind_update_on_generic_kind_skips_generic_nodes(
    db: InfrahubDatabase, default_branch: Branch, generic_profiles: list[Node], branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    candidate, migrations = generic_color_kind_migrations(branch=branch)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    await assert_kind_migrations_skip_nodes_changed_by_generic(
        db=db, branch=branch, generic_migration=migrations[0], kind_migrations=migrations[1:]
    )


@pytest.mark.parametrize("branch_kind", BRANCH_KINDS)
async def test_attribute_kind_update_on_generic_twice(
    db: InfrahubDatabase, default_branch: Branch, generic_profiles: list[Node], branch_kind: BranchKind
) -> None:
    branch = await get_migration_branch(db=db, default_branch=default_branch, branch_kind=branch_kind)
    candidate, migrations = generic_color_kind_migrations(branch=branch)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    await assert_second_run_changes_nothing(db=db, branch=branch, migrations=migrations)
