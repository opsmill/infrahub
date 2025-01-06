from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.registry import registry
from infrahub.core.schema import GenericSchema
from infrahub.permissions import report_schema_permissions

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.graphql.initialization import GraphqlContext


async def get_permissions(schema: MainSchemaTypes, context: GraphqlContext) -> dict[str, Any]:
    schema_objects = [schema]
    if isinstance(schema, GenericSchema):
        for node_name in schema.used_by:
            schema_object: MainSchemaTypes
            try:
                schema_object = registry.schema.get_node_schema(name=node_name, branch=context.branch, duplicate=False)
            except ValueError:
                schema_object = registry.schema.get_profile_schema(
                    name=node_name, branch=context.branch, duplicate=False
                )
            schema_objects.append(schema_object)

    response: dict[str, Any] = {"count": len(schema_objects), "edges": []}

    nodes = await report_schema_permissions(
        branch=context.branch, permission_manager=context.active_permissions, schemas=schema_objects
    )
    response["edges"] = [{"node": node} for node in nodes]

    return response
