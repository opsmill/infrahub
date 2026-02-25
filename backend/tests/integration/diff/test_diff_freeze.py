from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.diff.model.path import BranchTrackingId, FrozenTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.proposed_change.constants import ProposedChangeState
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, DEVICE_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


BRANCH_NAME = "freeze-test-branch"

DIFF_UPDATE_QUERY = """
mutation DiffUpdate($branch_name: String!) {
    DiffUpdate(data: { branch: $branch_name }, wait_until_completion: true) {
        ok
    }
}
"""

PROPOSED_CHANGE_CREATE = """
mutation ProposedChange(
  $name: String!,
  $source_branch: String!,
  $destination_branch: String!,
) {
  CoreProposedChangeCreate(
    data: {
      name: {value: $name},
      source_branch: {value: $source_branch},
      destination_branch: {value: $destination_branch}
    }
  ) {
    object {
      id
    }
  }
}
"""

PROPOSED_CHANGE_UPDATE = """
mutation UpdateProposedChange(
    $proposed_change_id: String!,
    $state: String
  ) {
  CoreProposedChangeUpdate(data:
    {
      id: $proposed_change_id,
      state: {value: $state}
    }
  ) {
    ok
  }
}
"""

BRANCH_DELETE = """
mutation BranchDelete($branch_name: String!) {
  BranchDelete(data: {name: $branch_name}, wait_until_completion: true) {
    ok
  }
}
"""

DIFF_TREE_QUERY = """
query DiffTree($branch_name: String!, $proposed_change_id: String!) {
  DiffTree(
    branch: $branch_name
    proposed_change_id: $proposed_change_id
  ) {
    num_added
    num_updated
    num_removed
    num_conflicts
    nodes {
      kind
      parent {
        relationship_name
      }
    }
  }
}
"""


