import pytest
from fastapi.testclient import TestClient

from infrahub.core.manager import NodeManager
from infrahub_client import InfrahubClient, InfrahubNode

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

    async def test_node_create_with_relationships(
        self, session, client: InfrahubClient, init_db_base, tag_blue, tag_red, repo01, gqlquery01
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
        assert nodedb.name.value == node.name.value
        querydb = await nodedb.query.get_peer(session=session)
        assert node.query.id == querydb.id

    async def test_node_update(self, session, client: InfrahubClient, init_db_base, tag_blue, tag_red, repo01):
        node = await client.get(kind="Repository", name__value="repo01")
        assert node.id is not None

        node.name.value = "repo02"
        node.tags.add(tag_blue.id)
        node.tags.add(tag_red.id)
        await node.save()

        nodedb = await NodeManager.get_one(id=node.id, session=session, include_owner=True, include_source=True)
        assert nodedb.name.value == "repo02"
        tags = await nodedb.tags.get(session=session)
        assert len(tags) == 2
