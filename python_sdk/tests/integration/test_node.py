import pytest
from fastapi.testclient import TestClient

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub_client import InfrahubClient
from infrahub_client.exceptions import NodeNotFound
from infrahub_client.node import InfrahubNode

# pylint: disable=unused-argument


class TestInfrahubNode:
    @pytest.fixture(scope="class")
    async def test_client(self):
        # pylint: disable=import-outside-toplevel
        from infrahub.main import app

        return TestClient(app)

    @pytest.fixture
    async def client(self, test_client):
        return await InfrahubClient.init(test_client=test_client)

    async def test_node_create(self, client: InfrahubClient, init_db_base, location_schema):
        data = {"name": {"value": "JFK1"}, "description": {"value": "JFK Airport"}, "type": {"value": "SITE"}}
        node = InfrahubNode(client=client, schema=location_schema, data=data)
        await node.save()

        assert node.id is not None

    async def test_node_delete_client(self, session, client: InfrahubClient, init_db_base, location_schema):
        data = {"name": {"value": "ARN"}, "description": {"value": "Arlanda Airport"}, "type": {"value": "SITE"}}
        node = InfrahubNode(client=client, schema=location_schema, data=data)
        await node.save()
        nodedb_pre_delete = await NodeManager.get_one(
            id=node.id, session=session, include_owner=True, include_source=True
        )

        await node.delete()
        nodedb_post_delete = await NodeManager.get_one(
            id=node.id, session=session, include_owner=True, include_source=True
        )
        assert nodedb_pre_delete
        assert nodedb_pre_delete.id
        assert not nodedb_post_delete

    async def test_node_delete_node(self, session, client: InfrahubClient, init_db_base, location_schema):
        obj = await Node.init(session=session, schema="Account")
        await obj.new(session=session, name="delete-my-account", type="Git")
        await obj.save(session=session)
        node_pre_delete = await client.get(kind="Account", name__value="delete-my-account")
        assert node_pre_delete
        assert node_pre_delete.id
        await node_pre_delete.delete()
        with pytest.raises(NodeNotFound):
            await client.get(kind="Account", name__value="delete-my-account")

    async def test_node_create_with_relationships(
        self,
        session,
        client: InfrahubClient,
        init_db_base,
        tag_blue: Node,
        tag_red: Node,
        repo01: Node,
        gqlquery01: Node,
    ):
        data = {
            "name": {"value": "rfile01"},
            "template_path": {"value": "mytemplate.j2"},
            "query": gqlquery01.id,
            "template_repository": {"id": repo01.id},
            "tags": [{"id": tag_blue.id}, tag_red.id],
        }

        node = await client.create(kind="RFile", data=data)
        await node.save()

        assert node.id is not None

        nodedb = await NodeManager.get_one(id=node.id, session=session, include_owner=True, include_source=True)
        assert nodedb.name.value == node.name.value  # type: ignore[attr-defined]
        querydb = await nodedb.query.get_peer(session=session)
        assert node.query.id == querydb.id  # type: ignore[attr-defined]

    async def test_node_create_with_properties(
        self,
        session,
        client: InfrahubClient,
        init_db_base,
        tag_blue: Node,
        tag_red: Node,
        repo01: Node,
        gqlquery01: Node,
        first_account: Node,
    ):
        data = {
            "name": {"value": "rfile02", "is_protected": True, "source": first_account.id, "owner": first_account.id},
            "template_path": {"value": "mytemplate.j2"},
            "query": {"id": gqlquery01.id},  # "source": first_account.id, "owner": first_account.id},
            "template_repository": {"id": repo01.id},  # "source": first_account.id, "owner": first_account.id},
            "tags": [{"id": tag_blue.id}, tag_red.id],
        }

        node = await client.create(kind="RFile", data=data)
        await node.save()

        assert node.id is not None

        nodedb = await NodeManager.get_one(id=node.id, session=session, include_owner=True, include_source=True)
        assert nodedb.name.value == node.name.value  # type: ignore[attr-defined]
        assert nodedb.name.is_protected is True

    async def test_node_update(
        self, session, client: InfrahubClient, init_db_base, tag_blue: Node, tag_red: Node, repo99: Node
    ):
        node = await client.get(kind="Repository", name__value="repo99")
        assert node.id is not None

        node.name.value = "repo95"  # type: ignore[attr-defined]
        node.tags.add(tag_blue.id)  # type: ignore[attr-defined]
        node.tags.add(tag_red.id)  # type: ignore[attr-defined]
        await node.save()

        nodedb = await NodeManager.get_one(id=node.id, session=session, include_owner=True, include_source=True)
        assert nodedb.name.value == "repo95"
        tags = await nodedb.tags.get(session=session)
        assert len(tags) == 2
