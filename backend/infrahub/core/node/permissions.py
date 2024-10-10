from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from . import Node

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class CoreGlobalPermission(Node):
    async def to_graphql(
        self,
        db: InfrahubDatabase,
        fields: Optional[dict] = None,
        related_node_ids: Optional[set] = None,
        filter_sensitive: bool = False,
        permissions: Optional[dict] = None,
    ) -> dict:
        response = await super().to_graphql(
            db,
            fields=fields,
            related_node_ids=related_node_ids,
            filter_sensitive=filter_sensitive,
            permissions=permissions,
        )

        if fields:
            if "identifier" in fields:
                response["identifier"] = {"value": f"global:{self.action.value}:{self.decision.value.value}"}  # type: ignore[attr-defined]

        return response


class CoreObjectPermission(Node):
    async def to_graphql(
        self,
        db: InfrahubDatabase,
        fields: Optional[dict] = None,
        related_node_ids: Optional[set] = None,
        filter_sensitive: bool = False,
        permissions: Optional[dict] = None,
    ) -> dict:
        response = await super().to_graphql(
            db,
            fields=fields,
            related_node_ids=related_node_ids,
            filter_sensitive=filter_sensitive,
            permissions=permissions,
        )

        if fields:
            if "identifier" in fields:
                response["identifier"] = {
                    "value": f"object:{self.namespace.value}:{self.name.value}:{self.action.value.value}:{self.decision.value.value}"  # type: ignore[attr-defined]
                }

        return response
