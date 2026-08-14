import asyncio
from pathlib import Path

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.protocols import (
    CoreGeneratorDefinition,
    CoreGenericRepository,
    CoreGroupAction,
    CoreNodeTriggerAttributeMatch,
    CoreNodeTriggerRule,
    CoreStandardGroup,
)
from infrahub_sdk.schema import NodeSchema, SchemaRoot
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo
from infrahub_sdk.testing.schemas.car_person import (
    TESTING_CAR,
    TESTING_MANUFACTURER,
    TESTING_PERSON,
    SchemaCarPerson,
)
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import FlowFilter, FlowFilterName

from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.setup import gather_all_automations
from tests.helpers.fixtures import get_fixtures_dir

# Large fan-out: one generator run bumps this many children, emitting this many node
# events as a burst. This is the scale where best-effort event delivery is expected to
# drop some events, so some downstream actions never fire.
CHILD_COUNT = 2000

# The downstream action flow. One flow run is created per delivered event, regardless of
# whether the group add itself succeeds, so counting these runs measures event delivery
# without being confused by contention on the shared target group.
ADD_NODE_TO_GROUP_FLOW = "action-add-node-to-group"


async def count_flow_runs(prefect_client: PrefectClient, flow_name: str) -> int:
    total = 0
    offset = 0
    page = 200
    while True:
        runs = await prefect_client.read_flow_runs(
            flow_filter=FlowFilter(name=FlowFilterName(any_=[flow_name])),
            limit=page,
            offset=offset,
        )
        total += len(runs)
        if len(runs) < page:
            break
        offset += len(runs)
    return total


