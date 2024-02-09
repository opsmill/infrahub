import pytest
from infrahub_sdk import UUIDT, InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.core.validators.attribute.regex import AttributeRegexUpdateValidator, AttributeRegexUpdateValidatorQuery
from infrahub.database import InfrahubDatabase
from infrahub.message_bus import Meta
from infrahub.message_bus.messages.validator_attribute_regex_update import (
    ValidatorAttributeRegexUpdate,
    ValidatorAttributeRegexUpdateResponse,
)
from infrahub.services import InfrahubServices


@pytest.fixture
async def schema_aware():
    SCHEMA = {
        "name": "Car",
        "namespace": "Test",
        "branch": "aware",
        "attributes": [
            {"name": "nbr_doors", "kind": "Number", "branch": "aware"},
        ],
    }

    node = NodeSchema(**SCHEMA)
    return node


async def test_query(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="ALFRED", height=160, cars=[car_accord_main.id])
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.regex = r"^[A-Z]+$"

    validator = AttributeRegexUpdateValidator(node_schema=person_schema, attribute_name="name")
    query = await AttributeRegexUpdateValidatorQuery.init(db=db, branch=default_branch, validator=validator)

    await query.execute(db=db)

    paths = query.get_paths()
    assert len(paths) == 1
    assert paths[0].value == "John"


async def test_validator(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="ALFRED", height=160, cars=[car_accord_main.id])
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.regex = r"^[A-Z]+$"

    validator = AttributeRegexUpdateValidator(node_schema=person_schema, attribute_name="name")
    results = await validator.run_validate(db=db, branch=default_branch)

    assert len(results) == 1
    assert results[0].display_label == "John"


async def test_rpc(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main, helper
):
    person_schema = registry.schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.regex = r"^[A-Z]+$"

    correlation_id = str(UUIDT())
    message = ValidatorAttributeRegexUpdate(
        node_schema=person_schema,
        attribute_name="name",
        branch=default_branch,
        meta=Meta(reply_to="ci-testing", correlation_id=correlation_id),
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator, client=InfrahubClient(), database=db)
    bus_simulator.service = service

    await service.send(message=message)
    assert len(bus_simulator.replies) == 1
    response: ValidatorAttributeRegexUpdateResponse = bus_simulator.replies[0]
    assert response.passed
    assert response.meta.correlation_id == correlation_id
    assert len(response.data.violations) == 1
    assert response.data.violations[0].display_label == "John"
