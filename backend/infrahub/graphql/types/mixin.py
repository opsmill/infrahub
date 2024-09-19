from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.manager import NodeManager
from infrahub.core.schema import GenericSchema, NodeSchema

if TYPE_CHECKING:
    from infrahub.graphql import GraphqlContext
    from infrahub.graphql.types.node import InfrahubObjectOptions


class QueryArguments:
    def __init__(self, partial_match: Any, offset: Any, limit: Any) -> None:
        self.partial_match = False
        self.limit: int | None = None
        self.offset: int | None = None
        if isinstance(partial_match, bool):
            self.partial_match = partial_match
        if isinstance(offset, int):
            self.offset = offset
        if isinstance(limit, int):
            self.limit = limit


class GetListMixin:
    """Mixins to Query the list of nodes using the NodeManager."""

    _meta: InfrahubObjectOptions

    @classmethod
    async def get_paginated_list(cls, fields: dict, context: GraphqlContext, **kwargs: dict[str, Any]) -> dict:
        partial_match = kwargs.pop("partial_match", False)
        offset = kwargs.pop("offset", None)
        limit = kwargs.pop("limit", None)
        query_args = QueryArguments(partial_match=partial_match, offset=offset, limit=limit)

        async with context.db.start_session() as db:
            schema = cls._meta.schema
            response: dict[str, Any] = {"edges": []}
            filters = {
                key: value
                for key, value in kwargs.items()
                if ("__" in key and value is not None) or key in ("ids", "hfid")
            }

            edges = fields.get("edges", {})
            node_fields = edges.get("node", {})

            permissions = fields.get("permissions")
            if permissions:
                response["permissions"] = {}
                permission_objects = [
                    {
                        "node": {
                            "kind": schema.kind,
                            "create": "allow",
                            "delete": "allow",
                            "update": "allow",
                            "view": "allow",
                        }
                    }
                ]
                if isinstance(schema, NodeSchema):
                    response["permissions"]["count"] = 1

                elif isinstance(schema, GenericSchema):
                    response["permissions"]["count"] = len(schema.used_by) + 1
                    for node in schema.used_by:
                        permission_objects.append(
                            {
                                "node": {
                                    "kind": node,
                                    "create": "allow",
                                    "delete": "allow",
                                    "update": "allow",
                                    "view": "allow",
                                }
                            }
                        )

                response["permissions"]["edges"] = permission_objects

            objs = await NodeManager.query(
                db=db,
                schema=schema,
                filters=filters or None,
                fields=node_fields,
                at=context.at,
                branch=context.branch,
                limit=query_args.limit,
                offset=query_args.offset,
                account=context.account_session,
                include_source=True,
                include_owner=True,
                partial_match=query_args.partial_match,
            )

            if "count" in fields:
                if filters.get("hfid"):
                    response["count"] = len(objs)
                else:
                    response["count"] = await NodeManager.count(
                        db=db,
                        schema=schema,
                        filters=filters,
                        at=context.at,
                        branch=context.branch,
                        partial_match=query_args.partial_match,
                    )

            if objs:
                objects = [
                    {"node": await obj.to_graphql(db=db, fields=node_fields, related_node_ids=context.related_node_ids)}
                    for obj in objs
                ]
                response["edges"] = objects

            return response
