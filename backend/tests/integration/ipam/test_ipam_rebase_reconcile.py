from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node

from .base import TestIpamReconcileBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase


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
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=branch)

        new_prefix = await Node.init(schema=prefix_schema, db=db, branch=registry.default_branch)
        await new_prefix.new(db=db, prefix="10.10.0.0/17", ip_namespace=initial_dataset["ns1"].id)
        await new_prefix.save(db=db)
        deleted_prefix_branch = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["net140"].id)
        assert deleted_prefix_branch
        await deleted_prefix_branch.delete(db=db)

        success = await client.branch.rebase(branch_name=branch.name)
        assert success is True

        deleted_prefix = await NodeManager.get_one(db=db, branch=branch.name, id=deleted_prefix_branch.id)
        assert deleted_prefix is None
        new_prefix_branch = await NodeManager.get_one(db=db, branch=branch.name, id=new_prefix.id)
        parent_rels = await new_prefix_branch.parent.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(parent_rels) == 1
        assert parent_rels[0].peer_id == initial_dataset["net146"].id
        children_rels = await new_prefix_branch.children.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(children_rels) == 3
        assert {child.peer_id for child in children_rels} == {
            initial_dataset["net142"].id,
            initial_dataset["net144"].id,
            initial_dataset["net145"].id,
        }
        address_rels = await new_prefix_branch.ip_addresses.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(address_rels) == 1
        assert address_rels[0].peer_id == initial_dataset["address10"].id

    async def test_step03_interlinked_prefixes_and_addresses(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        client: InfrahubClient,
    ) -> None:
        branch = await create_branch(db=db, branch_name="interlinked")
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=branch)
        address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=branch)

        net_10_0_0_0_7 = await Node.init(schema=prefix_schema, db=db, branch=branch)
        await net_10_0_0_0_7.new(db=db, prefix="10.0.0.0/7", ip_namespace=initial_dataset["ns1"].id)
        await net_10_0_0_0_7.save(db=db)
        net_10_0_0_0_15 = await Node.init(schema=prefix_schema, db=db, branch=branch)
        await net_10_0_0_0_15.new(
            db=db, prefix="10.0.0.0/15", parent=net_10_0_0_0_7.id, ip_namespace=initial_dataset["ns1"].id
        )
        await net_10_0_0_0_15.save(db=db)
        net_10_10_8_0_22 = await Node.init(schema=prefix_schema, db=db, branch=branch)
        await net_10_10_8_0_22.new(
            db=db, prefix="10.10.8.0/22", parent=net_10_0_0_0_15.id, ip_namespace=initial_dataset["ns1"].id
        )
        await net_10_10_8_0_22.save(db=db)
        address_10_10_1_2 = await Node.init(schema=address_schema, db=db, branch=branch)
        await address_10_10_1_2.new(
            db=db, address="10.10.1.2", ip_prefix=net_10_10_8_0_22.id, ip_namespace=initial_dataset["ns1"].id
        )
        await address_10_10_1_2.save(db=db)
        reconciler = IpamReconciler(db=db, branch=registry.get_branch_from_registry())
        await reconciler.reconcile(
            ip_value=ipaddress.ip_network(initial_dataset["net143"].prefix.value),
            namespace=initial_dataset["ns1"].id,
            node_uuid=initial_dataset["net143"].id,
            is_delete=True,
        )

        success = await client.branch.rebase(branch_name=branch.name)
        assert success is True

        # 10.10.0.0/7
        net_10_0_0_0_7_check = await NodeManager.get_one(db=db, branch=branch.name, id=net_10_0_0_0_7.id)
        parent_rels = await net_10_0_0_0_7_check.parent.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(parent_rels) == 0
        child_rels = await net_10_0_0_0_7_check.children.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(child_rels) == 1
        assert child_rels[0].peer_id == initial_dataset["net146"].id
        # 10.10.0.0/8
        net146_branch = await NodeManager.get_one(db=db, branch=branch.name, id=initial_dataset["net146"].id)
        parent_rels = await net146_branch.parent.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(parent_rels) == 1
        assert parent_rels[0].peer_id == net_10_0_0_0_7.id
        child_rels = await net146_branch.children.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(child_rels) == 2
        assert {c.peer_id for c in child_rels} == {net_10_0_0_0_15.id, initial_dataset["net140"].id}
        # 10.10.0.0/15
        net_10_0_0_0_15_check = await NodeManager.get_one(db=db, branch=branch.name, id=net_10_0_0_0_15.id)
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
        assert len(child_rels) == 3
        assert {c.peer_id for c in child_rels} == {
            initial_dataset["net142"].id,
            initial_dataset["net144"].id,
            initial_dataset["net145"].id,
        }
        child_addr_rels = await net140_branch.ip_addresses.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(child_addr_rels) == 1
        assert child_addr_rels[0].peer_id == initial_dataset["address10"].id
        # 10.10.0.0/17
        net_10_10_0_0_17_branch = (
            await NodeManager.query(
                db=db, branch=branch, schema=prefix_schema, filters={"prefix__value": "10.10.0.0/17"}
            )
        )[0]
        child_rels = await net_10_10_0_0_17_branch.children.get_relationships(db=db)  # type: ignore[attr-defined]
        assert len(child_rels) == 1
        assert child_rels[0].peer_id == net_10_10_8_0_22.id
        # 10.10.1.1
        address11_branch = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["address11"].id)
        prefix_rels = await address11_branch.ip_prefix.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(prefix_rels) == 1
        assert prefix_rels[0].peer_id == initial_dataset["net142"].id
        # 10.10.1.2
        address_10_10_1_2_branch = await NodeManager.get_one(db=db, branch=branch, id=address_10_10_1_2.id)
        prefix_rels = await address_10_10_1_2_branch.ip_prefix.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(prefix_rels) == 1
        assert prefix_rels[0].peer_id == initial_dataset["net142"].id
