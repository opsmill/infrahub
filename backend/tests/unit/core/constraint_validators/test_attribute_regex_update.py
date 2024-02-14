from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathResourceType, PathType, SchemaPathType
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.validators.attribute.regex import AttributeRegexUpdateValidator, AttributeRegexUpdateValidatorQuery
from infrahub.database import InfrahubDatabase
from infrahub.message_bus.messages import (
    SchemaValidatorPath,
    SchemaValidatorPathResponse,
)
from infrahub.services import InfrahubServices


async def test_query(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="ALFRED", height=160, cars=[car_accord_main.id])
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.regex = r"^[A-Z]+$"

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name")

    query = await AttributeRegexUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_data_paths()
    assert all_data_paths == [
        DataPath(
            resource_type=PathResourceType.DATA,
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_john_main.id,
            kind="TestPerson",
            field_name="name",
            value="John",
        )
    ]


async def test_validator(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="ALFRED", height=160, cars=[car_accord_main.id])
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson", branch=default_branch)
    name_attr = person_schema.get_attribute(name="name")
    name_attr.regex = r"^[A-Z]+$"
    registry.schema.set(name="TestPerson", schema=person_schema, branch=default_branch.name)

    validator = AttributeRegexUpdateValidator(
        node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name"),
    )
    results = await validator.run_validate(db=db, branch=default_branch)

    assert len(results) == 1
    assert results[0].display_label == f"Node (TestPerson: {person_john_main.id})"


async def test_rpc(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main, helper
):
    person_schema = registry.schema.get(name="TestPerson", branch=default_branch)
    name_attr = person_schema.get_attribute(name="name")
    name_attr.regex = r"^[A-Z]+$"
    registry.schema.set(name="TestPerson", schema=person_schema, branch=default_branch.name)

    message = SchemaValidatorPath(
        constraint_name="attribute.regex.update",
        node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name"),
        branch=default_branch,
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator, client=InfrahubClient(), database=db)
    bus_simulator.service = service

    response = await service.message_bus.rpc(message=message, response_class=SchemaValidatorPathResponse)
    assert len(response.data.violations) == 1
    assert response.data.violations[0].display_label == f"Node (TestPerson: {person_john_main.id})"
