import pytest
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

from infrahub_sdk import Config, InfrahubClient, SchemaRoot
from infrahub_sdk.exceptions import NodeNotFound
from infrahub_sdk.node import InfrahubNode

from .conftest import InfrahubTestClient

# pylint: disable=unused-argument


class TestInfrahubNode:
    @pytest.fixture(scope="class")
    async def test_client(self):
        # pylint: disable=import-outside-toplevel

        from infrahub.server import app

        return InfrahubTestClient(app)

    @pytest.fixture
    async def client(self, test_client):
        config = Config(username="admin", password="infrahub", requester=test_client.async_request)
        return await InfrahubClient.init(config=config)

    @pytest.fixture(scope="class")
    async def load_builtin_schema(
        self, db: InfrahubDatabase, test_client: InfrahubTestClient, builtin_org_schema: SchemaRoot
    ):
        config = Config(username="admin", password="infrahub", requester=test_client.async_request)
        client = await InfrahubClient.init(config=config)
        success, response = await client.schema.load(schemas=[builtin_org_schema.dict()])
        assert response is None
        assert success

    async def test_node_create(self, client: InfrahubClient, init_db_base, load_builtin_schema, location_schema):
        data = {
            "name": {"value": "JFK1"},
            "description": {"value": "JFK Airport"},
            "type": {"value": "SITE"},
        }
        node = InfrahubNode(client=client, schema=location_schema, data=data)
        await node.save()

        assert node.id is not None

    async def test_node_delete_client(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        init_db_base,
        load_builtin_schema,
        location_schema,
    ):
        data = {
            "name": {"value": "ARN"},
            "description": {"value": "Arlanda Airport"},
            "type": {"value": "SITE"},
        }
        node = InfrahubNode(client=client, schema=location_schema, data=data)
        await node.save()
        nodedb_pre_delete = await NodeManager.get_one(id=node.id, db=db, include_owner=True, include_source=True)

        await node.delete()
        nodedb_post_delete = await NodeManager.get_one(id=node.id, db=db, include_owner=True, include_source=True)
        assert nodedb_pre_delete
        assert nodedb_pre_delete.id
        assert not nodedb_post_delete

    async def test_node_delete_node(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        init_db_base,
        load_builtin_schema,
        location_schema,
    ):
        obj = await Node.init(db=db, schema="CoreAccount")
        await obj.new(db=db, name="delete-my-account", type="Git", password="delete-my-password")
        await obj.save(db=db)
        node_pre_delete = await client.get(kind="CoreAccount", name__value="delete-my-account")
        assert node_pre_delete
        assert node_pre_delete.id
        await node_pre_delete.delete()
        with pytest.raises(NodeNotFound):
            await client.get(kind="CoreAccount", name__value="delete-my-account")

    async def test_node_create_with_relationships(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        init_db_base,
        load_builtin_schema,
        tag_blue: Node,
        tag_red: Node,
        repo01: Node,
        gqlquery01: Node,
    ):
        data = {
            "name": {"value": "rfile01"},
            "template_path": {"value": "mytemplate.j2"},
            "query": gqlquery01.id,
            "repository": {"id": repo01.id},
            "tags": [tag_blue.id, tag_red.id],
        }

        node = await client.create(kind="CoreRFile", data=data)
        await node.save()

        assert node.id is not None

        nodedb = await NodeManager.get_one(id=node.id, db=db, include_owner=True, include_source=True)
        assert nodedb.name.value == node.name.value  # type: ignore[attr-defined]
        querydb = await nodedb.query.get_peer(db=db)
        assert node.query.id == querydb.id  # type: ignore[attr-defined]

    async def test_node_update_payload_with_relationships(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        init_db_base,
        load_builtin_schema,
        tag_blue: Node,
        tag_red: Node,
        repo01: Node,
        gqlquery01: Node,
    ):
        data = {
            "name": "rfile10",
            "template_path": "mytemplate.j2",
            "query": gqlquery01.id,
            "repository": repo01.id,
            "tags": [tag_blue.id, tag_red.id],
        }
        schema = await client.schema.get(kind="CoreRFile", branch="main")
        create_payload = client.schema.generate_payload_create(
            schema=schema, data=data, source=repo01.id, is_protected=True
        )
        obj = await client.create(kind="CoreRFile", branch="main", **create_payload)
        await obj.save()

        assert obj.id is not None
        nodedb = await client.get(kind="CoreRFile", id=str(obj.id))

        input_data = nodedb._generate_input_data()["data"]["data"]
        assert input_data["name"]["value"] == "rfile10"
        # Validate that the source isn't a dictionary bit a reference to the repo
        assert input_data["name"]["source"] == repo01.id

    async def test_node_create_with_properties(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        init_db_base,
        load_builtin_schema,
        tag_blue: Node,
        tag_red: Node,
        repo01: Node,
        gqlquery01: Node,
        first_account: Node,
    ):
        data = {
            "name": {
                "value": "rfile02",
                "is_protected": True,
                "source": first_account.id,
                "owner": first_account.id,
            },
            "template_path": {"value": "mytemplate.j2"},
            "query": {"id": gqlquery01.id},  # "source": first_account.id, "owner": first_account.id},
            "repository": {"id": repo01.id},  # "source": first_account.id, "owner": first_account.id},
            "tags": [tag_blue.id, tag_red.id],
        }

        node = await client.create(kind="CoreRFile", data=data)
        await node.save()

        assert node.id is not None

        nodedb = await NodeManager.get_one(id=node.id, db=db, include_owner=True, include_source=True)
        assert nodedb.name.value == node.name.value  # type: ignore[attr-defined]
        assert nodedb.name.is_protected is True

    async def test_node_update(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        init_db_base,
        load_builtin_schema,
        tag_blue: Node,
        tag_red: Node,
        repo99: Node,
    ):
        node = await client.get(kind="CoreRepository", name__value="repo99")
        assert node.id is not None

        node.name.value = "repo95"  # type: ignore[attr-defined]
        node.tags.add(tag_blue.id)  # type: ignore[attr-defined]
        node.tags.add(tag_red.id)  # type: ignore[attr-defined]
        await node.save()

        nodedb = await NodeManager.get_one(id=node.id, db=db, include_owner=True, include_source=True)
        assert nodedb.name.value == "repo95"
        tags = await nodedb.tags.get(db=db)
        assert len(tags) == 2

    async def test_node_update_2(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        init_db_base,
        load_builtin_schema,
        tag_green: Node,
        tag_red: Node,
        tag_blue: Node,
        gqlquery02: Node,
        repo99: Node,
    ):
        node = await client.get(kind="CoreGraphQLQuery", name__value="query02")
        assert node.id is not None

        node.name.value = "query021"  # type: ignore[attr-defined]
        node.repository = repo99.id  # type: ignore[attr-defined]
        node.tags.add(tag_green.id)  # type: ignore[attr-defined]
        node.tags.remove(tag_red.id)  # type: ignore[attr-defined]
        await node.save()

        nodedb = await NodeManager.get_one(id=node.id, db=db, include_owner=True, include_source=True)
        repodb = await nodedb.repository.get_peer(db=db)
        assert repodb.id == repo99.id

        tags = await nodedb.tags.get(db=db)
        assert sorted([tag.peer_id for tag in tags]) == sorted([tag_green.id, tag_blue.id])

    async def test_node_update_3_idempotency(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        init_db_base,
        load_builtin_schema,
        tag_green: Node,
        tag_red: Node,
        tag_blue: Node,
        gqlquery03: Node,
        repo99: Node,
    ):
        node = await client.get(kind="CoreGraphQLQuery", name__value="query03")
        assert node.id is not None

        updated_query = f"\n\n{node.query.value}"  # type: ignore[attr-defined]
        node.name.value = "query031"  # type: ignore[attr-defined]
        node.query.value = updated_query  # type: ignore[attr-defined]
        first_update = node._generate_input_data(update=True)
        await node.save()
        nodedb = await NodeManager.get_one(id=node.id, db=db, include_owner=True, include_source=True)

        node = await client.get(kind="CoreGraphQLQuery", name__value="query031")

        node.name.value = "query031"  # type: ignore[attr-defined]
        node.query.value = updated_query  # type: ignore[attr-defined]

        second_update = node._generate_input_data(update=True)

        assert nodedb.query.value == updated_query  # type: ignore[attr-defined]
        assert "query" in first_update["data"]["data"]
        assert "value" in first_update["data"]["data"]["query"]
        assert first_update["variables"]
        assert "query" not in second_update["data"]["data"]
        assert not second_update["variables"]

    async def test_convert_node(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        location_schema,
        init_db_base,
        load_builtin_schema,
        location_cdg: Node,
    ):
        data = await location_cdg.to_graphql(db=db)
        node = InfrahubNode(client=client, schema=location_schema, data=data)

        # pylint: disable=no-member
        assert node.name.value == "cdg01"  # type: ignore[attr-defined]
