from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError
from prefect import get_client
from tests.helpers.test_app import TestInfrahubApp

from infrahub.core.constants.infrahubkind import PROPOSEDCHANGE
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreAccountGroup

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient
    from prefect.client.orchestration import PrefectClient

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestProposedChangeReview(TestInfrahubApp):
    review_query = """
    mutation ProposedChangeReview($data: ProposedChangeReviewInput!) {
        CoreProposedChangeReview(data: $data) {
            ok
        }
    }
    """

    @pytest.fixture(scope="class")
    async def prefect_client(self, prefect_test_fixture) -> AsyncGenerator[PrefectClient, None]:
        async with get_client(sync_client=False) as client:
            yield client

    async def test_approve_then_reject(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        car_person_schema: SchemaBranch,
        unprivileged_client: InfrahubClient,
        prefect_client: PrefectClient,
    ) -> None:
        """Test the complete proposed change review flow including relationship updates."""

        # Create a branch for the proposed change
        source_branch = await create_branch(branch_name="branch-proposed-change", db=db)

        # Create a proposed change
        proposed_change = await client.create(
            kind=PROPOSEDCHANGE,
            data={"source_branch": source_branch.name, "destination_branch": "main", "name": "test-pc"},
        )
        await proposed_change.save()

        # Get the proposed change to verify initial state
        pc = await client.get(kind=PROPOSEDCHANGE, id=proposed_change.id)
        assert pc is not None
        approved_by_peers = {related_node.peer for related_node in pc.approved_by.peers}
        assert len(approved_by_peers) == 0
        rejected_by_peers = {related_node.peer for related_node in pc.rejected_by.peers}
        assert len(rejected_by_peers) == 0

        # Test the ProposedChangeReview mutation with APPROVED decision

        response = await unprivileged_client.execute_graphql(
            query=self.review_query,
            variables={"data": {"id": str(proposed_change.id), "decision": "APPROVE"}},
            branch_name=source_branch.name,
        )

        assert response["CoreProposedChangeReview"]["ok"] is True

        reviewer = await unprivileged_client.get_user()

        # Verify the proposed change still exists and is in the correct state
        updated_pc = await client.get(kind=PROPOSEDCHANGE, id=proposed_change.id, prefetch_relationships=True)
        assert updated_pc is not None
        assert updated_pc.state.value == "open"  # Should still be open after review
        assert {related_node.peer.id for related_node in updated_pc.approved_by.peers} == {
            reviewer["AccountProfile"]["id"]
        }
        assert len(updated_pc.rejected_by.peers) == 0

        # Verify that an event has been logged
        await self.assert_event(prefect_client=prefect_client, event_name="infrahub.proposed_change.approved")

        # Test the ProposedChangeReview mutation with REJECTED decision
        response = await unprivileged_client.execute_graphql(
            query=self.review_query,
            variables={"data": {"id": str(proposed_change.id), "decision": "REJECT"}},
            branch_name=source_branch.name,
        )

        assert response["CoreProposedChangeReview"]["ok"] is True

        # Verify user has been removed from `approved_by` and added to `rejected_by`
        updated_pc = await client.get(kind=PROPOSEDCHANGE, id=proposed_change.id, prefetch_relationships=True)
        assert updated_pc is not None
        assert updated_pc.state.value == "open"  # Should still be open after review

        approved_by_peers = {related_node.peer.id for related_node in updated_pc.approved_by.peers}
        assert len(approved_by_peers) == 0
        rejected_by_peers = {related_node.peer.id for related_node in updated_pc.rejected_by.peers}
        assert rejected_by_peers == {reviewer["AccountProfile"]["id"]}

        # Verify that an event has been logged
        await self.assert_event(prefect_client=prefect_client, event_name="infrahub.proposed_change.rejected")

    async def test_cancel_approve(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        car_person_schema: SchemaBranch,
        unprivileged_client: InfrahubClient,
        prefect_client: PrefectClient,
    ) -> None:
        """Test the complete proposed change review flow including relationship updates."""

        # Create a branch for the proposed change
        source_branch = await create_branch(branch_name="branch-pc-2", db=db)

        # Create a proposed change
        proposed_change = await client.create(
            kind=PROPOSEDCHANGE,
            data={"source_branch": source_branch.name, "destination_branch": "main", "name": "test-pc-2"},
        )
        await proposed_change.save()

        # Get the proposed change to verify initial state
        pc = await client.get(kind=PROPOSEDCHANGE, id=proposed_change.id)
        assert pc is not None
        approved_by_peers = {related_node.peer for related_node in pc.approved_by.peers}
        assert len(approved_by_peers) == 0
        rejected_by_peers = {related_node.peer for related_node in pc.rejected_by.peers}
        assert len(rejected_by_peers) == 0

        # Approve the PC
        await unprivileged_client.execute_graphql(
            query=self.review_query,
            variables={"data": {"id": str(proposed_change.id), "decision": "APPROVE"}},
            branch_name=source_branch.name,
        )

        # Verify the proposed change still exists and is in the correct state
        updated_pc = await client.get(kind=PROPOSEDCHANGE, id=proposed_change.id, prefetch_relationships=True)
        assert updated_pc is not None
        reviewer = await unprivileged_client.get_user()
        assert {related_node.peer.id for related_node in updated_pc.approved_by.peers} == {
            reviewer["AccountProfile"]["id"]
        }
        assert len(updated_pc.rejected_by.peers) == 0

        # Un-approve the PC
        response = await unprivileged_client.execute_graphql(
            query=self.review_query,
            variables={"data": {"id": str(proposed_change.id), "decision": "CANCEL_APPROVE"}},
            branch_name=source_branch.name,
        )

        assert response["CoreProposedChangeReview"]["ok"] is True

        updated_pc = await client.get(kind=PROPOSEDCHANGE, id=proposed_change.id, prefetch_relationships=True)
        assert updated_pc is not None
        assert updated_pc.state.value == "open"
        assert len(updated_pc.approved_by.peers) == 0
        assert len(updated_pc.rejected_by.peers) == 0

        # Verify that an event has been logged
        await self.assert_event(prefect_client=prefect_client, event_name="infrahub.proposed_change.approval_revoked")

    async def test_cancel_reject(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        car_person_schema: SchemaBranch,
        unprivileged_client: InfrahubClient,
        prefect_client: PrefectClient,
    ) -> None:
        """Test the complete proposed change review flow including relationship updates."""

        # Create a branch for the proposed change
        source_branch = await create_branch(branch_name="branch-pc-3", db=db)

        # Create a proposed change
        proposed_change = await client.create(
            kind=PROPOSEDCHANGE,
            data={"source_branch": source_branch.name, "destination_branch": "main", "name": "test-pc-3"},
        )
        await proposed_change.save()

        # Get the proposed change to verify initial state
        pc = await client.get(kind=PROPOSEDCHANGE, id=proposed_change.id)
        assert pc is not None
        approved_by_peers = {related_node.peer for related_node in pc.approved_by.peers}
        assert len(approved_by_peers) == 0
        rejected_by_peers = {related_node.peer for related_node in pc.rejected_by.peers}
        assert len(rejected_by_peers) == 0

        # Reject the PC
        await unprivileged_client.execute_graphql(
            query=self.review_query,
            variables={"data": {"id": str(proposed_change.id), "decision": "REJECT"}},
            branch_name=source_branch.name,
        )

        # Verify the proposed change still exists and is in the correct state
        updated_pc = await client.get(kind=PROPOSEDCHANGE, id=proposed_change.id, prefetch_relationships=True)
        assert updated_pc is not None
        reviewer = await unprivileged_client.get_user()
        assert {related_node.peer.id for related_node in updated_pc.rejected_by.peers} == {
            reviewer["AccountProfile"]["id"]
        }
        assert len(updated_pc.approved_by.peers) == 0

        # Un-reject the PC
        response = await unprivileged_client.execute_graphql(
            query=self.review_query,
            variables={"data": {"id": str(proposed_change.id), "decision": "CANCEL_REJECT"}},
            branch_name=source_branch.name,
        )

        assert response["CoreProposedChangeReview"]["ok"] is True

        updated_pc = await client.get(kind=PROPOSEDCHANGE, id=proposed_change.id, prefetch_relationships=True)
        assert updated_pc is not None
        assert updated_pc.state.value == "open"
        assert len(updated_pc.approved_by.peers) == 0
        assert len(updated_pc.rejected_by.peers) == 0

        # Verify that an event has been logged
        await self.assert_event(prefect_client=prefect_client, event_name="infrahub.proposed_change.rejection_revoked")

    async def test_missing_permission(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        car_person_schema: SchemaBranch,
        unprivileged_client: InfrahubClient,
    ) -> None:
        """Test that an approval is rejected if the user does not have the permission to make it."""
        # Create a branch for the proposed change
        source_branch = await create_branch(branch_name="branch-pc-4", db=db)

        # Create a proposed change
        proposed_change = await client.create(
            kind=PROPOSEDCHANGE,
            data={"source_branch": source_branch.name, "destination_branch": "main", "name": "test-pc-4"},
        )
        await proposed_change.save()

        # Get the proposed change to verify initial state
        pc = await client.get(kind=PROPOSEDCHANGE, id=proposed_change.id)
        assert pc is not None
        approved_by_peers = {related_node.peer for related_node in pc.approved_by.peers}
        assert len(approved_by_peers) == 0
        rejected_by_peers = {related_node.peer for related_node in pc.rejected_by.peers}
        assert len(rejected_by_peers) == 0

        # Remove the proposed change approver role from the unprivileged user
        account_group = await NodeManager.get_one_by_hfid(db=db, hfid=["Infrahub Users"], kind=CoreAccountGroup)
        assert account_group
        await account_group.members.delete(db=db)

        # Try to approve the PC
        with pytest.raises(GraphQLError) as exc:
            await unprivileged_client.execute_graphql(
                query=self.review_query,
                variables={"data": {"id": str(proposed_change.id), "decision": "APPROVE"}},
                branch_name=source_branch.name,
                raise_for_error=False,
            )

        assert exc.value.errors[0]["message"] == "You are not allowed to review proposed changes"

        # Verify the proposed change still exists and is in the correct state
        updated_pc = await client.get(kind=PROPOSEDCHANGE, id=proposed_change.id, prefetch_relationships=True)
        assert updated_pc is not None
        assert len(updated_pc.approved_by.peers) == 0
        assert len(updated_pc.rejected_by.peers) == 0