class TestGeneratorChainDeliveryStress(TestInfrahubDockerClient, SchemaCarPerson):
    """Push the event-driven generator chain to a scale where events are dropped.

    An upstream generator bumps a `description` "checksum" on CHILD_COUNT children in one
    run (a burst of node events). A CoreNodeTriggerRule on that update runs a cheap
    group-add action. If delivery were reliable, the number of action flow runs would equal
    the number of children actually updated. Fewer flow runs than updates means node events
    were dropped before reaching the trigger, which is the AI-DC "only part of the chain
    runs" failure.
    """

    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    def initial_schema(
        self,
        schema_car_base: NodeSchema,
        schema_person_base: NodeSchema,
        schema_manufacturer_base: NodeSchema,
    ) -> SchemaRoot:
        return SchemaRoot(
            version="1.0",
            nodes=[schema_car_base, schema_person_base, schema_manufacturer_base],
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
    async def stress_data(
        self, client: InfrahubClient, default_branch: str, remote_repos_dir: Path, load_initial_schema: None
    ) -> dict:
        manufacturer = await client.create(kind=TESTING_MANUFACTURER, name="ACME")
        await manufacturer.save()

        person = await client.create(kind=TESTING_PERSON, name="FanOut")
        await person.save()

        batch = await client.create_batch()
        for index in range(CHILD_COUNT):
            car = await client.create(
                kind=TESTING_CAR,
                name=f"car-{index:05d}",
                color="black",
                manufacturer=manufacturer,
                owner=person,
            )
            batch.add(task=car.save, node=car)
        async for _ in batch.execute():
            pass

        # Target groups must exist before repo sync (generator definitions resolve targets
        # by name). signal-cars targets the person; mark-cars is unused here but the repo's
        # mark-car generator still resolves it. delivered is the sink for the group action.
        signal_group = await client.create(kind=CoreStandardGroup, name="signal-cars", members=[person.id])
        await signal_group.save()
        mark_group = await client.create(kind=CoreStandardGroup, name="mark-cars", members=[])
        await mark_group.save()
        delivered_group = await client.create(kind=CoreStandardGroup, name="delivered", members=[])
        await delivered_group.save()

        repo_name = "checksum-chain"
        repo_dir = get_fixtures_dir() / "repos" / repo_name / "initial__main"
        repo = GitRepo(name=repo_name, src_directory=repo_dir, dst_directory=remote_repos_dir)
        await repo.add_to_infrahub(client=client)
        in_sync = await repo.wait_for_sync_to_complete(client=client, retries=20)
        assert in_sync

        repos = await client.all(kind=CoreGenericRepository)
        assert repos

        return {"person": person, "delivered_group": delivered_group}

    async def _updated_count(self, client: InfrahubClient, branch: str) -> int:
        query = 'query { TestingCar(description__value: "signal") { count } }'
        result = await client.execute_graphql(query=query, branch_name=branch)
        return result["TestingCar"]["count"]

    async def test_all_burst_events_trigger_the_downstream_action(
        self, client: InfrahubClient, default_branch: str, prefect_client: PrefectClient, stress_data: dict
    ) -> None:
        person = stress_data["person"]
        delivered_group = stress_data["delivered_group"]

        signal_definition = await client.get(kind=CoreGeneratorDefinition, name__value="signal-cars")

        group_action = await client.create(kind=CoreGroupAction, name="add-to-delivered", group=delivered_group)
        await group_action.save()

        node_trigger = await client.create(
            kind=CoreNodeTriggerRule,
            name="trigger-delivery-stress",
            active=False,
            branch_scope="all_branches",
            node_kind=TESTING_CAR,
            mutation_action="updated",
            action=group_action,
        )
        await node_trigger.save()

        attribute_match = await client.create(
            kind=CoreNodeTriggerAttributeMatch,
            attribute_name="description",
            value_match="any",
            trigger=node_trigger,
        )
        await attribute_match.save()

        node_trigger.active.value = True
        await node_trigger.save()

        for _ in range(60):
            automations = await gather_all_automations(client=prefect_client)
            observed = [automation.name.split(NAME_SEPARATOR)[-1] for automation in automations]
            if node_trigger.name.value in observed:
                break
            await asyncio.sleep(1)

        # Fire the upstream generator asynchronously; it bumps every child's description,
        # emitting CHILD_COUNT node events. Async so the client does not time out on the run.
        mutation = (
            "mutation {"
            f'  CoreGeneratorDefinitionRun(data: {{id: "{signal_definition.id}", nodes: ["{person.id}"]}},'
            "    wait_until_completion: false) {"
            "    ok"
            "  }"
            "}"
        )
        result = await client.execute_graphql(query=mutation, branch_name=default_branch)
        assert result["CoreGeneratorDefinitionRun"]["ok"] is True

        # Poll until both the emitted updates and the delivered action runs settle.
        updated = 0
        flow_runs = 0
        stable = 0
        for poll in range(150):  # up to ~12.5 min at 5s
            new_updated = await self._updated_count(client, default_branch)
            new_flow_runs = await count_flow_runs(prefect_client, ADD_NODE_TO_GROUP_FLOW)
            if new_updated == updated and new_flow_runs == flow_runs:
                stable += 1
            else:
                stable = 0
            updated, flow_runs = new_updated, new_flow_runs
            print(f"[poll {poll}] updates_emitted={updated}/{CHILD_COUNT} action_flow_runs={flow_runs}")
            if updated >= CHILD_COUNT and flow_runs >= updated:
                break
            if stable >= 12:  # ~60s with no change -> settled
                break
            await asyncio.sleep(5)

        print(f"FINAL: updates_emitted={updated} action_flow_runs={flow_runs} target={CHILD_COUNT}")

        assert updated == CHILD_COUNT, (
            f"Upstream generator only updated {updated}/{CHILD_COUNT} children; it did not finish, "
            f"so this run cannot measure delivery. Investigate the generator run before reading the result."
        )
        assert flow_runs == updated, (
            f"Only {flow_runs}/{updated} downstream action flows ran. {updated - flow_runs} per-child node "
            f"events were dropped before reaching the trigger. This is the 'only part of the chain runs' failure."
        )
