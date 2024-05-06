from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.services.adapters.cache.redis import RedisCache

from .base import TestIpamReconcileBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase


class TestIpamMergeReconcile(TestIpamReconcileBase):
    @pytest.fixture(scope="class", autouse=True)
    def enable_broker_settings(self):
        config.SETTINGS.broker.enable = True

    @pytest.fixture(scope="class", autouse=True)
    def bus_simulator_cache(self, bus_simulator):
        bus_simulator.service.cache = RedisCache()

    @pytest.fixture(scope="class", autouse=True)
    def git_repos_dir(self, git_repos_source_dir_module_scope): ...

    @pytest.fixture(scope="class")
    async def branch_1(self, db: InfrahubDatabase):
        return await create_branch(db=db, branch_name="new_address")

    @pytest.fixture(scope="class")
    async def new_address_1(self, branch_1, initial_dataset, db: InfrahubDatabase):
        address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=branch_1)
        new_address = await Node.init(schema=address_schema, db=db, branch=branch_1)
        await new_address.new(db=db, address="10.10.0.2", ip_namespace=initial_dataset["ns1"].id)
        await new_address.save(db=db)
        return new_address

    @pytest.fixture(scope="class")
    async def branch_2(self, db: InfrahubDatabase):
        return await create_branch(db=db, branch_name="delete_prefix")

    async def test_step01_add_address(
        self, db: InfrahubDatabase, initial_dataset, client: InfrahubClient, branch_1, new_address_1
    ) -> None:
        proposed_change_create = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={"source_branch": branch_1.name, "destination_branch": "main", "name": "add_address_pc"},
        )
        await proposed_change_create.save()
        proposed_change_create.state.value = "merged"  # type: ignore[attr-defined]
        await proposed_change_create.save()

        updated_address = await NodeManager.get_one(db=db, branch=branch_1.name, id=new_address_1.id)
        parent_rels = await updated_address.ip_prefix.get_relationships(db=db)  # type: ignore[union-attr]
        assert len(parent_rels) == 1
        assert parent_rels[0].peer_id == initial_dataset["net140"].id

    async def test_step02_add_delete_prefix(
        self, db: InfrahubDatabase, initial_dataset, client: InfrahubClient, branch_2, new_address_1
    ) -> None:
        proposed_change_create = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={"source_branch": branch_2.name, "destination_branch": "main", "name": "delete_prefix_pc"},
        )
        await proposed_change_create.save()
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=branch_2)
        new_prefix = await Node.init(schema=prefix_schema, db=db, branch=registry.default_branch)
        await new_prefix.new(db=db, prefix="10.10.0.0/17", ip_namespace=initial_dataset["ns1"].id)
        await new_prefix.save(db=db)
        deleted_prefix_branch = await NodeManager.get_one(db=db, branch=branch_2, id=initial_dataset["net140"].id)
        assert deleted_prefix_branch
        await deleted_prefix_branch.delete(db=db)

        proposed_change_create.state.value = "merged"  # type: ignore[attr-defined]
        await proposed_change_create.save()

        deleted_prefix = await NodeManager.get_one(db=db, branch=branch_2.name, id=deleted_prefix_branch.id)
        assert deleted_prefix is None
        new_prefix_branch = await NodeManager.get_one(db=db, branch=branch_2.name, id=new_prefix.id)
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
        assert len(address_rels) == 2
        assert {ar.peer_id for ar in address_rels} == {new_address_1.id, initial_dataset["address10"].id}
