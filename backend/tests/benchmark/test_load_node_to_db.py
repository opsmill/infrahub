from collections.abc import Callable
from typing import Any

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.schema import (
    NodeSchema,
    SchemaRoot,
    internal_schema,
)
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


def test_load_node_to_db_node_schema(
    aio_benchmark: Callable[..., Any], db: InfrahubDatabase, default_branch: Branch
) -> None:
    registry.schema = SchemaManager()
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)

    SCHEMA: dict[str, Any] = {
        "name": "Criticality",
        "namespace": "Testing",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number"},
            {"name": "color", "kind": "Text", "default_value": "#444444"},
            {"name": "description", "kind": "Text", "optional": True},
        ],
        "relationships": [
            {"name": "others", "peer": "TestingCriticality", "optional": True, "cardinality": "many"},
        ],
    }
    node = NodeSchema(**SCHEMA)

    aio_benchmark(
        registry.schema.load_node_to_db, node=node, db=db, branch=default_branch, at=Timestamp(), user_id="user-id"
    )
