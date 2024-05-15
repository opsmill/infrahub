import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.resource_manager import CoreIPAddressPool
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PoolExhaustedError


async def test_get_next(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net145 = ip_dataset_prefix_v4["net145"]

    adress_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)

    pool = await CoreIPAddressPool.init(schema=adress_pool_schema, db=db)
    await pool.new(db=db, name="pool1", resources=[net145], ip_namespace=ns1, default_address_type="IpamIPAddress")
    await pool.save(db=db)

    assert pool

    next_address = await pool.get_next(db=db, size=30)
    assert str(next_address) == "10.10.3.2/30"

    next_prefix = await pool.get_resource(
        db=db, address_type="IpamIPAddress", identifier="item1", branch=default_branch
    )
    assert next_prefix

    next_prefix2 = await pool.get_resource(
        db=db, address_type="IpamIPAddress", identifier="item1", branch=default_branch
    )
    assert next_prefix.id == next_prefix2.id


async def test_get_next_full(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net147 = ip_dataset_prefix_v4["net147"]

    adress_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)

    pool = await CoreIPAddressPool.init(schema=adress_pool_schema, db=db)
    await pool.new(db=db, name="pool2", resources=[net147], ip_namespace=ns1, default_address_type="IpamIPAddress")
    await pool.save(db=db)

    assert pool

    with pytest.raises(PoolExhaustedError, match="There are no more addresses available in this pool"):
        await pool.get_next(db=db, size=30)
