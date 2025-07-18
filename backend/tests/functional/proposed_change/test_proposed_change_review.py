from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.test_app import TestInfrahubApp

from infrahub.core.constants.infrahubkind import PROPOSEDCHANGE
from infrahub.core.initialization import create_branch

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient


class TestProposedChangeReview(TestInfrahubApp):
    review_query: str = """
        mutation ProposedChangeReview($data: ProposedChangeReviewInput!) {
            CoreProposedChangeReview(data: $data) {
                ok
            }
        }
        """

    async def test_approve_then_reject(
        self, client: InfrahubClient, db, car_person_schema, unprivileged_client
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
        approvals = {related_node.peer for related_node in pc.approvals.peers}
        assert len(approvals) == 0
        rejects = {related_node.peer for related_node in pc.rejects.peers}
        assert len(rejects) == 0

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
        assert {related_node.peer.approver.id for related_node in updated_pc.approvals.peers} == {
            reviewer["AccountProfile"]["id"]
        }
        assert len(updated_pc.rejects.peers) == 0

        # Test the ProposedChangeReview mutation with REJECTED decision
        response = await unprivileged_client.execute_graphql(
            query=self.review_query,
            variables={"data": {"id": str(proposed_change.id), "decision": "REJECT"}},
            branch_name=source_branch.name,
        )

        assert response["CoreProposedChangeReview"]["ok"] is True

        # Verify user has been removed from `approvals` and added to `rejects`
        updated_pc = await client.get(kind=PROPOSEDCHANGE, id=proposed_change.id, prefetch_relationships=True)
        assert updated_pc is not None
        assert updated_pc.state.value == "open"  # Should still be open after review

        approvals = {related_node.peer.approver.id for related_node in updated_pc.approvals.peers}
        assert len(approvals) == 0
        rejects = {related_node.peer.rejecter.id for related_node in updated_pc.rejects.peers}
        assert rejects == {reviewer["AccountProfile"]["id"]}

    async def test_cancel_approve(self, client: InfrahubClient, db, car_person_schema, unprivileged_client) -> None:
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
        approvals = {related_node.peer for related_node in pc.approvals.peers}
        assert len(approvals) == 0
        rejects = {related_node.peer for related_node in pc.rejects.peers}
        assert len(rejects) == 0

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
        assert {related_node.peer.approver.id for related_node in updated_pc.approvals.peers} == {
            reviewer["AccountProfile"]["id"]
        }
        assert len(updated_pc.rejects.peers) == 0

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
        assert len(updated_pc.approvals.peers) == 0
        assert len(updated_pc.rejects.peers) == 0

    async def test_cancel_reject(self, client: InfrahubClient, db, car_person_schema, unprivileged_client) -> None:
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
        approvals = {related_node.peer for related_node in pc.approvals.peers}
        assert len(approvals) == 0
        rejects = {related_node.peer for related_node in pc.rejects.peers}
        assert len(rejects) == 0

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
        assert {related_node.peer.rejecter.id for related_node in updated_pc.rejects.peers} == {
            reviewer["AccountProfile"]["id"]
        }
        assert len(updated_pc.approvals.peers) == 0

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
        assert len(updated_pc.approvals.peers) == 0
        assert len(updated_pc.rejects.peers) == 0
