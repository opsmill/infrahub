from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union

from .. import Node

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class ResourceManagerBase(Node):
    async def get_resource(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        identifier: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> Node:
        raise NotImplementedError()

    async def get_utilization(self, db: InfrahubDatabase, at: Optional[Union[Timestamp, str]] = None) -> float:
        raise NotImplementedError()

    async def get_utilization_default_branch(
        self, db: InfrahubDatabase, at: Optional[Union[Timestamp, str]] = None
    ) -> float:
        raise NotImplementedError()

    async def to_graphql(
        self,
        db: InfrahubDatabase,
        fields: Optional[dict] = None,
        related_node_ids: Optional[set] = None,
        filter_sensitive: bool = False,
    ) -> dict:
        response = await super().to_graphql(
            db, fields=fields, related_node_ids=related_node_ids, filter_sensitive=filter_sensitive
        )
        special_fields_set = {"utilization", "utilization_branches", "utilization_default_branch"}
        if not fields:
            return response
        fields_set = set(fields)
        if not fields_set & special_fields_set:
            return response
        if "utilization" in fields_set:
            response["utilization"] = {"value": await self.get_utilization(db=db)}
        if "utilization_default_branch" in fields_set:
            response["utilization_default_branch"] = {"value": await self.get_utilization_default_branch(db=db)}

        return response
