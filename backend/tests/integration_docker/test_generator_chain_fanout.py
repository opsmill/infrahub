import asyncio
from collections import Counter
from pathlib import Path

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.protocols import (
    BuiltinTag,
    CoreGeneratorAction,
    CoreGeneratorDefinition,
    CoreGenericRepository,
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

# One parent with this many children. The upstream generator bumps all of them in a single
# run, so the chain must fire this many downstream *generator* flows. Unlike the cheap
# group-add stress, each downstream hop is a full generator flow (class load, query, write),
# which is where heavy flows might fail or crash under load.
CHILD_COUNT = 400

ACTION_FLOW = "action-run-generator"
GENERATOR_FLOW = "generator-run"


async def flow_run_states(prefect_client: PrefectClient, flow_name: str) -> Counter:
    """Tally flow runs of a given flow by terminal/current state."""
    counter: Counter = Counter()
    offset = 0
    page = 200
    while True:
        runs = await prefect_client.read_flow_runs(
            flow_filter=FlowFilter(name=FlowFilterName(any_=[flow_name])),
            limit=page,
            offset=offset,
        )
        for run in runs:
            counter[run.state_type.value if run.state_type else "UNKNOWN"] += 1
        if len(runs) < page:
            break
        offset += len(runs)
    return counter


class TestGeneratorChainFanOut(TestInfrahubDockerClient, SchemaCarPerson):
    """Run the faithful generator->generator chain at scale and watch for flow failures.

    Upstream generator ``signal-cars`` bumps ``description`` on every child car in one run.
    A ``CoreNodeTriggerRule`` on that update runs the downstream ``mark-car`` generator, which
    drops a marker tag. The test reports how many events were delivered (action flows), how
    many downstream generator flows completed vs failed/crashed, and how many tags landed.
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
    async def chain_data(
        self, client: InfrahubClient, default_branch: str, remote_repos_dir: Path, load_initial_schema: None
    ) -> dict:
        manufacturer = await client.create(kind=TESTING_MANUFACTURER, name="ACME")
        await manufacturer.save()

        person = await client.create(kind=TESTING_PERSON, name="FanOut")
        await person.save()

        batch = await client.create_batch()
        cars = []
        for index in range(CHILD_COUNT):
            car = await client.create(
                kind=TESTING_CAR,
                name=f"car-{index:05d}",
                color="black",
                manufacturer=manufacturer,
                owner=person,
            )
            cars.append(car)
            batch.add(task=car.save, node=car)
        async for _ in batch.execute():
            pass

        # Target groups must exist before repo sync: the generator definitions resolve their
        # `targets` by group name at import time.
        signal_group = await client.create(kind=CoreStandardGroup, name="signal-cars", members=[person.id])
        await signal_group.save()

        mark_group = await client.create(kind=CoreStandardGroup, name="mark-cars", members=[car.id for car in cars])
        await mark_group.save()

        repo_name = "checksum-chain"
        repo_dir = get_fixtures_dir() / "repos" / repo_name / "initial__main"
        repo = GitRepo(name=repo_name, src_directory=repo_dir, dst_directory=remote_repos_dir)
        await repo.add_to_infrahub(client=client)
        in_sync = await repo.wait_for_sync_to_complete(client=client, retries=20)
        assert in_sync

        repos = await client.all(kind=CoreGenericRepository)
        assert repos

        return {"person": person}

    async def test_generator_chain_fans_out_to_all_children(
        self, client: InfrahubClient, default_branch: str, prefect_client: PrefectClient, chain_data: dict
    ) -> None:
        person = chain_data["person"]

        mark_definition = await client.get(kind=CoreGeneratorDefinition, name__value="mark-car")
        signal_definition = await client.get(kind=CoreGeneratorDefinition, name__value="signal-cars")

        generator_action = await client.create(
            kind=CoreGeneratorAction, name="run-mark-car", generator=mark_definition
        )
        await generator_action.save()

        node_trigger = await client.create(
            kind=CoreNodeTriggerRule,
            name="trigger-mark-car-on-signal",
            active=False,
            branch_scope="all_branches",
            node_kind=TESTING_CAR,
            mutation_action="updated",
            action=generator_action,
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
        # emitting CHILD_COUNT node events, each of which must run mark-car.
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

        # Poll until the chain settles. mark-car is a full generator flow, so watch for
        # failed/crashed generator runs, not just slow ones.
        action_total = 0
        gen_bad = 0
        marked = 0
        stable = 0
        prev = None
        for poll in range(240):  # long window; generator flows are heavy
            action_states = await flow_run_states(prefect_client, ACTION_FLOW)
            gen_states = await flow_run_states(prefect_client, GENERATOR_FLOW)
            action_total = sum(action_states.values())
            gen_bad = gen_states.get("FAILED", 0) + gen_states.get("CRASHED", 0)
            tags = await client.all(kind=BuiltinTag)
            marked = len([tag for tag in tags if tag.name.value.startswith("processed-")])

            snapshot = (action_total, marked, gen_bad)
            stable = stable + 1 if snapshot == prev else 0
            prev = snapshot

            print(
                f"[poll {poll}] delivered(action_flows)={action_total} completed(tags)={marked}/{CHILD_COUNT} "
                f"gen_failed_crashed={gen_bad} action_states={dict(action_states)} gen_states={dict(gen_states)}"
            )
            if marked >= CHILD_COUNT and action_total >= CHILD_COUNT:
                break
            if stable >= 12:  # ~60s with no change -> settled
                break
            await asyncio.sleep(5)

        print(
            f"FINAL: target={CHILD_COUNT} delivered(action_flows)={action_total} "
            f"completed(tags)={marked} gen_failed_crashed={gen_bad}"
        )

        # Delivery should hold (the 2000-event stress showed no loss). If it does not, that is
        # event loss; if it holds but generators failed/crashed, that is a generator-scale bug;
        # if everything just lags, tags climb to target given enough time.
        assert action_total == CHILD_COUNT, (
            f"delivery: only {action_total}/{CHILD_COUNT} downstream action flows fired -> node events dropped."
        )
        assert gen_bad == 0, (
            f"{gen_bad} downstream generator flows failed/crashed at scale -> generator-scale failure."
        )
        assert marked == CHILD_COUNT, (
            f"only {marked}/{CHILD_COUNT} downstream generators completed."
        )
