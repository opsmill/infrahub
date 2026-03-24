from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.exceptions import GraphQLError

from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode

    from infrahub.core.branch.models import Branch
    from infrahub.database import InfrahubDatabase


class TestDeleteAgnosticRel(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def load_schema(self, client: InfrahubClient, car_person_branch_agnostic_schema: dict[str, Any]) -> None:
        await client.schema.load([car_person_branch_agnostic_schema])

    @pytest.fixture(scope="class")
    async def owner_1(self, client: InfrahubClient, load_schema: None) -> InfrahubNode:
        owner_1 = await client.create(kind="TestPerson", name="owner_1")
        await owner_1.save()
        return owner_1

    @pytest.fixture(scope="class")
    async def owner_2(self, client: InfrahubClient, load_schema: None) -> InfrahubNode:
        owner_2 = await client.create(kind="TestPerson", name="owner_2")
        await owner_2.save()
        return owner_2

    @pytest.fixture(scope="class")
    async def car(self, client: InfrahubClient, load_schema: None, owner_1: InfrahubNode) -> InfrahubNode:
        car = await client.create(kind="TestCar", name="car_name", agnostic_owner=owner_1)
        await car.save()
        return car

    @pytest.fixture(scope="class")
    async def car_2(self, client: InfrahubClient, load_schema: None, owner_2: InfrahubNode) -> InfrahubNode:
        car = await client.create(kind="TestCar", name="car_name_2", agnostic_owner=owner_2)
        await car.save()
        return car

    @pytest.fixture(scope="class")
    async def roofrack_2(self, client: InfrahubClient, load_schema: None, car_2: InfrahubNode) -> InfrahubNode:
        roofrack = await client.create(kind="TestRoofrack", size="big", car=car_2)
        await roofrack.save()
        return roofrack

    async def test_delete_agnostic_rel(
        self,
        client: InfrahubClient,
        load_schema: None,
        owner_1: InfrahubNode,
        owner_2: InfrahubNode,
        car: InfrahubNode,
    ) -> None:
        """
        Loads a car-person agnostic schema, then :
        - create a Car
        - link it to a Person
        - changes owner and retrieve the car.
        This test makes sure changing owner, involving deleting relationship with first owner, works correctly.
        See https://github.com/opsmill/infrahub/issues/5559.
        """
        car = await client.get(kind="TestCar", name__value="car_name", prefetch_relationships=True)
        car.agnostic_owner = owner_2
        await car.save()

        car = await client.get(kind="TestCar", name__value="car_name", prefetch_relationships=True)
        assert car.agnostic_owner.peer.name.value == "owner_2"

    async def test_delete_aware_mandatory_node_blocked(
        self, client: InfrahubClient, owner_2: InfrahubNode, car: InfrahubNode
    ) -> None:
        owner_2 = await client.get(kind="TestPerson", name__value="owner_2")

        with pytest.raises(GraphQLError) as exc:
            await owner_2.delete()

        assert (
            f"Cannot delete TestPerson '{owner_2.id}'. It is linked to mandatory relationship agnostic_owner on node TestCar '{car.id}'"
            in exc.value.message
        )

    async def test_delete_agnostic_node(self, client: InfrahubClient, owner_2: InfrahubNode, car: InfrahubNode) -> None:
        car = await client.get(kind="TestCar", name__value="car_name", prefetch_relationships=True)
        await car.delete()

        owner_2 = await client.get(kind="TestPerson", name__value=owner_2.name.value, prefetch_relationships=True)
        assert len(owner_2.cars.peers) == 0

    async def test_delete_aware_node_with_agnostic_parent_blocked(
        self, client: InfrahubClient, car_2: InfrahubNode, roofrack_2: InfrahubNode
    ) -> None:
        car_2 = await client.get(kind="TestCar", name__value=car_2.name.value, prefetch_relationships=True)

        with pytest.raises(GraphQLError) as exc:
            await car_2.delete()

        assert (
            f"Cannot delete TestCar '{car_2.id}'. It is linked to mandatory relationship car on node TestRoofrack '{roofrack_2.id}'"
            in exc.value.message
        )

    async def test_delete_branch(
        self, client: InfrahubClient, car_2: InfrahubNode, roofrack_2: InfrahubNode, db: InfrahubDatabase
    ) -> None:
        branch2 = await client.branch.create(branch_name="branch2")

        owner = await client.create(kind="TestPerson", name="owner", branch=branch2.name)
        await owner.save()

        car = await client.create(kind="TestCar", name="car_name", agnostic_owner=owner)
        await car.save()

        deleted_ok = await client.branch.delete(branch_name=branch2.name)
        assert deleted_ok

        # Make sure owner has been correctly deleted
        query = """
        MATCH (n: Node)
        WHERE n.uuid = $node_uuid
        RETURN n
        """

        results = await db.execute_query(query=query, params={"node_uuid": owner.id})
        assert len(results) == 0

        # Make sure all nodes are connected to root

        query = """
        MATCH (n: Node)
        WHERE NOT exists((n)-[:IS_PART_OF]-(:Root))
        RETURN n
        """

        results = await db.execute_query(query=query)
        assert len(results) == 0

    async def test_delete_branch_with_aware_owner_relationship(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        car_2: InfrahubNode,
        roofrack_2: InfrahubNode,
        db: InfrahubDatabase,
    ) -> None:
        aware_owner = await client.create(kind="TestPerson", name="aware_owner", branch=default_branch.name)
        await aware_owner.save()
        agnostic_owner = await client.create(kind="TestPerson", name="agnostic_owner", branch=default_branch.name)
        await agnostic_owner.save()

        branch2 = await client.branch.create(branch_name="branch2")

        car = await client.create(
            kind="TestCar", name="radical_car", aware_owner=aware_owner, agnostic_owner=agnostic_owner
        )
        await car.save()

        deleted_ok = await client.branch.delete(branch_name=branch2.name)
        assert deleted_ok

        # Verify no orphaned Relationships
        query = """
        MATCH (rel:Relationship)-[:IS_RELATED]-(peer:Node)
        WITH DISTINCT rel, peer
        WITH rel, count(*) AS num_peers
        WHERE num_peers < 2
        RETURN rel
        """

        results = await db.execute_query(query=query)
        assert len(results) == 0
