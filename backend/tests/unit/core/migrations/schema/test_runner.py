from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.schema.runner import schema_migrations_runner
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema
from infrahub.core.utils import count_nodes
from infrahub.database import InfrahubDatabase
from infrahub.services import InfrahubServices


async def test_schema_migrations_runner(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main, helper
):
    schema = registry.schema.get_schema_branch(name=default_branch.name).duplicate()
    person_schema = schema.get(name="TestPerson")
    person_schema.attributes.append(AttributeSchema(name="color", kind="Text", optional=True))
    schema.set(name="TestPerson", schema=person_schema)
    schema.process()

    migrations = [
        SchemaUpdateMigrationInfo(
            migration_name="node.attribute.add",
            path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="color"),
        )
    ]

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator, client=InfrahubClient(), database=db)
    bus_simulator.service = service

    assert await count_nodes(db=db, label="TestPerson") == 1
    assert await count_nodes(db=db, label="Attribute") == 12

    errors = await schema_migrations_runner(
        branch=default_branch, schema=schema, migrations=migrations, service=service
    )
    assert errors == []

    assert await count_nodes(db=db, label="TestPerson") == 1
    assert await count_nodes(db=db, label="Attribute") == 13
