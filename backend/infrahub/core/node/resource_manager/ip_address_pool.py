from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.query.ipam import get_ip_addresses
from infrahub.core.query.resource_manager import (
    IPAddressPoolGetReserved,
    IPAddressPoolSetReserved,
)
from infrahub.exceptions import PoolExhaustedError, ValidationError
from infrahub.pools.address import get_available

from .. import Node

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.ipam.constants import IPAddressType
    from infrahub.database import InfrahubDatabase


class CoreIPAddressPool(Node):
    async def get_resource(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        identifier: str | None = None,
        data: dict[str, Any] | None = None,
        address_type: str | None = None,
        prefixlen: int | None = None,
    ) -> Node:
        # Check if there is already a resource allocated with this identifier
        # if not, pull all existing prefixes and allocated the next available

        if identifier:
            query_get = await IPAddressPoolGetReserved.init(db=db, pool_id=self.id, identifier=identifier)
            await query_get.execute(db=db)
            result = query_get.get_result()

            if result:
                address = result.get_node("address")
                # TODO add support for branch, if the node is reserved with this id in another branch we should return an error
                node = await registry.manager.get_one(db=db, id=address.get("uuid"), branch=branch)

                if node:
                    return node

        data = data or {}

        address_type = address_type or data.get("address_type") or self.default_address_type.value  # type: ignore[attr-defined]
        if not address_type:
            raise ValueError(
                f"IPAddressPool: {self.name.value} | "  # type: ignore[attr-defined]
                "An address_type or a default_value type must be provided to allocate a new IP address"
            )

        ip_namespace = await self.ip_namespace.get_peer(db=db)  # type: ignore[attr-defined]

        prefixlen = prefixlen or data.get("prefixlen") or self.default_prefix_length.value  # type: ignore[attr-defined]

        next_address = await self.get_next(db=db, prefixlen=prefixlen)

        target_schema = registry.get_node_schema(name=address_type, branch=branch)
        node = await Node.init(db=db, schema=target_schema, branch=branch)
        try:
            await node.new(db=db, address=str(next_address), ip_namespace=ip_namespace, **data)
        except ValidationError as exc:
            raise ValueError(f"IPAddressPool: {self.name.value} | {exc!s}") from exc  # type: ignore[attr-defined]
        await node.save(db=db)
        reconciler = IpamReconciler(db=db, branch=branch)
        await reconciler.reconcile(ip_value=next_address, namespace=ip_namespace.id, node_uuid=node.get_id())

        if identifier:
            query_set = await IPAddressPoolSetReserved.init(
                db=db, pool_id=self.id, identifier=identifier, address_id=node.id
            )
            await query_set.execute(db=db)

        return node

    async def get_next(self, db: InfrahubDatabase, prefixlen: int | None = None) -> IPAddressType:
        resources = await self.resources.get_peers(db=db)  # type: ignore[attr-defined]
        ip_namespace = await self.ip_namespace.get_peer(db=db)  # type: ignore[attr-defined]

        try:
            weighted_resources = sorted(resources.values(), key=lambda r: r.allocation_weight.value or 0, reverse=True)
        except AttributeError:
            weighted_resources = list(resources.values())

        for resource in weighted_resources:
            ip_prefix = ipaddress.ip_network(resource.prefix.value)  # type: ignore[attr-defined]
            prefix_length = prefixlen or ip_prefix.prefixlen

            if not ip_prefix.prefixlen <= prefix_length <= ip_prefix.max_prefixlen:
                raise ValidationError(input_value="Invalid prefix length for current selected prefix")

            addresses = await get_ip_addresses(
                db=db, ip_prefix=ip_prefix, namespace=ip_namespace, branch=self._branch, branch_agnostic=True
            )

            available = get_available(
                network=ip_prefix,
                addresses=[ip.address for ip in addresses],
                is_pool=resource.is_pool.value,  # type: ignore[attr-defined]
            )

            if available:
                next_address = available.iter_cidrs()[0]
                return ipaddress.ip_interface(f"{next_address.ip}/{prefix_length}")

        raise PoolExhaustedError("There are no more addresses available in this pool.")
