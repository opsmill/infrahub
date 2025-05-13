from typing import TYPE_CHECKING

from prefect import get_run_logger, task
from prefect.automations import AutomationCore
from prefect.cache_policies import NONE
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterName
from prefect.events.schemas.automations import Automation

from infrahub.trigger.models import TriggerDefinition

from .models import TriggerSetupReport, TriggerType

if TYPE_CHECKING:
    from uuid import UUID


def compare_automations(target: AutomationCore, existing: Automation) -> bool:
    """Compare an AutomationCore with an existing Automation object to identify if they are identical or not

    Return True if the target is identical to the existing automation
    """

    target_dump = target.model_dump(exclude_defaults=True, exclude_none=True)
    existing_dump = existing.model_dump(exclude_defaults=True, exclude_none=True, exclude={"id"})

    return target_dump == existing_dump


@task(name="trigger-setup", task_run_name="Setup triggers", cache_policy=NONE)  # type: ignore[arg-type]
async def setup_triggers(
    client: PrefectClient,
    triggers: list[TriggerDefinition],
    trigger_type: TriggerType | None = None,
    force_update: bool = False,
) -> TriggerSetupReport:
    log = get_run_logger()

    report = TriggerSetupReport()

    if trigger_type:
        log.debug(f"Setting up triggers of type {trigger_type.value}")
    else:
        log.debug("Setting up all triggers")

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

    # If a trigger type is provided, narrow down the list of existing triggers to know which one to delete
    existing_automations: dict[str, Automation] = {}
    if trigger_type:
        existing_automations = {
            item.name: item for item in await client.read_automations() if item.name.startswith(trigger_type.value)
        }
    else:
        existing_automations = {item.name: item for item in await client.read_automations()}

    trigger_names = [trigger.generate_name() for trigger in triggers]
    automation_names = list(existing_automations.keys())

    log.debug(f"{len(automation_names)} existing triggers ({automation_names})")
    log.debug(f"{len(trigger_names)} triggers to configure ({trigger_names})")

    to_delete = set(automation_names) - set(trigger_names)
    log.debug(f"{len(to_delete)} triggers to delete ({to_delete})")

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
            if force_update or not compare_automations(target=automation, existing=existing_automation):
                await client.update_automation(automation_id=existing_automation.id, automation=automation)
                log.info(f"{trigger.generate_name()} Updated")
                report.updated.append(trigger)
            else:
                report.unchanged.append(trigger)
        else:
            await client.create_automation(automation=automation)
            log.info(f"{trigger.generate_name()} Created")
            report.created.append(trigger)

    # -------------------------------------------------------------
    # Delete Triggers that shouldn't be there
    # -------------------------------------------------------------
    for item_to_delete in to_delete:
        existing_automation = existing_automations.get(item_to_delete)

        if not existing_automation:
            continue

        report.deleted.append(existing_automation)
        await client.delete_automation(automation_id=existing_automation.id)
        log.info(f"{item_to_delete} Deleted")

    if trigger_type:
        log.info(
            f"Processed triggers of type {trigger_type.value}: "
            f"{len(report.created)} created, {len(report.updated)} updated, {len(report.unchanged)} unchanged, {len(report.deleted)} deleted"
        )
    else:
        log.info(
            f"Processed all triggers: "
            f"{len(report.created)} created, {len(report.updated)} updated, {len(report.unchanged)} unchanged, {len(report.deleted)} deleted"
        )

    return report
