from __future__ import annotations

from typing import TYPE_CHECKING, Union

import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.initialization import create_branch, create_ipam_namespace, get_default_ipnamespace
from infrahub.core.ipam.utilization import PrefixUtilizationGetter
from infrahub.core.node import Node
from infrahub.graphql import prepare_graphql_params
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


POOL_UTILIZATION_QUERY = """
query GetPool($pool_id: String!) {
  InfrahubResourcePoolUtilization(pool_id: $pool_id) {
    count
    utilization
    utilization_default_branch
    edges {
      node {
        display_label
        id
        kind
        utilization
        utilization_default_branch
        weight
      }
    }
  }
}"""


class TestIpamUtilization(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        register_ipam_schema,
    ) -> dict[str, Union[Node, list[Node]]]:
        await create_ipam_namespace(db=db)
        default_ipnamespace = await get_default_ipnamespace(db=db)
        default_branch = registry.default_branch

        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
        address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)
        prefix_pool_schema = registry.schema.get_node_schema(name="CorePrefixPool", branch=default_branch)
        address_pool_schema = registry.schema.get_node_schema(name="CoreIPAddressPool", branch=default_branch)

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

        prefix_pool = await Node.init(db=db, schema=prefix_pool_schema)
        await prefix_pool.new(db=db, name="prefix_pool", ip_namespace=default_ipnamespace, resources=[container])
        await prefix_pool.save(db=db)
        address_pool = await Node.init(db=db, schema=address_pool_schema)
        await address_pool.new(
            db=db,
            name="address_pool",
            default_address_type="IpamIPAddress",
            ip_namespace=default_ipnamespace,
            resources=[prefix],
        )
        await address_pool.save(db=db)

        return {
            "container": container,
            "prefix": prefix,
            "prefix2": prefix2,
            "addresses": addresses,
            "prefix_pool": prefix_pool,
            "address_pool": address_pool,
        }

    @pytest.fixture(scope="class")
    async def branch2(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="branch2")

    @pytest.fixture(scope="class")
    async def step_02_dataset(
        self, db: InfrahubDatabase, initial_dataset, branch2
    ) -> dict[str, Union[Node, list[Node]]]:
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=branch2)
        address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=branch2)
        container = initial_dataset["container"]
        prefix = initial_dataset["prefix"]

        prefix_branch = await Node.init(db=db, branch=branch2, schema=prefix_schema)
        await prefix_branch.new(db=db, prefix="192.0.3.0/28", member_type="address", parent=container)
        await prefix_branch.save(db=db)

        prefix2_branch = await Node.init(db=db, branch=branch2, schema=prefix_schema)
        await prefix2_branch.new(db=db, prefix="192.0.3.128/28", member_type="prefix", parent=container)
        await prefix2_branch.save(db=db)

        branch_addresses = []
        for i in range(1, 15):
            address = await Node.init(db=db, branch=branch2, schema=address_schema)
            await address.new(db=db, address=f"192.0.3.{i}/28", ip_prefix=prefix_branch)
            await address.save(db=db)
            branch_addresses.append(address)

        addresses = []
        for i in range(8, 15):
            address = await Node.init(db=db, branch=branch2, schema=address_schema)
            await address.new(db=db, address=f"192.0.2.{i}/28", ip_prefix=prefix)
            await address.save(db=db)
            addresses.append(address)

        return {
            "prefix_branch": prefix_branch,
            "prefix2_branch": prefix2_branch,
            "addresses": addresses,
            "branch_addresses": branch_addresses,
        }

    @pytest.fixture(scope="class")
    async def step_03_dataset(self, db: InfrahubDatabase, initial_dataset, step_02_dataset) -> None:
        prefix2 = initial_dataset["prefix2"]
        await prefix2.delete(db=db)

        main_addresses = initial_dataset["addresses"]
        await main_addresses[0].delete(db=db)

        prefix2_branch = step_02_dataset["prefix2_branch"]
        await prefix2_branch.delete(db=db)

        step2_addresses = step_02_dataset["addresses"]
        await step2_addresses[0].delete(db=db)
        step2_branch_addresses = step_02_dataset["branch_addresses"]
        await step2_branch_addresses[0].delete(db=db)

    async def test_step01_main_utilization(self, db: InfrahubDatabase, default_branch: Branch, initial_dataset):
        container = initial_dataset["container"]
        prefix = initial_dataset["prefix"]
        prefix2 = initial_dataset["prefix2"]
        getter = PrefixUtilizationGetter(db=db, ip_prefixes=[container, prefix, prefix2])

        assert await getter.get_use_percentage(ip_prefixes=[container]) == 100 / 8
        assert await getter.get_use_percentage(ip_prefixes=[prefix2]) == 0
        assert await getter.get_use_percentage(ip_prefixes=[prefix]) == 50.0

    async def test_step01_graphql_utilization(
        self, db: InfrahubDatabase, client: InfrahubClient, default_branch: Branch, initial_dataset
    ):
        container = initial_dataset["container"]
        prefix_pool = initial_dataset["prefix_pool"]
        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=POOL_UTILIZATION_QUERY,
            context_value=gql_params.context,
            variable_values={"pool_id": prefix_pool.id},
        )

        assert not result.errors
        assert result.data
        assert result.data == {
            "InfrahubResourcePoolUtilization": {
                "count": 1,
                "utilization": 12.5,
                "utilization_default_branch": 12.5,
                "edges": [
                    {
                        "node": {
                            "display_label": await container.render_display_label(db=db),
                            "id": container.id,
                            "kind": "IpamIPPrefix",
                            "utilization": 12.5,
                            "utilization_default_branch": 12.5,
                            "weight": 256,
                        }
                    }
                ],
            }
        }

    async def test_step02_branch_utilization(
        self, db: InfrahubDatabase, default_branch: Branch, branch2: Branch, initial_dataset, step_02_dataset
    ):
        container = initial_dataset["container"]
        prefix = initial_dataset["prefix"]
        prefix_branch = step_02_dataset["prefix_branch"]
        prefix2_branch = step_02_dataset["prefix2_branch"]
        getter = PrefixUtilizationGetter(db=db, ip_prefixes=[container, prefix, prefix_branch, prefix2_branch])

        assert await getter.get_use_percentage(ip_prefixes=[container]) == 25.0
        assert await getter.get_use_percentage(ip_prefixes=[container], branch_names=[branch2.name]) == 12.5
        assert await getter.get_use_percentage(ip_prefixes=[container], branch_names=[default_branch.name]) == 12.5
        assert await getter.get_use_percentage(ip_prefixes=[prefix2_branch]) == 0
        assert await getter.get_use_percentage(ip_prefixes=[prefix2_branch], branch_names=[branch2.name]) == 0
        assert await getter.get_use_percentage(ip_prefixes=[prefix2_branch], branch_names=[default_branch.name]) == 0
        assert await getter.get_use_percentage(ip_prefixes=[prefix_branch]) == 100.0
        assert await getter.get_use_percentage(ip_prefixes=[prefix_branch], branch_names=[branch2.name]) == 100.0
        assert await getter.get_use_percentage(ip_prefixes=[prefix_branch], branch_names=[default_branch.name]) == 0
        assert await getter.get_use_percentage(ip_prefixes=[prefix]) == 100.0
        assert await getter.get_use_percentage(ip_prefixes=[prefix], branch_names=[branch2.name]) == 50.0
        assert await getter.get_use_percentage(ip_prefixes=[prefix], branch_names=[default_branch.name]) == 50.0

    async def test_step03_utilization_with_deletes(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        branch2: Branch,
        initial_dataset,
        step_02_dataset,
        step_03_dataset,
    ):
        container = initial_dataset["container"]
        prefix = initial_dataset["prefix"]
        prefix_branch = step_02_dataset["prefix_branch"]
        getter = PrefixUtilizationGetter(db=db, ip_prefixes=[container, prefix, prefix_branch])

        assert await getter.get_use_percentage(ip_prefixes=[container]) == 12.5
        assert await getter.get_use_percentage(ip_prefixes=[container], branch_names=[branch2.name]) == 100 / 16
        assert await getter.get_use_percentage(ip_prefixes=[container], branch_names=[default_branch.name]) == 100 / 16
        assert await getter.get_use_percentage(ip_prefixes=[prefix_branch]) == (13 / 14) * 100
        assert (
            await getter.get_use_percentage(ip_prefixes=[prefix_branch], branch_names=[branch2.name]) == (13 / 14) * 100
        )
        assert await getter.get_use_percentage(ip_prefixes=[prefix_branch], branch_names=[default_branch.name]) == 0
        assert await getter.get_use_percentage(ip_prefixes=[prefix]) == (12 / 14) * 100
        assert await getter.get_use_percentage(ip_prefixes=[prefix], branch_names=[branch2.name]) == (6 / 14) * 100
        assert (
            await getter.get_use_percentage(ip_prefixes=[prefix], branch_names=[default_branch.name]) == (6 / 14) * 100
        )
