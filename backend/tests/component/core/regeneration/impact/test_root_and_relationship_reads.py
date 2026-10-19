from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.regeneration.impact import get_field_level_impacted_subscribers
from infrahub.core.regeneration.models import TargetSelection
from tests.constants import TestKind
from tests.helpers.diff_summary import node_diff
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

from .helpers import SUBSCRIBER_KIND, query_report

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

# The root car is pinned by id, and the query reads the names of every car of its owner: a car is read
# both at the root and through the ``owner`` and ``cars`` relationships.
QUERY_CAR_WITH_ITS_OWNER_CARS = """
query GetImpactCarWithOwnerCars($ids: [ID!]!) {
    TestingCar(ids: $ids) {
        edges {
            node {
                name { value }
                owner { node { cars { edges { node { name { value } } } } } }
            }
        }
    }
}
"""

# The root car is pinned by id, and the query reads the names of the cars its previous owner owns. A car
# without a previous owner is reached back through no relationship, so only its root read selects it.
QUERY_CAR_WITH_ITS_PREVIOUS_OWNER_CARS = """
query GetImpactCarWithPreviousOwnerCars($ids: [ID!]!) {
    TestingCar(ids: $ids) {
        edges {
            node {
                name { value }
                previous_owner { node { cars { edges { node { name { value } } } } } }
            }
        }
    }
}
"""


class TestRootAndRelationshipReadImpact(TestInfrahubApp):
    """Narrow a change on a kind the query reads both at its root and through a relationship.

    Two owners: the first owns the first car, a group member, and a second car that is no member; the
    second owner owns the third car, the member of another group.
    """

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=CAR_SCHEMA, update_db=True)

        manufacturer = await Node.init(db=db, schema=TestKind.MANUFACTURER)
        await manufacturer.new(db=db, name="maker")
        await manufacturer.save(db=db)

        owner = await Node.init(db=db, schema=TestKind.PERSON)
        await owner.new(db=db, name="owner-1")
        await owner.save(db=db)

        other_owner = await Node.init(db=db, schema=TestKind.PERSON)
        await other_owner.new(db=db, name="owner-2")
        await other_owner.save(db=db)

        cars = []
        for name, car_owner in (("car-1", owner), ("car-2", owner), ("car-3", other_owner)):
            car = await Node.init(db=db, schema=TestKind.CAR)
            await car.new(db=db, name=name, color="red", owner=car_owner, manufacturer=manufacturer)
            await car.save(db=db)
            cars.append(car)
        first_car, second_car, third_car = cars

        stored_query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await stored_query.new(
            db=db,
            name="GetImpactCarWithOwnerCars",
            query=QUERY_CAR_WITH_ITS_OWNER_CARS,
            models=[TestKind.CAR, TestKind.PERSON],
        )
        await stored_query.save(db=db)

        subscribers = []
        for member, name in ((first_car, "first-car-artifact"), (third_car, "third-car-artifact")):
            subscriber = await Node.init(db=db, schema=TestKind.TAG)
            await subscriber.new(db=db, name=name)
            await subscriber.save(db=db)
            group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP)
            await group.new(
                db=db, name=f"{name}-targets", query=stored_query, members=[member], subscribers=[subscriber]
            )
            await group.save(db=db)
            subscribers.append(subscriber)
        first_subscriber, third_subscriber = subscribers

        return {
            "first_car_id": first_car.id,
            "second_car_id": second_car.id,
            "third_car_id": third_car.id,
            "first_subscriber_id": first_subscriber.id,
            "third_subscriber_id": third_subscriber.id,
        }

    async def _resolve(
        self,
        *,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
        car_id: str,
        query: str = QUERY_CAR_WITH_ITS_OWNER_CARS,
    ) -> TargetSelection:
        return await get_field_level_impacted_subscribers(
            query_report=query_report(query, default_branch),
            diff_summary=[
                node_diff(node_id=car_id, kind=TestKind.CAR, branch=default_branch.name, field_names=["name"])
            ],
            query_branch=default_branch.name,
            subscriber_kind=SUBSCRIBER_KIND,
            every_target=[dataset["first_subscriber_id"], dataset["third_subscriber_id"]],
            client=client,
        )

    async def test_change_on_a_car_read_only_through_the_relationship_selects_the_reading_member(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """The second car is no group member: its change walks back through its owner to the first car."""
        resolved = await self._resolve(
            dataset=dataset, default_branch=default_branch, client=client, car_id=dataset["second_car_id"]
        )

        assert resolved == TargetSelection(ids=[dataset["first_subscriber_id"]])

    async def test_change_on_a_car_read_at_the_root_selects_its_own_member(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """The third car is the root of its own group and shares no owner with the first car."""
        resolved = await self._resolve(
            dataset=dataset, default_branch=default_branch, client=client, car_id=dataset["third_car_id"]
        )

        assert resolved == TargetSelection(ids=[dataset["third_subscriber_id"]])

    async def test_change_on_a_car_no_relationship_reaches_back_selects_its_own_member(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """The first car has no previous owner, so walking the relationship back from it reaches no member."""
        resolved = await self._resolve(
            dataset=dataset,
            default_branch=default_branch,
            client=client,
            car_id=dataset["first_car_id"],
            query=QUERY_CAR_WITH_ITS_PREVIOUS_OWNER_CARS,
        )

        assert resolved == TargetSelection(ids=[dataset["first_subscriber_id"]])
