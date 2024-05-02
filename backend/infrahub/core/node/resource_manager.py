from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Any, Optional

from infrahub.core import registry
from infrahub.core.query.ipam import get_subnets
from infrahub.core.query.resource_manager import PrefixPoolGetReserved, PrefixPoolSetReserved
from infrahub.pools.prefix import PrefixPool

# from infrahub.core.query.ipam import get_utilization
from . import Node

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.ipam.constants import IPNetworkType
    from infrahub.database import InfrahubDatabase


class CorePrefixGlobalPool(Node):
    async def get_resource(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        pool_identifier: str,
        **kwargs: dict[str, Any],
    ) -> Node:
        prefix_pool_schema = registry.schema.get(name="CorePrefixPool", branch=branch, duplicate=False)
        pools = await registry.manager.query(
            db=db,
            schema=prefix_pool_schema,
            filters={"global_pool__id": self.id, "global_identifier__value": pool_identifier},
        )

        if not pools:
            raise ValueError(f"Unable to identifier a valid CorePrefixPool based on {pool_identifier}")

        for pool in pools:
            try:
                return await pool.get_resource(db=db, branch=branch, **kwargs)  # type: ignore[attr-defined]
            except IndexError:
                continue

        raise IndexError("No more resources available in the global pool")

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

        if fields:
            if "utilization" in fields:
                # utilization = await get_utilization(self, db, branch=self._branch)
                response["utilization"] = {"value": 11}

        return response


class CorePrefixPool(Node):
    async def get_resource(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        identifier: Optional[str] = None,
        size: Optional[int] = None,
        member_type: Optional[str] = None,
        prefix_type: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> Node:
        # Check if there is already a resource allocated with this identifier
        # if not, pull all existing prefixes and allocated the next available
        if identifier:
            query_get = await PrefixPoolGetReserved.init(db=db, pool_id=self.id, identifier=identifier)
            await query_get.execute(db=db)
            result = query_get.get_result()
            if result:
                prefix = result.get_node("prefix")
                # TODO add support for branch, if the node is reserved with this id in another branch we should return an error
                node = await registry.manager.get_one(db=db, id=prefix.get("uuid"), branch=branch)
                if node:
                    return node

        ip_namespace = await self.ip_namespace.get_peer(db=db)  # type: ignore[attr-defined]

        data = data or {}

        size = size or data.get("size", None) or self.default_prefix_size.value  # type: ignore[attr-defined]
        if not size:
            raise ValueError(
                f"PrefixPool: {self.name.value} | "  # type: ignore[attr-defined]
                "A size or a default_value must be provided to allocate a new prefix"
            )

        next_prefix = await self.get_next(db=db, size=size)

        prefix_type = prefix_type or data.get("prefix_type", None) or self.default_prefix_type.value  # type: ignore[attr-defined]
        if not prefix_type:
            raise ValueError(
                f"PrefixPool: {self.name.value} | "  # type: ignore[attr-defined]
                "A prefix_type or a default_value type must be provided to allocate a new prefix"
            )

        member_type = member_type or data.get("member_type", None) or self.default_member_type.value.value  # type: ignore[attr-defined]

        target_schema = registry.get_node_schema(name=prefix_type, branch=branch)
        node = await Node.init(db=db, schema=target_schema, branch=branch)
        await node.new(db=db, prefix=str(next_prefix), member_type=member_type, ip_namespace=ip_namespace, **data)
        await node.save(db=db)

        if identifier:
            query_set = await PrefixPoolSetReserved.init(
                db=db, pool_id=self.id, identifier=identifier, prefix_id=node.id
            )
            await query_set.execute(db=db)

        return node

    async def get_next(self, db: InfrahubDatabase, size: int) -> IPNetworkType:
        # Measure utilization of all prefixes identified as resources
        resources = await self.resources.get_peers(db=db)  # type: ignore[attr-defined]
        ip_namespace = await self.ip_namespace.get_peer(db=db)  # type: ignore[attr-defined]

        for resource in resources.values():
            subnets = await get_subnets(
                db=db,
                ip_prefix=ipaddress.ip_network(resource.prefix.value),  # type: ignore[attr-defined]
                namespace=ip_namespace,
                branch=self._branch,
            )

            pool = PrefixPool(resource.prefix.value)  # type: ignore[attr-defined]
            for subnet in subnets:
                pool.reserve(subnet=str(subnet.prefix))

            try:
                next_available = pool.get(size=size)
                return next_available
            except IndexError:
                continue

        raise IndexError("No more resources available")

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

        if fields:
            if "utilization" in fields:
                # TODO need to build a query to measure the utilization across branches for all resources at once

                # utilization = await get_utilization(self, db, branch=self._branch)
                response["utilization"] = {"value": 99}

        return response
