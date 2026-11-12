from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Any

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.ipam.constants import ANY_BRANCH
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.ipam.resource_allocator import IPAMResourceAllocator
from infrahub.core.query.resource_manager import (
    IPAddressPoolGetReserved,
    IPAddressPoolSetReserved,
)
from infrahub.exceptions import PoolExhaustedError, ValidationError

from .. import Node
from ..lock_utils import RESOURCE_POOL_LOCK_NAMESPACE
from .ip_pool_branch import get_namespace_on_branch, get_resources_on_branch
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

        # Only an explicitly requested kind is validated; the pool's own default is left alone.
        requested_address_type = address_type or data.get("address_type")

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
                # A branch reuses the oldest reservation it can read, as a reservation made on
                # another branch, or on a deleted one, points at an address it cannot see
                reserved_ids = [result.get_node("address").get("uuid") for result in query_get.get_results()]
                readable = await registry.manager.get_many(db=db, ids=reserved_ids, branch=branch)
                for reserved_id in reserved_ids:
                    if node := readable.get(reserved_id):
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
                        return node

            address_type = requested_address_type or self.default_address_type.value  # type: ignore[attr-defined]
            if not address_type:
                raise ValueError(
                    f"IPAddressPool: {self.name.value} | "  # type: ignore[attr-defined]
                    "An address_type or a default_value type must be provided to allocate a new IP address"
                )

            ip_namespace = await get_namespace_on_branch(db=db, pool=self, branch=branch)

            prefixlen = prefixlen or data.get("prefixlen") or self.default_prefix_length.value  # type: ignore[attr-defined]

            next_address = await self._get_next_on_branch(
                db=db, prefixlen=prefixlen, branch=branch, ip_namespace=ip_namespace
            )

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

    async def get_next(
        self, db: InfrahubDatabase, prefixlen: int | None = None, branch: Branch | None = None
    ) -> IPAddressType:
        """Return the next free address on `branch`, by default the branch the pool was read on.

        Raises:
            ResourceNotFoundError: When the pool's namespace does not exist on the branch.
            PoolExhaustedError: When no resource exists on the branch, or none has room left.

        """
        branch = branch or self._branch
        ip_namespace = await get_namespace_on_branch(db=db, pool=self, branch=branch)
        return await self._get_next_on_branch(db=db, prefixlen=prefixlen, branch=branch, ip_namespace=ip_namespace)

    async def _get_next_on_branch(
        self, db: InfrahubDatabase, prefixlen: int | None, branch: Branch, ip_namespace: Node
    ) -> IPAddressType:
        resources = await get_resources_on_branch(db=db, pool=self, branch=branch)
        # A value stays taken while any live branch holds it, so free values are searched across branches.
        allocator = IPAMResourceAllocator(db=db)

        for resource in resources:
            ip_prefix = ipaddress.ip_network(resource.prefix.value)  # type: ignore[attr-defined]
            prefix_length = prefixlen or ip_prefix.prefixlen

            if not ip_prefix.prefixlen <= prefix_length <= ip_prefix.max_prefixlen:
                raise ValidationError(input_value="Invalid prefix length for current selected prefix")

            next_address = await allocator.get_next_address(
                ip_prefix=ip_prefix,
                namespace=ip_namespace.get_id(),
                on_branch=ANY_BRANCH,
                is_pool=resource.is_pool.value,  # type: ignore[attr-defined]
            )

            if next_address:
                return ipaddress.ip_interface(f"{next_address.ip}/{prefix_length}")

        raise PoolExhaustedError("There are no more addresses available in this pool.")
