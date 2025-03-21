from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Any

from netaddr import IPSet

from infrahub.core import registry
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.query.ipam import get_subnets
from infrahub.core.query.resource_manager import (
    PrefixPoolGetReserved,
    PrefixPoolSetReserved,
)
from infrahub.exceptions import ValidationError
from infrahub.pools.prefix import get_next_available_prefix

from .. import Node

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.ipam.constants import IPNetworkType
    from infrahub.database import InfrahubDatabase


class CoreIPPrefixPool(Node):
    async def get_resource(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        identifier: str | None = None,
        data: dict[str, Any] | None = None,
        prefixlen: int | None = None,
        member_type: str | None = None,
        prefix_type: str | None = None,
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

        prefixlen = prefixlen or data.get("prefixlen", None) or self.default_prefix_length.value  # type: ignore[attr-defined]
        if not prefixlen:
            raise ValueError(
                f"IPPrefixPool: {self.name.value} | "  # type: ignore[attr-defined]
                "A prefixlen or a default_value must be provided to allocate a new prefix"
            )

        next_prefix = await self.get_next(db=db, prefixlen=prefixlen)

        prefix_type = prefix_type or data.get("prefix_type", None) or self.default_prefix_type.value  # type: ignore[attr-defined]
        if not prefix_type:
            raise ValueError(
                f"IPPrefixPool: {self.name.value} | "  # type: ignore[attr-defined]
                "A prefix_type or a default_value type must be provided to allocate a new prefix"
            )

        member_type = member_type or data.get("member_type", None) or self.default_member_type.value.value  # type: ignore[attr-defined]

        target_schema = registry.get_node_schema(name=prefix_type, branch=branch)
        node = await Node.init(db=db, schema=target_schema, branch=branch)
        try:
            await node.new(db=db, prefix=str(next_prefix), member_type=member_type, ip_namespace=ip_namespace, **data)
        except ValidationError as exc:
            raise ValueError(f"IPPrefixPool: {self.name.value} | {exc!s}") from exc  # type: ignore[attr-defined]
        await node.save(db=db)
        reconciler = IpamReconciler(db=db, branch=branch)
        await reconciler.reconcile(ip_value=next_prefix, namespace=ip_namespace.id, node_uuid=node.get_id())

        if identifier:
            query_set = await PrefixPoolSetReserved.init(
                db=db, pool_id=self.id, identifier=identifier, prefix_id=node.id
            )
            await query_set.execute(db=db)

        return node

    async def get_next(self, db: InfrahubDatabase, prefixlen: int) -> IPNetworkType:
        # Measure utilization of all prefixes identified as resources
        resources = await self.resources.get_peers(db=db)  # type: ignore[attr-defined]
        ip_namespace = await self.ip_namespace.get_peer(db=db)  # type: ignore[attr-defined]

        for resource in resources.values():
            subnets = await get_subnets(
                db=db,
                ip_prefix=ipaddress.ip_network(resource.prefix.value),  # type: ignore[attr-defined]
                namespace=ip_namespace,
                branch=self._branch,
                branch_agnostic=True,
            )

            pool = IPSet([resource.prefix.value])
            for subnet in subnets:
                pool.remove(addr=str(subnet.prefix))

            try:
                prefix_ver = ipaddress.ip_network(resource.prefix.value).version
                next_available = get_next_available_prefix(pool=pool, prefix_length=prefixlen, prefix_ver=prefix_ver)
                return next_available
            except ValueError:
                continue

        raise IndexError("No more resources available")
