from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Any

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.ipam.resource_allocator import IPAMResourceAllocator
from infrahub.core.query.resource_manager import (
    IPAddressPoolGetReserved,
    IPAddressPoolSetReserved,
)
from infrahub.exceptions import PoolExhaustedError, ValidationError

from .. import Node
from ..lock_utils import RESOURCE_POOL_LOCK_NAMESPACE
from .kind_validation import validate_allocated_kind
from .reservation import validate_reserved_kind, validate_reserved_prefix_length

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.ipam.constants import IPAddressType
    from infrahub.core.timestamp import Timestamp
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
        peer_kind: str | None = None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> Node:
        data = data or {}
        pool_name = str(self.get_attribute("name").value)

        # Only the caller's explicit choice is validated against the peer, never the pool's
        # own default: see validate_allocated_kind. Resolved before the reservation lookup
        # so an existing reservation can be checked against it too.
        requested_address_type = address_type or data.get("address_type")

        # Deliberately outside the pool lock: this check needs nothing but the pool's name and
        # the requested kind, so a request that can never succeed must not queue behind the
        # allocations of every other caller of this pool.
        validate_allocated_kind(
            db=db,
            branch=branch,
            pool_kind="IPAddressPool",
            pool_name=pool_name,
            requested_kind=requested_address_type,
            peer_kind=peer_kind,
        )

        async with lock.registry.get(name=self.get_id(), namespace=RESOURCE_POOL_LOCK_NAMESPACE):
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
                        validate_reserved_prefix_length(
                            pool_kind="IPAddressPool",
                            pool_name=pool_name,
                            reserved_value=node.get_attribute("address").value,
                            prefixlen=prefixlen,
                            data=data,
                        )
                        validate_reserved_kind(
                            pool_kind="IPAddressPool",
                            pool_name=pool_name,
                            reserved_value=node.get_attribute("address").value,
                            reserved_kind=node.get_kind(),
                            requested_kind=requested_address_type,
                        )
                        # The reservation may have been created under a peer more permissive than
                        # this caller's — the standalone mutation validates against the broad
                        # BuiltinIPAddress generic, a relationship against its own narrower peer.
                        # Relationship.set_peer performs no kind check, so without this the
                        # reserved node would be attached to a peer that cannot hold it.
                        validate_allocated_kind(
                            db=db,
                            branch=branch,
                            pool_kind="IPAddressPool",
                            pool_name=pool_name,
                            requested_kind=node.get_kind(),
                            peer_kind=peer_kind,
                        )
                        return node

            address_type = requested_address_type or self.default_address_type.value  # type: ignore[attr-defined]
            if not address_type:
                raise ValueError(
                    f"IPAddressPool: {self.name.value} | "  # type: ignore[attr-defined]
                    "An address_type or a default_value type must be provided to allocate a new IP address"
                )

            ip_namespace = await self.ip_namespace.get_peer(db=db)  # type: ignore[attr-defined]

            prefixlen = prefixlen or data.get("prefixlen") or self.default_prefix_length.value  # type: ignore[attr-defined]

            next_address = await self.get_next(db=db, prefixlen=prefixlen)

            target_schema = registry.get_node_schema(name=address_type, branch=branch)
            node = await Node.init(db=db, schema=target_schema, branch=branch, at=at)
            try:
                await node.new(db=db, address=str(next_address), ip_namespace=ip_namespace, **data)
            except ValidationError as exc:
                raise ValueError(f"IPAddressPool: {self.name.value} | {exc!s}") from exc  # type: ignore[attr-defined]
            await node.save(db=db, at=at, user_id=user_id)
            reconciler = IpamReconciler(db=db, branch=branch)
            await reconciler.reconcile(ip_value=next_address, namespace=ip_namespace.id, node_uuid=node.get_id())

            if identifier:
                query_set = await IPAddressPoolSetReserved.init(
                    db=db, pool_id=self.id, identifier=identifier, address_id=node.id, at=at
                )
                await query_set.execute(db=db)

            return node

    async def get_next(self, db: InfrahubDatabase, prefixlen: int | None = None) -> IPAddressType:
        resources = await self.resources.get_peers(db=db)  # type: ignore[attr-defined]
        ip_namespace = await self.ip_namespace.get_peer(db=db)  # type: ignore[attr-defined]
        allocator = IPAMResourceAllocator(db=db, namespace=ip_namespace, branch=self._branch, branch_agnostic=True)

        try:
            weighted_resources = sorted(resources.values(), key=lambda r: r.allocation_weight.value or 0, reverse=True)
        except AttributeError:
            weighted_resources = list(resources.values())

        for resource in weighted_resources:
            ip_prefix = ipaddress.ip_network(resource.prefix.value)  # type: ignore[attr-defined]
            prefix_length = prefixlen or ip_prefix.prefixlen

            if not ip_prefix.prefixlen <= prefix_length <= ip_prefix.max_prefixlen:
                raise ValidationError(input_value="Invalid prefix length for current selected prefix")

            next_address = await allocator.get_next_address(
                ip_prefix=ip_prefix,
                is_pool=resource.is_pool.value,  # type: ignore[attr-defined]
            )

            if next_address:
                return ipaddress.ip_interface(f"{next_address.ip}/{prefix_length}")

        raise PoolExhaustedError("There are no more addresses available in this pool.")
