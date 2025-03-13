import pytest
from prefect.client.orchestration import PrefectClient, get_client

from infrahub.trigger.catalogue import builtin_triggers
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import setup_triggers
from infrahub.workflows.initialization import setup_deployments, setup_worker_pools


@pytest.fixture
async def prefect_client(prefect_test_fixture):
    async with get_client(sync_client=False) as prefect_client:
        yield prefect_client


@pytest.fixture
async def cleanup_automation(prefect_client: PrefectClient) -> None:
    automations = await prefect_client.read_automations()
    for automation in automations:
        await prefect_client.delete_automation(automation.id)


@pytest.fixture
async def init_prefect(prefect_client: PrefectClient) -> None:
    await setup_worker_pools(client=prefect_client)
    await setup_deployments(client=prefect_client)


async def test_setup_triggers(prefect_client: PrefectClient, init_prefect, cleanup_automation):
    await setup_triggers(client=prefect_client, triggers=builtin_triggers, trigger_type=TriggerType.BUILTIN)

    automations = await prefect_client.read_automations()
    assert len(automations) == len(builtin_triggers)

    # Remove 2 Triggers and ensure that setup_triggers is working as expected
    await setup_triggers(client=prefect_client, triggers=builtin_triggers[:-2], trigger_type=TriggerType.BUILTIN)
    automations = await prefect_client.read_automations()
    assert len(automations) == len(builtin_triggers[:-2])
