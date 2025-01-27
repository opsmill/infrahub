from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient


class TestDeleteAgnosticRel(TestInfrahubApp):
    async def test_delete_agnostic_rel(
        self, client: InfrahubClient, car_person_branch_agnostic_schema: dict[str, Any]
    ) -> None:
        """
        Loads a car-person agnostic schema, then :
        - create a Car
        - link it to a Person
        - changes owner and retrieve the car.
        This test makes sure changing owner, involving deleting relationship with first owner, works correctly.
        See https://github.com/opsmill/infrahub/issues/5559.
        """

        await client.schema.load([car_person_branch_agnostic_schema])

        owner_1 = await client.create(kind="TestPerson", name="owner_1")
        await owner_1.save()

        car = await client.create(kind="TestCar", name="car_name", owner=owner_1)
        await car.save()

        car = await client.get(kind="TestCar", name__value="car_name", prefetch_relationships=True)

        owner_2 = await client.create(kind="TestPerson", name="owner_2")
        await owner_2.save()

        car.owner = owner_2
        await car.save()

        car = await client.get(kind="TestCar", name__value="car_name", prefetch_relationships=True)
        assert car.owner.peer.name.value == "owner_2"
