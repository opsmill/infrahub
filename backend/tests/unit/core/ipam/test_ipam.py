import ipaddress

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.ipam import (
    IPPrefixContainerFetch,
    IPPrefixSubnetFetch,
    IPPrefixUtilization,
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
    default_ipnamespace: Node,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)

    container = await Node.init(db=db, schema=prefix_schema)
    await container.new(db=db, prefix="2001:db8::/32", ip_namespace=default_ipnamespace)
    await container.save(db=db)

    prefix = await Node.init(db=db, schema=prefix_schema)
    await prefix.new(db=db, prefix="2001:db8::/48", parent=container, ip_namespace=default_ipnamespace)
    await prefix.save(db=db)

    unrelated = await Node.init(db=db, schema=prefix_schema)
    await unrelated.new(db=db, prefix="192.0.2.0/24", ip_namespace=default_ipnamespace)
    await unrelated.save(db=db)

    container_ip_network = ipaddress.ip_network(container.prefix.value)
    prefix_ip_network = ipaddress.ip_network(prefix.prefix.value)

    prefix_container = await get_container(db=db, branch=default_branch, ip_prefix=container_ip_network)
    assert prefix_container is None

    prefix_container = await get_container(db=db, branch=default_branch, ip_prefix=prefix_ip_network)
    assert prefix_container
    assert prefix_container.prefix == ipaddress.ip_network(container_ip_network)


@pytest.mark.parametrize(
    "input,response",
    [
        (ipaddress.ip_network("10.10.0.0/22"), ["10.10.1.0/24", "10.10.2.0/24", "10.10.3.0/27"]),
        (ipaddress.ip_network("2001:db8::/32"), ["2001:db8::/48"]),
    ],
)
async def test_ipprefix_subnets(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01, input, response):
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixSubnetFetch.init(db=db, branch=default_branch, obj=input, namespace=ns1_id)
    await query.execute(db=db)
    subnets = query.get_subnets()

    assert sorted([str(subnet.prefix) for subnet in subnets]) == response


async def test_ipprefix_subnets_small_dataset(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)

    ns1 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns1.new(db=db, name="ns1")
    await ns1.save(db=db)

    net161 = await Node.init(db=db, schema=prefix_schema)
    await net161.new(db=db, prefix="2001:db8::/48", ip_namespace=ns1)
    await net161.save(db=db)

    query = await IPPrefixSubnetFetch.init(
        db=db, branch=default_branch, obj=ipaddress.ip_network("2001:db8::/32"), namespace=ns1.id
    )
    await query.execute(db=db)
    subnets = query.get_subnets()

    assert sorted([str(subnet.prefix) for subnet in subnets]) == ["2001:db8::/48"]


@pytest.mark.parametrize(
    "input,response",
    [
        (ipaddress.ip_network("10.10.0.0/22"), "10.10.0.0/16"),
        (ipaddress.ip_network("10.10.1.0/28"), "10.10.1.0/27"),
        (ipaddress.ip_interface("10.10.1.10/27"), "10.10.1.0/27"),
    ],
)
async def test_ipprefix_container(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01, input, response):
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixContainerFetch.init(db=db, branch=default_branch, obj=input, namespace=ns1_id)

    await query.execute(db=db)
    container = query.get_container()
    assert container is not None
    assert str(container.prefix) == response


async def test_ipaddress_is_within_ipprefix(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    prefix = await Node.init(db=db, schema=prefix_schema)
    await prefix.new(db=db, prefix="2001:db8::/64", ip_namespace=default_ipnamespace)
    await prefix.save(db=db)

    address = await Node.init(db=db, schema=address_schema)
    await address.new(db=db, address="2001:db8::1/64", ip_prefix=prefix, ip_namespace=default_ipnamespace)
    await address.save(db=db)

    unrelated = await Node.init(db=db, schema=address_schema)
    await unrelated.new(db=db, address="192.0.2.1/32", ip_namespace=default_ipnamespace)
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

    prefix2 = await Node.init(db=db, schema=prefix_schema)
    await prefix2.new(db=db, prefix="192.0.2.128/28", member_type="prefix", parent=container)
    await prefix2.save(db=db)

    addresses = []
    for i in range(1, 8):
        address = await Node.init(db=db, schema=address_schema)
        await address.new(db=db, address=f"192.0.2.{i}/28", ip_prefix=prefix)
        await address.save(db=db)
        addresses.append(address)

    query = await IPPrefixUtilization.init(db, branch=default_branch, ip_prefix=container)
    await query.execute(db)
    assert query.get_prefix_use_percentage() == 100 / 8
    assert await get_utilization(db=db, branch=default_branch, ip_prefix=container) == 100 / 8

    query = await IPPrefixUtilization.init(db, branch=default_branch, ip_prefix=prefix2)
    await query.execute(db)
    assert query.get_prefix_use_percentage() == 0
    assert await get_utilization(db=db, branch=default_branch, ip_prefix=prefix2) == 0

    query = await IPPrefixUtilization.init(db, branch=default_branch, ip_prefix=prefix)
    await query.execute(db)
    assert query.get_address_use_percentage() == 50.0
    assert await get_utilization(db=db, branch=default_branch, ip_prefix=prefix) == 50.0


async def test_query_by_parent_ids(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    reconciler = IpamReconciler(db=db, branch=default_branch)
    ns1 = ip_dataset_01["ns1"]
    net146 = ip_dataset_01["net146"]
    nodes = await NodeManager.query(
        db=db, branch=default_branch, schema="IpamIPPrefix", filters={"parent__ids": [net146.id]}
    )
    assert len(nodes) == 1
    assert nodes[0].id == ip_dataset_01["net140"].id

    net150 = await Node.init(db=db, schema=prefix_schema)
    await net150.new(db=db, prefix="10.10.0.0/15", ip_namespace=ns1, parent=net146)
    await net150.save(db=db)
    await reconciler.reconcile(ip_value=ipaddress.ip_network(net150.prefix.value), namespace=ns1)

    nodes = await NodeManager.query(
        db=db, branch=default_branch, schema="IpamIPPrefix", filters={"parent__ids": [net146.id]}
    )
    assert len(nodes) == 1
    assert nodes[0].id == net150.id
    nodes = await NodeManager.query(
        db=db, branch=default_branch, schema="IpamIPPrefix", filters={"parent__ids": [net150.id]}
    )
    assert len(nodes) == 1
    assert nodes[0].id == ip_dataset_01["net140"].id
