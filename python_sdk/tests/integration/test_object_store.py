from infrahub_sdk import Config, InfrahubClient

from tests.helpers.test_app import TestInfrahubApp


FILE_CONTENT_01 = """
    any content
    another content
    """


class TestObjectStore(TestInfrahubApp):
    async def test_upload_and_get(self, client: InfrahubClient):
        response = await client.object_store.upload(content=FILE_CONTENT_01)

        assert sorted(list(response.keys())) == ["checksum", "identifier"]
        assert response["checksum"] == "aa19b96860ec59a73906dd8660bb3bad"
        assert response["identifier"]

        content = await client.object_store.get(identifier=response["identifier"])
        assert content == FILE_CONTENT_01
