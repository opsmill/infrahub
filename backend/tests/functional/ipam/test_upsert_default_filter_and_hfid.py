import logging

from infrahub_sdk import InfrahubClient

from tests.helpers.test_app import TestInfrahubApp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

schema = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Person",
            "namespace": "Test",
            "default_filter": "firstname__value",
            "human_friendly_id": ["firstname__value", "lastname__value"],
            "attributes": [
                {"name": "firstname", "kind": "Text"},
                {"name": "lastname", "kind": "Text"},
            ],
        },
    ],
}


class TestUpsertWithBothHfidAndDefaulFilter(TestInfrahubApp):
    async def test_multiple_upsert(self, client: InfrahubClient) -> None:
        res = await client.schema.load([schema])
        assert len(res.errors) == 0, res.errors

        lastnames = ["Martin", "Dupont", "Doe"]
        for lastname in lastnames:
            person = await client.create("TestPerson", firstname="Clement", lastname=lastname)
            await person.save(allow_upsert=True)

        persons = await client.all(kind="TestPerson")
        assert len(persons) == 3
