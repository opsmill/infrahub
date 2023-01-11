import pytest

from infrahub.main import app
from fastapi.testclient import TestClient

from infrahub_client import InfrahubClient
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.initialization import create_branch


class TestInfrahubClient:
    @pytest.fixture(scope="class")
    async def client(self):
        return TestClient(app)

    @pytest.fixture(scope="class")
    async def base_dataset(self, session):

        await create_branch(branch_name="branch01", session=session)

        query_string = """
        query {
            branch {
                id
                name
            }
        }
        """
        obj1 = await Node.init(schema="GraphQLQuery", session=session)
        await obj1.new(session=session, name="test_query2", description="test query", query=query_string)
        await obj1.save(session=session)

        obj2 = await Node.init(schema="Repository", session=session)
        await obj2.new(
            session=session, name="repository1", description="test repository", location="git@github.com:mock/test.git"
        )
        await obj2.save(session=session)

        obj3 = await Node.init(schema="RFile", session=session)
        await obj3.new(
            session=session,
            name="rfile1",
            description="test rfile",
            template_path="mytemplate.j2",
            template_repository=obj2,
            query=obj1,
        )
        await obj3.save(session=session)

    async def test_query_branches(self, client, init_db_base, base_dataset):

        ifc = await InfrahubClient.init(test_client=client)
        branches = await ifc.get_list_branches()

        assert "main" in branches
        assert "branch01" in branches

    async def test_query_graphql_queries(self, client, init_db_base, base_dataset):

        ifc = await InfrahubClient.init(test_client=client)
        queries = await ifc.get_list_graphql_queries(branch_name="main")

        assert "test_query2" in queries

    async def test_create_graphql_query_main(self, client, session, init_db_base, base_dataset):

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
        await ifc.create_graphql_query(branch_name=branch_name, name="test_query", query=query_string)

        queries = await NodeManager.query("GraphQLQuery", branch=branch_name, session=session)
        assert len(queries) == 2

    async def test_query_rfiles(self, client, init_db_base, base_dataset):

        ifc = await InfrahubClient.init(test_client=client)
        rfiles = await ifc.get_list_rfiles(branch_name="main")

        assert "rfile1" in rfiles

    async def test_create_rfile_main(self, client, session, init_db_base, base_dataset):

        branch_name = "main"

        rfiles = await NodeManager.query("RFile", branch=branch_name, session=session)
        repositories = await NodeManager.query("Repository", branch=branch_name, session=session)
        queries = await NodeManager.query("GraphQLQuery", branch=branch_name, session=session)

        assert len(rfiles) == 1

        ifc = await InfrahubClient.init(test_client=client)
        await ifc.create_rfile(
            branch_name=branch_name,
            name="rfile1",
            description="test rfile2",
            template_path="mytemplate.j2",
            template_repository=str(repositories[0].id),
            query=str(queries[0].name.value),
        )

        rfiles = await NodeManager.query("RFile", branch=branch_name, session=session)
        assert len(rfiles) == 2
