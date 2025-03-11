import time
import uuid

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.batch import InfrahubBatch
from mypy.checkexpr import defaultdict

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from tests.helpers.test_app import TestInfrahubApp


class TestBenchmarkBatches(TestInfrahubApp):
    @pytest.fixture
    def timing_collector(self):
        timing_info = defaultdict(dict)
        yield timing_info
        # Print the collected timing information in a grid format at the end of all test runs
        print("\nTiming information for all test runs:")
        # Dynamically generate column headers
        all_keys = set()
        for batch_size in timing_info:
            all_keys.update(timing_info[batch_size].keys())
        all_keys = sorted(all_keys)

        # Calculate the maximum width for each column
        col_widths = {
            key: max(len(key), len(timing_info[batch_size].get(key, "N/A")))
            for key in all_keys
            for batch_size in timing_info
        }

        # Print header row
        header = f"{'Batch Size':<10} | " + " | ".join(f"{key:<{col_widths[key]}}" for key in all_keys)
        print(header)
        print("=" * (10 + sum(col_widths.values()) + 3 * len(all_keys)))

        # Print data rows
        for batch_size in sorted(timing_info.keys()):
            row = f"{batch_size:<10} | "
            for key in all_keys:
                elapsed_time = timing_info[batch_size].get(key, "N/A")
                row += f"{elapsed_time:<{col_widths[key]}} | "
            print(row)

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

        params: dict = {"kinds": kinds}

        await db.execute_query(query=query, params=params, name="delete_nodes")

    @pytest.fixture
    async def load_schema(self, client, branch, car_person_schema_unique_owner):
        res = await client.schema.load([car_person_schema_unique_owner], branch=branch.name)
        assert len(res.errors) == 0, res.errors

    @pytest.mark.parametrize("allow_upsert", [True, False])
    @pytest.mark.parametrize("batch_size", [100])
    def test_create_nodes_batch(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        load_schema,
        branch: Branch,
        allow_upsert: bool,
        batch_size: int,
        aio_benchmark,
        exec_async,
        timing_collector,
    ) -> None:
        batch = exec_async(
            self.create_car_batch,
            batch_size=batch_size,
            client=client,
            allow_upsert=allow_upsert,
            db=db,
            branch=branch.name,
        )

        # Raises a "loop already running" error
        aio_benchmark(
            execute_batch,
            infrahub_batch=batch,
            branch=branch.name,
            allow_upsert=allow_upsert,
            batch_size=batch_size,
            timing_collector=timing_collector,
        )


async def execute_batch(infrahub_batch, branch, allow_upsert, batch_size, timing_collector):
    start_time = time.time()
    async for _, _ in infrahub_batch.execute():
        pass

    # Store data in order to have a manual report containing all test runs results
    elapsed_time = time.time() - start_time
    key = f"{branch}, allow_upsert={allow_upsert}"
    timing_collector[batch_size][key] = f"{elapsed_time:.2f}s"
