from __future__ import annotations

from typing import Any, Dict

import infrahub.config as config
from infrahub.core.manager import NodeManager


class GetListMixin:
    """Mixins to Query the list of nodes using the NodeManager."""

    @classmethod
    async def get_list(cls, fields: dict, context: dict, **kwargs):
        at = context.get("infrahub_at")
        branch = context.get("infrahub_branch")
        account = context.get("infrahub_account", None)
        db = context.get("infrahub_database")

        async with db.session(database=config.SETTINGS.database.database) as session:
            context["infrahub_session"] = session

            filters = {key: value for key, value in kwargs.items() if ("__" in key and value) or key == "ids"}

            objs = await NodeManager.query(
                db=db,
                schema=cls._meta.schema,
                filters=filters or None,
                fields=fields,
                at=at,
                branch=branch,
                account=account,
                include_source=True,
                include_owner=True,
            )

            if not objs:
                return []

            return [await obj.to_graphql(db=db, fields=fields) for obj in objs]

    @classmethod
    async def get_paginated_list(cls, fields: dict, context: dict, **kwargs):
        at = context.get("infrahub_at")
        branch = context.get("infrahub_branch")
        account = context.get("infrahub_account", None)
        db = context.get("infrahub_database")

        response: Dict[str, Any] = {"edges": []}
        offset = kwargs.pop("offset", None)
        limit = kwargs.pop("limit", None)
        filters = {key: value for key, value in kwargs.items() if ("__" in key and value) or key == "ids"}
        if "count" in fields:
            response["count"] = await NodeManager.count(
                db=db,
                schema=cls._meta.schema,
                filters=filters,
                at=at,
                branch=branch,
            )
        edges = fields.get("edges", {})
        node_fields = edges.get("node", {})

        objs = await NodeManager.query(
            db=db,
            schema=cls._meta.schema,
            filters=filters or None,
            fields=node_fields,
            at=at,
            branch=branch,
            limit=limit,
            offset=offset,
            account=account,
            include_source=True,
            include_owner=True,
        )

        if objs:
            objects = [{"node": await obj.to_graphql(db=db, fields=node_fields)} for obj in objs]
            response["edges"] = objects

        return response
