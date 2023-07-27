import pytest
from fastapi.testclient import TestClient

from infrahub_client import InfrahubClient

FILE_CONTENT_01 = """
    any content
    another content
    """


class TestObjectStore:
    @pytest.fixture(scope="class")
    async def test_client(self):
        # pylint: disable=import-outside-toplevel

        from infrahub.server import app

        return TestClient(app)

    @pytest.fixture
    async def client(self, test_client):
        return await InfrahubClient.init(test_client=test_client)

    async def test_upload_and_get(self, client: InfrahubClient):
        response = await client.object_store.upload(content=FILE_CONTENT_01)

        assert sorted(list(response.keys())) == ["checksum", "identifier"]
        assert response["checksum"] == "aa19b96860ec59a73906dd8660bb3bad"
        assert response["identifier"]

        content = await client.object_store.get(identifier=response["identifier"])
        assert content == FILE_CONTENT_01
