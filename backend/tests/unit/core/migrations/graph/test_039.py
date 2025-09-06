from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m039_ipam_reconcile import Migration039
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


@dataclass
class IpPrefixDetails:
    node_uuid: str
    prefix: str
    expected_parent_uuid: str | None
    expected_children_uuids: set[str]


class TestMigration039:
    branch_name = "ip_test_branch"

    @pytest.fixture
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        register_ipam_schema: SchemaBranch,
    ) -> dict[str, Node]:
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
        # address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

        # namespaces
        ns1 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await ns1.new(db=db, name="ns1")
        await ns1.save(db=db)
        ns2 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await ns2.new(db=db, name="ns2")
        await ns2.save(db=db)

        net146 = await Node.init(db=db, schema=prefix_schema)
        await net146.new(db=db, prefix="10.0.0.0/8", ip_namespace=ns1)
        await net146.save(db=db)

        net140 = await Node.init(db=db, schema=prefix_schema)
        await net140.new(db=db, prefix="10.10.0.0/16", ip_namespace=ns1, parent=net146)
        await net140.save(db=db)

        branch = await create_branch(db=db, branch_name=self.branch_name)

        net140_branch = await NodeManager.get_one(db=db, branch=branch, id=net140.id)
        net140_branch.prefix.value = "10.10.0.0/17"
        await net140_branch.parent.update(db=db, data=net140.id)
        await net140_branch.save(db=db)

        return {
            "ns1": ns1,
            "ns2": ns2,
            "net140": net140,
            "net146": net146,
        }

    @pytest.fixture
    async def branch(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name=self.branch_name)

    @pytest.fixture
    async def net140_updated(
        self, db: InfrahubDatabase, initial_dataset: dict[str, Node], branch: Branch
    ) -> IpPrefixDetails:
        net140 = initial_dataset["net140"]
        net146 = initial_dataset["net146"]
        net140_branch = await NodeManager.get_one(db=db, branch=branch, id=net140.id)
        net140_branch.prefix.value = "10.10.0.0/17"
        await net140_branch.parent.update(db=db, data=net140.id)
        await net140_branch.save(db=db)

        return IpPrefixDetails(
            node_uuid=net140_branch.id,
            prefix="10.10.0.0/17",
            expected_parent_uuid=net146.id,
            expected_children_uuids=set(),
        )

    @pytest.fixture
    async def branch_updates(
        self, initial_dataset: dict[str, Node], branch: Branch, net140_updated: IpPrefixDetails
    ) -> list[IpPrefixDetails]:
        return {"net140": net140_updated}

    async def test_migration_039(
        self, db: InfrahubDatabase, initial_dataset, branch: Branch, branch_updates: dict[str, IpPrefixDetails]
    ) -> None:
        branch = await Branch.get_by_name(db=db, name=self.branch_name)

        migration = Migration039()
        await migration.execute(db=db)

        for ip_prefix_details in branch_updates.values():
            reconciled_prefix = await NodeManager.get_one(db=db, branch=branch, id=ip_prefix_details.node_uuid)

            assert reconciled_prefix.prefix.value == ip_prefix_details.prefix

            expected_parent_uuid = ip_prefix_details.expected_parent_uuid
            parent_rels = await reconciled_prefix.parent.get_relationships(db=db)
            assert len(parent_rels) == (1 if expected_parent_uuid else 0)
            if expected_parent_uuid:
                assert parent_rels[0].peer_id == expected_parent_uuid

            expected_child_uuids = ip_prefix_details.expected_children_uuids
            child_rels = await reconciled_prefix.children.get_relationships(db=db)
            assert len(child_rels) == len(expected_child_uuids)
            assert {rel.peer_id for rel in child_rels} == expected_child_uuids
