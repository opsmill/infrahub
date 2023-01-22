from deepdiff import DeepDiff

from infrahub.core import registry
from infrahub.core.manager import SchemaManager
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot, internal_schema


async def test_register_schema_to_registry(session, default_branch):
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "criticality",
                "kind": "Criticality",
                "default_filter": "name__value",
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "String", "unique": True},
                    {"name": "level", "kind": "Integer"},
                    {"name": "color", "kind": "String", "default_value": "#444444"},
                    {"name": "description", "kind": "String", "optional": True},
                ],
            }
        ],
        "generics": [
            {
                "name": "generic_group",
                "kind": "GenericGroup",
                "branch": True,
            },
            {
                "name": "generic_interface",
                "kind": "GenericInterface",
                "branch": True,
                "attributes": [
                    {"name": "my_generic_name", "kind": "String"},
                ],
            },
        ],
    }
    schema = SchemaRoot(**FULL_SCHEMA)
    await SchemaManager.register_schema_to_registry(schema=schema)

    assert isinstance(await registry.get_schema(session=session, name="Criticality"), NodeSchema)
    assert isinstance(await registry.get_schema(session=session, name="GenericGroup"), GenericSchema)
    assert isinstance(await registry.get_schema(session=session, name="GenericInterface"), GenericSchema)


async def test_load_node_to_db_node_schema(session, default_branch):

    schema = SchemaRoot(**internal_schema)
    await SchemaManager.register_schema_to_registry(schema=schema)

    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "level", "kind": "Integer"},
            {"name": "color", "kind": "String", "default_value": "#444444"},
            {"name": "description", "kind": "String", "optional": True},
        ],
    }
    node = NodeSchema(**SCHEMA)
    await SchemaManager.load_node_to_db(node=node, session=session)

    assert True


async def test_load_node_to_db_generic_schema(session, default_branch):

    schema = SchemaRoot(**internal_schema)
    await SchemaManager.register_schema_to_registry(schema=schema)

    SCHEMA = {
        "name": "generic_interface",
        "kind": "GenericInterface",
        "branch": True,
        "attributes": [
            {"name": "my_generic_name", "kind": "String"},
        ],
    }
    node = GenericSchema(**SCHEMA)
    await SchemaManager.load_node_to_db(node=node, session=session)

    assert True


async def test_load_schema_to_db(session, default_branch):

    schema = SchemaRoot(**internal_schema)
    await SchemaManager.register_schema_to_registry(schema=schema)

    await SchemaManager.load_schema_to_db(schema=schema, session=session)

    node_schema = await registry.get_schema(name="NodeSchema", session=session)
    results = await SchemaManager.query(schema=node_schema, session=session)
    assert len(results) > 1


async def test_load_schema_from_db(session, default_branch):

    schema = SchemaRoot(**internal_schema)
    await SchemaManager.register_schema_to_registry(schema=schema)

    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "level", "kind": "Integer"},
            {"name": "color", "kind": "String", "default_value": "#444444"},
            {"name": "description", "kind": "String", "optional": True},
        ],
    }
    node = NodeSchema(**SCHEMA)
    await SchemaManager.load_node_to_db(node=node, session=session)

    schema = await SchemaManager.load_schema_from_db(session=session)
    assert len(schema.nodes) == 1

    diff = DeepDiff(node.dict(), schema.nodes[0].dict(), ignore_order=True)
    assert not diff
