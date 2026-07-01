from __future__ import annotations

from asyncio import sleep, timeout
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

from tests.helpers.schema.color import COLOR
from tests.helpers.schema.tshirt import TSHIRT

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub_sdk import InfrahubClient

COLOR_KIND = "TestingColor"
TSHIRT_KIND = "TestingTShirt"


def _schema_dict() -> dict:
    """Reuse the TShirt and Color helpers, dropping the transform-python attribute (it needs a transform repo) and making color optional."""
    tshirt = TSHIRT.duplicate()
    tshirt.generate_template = False
    tshirt.attributes = [attribute for attribute in tshirt.attributes if attribute.name != "pitch"]
    for relationship in tshirt.relationships:
        if relationship.name == "color":
            relationship.optional = True
    return {"version": "1.0", "nodes": [COLOR.model_dump(), tshirt.model_dump()]}


async def _wait_until(predicate: Callable[[], Awaitable[bool]], *, seconds: int = 120) -> None:
    async with timeout(seconds):
        while not await predicate():  # noqa: ASYNC110
            await sleep(2)


class TestMergeDeletePeerRecompute(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    def delete_peer_schema(self) -> dict:
        return _schema_dict()

    async def test_merge_survives_deleting_a_read_peer(self, client: InfrahubClient, delete_peer_schema: dict) -> None:
        """Merging a branch that deleted a read peer completes instead of erroring on the missing peer."""
        loaded = await client.schema.load(schemas=[delete_peer_schema], wait_until_converged=True)
        assert loaded.schema_updated

        color = await client.create(kind=COLOR_KIND, data={"name": "red", "description": "the red one"})
        await color.save()
        tshirt = await client.create(kind=TSHIRT_KIND, data={"name": "tee", "color": color})
        await tshirt.save()

        async def _reader_initial() -> bool:
            refreshed = await client.get(kind=TSHIRT_KIND, id=tshirt.id)
            return refreshed.display_label == "tee red"

        await _wait_until(_reader_initial)

        branch = await client.branch.create(branch_name="delete-peer-survives")
        color_on_branch = await client.get(kind=COLOR_KIND, id=color.id, branch=branch.name)
        await color_on_branch.delete()

        await client.branch.merge(branch_name=branch.name)

        refreshed = await client.get(kind=TSHIRT_KIND, id=tshirt.id)
        assert refreshed.name.value == "tee"
