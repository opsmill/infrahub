import ipaddress
from dataclasses import dataclass
from unittest.mock import AsyncMock, call

import pytest

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m039_ipam_reconcile import Migration039
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.test_app import TestInfrahubApp


@dataclass
class IpPrefixDetails:
    branch: str
    node_uuid: str
    prefix: str
    expected_namespace_uuid: str
    expected_parent_uuid: str | None
    expected_children_uuids: set[str]


@dataclass
class IpAddressDetails:
    branch: str
    node_uuid: str
    address: str
    expected_namespace_uuid: str
    expected_prefix_uuid: str


class WrappedMigration039(Migration039):
    async def _get_reconciler(self, db: InfrahubDatabase, branch_name: str) -> IpamReconciler:
        reconciler = await super()._get_reconciler(db=db, branch_name=branch_name)
        if isinstance(reconciler, AsyncMock):
            return reconciler
        wrapped_reconciler = AsyncMock(wraps=reconciler)
        self._reconcilers_by_branch[branch_name] = wrapped_reconciler
        return wrapped_reconciler


class TestMigration039(TestInfrahubApp):
    branch_name = "ip_test_branch"
    branch_2_name = "ip_test_branch_2"

    @pytest.fixture
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        register_ipam_schema: SchemaBranch,
    ) -> dict[str, Node]:
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
        address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

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

        net142 = await Node.init(db=db, schema=prefix_schema)
        await net142.new(db=db, prefix="10.10.1.0/24", ip_namespace=ns1, parent=net140)
        await net142.save(db=db)

        net143 = await Node.init(db=db, schema=prefix_schema)
        await net143.new(db=db, prefix="10.10.1.0/27", ip_namespace=ns1, parent=net142)
        await net143.save(db=db)

        address10 = await Node.init(db=db, schema=address_schema)
        await address10.new(db=db, address="10.10.0.0", ip_prefix=net140, ip_namespace=ns1)
        await address10.save(db=db)

        address11 = await Node.init(db=db, schema=address_schema)
        await address11.new(db=db, address="10.10.1.1", ip_prefix=net143, ip_namespace=ns1)
        await address11.save(db=db)

        return {
            "ns1": ns1,
            "ns2": ns2,
            "net140": net140,
            "net142": net142,
            "net143": net143,
            "net146": net146,
            "address10": address10,
            "address11": address11,
        }

    @pytest.fixture
    async def branch(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name=self.branch_name)

    @pytest.fixture
    async def branch_2(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name=self.branch_2_name)

    @pytest.fixture
    async def net140_updated(
        self, db: InfrahubDatabase, initial_dataset: dict[str, Node], branch: Branch
    ) -> IpPrefixDetails:
        """Update prefix from 10.10.0.0/16 to 10.10.0.0/17 and set parent to self"""
        ns1 = initial_dataset["ns1"]
        net140 = initial_dataset["net140"]
        net143 = initial_dataset["net143"]
        net146 = initial_dataset["net146"]
        net140_branch = await NodeManager.get_one(db=db, branch=branch, id=net140.id)
        net140_branch.prefix.value = "10.10.0.0/17"
        await net140_branch.parent.update(db=db, data=net140.id)
        await net140_branch.save(db=db)

        return IpPrefixDetails(
            branch=branch.name,
            node_uuid=net140_branch.id,
            prefix="10.10.0.0/17",
            expected_namespace_uuid=ns1.id,
            expected_parent_uuid=net146.id,
            expected_children_uuids={net143.id},
        )

    @pytest.fixture
    async def net142_updated(
        self, db: InfrahubDatabase, initial_dataset: dict[str, Node], branch: Branch
    ) -> IpPrefixDetails:
        """Update prefix from ns1 to ns2 on branch"""
        net142 = initial_dataset["net142"]
        ns2 = initial_dataset["ns2"]
        net142_branch = await NodeManager.get_one(db=db, branch=branch, id=net142.id)
        await net142_branch.ip_namespace.update(db=db, data=ns2.id)
        await net142_branch.save(db=db)

        return IpPrefixDetails(
            branch=branch.name,
            node_uuid=net142_branch.id,
            prefix="10.10.1.0/24",
            expected_namespace_uuid=ns2.id,
            expected_parent_uuid=None,
            expected_children_uuids=set(),
        )

    @pytest.fixture
    async def net143_updated(
        self, db: InfrahubDatabase, initial_dataset: dict[str, Node], branch_2: Branch
    ) -> IpPrefixDetails:
        """Update prefix from "10.10.1.0/27" to 10.10.0.0/20"""
        ns1 = initial_dataset["ns1"]
        net140 = initial_dataset["net140"]
        net142 = initial_dataset["net142"]
        net143 = initial_dataset["net143"]
        net143_branch = await NodeManager.get_one(db=db, branch=branch_2, id=net143.id)
        net143_branch.prefix.value = "10.10.0.0/20"
        await net143_branch.save(db=db)

        return IpPrefixDetails(
            branch=branch_2.name,
            node_uuid=net143_branch.id,
            prefix="10.10.0.0/20",
            expected_namespace_uuid=ns1.id,
            expected_parent_uuid=net140.id,
            expected_children_uuids={net142.id},
        )

    @pytest.fixture
    async def address10_updated(
        self, db: InfrahubDatabase, initial_dataset: dict[str, Node], branch: Branch
    ) -> IpAddressDetails:
        """Update address value on branch"""
        address10 = initial_dataset["address10"]
        ns1 = initial_dataset["ns1"]
        net146 = initial_dataset["net146"]
        address10_branch = await NodeManager.get_one(db=db, branch=branch, id=address10.id)
        address10_branch.address.value = "10.0.0.1/32"
        await address10_branch.save(db=db)

        return IpAddressDetails(
            branch=branch.name,
            node_uuid=address10_branch.id,
            address="10.0.0.1/32",
            expected_namespace_uuid=ns1.id,
            expected_prefix_uuid=net146.id,
        )

    @pytest.fixture
    async def branch_prefix_updates(
        self,
        initial_dataset: dict[str, Node],
        branch: Branch,
        branch_2: Branch,
        net140_updated: IpPrefixDetails,
        net142_updated: IpPrefixDetails,
        net143_updated: IpPrefixDetails,
    ) -> list[IpPrefixDetails]:
        return {"net140": net140_updated, "net142": net142_updated, "net143": net143_updated}

    @pytest.fixture
    async def branch_address_updates(
        self,
        initial_dataset: dict[str, Node],
        branch: Branch,
        branch_2: Branch,
        address10_updated: IpAddressDetails,
    ) -> list[IpAddressDetails]:
        return {"address10": address10_updated}

    async def test_migration_039(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        branch_prefix_updates: dict[str, IpPrefixDetails],
        branch_address_updates: dict[str, IpAddressDetails],
    ) -> None:
        migration = WrappedMigration039()
        await migration.execute(db=db, at=Timestamp())

        # validate that we only reconciled on the branch
        assert set(migration._reconcilers_by_branch.keys()) == {self.branch_name, self.branch_2_name}
        # validate that we only reconciled the expected IP prefixes/addresses
        for branch_name in [self.branch_name, self.branch_2_name]:
            wrapped_branch_reconciler = migration._reconcilers_by_branch[branch_name]
            expected_reconciler_calls = [
                call(
                    ip_value=ipaddress.ip_network(ip_prefix_details.prefix),
                    namespace=ip_prefix_details.expected_namespace_uuid,
                    node_uuid=ip_prefix_details.node_uuid,
                )
                for ip_prefix_details in branch_prefix_updates.values()
                if ip_prefix_details.branch == branch_name
            ]
            expected_reconciler_calls.extend(
                [
                    call(
                        ip_value=ipaddress.ip_interface(ip_address_details.address),
                        namespace=ip_address_details.expected_namespace_uuid,
                        node_uuid=ip_address_details.node_uuid,
                    )
                    for ip_address_details in branch_address_updates.values()
                    if ip_address_details.branch == branch_name
                ]
            )
            wrapped_branch_reconciler.reconcile.assert_has_awaits(expected_reconciler_calls, any_order=True)

        for ip_prefix_details in branch_prefix_updates.values():
            reconciled_prefix = await NodeManager.get_one(
                db=db, branch=ip_prefix_details.branch, id=ip_prefix_details.node_uuid
            )

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

            expected_namespace_uuid = ip_prefix_details.expected_namespace_uuid
            namespace_rels = await reconciled_prefix.ip_namespace.get_relationships(db=db)
            assert len(namespace_rels) == 1
            assert namespace_rels[0].peer_id == expected_namespace_uuid

        for ip_address_details in branch_address_updates.values():
            reconciled_address = await NodeManager.get_one(
                db=db, branch=ip_address_details.branch, id=ip_address_details.node_uuid
            )

            assert reconciled_address.address.value == ip_address_details.address

            expected_prefix_uuid = ip_address_details.expected_prefix_uuid
            prefix_rels = await reconciled_address.ip_prefix.get_relationships(db=db)
            assert len(prefix_rels) == 1
            assert prefix_rels[0].peer_id == expected_prefix_uuid

            expected_namespace_uuid = ip_address_details.expected_namespace_uuid
            namespace_rels = await reconciled_address.ip_namespace.get_relationships(db=db)
            assert len(namespace_rels) == 1
            assert namespace_rels[0].peer_id == expected_namespace_uuid
