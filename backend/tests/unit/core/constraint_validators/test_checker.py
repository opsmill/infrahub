from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema_manager import SchemaUpdateConstraintInfo
from infrahub.core.validators.checker import schema_validators_checker
from infrahub.database import InfrahubDatabase
from infrahub.services import InfrahubServices


async def test_schema_validators_checker(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main, helper
):
    schema = registry.schema.get_schema_branch(name=default_branch.name).duplicate()
    person_schema = schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.regex = r"^[A-Z]+$"
    schema.set(name="TestPerson", schema=person_schema)

    constraints = [
        SchemaUpdateConstraintInfo(
            constraint_name="attribute.regex.update",
            path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name"),
        )
    ]

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator, client=InfrahubClient(), database=db)
    bus_simulator.service = service

    errors = await schema_validators_checker(
        branch=default_branch, schema=schema, constraints=constraints, service=service
    )

    assert len(errors) == 1
    assert "is not compatible with the constraint 'attribute.regex.update'" in errors[0]
