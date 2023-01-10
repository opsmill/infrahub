from infrahub_client import InfrahubClient

from infrahub.core.manager import NodeManager


async def test_query_branches(client, init_db_base, base_dataset):

    ifc = await InfrahubClient.init(test_client=client)
    branches = await ifc.get_list_branches()

    assert "main" in branches
    assert "branch01" in branches


async def test_create_graphql_query_main(client, session, init_db_base, base_dataset):

    query_string = """
    query {
        branch {
            id
            name
            is_data_only
        }
    }
    """
    branch_name = "main"

    queries = await NodeManager.query("GraphQLQuery", branch=branch_name, session=session)

    assert len(queries) == 1

    ifc = await InfrahubClient.init(test_client=client)
    query = await ifc.create_graphql_query(branch_name=branch_name, name="test_query", query=query_string)

    queries = await NodeManager.query("GraphQLQuery", branch=branch_name, session=session)
    assert len(queries) == 2
