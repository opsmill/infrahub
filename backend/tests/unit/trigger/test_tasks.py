import pytest
from prefect.client.orchestration import PrefectClient, get_client

from infrahub.trigger.catalogue import builtin_triggers
from infrahub.trigger.models import EventTrigger, TriggerType
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


async def test_setup_triggers(prefect_client: PrefectClient, init_prefect, cleanup_automation) -> None:
    report = await setup_triggers(client=prefect_client, triggers=builtin_triggers, trigger_type=TriggerType.BUILTIN)

    assert len(report.deleted) == 0
    assert len(report.updated) == 0
    assert len(report.unchanged) == 0
    assert len(report.created) == len(builtin_triggers)

    automations = await prefect_client.read_automations()
    assert len(automations) == len(builtin_triggers)

    # Update 1 Trigger and remove 2 to ensure that setup_triggers is working as expected
    builtin_triggers[0].trigger = EventTrigger(events={"new.event.name"})
    report_after = await setup_triggers(
        client=prefect_client, triggers=builtin_triggers[:-2], trigger_type=TriggerType.BUILTIN
    )

    assert len(report_after.deleted) == 2
    assert len(report_after.updated) == 1
    assert len(report_after.unchanged) == len(builtin_triggers) - 3
    assert len(report_after.created) == 0

    automations = await prefect_client.read_automations()
    assert len(automations) == len(builtin_triggers[:-2])

    # Ensure force_update is working properly
    report_force = await setup_triggers(
        client=prefect_client, triggers=builtin_triggers[:-2], trigger_type=TriggerType.BUILTIN, force_update=True
    )
    assert len(report_force.deleted) == 0
    assert len(report_force.updated) == len(builtin_triggers) - 2
    assert len(report_force.unchanged) == 0
    assert len(report_force.created) == 0
