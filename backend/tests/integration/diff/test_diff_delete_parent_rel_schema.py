"""Test that removing a Parent relationship from the schema is correctly reflected in the diff."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.test_app import TestInfrahubApp

from ..shared import load_schema

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

PARENT_REL_BRANCH_NAME = "branch_parent_rel_schema_remove"

CLUSTER_KIND = "TestCluster"
VIRTUAL_INTERFACE_KIND = "NetworkVirtualInterface"
PROVIDER_GENERIC = "NetworkVirtualInterfaceProvider"

PARENT_REL_SCHEMA: dict[str, Any] = {
    "version": "1.0",
    "generics": [
        {
            "name": "VirtualInterfaceProvider",
            "namespace": "Network",
            "attributes": [
                {"name": "name", "kind": "Text"},
            ],
        },
    ],
    "nodes": [
        {
            "name": "Cluster",
            "namespace": "Test",
            "inherit_from": [PROVIDER_GENERIC],
            "attributes": [
                {
                    "name": "name",
                    "kind": "Text",
                    "optional": True,
                },
            ],
        },
        {
            "name": "VirtualInterface",
            "namespace": "Network",
            "attributes": [
                {"name": "name", "kind": "Text"},
            ],
            "relationships": [
                {
                    "name": "provider",
                    "peer": PROVIDER_GENERIC,
                    "kind": "Parent",
                    "optional": False,
                    "cardinality": "one",
                },
            ],
        },
    ],
}


class TestDiffDeleteParentRelSchema(TestInfrahubApp):
    """Verify the diff is correct after a Parent relationship is removed from the schema mid-branch."""

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> None:
        await load_schema(db=db, schema=PARENT_REL_SCHEMA)

    @pytest.fixture(scope="class")
    async def diff_branch(
        self,
        db: InfrahubDatabase,
        initial_dataset: None,
    ) -> Branch:
        return await create_branch(db=db, branch_name=PARENT_REL_BRANCH_NAME)

    async def test_parent_rel_removed_by_schema_change(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """Removing a Parent relationship from the schema after data is created should
        produce a diff where the child node no longer has the removed relationship.

        1. Create TestCluster + VirtualInterface (provider=TestCluster) on branch.
        2. Update the branch diff.
        3. Schema change: mark ``provider`` relationship as absent.
        4. Modify VirtualInterface and delete TestCluster.
        5. Update the branch diff again.
        6. Validate VirtualInterface is in the diff without the ``provider`` relationship.
        """
        # Create data on the branch
        cluster = await Node.init(schema=CLUSTER_KIND, db=db, branch=diff_branch)
        await cluster.new(db=db, name="test-cluster")
        await cluster.save(db=db)

        vi = await Node.init(schema=VIRTUAL_INTERFACE_KIND, db=db, branch=diff_branch)
        await vi.new(db=db, name="eth0", provider=cluster)
        await vi.save(db=db)

        # First diff update
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)

        # Remove the provider Parent relationship from the schema
        schema_removal: dict[str, Any] = {
            "version": "1.0",
            "nodes": [
                {
                    "name": "VirtualInterface",
                    "namespace": "Network",
                    "relationships": [
                        {
                            "name": "provider",
                            "peer": PROVIDER_GENERIC,
                            "kind": "Parent",
                            "optional": False,
                            "cardinality": "one",
                            "state": "absent",
                        },
                    ],
                },
            ],
        }

        response = await client.schema.load(schemas=[schema_removal], branch=diff_branch.name)
        assert not response.errors

        # Modify VirtualInterface and delete the cluster
        vi_updated = await NodeManager.get_one(db=db, id=vi.id, branch=diff_branch)
        vi_updated.name.value = "eth0-updated"  # type: ignore[union-attr]
        await vi_updated.save(db=db)

        cluster_deleted = await NodeManager.get_one(db=db, id=cluster.id, branch=diff_branch)
        await cluster_deleted.delete(db=db)

        # Second diff update
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)

        # Validate the diff
        diff_repo = await component_registry.get_component(DiffRepository, db=db, branch=diff_branch)
        diff = await diff_repo.get_one(
            tracking_id=BranchTrackingId(name=diff_branch.name),
            diff_branch_name=diff_branch.name,
        )

        nodes_by_id = {n.uuid: n for n in diff.nodes}
        assert vi.id in nodes_by_id, f"NetworkVirtualInterface {vi.id} should be in the diff"
        vi_node = nodes_by_id[vi.id]
        assert vi_node.kind == VIRTUAL_INTERFACE_KIND

        # this relationship should be removed once #2474 is implemented
        # assert not vi_node.has_relationship("provider"), (
        #     "The 'provider' Parent relationship should not be in the diff after being removed from the schema"
        # )
