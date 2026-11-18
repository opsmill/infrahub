from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import NULL_VALUE, PathType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.attribute.regex import AttributeRegexChecker, AttributeRegexUpdateValidatorQuery
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase


async def test_query(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="ALFRED", height=160, cars=[car_accord_main.id])
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.parameters.regex = r"^[A-Z]+$"

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name")

    query = await AttributeRegexUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert all_data_paths == [
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_john_main.id,
            kind="TestPerson",
            field_name="name",
            value="John",
        )
    ]


async def test_query_NULL_allowed(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node, person_john_main: Node
) -> None:
    car_schema = registry.schema.get(name="TestCar")
    color_attr = car_schema.get_attribute(name="color")
    color_attr.optional = True
    registry.schema.set(name="TestCar", schema=car_schema)

    no_color_car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await no_color_car.new(
        db=db, name="NoColor", color=NULL_VALUE, nbr_seats=3, is_electric=False, owner=person_john_main
    )
    await no_color_car.save(db=db)
    upper_color_car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await upper_color_car.new(
        db=db, name="BIGCAR", color="#ABCDEE", nbr_seats=4, is_electric=True, owner=person_john_main
    )
    await upper_color_car.save(db=db)

    car_schema = registry.schema.get(name="TestCar")
    color_attr = car_schema.get_attribute(name="color")
    color_attr.parameters.regex = r"^#[a-z0-9]+$"

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color")

    query = await AttributeRegexUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 1
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=upper_color_car.id,
            kind="TestCar",
            field_name="color",
            value="#ABCDEE",
        )
    ) in all_data_paths


async def test_query_update_on_branch(
    db: InfrahubDatabase, branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    person_john_main.name.value = "little john"
    await person_john_main.save(db=db)

    await branch.rebase(db=db)
    person_john = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
    person_john.name.value = "BIGJOHN"
    await person_john.save(db=db)
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="ALFRED", height=160, cars=[car_accord_main.id])
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.parameters.regex = r"^[A-Z]+$"

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name")

    query = await AttributeRegexUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert all_data_paths == []


async def test_query_node_deleted_on_branch(
    db: InfrahubDatabase, branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    person_john_main.name.value = "little john"
    await person_john_main.save(db=db)

    await branch.rebase(db=db)
    person_john = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
    await person_john.delete(db=db)
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="ALFRED", height=160, cars=[car_accord_main.id])
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.parameters.regex = r"^[A-Z]+$"

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name")

    query = await AttributeRegexUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert all_data_paths == []


async def test_validator(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="ALFRED", height=160, cars=[car_accord_main.id])
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson", branch=default_branch)
    name_attr = person_schema.get_attribute(name="name")
    name_attr.parameters.regex = r"^[A-Z]+$"
    registry.schema.set(name="TestPerson", schema=person_schema, branch=default_branch.name)

    request = SchemaConstraintValidatorRequest(
        branch=default_branch,
        constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value,
        node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name"),
        schema_branch=SchemaBranch(cache={}, name="test"),
    )

    constraint_checker = AttributeRegexChecker(db=db, branch=default_branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 1
    assert data_paths[0].node_id == person_john_main.id


@dataclass(frozen=True)
class ViewCase:
    name: str
    is_isolated: bool
    reports_the_node_created_on_main_after_branching: bool


VIEW_CASES = [
    ViewCase(name="branch-view", is_isolated=True, reports_the_node_created_on_main_after_branching=False),
    ViewCase(name="merge-view", is_isolated=False, reports_the_node_created_on_main_after_branching=True),
]


@pytest.mark.parametrize("case", VIEW_CASES, ids=lambda case: case.name)
async def test_validator_on_branch_reads_the_requested_view_of_main(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch, case: ViewCase
) -> None:
    valid = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await valid.new(db=db, name="ALFRED")
    await valid.save(db=db)
    branch = await create_branch(db=db, branch_name="branch-adds-regex")
    created_after_branching = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await created_after_branching.new(db=db, name="bob")
    await created_after_branching.save(db=db)

    person_schema = registry.schema.get(name="TestPerson", branch=branch).duplicate()
    person_schema.get_attribute(name="name").parameters.regex = r"^[A-Z]+$"
    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value,
        node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name"),
        schema_branch=SchemaBranch(cache={}, name="test"),
        is_isolated=case.is_isolated,
    )

    grouped_data_paths = await AttributeRegexChecker(db=db, branch=branch).check(request)

    expected = [
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=created_after_branching.id,
            kind="TestPerson",
            field_name="name",
            value="bob",
        )
    ]
    assert len(grouped_data_paths) == 1
    assert grouped_data_paths[0].get_all_data_paths() == (
        expected if case.reports_the_node_created_on_main_after_branching else []
    )
