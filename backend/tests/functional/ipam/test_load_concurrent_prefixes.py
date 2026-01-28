from __future__ import annotations

import ipaddress
from ipaddress import IPv4Network
from typing import TYPE_CHECKING

from tests.functional.ipam.base import TestIpam
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import SchemaRoot
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


# See https://github.com/opsmill/infrahub/issues/4523
class TestLoadConcurrentPrefixes(TestIpam):
    async def test_load_concurrent_prefixes(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        default_ipnamespace: Node,
        register_ipam_schema: SchemaBranch,
    ) -> None:
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
                # Without locking mechanism server side, parent might not be present
                assert n.parent.peer.prefix.value == network_8

    async def test_too_many_relationships(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        default_ipnamespace: Node,
        prefix_with_rel_in_hfid_schema: SchemaRoot,
    ) -> None:
        await load_schema(db=db, schema=prefix_with_rel_in_hfid_schema)

        prefixes = [IPv4Network("10.0.0.0/8"), IPv4Network("10.0.0.0/16"), IPv4Network("10.1.0.0/16")]

        for prefix_val in prefixes:
            prefix = await client.create("InfraPrefix", prefix=f"{prefix_val}")
            await prefix.save()

        results = await client.all("InfraPrefix")
        prefixes_results = [prefix.prefix.value for prefix in results]
        assert prefixes_results == prefixes
