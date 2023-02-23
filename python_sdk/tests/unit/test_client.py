from infrahub_client import BranchData, InfrahubClient, Query, RepositoryData


async def test_init_client():
    await InfrahubClient.init()

    assert True


async def test_get_branches(mock_branches_list_query):  # pylint: disable=unused-argument
    client = await InfrahubClient.init(address="http://mock")
    branches = await client.get_list_branches()

    assert len(branches) == 2
    assert isinstance(branches["main"], BranchData)


async def test_get_repositories(mock_branches_list_query, mock_repositories_query):  # pylint: disable=unused-argument
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


async def test_query_rendering_no_vars():
    data01 = {
        "device": {"name": {"value": None}, "description": {"value": None}, "interfaces": {"name": {"value": None}}}
    }
    query = Query(data=data01)

    expected_query = """
query {
    device {
        name {
            value
        }
        description {
            value
        }
        interfaces {
            name {
                value
            }
        }
    }
}
"""
    assert query.render_first_line() == "query {"
    assert query.render() == expected_query


async def test_query_rendering_with_vars():
    data01 = {
        "device": {
            "@filters": {"name__value": "$name"},
            "name": {"value": None},
            "description": {"value": None},
            "interfaces": {"@filters": {"enabled__value": "$enabled"}, "name": {"value": None}},
        }
    }
    query = Query(data=data01, variables={"name": str, "enabled": bool})

    expected_query = """
query ($name: String!, $enabled: Boolean!) {
    device(name__value: $name) {
        name {
            value
        }
        description {
            value
        }
        interfaces(enabled__value: $enabled) {
            name {
                value
            }
        }
    }
}
"""
    assert query.render_first_line() == "query ($name: String!, $enabled: Boolean!) {"
    assert query.render() == expected_query
