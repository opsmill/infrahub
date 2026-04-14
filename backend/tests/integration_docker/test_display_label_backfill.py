from __future__ import annotations

from asyncio import sleep
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.task.models import TaskFilter, TaskState
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

from tests.helpers.schema import COLOR

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

QUERY_DISPLAY_LABELS = """
query {
    TestingColor {
        edges {
            node {
                id
                display_label
            }
        }
    }
}
"""


async def wait_for_all_tasks_to_be_completed(client: InfrahubClient) -> None:
    while (  # noqa: ASYNC110
        await client.task.count(filters=TaskFilter(state=[TaskState.PENDING, TaskState.RUNNING, TaskState.SCHEDULED]))
        > 0
    ):
        await sleep(1)


class TestDisplayLabelBackfillOnSchemaChange(TestInfrahubDockerClient):
    """IFC-2459: existing nodes should get their display_label backfilled
    after the schema is updated to add one."""

    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    def schema_without_display_label(self) -> dict:
        schema = COLOR.duplicate()
        schema.display_label = None
        return {"version": "1.0", "nodes": [schema.model_dump()]}

    @pytest.fixture(scope="class")
    def schema_with_display_label(self) -> dict:
        return {"version": "1.0", "nodes": [COLOR.model_dump()]}

    async def _get_display_labels(self, client: InfrahubClient) -> dict[str, str]:
        result = await client.execute_graphql(query=QUERY_DISPLAY_LABELS)
        return {e["node"]["id"]: e["node"]["display_label"] for e in result["TestingColor"]["edges"]}

    async def test_step01_load_schema_without_display_label(
        self, client: InfrahubClient, schema_without_display_label: dict
    ) -> None:
        response = await client.schema.load(schemas=[schema_without_display_label], wait_until_converged=True)
        assert response.schema_updated

    async def test_step02_create_node_and_verify_no_display_label(self, client: InfrahubClient) -> None:
        color = await client.create(kind="TestingColor", name="Red", description="A warm color")
        await color.save()

        await wait_for_all_tasks_to_be_completed(client=client)
        labels = await self._get_display_labels(client)
        # Display label is null, so defaults to repr()
        assert labels[color.id] == f"TestingColor(ID: {color.id})"

    async def test_step03_load_schema_with_display_label(
        self, client: InfrahubClient, schema_with_display_label: dict
    ) -> None:
        response = await client.schema.load(schemas=[schema_with_display_label], wait_until_converged=True)
        assert response.schema_updated

    async def test_step04_create_second_node(self, client: InfrahubClient) -> None:
        color = await client.create(kind="TestingColor", name="Blue", description="A cool color")
        await color.save()

        labels = await self._get_display_labels(client)
        assert labels[color.id] == "Blue"

    async def test_step05_display_labels_backfilled(self, client: InfrahubClient) -> None:
        await wait_for_all_tasks_to_be_completed(client=client)
        labels = await self._get_display_labels(client)
        assert set(labels.values()) == {"Red", "Blue"}
