import ipaddress
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, InfrahubKind
from infrahub.core.ipam import get_ip_addresses, get_subnets
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def register_ipam_schema(db: InfrahubDatabase, default_branch: Branch, data_schema: None) -> None:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "IPPrefix",
                "namespace": "Ipam",
                "default_filter": "prefix__value",
                "order_by": ["prefix__value"],
                "display_labels": ["prefix__value"],
                "branch": BranchSupportType.AWARE.value,
                "inherit_from": [InfrahubKind.IPPREFIX],
            },
            {
                "name": "IPAddress",
                "namespace": "Ipam",
                "default_filter": "address__value",
                "order_by": ["address__value"],
                "display_labels": ["address__value"],
                "branch": BranchSupportType.AWARE.value,
                "inherit_from": [InfrahubKind.IPADDRESS],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


async def test_validate_prefix_create(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, register_ipam_schema: None
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)

    prefix1 = await Node.init(db=db, schema=prefix_schema)
    await prefix1.new(db=db, prefix="2001:db8::/32")
    await prefix1.save(db=db)

    prefix2 = await Node.init(db=db, schema=prefix_schema)
    await prefix2.new(db=db, prefix="192.0.2.0/24")
    await prefix2.save(db=db)


async def test_validate_address_create(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, register_ipam_schema: None
):
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    address1 = await Node.init(db=db, schema=address_schema)
    await address1.new(db=db, address="2001:db8::/64")
    await address1.save(db=db)

    address2 = await Node.init(db=db, schema=address_schema)
    await address2.new(db=db, address="192.0.2.0/24")
    await address2.save(db=db)


async def test_validate_prefix_within_prefix(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, register_ipam_schema: None
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

    subnets = await get_subnets(db=db, branch=default_branch, ip_prefix=prefix)
    assert len(subnets) == 1
    assert subnets[0] == ipaddress.ip_network("2001:db8::/48")


async def test_validate_address_within_prefix(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, register_ipam_schema: None
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

    ip_addresses = await get_ip_addresses(db=db, branch=default_branch, ip_prefix=prefix)
    assert len(ip_addresses) == 1
    assert ip_addresses[0] == ipaddress.ip_interface("2001:db8::1/64")
