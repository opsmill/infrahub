import pytest
from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.exceptions import BranchNotFound
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.schema import SchemaRoot

from .conftest import InfrahubTestClient

# pylint: disable=unused-argument


class TestInfrahubClient:
    @pytest.fixture(scope="class")
    async def test_client(self) -> InfrahubTestClient:
        registry.delete_all()

        # pylint: disable=import-outside-toplevel
        from infrahub.server import app

        return InfrahubTestClient(app)

    @pytest.fixture
    async def client(self, test_client: InfrahubTestClient) -> InfrahubClient:
        config = Config(username="admin", password="infrahub", requester=test_client.async_request)
        return await InfrahubClient.init(config=config)

    @pytest.fixture(scope="class")
    async def base_dataset(self, db: InfrahubDatabase, test_client: InfrahubTestClient, builtin_org_schema: SchemaRoot):
        config = Config(username="admin", password="infrahub", requester=test_client.async_request)
        client = await InfrahubClient.init(config=config)
        success, response = await client.schema.load(schemas=[builtin_org_schema.dict()])
        assert response is None
        assert success

        await create_branch(branch_name="branch01", db=db)

        query_string = """
        query {
            branch {
                id
                name
            }
        }
        """
        obj1 = await Node.init(schema="CoreGraphQLQuery", db=db)
        await obj1.new(db=db, name="test_query2", description="test query", query=query_string)
        await obj1.save(db=db)

        obj2 = await Node.init(schema="CoreRepository", db=db)
        await obj2.new(
            db=db,
            name="repository1",
            description="test repository",
            location="git@github.com:mock/test.git",
        )
        await obj2.save(db=db)

        obj3 = await Node.init(schema="CoreTransformJinja2", db=db)
        await obj3.new(
            db=db,
            name="rfile1",
            description="test rfile",
            template_path="mytemplate.j2",
            repository=obj2,
            query=obj1,
        )
        await obj3.save(db=db)

        obj4 = await Node.init(schema="CoreTransformPython", db=db)
        await obj4.new(
            db=db,
            name="transform01",
            description="test transform01",
            file_path="mytransformation.py",
            class_name="Transform01",
            query=obj1,
            repository=obj2,
            rebase=False,
        )
        await obj4.save(db=db)

    async def test_query_branches(self, client: InfrahubClient, init_db_base, base_dataset):
        branches = await client.branch.all()
        main = await client.branch.get(branch_name="main")

        with pytest.raises(BranchNotFound):
            await client.branch.get(branch_name="not-found")

        assert main.name == "main"
        assert "main" in branches
        assert "branch01" in branches

    async def test_branch_delete(self, client: InfrahubClient, init_db_base, base_dataset, db):
        async_branch = "async-delete-branch"
        await create_branch(branch_name=async_branch, db=db)
        pre_delete = await client.branch.all()
        await client.branch.delete(async_branch)
        post_delete = await client.branch.all()
        assert async_branch in pre_delete.keys()
        assert async_branch not in post_delete.keys()

    async def test_get_all(self, client: InfrahubClient, init_db_base, base_dataset):
        obj1 = await client.create(kind="BuiltinLocation", name="jfk1", description="new york", type="site")
        await obj1.save()

        obj2 = await client.create(kind="BuiltinLocation", name="sfo1", description="san francisco", type="site")
        await obj2.save()

        nodes = await client.all(kind="BuiltinLocation")
        assert len(nodes) == 2
        assert isinstance(nodes[0], InfrahubNode)
        assert sorted([node.name.value for node in nodes]) == ["jfk1", "sfo1"]  # type: ignore[attr-defined]

    async def test_get_one(self, client: InfrahubClient, init_db_base, base_dataset):
        obj1 = await client.create(kind="BuiltinLocation", name="jfk2", description="new york", type="site")
        await obj1.save()

        obj2 = await client.create(kind="BuiltinLocation", name="sfo2", description="san francisco", type="site")
        await obj2.save()

        node1 = await client.get(kind="BuiltinLocation", id=obj1.id)
        assert isinstance(node1, InfrahubNode)
        assert node1.name.value == "jfk2"  # type: ignore[attr-defined]

        node2 = await client.get(kind="BuiltinLocation", id="jfk2")
        assert isinstance(node2, InfrahubNode)
        assert node2.name.value == "jfk2"  # type: ignore[attr-defined]

    async def test_get_generic(self, client: InfrahubClient, db: InfrahubDatabase, init_db_base):
        nodes = await client.all(kind="CoreNode")
        assert len(nodes)

    async def test_get_generic_fragment(self, client: InfrahubClient, db: InfrahubDatabase, init_db_base):
        nodes = await client.all(kind="LineageSource", fragment=True, exclude=["type"])
        assert len(nodes)
        assert nodes[0].typename == "CoreAccount"
        assert nodes[0].name.value is not None  # type: ignore[attr-defined]

    async def test_get_generic_filter_source(self, client: InfrahubClient, db: InfrahubDatabase, init_db_base):
        admin = await client.get(kind="CoreAccount", name__value="admin")

        obj1 = await client.create(
            kind="BuiltinLocation", name={"value": "jfk3", "source": admin.id}, description="new york", type="site"
        )
        await obj1.save()

        nodes = await client.filters(kind="CoreNode", any__source__id=admin.id)
        assert len(nodes) == 1
        assert nodes[0].typename == "BuiltinLocation"
        assert nodes[0].id == obj1.id

    async def test_get_related_nodes(self, client: InfrahubClient, db: InfrahubDatabase, init_db_base):
        nodes = await client.all(kind="CoreRepository")
        assert len(nodes) == 1
        repo = nodes[0]

        assert repo.transformations.peers == []  # type: ignore[attr-defined]
        await repo.transformations.fetch()  # type: ignore[attr-defined]
        assert len(repo.transformations.peers) == 2  # type: ignore[attr-defined]
