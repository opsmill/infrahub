import ipaddress
from typing import List

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.query.ipam import (
    get_container,
    get_ip_addresses,
    get_ip_prefix_for_ip_address,
    get_subnets,
    get_utilization,
)
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase


async def test_ipprefix_creation(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)

    prefix1 = await Node.init(db=db, schema=prefix_schema)
    await prefix1.new(db=db, prefix="2001:db8::/32")
    await prefix1.save(db=db)

    prefix2 = await Node.init(db=db, schema=prefix_schema)
    await prefix2.new(db=db, prefix="192.0.2.0/24")
    await prefix2.save(db=db)


async def test_ipaddress_creation(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    address1 = await Node.init(db=db, schema=address_schema)
    await address1.new(db=db, address="2001:db8::/64")
    await address1.save(db=db)

    address2 = await Node.init(db=db, schema=address_schema)
    await address2.new(db=db, address="192.0.2.0/24")
    await address2.save(db=db)


async def test_ipprefix_is_within_container(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)

    container = await Node.init(db=db, schema=prefix_schema)
    await container.new(db=db, prefix="2001:db8::/32")
    await container.save(db=db)

    prefix = await Node.init(db=db, schema=prefix_schema)
    await prefix.new(db=db, prefix="2001:db8::/48")
    await prefix.save(db=db)

    unrelated = await Node.init(db=db, schema=prefix_schema)
    await unrelated.new(db=db, prefix="192.0.2.0/24")
    await unrelated.save(db=db)

    container_ip_network = ipaddress.ip_network(container.prefix.value)
    prefix_ip_network = ipaddress.ip_network(prefix.prefix.value)

    prefix_container = await get_container(db=db, branch=default_branch, ip_prefix=container_ip_network)
    assert prefix_container is None

    prefix_container = await get_container(db=db, branch=default_branch, ip_prefix=prefix_ip_network)
    assert prefix_container
    assert prefix_container.prefix == ipaddress.ip_network(container_ip_network)


async def test_ipprefix_subnets(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)

    container = await Node.init(db=db, schema=prefix_schema)
    await container.new(db=db, prefix="2001:db8::/32")
    await container.save(db=db)

    prefix = await Node.init(db=db, schema=prefix_schema)
    await prefix.new(db=db, prefix="2001:db8::/48")
    await prefix.save(db=db)

    unrelated = await Node.init(db=db, schema=prefix_schema)
    await unrelated.new(db=db, prefix="192.0.2.0/24")
    await unrelated.save(db=db)

    container_ip_network = ipaddress.ip_network(container.prefix.value)
    prefix_ip_network = ipaddress.ip_network(prefix.prefix.value)

    subnets = await get_subnets(db=db, branch=default_branch, ip_prefix=container_ip_network)
    assert len(subnets) == 1
    assert subnets[0].prefix == prefix_ip_network

    subnets = await get_subnets(db=db, branch=default_branch, ip_prefix=prefix_ip_network)
    assert len(subnets) == 0


async def test_ipaddress_is_within_ipprefix(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    prefix = await Node.init(db=db, schema=prefix_schema)
    await prefix.new(db=db, prefix="2001:db8::/64")
    await prefix.save(db=db)

    address = await Node.init(db=db, schema=address_schema)
    await address.new(db=db, address="2001:db8::1/64")
    await address.save(db=db)

    unrelated = await Node.init(db=db, schema=address_schema)
    await unrelated.new(db=db, address="192.0.2.1/32")
    await unrelated.save(db=db)

    prefix_ip_network = ipaddress.ip_network(prefix.prefix.value)
    address_ip_address = ipaddress.ip_interface(address.address.value)

    ip_addresses = await get_ip_addresses(db=db, branch=default_branch, ip_prefix=prefix_ip_network)
    assert len(ip_addresses) == 1
    assert ip_addresses[0].address == address_ip_address

    ip_prefix = await get_ip_prefix_for_ip_address(db=db, branch=default_branch, ip_address=address_ip_address)
    assert ip_prefix
    assert ip_prefix.prefix == prefix_ip_network


async def test_ipprefix_utilization(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    container = await Node.init(db=db, schema=prefix_schema)
    await container.new(db=db, prefix="192.0.2.0/24")
    await container.save(db=db)

    prefix = await Node.init(db=db, schema=prefix_schema)
    await prefix.new(db=db, prefix="192.0.2.0/28")
    await prefix.save(db=db)

    # Build relationship between container and prefix
    await container.children.update(db=db, data=prefix)
    await container.children.save(db=db)
    await prefix.parent.update(db=db, data=container)
    await prefix.parent.save(db=db)

    addresses: List[Node] = []
    for i in range(1, 8):
        address = await Node.init(db=db, schema=address_schema)
        await address.new(db=db, address=f"192.0.2.{i}/28")
        await address.ip_prefix.update(db=db, data=prefix)
        await address.save(db=db)
        addresses.append(address)

    # Build relationships between addresses and prefix
    await prefix.ip_addresses.update(db=db, data=addresses)
    await prefix.ip_addresses.save(db=db)

    assert await get_utilization(db=db, branch=default_branch, ip_prefix=container) == 100 / 16
    assert await get_utilization(db=db, branch=default_branch, ip_prefix=prefix) == 50.0
