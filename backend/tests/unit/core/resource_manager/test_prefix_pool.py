import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.node.resource_manager import CorePrefixPool
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase


async def test_get_next(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]
    net141 = ip_dataset_prefix_v4["net141"]

    prefix_pool_schema = registry.schema.get_node_schema(name="CorePrefixPool", branch=default_branch)

    pool = await CorePrefixPool.init(schema=prefix_pool_schema, db=db)
    await pool.new(db=db, name="pool1", resources=[net140, net141], ip_namespace=ns1)
    await pool.save(db=db)

    assert pool

    next_subnet = await pool.get_next(db=db, size=17)
    assert str(next_subnet) == "10.10.128.0/17"

    next_prefix = await pool.get_resource(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix

    next_prefix2 = await pool.get_resource(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix.id == next_prefix2.id


async def test_get_one(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]
    net141 = ip_dataset_prefix_v4["net141"]

    prefix_pool_schema = registry.schema.get_node_schema(name="CorePrefixPool", branch=default_branch)

    pool = await CorePrefixPool.init(schema=prefix_pool_schema, db=db)
    await pool.new(db=db, name="pool1", resources=[net140, net141], ip_namespace=ns1)
    await pool.save(db=db)

    assert pool

    next_prefix = await pool.get_resource(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix

    next_prefix2 = await pool.get_resource(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix.id == next_prefix2.id

    next_prefix3 = await pool.get_resource(
        db=db, size=24, prefix_type="IpamIPPrefix", member_type="address", identifier="item2", branch=default_branch
    )
    assert next_prefix3.member_type.value == "address"

    with pytest.raises(ValueError):
        await pool.get_resource(db=db, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch)

    with pytest.raises(ValueError):
        await pool.get_resource(db=db, size=17, member_type="prefix", branch=default_branch)


async def test_get_all_resources(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]
    net141 = ip_dataset_prefix_v4["net141"]

    prefix_pool_schema = registry.schema.get_node_schema(name="CorePrefixPool", branch=default_branch)

    pool = await CorePrefixPool.init(schema=prefix_pool_schema, db=db)
    await pool.new(db=db, name="pool1", resources=[net140, net141], ip_namespace=ns1)
    await pool.save(db=db)

    assert pool

    prefix1 = await pool.get_resource(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
    )
    prefix2 = await pool.get_resource(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
    )
    prefix3 = await pool.get_resource(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
    )
    with pytest.raises(IndexError):
        await pool.get_resource(db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch)

    prefix4 = await pool.get_resource(
        db=db, size=24, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
    )
    prefix5 = await pool.get_resource(
        db=db, size=24, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
    )

    all_prefixes = [
        prefix1.prefix.value,
        prefix2.prefix.value,
        prefix3.prefix.value,
        prefix4.prefix.value,
        prefix5.prefix.value,
    ]
    assert sorted(all_prefixes) == ["10.10.0.0/24", "10.10.128.0/17", "10.10.4.0/24", "10.11.0.0/17", "10.11.128.0/17"]
