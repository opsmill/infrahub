from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.tasks import process_jinja2
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from tests.helpers.schema import COLOR, TSHIRT, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
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
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
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

        t1 = await Node.init(db=db, schema="TestingTShirt")
        await t1.new(db=db, name="Explorer", color=c1)
        await t1.save(db=db)

        return {"c1": c1, "c2": c2, "t1": t1}

    async def test_description_after_color_change(
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
        # manually here
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
