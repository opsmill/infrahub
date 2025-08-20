from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.permissions.constants import PermissionDecisionFlag

from . import Node

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class CoreGlobalPermission(Node):
    async def to_graphql(
        self,
        db: InfrahubDatabase,
        fields: dict | None = None,
        related_node_ids: set | None = None,
        filter_sensitive: bool = False,
        permissions: dict | None = None,
        include_properties: bool = True,
    ) -> dict:
        response = await super().to_graphql(
            db,
            fields=fields,
            related_node_ids=related_node_ids,
            filter_sensitive=filter_sensitive,
            permissions=permissions,
            include_properties=include_properties,
        )

        if fields:
            if "identifier" in fields:
                decision = PermissionDecisionFlag(value=self.decision.value.value)  # type: ignore[attr-defined]
                response["identifier"] = {"value": f"global:{self.action.value}:{decision.name.lower()}"}  # type: ignore[attr-defined,union-attr]

        return response


class CoreObjectPermission(Node):
    async def to_graphql(
        self,
        db: InfrahubDatabase,
        fields: dict | None = None,
        related_node_ids: set | None = None,
        filter_sensitive: bool = False,
        permissions: dict | None = None,
        include_properties: bool = True,
    ) -> dict:
        response = await super().to_graphql(
            db,
            fields=fields,
            related_node_ids=related_node_ids,
            filter_sensitive=filter_sensitive,
            permissions=permissions,
            include_properties=include_properties,
        )

        if fields:
            if "identifier" in fields:
                decision = PermissionDecisionFlag(value=self.decision.value.value)  # type: ignore[attr-defined]
                response["identifier"] = {
                    "value": f"object:{self.namespace.value}:{self.name.value}:{self.action.value.value}:{decision.name.lower()}"  # type: ignore[attr-defined,union-attr]
                }

        return response
