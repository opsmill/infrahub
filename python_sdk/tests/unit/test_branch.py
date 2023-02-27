from infrahub_client.branch import BranchData


async def test_get_branches(client, mock_branches_list_query):  # pylint: disable=unused-argument
    branches = await client.branch.all()

    assert len(branches) == 2
    assert isinstance(branches["main"], BranchData)
