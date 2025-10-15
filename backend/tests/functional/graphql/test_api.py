from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestPreviousVersions(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA, update_db=True)

        p1 = await Node.init(db=db, schema="TestingPerson")
        await p1.new(db=db, name="John")
        await p1.save(db=db)
        p2 = await Node.init(db=db, schema="TestingPerson")
        await p2.new(db=db, name="Jane")
        await p2.save(db=db)

    async def test_query_at_previous_schema(self, initial_dataset: str, client: InfrahubClient) -> None:
        time_before = Timestamp()

        query = """
        query {
            TestingPerson {
                count
                edges {
                    node {
                        id
                        display_label
                        name {
                            value
                        }
                        height {
                            value
                        }
                    }
                }
            }
        }
        """

        response = await client.execute_graphql(query=query)

        assert response["TestingPerson"]["count"] == 2

        john = [
            person["node"] for person in response["TestingPerson"]["edges"] if person["node"]["name"]["value"] == "John"
        ][0]
        jane = [
            person["node"] for person in response["TestingPerson"]["edges"] if person["node"]["name"]["value"] == "Jane"
        ][0]
        assert john["display_label"] == "John"
        assert jane["display_label"] == "Jane"

        creation = await client.schema.load(
            schemas=[
                {
                    "version": "1.0",
                    "nodes": [
                        {
                            "name": "Person",
                            "namespace": "Testing",
                            "default_filter": "name__value",
                            "display_label": "{{ name__value }} {{ height__value }}",
                            "attributes": [
                                {"name": "name", "kind": "Text", "unique": True},
                                {"name": "height", "kind": "Number", "optional": True},
                                {"name": "description", "kind": "Text", "optional": True},
                                {"name": "age", "kind": "Number", "optional": True},
                            ],
                            "inherit_from": ["LineageOwner", "LineageSource", "CoreArtifactTarget"],
                        },
                    ],
                }
            ]
        )
        assert creation.schema_updated

        # Since we don't run the prefect tasks to update existing display labels in the
        # functional tests we instead here update the height which will in turn
        # update the display labels
        john_sdk = await client.get(kind="TestingPerson", id=john["id"])
        john_sdk.height.value = 180
        await john_sdk.save()
        jane_sdk = await client.get(kind="TestingPerson", id=jane["id"])
        jane_sdk.height.value = 170
        await jane_sdk.save()

        response = await client.execute_graphql(query=query)

        assert response["TestingPerson"]["count"] == 2

        john = [
            person["node"] for person in response["TestingPerson"]["edges"] if person["node"]["name"]["value"] == "John"
        ][0]
        jane = [
            person["node"] for person in response["TestingPerson"]["edges"] if person["node"]["name"]["value"] == "Jane"
        ][0]
        assert john["display_label"] == "John 180"
        assert jane["display_label"] == "Jane 170"

        # Query before we updated the schema to validate that we can pull the latest schema
        response = await client.execute_graphql(query=query, at=time_before.to_string())

        assert response["TestingPerson"]["count"] == 2

        john = [
            person["node"] for person in response["TestingPerson"]["edges"] if person["node"]["name"]["value"] == "John"
        ][0]
        jane = [
            person["node"] for person in response["TestingPerson"]["edges"] if person["node"]["name"]["value"] == "Jane"
        ][0]
        assert john["display_label"] == "John"
        assert jane["display_label"] == "Jane"
