from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError

from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient


schema_number_parameters = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Application",
            "namespace": "Random",
            "include_in_menu": True,
            "attributes": [
                {
                    "name": "size",
                    "kind": "Number",
                    "parameters": {"min_value": 10, "max_value": 4094, "excluded_values": "12,14-16"},
                    "optional": False,
                }
            ],
        },
    ],
}


class TestNbParameters(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def load_schema(self, client: InfrahubClient) -> None:
        response = await client.schema.load(schemas=[schema_number_parameters])
        assert len(response.errors) == 0, response.errors

    async def test_min_max_value(self, client: InfrahubClient, load_schema) -> None:
        node = await client.create(kind="RandomApplication", size=5)
        with pytest.raises(GraphQLError) as exc:
            await node.save()
            assert "5 is lower than the minimum allowed value 10 at size" in exc.value.message

        node = await client.create(kind="RandomApplication", size=10_000)
        with pytest.raises(GraphQLError) as exc:
            await node.save()
            assert r"10000 is higher than the maximum allowed value 4096 at size" in exc.value.message

    async def test_excluded_values(self, client: InfrahubClient, load_schema) -> None:
        node = await client.create(kind="RandomApplication", size=12)
        with pytest.raises(GraphQLError) as exc:
            await node.save()
            assert "12 is in the excluded values at size" in exc.value.message

        node = await client.create(kind="RandomApplication", size=14)
        with pytest.raises(GraphQLError) as exc:
            await node.save()
            assert "14 is in the excluded range 14-16 at size" in exc.value.message

        node = await client.create(kind="RandomApplication", size=16)
        with pytest.raises(GraphQLError) as exc:
            await node.save()
            assert "16 is in the excluded range 14-16 at size" in exc.value.message

    async def test_create_attribute_successfully(self, client: InfrahubClient, load_schema) -> None:
        node = await client.create(kind="RandomApplication", size=13)
        await node.save()
