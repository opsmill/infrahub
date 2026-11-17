"""A schema migration that runs a second time on the same branch leaves the graph unchanged.

Each test builds one migration by hand, runs it, reads the whole graph, runs it again on the same branch
and compares. The comparison covers every vertex and edge, the global branch included, so a second run
that rewrites an edge, bumps metadata or closes a global edge fails the test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.schema.node_attribute_add import NodeAttributeAddMigration
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.core.schema.definitions.core.template import core_object_component_template, core_object_template
from tests.component.core.migrations.schema.second_run_helpers import (
    BRANCH_KINDS,
    BranchKind,
    assert_graph_unchanged,
    assert_second_run_changes_nothing,
    get_migration_branch,
    read_graph_state,
    register_candidate,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@dataclass
class CarData:
    person: Node
    cars: list[Node]
    profile: Node
    template_person: Node
    template_car: Node


@pytest.fixture
async def car_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    registry.schema.register_schema(
        schema=SchemaRoot(generics=[core_object_template, core_object_component_template]), branch=default_branch.name
    )
    for node in car_person_schema_unregistered.nodes:
        node.generate_template = True
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


@pytest.fixture
async def car_data(db: InfrahubDatabase, default_branch: Branch, car_schema: SchemaBranch) -> CarData:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)

    cars = []
    for name, nbr_seats, color in (("accord", 5, "#111111"), ("camry", 4, "#222222")):
        car = await Node.init(db=db, schema="TestCar", branch=default_branch)
        await car.new(db=db, name=name, nbr_seats=nbr_seats, color=color, is_electric=False, owner=person)
        await car.save(db=db)
        cars.append(car)

    profile = await Node.init(db=db, schema="ProfileTestCar", branch=default_branch)
    await profile.new(db=db, profile_name="car-profile", nbr_seats=3, color="#333333")
    await profile.save(db=db)

    template_person = await Node.init(db=db, schema="TemplateTestPerson", branch=default_branch)
    await template_person.new(db=db, template_name="person-template")
    await template_person.save(db=db)
    template_car = await Node.init(db=db, schema="TemplateTestCar", branch=default_branch)
    await template_car.new(db=db, template_name="car-template", nbr_seats=2, color="#444444", owner=template_person)
    await template_car.save(db=db)

    return CarData(
        person=person, cars=cars, profile=profile, template_person=template_person, template_car=template_car
    )


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
