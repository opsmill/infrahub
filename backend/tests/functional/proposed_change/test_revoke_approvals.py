from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.protocols import CoreProposedChange
from infrahub_sdk.uuidt import UUIDT
from tests.helpers.test_app import TestInfrahubApp

from infrahub.core.constants.infrahubkind import PROPOSEDCHANGE
from infrahub.core.initialization import create_account, create_branch

if TYPE_CHECKING:
    from tests.adapters.message_bus import BusSimulator
    from tests.helpers.test_client import InfrahubTestClient

    from infrahub.services import InfrahubServices


class TestRevokeApprovalOnBranchChanges(TestInfrahubApp):
    check_for_changes_query: str = """
        mutation ProposedChangeCheckForChanges {
            CoreProposedChangeCheckForChanges {
                ok
            }
        }
        """

    approve_query: str = """
        mutation ProposedChangeReview($data: ProposedChangeReviewInput!) {
            CoreProposedChangeReview(data: $data) {
                ok
            }
        }
        """

    @pytest.fixture(scope="class")
    async def unprivileged_client_2(
        self,
        test_client: InfrahubTestClient,
        bus_simulator: BusSimulator,
        service: InfrahubServices,
        db,
    ) -> InfrahubClient:
        token = str(UUIDT())
        _ = await create_account(
            db=db,
            name="unprivileged_2",
            password="testing_unprivileged_password",
            token_value=token,
        )

        config = Config(
            api_token=token,
            requester=test_client.async_request,
            sync_requester=test_client.sync_request,
            schema_converge_timeout=5,
        )

        sdk_client = InfrahubClient(config=config)
        return sdk_client

    @pytest.fixture(scope="class")
    async def unprivileged_client_3(
        self,
        test_client: InfrahubTestClient,
        bus_simulator: BusSimulator,
        service: InfrahubServices,
        db,
    ) -> InfrahubClient:
        token = str(UUIDT())
        _ = await create_account(
            db=db,
            name="unprivileged_3",
            password="testing_unprivileged_password_2",
            token_value=token,
        )

        config = Config(
            api_token=token,
            requester=test_client.async_request,
            sync_requester=test_client.sync_request,
            schema_converge_timeout=5,
        )

        sdk_client = InfrahubClient(config=config)
        return sdk_client

    async def test_no_revoke_when_no_changes(
        self, client: InfrahubClient, db, car_person_schema, unprivileged_client
    ) -> None:
        """Test that no approvals are revoked when there are no changes."""
        # Create a branch for the proposed change
        source_branch = await create_branch(branch_name="branch-no-changes", db=db)

        # Create a proposed change
        proposed_change = await client.create(
            kind=PROPOSEDCHANGE,
            data={"source_branch": source_branch.name, "destination_branch": "main", "name": "test-pc-no-changes"},
        )
        await proposed_change.save()

        # Approve the proposed change
        response = await unprivileged_client.execute_graphql(
            query=self.approve_query,
            variables={"data": {"id": str(proposed_change.id), "decision": "APPROVE"}},
            branch_name=source_branch.name,
        )

        # Verify approval was added
        proposed_change = await client.get(kind=CoreProposedChange, id=proposed_change.id, prefetch_relationships=True)
        assert len(proposed_change.approvals.peers) == 1

        # Run changes checks, should not clear approvals since no changes occurred
        response = await client.execute_graphql(
            query=self.check_for_changes_query,
            branch_name="main",
        )
        assert response["CoreProposedChangeCheckForChanges"]["ok"]

        # Verify approval is still there
        proposed_change = await client.get(kind=CoreProposedChange, id=proposed_change.id, prefetch_relationships=True)
        assert len(proposed_change.approvals.peers) == 1

    async def test_checks_run_when_no_approvals(self, client: InfrahubClient, db, car_person_schema) -> None:
        """Test that nothing happens when proposed changes have no approvals."""

        source_branch = await create_branch(branch_name="branch-no-approvals", db=db)

        proposed_change = await client.create(
            kind=PROPOSEDCHANGE,
            data={"source_branch": source_branch.name, "destination_branch": "main", "name": "test-pc-no-approvals"},
        )
        await proposed_change.save()

        assert len(proposed_change.approvals.peers) == 0

        person = await client.create(
            kind="TestPerson",
            data={"name": "Jane Doe"},
            branch=source_branch.name,
        )
        await person.save()

        response = await client.execute_graphql(
            query=self.check_for_changes_query,
            branch_name="main",
        )
        assert response["CoreProposedChangeCheckForChanges"]["ok"]
        assert len(proposed_change.approvals.peers) == 0

    async def test_revoke_when_changes_on_different_branches(
        self, client: InfrahubClient, db, car_person_schema, unprivileged_client
    ) -> None:
        """Test that approvals are revoked when there are changes."""

        branch1 = await create_branch(branch_name="branch-multi-1", db=db)
        branch2 = await create_branch(branch_name="branch-multi-2", db=db)

        # Create proposed changes for different branches
        proposed_change1 = await client.create(
            kind=PROPOSEDCHANGE,
            data={"source_branch": branch1.name, "destination_branch": "main", "name": "test-pc-multi-1"},
        )
        await proposed_change1.save()

        proposed_change2 = await client.create(
            kind=PROPOSEDCHANGE,
            data={"source_branch": branch2.name, "destination_branch": "main", "name": "test-pc-multi-2"},
        )
        await proposed_change2.save()

        # Approve both proposed changes
        # TODO use the graphql mutation to approv pc1 and pc2
        response = await unprivileged_client.execute_graphql(
            query=self.approve_query,
            variables={"data": {"id": str(proposed_change1.id), "decision": "APPROVE"}},
            branch_name=branch1.name,
        )
        response = await unprivileged_client.execute_graphql(
            query=self.approve_query,
            variables={"data": {"id": str(proposed_change2.id), "decision": "APPROVE"}},
            branch_name=branch2.name,
        )

        proposed_change1 = await client.get(
            kind=CoreProposedChange, id=proposed_change1.id, prefetch_relationships=True
        )
        proposed_change2 = await client.get(
            kind=CoreProposedChange, id=proposed_change2.id, prefetch_relationships=True
        )

        assert len(proposed_change1.approvals.peers) == 1
        assert len(proposed_change2.approvals.peers) == 1

        # Create changes on both branches
        person1 = await client.create(
            kind="TestPerson",
            data={"name": "Person 1"},
            branch=branch1.name,
        )
        await person1.save()

        person2 = await client.create(
            kind="TestPerson",
            data={"name": "Person 2"},
            branch=branch2.name,
        )
        await person2.save()

        response = await client.execute_graphql(
            query=self.check_for_changes_query,
            branch_name="main",
        )
        assert response["CoreProposedChangeCheckForChanges"]["ok"]

        # Verify both approvals were revoked
        pc1_updated = await client.get(kind=CoreProposedChange, id=proposed_change1.id, prefetch_relationships=True)
        pc2_updated = await client.get(kind=CoreProposedChange, id=proposed_change2.id, prefetch_relationships=True)
        assert len(pc1_updated.approvals.peers) == 0
        assert len(pc2_updated.approvals.peers) == 0

    async def test_revoke_when_changes_between_approvals(
        self,
        client: InfrahubClient,
        db,
        car_person_schema,
        unprivileged_client,
        unprivileged_client_2,
        unprivileged_client_3,
    ) -> None:
        """
        Approves a PC, makes changes, approves again with a different user, and make sure only first approval is removed
        """

        branch1 = await create_branch(branch_name="branch-multi-approvals", db=db)

        proposed_change = await client.create(
            kind=PROPOSEDCHANGE,
            data={"source_branch": branch1.name, "destination_branch": "main", "name": "test-pc"},
        )
        await proposed_change.save()

        _ = await unprivileged_client.execute_graphql(
            query=self.approve_query,
            variables={"data": {"id": str(proposed_change.id), "decision": "APPROVE"}},
            branch_name=branch1.name,
        )

        _ = await unprivileged_client_2.execute_graphql(
            query=self.approve_query,
            variables={"data": {"id": str(proposed_change.id), "decision": "APPROVE"}},
            branch_name=branch1.name,
        )

        person1 = await client.create(
            kind="TestPerson",
            data={"name": "Person 1"},
            branch=branch1.name,
        )
        await person1.save()

        _ = await unprivileged_client_3.execute_graphql(
            query=self.approve_query,
            variables={"data": {"id": str(proposed_change.id), "decision": "APPROVE"}},
            branch_name=branch1.name,
        )

        response = await client.execute_graphql(
            query=self.check_for_changes_query,
            branch_name="main",
        )
        assert response["CoreProposedChangeCheckForChanges"]["ok"]

        # Verify the two first approvals were revoked
        pc_updated = await client.get(kind=CoreProposedChange, id=proposed_change.id, prefetch_relationships=True)
        assert len(pc_updated.approvals.peers) == 1
        approver_id = (await unprivileged_client_3.get_user())["AccountProfile"]["id"]
        assert pc_updated.approvals.peers[0].peer.approver.id == approver_id
