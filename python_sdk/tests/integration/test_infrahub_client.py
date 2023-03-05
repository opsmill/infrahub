import pytest
from fastapi.testclient import TestClient

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub_client import InfrahubClient, InfrahubNode

# pylint: disable=unused-argument


class TestInfrahubClient:
    @pytest.fixture(scope="class")
    async def test_client(self):
        # pylint: disable=import-outside-toplevel
        from infrahub.main import app

        return TestClient(app)

    @pytest.fixture
    async def client(self, test_client):
        return await InfrahubClient.init(test_client=test_client)

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

        obj4 = await Node.init(schema="TransformPython", session=session)
        await obj4.new(
            session=session,
            name="transform01",
            description="test transform01",
            file_path="mytransformation.py",
            class_name="Transform01",
            query=obj1,
            url="tf01",
            repository=obj2,
            rebase=False,
        )
        await obj4.save(session=session)

    async def test_query_branches(self, client: InfrahubClient, init_db_base, base_dataset):
        branches = await client.branch.all()

        assert "main" in branches
        assert "branch01" in branches

    async def test_query_graphql_queries(self, client: InfrahubClient, init_db_base, base_dataset):
        queries = await client.get_list_graphql_queries(branch_name="main")

        assert "test_query2" in queries

    async def test_create_graphql_query_main(self, client: InfrahubClient, session, init_db_base, base_dataset):
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

        await client.create_graphql_query(branch_name=branch_name, name="test_query", query=query_string)

        queries = await NodeManager.query("GraphQLQuery", branch=branch_name, session=session)
        assert len(queries) == 2

    async def test_get_all(self, client: InfrahubClient, session, init_db_base):
        obj1 = await Node.init(schema="Location", session=session)
        await obj1.new(session=session, name="jfk1", description="new york", type="site")
        await obj1.save(session=session)

        obj2 = await Node.init(schema="Location", session=session)
        await obj2.new(session=session, name="sfo1", description="san francisco", type="site")
        await obj2.save(session=session)

        nodes = await client.all(kind="Location")
        assert len(nodes) == 2
        assert isinstance(nodes[0], InfrahubNode)
        assert sorted([node.name.value for node in nodes]) == ["jfk1", "sfo1"]

    async def test_get_one(self, client: InfrahubClient, session, init_db_base):
        obj1 = await Node.init(schema="Location", session=session)
        await obj1.new(session=session, name="jfk1", description="new york", type="site")
        await obj1.save(session=session)

        obj2 = await Node.init(schema="Location", session=session)
        await obj2.new(session=session, name="sfo1", description="san francisco", type="site")
        await obj2.save(session=session)

        node = await client.get(kind="Location", id=obj1.id)
        assert isinstance(node, InfrahubNode)
        assert node.name.value == "jfk1"

    async def test_query_rfiles(self, client: InfrahubClient, init_db_base, base_dataset):
        rfiles = await client.get_list_rfiles(branch_name="main")

        assert "rfile1" in rfiles

    async def test_create_rfile_main(self, client: InfrahubClient, session, init_db_base, base_dataset):
        branch_name = "main"

        rfiles = await NodeManager.query("RFile", branch=branch_name, session=session)
        repositories = await NodeManager.query("Repository", branch=branch_name, session=session)
        queries = await NodeManager.query("GraphQLQuery", branch=branch_name, session=session)

        assert len(rfiles) == 1

        await client.create_rfile(
            branch_name=branch_name,
            name="rfile1",
            description="test rfile2",
            template_path="mytemplate.j2",
            template_repository=str(repositories[0].id),
            query=str(queries[0].name.value),
        )

        rfiles = await NodeManager.query("RFile", branch=branch_name, session=session)
        assert len(rfiles) == 2

    async def test_query_transform_python(self, client: InfrahubClient, init_db_base, base_dataset):
        transforms = await client.get_list_transform_python(branch_name="main")

        assert "transform01" in transforms

    async def test_create_transform_python_main(self, client: InfrahubClient, session, init_db_base, base_dataset):
        branch_name = "main"

        transforms = await NodeManager.query("TransformPython", branch=branch_name, session=session)
        repositories = await NodeManager.query("Repository", branch=branch_name, session=session)
        queries = await NodeManager.query("GraphQLQuery", branch=branch_name, session=session)

        assert len(transforms) == 1

        await client.create_transform_python(
            branch_name=branch_name,
            name="transform02",
            description="test fransform02",
            file_path="mytransformation02.py",
            class_name="Transform02",
            url="transform02",
            query=str(queries[0].name.value),
            repository=str(repositories[0].id),
        )

        transforms = await NodeManager.query("TransformPython", branch=branch_name, session=session)
        assert len(transforms) == 2
