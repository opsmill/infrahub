from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.initialization import create_branch, create_ipam_namespace, get_default_ipnamespace
from infrahub.core.ipam.utilization import PrefixUtilizationGetter
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

# mypy: disable-error-code="union-attr"


POOL_UTILIZATION_QUERY = """
query GetPool($pool_id: String!) {
  InfrahubResourcePoolUtilization(pool_id: $pool_id) {
    count
    utilization
    utilization_default_branch
    utilization_branches
    edges {
      node {
        display_label
        id
        kind
        utilization
        utilization_default_branch
        utilization_branches
        weight
      }
    }
  }
}"""


PREFIX_UTILIZATION_QUERY = """
query GetPrefixUtilization($prefix_ids: [ID!]) {
  BuiltinIPPrefix(ids: $prefix_ids) {
    edges {
      node {
        utilization { value }
        id
        prefix { value }
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
    ) -> dict[str, Node | list[Node]]:
        await create_ipam_namespace(db=db)
        default_ipnamespace = await get_default_ipnamespace(db=db)
        default_branch = registry.default_branch

        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
        address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)
        prefix_pool_schema = registry.schema.get_node_schema(name="CoreIPPrefixPool", branch=default_branch)
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
    async def step_02_dataset(self, db: InfrahubDatabase, initial_dataset, branch2) -> dict[str, Node | list[Node]]:
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=branch2)
        address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=branch2)
        container = initial_dataset["container"]
        prefix = initial_dataset["prefix"]
        prefix_pool = initial_dataset["prefix_pool"]
        address_pool = initial_dataset["address_pool"]

        container_branch = await Node.init(db=db, branch=branch2, schema=prefix_schema)
        await container_branch.new(db=db, prefix="192.0.4.0/24", member_type="prefix")
        await container_branch.save(db=db)

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

        prefix_pool_updated = await NodeManager.get_one(db=db, id=prefix_pool.id, branch=branch2)
        peers = await prefix_pool_updated.resources.get_peers(db=db)
        await prefix_pool_updated.resources.update(db=db, data=list(peers.values()) + [container_branch])
        await prefix_pool_updated.save(db=db)
        address_pool_updated = await NodeManager.get_one(db=db, id=address_pool.id, branch=branch2)
        peers = await address_pool_updated.resources.get_peers(db=db)
        await address_pool_updated.resources.update(db=db, data=list(peers.values()) + [prefix_branch])
        await address_pool_updated.save(db=db)

        return {
            "container_branch": container_branch,
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

    async def test_step01_graphql_prefix_pool_utilization(
        self, db: InfrahubDatabase, default_branch: Branch, initial_dataset
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
                "utilization_branches": 0,
                "edges": [
                    {
                        "node": {
                            "display_label": await container.render_display_label(db=db),
                            "id": container.id,
                            "kind": "IpamIPPrefix",
                            "utilization": 12.5,
                            "utilization_default_branch": 12.5,
                            "utilization_branches": 0,
                            "weight": 256,
                        }
                    }
                ],
            }
        }

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=PREFIX_UTILIZATION_QUERY,
            context_value=gql_params.context,
            variable_values={"prefix_ids": [container.id]},
        )

        assert not result.errors
        assert result.data
        assert result.data == {
            "BuiltinIPPrefix": {
                "edges": [
                    {
                        "node": {
                            "id": container.id,
                            "utilization": {"value": 12},
                            "prefix": {"value": container.prefix.value},
                        }
                    }
                ],
            }
        }

    async def test_step01_graphql_address_pool_utilization(
        self, db: InfrahubDatabase, default_branch: Branch, initial_dataset
    ):
        prefix = initial_dataset["prefix"]
        address_pool = initial_dataset["address_pool"]
        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=POOL_UTILIZATION_QUERY,
            context_value=gql_params.context,
            variable_values={"pool_id": address_pool.id},
        )

        assert not result.errors
        assert result.data
        assert result.data == {
            "InfrahubResourcePoolUtilization": {
                "count": 1,
                "utilization": 50,
                "utilization_default_branch": 50,
                "utilization_branches": 0,
                "edges": [
                    {
                        "node": {
                            "display_label": await prefix.render_display_label(db=db),
                            "id": prefix.id,
                            "kind": "IpamIPPrefix",
                            "utilization": 50,
                            "utilization_default_branch": 50,
                            "utilization_branches": 0,
                            "weight": 14,
                        }
                    }
                ],
            }
        }
        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=PREFIX_UTILIZATION_QUERY,
            context_value=gql_params.context,
            variable_values={"prefix_ids": [prefix.id]},
        )

        assert not result.errors
        assert result.data
        assert result.data == {
            "BuiltinIPPrefix": {
                "edges": [
                    {
                        "node": {
                            "id": prefix.id,
                            "utilization": {"value": 50},
                            "prefix": {"value": prefix.prefix.value},
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

    async def test_step02_graphql_prefix_pool_branch_utilization(
        self, db: InfrahubDatabase, default_branch: Branch, branch2: Branch, initial_dataset, step_02_dataset
    ):
        container = initial_dataset["container"]
        container_branch = step_02_dataset["container_branch"]
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
        pool_data = result.data["InfrahubResourcePoolUtilization"]
        assert pool_data["count"] == 2
        assert pool_data["utilization"] == 12.5
        assert pool_data["utilization_default_branch"] == 100 / 16
        assert pool_data["utilization_branches"] == 100 / 16
        prefix_details_list = pool_data["edges"]
        assert {
            "node": {
                "display_label": await container.render_display_label(db=db),
                "id": container.id,
                "kind": "IpamIPPrefix",
                "utilization": 25.0,
                "utilization_default_branch": 12.5,
                "utilization_branches": 12.5,
                "weight": 256,
            }
        } in prefix_details_list
        assert {
            "node": {
                "display_label": await container_branch.render_display_label(db=db),
                "id": container_branch.id,
                "kind": "IpamIPPrefix",
                "utilization": 0,
                "utilization_default_branch": 0,
                "utilization_branches": 0,
                "weight": 256,
            }
        } in prefix_details_list

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch2)
        result = await graphql(
            schema=gql_params.schema,
            source=PREFIX_UTILIZATION_QUERY,
            context_value=gql_params.context,
            variable_values={"prefix_ids": [container.id, container_branch.id]},
        )

        assert not result.errors
        assert result.data
        prefix_details_list = result.data["BuiltinIPPrefix"]["edges"]
        assert len(prefix_details_list) == 2
        assert {
            "node": {
                "id": container.id,
                "utilization": {"value": 12},
                "prefix": {"value": container.prefix.value},
            }
        } in prefix_details_list
        assert {
            "node": {
                "id": container_branch.id,
                "utilization": {"value": 0},
                "prefix": {"value": container_branch.prefix.value},
            }
        } in prefix_details_list

    async def test_step02_graphql_address_pool_branch_utilization(
        self, db: InfrahubDatabase, default_branch: Branch, branch2: Branch, initial_dataset, step_02_dataset
    ):
        prefix = initial_dataset["prefix"]
        prefix_branch = step_02_dataset["prefix_branch"]
        address_pool = initial_dataset["address_pool"]
        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=POOL_UTILIZATION_QUERY,
            context_value=gql_params.context,
            variable_values={"pool_id": address_pool.id},
        )

        assert not result.errors
        assert result.data
        pool_data = result.data["InfrahubResourcePoolUtilization"]
        assert pool_data["count"] == 2
        assert pool_data["utilization"] == 100
        assert pool_data["utilization_default_branch"] == 25.0
        assert pool_data["utilization_branches"] == 75.0
        prefix_details_list = pool_data["edges"]
        assert {
            "node": {
                "display_label": await prefix.render_display_label(db=db),
                "id": prefix.id,
                "kind": "IpamIPPrefix",
                "utilization": 100,
                "utilization_default_branch": 50,
                "utilization_branches": 50,
                "weight": 14,
            }
        } in prefix_details_list
        assert {
            "node": {
                "display_label": await prefix_branch.render_display_label(db=db),
                "id": prefix_branch.id,
                "kind": "IpamIPPrefix",
                "utilization": 100,
                "utilization_default_branch": 0,
                "utilization_branches": 100,
                "weight": 14,
            }
        } in prefix_details_list

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch2)
        result = await graphql(
            schema=gql_params.schema,
            source=PREFIX_UTILIZATION_QUERY,
            context_value=gql_params.context,
            variable_values={"prefix_ids": [prefix.id, prefix_branch.id]},
        )

        assert not result.errors
        assert result.data
        prefix_details_list = result.data["BuiltinIPPrefix"]["edges"]
        assert len(prefix_details_list) == 2
        assert {
            "node": {
                "id": prefix.id,
                "utilization": {"value": 50},
                "prefix": {"value": prefix.prefix.value},
            }
        } in prefix_details_list
        assert {
            "node": {
                "id": prefix_branch.id,
                "utilization": {"value": 100},
                "prefix": {"value": prefix_branch.prefix.value},
            }
        } in prefix_details_list

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

    async def test_step03_graphql_prefix_pool_delete_utilization(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        branch2: Branch,
        initial_dataset,
        step_02_dataset,
        step_03_dataset,
    ):
        container = initial_dataset["container"]
        container_branch = step_02_dataset["container_branch"]
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
        pool_data = result.data["InfrahubResourcePoolUtilization"]
        assert pool_data["count"] == 2
        assert pool_data["utilization"] == 100 / 16
        assert pool_data["utilization_default_branch"] == 100 / 32
        assert pool_data["utilization_branches"] == 100 / 32
        prefix_details_list = pool_data["edges"]
        assert {
            "node": {
                "display_label": await container.render_display_label(db=db),
                "id": container.id,
                "kind": "IpamIPPrefix",
                "utilization": 12.5,
                "utilization_default_branch": 100 / 16,
                "utilization_branches": 100 / 16,
                "weight": 256,
            }
        } in prefix_details_list
        assert {
            "node": {
                "display_label": await container_branch.render_display_label(db=db),
                "id": container_branch.id,
                "kind": "IpamIPPrefix",
                "utilization": 0,
                "utilization_default_branch": 0,
                "utilization_branches": 0,
                "weight": 256,
            }
        } in prefix_details_list

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch2)
        result = await graphql(
            schema=gql_params.schema,
            source=PREFIX_UTILIZATION_QUERY,
            context_value=gql_params.context,
            variable_values={"prefix_ids": [container.id, container_branch.id]},
        )

        assert not result.errors
        assert result.data
        prefix_details_list = result.data["BuiltinIPPrefix"]["edges"]
        assert len(prefix_details_list) == 2
        assert {
            "node": {
                "id": container.id,
                "utilization": {"value": 6},
                "prefix": {"value": container.prefix.value},
            }
        } in prefix_details_list
        assert {
            "node": {
                "id": container_branch.id,
                "utilization": {"value": 0},
                "prefix": {"value": container_branch.prefix.value},
            }
        } in prefix_details_list

    async def test_step03_graphql_address_pool_delete_utilization(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        branch2: Branch,
        initial_dataset,
        step_02_dataset,
        step_03_dataset,
    ):
        prefix = initial_dataset["prefix"]
        prefix_branch = step_02_dataset["prefix_branch"]
        address_pool = initial_dataset["address_pool"]
        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=POOL_UTILIZATION_QUERY,
            context_value=gql_params.context,
            variable_values={"pool_id": address_pool.id},
        )

        assert not result.errors
        assert result.data
        pool_data = result.data["InfrahubResourcePoolUtilization"]
        assert pool_data["count"] == 2
        assert pool_data["utilization"] == (25 / 28) * 100
        assert pool_data["utilization_default_branch"] == (6 / 28) * 100
        assert pool_data["utilization_branches"] == (19 / 28) * 100
        prefix_details_list = pool_data["edges"]
        assert {
            "node": {
                "display_label": await prefix.render_display_label(db=db),
                "id": prefix.id,
                "kind": "IpamIPPrefix",
                "utilization": (12 / 14) * 100,
                "utilization_default_branch": (6 / 14) * 100,
                "utilization_branches": (6 / 14) * 100,
                "weight": 14,
            }
        } in prefix_details_list
        assert {
            "node": {
                "display_label": await prefix_branch.render_display_label(db=db),
                "id": prefix_branch.id,
                "kind": "IpamIPPrefix",
                "utilization": (13 / 14) * 100,
                "utilization_default_branch": 0,
                "utilization_branches": (13 / 14) * 100,
                "weight": 14,
            }
        } in prefix_details_list

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch2)
        result = await graphql(
            schema=gql_params.schema,
            source=PREFIX_UTILIZATION_QUERY,
            context_value=gql_params.context,
            variable_values={"prefix_ids": [prefix.id, prefix_branch.id]},
        )

        assert not result.errors
        assert result.data
        prefix_details_list = result.data["BuiltinIPPrefix"]["edges"]
        assert len(prefix_details_list) == 2
        assert {
            "node": {
                "id": prefix.id,
                "utilization": {"value": int(6 / 14 * 100)},
                "prefix": {"value": prefix.prefix.value},
            }
        } in prefix_details_list
        assert {
            "node": {
                "id": prefix_branch.id,
                "utilization": {"value": int(13 / 14 * 100)},
                "prefix": {"value": prefix_branch.prefix.value},
            }
        } in prefix_details_list
