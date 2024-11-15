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
        await p1.new(db=db, name="John", height=180)
        await p1.save(db=db)
        p2 = await Node.init(db=db, schema="TestingPerson")
        await p2.new(db=db, name="Jane", height=170)
        await p2.save(db=db)

    async def test_query_at_previous_schema(self, initial_dataset: str, client: InfrahubClient) -> None:
        time_before = Timestamp()

        query = """
        query {
            TestingPerson {
                edges {
                    node {
                        display_label
                    }
                }
            }
        }
        """

        response = await client.execute_graphql(query=query)

        assert response == {
            "TestingPerson": {
                "edges": [
                    {"node": {"display_label": "John"}},
                    {"node": {"display_label": "Jane"}},
                ],
            },
        }

        creation = await client.schema.load(
            schemas=[
                {
                    "version": "1.0",
                    "nodes": [
                        {
                            "name": "Person",
                            "namespace": "Testing",
                            "default_filter": "name__value",
                            "display_labels": ["name__value", "height__value"],
                            "attributes": [
                                {"name": "name", "kind": "Text", "unique": True},
                                {"name": "height", "kind": "Number", "optional": True},
                                {"name": "description", "kind": "Text", "optional": True},
                                {"name": "age", "kind": "Number", "optional": True},
                            ],
                            "inherit_from": ["LineageOwner", "LineageSource"],
                        },
                    ],
                }
            ]
        )
        assert creation.schema_updated
        response = await client.execute_graphql(query=query)
        assert response == {
            "TestingPerson": {
                "edges": [
                    {"node": {"display_label": "John 180"}},
                    {"node": {"display_label": "Jane 170"}},
                ],
            },
        }

        # Query before we updated the schema to validate that we can pull the latest schema
        response = await client.execute_graphql(query=query, at=time_before.to_string())
        assert response == {
            "TestingPerson": {
                "edges": [
                    {"node": {"display_label": "John"}},
                    {"node": {"display_label": "Jane"}},
                ],
            },
        }
