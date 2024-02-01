from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from infrahub.core.schema import NodeSchema

if TYPE_CHECKING:
    from neo4j.graph import Node as Neo4jNode

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


def find_node_schema(db: InfrahubDatabase, node: Neo4jNode, branch: Union[Branch, str], duplicate: bool) -> Optional[NodeSchema]:
    for label in node.labels:
        if db.schema.has(name=label, branch=branch):
            schema = db.schema.get(name=label, branch=branch, duplicate=duplicate)
            if isinstance(schema, NodeSchema):
                return schema

    return None