class TestDiffFreeze(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> dict[str, Node]:
        await load_schema(db, schema=CAR_SCHEMA)
        await load_schema(db, schema=DEVICE_SCHEMA)

        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, description="Original person")
        await john.save(db=db)

        acme = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await acme.new(db=db, name="Acme Motors", description="Test manufacturer")
        await acme.save(db=db)

        return {"john": john, "acme": acme}

    async def test_freeze_diff_on_proposed_change_close(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: dict[str, Node],
        client: InfrahubClient,
    ) -> None:
        """Test that closing a proposed change freezes its diff and allows new diffs on the same branch."""
        # Step 1: Create branch
        branch = await create_branch(db=db, branch_name=BRANCH_NAME)

        # Step 2: Make initial changes on branch
        alice = await Node.init(schema=TestKind.PERSON, db=db, branch=branch.name)
        await alice.new(db=db, name="Alice", height=165, description="First person added")
        await alice.save(db=db)

        # Step 3: Run DiffUpdate to create initial diff
        result = await client.execute_graphql(query=DIFF_UPDATE_QUERY, variables={"branch_name": BRANCH_NAME})
        assert result["DiffUpdate"]["ok"]

        # Step 4: Create first proposed change (PC1)
        pc1_result = await client.execute_graphql(
            query=PROPOSED_CHANGE_CREATE,
            variables={
                "name": "PC1-freeze-test",
                "source_branch": BRANCH_NAME,
                "destination_branch": default_branch.name,
            },
        )
        pc1_id = pc1_result["CoreProposedChangeCreate"]["object"]["id"]

        # Get the diff before closing PC1
        component_registry = get_component_registry()
        diff_repo = await component_registry.get_component(DiffRepository, db=db, branch=branch)
        diff_before_close = await diff_repo.get_one(
            tracking_id=BranchTrackingId(name=BRANCH_NAME),
            diff_branch_name=BRANCH_NAME,
        )
        assert len(diff_before_close.nodes) == 1
        nodes_by_label = {n.label: n for n in diff_before_close.nodes}
        assert "Alice" in nodes_by_label
        assert diff_before_close.is_frozen is False
        diff_before_close_to_time = diff_before_close.to_time

        # Step 5: Close PC1 (this should freeze the diff)
        await client.execute_graphql(
            query=PROPOSED_CHANGE_UPDATE,
            variables={"proposed_change_id": pc1_id, "state": ProposedChangeState.CLOSED.value},
        )

        # Verify the diff is now frozen with FrozenTrackingId
        frozen_diff_metadata = await diff_repo.get_roots_metadata(proposed_change_id=pc1_id)
        assert len(frozen_diff_metadata) == 2  # branch diff + base diff
        for metadata in frozen_diff_metadata:
            assert metadata.is_frozen is True
            assert isinstance(metadata.tracking_id, FrozenTrackingId)
            assert metadata.tracking_id.name == pc1_id
            assert metadata.proposed_change_id == pc1_id

        # Get the frozen branch diff
        frozen_branch_metadata = next(m for m in frozen_diff_metadata if m.diff_branch_name == BRANCH_NAME)

        # Step 6: Create second proposed change (PC2)
        pc2_result = await client.execute_graphql(
            query=PROPOSED_CHANGE_CREATE,
            variables={
                "name": "PC2-freeze-test",
                "source_branch": BRANCH_NAME,
                "destination_branch": default_branch.name,
            },
        )
        pc2_id = pc2_result["CoreProposedChangeCreate"]["object"]["id"]

        # Step 7: Make more changes on branch
        diff_branch = registry.get_branch_from_registry(branch=BRANCH_NAME)
        bob = await Node.init(schema=TestKind.PERSON, db=db, branch=diff_branch.name)
        await bob.new(db=db, name="Bob", height=180, description="Second person added")
        await bob.save(db=db)
        second_change_time = Timestamp()

        # Step 8: Run DiffUpdate again
        result = await client.execute_graphql(query=DIFF_UPDATE_QUERY, variables={"branch_name": BRANCH_NAME})
        assert result["DiffUpdate"]["ok"]

        # Step 9: Validate frozen diff for PC1 still has original changes and time range
        frozen_diff = await diff_repo.get_one(
            tracking_id=FrozenTrackingId(name=pc1_id),
            diff_branch_name=BRANCH_NAME,
        )
        assert frozen_diff.uuid == frozen_branch_metadata.uuid
        # Frozen diff should have same time range as before it was closed
        assert frozen_diff.to_time == diff_before_close_to_time
        assert frozen_diff.to_time < second_change_time
        assert len(frozen_diff.nodes) == 1
        frozen_nodes_by_label = {n.label: n for n in frozen_diff.nodes}
        assert "Alice" in frozen_nodes_by_label
        assert "Bob" not in frozen_nodes_by_label

        # Step 10: Validate diff for PC2 has all changes and correct time range
        pc2_diff_metadata = await diff_repo.get_roots_metadata(proposed_change_id=pc2_id)
        assert len(pc2_diff_metadata) == 2  # branch diff + base diff
        pc2_branch_metadata = next(m for m in pc2_diff_metadata if m.diff_branch_name == BRANCH_NAME)
        assert pc2_branch_metadata.is_frozen is False
        assert isinstance(pc2_branch_metadata.tracking_id, BranchTrackingId)

        current_diff = await diff_repo.get_one(
            tracking_id=BranchTrackingId(name=BRANCH_NAME),
            diff_branch_name=BRANCH_NAME,
        )
        assert current_diff.uuid == pc2_branch_metadata.uuid
        # Current diff should have same from_time as frozen diff (branch creation time)
        assert current_diff.from_time == frozen_diff.from_time
        assert current_diff.to_time >= second_change_time
        assert len(current_diff.nodes) == 2
        current_nodes_by_label = {n.label: n for n in current_diff.nodes}
        assert "Alice" in current_nodes_by_label
        assert "Bob" in current_nodes_by_label

        # Verify both diffs coexist - frozen diff is distinct from current diff
        assert frozen_diff.uuid != current_diff.uuid

        # Step 11: Verify frozen diff cannot be deleted by normal delete operations
        await diff_repo.delete_diff_roots(diff_root_uuids=[frozen_diff.uuid], include_frozen=False)
        # Frozen diff should still exist
        frozen_diff_after_delete = await diff_repo.get_one(
            tracking_id=FrozenTrackingId(name=pc1_id),
            diff_branch_name=BRANCH_NAME,
        )
        assert frozen_diff_after_delete.uuid == frozen_diff.uuid

    async def test_freeze_diff_on_branch_delete(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: dict[str, Node],
        client: InfrahubClient,
    ) -> None:
        """Test that deleting a branch freezes diffs for open proposed changes associated with that branch."""
        branch_name = "branch-delete-freeze-test"

        # Step 1: Create branch
        branch = await create_branch(db=db, branch_name=branch_name)

        # Step 2: Make changes on branch
        # includes interface-device PARENT relationship for testing parent serialization in DiffTreeResolver
        device = await Node.init(schema=TestKind.DEVICE, db=db, branch=branch.name)
        await device.new(db=db, name="device01", manufacturer="Cisco", height=2, weight=10, airflow="Front to rear")
        await device.save(db=db)

        intf = await Node.init(schema=TestKind.PHYSICAL_INTERFACE, db=db, branch=branch.name)
        await intf.new(db=db, name="eth0", device=device, phys_type="SFP+ (10GE)")
        await intf.save(db=db)

        # Step 3: Run DiffUpdate to create diff
        result = await client.execute_graphql(query=DIFF_UPDATE_QUERY, variables={"branch_name": branch_name})
        assert result["DiffUpdate"]["ok"]

        # Step 4: Create proposed change linked to the branch
        pc_result = await client.execute_graphql(
            query=PROPOSED_CHANGE_CREATE,
            variables={
                "name": "PC-branch-delete-freeze-test",
                "source_branch": branch_name,
                "destination_branch": default_branch.name,
            },
        )
        pc_id = pc_result["CoreProposedChangeCreate"]["object"]["id"]

        # Verify diff is linked to PC and not frozen
        component_registry = get_component_registry()
        diff_repo = await component_registry.get_component(DiffRepository, db=db, branch=branch)
        diff_before_delete = await diff_repo.get_one(
            tracking_id=BranchTrackingId(name=branch_name),
            diff_branch_name=branch_name,
        )
        assert diff_before_delete.proposed_change_id == pc_id
        assert diff_before_delete.is_frozen is False
        assert isinstance(diff_before_delete.tracking_id, BranchTrackingId)
        diff_kinds_before = {n.kind for n in diff_before_delete.nodes}
        assert TestKind.DEVICE in diff_kinds_before
        assert TestKind.PHYSICAL_INTERFACE in diff_kinds_before

        # Step 5: Delete the branch
        result = await client.execute_graphql(query=BRANCH_DELETE, variables={"branch_name": branch_name})
        assert result["BranchDelete"]["ok"]

        # Step 6: Verify diffs are now frozen with FrozenTrackingId
        frozen_diff_metadata = await diff_repo.get_roots_metadata(proposed_change_id=pc_id)
        assert len(frozen_diff_metadata) == 2  # branch diff + base diff
        for metadata in frozen_diff_metadata:
            assert metadata.is_frozen is True
            assert isinstance(metadata.tracking_id, FrozenTrackingId)
            assert metadata.tracking_id.name == pc_id
            assert metadata.proposed_change_id == pc_id

        # Verify the frozen diff still has the original data
        frozen_branch_metadata = next(m for m in frozen_diff_metadata if m.diff_branch_name == branch_name)
        frozen_diff = await diff_repo.get_one(
            tracking_id=FrozenTrackingId(name=pc_id),
            diff_branch_name=branch_name,
        )
        assert frozen_diff.uuid == frozen_branch_metadata.uuid
        assert frozen_diff.is_frozen is True
        frozen_kinds = {n.kind for n in frozen_diff.nodes}
        assert TestKind.DEVICE in frozen_kinds
        assert TestKind.PHYSICAL_INTERFACE in frozen_kinds

        # Step 7: Verify frozen diff can be retrieved via DiffTree GraphQL query
        # even after the branch is deleted
        diff_tree_result = await client.execute_graphql(
            query=DIFF_TREE_QUERY,
            variables={"branch_name": branch_name, "proposed_change_id": pc_id},
        )
        assert "DiffTree" in diff_tree_result
        assert diff_tree_result["DiffTree"] is not None
        # Verify there are added nodes (Device + PhysicalInterface)
        assert diff_tree_result["DiffTree"]["num_added"] >= 2
        assert diff_tree_result["DiffTree"]["num_removed"] == 0
        assert diff_tree_result["DiffTree"]["num_conflicts"] == 0
        # Verify node kinds and parent info are returned correctly
        tree_nodes = diff_tree_result["DiffTree"]["nodes"]
        tree_nodes_by_kind = {n["kind"]: n for n in tree_nodes}
        assert TestKind.DEVICE in tree_nodes_by_kind
        assert TestKind.PHYSICAL_INTERFACE in tree_nodes_by_kind
        # PhysicalInterface should have Device as its parent via the "interfaces" relationship
        intf_node = tree_nodes_by_kind[TestKind.PHYSICAL_INTERFACE]
        assert intf_node["parent"] is not None
        assert intf_node["parent"]["relationship_name"] == "interfaces"

    async def test_branch_diff_update_using_frozen_diff(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: dict[str, Node],
        client: InfrahubClient,
    ) -> None:
        """Test a branch-tracking diff using a previous frozen diff

        This validates the scenario where:
        1. Create a branch
        2. Make changes
        3. Create a proposed change and link the diff
        4. Close the proposed change, freezing the diff
        5. Make more changes on the branch
        6. Refresh the diff for the branch (without creating a new PC)
        7. Frozen diff still exists and is linked to the closed PC
        8. New BranchTrackingId diff has latest data and is NOT linked to any PC
        """
        branch_name = "freeze-persist-test-branch"

        # Step 1: Create branch
        branch = await create_branch(db=db, branch_name=branch_name)

        # Step 2: Make initial changes on branch
        carol = await Node.init(schema=TestKind.PERSON, db=db, branch=branch.name)
        await carol.new(db=db, name="Carol", height=170, description="First person on persist test")
        await carol.save(db=db)

        # Step 3: Run DiffUpdate to create initial diff
        result = await client.execute_graphql(query=DIFF_UPDATE_QUERY, variables={"branch_name": branch_name})
        assert result["DiffUpdate"]["ok"]

        # Create proposed change
        pc_result = await client.execute_graphql(
            query=PROPOSED_CHANGE_CREATE,
            variables={
                "name": "PC-persist-test",
                "source_branch": branch_name,
                "destination_branch": default_branch.name,
            },
        )
        pc_id = pc_result["CoreProposedChangeCreate"]["object"]["id"]

        # Verify diff is linked to the PC and has BranchTrackingId
        component_registry = get_component_registry()
        diff_repo = await component_registry.get_component(DiffRepository, db=db, branch=branch)
        diff_before_close = await diff_repo.get_one(
            tracking_id=BranchTrackingId(name=branch_name),
            diff_branch_name=branch_name,
        )
        assert diff_before_close.proposed_change_id == pc_id
        assert diff_before_close.is_frozen is False
        assert isinstance(diff_before_close.tracking_id, BranchTrackingId)
        assert len(diff_before_close.nodes) == 1
        assert any(n.label == "Carol" for n in diff_before_close.nodes)
        diff_before_close_to_time = diff_before_close.to_time

        # Step 4: Close the proposed change (this freezes the diff)
        await client.execute_graphql(
            query=PROPOSED_CHANGE_UPDATE,
            variables={"proposed_change_id": pc_id, "state": ProposedChangeState.CLOSED.value},
        )

        # Verify diff is now frozen and linked to closed PC
        frozen_diff_metadata_list = await diff_repo.get_roots_metadata(proposed_change_id=pc_id)
        assert len(frozen_diff_metadata_list) == 2  # branch diff + base diff
        for frozen_diff_metadata in frozen_diff_metadata_list:
            assert frozen_diff_metadata.is_frozen is True
            assert isinstance(frozen_diff_metadata.tracking_id, FrozenTrackingId)
            assert frozen_diff_metadata.tracking_id.name == pc_id
            assert frozen_diff_metadata.proposed_change_id == pc_id

        # Step 5: Make more changes on the branch
        diff_branch = registry.get_branch_from_registry(branch=branch_name)
        dave = await Node.init(schema=TestKind.PERSON, db=db, branch=diff_branch.name)
        await dave.new(db=db, name="Dave", height=185, description="Second person on persist test")
        await dave.save(db=db)
        second_change_time = Timestamp()

        # Step 6: Refresh the diff for the branch (no new PC created)
        result = await client.execute_graphql(query=DIFF_UPDATE_QUERY, variables={"branch_name": branch_name})
        assert result["DiffUpdate"]["ok"]

        # Step 7: Validate frozen diff still exists and is linked to closed PC
        frozen_diff = await diff_repo.get_one(
            tracking_id=FrozenTrackingId(name=pc_id),
            diff_branch_name=branch_name,
        )
        assert frozen_diff.uuid == next(m.uuid for m in frozen_diff_metadata_list if m.diff_branch_name == branch_name)
        assert frozen_diff.is_frozen is True
        assert isinstance(frozen_diff.tracking_id, FrozenTrackingId)
        assert frozen_diff.tracking_id.name == pc_id
        assert frozen_diff.proposed_change_id == pc_id
        # Frozen diff should have same time range as before it was closed
        assert frozen_diff.to_time == diff_before_close_to_time
        assert frozen_diff.to_time < second_change_time
        # Frozen diff should only have original changes (Carol, not Dave)
        assert len(frozen_diff.nodes) == 1
        frozen_nodes_by_label = {n.label: n for n in frozen_diff.nodes}
        assert "Carol" in frozen_nodes_by_label
        assert "Dave" not in frozen_nodes_by_label

        # Step 8: Validate the new BranchTrackingId diff has latest data and is NOT linked to any PC
        current_diff = await diff_repo.get_one(
            tracking_id=BranchTrackingId(name=branch_name),
            diff_branch_name=branch_name,
        )
        # Current diff should be different from frozen diff
        assert current_diff.uuid != frozen_diff.uuid
        # Current diff should NOT be frozen
        assert current_diff.is_frozen is False
        # Current diff should have BranchTrackingId
        assert isinstance(current_diff.tracking_id, BranchTrackingId)
        assert current_diff.tracking_id.name == branch_name
        # Current diff should NOT be linked to any proposed change
        assert current_diff.proposed_change_id is None
        # Current diff should have latest data (both Carol and Dave)
        assert len(current_diff.nodes) == 2
        current_nodes_by_label = {n.label: n for n in current_diff.nodes}
        assert "Carol" in current_nodes_by_label
        assert "Dave" in current_nodes_by_label
        # Current diff should have updated time range
        assert current_diff.from_time == frozen_diff.from_time  # Same branch creation time
        assert current_diff.to_time >= second_change_time
