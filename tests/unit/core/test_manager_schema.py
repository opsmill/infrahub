from deepdiff import DeepDiff

from infrahub.core import registry
from infrahub.core.manager import SchemaManager
from infrahub.core.schema import NodeSchema, SchemaRoot, internal_schema


def test_load_schema_node_to_db(default_branch):

    schema = SchemaRoot(**internal_schema)
    SchemaManager.register_schema_to_registry(schema)

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
    SchemaManager.load_schema_node_to_db(node)

    assert True


def test_load_schema_to_db(default_branch):

    schema = SchemaRoot(**internal_schema)
    SchemaManager.register_schema_to_registry(schema)

    SchemaManager.load_schema_to_db(schema)

    node_schema = registry.get_schema("NodeSchema")
    results = SchemaManager.query(node_schema)
    assert len(results) > 1


def test_load_schema_from_db(default_branch):

    schema = SchemaRoot(**internal_schema)
    SchemaManager.register_schema_to_registry(schema)

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
    SchemaManager.load_schema_node_to_db(node)

    schema = SchemaManager.load_schema_from_db()
    assert len(schema.nodes) == 1

    diff = DeepDiff(node.dict(), schema.nodes[0].dict(), ignore_order=True)
    assert not diff
