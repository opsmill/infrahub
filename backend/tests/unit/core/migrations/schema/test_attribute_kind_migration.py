import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.schema.attribute_kind_update import (
    AttributeKindUpdateMigration,
    AttributeKindUpdateMigrationQuery01,
)
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import NodeSchema
from infrahub.core.utils import count_nodes
from infrahub.database import InfrahubDatabase


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


async def test_query01(
    db: InfrahubDatabase,
    car_accord_main: Node,
    car_volt_main: Node,
    person_john_main,
    person_alfred_main,
    branch: Branch,
):
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="Otto", height=160)
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    initial_schema = person_schema.duplicate()
    height_attr = person_schema.get_attribute(name="height")
    height_attr.kind = "Text"

    initial_nbr_attribute = await count_nodes(db=db, label="Attribute")

    migration = AttributeKindUpdateMigration(
        new_node_schema=person_schema,
        previous_node_schema=initial_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height"),
    )
    query = await AttributeKindUpdateMigrationQuery01.init(db=db, branch=branch, migration=migration)
    await query.execute(db=db)
    assert await count_nodes(db=db, label="Attribute") == initial_nbr_attribute + 3

    # Re-execute the query once to ensure that it won't recreate the attribute twice
    query = await AttributeKindUpdateMigrationQuery01.init(db=db, branch=branch, migration=migration)
    await query.execute(db=db)
    assert await count_nodes(db=db, label="Attribute") == initial_nbr_attribute + 3


async def test_migration(
    db: InfrahubDatabase,
    car_accord_main: Node,
    car_volt_main: Node,
    person_john_main,
    person_alfred_main,
    branch: Branch,
):
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="Otto", height=160)
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    initial_schema = person_schema.duplicate()
    height_attr = person_schema.get_attribute(name="height")
    height_attr.kind = "Text"

    initial_nbr_attribute = await count_nodes(db=db, label="Attribute")

    migration = AttributeKindUpdateMigration(
        new_node_schema=person_schema,
        previous_node_schema=initial_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height"),
    )

    execution_result = await migration.execute(db=db, branch=branch)
    assert not execution_result.errors

    assert await count_nodes(db=db, label="Attribute") == initial_nbr_attribute + 3
