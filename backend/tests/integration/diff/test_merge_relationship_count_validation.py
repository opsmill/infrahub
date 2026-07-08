"""Merge-time validation of relationship-count constraints.

These cover cases where an individually-valid branch produces an invalid post-merge
configuration that pre-merge constraint validation must reject (or that the merge's own
conflict handling must prevent).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestMergeCardinalityOneCrossBranch(TestInfrahubApp):
    """The same cardinality-one relationship pointed at different peers on each branch."""

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> dict[str, str]:
        await load_schema(db, schema=CAR_SCHEMA)

        manufacturer = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await manufacturer.new(db=db, name="Koenigsegg")
        await manufacturer.save(db=db)
        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175)
        await john.save(db=db)
        richard = await Node.init(schema=TestKind.PERSON, db=db)
        await richard.new(db=db, name="Richard", height=180)
        await richard.save(db=db)
        sarah = await Node.init(schema=TestKind.PERSON, db=db)
        await sarah.new(db=db, name="Sarah", height=170)
        await sarah.save(db=db)
        jesko = await Node.init(schema=TestKind.CAR, db=db)
        await jesko.new(db=db, name="Jesko", color="Red", owner=john, manufacturer=manufacturer)
        await jesko.save(db=db)

        return {"car_id": jesko.id, "richard_id": richard.id, "sarah_id": sarah.id}

    async def test_cross_branch_cardinality_one_never_exceeds_one(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: dict[str, str],
        client: InfrahubClient,
    ) -> None:
        """Two branches set the same optional cardinality-one relationship to different peers.

        Whichever way it is handled (conflict rejection, resolution, or count validation), main
        must never end up with two peers on a cardinality-one relationship.
        """
        branch = await client.branch.create(branch_name="set_previous_owner")
        car_on_branch = await NodeManager.get_one(db=db, id=initial_dataset["car_id"], branch=branch.name)
        assert car_on_branch
        await car_on_branch.get_relationship("previous_owner").update(db=db, data={"id": initial_dataset["richard_id"]})
        await car_on_branch.save(db=db)

        car_on_main = await NodeManager.get_one(db=db, id=initial_dataset["car_id"], branch=default_branch)
        assert car_on_main
        await car_on_main.get_relationship("previous_owner").update(db=db, data={"id": initial_dataset["sarah_id"]})
        await car_on_main.save(db=db)

        with contextlib.suppress(GraphQLError):
            await client.branch.merge(branch_name=branch.name)

        merged_car = await NodeManager.get_one(db=db, id=initial_dataset["car_id"], branch=default_branch)
        assert merged_car
        # The direct branch merge rejects the cross-branch conflict, so main keeps its own peer (Sarah)
        # and never ends up with two peers on the cardinality-one relationship.
        previous_owners = await merged_car.get_relationship("previous_owner").get_relationships(db=db)
        assert len(previous_owners) == 1
        assert previous_owners[0].get_peer_id() == initial_dataset["sarah_id"]
