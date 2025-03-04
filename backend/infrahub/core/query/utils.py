from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema import NodeSchema, ProfileSchema, TemplateSchema

if TYPE_CHECKING:
    from neo4j.graph import Node as Neo4jNode

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


def find_node_schema(
    db: InfrahubDatabase, node: Neo4jNode, branch: Branch | str, duplicate: bool = False
) -> NodeSchema | ProfileSchema | TemplateSchema | None:
    for label in node.labels:
        if db.schema.has(name=label, branch=branch):
            schema = db.schema.get(name=label, branch=branch, duplicate=duplicate)
            if isinstance(schema, NodeSchema | ProfileSchema | TemplateSchema):
                return schema

    return None


def filter_and(items: list[str]) -> str:
    filter_str = " AND ".join(items)
    if len(items) > 1:
        return f" ( {filter_str} ) "
    return filter_str


def filter_or(items: list[str]) -> str:
    filter_str = " OR ".join(items)
    if len(items) > 1:
        return f" ( {filter_str} ) "
    return filter_str
