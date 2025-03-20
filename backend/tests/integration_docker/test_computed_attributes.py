from asyncio import sleep
from pathlib import Path

import pytest
import yaml
from infrahub_sdk import InfrahubClient
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

CURRENT_DIRECTORY = Path(__file__).parent.resolve()


class TestComputedAttributes(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    async def test_load_schema(self, client: InfrahubClient) -> None:
        """Prepare the schema"""
        with Path(CURRENT_DIRECTORY / "test_files/computed_tshirt.yml").open(encoding="utf-8") as file:  # noqa: ASYNC230
            computed_tshirt = yaml.safe_load(file.read())

        tshirt_schema = await client.schema.load(schemas=[computed_tshirt], wait_until_converged=True)
        assert tshirt_schema.schema_updated
        # Validate that the schema is in sync after loading the device and interface schema
        assert await client.schema.in_sync()

    async def test_computed_attribute_update(self, client: InfrahubClient) -> None:
        """Validate that the computed attribute is registered and created and also updated correctly."""
        first_desc = "A Sunset Explorer t-shirt. A bold, vibrant orange that captures the warmth of the setting sun."
        final_desc = (
            "A Sunset Explorer t-shirt. A striking, lively shade of orange that radiates the golden warmth of a sunset."
        )
        data = {
            "name": "Sunset",
            "description": "A bold, vibrant orange that captures the warmth of the setting sun.",
        }
        color1 = await client.create(kind="TestingColor", data=data)
        await color1.save()
        data = {
            "name": "Ember Glow",
            "description": "A deep, fiery red-orange reminiscent of smoldering embers at dusk.",
        }
        color2 = await client.create(kind="TestingColor", data=data)
        await color2.save()

        data = {
            "name": "Explorer",
            "color": color1,
        }
        tshirt1 = await client.create(kind="TestingTShirt", data=data)
        await tshirt1.save()

        tshirt1_initial = await client.get(kind="TestingTShirt", id=tshirt1.id)
        color1_initial = await client.get(kind="TestingColor", id=color1.id)

        assert tshirt1_initial.description.value == first_desc

        color1_initial.description.value = (
            "A striking, lively shade of orange that radiates the golden warmth of a sunset."
        )
        await color1_initial.save()

        for _ in range(10):
            # Give the computed attribute triggers a little while to run
            tshirt1_updated = await client.get(kind="TestingTShirt", id=tshirt1.id)
            if tshirt1_updated.description.value != first_desc:
                break
            await sleep(1)

        assert tshirt1_updated.description.value == final_desc

        tshirt1_second_update = await client.get(kind="TestingTShirt", id=tshirt1.id)
        tshirt1_second_update.color = color2
        await tshirt1_second_update.save()

        expected_description = (
            "A Ember Glow Explorer t-shirt. A deep, fiery red-orange reminiscent of smoldering embers at dusk."
        )

        for _ in range(10):
            # Give the computed attribute triggers a little while to run
            tshirt1_second_update_result = await client.get(kind="TestingTShirt", id=tshirt1.id)
            if tshirt1_second_update_result.description.value == expected_description:
                break
            await sleep(1)

        assert tshirt1_second_update_result.description.value == expected_description
