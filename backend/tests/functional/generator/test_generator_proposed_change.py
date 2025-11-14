from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.protocols import CoreValidator
from infrahub_sdk.task.models import TaskFilter, TaskState
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

from infrahub.core.constants import InfrahubKind, ValidatorState
from infrahub.core.node import Node

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient
    from tests.adapters.message_bus import BusSimulator

    from infrahub.database import InfrahubDatabase


async def wait_for_pipeline_to_be_completed(
    client: InfrahubClient, branch: str, proposed_change_id: str, timeout: int = 15
) -> bool:
    for _ in range(timeout):
        validators = await client.filters(kind=CoreValidator, proposed_change__ids=[proposed_change_id], branch=branch)
        if all(validator.state.value == ValidatorState.COMPLETED.value for validator in validators):
            return True
        await asyncio.sleep(1)

    raise TimeoutError(f"Pipeline did not complete in {timeout} seconds")


async def wait_for_all_tasks_to_be_completed(client: InfrahubClient, timeout: int = 15) -> bool:
    for _ in range(timeout):
        tasks = await client.task.filter(
            filter=TaskFilter(state=[TaskState.RUNNING, TaskState.PENDING, TaskState.SCHEDULED])
        )
        if len(tasks) == 0:
            return True
        await asyncio.sleep(1)
    raise TimeoutError(f"All tasks did not complete in {timeout} seconds")


class TestMutationGenerator(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)

        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, age=25, description="The famous Joe Doe")
        await john.save(db=db)
        koenigsegg = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await koenigsegg.new(db=db, name="Koenigsegg")
        await koenigsegg.save(db=db)
        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people", members=[john])
        await people.save(db=db)

        jesko = await Node.init(schema=TestKind.CAR, db=db)
        await jesko.new(
            db=db,
            name="Jesko",
            color="Red",
            description="A limited production mid-engine sports car",
            owner=john,
            manufacturer=koenigsegg,
        )
        await jesko.save(db=db)

        FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
        )
        await client_repository.save()

    async def test_create_proposed_change(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient
    ) -> None:
        branch = await client.branch.create(branch_name="branch2")

        richard = await Node.init(schema=TestKind.PERSON, db=db, branch=branch.name)
        await richard.new(db=db, name="Richard", height=180, description="The less famous Richard Doe")
        await richard.save(db=db)

        # Create a proposed change
        proposed_change = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={
                "source_branch": branch.name,
                "destination_branch": "main",
                "name": "test-generator",
            },
        )
        await proposed_change.save()

        await wait_for_pipeline_to_be_completed(
            client=client, branch=branch.name, proposed_change_id=proposed_change.id
        )

        tags = await client.all(kind="BuiltinTag", branch=branch.name)
        assert "JOHN__JESKO" not in [tag.name.value for tag in tags]
        assert "John..Jesko" in [tag.name.value for tag in tags]
        assert "john-jesko" in [tag.name.value for tag in tags]

        local_groups = await client.filters(kind=InfrahubKind.GENERATORGROUP, branch=branch.name)
        assert len(local_groups) == 2

        aware_groups = await client.filters(kind=InfrahubKind.GENERATORAWAREGROUP, branch=branch.name)
        assert len(aware_groups) == 1

    # async def test_merge_proposed_change(self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> None:

    #     # Change the name of the car in main before merging the branch to validate if the generator have been executed after the merge
    #     car = await client.get(kind=TestKind.CAR, name__value="Jesko")
    #     car.name.value = "Jesko99"
    #     await car.save()

    #     # merge the proposed change
    #     proposed_change = await client.get(kind=CoreProposedChange, name__value="test-generator")
    #     proposed_change.state.value = ProposedChangeState.MERGED.value
    #     await proposed_change.save()

    #     await wait_for_all_tasks_to_be_completed(client=client, timeout=30)

    #     tags = await client.all(kind="BuiltinTag", branch="branch2")
    #     assert "JOHN__JESKO" not in [tag.name.value for tag in tags]
    #     assert "John..Jesko" in [tag.name.value for tag in tags]
    #     assert "john-jesko99" in [tag.name.value for tag in tags]
