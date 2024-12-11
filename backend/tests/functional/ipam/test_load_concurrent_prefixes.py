import ipaddress

from infrahub.database import InfrahubDatabase
from tests.integration.ipam.base import TestIpam


# See https://github.com/opsmill/infrahub/issues/4523
class TestLoadConcurrentPrefixes(TestIpam):
    async def test_load_concurrent_prefixes(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
        default_ipnamespace,
        register_ipam_schema,
    ):
        prefixes_batch = await client.create_batch()
        network_8 = ipaddress.IPv4Network("10.0.0.0/8")
        networks_16 = list(network_8.subnets(new_prefix=16))

        networks = [network_8] + networks_16[0:10]

        for network in networks:
            prefix = await client.create("IpamIPPrefix", prefix=f"{network}")
            prefixes_batch.add(task=prefix.save, node=prefix, allow_upsert=True)

        async for _, _ in prefixes_batch.execute():
            pass

        nodes = await client.all("IpamIPPrefix", prefetch_relationships=True, populate_store=True)
        for n in nodes:
            if n.prefix.value != network_8:
                assert n.parent.peer.prefix.value == network_8
