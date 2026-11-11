"""Saves whose human-friendly ID combines two numbers drawn from pools in the same request."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from tests.helpers.number_pool import add_pool_range
from tests.helpers.schema import load_schema

from .helpers import execute, refused_write

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

SLOT = NodeSchema(
    name="Slot",
    namespace="Testing",
    include_in_menu=False,
    label="Slot",
    human_friendly_id=["rack__value", "slot__value"],
    attributes=[
        AttributeSchema(name="rack", kind="Number", optional=True),
        AttributeSchema(name="slot", kind="Number", optional=True),
        AttributeSchema(name="note", kind="Text", optional=True),
    ],
)

CREATE_SLOT = """
mutation CreateSlot($data: TestingSlotCreateInput!) {
    TestingSlotCreate(data: $data) { ok object { id } }
}
"""

UPSERT_SLOT = """
mutation UpsertSlot($data: TestingSlotUpsertInput!) {
    TestingSlotUpsert(data: $data) { ok object { id } }
}
"""


async def new_slot_pool(db: InfrahubDatabase, name: str, attribute: str, start: int, end: int) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(db=db, name=name, node=SLOT.kind, node_attribute=attribute, start_range=start, end_range=end)
    await pool.save(db=db)
    await add_pool_range(db=db, pool=pool, start=start, end=end)
    return pool


async def held_slot(db: InfrahubDatabase, branch: Branch, rack: int, slot: int) -> str:
    data = await execute(
        db=db,
        branch=branch,
        source=CREATE_SLOT,
        variables={"data": {"rack": {"value": rack}, "slot": {"value": slot}, "note": {"value": "held by hand"}}},
    )
    assert data
    return str(data["TestingSlotCreate"]["object"]["id"])


class TestTwoPooledNumbersInOneHumanFriendlyId:
    """Each test draws from pools of its own, so their numbers never meet."""

    @pytest.fixture(scope="class")
    async def slot_branch(self, db: InfrahubDatabase, main_branch: Branch) -> Branch:
        await load_schema(db=db, schema=SchemaRoot(nodes=[SLOT]))
        main_branch.update_schema_hash()
        return main_branch

    async def test_a_create_drawing_both_numbers_another_object_holds_names_both_pools(
        self, db: InfrahubDatabase, slot_branch: Branch
    ) -> None:
        racks = await new_slot_pool(db=db, name="racks-create", attribute="rack", start=1, end=9)
        slots = await new_slot_pool(db=db, name="slots-create", attribute="slot", start=21, end=29)
        holding_id = await held_slot(db=db, branch=slot_branch, rack=1, slot=21)

        message = await refused_write(
            db=db,
            branch=slot_branch,
            source=CREATE_SLOT,
            variables={"data": {"rack": {"from_pool": {"id": racks.id}}, "slot": {"from_pool": {"id": slots.id}}}},
        )

        assert message == (
            "Violates uniqueness constraint 'rack-slot': the 'racks-create' pool allocated 1 for rack and the "
            f"'slots-create' pool allocated 21 for slot, which object '1, 21' ('{holding_id}') already holds. Attach "
            f"those numbers to their pools by updating object '{holding_id}' with rack value 1 and from_pool "
            "'racks-create', and slot value 21 and from_pool 'slots-create', or change them, then retry."
        )
        assert [node.get_id() for node in await NodeManager.query(db=db, schema=SLOT.kind, branch=slot_branch)] == [
            holding_id
        ]

    async def test_an_upsert_drawing_both_numbers_another_object_holds_leaves_that_object_alone(
        self, db: InfrahubDatabase, slot_branch: Branch
    ) -> None:
        racks = await new_slot_pool(db=db, name="racks-upsert", attribute="rack", start=11, end=19)
        slots = await new_slot_pool(db=db, name="slots-upsert", attribute="slot", start=31, end=39)
        holding_id = await held_slot(db=db, branch=slot_branch, rack=11, slot=31)

        message = await refused_write(
            db=db,
            branch=slot_branch,
            source=UPSERT_SLOT,
            variables={
                "data": {
                    "rack": {"from_pool": {"id": racks.id}},
                    "slot": {"from_pool": {"id": slots.id}},
                    "note": {"value": "upserted"},
                }
            },
        )

        assert message == (
            "Violates uniqueness constraint 'rack-slot': the 'racks-upsert' pool allocated 11 for rack and the "
            f"'slots-upsert' pool allocated 31 for slot, which object '11, 31' ('{holding_id}') already holds. "
            f"Attach those numbers to their pools by updating object '{holding_id}' with rack value 11 and from_pool "
            "'racks-upsert', and slot value 31 and from_pool 'slots-upsert', or change them, then retry."
        )
        holding_object = await NodeManager.get_one(db=db, id=holding_id, branch=slot_branch, raise_on_error=True)
        assert holding_object.get_attribute(name="note").value == "held by hand"
