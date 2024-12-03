from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.tasks import process_jinja2, process_transform, query_transform_targets
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import COLOR, TSHIRT, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestComputedAttribute(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def data(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        default_branch: Branch,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
        git_repos_source_dir_module_scope: Path,
    ) -> dict[str, Node]:
        await load_schema(db, schema=SchemaRoot(nodes=[COLOR, TSHIRT]), update_db=True)

        c1 = await Node.init(db=db, schema="TestingColor")
        await c1.new(
            db=db, name="Sunset", description="A bold, vibrant orange that captures the warmth of the setting sun."
        )
        await c1.save(db=db)
        c2 = await Node.init(db=db, schema="TestingColor")
        await c2.new(db=db, name="Ocean", description="Deep and calming, like the endless expanse of the ocean.")
        await c2.save(db=db)

        c3 = await Node.init(db=db, schema="TestingColor")
        await c3.new(db=db, name="Ivory", description="A soft off-white, smooth and classic.")
        await c3.save(db=db)

        t1 = await Node.init(db=db, schema="TestingTShirt")
        await t1.new(db=db, name="Explorer", color=c1)
        await t1.save(db=db)

        t2 = await Node.init(db=db, schema="TestingTShirt")
        await t2.new(db=db, name="Rouge", color=c3)
        await t2.save(db=db)

        FileRepo(name="computed-attributes-functional", sources_directory=git_repos_source_dir_module_scope)
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={
                "name": "computed-attributes-functional",
                "location": f"{git_repos_source_dir_module_scope}/computed-attributes-functional",
            },
            branch=default_branch.name,
        )
        await client_repository.save()

        return {"c1": c1, "c2": c2, "c3": c3, "t1": t1, "t2": t2}

    async def test_description_after_color_change_jinja2(
        self, data: dict[str, Node], client: InfrahubClient, default_branch: Branch
    ) -> None:
        tshirt_1 = await client.get(kind="TestingTShirt", id=data["t1"].id)
        assert (
            tshirt_1.description.value
            == "A Sunset Explorer t-shirt. A bold, vibrant orange that captures the warmth of the setting sun."
        )

        tshirt_1.color = data["c2"].id
        await tshirt_1.save()

        # As we currently don't have a way to trigger on events within these tests we fire the automated workflow
        # manually
        await process_jinja2(
            branch_name=default_branch.name,
            node_kind="TestingTShirt",
            object_id=tshirt_1.id,
            computed_attribute_kind="TestingTShirt",
            computed_attribute_name="description",
            updated_fields=["color"],
        )

        tshirt_updated = await client.get(kind="TestingTShirt", id=data["t1"].id)
        assert (
            tshirt_updated.description.value
            == "A Ocean Explorer t-shirt. Deep and calming, like the endless expanse of the ocean."
        )

    async def test_description_after_chainging_color_description_transform(
        self, data: dict[str, Node], client: InfrahubClient, default_branch: Branch
    ) -> None:
        # As we currently don't have a way to trigger on events within these tests we fire the automated workflow
        # manually
        tshirt_obj = data["t2"]
        color_obj = data["c3"]

        tshirt_initial = await client.get(kind="TestingTShirt", id=tshirt_obj.id)

        await process_transform(
            branch_name=default_branch.name,
            object_id=tshirt_obj.id,
            node_kind="TestingTShirt",
            computed_attribute_name="pitch",
            computed_attribute_kind="TestingTShirt",
        )

        tshirt_first_pitch_allocation = await client.get(kind="TestingTShirt", id=tshirt_obj.id)

        color = await client.get(kind="TestingColor", id=color_obj.id)
        color.description.value = "A soft off-white, smooth and timeless."
        await color.save()

        await query_transform_targets(branch_name=default_branch.name, node_kind="TestingColor", object_id=color_obj.id)

        tshirt_altered_pitch_allocation = await client.get(kind="TestingTShirt", id=tshirt_obj.id)
        assert not tshirt_initial.pitch.value
        assert (
            tshirt_first_pitch_allocation.pitch.value
            == "Buy your Rouge t-shirt today. Look great in a soft off-white, smooth and classic."
        )
        assert (
            tshirt_altered_pitch_allocation.pitch.value
            == "Buy your Rouge t-shirt today. Look great in a soft off-white, smooth and timeless."
        )
