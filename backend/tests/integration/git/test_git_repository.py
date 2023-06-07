import pytest
from fastapi.testclient import TestClient

from infrahub.core.initialization import first_time_initialization
from infrahub.core.node import Node
from infrahub.core.utils import count_relationships, delete_all_nodes
from infrahub.git import InfrahubRepository
from infrahub_client import InfrahubClient, NodeNotFound

# pylint: disable=unused-argument


class TestInfrahubClient:
    @pytest.fixture(scope="class")
    async def base_dataset(self, session):
        await delete_all_nodes(session=session)
        await first_time_initialization(session=session)

    @pytest.fixture(scope="class")
    async def test_client(self, base_dataset):
        # pylint: disable=import-outside-toplevel
        from infrahub.api import main

        return TestClient(main.app)

    @pytest.fixture
    async def client(self, test_client):
        return await InfrahubClient.init(test_client=test_client)

    @pytest.fixture
    async def repo(self, test_client, client, session, git_upstream_repo_10, git_repos_dir):
        # Create the repository in the Graph
        obj = await Node.init(schema="Repository", session=session)
        await obj.new(
            session=session,
            name=git_upstream_repo_10["name"],
            description="test repository",
            location="git@github.com:mock/test.git",
        )
        await obj.save(session=session)

        # Initialize the repository on the file system
        repo = await InfrahubRepository.new(
            id=obj.id,
            name=git_upstream_repo_10["name"],
            location=git_upstream_repo_10["path"],
        )

        repo.client = client

        return repo

    async def test_import_all_graphql_query(self, session, client: InfrahubClient, repo: InfrahubRepository):
        commit = repo.get_commit_value(branch_name="main")
        await repo.import_all_graphql_query(branch_name="main", commit=commit)

        queries = await client.all(kind="GraphQLQuery")
        assert len(queries) == 5

        # Validate if the function is idempotent, another import just after the first one shouldn't change anything
        nbr_relationships_before = await count_relationships(session=session)

        await repo.import_all_graphql_query(branch_name="main", commit=commit)
        assert await count_relationships(session=session) == nbr_relationships_before

        # 1. Modify a query to validate if its being properly updated
        # 2. Add a query that doesn't exist in GIt and validate that it's been deleted
        value_before_change = queries[0].query.value
        queries[0].query.value = "query myquery { location { edges { id }}}"
        await queries[0].save()

        obj = await Node.init(schema="GraphQLQuery", session=session)
        await obj.new(
            session=session,
            name="soontobedeletedquery",
            query="query soontobedeletedquery { location { edges { id }}}",
            repository=str(repo.id),
        )
        await obj.save(session=session)

        await repo.import_all_graphql_query(branch_name="main", commit=commit)

        modified_query = await client.get(kind="GraphQLQuery", id=queries[0].id)
        assert modified_query.query.value == value_before_change

        with pytest.raises(NodeNotFound):
            await client.get(kind="GraphQLQuery", id=obj.id) is None

    async def test_import_all_python_files(self, session, client: InfrahubClient, repo: InfrahubRepository):
        commit = repo.get_commit_value(branch_name="main")
        await repo.import_all_python_files(branch_name="main", commit=commit)

        checks = await client.all(kind="Check")
        assert len(checks) != 0

        transforms = await client.all(kind="TransformPython")
        assert len(transforms) != 0

        # Validate if the function is idempotent, another import just after the first one shouldn't change anything
        nbr_relationships_before = await count_relationships(session=session)

        await repo.import_all_python_files(branch_name="main", commit=commit)
        assert await count_relationships(session=session) == nbr_relationships_before

    async def test_import_all_yaml_files(self, session, client: InfrahubClient, repo: InfrahubRepository):
        commit = repo.get_commit_value(branch_name="main")
        await repo.import_all_yaml_files(branch_name="main", commit=commit)

        rfiles = await client.all(kind="RFile")
        assert len(rfiles) == 2

        # Validate if the function is idempotent, another import just after the first one shouldn't change anything
        nbr_relationships_before = await count_relationships(session=session)

        await repo.import_all_yaml_files(branch_name="main", commit=commit)
        assert await count_relationships(session=session) == nbr_relationships_before
