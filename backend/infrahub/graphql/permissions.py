from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.registry import registry
from infrahub.core.schema import GenericSchema
from infrahub.permissions.report import report_schema_permissions

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext


async def get_permissions(db: InfrahubDatabase, schema: MainSchemaTypes, context: GraphqlContext) -> dict[str, Any]:
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
        db=db, schemas=schema_objects, branch=context.branch, account_session=context.active_account_session
    )
    response["edges"] = [{"node": node} for node in nodes]

    return response
