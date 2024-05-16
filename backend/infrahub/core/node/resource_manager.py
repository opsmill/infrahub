from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Any, Optional

from infrahub.core import registry
from infrahub.core.ipam.size import get_prefix_space
from infrahub.core.ipam.utilization import PrefixUtilizationGetter
from infrahub.core.query.ipam import IPPrefixUtilization, get_ip_addresses, get_subnets
from infrahub.core.query.resource_manager import (
    IPAddressPoolGetReserved,
    IPAddressPoolSetReserved,
    PrefixPoolGetReserved,
    PrefixPoolSetReserved,
)
from infrahub.exceptions import PoolExhaustedError, ValidationError
from infrahub.pools.address import get_available
from infrahub.pools.prefix import PrefixPool

# from infrahub.core.query.ipam import get_utilization_percentage
from . import Node

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.ipam.constants import IPAddressType, IPNetworkType
    from infrahub.database import InfrahubDatabase


class CoreIPAddressPool(Node):
    async def get_resource(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        identifier: Optional[str] = None,
        address_type: Optional[str] = None,
        prefixlen: Optional[int] = None,
        data: Optional[dict[str, Any]] = None,
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

        prefixlen = prefixlen or data.get("prefixlen") or self.default_prefix_size.value  # type: ignore[attr-defined]

        next_prefix = await self.get_next(db=db, size=prefixlen)

        target_schema = registry.get_node_schema(name=address_type, branch=branch)
        node = await Node.init(db=db, schema=target_schema, branch=branch)
        await node.new(db=db, address=str(next_prefix), ip_namespace=ip_namespace, **data)
        await node.save(db=db)

        if identifier:
            query_set = await IPAddressPoolSetReserved.init(
                db=db, pool_id=self.id, identifier=identifier, address_id=node.id
            )
            await query_set.execute(db=db)

        return node

    async def get_next(self, db: InfrahubDatabase, size: Optional[int] = None) -> IPAddressType:
        # Measure utilization of all prefixes identified as resources
        resources = await self.resources.get_peers(db=db)  # type: ignore[attr-defined]
        ip_namespace = await self.ip_namespace.get_peer(db=db)  # type: ignore[attr-defined]

        for resource in resources.values():
            ip_prefix = ipaddress.ip_network(resource.prefix.value)  # type: ignore[attr-defined]
            prefix_length = size or ip_prefix.prefixlen

            if not ip_prefix.prefixlen <= prefix_length <= ip_prefix.max_prefixlen:
                raise ValidationError(input_value="Invalid prefix length for current selected prefix")

            addresses = await get_ip_addresses(
                db=db,
                ip_prefix=ip_prefix,
                namespace=ip_namespace,
                branch=self._branch,
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

                # utilization = await get_utilization_percentage(self, db, branch=self._branch)
                response["utilization"] = {"value": 99}

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

        special_fields = {"total_member_count", "all_used_member_count", "branch_used_member_count", "utilization"}
        if fields and special_fields & set(fields):
            ip_prefixes = await self.resources.get_peers(db=db)  # type: ignore[attr-defined]
            getter = PrefixUtilizationGetter(db=db, ip_prefixes=ip_prefixes)

            # TODO: how to handle mixed address and prefix member_type prefixes?

            if "total_member_count" in fields:
                total_member_count = 0
                for ip_prefix in ip_prefixes:
                    total_member_count += get_prefix_space(ip_prefix=ip_prefix)
                response["total_member_count"] = {"value": total_member_count}
            if "all_used_member_count" in fields:
                all_used_member_count = 0
                for ip_prefix in ip_prefixes:
                    prefix_used_members = await getter.get_children(ip_prefix=ip_prefix)
                    all_used_member_count += len(prefix_used_members)
                response["all_used_member_count"] = {"value": all_used_member_count}
            if "branch_used_member_count" in fields:
                branch_used_member_count = 0
                for ip_prefix in ip_prefixes:
                    prefix_branch_used_members = await getter.get_children(ip_prefix=ip_prefix, branch_name=self._branch.name)
                    branch_used_member_count += len(prefix_branch_used_members)
                response["branch_used_member_count"] = {"value": branch_used_member_count}
            if "utilization" in fields:
                # TODO: aggregate utilization for all IP prefixes 
                response["utilization"] = {"value": 99}

        return response
