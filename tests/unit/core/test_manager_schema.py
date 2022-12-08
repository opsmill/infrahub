import pytest

from deepdiff import DeepDiff

from infrahub.core import registry
from infrahub.core.manager import SchemaManager
from infrahub.core.schema import NodeSchema, SchemaRoot, internal_schema


@pytest.mark.asyncio
async def test_load_schema_node_to_db(session, default_branch):

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
    await SchemaManager.load_schema_node_to_db(schema_node=node, session=session)

    assert True


@pytest.mark.asyncio
async def test_load_schema_to_db(session, default_branch):

    schema = SchemaRoot(**internal_schema)
    await SchemaManager.register_schema_to_registry(schema=schema)

    await SchemaManager.load_schema_to_db(schema=schema, session=session)

    node_schema = await registry.get_schema(name="NodeSchema", session=session)
    results = await SchemaManager.query(schema=node_schema, session=session)
    assert len(results) > 1


@pytest.mark.asyncio
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
    await SchemaManager.load_schema_node_to_db(schema_node=node, session=session)

    schema = await SchemaManager.load_schema_from_db(session=session)
    assert len(schema.nodes) == 1

    diff = DeepDiff(node.dict(), schema.nodes[0].dict(), ignore_order=True)
    assert not diff
