from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.validators.attribute.regex import AttributeRegexChecker, AttributeRegexUpdateValidatorQuery
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase
from infrahub.message_bus.messages import SchemaValidatorPathResponse
from infrahub.message_bus.messages.schema_validator_path import SchemaValidatorPath
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


async def test_query_update_on_branch(
    db: InfrahubDatabase, branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
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
    name_attr.regex = r"^[A-Z]+$"

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
    db: InfrahubDatabase, branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
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
    name_attr.regex = r"^[A-Z]+$"

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
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="ALFRED", height=160, cars=[car_accord_main.id])
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson", branch=default_branch)
    name_attr = person_schema.get_attribute(name="name")
    name_attr.regex = r"^[A-Z]+$"
    registry.schema.set(name="TestPerson", schema=person_schema, branch=default_branch.name)

    request = SchemaConstraintValidatorRequest(
        branch=default_branch,
        constraint_name="attribute.regex.update",
        node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name"),
    )

    constraint_checker = AttributeRegexChecker(db=db, branch=default_branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 1
    assert data_paths[0].node_id == person_john_main.id


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
