from __future__ import annotations

from asyncio import sleep
from typing import TYPE_CHECKING

import pytest
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
    """Existing nodes should get their display_label backfilled after the schema is updated to add one."""

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

    @pytest.fixture(scope="class")
    async def color_before(self, client: InfrahubClient, schema_without_display_label: dict) -> str:
        """Load schema without display_label and create a node."""
        response = await client.schema.load(schemas=[schema_without_display_label], wait_until_converged=True)
        assert response.schema_updated

        color = await client.create(kind="TestingColor", name="Red", description="A warm color")
        await color.save()
        return color.id

    @pytest.fixture(scope="class")
    async def color_after(self, client: InfrahubClient, color_before: str, schema_with_display_label: dict) -> str:
        """Update schema to add display_label and create a second node."""
        response = await client.schema.load(schemas=[schema_with_display_label], wait_until_converged=True)
        assert response.schema_updated

        color = await client.create(kind="TestingColor", name="Blue", description="A cool color")
        await color.save()
        return color.id

    async def _get_display_labels(self, client: InfrahubClient) -> dict[str, str]:
        result = await client.execute_graphql(query=QUERY_DISPLAY_LABELS)
        return {e["node"]["id"]: e["node"]["display_label"] for e in result["TestingColor"]["edges"]}

    async def test_node_created_before_display_label_has_repr(self, client: InfrahubClient, color_before: str) -> None:
        """A node created without display_label in the schema should fall back to repr()."""
        await wait_for_all_tasks_to_be_completed(client=client)
        labels = await self._get_display_labels(client)
        assert labels[color_before] == f"TestingColor(ID: {color_before})"

    async def test_node_created_after_display_label_has_value(self, client: InfrahubClient, color_after: str) -> None:
        """A node created after display_label is added should have the correct value."""
        labels = await self._get_display_labels(client)
        assert labels[color_after] == "Blue"

    async def test_backfill_updates_preexisting_node(self, client: InfrahubClient, color_after: str) -> None:
        """After the async backfill completes, all nodes should have correct display_labels."""
        await wait_for_all_tasks_to_be_completed(client=client)
        labels = await self._get_display_labels(client)
        assert set(labels.values()) == {"Red", "Blue"}
