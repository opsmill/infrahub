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
from tests.helpers.schema import CAR_SCHEMA, load_schema
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

        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, description="Original person")
        await john.save(db=db)

        return {"john": john}

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
