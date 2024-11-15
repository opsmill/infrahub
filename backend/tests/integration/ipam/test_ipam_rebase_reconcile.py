from __future__ import annotations

from typing import TYPE_CHECKING

from graphql import graphql

from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql.initialization import prepare_graphql_params

from .base import TestIpamReconcileBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase

CREATE_IPPREFIX = """
mutation CreatePrefix($prefix: String!, $namespace_id: String!) {
    IpamIPPrefixCreate(
        data: {
            prefix: {
                value: $prefix
            }
            ip_namespace: {
                id: $namespace_id
            }
        }
    ) {
        ok
        object {
            id
        }
    }
}
"""

CREATE_IPADDRESS = """
mutation CreateAddress($address: String!, $namespace_id: String!) {
    IpamIPAddressCreate(
        data: {
            address: {
                value: $address
            }
            ip_namespace: {
                id: $namespace_id
            }
        }
    ) {
        ok
        object {
            id
        }
    }
}
"""


class TestIpamRebaseReconcile(TestIpamReconcileBase):
    async def test_step01_add_address(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        client: InfrahubClient,
    ) -> None:
        branch = await create_branch(db=db, branch_name="new_address")
        address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=branch)

        new_address = await Node.init(schema=address_schema, db=db, branch=branch)
        await new_address.new(db=db, address="10.10.0.2", ip_namespace=initial_dataset["ns1"].id)
        await new_address.save(db=db)

        success = await client.branch.rebase(branch_name=branch.name)
        assert success is True

        updated_address = await NodeManager.get_one(db=db, branch=branch.name, id=new_address.id)
        parent_rels = await updated_address.ip_prefix.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(parent_rels) == 1
        assert parent_rels[0].peer_id == initial_dataset["net140"].id

    async def test_step02_add_delete_prefix(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        client: InfrahubClient,
    ) -> None:
        branch = await create_branch(db=db, branch_name="delete_prefix")

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=registry.default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_IPPREFIX,
            context_value=gql_params.context,
            variable_values={"prefix": "10.0.0.0/7", "namespace_id": initial_dataset["ns1"].id},
        )
        assert not result.errors
        assert result.data
        assert result.data["IpamIPPrefixCreate"]
        assert result.data["IpamIPPrefixCreate"]["ok"]
        assert result.data["IpamIPPrefixCreate"]["object"]["id"]
        new_prefix_id = result.data["IpamIPPrefixCreate"]["object"]["id"]

        deleted_prefix_branch = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["net140"].id)
        assert deleted_prefix_branch
        await deleted_prefix_branch.delete(db=db)

        success = await client.branch.rebase(branch_name=branch.name)
        assert success is True

        deleted_prefix = await NodeManager.get_one(db=db, branch=branch.name, id=deleted_prefix_branch.id)
        assert deleted_prefix is None
        new_prefix_branch = await NodeManager.get_one(db=db, branch=branch.name, id=new_prefix_id)
        assert new_prefix_branch.is_top_level.value is True
        parent_rels = await new_prefix_branch.parent.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(parent_rels) == 0
        children_rels = await new_prefix_branch.children.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(children_rels) == 1
        assert {child.peer_id for child in children_rels} == {initial_dataset["net146"].id}
        address_rels = await new_prefix_branch.ip_addresses.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(address_rels) == 0

        net_146_prefix_branch = await NodeManager.get_one(db=db, branch=branch.name, id=initial_dataset["net146"].id)
        assert net_146_prefix_branch.is_top_level.value is False
        parent_rels = await net_146_prefix_branch.parent.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(parent_rels) == 1
        assert parent_rels[0].peer_id == new_prefix_id
        children_rels = await net_146_prefix_branch.children.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(children_rels) == 3
        assert {child.peer_id for child in children_rels} == {
            initial_dataset["net142"].id,
            initial_dataset["net144"].id,
            initial_dataset["net145"].id,
        }
        address_rels = await net_146_prefix_branch.ip_addresses.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(address_rels) == 1
        assert address_rels[0].peer_id == initial_dataset["address10"].id

    async def test_step03_interlinked_prefixes_and_addresses(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        client: InfrahubClient,
    ) -> None:
        branch = await create_branch(db=db, branch_name="interlinked")

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=registry.default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_IPPREFIX,
            context_value=gql_params.context,
            variable_values={"prefix": "10.0.0.0/7", "namespace_id": initial_dataset["ns1"].id},
        )
        assert not result.errors
        assert result.data
        assert result.data["IpamIPPrefixCreate"]
        assert result.data["IpamIPPrefixCreate"]["ok"]
        assert result.data["IpamIPPrefixCreate"]["object"]["id"]
        net_10_0_0_0_7_id = result.data["IpamIPPrefixCreate"]["object"]["id"]

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_IPPREFIX,
            context_value=gql_params.context,
            variable_values={
                "prefix": "10.0.0.0/15",
                "namespace_id": initial_dataset["ns1"].id,
            },
        )
        assert not result.errors
        assert result.data
        assert result.data["IpamIPPrefixCreate"]
        assert result.data["IpamIPPrefixCreate"]["ok"]
        assert result.data["IpamIPPrefixCreate"]["object"]["id"]
        net_10_0_0_0_15_id = result.data["IpamIPPrefixCreate"]["object"]["id"]

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=registry.default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_IPPREFIX,
            context_value=gql_params.context,
            variable_values={
                "prefix": "10.10.8.0/22",
                "namespace_id": initial_dataset["ns1"].id,
            },
        )
        assert not result.errors
        assert result.data
        assert result.data["IpamIPPrefixCreate"]
        assert result.data["IpamIPPrefixCreate"]["ok"]
        assert result.data["IpamIPPrefixCreate"]["object"]["id"]
        net_10_10_8_0_22_id = result.data["IpamIPPrefixCreate"]["object"]["id"]

        gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_IPADDRESS,
            context_value=gql_params.context,
            variable_values={
                "address": "10.10.1.2",
                "namespace_id": initial_dataset["ns1"].id,
            },
        )
        assert not result.errors
        assert result.data
        assert result.data["IpamIPAddressCreate"]
        assert result.data["IpamIPAddressCreate"]["ok"]
        assert result.data["IpamIPAddressCreate"]["object"]["id"]
        address_10_10_1_2_id = result.data["IpamIPAddressCreate"]["object"]["id"]

        success = await client.branch.rebase(branch_name=branch.name)
        assert success is True

        # 10.10.0.0/7
        net_10_0_0_0_7_check = await NodeManager.get_one(db=db, branch=branch.name, id=net_10_0_0_0_7_id)
        parent_rels = await net_10_0_0_0_7_check.parent.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(parent_rels) == 0
        child_rels = await net_10_0_0_0_7_check.children.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(child_rels) == 1
        assert child_rels[0].peer_id == initial_dataset["net146"].id
        # 10.10.0.0/8
        net146_branch = await NodeManager.get_one(db=db, branch=branch.name, id=initial_dataset["net146"].id)
        parent_rels = await net146_branch.parent.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(parent_rels) == 1
        assert parent_rels[0].peer_id == net_10_0_0_0_7_id
        child_rels = await net146_branch.children.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(child_rels) == 2
        assert {c.peer_id for c in child_rels} == {net_10_0_0_0_15_id, initial_dataset["net140"].id}
        # 10.10.0.0/15
        net_10_0_0_0_15_check = await NodeManager.get_one(db=db, branch=branch.name, id=net_10_0_0_0_15_id)
        parent_rels = await net_10_0_0_0_15_check.parent.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(parent_rels) == 1
        assert parent_rels[0].peer_id == initial_dataset["net146"].id
        child_rels = await net_10_0_0_0_15_check.children.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(child_rels) == 0
        # 10.10.0.0/16
        net140_branch = await NodeManager.get_one(db=db, branch=branch.name, id=initial_dataset["net140"].id)
        parent_rels = await net140_branch.parent.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(parent_rels) == 1
        assert parent_rels[0].peer_id == initial_dataset["net146"].id
        child_rels = await net140_branch.children.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(child_rels) == 4
        assert {c.peer_id for c in child_rels} == {
            initial_dataset["net142"].id,
            initial_dataset["net144"].id,
            initial_dataset["net145"].id,
            net_10_10_8_0_22_id,
        }
        child_addr_rels = await net140_branch.ip_addresses.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(child_addr_rels) == 1
        assert child_addr_rels[0].peer_id == initial_dataset["address10"].id
        # 10.10.1.1
        address11_branch = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["address11"].id)
        prefix_rels = await address11_branch.ip_prefix.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(prefix_rels) == 1
        assert prefix_rels[0].peer_id == initial_dataset["net143"].id
        # 10.10.1.2
        address_10_10_1_2_branch = await NodeManager.get_one(db=db, branch=branch, id=address_10_10_1_2_id)
        prefix_rels = await address_10_10_1_2_branch.ip_prefix.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(prefix_rels) == 1
        assert prefix_rels[0].peer_id == initial_dataset["net143"].id
