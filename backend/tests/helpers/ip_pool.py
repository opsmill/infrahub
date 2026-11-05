"""Build IP prefix and IP address pools, and the namespaces and resources they allocate from, for component tests."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from itertools import islice
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

POOL_NAME = "ip-pool"
NAMESPACE_NAME = "pool-ns"
PREFIX_KIND = "IpamIPPrefix"
ADDRESS_KIND = "IpamIPAddress"


@dataclass(frozen=True)
class IPPoolCase:
    """A prefix pool or an address pool over one resource, and the values it allocates from that resource."""

    name: str
    pool_kind: str
    allocated_kind: str
    attribute_name: str
    resource: str
    other_resource: str
    """A resource of the same size outside `resource`, for a pool with two resources."""
    prefixlen: int | None
    """The length of each prefix a prefix pool allocates; an address pool allocates addresses, so it has none."""

    async def allocate(self, db: InfrahubDatabase, pool: Node, branch: Branch) -> Node:
        if self.prefixlen is not None:
            assert isinstance(pool, CoreIPPrefixPool)
            return await pool.get_resource(
                db=db, branch=branch, prefixlen=self.prefixlen, prefix_type=PREFIX_KIND, member_type="address"
            )
        assert isinstance(pool, CoreIPAddressPool)
        return await pool.get_resource(db=db, branch=branch)

    async def next_value(self, db: InfrahubDatabase, pool: Node, branch: Branch) -> str:
        if self.prefixlen is not None:
            assert isinstance(pool, CoreIPPrefixPool)
            return str(await pool.get_next(db=db, prefixlen=self.prefixlen, branch=branch))
        assert isinstance(pool, CoreIPAddressPool)
        return str(await pool.get_next(db=db, branch=branch))

    def value_of(self, node: Node) -> str:
        return str(node.get_attribute(self.attribute_name).value)

    def values(self, count: int) -> list[str]:
        """The first `count` values of `resource`, lowest first, in the form the pool stores them."""
        network = ipaddress.ip_network(self.resource)
        if self.prefixlen is not None:
            return [str(subnet) for subnet in islice(network.subnets(new_prefix=self.prefixlen), count)]
        return [f"{network.network_address + index + 1}/{network.prefixlen}" for index in range(count)]

    async def create_held_node(
        self, db: InfrahubDatabase, namespace: Node, value: str, branch: Branch | None = None
    ) -> Node:
        """A prefix or address of the kind the pool allocates, holding `value` in `namespace`."""
        node = await Node.init(db=db, schema=self.allocated_kind, branch=branch)
        fields: dict[str, Any] = {"ip_namespace": namespace, self.attribute_name: value}
        await node.new(db=db, **fields)
        await node.save(db=db)
        return node

    async def allocated_values_on(self, db: InfrahubDatabase, branch: Branch) -> list[str]:
        """The values `branch` holds for the allocated kind, without the resource itself, sorted."""
        nodes = await NodeManager.query(db=db, schema=self.allocated_kind, branch=branch)
        return sorted(value for node in nodes if (value := self.value_of(node)) != self.resource)


PREFIX_POOL_IPV4 = IPPoolCase(
    name="prefix-ipv4",
    pool_kind=InfrahubKind.IPPREFIXPOOL,
    allocated_kind=PREFIX_KIND,
    attribute_name="prefix",
    resource="10.20.0.0/16",
    other_resource="10.21.0.0/16",
    prefixlen=24,
)
PREFIX_POOL_IPV6 = IPPoolCase(
    name="prefix-ipv6",
    pool_kind=InfrahubKind.IPPREFIXPOOL,
    allocated_kind=PREFIX_KIND,
    attribute_name="prefix",
    resource="2001:db8:20::/48",
    other_resource="2001:db8:21::/48",
    prefixlen=64,
)
ADDRESS_POOL_IPV4 = IPPoolCase(
    name="address-ipv4",
    pool_kind=InfrahubKind.IPADDRESSPOOL,
    allocated_kind=ADDRESS_KIND,
    attribute_name="address",
    resource="10.30.0.0/29",
    other_resource="10.31.0.0/29",
    prefixlen=None,
)
ADDRESS_POOL_IPV6 = IPPoolCase(
    name="address-ipv6",
    pool_kind=InfrahubKind.IPADDRESSPOOL,
    allocated_kind=ADDRESS_KIND,
    attribute_name="address",
    resource="2001:db8:30::/125",
    other_resource="2001:db8:31::/125",
    prefixlen=None,
)
IP_POOL_CASES = [PREFIX_POOL_IPV4, PREFIX_POOL_IPV6, ADDRESS_POOL_IPV4, ADDRESS_POOL_IPV6]


async def create_namespace(db: InfrahubDatabase, name: str = NAMESPACE_NAME, branch: Branch | None = None) -> Node:
    namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE, branch=branch)
    await namespace.new(db=db, name=name)
    await namespace.save(db=db)
    return namespace


async def create_prefix(
    db: InfrahubDatabase,
    namespace: Node,
    value: str,
    branch: Branch | None = None,
    allocation_weight: int | None = None,
) -> Node:
    prefix = await Node.init(db=db, schema=PREFIX_KIND, branch=branch)
    await prefix.new(db=db, prefix=value, ip_namespace=namespace, allocation_weight=allocation_weight)
    await prefix.save(db=db)
    return prefix


async def create_pool(
    db: InfrahubDatabase, case: IPPoolCase, namespace: Node, resources: list[Node], branch: Branch | None = None
) -> Node:
    """A pool of the case's kind named `POOL_NAME`; an address pool allocates `IpamIPAddress` nodes."""
    pool: CoreIPPrefixPool | CoreIPAddressPool
    if case.pool_kind == InfrahubKind.IPADDRESSPOOL:
        pool = await CoreIPAddressPool.init(db=db, schema=case.pool_kind, branch=branch)
        await pool.new(
            db=db, name=POOL_NAME, resources=resources, ip_namespace=namespace, default_address_type=ADDRESS_KIND
        )
    else:
        pool = await CoreIPPrefixPool.init(db=db, schema=case.pool_kind, branch=branch)
        await pool.new(db=db, name=POOL_NAME, resources=resources, ip_namespace=namespace)
    await pool.save(db=db)
    return pool


async def pool_on(db: InfrahubDatabase, pool: Node, branch: Branch) -> Node:
    return await NodeManager.get_one(db=db, id=pool.id, branch=branch, raise_on_error=True)


async def delete_on(db: InfrahubDatabase, node: Node, branch: Branch) -> None:
    node_on_branch = await NodeManager.get_one(db=db, id=node.id, branch=branch, raise_on_error=True)
    await node_on_branch.delete(db=db)


async def set_value_on(db: InfrahubDatabase, node: Node, branch: Branch, attribute_name: str, value: str) -> None:
    node_on_branch = await NodeManager.get_one(db=db, id=node.id, branch=branch, raise_on_error=True)
    node_on_branch.get_attribute(attribute_name).value = value
    await node_on_branch.save(db=db)
