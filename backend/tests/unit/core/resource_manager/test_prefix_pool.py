import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.resource_manager import CorePrefixPool
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def ip_dataset_01(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)

    # -----------------------
    # Namespace NS1
    # -----------------------

    ns1 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns1.new(db=db, name="ns1")
    await ns1.save(db=db)

    net146 = await Node.init(db=db, schema=prefix_schema)
    await net146.new(db=db, prefix="10.0.0.0/8", ip_namespace=ns1)
    await net146.save(db=db)

    net140 = await Node.init(db=db, schema=prefix_schema)
    await net140.new(db=db, prefix="10.10.0.0/16", ip_namespace=ns1, parent=net146)
    await net140.save(db=db)

    net141 = await Node.init(db=db, schema=prefix_schema)
    await net141.new(db=db, prefix="10.11.0.0/16", ip_namespace=ns1, parent=net146)
    await net141.save(db=db)

    net142 = await Node.init(db=db, schema=prefix_schema)
    await net142.new(db=db, prefix="10.10.1.0/24", parent=net140, ip_namespace=ns1)
    await net142.save(db=db)

    net143 = await Node.init(db=db, schema=prefix_schema)
    await net143.new(db=db, prefix="10.10.1.0/27", parent=net142, ip_namespace=ns1)
    await net143.save(db=db)

    net144 = await Node.init(db=db, schema=prefix_schema)
    await net144.new(db=db, prefix="10.10.2.0/24", parent=net140, ip_namespace=ns1)
    await net144.save(db=db)

    net145 = await Node.init(db=db, schema=prefix_schema)
    await net145.new(db=db, prefix="10.10.3.0/27", parent=net140, ip_namespace=ns1)
    await net145.save(db=db)

    data = {
        "ns1": ns1,
        # "ns2": ns2,
        # "net161": net161,
        # "net162": net162,
        "net140": net140,
        "net141": net141,
        "net142": net142,
        "net143": net143,
        "net144": net144,
        "net145": net145,
        "net146": net146,
        # "address10": address10,
        # "address11": address11,
        # "net240": net240,
        # "net241": net241,
        # "net242": net242,
    }
    return data


async def test_get_next(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_01,
):
    ns1 = ip_dataset_01["ns1"]
    net140 = ip_dataset_01["net140"]
    net141 = ip_dataset_01["net141"]

    prefix_pool_schema = registry.schema.get_node_schema(name="CorePrefixPool", branch=default_branch)

    pool = await CorePrefixPool.init(schema=prefix_pool_schema, db=db)
    await pool.new(db=db, name="pool1", resources=[net140, net141], ip_namespace=ns1)
    await pool.save(db=db)

    assert pool

    next_subnet = await pool.get_next(db=db, size=17)
    assert str(next_subnet) == "10.10.128.0/17"

    next_prefix = await pool.get_one(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix

    next_prefix2 = await pool.get_one(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix.id == next_prefix2.id


async def test_get_one(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_01,
):
    ns1 = ip_dataset_01["ns1"]
    net140 = ip_dataset_01["net140"]
    net141 = ip_dataset_01["net141"]

    prefix_pool_schema = registry.schema.get_node_schema(name="CorePrefixPool", branch=default_branch)

    pool = await CorePrefixPool.init(schema=prefix_pool_schema, db=db)
    await pool.new(db=db, name="pool1", resources=[net140, net141], ip_namespace=ns1)
    await pool.save(db=db)

    assert pool

    next_prefix = await pool.get_one(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix

    next_prefix2 = await pool.get_one(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=default_branch
    )
    assert next_prefix.id == next_prefix2.id

    next_prefix3 = await pool.get_one(
        db=db, size=24, prefix_type="IpamIPPrefix", member_type="address", identifier="item2", branch=default_branch
    )
    assert next_prefix3.member_type.value == "address"

    with pytest.raises(ValueError):
        await pool.get_one(db=db, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch)

    with pytest.raises(ValueError):
        await pool.get_one(db=db, size=17, member_type="prefix", branch=default_branch)


async def test_get_all_resources(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_01,
):
    ns1 = ip_dataset_01["ns1"]
    net140 = ip_dataset_01["net140"]
    net141 = ip_dataset_01["net141"]

    prefix_pool_schema = registry.schema.get_node_schema(name="CorePrefixPool", branch=default_branch)

    pool = await CorePrefixPool.init(schema=prefix_pool_schema, db=db)
    await pool.new(db=db, name="pool1", resources=[net140, net141], ip_namespace=ns1)
    await pool.save(db=db)

    assert pool

    prefix1 = await pool.get_one(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
    )
    prefix2 = await pool.get_one(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
    )
    prefix3 = await pool.get_one(
        db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
    )
    with pytest.raises(IndexError):
        await pool.get_one(db=db, size=17, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch)

    prefix4 = await pool.get_one(
        db=db, size=24, prefix_type="IpamIPPrefix", member_type="prefix", branch=default_branch
    )
    prefix5 = await pool.get_one(
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
