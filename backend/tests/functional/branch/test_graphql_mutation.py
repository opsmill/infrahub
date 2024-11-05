from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import BranchNotFoundError
from infrahub_sdk.graphql import Mutation

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.services.adapters.cache.redis import RedisCache
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestBranchMutations(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> str:
        await load_schema(db, schema=CAR_SCHEMA)

        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
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

        bus_simulator.service.cache = RedisCache()
        FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
        )
        await client_repository.save()
        return client_repository.id

    async def test_branch_delete_async(self, initial_dataset: str, client: InfrahubClient) -> None:
        branch = await client.branch.create(branch_name="branch_to_delete")

        query = Mutation(
            mutation="BranchDelete",
            input_data={"data": {"name": branch.name}, "wait_until_completion": False},
            query={"ok": None, "task": {"id": None}},
        )
        result = await client.execute_graphql(query=query.render())
        assert result["BranchDelete"]["ok"] is True
        assert result["BranchDelete"]["task"]["id"]

        with pytest.raises(BranchNotFoundError):
            await client.branch.get(branch_name=branch.name)

    async def test_branch_delete(self, initial_dataset: str, client: InfrahubClient) -> None:
        branch = await client.branch.create(branch_name="branch_to_delete_sync")

        query = Mutation(
            mutation="BranchDelete",
            input_data={"data": {"name": branch.name}},
            query={"ok": None, "task": {"id": None}},
        )
        result = await client.execute_graphql(query=query.render())
        assert result["BranchDelete"]["ok"] is True
        assert result["BranchDelete"]["task"] is None

        with pytest.raises(BranchNotFoundError):
            await client.branch.get(branch_name=branch.name)

    async def test_branch_rebase_async(self, initial_dataset: str, client: InfrahubClient) -> None:
        branch = await client.branch.create(branch_name="branch_to_rebase")

        query = Mutation(
            mutation="BranchRebase",
            input_data={"data": {"name": branch.name}, "wait_until_completion": False},
            query={"ok": None, "task": {"id": None}, "object": {"id": None}},
        )
        result = await client.execute_graphql(query=query.render())
        assert result["BranchRebase"]["ok"] is True
        assert result["BranchRebase"]["object"]["id"] == branch.id
        assert result["BranchRebase"]["task"]["id"]

        branch_after = await client.branch.get(branch_name=branch.name)
        assert branch.branched_from != branch_after.branched_from

    async def test_branch_rebase(self, initial_dataset: str, client: InfrahubClient) -> None:
        branch = await client.branch.create(branch_name="branch_to_rebase_sync")

        query = Mutation(
            mutation="BranchRebase",
            input_data={"data": {"name": branch.name}},
            query={"ok": None, "task": {"id": None}, "object": {"id": None}},
        )
        result = await client.execute_graphql(query=query.render())
        assert result["BranchRebase"]["ok"] is True
        assert result["BranchRebase"]["object"]["id"] == branch.id
        assert result["BranchRebase"]["task"] is None

        branch_after = await client.branch.get(branch_name=branch.name)
        assert branch.branched_from != branch_after.branched_from
