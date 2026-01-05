import uuid
from collections.abc import Callable
from typing import Any

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.batch import InfrahubBatch

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from tests.helpers.test_app import TestInfrahubApp


@pytest.mark.timeout(1800)  # Increase timeout as codspeed runs tests multiple times.
class TestBenchmarkNodeCreationBatch(TestInfrahubApp):
    async def create_car_batch(
        self,
        batch_size: int,
        client: InfrahubClient,
        allow_upsert: bool,
        branch: str,
        db: InfrahubDatabase,
    ) -> InfrahubBatch:
        # Reset database state to not alter benchmark
        await self.delete_nodes(db=db, kinds=["TestCar", "TestPerson"])

        batch = await client.create_batch()
        for _ in range(batch_size):
            # First create the owner of the car, that is part of car's uniqueness constraint.
            short_id = str(uuid.uuid4())[:8]
            person_name = f"person-{short_id}"
            person_node = await Node.init(db=db, schema="TestPerson", branch=branch)
            await person_node.new(db=db, name=person_name)
            await person_node.save(db=db)

            # Add the car to the batch.
            short_id = str(uuid.uuid4())[:8]
            car_name = f"car-{short_id}"
            car = await client.create(kind="TestCar", name=car_name, nbr_seats=4, owner=person_name, branch=branch)
            batch.add(task=car.save, node=car, allow_upsert=allow_upsert)

        return batch

    @staticmethod
    async def delete_nodes(db: InfrahubDatabase, kinds: list[str]) -> None:
        query = """
        MATCH (n)
        WHERE n.kind in $kinds
        DETACH DELETE n
        """

        params: dict[str, Any] = {"kinds": kinds}

        await db.execute_query(query=query, params=params, name="delete_nodes")

    @pytest.fixture
    async def load_schema(
        self, client: InfrahubClient, branch: Branch, car_person_schema_unique_owner: dict[str, Any]
    ) -> None:
        res = await client.schema.load([car_person_schema_unique_owner], branch=branch.name)
        assert len(res.errors) == 0, res.errors

    @pytest.mark.parametrize("allow_upsert", [True, False])
    @pytest.mark.parametrize("batch_size", [100])
    def test_create_nodes_batch(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        load_schema: None,
        branch: Branch,
        allow_upsert: bool,
        batch_size: int,
        aio_benchmark: Callable[..., Any],
        exec_async: Callable[..., Any],
    ) -> None:
        batch = exec_async(
            self.create_car_batch,
            batch_size=batch_size,
            client=client,
            allow_upsert=allow_upsert,
            db=db,
            branch=branch.name,
        )

        aio_benchmark(
            execute_batch,
            infrahub_batch=batch,
        )


async def execute_batch(infrahub_batch: InfrahubBatch) -> None:
    async for _, _ in infrahub_batch.execute():
        pass
