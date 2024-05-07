from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from infrahub.core import registry
from infrahub.core.schema import NodeSchema, ProfileSchema

if TYPE_CHECKING:
    from neo4j.graph import Node as Neo4jNode

    from infrahub.core.branch import Branch


def find_node_schema(
    node: Neo4jNode, branch: Union[Branch, str], duplicate: bool
) -> Optional[Union[NodeSchema, ProfileSchema]]:
    for label in node.labels:
        if registry.schema.has(name=label, branch=branch):
            schema = registry.schema.get(name=label, branch=branch, duplicate=duplicate)
            if isinstance(schema, (NodeSchema, ProfileSchema)):
                return schema

    return None
