from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fast_depends import dependency_provider
from infrahub_sdk.graphql import Mutation
from infrahub_sdk.protocols import CoreGeneratorDefinition
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import FlowFilter, FlowFilterName, FlowRunFilter, FlowRunFilterTags
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

from infrahub.actions.tasks import _run_generators
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.workers.dependencies import build_client
from infrahub.workflows.constants import WorkflowTag

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

        tags = await client.all(kind="TestingTag", branch="branch1")
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

        tags = await client.all(kind="TestingTag", branch="branch1")
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

    async def test_generator_run_is_tagged_with_its_instance(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient
    ) -> None:
        """A generator run tags its flow run with the generator instance it creates or reuses."""
        manufacturer = await client.get(kind=TestKind.MANUFACTURER, branch="branch1", name__value="Koenigsegg")
        target = await client.create(kind=TestKind.PERSON, branch="branch1", data={"name": "Marcus", "height": 170})
        await target.save()
        car = await client.create(
            kind=TestKind.CAR,
            branch="branch1",
            data={"name": "Regera", "color": "Blue", "owner": target.id, "manufacturer": manufacturer.id},
        )
        await car.save()
        people = await client.get(kind=InfrahubKind.STANDARDGROUP, branch="branch1", name__value="people")
        await people.members.fetch()
        people.members.add(target.id)
        await people.save()

        generator = await client.get(kind=CoreGeneratorDefinition, branch="branch1", name__value="cartags")
        mutation = Mutation(
            mutation="CoreGeneratorDefinitionRun", input_data={"data": {"id": generator.id}}, query={"ok": None}
        )
        response = await client.execute_graphql(query=mutation.render(), branch_name="branch1")
        assert response["CoreGeneratorDefinitionRun"]["ok"]

        instances = await client.filters(kind=InfrahubKind.GENERATORINSTANCE, object__ids=[target.id], branch="branch1")
        assert len(instances) == 1

        instance_tag = WorkflowTag.RELATED_NODE.render(identifier=instances[0].id)
        target_tag = WorkflowTag.RELATED_NODE.render(identifier=target.id)
        branch_tag = WorkflowTag.BRANCH.render(identifier="branch1")

        async with get_client(sync_client=False) as prefect:
            runs = await prefect.read_flow_runs(
                flow_filter=FlowFilter(name=FlowFilterName(any_=["generator-run"])),
                flow_run_filter=FlowRunFilter(tags=FlowRunFilterTags(all_=[instance_tag])),
            )

        # run_generator tags the branch, the target node and the instance in a single call, so the
        # run carries exactly the target and instance related-node tags plus the branch tag: the
        # instance tag is added alongside the target, not swapped in for it.
        assert len(runs) == 1
        related_node_prefix = WorkflowTag.RELATED_NODE.render(identifier="")
        tags = set(runs[0].tags)
        assert {tag for tag in tags if tag.startswith(related_node_prefix)} == {target_tag, instance_tag}
        assert branch_tag in tags

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

        tags = await client.all(kind="TestingTag", branch="branch1")
        assert "bill-jesko" in [tag.name.value for tag in tags]
