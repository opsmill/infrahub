from infrahub_sdk import InfrahubClient

from infrahub.core.constants.infrahubkind import IPPREFIXPOOL, NAMESPACE
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.database import InfrahubDatabase
from tests.helpers.test_app import TestInfrahubApp


class TestDeleteBranchPool(TestInfrahubApp):
    async def test_pool(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch,
        register_core_models_schema,
        register_ipam_schema,
    ) -> None:
        branch2 = await create_branch(branch_name="branch2", db=db)

        ns1 = await Node.init(db=db, schema=NAMESPACE)
        await ns1.new(db=db, name="ns1")
        await ns1.save(db=db)

        net161 = await Node.init(db=db, schema="IpamIPPrefix", branch=branch2)
        await net161.new(db=db, prefix="10.10.0.0/16", ip_namespace=ns1)
        await net161.save(db=db)

        ipv6_prefix_pool = await CoreIPPrefixPool.init(schema=IPPREFIXPOOL, db=db)
        await ipv6_prefix_pool.new(
            db=db,
            name="ipv6_prefix",
            default_prefix_length=24,
            default_prefix_type="IpamIPPrefix",
            resources=[net161],
            ip_namespace=ns1,
        )
        await ipv6_prefix_pool.save(db=db)

        next_prefix = await ipv6_prefix_pool.get_resource(
            db=db, prefixlen=16, prefix_type="IpamIPPrefix", member_type="prefix", identifier="item1", branch=branch2
        )
        assert next_prefix
