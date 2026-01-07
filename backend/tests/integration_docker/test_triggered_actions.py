import asyncio
from pathlib import Path

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.protocols import (
    BuiltinTag,
    CoreGeneratorAction,
    CoreGeneratorDefinition,
    CoreGenericRepository,
    CoreGroupAction,
    CoreGroupTriggerRule,
    CoreNodeTriggerAttributeMatch,
    CoreNodeTriggerRule,
    CoreStandardGroup,
)
from infrahub_sdk.schema import AttributeSchema as Attr
from infrahub_sdk.schema import NodeSchema, SchemaRoot
from infrahub_sdk.schema.main import AttributeKind
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo
from infrahub_sdk.testing.schemas.car_person import (
    TESTING_CAR,
    TESTING_MANUFACTURER,
    TESTING_PERSON,
    SchemaCarPerson,
)
from prefect.client.orchestration import PrefectClient

from infrahub.core.constants import InfrahubKind
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.setup import gather_all_automations
from tests.helpers.fixtures import get_fixtures_dir

CURRENT_DIRECTORY = Path(__file__).parent.resolve()


class TestingTag(BuiltinTag): ...


class TestTriggeredActions(TestInfrahubDockerClient, SchemaCarPerson):
    @pytest.fixture(scope="class")
    def testing_tag_base(self) -> NodeSchema:
        return NodeSchema(
            name="Tag",
            namespace="Testing",
            description="Standard Tag object to attach to other objects to provide some context.",
            include_in_menu=True,
            icon="mdi:tag-multiple",
            label="Tag",
            default_filter="name__value",
            order_by=["name__value"],
            display_labels=["name__value"],
            uniqueness_constraints=[["name__value"]],
            attributes=[
                Attr(name="name", kind=AttributeKind.TEXT, unique=True),
                Attr(name="description", kind=AttributeKind.TEXT, optional=True),
            ],
        )

    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    def schema_person_artifact(self, schema_person_base: NodeSchema) -> NodeSchema:
        person_schema = schema_person_base.model_copy(deep=True)
        person_schema.inherit_from = [InfrahubKind.ARTIFACTTARGET]
        return person_schema

    @pytest.fixture(scope="class")
    def initial_schema(
        self,
        schema_car_base: NodeSchema,
        schema_person_artifact: NodeSchema,
        schema_manufacturer_base: NodeSchema,
        testing_tag_base: NodeSchema,
    ) -> SchemaRoot:
        return SchemaRoot(
            version="1.0",
            nodes=[schema_person_artifact, schema_car_base, schema_manufacturer_base, testing_tag_base],
        )

    @pytest.fixture(scope="class")
    async def load_initial_schema(
        self, default_branch: str, client: InfrahubClient, initial_schema: SchemaRoot
    ) -> None:
        await client.schema.wait_until_converged(branch=default_branch)

        resp = await client.schema.load(
            schemas=[initial_schema.to_schema_dict()], branch=default_branch, wait_until_converged=True
        )
        assert resp.errors == {}

    @pytest.fixture(scope="class")
    async def load_initial_data(
        self, client: InfrahubClient, default_branch: str, remote_repos_dir: Path, load_initial_schema: None
    ) -> None:
        data = await self.create_initial_data(client=client, branch=default_branch)
        persons = data[TESTING_PERSON]

        # Create Group People
        group_people = await client.create(
            kind="CoreStandardGroup", name="people", members=[item.id for item in persons]
        )
        await group_people.save()

        # Add repositories
        fixture_dir = get_fixtures_dir()
        repo_name = "car-dealership"
        repo_dir = fixture_dir / "repos" / repo_name / "initial__main"
        repo = GitRepo(name=repo_name, src_directory=repo_dir, dst_directory=remote_repos_dir)
        await repo.add_to_infrahub(client=client)
        in_sync = await repo.wait_for_sync_to_complete(client=client, retries=20)
        assert in_sync

        repos = await client.all(kind=CoreGenericRepository)
        assert repos

    async def wait_until_automations_are_configured(self, automation_names: list[str], client: PrefectClient) -> None:
        continue_waiting = True
        max_retries = 30
        retry = 0

        while continue_waiting:
            automations = await gather_all_automations(client=client)
            observed_automation_names = [automation.name.split(NAME_SEPARATOR)[-1] for automation in automations]
            if set(automation_names).issubset(observed_automation_names):
                continue_waiting = False
            else:
                retry += 1
                if retry >= max_retries:
                    assert set(automation_names).issubset(observed_automation_names)
                await asyncio.sleep(1)

    async def test_create_main_triggers(
        self, client: InfrahubClient, default_branch: str, prefect_client: PrefectClient, load_initial_data: None
    ) -> None:
        description_trigger_value = "right-stuff"

        group_people = await client.get(
            kind=CoreStandardGroup, name__value="people", prefetch_relationships=True, populate_store=True
        )

        group_action = await client.create(kind=CoreGroupAction, name="add-to-people", group=group_people)
        await group_action.save()

        tags_original = await client.all(kind=TestingTag)
        tag_names_original = [tag.name.value for tag in tags_original]

        node_trigger = await client.create(
            kind=CoreNodeTriggerRule,
            name="trigger-add-to-people",
            active=False,
            node_kind=TESTING_PERSON,
            mutation_action="updated",
            action=group_action,
        )
        await node_trigger.save()

        attribute_match = await client.create(
            kind=CoreNodeTriggerAttributeMatch,
            attribute_name="description",
            value=description_trigger_value,
            value_match="value",
            trigger=node_trigger,
        )
        await attribute_match.save()

        node_trigger.active.value = True
        await node_trigger.save()

        # Get the generator definition defined in the car-dealership repository
        generator_definition = await client.get(kind=CoreGeneratorDefinition, name__value="cartags")
        generator_action = await client.create(
            kind=CoreGeneratorAction, name="run-cartags-generator", generator=generator_definition
        )
        await generator_action.save()

        group_trigger = await client.create(
            kind=CoreGroupTriggerRule,
            name="run-generator-for-new-members",
            branch_scope="all_branches",
            members_added=True,
            group=group_people,
            action=generator_action,
        )
        await group_trigger.save()

        group_people = await client.get(
            kind=CoreStandardGroup, name__value="people", prefetch_relationships=True, populate_store=True
        )

        await group_people.members.fetch()
        original_member_ids = [node.id for node in group_people.members.peers]

        await self.wait_until_automations_are_configured(
            automation_names=[group_trigger.name.value, node_trigger.name.value], client=prefect_client
        )

        laura = await client.create(kind=TESTING_PERSON, name="Laura")
        await laura.save()

        volkswagen = await client.get(kind=TESTING_MANUFACTURER, hfid=["Volkswagen"])

        sharan = await client.create(kind=TESTING_CAR, name="Sharan", color="Red", manufacturer=volkswagen, owner=laura)
        await sharan.save()

        laura.description.value = description_trigger_value
        await laura.save()

        group_people = await client.get(
            kind=CoreStandardGroup, name__value="people", prefetch_relationships=True, populate_store=True
        )

        await group_people.members.fetch()
        for _ in range(30):
            tags_updated = await client.all(kind=TestingTag)
            tag_names_updated = [tag.name.value for tag in tags_updated]
            if len(tag_names_updated) > len(tag_names_original):
                break
            await asyncio.sleep(1)

        group_people = await client.get(
            kind=CoreStandardGroup, name__value="people", prefetch_relationships=True, populate_store=True
        )

        await group_people.members.fetch()
        final_member_ids = [node.id for node in group_people.members.peers]

        # Validate that the correct tag was created by the generator
        assert "laura-sharan" not in tag_names_original
        assert "laura-sharan" in tag_names_updated
        # Validate that Laura was added to the group
        assert laura.id not in original_member_ids
        assert laura.id in final_member_ids
