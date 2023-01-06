from infrahub_client import InfrahubClient, BranchData, RepositoryData


async def test_init_client():

    client = await InfrahubClient.init()

    assert True


async def test_get_branches(mock_branches_list_query):

    client = await InfrahubClient.init(address="http://mock")
    branches = await client.get_list_branches()

    assert len(branches) == 2
    assert isinstance(branches["main"], BranchData)


async def test_get_repositories(mock_branches_list_query, mock_repositories_query):

    client = await InfrahubClient.init(address="http://mock")
    repos = await client.get_list_repositories()

    expected_response = RepositoryData(
        id="9486cfce-87db-479d-ad73-07d80ba96a0f",
        name="infrahub-demo-edge",
        location="git@github.com:dgarros/infrahub-demo-edge.git",
        branches={"cr1234": "bbbbbbbbbbbbbbbbbbbb", "main": "aaaaaaaaaaaaaaaaaaaa"},
    )
    assert len(repos) == 1
    assert repos["infrahub-demo-edge"] == expected_response
