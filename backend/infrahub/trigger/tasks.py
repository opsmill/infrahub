from typing import TYPE_CHECKING

from prefect import get_run_logger, task
from prefect.automations import AutomationCore
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterName

from .catalogue import triggers

if TYPE_CHECKING:
    from uuid import UUID


@task(name="trigger-setup", task_run_name="Setup triggers in task-manager")
async def setup_triggers(client: PrefectClient) -> None:
    log = get_run_logger()

    # -------------------------------------------------------------
    # Retrieve existing Deployments and Automation from the server
    # -------------------------------------------------------------
    deployment_names = list({name for trigger in triggers for name in trigger.get_deployment_names()})
    deployments = {
        item.name: item
        for item in await client.read_deployments(
            deployment_filter=DeploymentFilter(name=DeploymentFilterName(any_=deployment_names))
        )
    }
    deployments_mapping: dict[str, UUID] = {name: item.id for name, item in deployments.items()}
    existing_automations = {item.name: item for item in await client.read_automations()}

    # -------------------------------------------------------------
    # Create or Update all triggers
    # -------------------------------------------------------------
    for trigger in triggers:
        automation = AutomationCore(
            name=trigger.name,
            description=trigger.description,
            enabled=True,
            trigger=trigger.trigger.get_prefect(),
            actions=[action.get_prefect(mapping=deployments_mapping) for action in trigger.actions],
        )

        existing_automation = existing_automations.get(trigger.name, None)

        if existing_automation:
            await client.update_automation(automation_id=existing_automation.id, automation=automation)
            log.info(f"{trigger.name} Updated")
        else:
            await client.create_automation(automation=automation)
            log.info(f"{trigger.name} Created")
