from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fast_depends import dependency_provider
from infrahub_sdk.graphql import Mutation
from infrahub_sdk.protocols import CoreGeneratorDefinition
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

from infrahub.actions.tasks import _run_generators
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.workers.dependencies import build_client

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient
    from tests.adapters.message_bus import BusSimulator

    from infrahub.database import InfrahubDatabase


class TestMutationGenerator(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
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

        branch1 = await client.branch.create(branch_name="branch1")

        FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
            branch=branch1.name,
        )
        await client_repository.save()

        richard = await Node.init(schema=TestKind.PERSON, db=db, branch=branch1.name)
        await richard.new(db=db, name="Richard", height=180, description="The less famous Richard Doe")
        await richard.save(db=db)

    async def test_execute_generator_local(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient
    ) -> None:
        generator = await client.get(kind=CoreGeneratorDefinition, branch="branch1", name__value="cartags")
        mutation = Mutation(
            mutation="CoreGeneratorDefinitionRun", input_data={"data": {"id": generator.id}}, query={"ok": None}
        )
        response = await client.execute_graphql(query=mutation.render(), branch_name="branch1")
        assert response["CoreGeneratorDefinitionRun"]["ok"]

        tags = await client.all(kind="BuiltinTag", branch="branch1")
        assert "john-jesko" in [tag.name.value for tag in tags]

        groups = await client.filters(kind=InfrahubKind.GENERATORGROUP, branch="branch1")
        assert len(groups) == 1

    async def test_execute_generator_aware(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient
    ) -> None:
        generator = await client.get(kind=CoreGeneratorDefinition, branch="branch1", name__value="cartags_upper")
        mutation = Mutation(
            mutation="CoreGeneratorDefinitionRun", input_data={"data": {"id": generator.id}}, query={"ok": None}
        )
        response = await client.execute_graphql(query=mutation.render(), branch_name="branch1")
        assert response["CoreGeneratorDefinitionRun"]["ok"]

        tags = await client.all(kind="BuiltinTag", branch="branch1")
        assert "JOHN__JESKO" in [tag.name.value for tag in tags]

        groups = await client.filters(kind=InfrahubKind.GENERATORAWAREGROUP, branch="branch1")
        assert len(groups) == 1

    async def test_execute_generator_background(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient
    ) -> None:
        generator = await client.get(kind=CoreGeneratorDefinition, branch="branch1", name__value="cartags")
        mutation = Mutation(
            mutation="CoreGeneratorDefinitionRun",
            input_data={"data": {"id": generator.id}, "wait_until_completion": False},
            query={"ok": None, "task": {"id": None}},
        )
        response = await client.execute_graphql(query=mutation.render(), branch_name="branch1")
        assert response["CoreGeneratorDefinitionRun"]["ok"]
        assert response["CoreGeneratorDefinitionRun"]["task"]["id"]

    async def test_execute_generator_action(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient
    ) -> None:
        generator = await client.get(kind=CoreGeneratorDefinition, branch="branch1", name__value="cartags")

        person_john = await client.get(kind=TestKind.PERSON, branch="branch1", name__value="John")
        person_john.name.value = "Bill"
        await person_john.save(allow_upsert=True)

        with dependency_provider.scope(build_client, lambda: client):
            await _run_generators(
                branch_name="branch1",
                node_ids=[person_john.id],
                generator_definition_id=generator.id,
                client=client,
                context=None,
            )

        tags = await client.all(kind="BuiltinTag", branch="branch1")
        assert "bill-jesko" in [tag.name.value for tag in tags]
