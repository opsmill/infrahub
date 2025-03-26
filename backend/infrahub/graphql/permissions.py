from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.registry import registry
from infrahub.core.schema import GenericSchema
from infrahub.permissions import report_schema_permissions

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.graphql.initialization import GraphqlContext


async def get_permissions(schema: MainSchemaTypes, graphql_context: GraphqlContext) -> dict[str, Any]:
    schema_objects = [schema]
    if isinstance(schema, GenericSchema):
        for node_name in schema.used_by:
            schema_objects.append(registry.schema.get(name=node_name, branch=graphql_context.branch, duplicate=False))

    response: dict[str, Any] = {"count": len(schema_objects), "edges": []}

    nodes = await report_schema_permissions(
        branch=graphql_context.branch, permission_manager=graphql_context.active_permissions, schemas=schema_objects
    )
    response["edges"] = [{"node": node} for node in nodes]

    return response
