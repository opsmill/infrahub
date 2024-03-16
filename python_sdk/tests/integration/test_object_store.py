import pytest
from infrahub.server import app

from infrahub_sdk import Config, InfrahubClient

from .conftest import InfrahubTestClient

FILE_CONTENT_01 = """
    any content
    another content
    """


class TestObjectStore:
    @pytest.fixture(scope="class")
    async def test_client(self):
        return InfrahubTestClient(app)

    @pytest.fixture
    async def client(self, test_client):
        config = Config(username="admin", password="infrahub", requester=test_client.async_request)
        return await InfrahubClient.init(config=config)

    async def test_upload_and_get(self, client: InfrahubClient):
        response = await client.object_store.upload(content=FILE_CONTENT_01)

        assert sorted(list(response.keys())) == ["checksum", "identifier"]
        assert response["checksum"] == "aa19b96860ec59a73906dd8660bb3bad"
        assert response["identifier"]

        content = await client.object_store.get(identifier=response["identifier"])
        assert content == FILE_CONTENT_01
