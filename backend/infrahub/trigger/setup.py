from typing import TYPE_CHECKING

from prefect import get_run_logger, task
from prefect.automations import AutomationCore
from prefect.cache_policies import NONE
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterName

from infrahub.trigger.models import TriggerDefinition

from .models import TriggerType

if TYPE_CHECKING:
    from uuid import UUID


@task(name="trigger-setup", task_run_name="Setup triggers", cache_policy=NONE)  # type: ignore[arg-type]
async def setup_triggers(
    client: PrefectClient,
    triggers: list[TriggerDefinition],
    trigger_type: TriggerType | None = None,
) -> None:
    log = get_run_logger()

    if trigger_type:
        log.info(f"Setting up triggers of type {trigger_type.value}")
    else:
        log.info("Setting up all triggers")

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

    # If a trigger type is provided, narrow down the list of existing triggers to know which one to delete
    if trigger_type:
        trigger_automations = [
            item.name for item in await client.read_automations() if item.name.startswith(trigger_type.value)
        ]
    else:
        trigger_automations = [item.name for item in await client.read_automations()]

    trigger_names = [trigger.generate_name() for trigger in triggers]

    log.debug(f"{len(trigger_automations)} existing triggers ({trigger_automations})")
    log.debug(f"{len(trigger_names)}  triggers to configure ({trigger_names})")

    to_delete = set(trigger_automations) - set(trigger_names)
    log.debug(f"{len(trigger_names)} triggers to delete ({to_delete})")

    # -------------------------------------------------------------
    # Create or Update all triggers
    # -------------------------------------------------------------
    for trigger in triggers:
        automation = AutomationCore(
            name=trigger.generate_name(),
            description=trigger.get_description(),
            enabled=True,
            trigger=trigger.trigger.get_prefect(),
            actions=[action.get_prefect(mapping=deployments_mapping) for action in trigger.actions],
        )

        existing_automation = existing_automations.get(trigger.generate_name(), None)

        if existing_automation:
            await client.update_automation(automation_id=existing_automation.id, automation=automation)
            log.info(f"{trigger.generate_name()} Updated")
        else:
            await client.create_automation(automation=automation)
            log.info(f"{trigger.generate_name()} Created")

    # -------------------------------------------------------------
    # Delete Triggers that shouldn't be there
    # -------------------------------------------------------------
    for item_to_delete in to_delete:
        existing_automation = existing_automations.get(item_to_delete)

        if not existing_automation:
            continue

        await client.delete_automation(automation_id=existing_automation.id)
        log.info(f"{item_to_delete} Deleted")
