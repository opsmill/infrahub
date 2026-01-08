import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


async def test_get_next(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_prefix_v4,
) -> None:
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]
    net141 = ip_dataset_prefix_v4["net141"]

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)

    pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db)
    await pool.new(db=db, name="pool1", resources=[net140, net141], ip_namespace=ns1)
    await pool.save(db=db)

    assert pool

    next_subnet = await pool.get_next(db=db, prefixlen=17)
    assert str(next_subnet) == "10.10.128.0/17"

    next_prefix = await pool.get_resource(
        db=db, prefixlen=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix

    next_prefix2 = await pool.get_resource(
        db=db, prefixlen=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix.id == next_prefix2.id


async def test_get_next_weighted(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_prefix_v4,
) -> None:
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]
    net141 = ip_dataset_prefix_v4["net141"]

    net140.allocation_weight.value = 100
    await net140.save(db=db)
    net141.allocation_weight.value = 200
    await net141.save(db=db)

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)

    pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db)
    await pool.new(db=db, name="pool1", resources=[net140, net141], ip_namespace=ns1)
    await pool.save(db=db)

    assert pool

    next_subnet = await pool.get_next(db=db, prefixlen=17)
    assert str(next_subnet) == "10.11.0.0/17"

    next_prefix = await pool.get_resource(
        db=db, prefixlen=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix

    next_prefix2 = await pool.get_resource(
        db=db, prefixlen=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix.id == next_prefix2.id


async def test_get_one(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_prefix_v4,
) -> None:
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]
    net141 = ip_dataset_prefix_v4["net141"]

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)

    pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db)
    await pool.new(db=db, name="pool1", resources=[net140, net141], ip_namespace=ns1)
    await pool.save(db=db)

    assert pool

    next_prefix = await pool.get_resource(
        db=db, prefixlen=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix

    next_prefix2 = await pool.get_resource(
        db=db, prefixlen=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix.id == next_prefix2.id

    next_prefix3 = await pool.get_resource(
        db=db,
        prefixlen=24,
        prefix_type="IpamIPPrefix",
        member_type="address",
        identifier="item2",
        branch=default_branch,
    )
    assert next_prefix3.member_type.value == "address"

    with pytest.raises(ValueError):
        await pool.get_resource(db=db, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch)

    with pytest.raises(ValueError):
        await pool.get_resource(db=db, prefixlen=17, member_type="prefix", branch=default_branch)


async def test_get_all_resources(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_prefix_v4,
) -> None:
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]
    net141 = ip_dataset_prefix_v4["net141"]

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)

    pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db)
    await pool.new(db=db, name="pool1", resources=[net140, net141], ip_namespace=ns1)
    await pool.save(db=db)

    assert pool

    prefix1 = await pool.get_resource(
        db=db, prefixlen=17, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
    )
    prefix2 = await pool.get_resource(
        db=db, prefixlen=17, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
    )
    another_branch = await create_branch(branch_name="another_branch", db=db)
    prefix3 = await pool.get_resource(
        db=db, prefixlen=17, prefix_type="IpamIPPrefix", member_type="prefix", branch=another_branch
    )
    with pytest.raises(IndexError):
        await pool.get_resource(
            db=db, prefixlen=17, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
        )

    prefix4 = await pool.get_resource(
        db=db, prefixlen=24, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
    )
    prefix5 = await pool.get_resource(
        db=db, prefixlen=24, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
    )

    all_prefixes = [
        prefix1.prefix.value,
        prefix2.prefix.value,
        prefix3.prefix.value,
        prefix4.prefix.value,
        prefix5.prefix.value,
    ]
    assert sorted(all_prefixes) == ["10.10.0.0/24", "10.10.128.0/17", "10.10.4.0/24", "10.11.0.0/17", "10.11.128.0/17"]


async def test_ipv6_large_prefix_pool_allocation(
    db: InfrahubDatabase, default_branch: Branch, default_ipnamespace: Node, register_ipam_schema: SchemaBranch
) -> None:
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)

    ns_v6 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns_v6.new(db=db, name="ns_v6_large")
    await ns_v6.save(db=db)

    parent_v6 = await Node.init(db=db, schema=prefix_schema)
    await parent_v6.new(db=db, prefix="2001:db8:abcd::/48", ip_namespace=ns_v6)
    await parent_v6.save(db=db)

    prefixes: list[Node] = []
    for i in range(100):
        existing = await Node.init(db=db, schema=prefix_schema)
        address_offset = i * 2
        await existing.new(db=db, prefix=f"2001:db8:abcd::{address_offset:x}/127", ip_namespace=ns_v6, parent=parent_v6)
        await existing.save(db=db)
        prefixes.append(existing)

    # Create fragmentation by deleting prefixes at positions 10, 50, and 90
    deleted_values = [prefixes[10].prefix.value, prefixes[50].prefix.value, prefixes[90].prefix.value]
    await prefixes[10].delete(db=db)
    await prefixes[50].delete(db=db)
    await prefixes[90].delete(db=db)

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)

    pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db)
    await pool.new(db=db, name="pool_v6_large", resources=[parent_v6], ip_namespace=ns_v6)
    await pool.save(db=db)

    new_prefixes: list[Node] = []
    for i in range(3):
        new_prefix = await pool.get_resource(
            db=db,
            prefixlen=127,
            prefix_type="IpamIPPrefix",
            member_type="prefix",
            identifier=f"v6_large_new_{i}",
            branch=default_branch,
        )
        new_prefixes.append(new_prefix)

    # Verify gaps are reused in order
    assert new_prefixes[0].prefix.value == deleted_values[0]
    assert new_prefixes[1].prefix.value == deleted_values[1]
    assert new_prefixes[2].prefix.value == deleted_values[2]

    next_prefix = await pool.get_resource(
        db=db,
        prefixlen=127,
        prefix_type="IpamIPPrefix",
        member_type="prefix",
        identifier="v6_large_next",
        branch=default_branch,
    )
    assert next_prefix.prefix.value == "2001:db8:abcd::c8/127"
