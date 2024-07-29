from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.server import app

from infrahub_sdk import Config, InfrahubClientSync
from infrahub_sdk.constants import InfrahubClientMode
from infrahub_sdk.exceptions import BranchNotFoundError
from infrahub_sdk.node import InfrahubNodeSync
from infrahub_sdk.playback import JSONPlayback
from infrahub_sdk.recorder import JSONRecorder
from infrahub_sdk.schema import ProfileSchema

from .conftest import InfrahubTestClient

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub.database import InfrahubDatabase


# pylint: disable=unused-argument


class TestInfrahubClientSync:
    @pytest.fixture(scope="class")
    async def test_client(self) -> InfrahubTestClient:
        return InfrahubTestClient(app)

    @pytest.fixture
    def client(self, test_client: InfrahubTestClient):
        config = Config(
            username="admin",
            password="infrahub",
            sync_requester=test_client.sync_request,
        )
        return InfrahubClientSync(config=config)

    @pytest.fixture(scope="class")
    async def base_dataset(self, db: InfrahubDatabase, test_client: InfrahubTestClient, builtin_org_schema):
        config = Config(username="admin", password="infrahub", sync_requester=test_client.sync_request)
        client = InfrahubClientSync(config=config)
        response = client.schema.load(schemas=[builtin_org_schema])
        assert not response.errors

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
        )
        await obj4.save(db=db)

    async def test_query_branches(self, client: InfrahubClientSync, init_db_base, base_dataset):
        branches = client.branch.all()
        main = client.branch.get(branch_name="main")

        with pytest.raises(BranchNotFoundError):
            client.branch.get(branch_name="not-found")

        assert main.name == "main"
        assert "main" in branches
        assert "branch01" in branches

    async def test_branch_delete(self, client: InfrahubClientSync, init_db_base, base_dataset, db):
        async_branch = "async-delete-branch"
        await create_branch(branch_name=async_branch, db=db)

        pre_delete = client.branch.all()
        client.branch.delete(async_branch)
        post_delete = client.branch.all()
        assert async_branch in pre_delete.keys()
        assert async_branch not in post_delete.keys()

    async def test_get_all(self, client: InfrahubClientSync, init_db_base, base_dataset):
        obj1 = client.create(kind="BuiltinLocation", name="jfk1", description="new york", type="site")
        obj1.save()

        obj2 = client.create(kind="BuiltinLocation", name="sfo1", description="san francisco", type="site")
        obj2.save()

        nodes = client.all(kind="BuiltinLocation")
        assert len(nodes) == 2
        assert isinstance(nodes[0], InfrahubNodeSync)
        assert sorted([node.name.value for node in nodes]) == ["jfk1", "sfo1"]  # type: ignore[attr-defined]

    async def test_get_one(self, client: InfrahubClientSync, init_db_base, base_dataset):
        obj1 = client.create(kind="BuiltinLocation", name="jfk2", description="new york", type="site")
        obj1.save()

        obj2 = client.create(kind="BuiltinLocation", name="sfo2", description="san francisco", type="site")
        obj2.save()

        node1 = client.get(kind="BuiltinLocation", id=obj1.id)
        assert isinstance(node1, InfrahubNodeSync)
        assert node1.name.value == "jfk2"  # type: ignore[attr-defined]

        node2 = client.get(kind="BuiltinLocation", id="jfk2")
        assert isinstance(node2, InfrahubNodeSync)
        assert node2.name.value == "jfk2"  # type: ignore[attr-defined]

    async def test_filters_partial_match(self, client: InfrahubClientSync, init_db_base, base_dataset):
        nodes = client.filters(kind="BuiltinLocation", name__value="jfk")
        assert not nodes

        nodes = client.filters(kind="BuiltinLocation", partial_match=True, name__value="jfk")
        assert len(nodes) == 2
        assert isinstance(nodes[0], InfrahubNodeSync)
        assert sorted([node.name.value for node in nodes]) == ["jfk1", "jfk2"]  # type: ignore[attr-defined]

    async def test_get_generic(self, client: InfrahubClientSync, init_db_base):
        nodes = client.all(kind="CoreNode")
        assert len(nodes)

    async def test_get_generic_fragment(self, client: InfrahubClientSync, init_db_base, base_dataset):
        nodes = client.all(kind="CoreGenericAccount", fragment=True, exclude=["type"])
        assert len(nodes)
        assert nodes[0].typename == "CoreAccount"
        assert nodes[0].name.value is not None  # type: ignore[attr-defined]

    async def test_get_generic_filter_source(self, client: InfrahubClientSync, init_db_base, base_dataset):
        admin = client.get(kind="CoreAccount", name__value="admin")

        obj1 = client.create(
            kind="BuiltinLocation", name={"value": "jfk3", "source": admin.id}, description="new york", type="site"
        )
        obj1.save()

        nodes = client.filters(kind="CoreNode", any__source__id=admin.id)
        assert len(nodes) == 1
        assert nodes[0].typename == "BuiltinLocation"
        assert nodes[0].id == obj1.id

    async def test_get_related_nodes(self, client: InfrahubClientSync, init_db_base, base_dataset):
        nodes = client.all(kind="CoreRepository")
        assert len(nodes) == 1
        repo = nodes[0]

        assert repo.transformations.peers == []  # type: ignore[attr-defined]
        repo.transformations.fetch()  # type: ignore[attr-defined]
        assert len(repo.transformations.peers) == 2  # type: ignore[attr-defined]

    def test_tracking_mode(self, client: InfrahubClientSync, db: InfrahubDatabase, init_db_base, base_dataset):
        tag_names = ["BLUE", "RED", "YELLOW"]
        orgname = "Acme"

        def create_org_with_tag(clt: InfrahubClientSync, nbr_tags: int):
            tags = []
            for idx in range(nbr_tags):
                obj = clt.create(kind="BuiltinTag", name=f"tracking-{tag_names[idx]}")
                obj.save(allow_upsert=True)
                tags.append(obj)

            org = clt.create(kind="TestOrganization", name=orgname, tags=tags)
            org.save(allow_upsert=True)

        # First execution, we create one org with 3 tags
        nbr_tags = 3
        with client.start_tracking(params={"orgname": orgname}, delete_unused_nodes=True) as clt:
            create_org_with_tag(clt=clt, nbr_tags=nbr_tags)

        assert client.mode == InfrahubClientMode.DEFAULT
        group = client.get(
            kind="CoreStandardGroup", name__value=client.group_context._generate_group_name(), include=["members"]
        )
        assert len(group.members.peers) == 4
        tags = client.all(kind="BuiltinTag")
        assert len(tags) == 3

        # Second execution, we create one org with 2 tags but we don't delete the third one
        nbr_tags = 2
        with client.start_tracking(params={"orgname": orgname}, delete_unused_nodes=False) as clt:
            create_org_with_tag(clt=clt, nbr_tags=nbr_tags)

        assert client.mode == InfrahubClientMode.DEFAULT
        group = client.get(
            kind="CoreStandardGroup", name__value=client.group_context._generate_group_name(), include=["members"]
        )
        assert len(group.members.peers) == 3
        tags = client.all(kind="BuiltinTag")
        assert len(tags) == 3

        # Third execution, we create one org with 1 tag and we delete the second one
        nbr_tags = 1
        with client.start_tracking(params={"orgname": orgname}, delete_unused_nodes=True) as clt:
            create_org_with_tag(clt=clt, nbr_tags=nbr_tags)

        assert client.mode == InfrahubClientMode.DEFAULT
        group = client.get(
            kind="CoreStandardGroup", name__value=client.group_context._generate_group_name(), include=["members"]
        )
        assert len(group.members.peers) == 2

        tags = client.all(kind="BuiltinTag")
        assert len(tags) == 2

        # Forth one, validate that the group will not be updated if there is an exception
        nbr_tags = 3
        with pytest.raises(ValueError):
            with client.start_tracking(params={"orgname": orgname}, delete_unused_nodes=True) as clt:
                create_org_with_tag(clt=clt, nbr_tags=nbr_tags)
                raise ValueError("something happened")

        assert client.mode == InfrahubClientMode.DEFAULT
        group = client.get(
            kind="CoreStandardGroup", name__value=client.group_context._generate_group_name(), include=["members"]
        )
        assert len(group.members.peers) == 2

    def test_recorder_with_playback(
        self, client: InfrahubClientSync, db: InfrahubDatabase, init_db_base, base_dataset, tmp_path: Path
    ):
        client.config.custom_recorder = JSONRecorder(directory=str(tmp_path))
        nodes = client.all(kind="CoreRepository")

        playback_config = JSONPlayback(directory=str(tmp_path))
        config = Config(
            address=client.config.address,
            sync_requester=playback_config.sync_request,
        )
        playback = InfrahubClientSync(config=config)
        recorded_nodes = playback.all(kind="CoreRepository")

        assert len(nodes) == 1
        assert nodes == recorded_nodes
        assert recorded_nodes[0].name.value == "repository1"

    def test_profile(self, client: InfrahubClientSync, db: InfrahubDatabase, init_db_base, base_dataset):
        profile_schema_kind = "ProfileBuiltinStatus"
        profile_schema = client.schema.get(kind=profile_schema_kind)
        assert isinstance(profile_schema, ProfileSchema)

        profile1 = client.create(
            kind=profile_schema_kind,
            profile_name="profile1",
            profile_priority=1000,
            description="description in profile",
        )
        profile1.save()

        obj = client.create(kind="BuiltinStatus", name="planned", profiles=[profile1])
        obj.save()

        obj1 = client.get(kind="BuiltinStatus", id=obj.id)
        assert obj1.description.value == "description in profile"
