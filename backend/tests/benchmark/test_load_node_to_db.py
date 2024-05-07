from infrahub.core import registry
from infrahub.core.schema import (
    NodeSchema,
    SchemaRoot,
    internal_schema,
)
from infrahub.core.schema_manager import SchemaManager
from infrahub.database import InfrahubDatabase


def test_load_node_to_db_node_schema(aio_benchmark, db: InfrahubDatabase, default_branch):
    registry.schema = SchemaManager()
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)

    SCHEMA = {
        "name": "Criticality",
        "namespace": "Builtin",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number"},
            {"name": "color", "kind": "Text", "default_value": "#444444"},
            {"name": "description", "kind": "Text", "optional": True},
        ],
        "relationships": [
            {"name": "others", "peer": "BuiltinCriticality", "optional": True, "cardinality": "many"},
        ],
    }
    node = NodeSchema(**SCHEMA)  # type: ignore[arg-type]

    aio_benchmark(registry.schema.load_node_to_db, node=node, db=db, branch=default_branch)
