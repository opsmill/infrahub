import ipaddress

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.query.ipam import (
    IPPrefixUtilization,
    get_container,
    get_ip_addresses,
    get_ip_prefix_for_ip_address,
    get_subnets,
    IPPrefixSubnetFetch,
    get_container,
    get_ip_addresses,
    get_ip_prefix_for_ip_address,
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
    await prefix.new(db=db, prefix="2001:db8::/48", parent=container)
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

    ns1 = await Node.init(db=db, schema="IpamIPNamespace")
    await ns1.new(db=db, name="ns1")
    await ns1.save(db=db)

    ns2 = await Node.init(db=db, schema="IpamIPNamespace")
    await ns2.new(db=db, name="ns2")
    await ns2.save(db=db)

    container = await Node.init(db=db, schema=prefix_schema)
    await container.new(db=db, prefix="2001:db8::/32", ip_namespace=ns1)
    await container.save(db=db)

    prefix = await Node.init(db=db, schema=prefix_schema)
    await prefix.new(db=db, prefix="2001:db8::/48", parent=container, ip_namespace=ns1)
    await prefix.save(db=db)

    net40 = await Node.init(db=db, schema=prefix_schema)
    await net40.new(db=db, prefix="192.0.0.0/16", ip_namespace=ns1)
    await net40.save(db=db)

    net41 = await Node.init(db=db, schema=prefix_schema)
    await net41.new(db=db, prefix="192.0.0.0/22", ip_namespace=ns1)
    await net41.save(db=db)

    net42 = await Node.init(db=db, schema=prefix_schema)
    await net42.new(db=db, prefix="192.0.1.0/24", parent=net40, ip_namespace=ns1)
    await net42.save(db=db)

    net43 = await Node.init(db=db, schema=prefix_schema)
    await net43.new(db=db, prefix="192.0.1.0/27", parent=net42, ip_namespace=ns1)
    await net43.save(db=db)

    net44 = await Node.init(db=db, schema=prefix_schema)
    await net44.new(db=db, prefix="192.0.2.0/24", parent=net40, ip_namespace=ns1)
    await net44.save(db=db)

    net44 = await Node.init(db=db, schema=prefix_schema)
    await net44.new(db=db, prefix="192.0.3.0/27", parent=net40, ip_namespace=ns1)
    await net44.save(db=db)

    container_ip_network = ipaddress.ip_network(net41.prefix.value)

    query = await IPPrefixSubnetFetch.init(
        db=db, branch=default_branch, ip_prefix=container_ip_network, namespace="ns1"
    )
    await query.execute(db=db)

    subnets = query.get_subnets()

    assert subnets


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
    await address.new(db=db, address="2001:db8::1/64", ip_prefix=prefix)
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
    await container.new(db=db, prefix="192.0.2.0/24", member_type="prefix")
    await container.save(db=db)

    prefix = await Node.init(db=db, schema=prefix_schema)
    await prefix.new(db=db, prefix="192.0.2.0/28", member_type="address", parent=container)
    await prefix.save(db=db)

    addresses = []
    for i in range(1, 8):
        address = await Node.init(db=db, schema=address_schema)
        await address.new(db=db, address=f"192.0.2.{i}/28", ip_prefix=prefix)
        await address.save(db=db)
        addresses.append(address)

    query = await IPPrefixUtilization.init(db, branch=default_branch, ip_prefix=container)
    await query.execute(db)
    assert await query.get_percentage() == 100 / 16

    query = await IPPrefixUtilization.init(db, branch=default_branch, ip_prefix=prefix)
    await query.execute(db)
    assert await query.get_percentage() == 50.0
