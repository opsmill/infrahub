from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from dependencies.registry import get_component_registry

from infrahub.core.manager import NodeManager
from infrahub.core.to_graphql.aggregated import AggregatedToGraphQLTranslators
from infrahub.core.to_graphql.model import ToGraphQLRequest

if TYPE_CHECKING:
    from infrahub.graphql import GraphqlContext


class GetListMixin:
    """Mixins to Query the list of nodes using the NodeManager."""

    @classmethod
    async def get_list(cls, fields: dict, context: GraphqlContext, **kwargs):
        to_graphql_translator = get_component_registry().get_component(AggregatedToGraphQLTranslators)
        async with context.db.start_session() as db:
            filters = {key: value for key, value in kwargs.items() if ("__" in key and value) or key == "ids"}

            objs = await NodeManager.query(
                db=db,
                schema=cls._meta.schema,
                filters=filters or None,
                fields=fields,
                at=context.at,
                branch=context.branch,
                account=context.account_session,
                include_source=True,
                include_owner=True,
            )

            if not objs:
                return []
            return [
                await to_graphql_translator.to_graphql(
                    ToGraphQLRequest(obj=obj, db=db, fields=fields, related_node_ids=context.related_node_ids)
                )
                for obj in objs
            ]

    @classmethod
    async def get_paginated_list(cls, fields: dict, context: GraphqlContext, **kwargs):
        to_graphql_translator = get_component_registry().get_component(AggregatedToGraphQLTranslators)
        partial_match = kwargs.pop("partial_match", False)

        async with context.db.start_session() as db:
            response: Dict[str, Any] = {"edges": []}
            offset = kwargs.pop("offset", None)
            limit = kwargs.pop("limit", None)
            filters = {key: value for key, value in kwargs.items() if ("__" in key and value) or key == "ids"}
            if "count" in fields:
                response["count"] = await NodeManager.count(
                    db=db,
                    schema=cls._meta.schema,
                    filters=filters,
                    at=context.at,
                    branch=context.branch,
                    partial_match=partial_match,
                )
            edges = fields.get("edges", {})
            node_fields = edges.get("node", {})

            objs = await NodeManager.query(
                db=db,
                schema=cls._meta.schema,
                filters=filters or None,
                fields=node_fields,
                at=context.at,
                branch=context.branch,
                limit=limit,
                offset=offset,
                account=context.account_session,
                include_source=True,
                include_owner=True,
                partial_match=partial_match,
            )
            if objs:
                objects = [
                    {
                        "node": await to_graphql_translator.to_graphql(
                            ToGraphQLRequest(
                                db=db, obj=obj, fields=node_fields, related_node_ids=context.related_node_ids
                            )
                        )
                    }
                    for obj in objs
                ]
                response["edges"] = objects

            return response
