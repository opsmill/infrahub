from asyncio import sleep
from pathlib import Path

import pytest
import yaml
from infrahub_sdk import InfrahubClient
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo

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

        # Validate computed attribute defined on generic
        assert tshirt1_initial.name_code.value == "WEARABLE-EXPLORER"

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
        tshirt1_second_update_result.name.value = "Gardener"
        await tshirt1_second_update_result.save()

        expected_name_code = "WEARABLE-GARDENER"
        for _ in range(10):
            # Give the computed attribute triggers a little while to run
            tshirt1_last_update_result = await client.get(kind="TestingTShirt", id=tshirt1.id)
            if tshirt1_last_update_result.name_code.value == expected_name_code:
                break
            await sleep(1)

        assert tshirt1_last_update_result.name_code.value == expected_name_code

    async def test_transform_based_computed_attribute(self, client: InfrahubClient, remote_repos_dir: Path) -> None:
        src_directory = CURRENT_DIRECTORY / "test_files/repos/computed_attribute"
        repo = GitRepo(name="computed_attribute", src_directory=src_directory, dst_directory=remote_repos_dir)
        commit = repo._repo.git[repo._repo.git.head()]
        assert len(list(repo._repo.git.get_walker())) == 1
        assert commit.message.decode("utf-8") == "First commit"

        response = await repo.add_to_infrahub(client=client)
        assert response.get(f"{repo.type.value}Create", {}).get("ok")

        repos = await client.all(kind=repo.type)
        assert repos

        europe = await client.create(
            kind="LocationContinent",
            data={
                "name": "eu",
            },
        )
        await europe.save()
        sweden = await client.create(
            kind="LocationCountry",
            data={
                "name": "se",
                "parent": europe,
            },
        )
        await sweden.save()
        sth = await client.create(
            kind="LocationSite",
            data={
                "name": "sth",
                "parent": sweden,
            },
        )

        await sth.save()
        france = await client.create(
            kind="LocationCountry",
            data={
                "name": "france",
                "parent": europe,
            },
        )
        await france.save()
        par = await client.create(
            kind="LocationSite",
            data={
                "name": "par",
                "parent": france,
            },
        )
        await par.save()

        sth_router_1 = await client.create(
            kind="InfraDevice",
            data={
                "device_type": "router",
                "instance": 1,
                "site": sth,
            },
        )
        await sth_router_1.save()

        initial_name_router_1 = "se-sth-router-1"
        for _ in range(20):
            # Provide some delay for the triggers to be setup and the computed attribute to render
            sth_router_1_collected = await client.get(kind="InfraDevice", id=sth_router_1.id, include=["name"])
            if sth_router_1_collected.name.value:
                # I (@ogenstad) will investigate why this sleep is required for this test
                await sleep(1)
                break
            await sleep(1)

        assert sth_router_1_collected.name.value == initial_name_router_1
        sweden_name_update = await client.get(kind="LocationCountry", id=sweden.id)
        sweden_name_update.name.value = "swe"
        await sweden_name_update.save()

        swe_name_router_1 = "swe-sth-router-1"
        for _ in range(10):
            # Give the computed attribute triggers a little while to run
            sth_router_1_swe = await client.get(kind="InfraDevice", id=sth_router_1.id, include=["name"])
            if sth_router_1_swe.name.value == swe_name_router_1:
                break
            await sleep(1)

        assert sth_router_1_swe.name.value == swe_name_router_1
