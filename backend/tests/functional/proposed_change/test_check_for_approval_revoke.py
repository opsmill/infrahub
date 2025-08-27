import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.exceptions import GraphQLError
from tests.helpers.test_app import TestInfrahubApp


class TestProposedChangeCheckForRevokeApprovals(TestInfrahubApp):
    async def test_raises_error(
        self,
        client: InfrahubClient,
    ) -> None:
        mutation = """
        mutation CoreProposedChangeCheckForApprovalRevoke($data: ProposedChangeCheckForApprovalRevokeInput!) {
            CoreProposedChangeCheckForApprovalRevoke(data: $data) {
                ok
            }
        }
        """

        with pytest.raises(GraphQLError) as exc:
            _ = await client.execute_graphql(
                query=mutation,
                variables={"data": {}},
                raise_for_error=True,
            )

        assert "Revoking existing approvals based on branch changes is an enterprise feature." in exc.value.message
