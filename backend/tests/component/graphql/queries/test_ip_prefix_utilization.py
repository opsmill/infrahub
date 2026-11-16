from collections.abc import Generator
from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.ipam import BuiltinIPPrefix
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

UTILIZATION_ONLY_QUERY = """
query($prefix: String!) {
    IpamIPPrefix(prefix__value: $prefix) {
        edges { node { utilization { value } } }
    }
}
"""

UTILIZATION_WITH_PREFIX_QUERY = """
query($prefix: String!) {
    IpamIPPrefix(prefix__value: $prefix) {
        edges { node { prefix { value } utilization { value } } }
    }
}
"""

UTILIZATION_WITH_PREFIX_AND_IS_POOL_QUERY = """
query($prefix: String!) {
    IpamIPPrefix(prefix__value: $prefix) {
        edges { node { prefix { value } is_pool { value } utilization { value } } }
    }
}
"""

QUERY_PARAMS = [
    pytest.param(UTILIZATION_ONLY_QUERY, id="utilization_only"),
    pytest.param(UTILIZATION_WITH_PREFIX_QUERY, id="with_prefix"),
    pytest.param(UTILIZATION_WITH_PREFIX_AND_IS_POOL_QUERY, id="with_prefix_and_is_pool"),
]


@dataclass
class UsableAddressesTestCase:
    name: str
    prefix: str
    expected_utilization: int


USABLE_ADDRESSES_TEST_CASES: list[UsableAddressesTestCase] = [
    UsableAddressesTestCase(
        name="pool_prefix_counts_network_and_broadcast_addresses",
        prefix="192.0.2.0/29",
        expected_utilization=75,
    ),
    UsableAddressesTestCase(
        name="ipv4_prefix_excludes_network_and_broadcast_addresses",
        prefix="192.0.2.8/29",
        expected_utilization=50,
    ),
    UsableAddressesTestCase(
        name="ipv4_31_counts_both_addresses",
        prefix="192.0.2.16/31",
        expected_utilization=50,
    ),
    UsableAddressesTestCase(
        name="ipv4_32_counts_its_single_address",
        prefix="192.0.2.18/32",
        expected_utilization=100,
    ),
]


class TestIPPrefixUtilization:
    async def _create_prefix(
        self, db: InfrahubDatabase, namespace: Node, prefix: str, is_pool: bool, addresses: list[str]
    ) -> Node:
        prefix_node = await Node.init(db=db, schema="IpamIPPrefix")
        await prefix_node.new(db=db, prefix=prefix, member_type="address", is_pool=is_pool, ip_namespace=namespace)
        await prefix_node.save(db=db)
        for address in addresses:
            address_node = await Node.init(db=db, schema="IpamIPAddress")
            await address_node.new(db=db, address=address, ip_prefix=prefix_node, ip_namespace=namespace)
            await address_node.save(db=db)
        return prefix_node

    @pytest.fixture(scope="class")
    def ip_prefix_node_class(self, default_branch_scope_class: Branch) -> Generator[None, None, None]:
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setitem(registry.node, InfrahubKind.IPPREFIX, BuiltinIPPrefix)
            yield

    @pytest.fixture(scope="class")
    async def ip_prefixes(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
        register_ipam_schema_scope_class: SchemaBranch,
        ip_prefix_node_class: None,
    ) -> None:
        namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await namespace.new(db=db, name="ns-utilization")
        await namespace.save(db=db)

        await self._create_prefix(
            db=db,
            namespace=namespace,
            prefix="192.0.2.0/29",
            is_pool=True,
            addresses=[f"192.0.2.{host}/29" for host in range(6)],
        )
        await self._create_prefix(
            db=db,
            namespace=namespace,
            prefix="192.0.2.8/29",
            is_pool=False,
            addresses=["192.0.2.9/29", "192.0.2.10/29", "192.0.2.11/29"],
        )
        await self._create_prefix(
            db=db, namespace=namespace, prefix="192.0.2.16/31", is_pool=False, addresses=["192.0.2.16/31"]
        )
        await self._create_prefix(
            db=db, namespace=namespace, prefix="192.0.2.18/32", is_pool=False, addresses=["192.0.2.18/32"]
        )

    @pytest.fixture(scope="class")
    async def time_before_pool_prefix_unmarked(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
        register_ipam_schema_scope_class: SchemaBranch,
        ip_prefix_node_class: None,
    ) -> Timestamp:
        namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await namespace.new(db=db, name="ns-utilization-history")
        await namespace.save(db=db)

        prefix_node = await self._create_prefix(
            db=db,
            namespace=namespace,
            prefix="192.0.2.32/29",
            is_pool=True,
            addresses=["192.0.2.33/29", "192.0.2.34/29", "192.0.2.35/29"],
        )
        before_change = Timestamp()
        prefix_node.get_attribute(name="is_pool").value = False
        await prefix_node.save(db=db)
        return before_change

    @pytest.mark.parametrize("query", QUERY_PARAMS)
    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in USABLE_ADDRESSES_TEST_CASES])
    async def test_utilization_counts_usable_addresses_whatever_fields_are_requested(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        ip_prefixes: None,
        test_case: UsableAddressesTestCase,
        query: str,
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"prefix": test_case.prefix},
        )

        assert result.errors is None
        assert result.data
        assert [edge["node"]["utilization"]["value"] for edge in result.data["IpamIPPrefix"]["edges"]] == [
            test_case.expected_utilization
        ]

    @pytest.mark.parametrize("query", QUERY_PARAMS)
    async def test_utilization_at_a_past_time_uses_is_pool_at_that_time(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        time_before_pool_prefix_unmarked: Timestamp,
        query: str,
    ) -> None:
        gql_params = await prepare_graphql_params(
            db=db, branch=default_branch_scope_class, at=time_before_pool_prefix_unmarked
        )

        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"prefix": "192.0.2.32/29"},
        )

        assert result.errors is None
        assert result.data
        assert [edge["node"]["utilization"]["value"] for edge in result.data["IpamIPPrefix"]["edges"]] == [37]
