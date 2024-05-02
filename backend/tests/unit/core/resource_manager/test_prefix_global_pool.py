from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.node.resource_manager import CorePrefixGlobalPool, CorePrefixPool
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase


async def test_get_one(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    init_nodes_registry,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net142 = ip_dataset_prefix_v4["net142"]
    net144 = ip_dataset_prefix_v4["net144"]

    prefix_pool_schema = registry.schema.get_node_schema(name="CorePrefixPool", branch=default_branch)
    global_pool_schema = registry.schema.get_node_schema(name="CorePrefixGlobalPool", branch=default_branch)

    global_pool = await CorePrefixGlobalPool.init(schema=global_pool_schema, db=db)
    await global_pool.new(db=db, name="global_pool")
    await global_pool.save(db=db)

    pool_fr = await CorePrefixPool.init(schema=prefix_pool_schema, db=db)
    await pool_fr.new(
        db=db, name="pool_fr", global_identifier="fr", resources=[net142], ip_namespace=ns1, global_pool=global_pool
    )
    await pool_fr.save(db=db)

    pool_de = await CorePrefixPool.init(schema=prefix_pool_schema, db=db)
    await pool_de.new(
        db=db, name="pool_de", global_identifier="de", resources=[net144], ip_namespace=ns1, global_pool=global_pool
    )
    await pool_de.save(db=db)

    next_prefix = await global_pool.get_resource(
        db=db,
        size=27,
        pool_identifier="de",
        prefix_type="IpamIPPrefix",
        member_type="prefix",
        identifier="item1",
        branch=default_branch,
    )
    assert next_prefix

    next_prefix2 = await global_pool.get_resource(
        db=db,
        size=27,
        pool_identifier="de",
        prefix_type="IpamIPPrefix",
        member_type="prefix",
        identifier="item1",
        branch=default_branch,
    )
    assert next_prefix.id == next_prefix2.id

    next_prefix3 = await global_pool.get_resource(
        db=db,
        size=27,
        pool_identifier="fr",
        prefix_type="IpamIPPrefix",
        member_type="address",
        identifier="item1",
        branch=default_branch,
    )
    assert next_prefix3.id != next_prefix2.id
