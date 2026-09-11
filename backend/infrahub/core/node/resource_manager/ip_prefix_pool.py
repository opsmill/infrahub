from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Any

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.ipam.resource_allocator import IPAMResourceAllocator
from infrahub.core.query.resource_manager import (
    PrefixPoolGetReserved,
    PrefixPoolSetReserved,
)
from infrahub.exceptions import ValidationError

from .. import Node
from ..lock_utils import RESOURCE_POOL_LOCK_NAMESPACE
from .kind_validation import validate_allocated_kind
from .reservation import validate_reserved_kind, validate_reserved_prefix_length

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.ipam.constants import IPNetworkType
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class CoreIPPrefixPool(Node):
    async def get_resource(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        identifier: str | None = None,
        data: dict[str, Any] | None = None,
        prefixlen: int | None = None,
        size: int | None = None,
        member_type: str | None = None,
        prefix_type: str | None = None,
        peer_kind: str | None = None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> Node:
        # TODO(IFC-2945): drop this alias once the public `size` input field is renamed to `prefixlen`.
        if prefixlen is None:
            prefixlen = size
        data = data or {}
        pool_name = str(self.get_attribute("name").value)

        # Validated before anything is allocated, and only for the caller's explicit choice —
        # never the pool's own default: see validate_allocated_kind. Resolved before the
        # reservation lookup so an existing reservation can be checked against it too.
        requested_prefix_type = prefix_type or data.get("prefix_type", None)

        # Deliberately outside the pool lock: this check needs nothing but the pool's name and
        # the requested kind, so a request that can never succeed must not queue behind the
        # allocations of every other caller of this pool.
        validate_allocated_kind(
            db=db,
            branch=branch,
            pool_kind="IPPrefixPool",
            pool_name=pool_name,
            requested_kind=requested_prefix_type,
            peer_kind=peer_kind,
        )

        async with lock.registry.get(name=self.get_id(), namespace=RESOURCE_POOL_LOCK_NAMESPACE):
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
                        validate_reserved_prefix_length(
                            pool_kind="IPPrefixPool",
                            pool_name=pool_name,
                            reserved_value=node.get_attribute("prefix").value,
                            prefixlen=prefixlen,
                            data=data,
                        )
                        validate_reserved_kind(
                            pool_kind="IPPrefixPool",
                            pool_name=pool_name,
                            reserved_value=node.get_attribute("prefix").value,
                            reserved_kind=node.get_kind(),
                            requested_kind=requested_prefix_type,
                        )
                        # The reservation may have been created under a peer more permissive than
                        # this caller's — the standalone mutation validates against the broad
                        # BuiltinIPPrefix generic, a relationship against its own narrower peer.
                        # Relationship.set_peer performs no kind check, so without this the
                        # reserved node would be attached to a peer that cannot hold it.
                        validate_allocated_kind(
                            db=db,
                            branch=branch,
                            pool_kind="IPPrefixPool",
                            pool_name=pool_name,
                            requested_kind=node.get_kind(),
                            peer_kind=peer_kind,
                        )
                        return node

            ip_namespace = await self.ip_namespace.get_peer(db=db)  # type: ignore[attr-defined]

            prefixlen = prefixlen or data.get("prefixlen", None) or self.default_prefix_length.value  # type: ignore[attr-defined]
            if not prefixlen:
                raise ValueError(
                    f"IPPrefixPool: {self.name.value} | "  # type: ignore[attr-defined]
                    "A prefixlen or a default_value must be provided to allocate a new prefix"
                )

            next_prefix = await self.get_next(db=db, prefixlen=prefixlen)

            prefix_type = requested_prefix_type or self.default_prefix_type.value  # type: ignore[attr-defined]
            if not prefix_type:
                raise ValueError(
                    f"IPPrefixPool: {self.name.value} | "  # type: ignore[attr-defined]
                    "A prefix_type or a default_value type must be provided to allocate a new prefix"
                )

            member_type = member_type or data.get("member_type", None) or self.default_member_type.value.value  # type: ignore[attr-defined]
            data["member_type"] = member_type

            target_schema = registry.get_node_schema(name=prefix_type, branch=branch)
            node = await Node.init(db=db, schema=target_schema, branch=branch, at=at)
            try:
                await node.new(db=db, prefix=str(next_prefix), ip_namespace=ip_namespace, **data)
            except ValidationError as exc:
                raise ValueError(f"IPPrefixPool: {self.name.value} | {exc!s}") from exc  # type: ignore[attr-defined]
            await node.save(db=db, at=at, user_id=user_id)
            reconciler = IpamReconciler(db=db, branch=branch)
            await reconciler.reconcile(ip_value=next_prefix, namespace=ip_namespace.id, node_uuid=node.get_id())

            if identifier:
                query_set = await PrefixPoolSetReserved.init(
                    db=db, pool_id=self.id, identifier=identifier, prefix_id=node.id, at=at
                )
                await query_set.execute(db=db)

            return node

    async def get_next(self, db: InfrahubDatabase, prefixlen: int) -> IPNetworkType:
        resources = await self.resources.get_peers(db=db)  # type: ignore[attr-defined]
        ip_namespace = await self.ip_namespace.get_peer(db=db)  # type: ignore[attr-defined]
        allocator = IPAMResourceAllocator(db=db, namespace=ip_namespace, branch=self._branch, branch_agnostic=True)

        try:
            weighted_resources = sorted(resources.values(), key=lambda r: r.allocation_weight.value or 0, reverse=True)
        except AttributeError:
            weighted_resources = list(resources.values())

        for resource in weighted_resources:
            resource_prefix = ipaddress.ip_network(resource.prefix.value)  # type: ignore[attr-defined]
            next_available = await allocator.get_next_prefix(
                ip_prefix=resource_prefix, target_prefix_length=prefixlen, parent_uuid=resource.id
            )
            if next_available:
                return next_available

        raise IndexError("No more resources available")
