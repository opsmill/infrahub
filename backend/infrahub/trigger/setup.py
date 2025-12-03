from typing import TYPE_CHECKING, Awaitable, Callable

from prefect import get_run_logger, task
from prefect.automations import AutomationCore
from prefect.cache_policies import NONE
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterName
from prefect.events.schemas.automations import Automation
from prefect.exceptions import PrefectHTTPStatusError

from infrahub import lock
from infrahub.database import InfrahubDatabase
from infrahub.trigger.models import TriggerDefinition

from .models import TriggerComparison, TriggerSetupReport, TriggerType

if TYPE_CHECKING:
    from uuid import UUID


def compare_automations(
    target: AutomationCore, existing: Automation, trigger_type: TriggerType | None, force_update: bool = False
) -> TriggerComparison:
    """Compare an AutomationCore with an existing Automation object to identify if they are identical,
    if it's a branch specific automation and the branch filter may be different, or if they are different.
    """

    if force_update:
        return TriggerComparison.UPDATE

    target_dump = target.model_dump(exclude_defaults=True, exclude_none=True)
    existing_dump = existing.model_dump(exclude_defaults=True, exclude_none=True, exclude={"id"})

    if target_dump == existing_dump:
        return TriggerComparison.MATCH

    if not trigger_type or not trigger_type.is_branch_specific:
        return TriggerComparison.UPDATE

    if target.description == existing.description:
        # If only the branch related info is different, we consider it a refresh
        return TriggerComparison.REFRESH

    return TriggerComparison.UPDATE


@task(name="trigger-setup-specific", task_run_name="Setup triggers of a specific kind", cache_policy=NONE)  # type: ignore[arg-type]
async def setup_triggers_specific(
    gatherer: Callable[[InfrahubDatabase | None], Awaitable[list[TriggerDefinition]]],
    trigger_type: TriggerType,
    db: InfrahubDatabase | None = None,
) -> TriggerSetupReport:
    async with lock.registry.get(
        name=f"configure-action-rules-{trigger_type.value}", namespace="trigger-rules", local=False
    ):
        if db:
            async with db.start_session(read_only=True) as dbs:
                triggers = await gatherer(dbs)
        else:
            triggers = await gatherer(db)
        async with get_client(sync_client=False) as prefect_client:
            return await setup_triggers(
                client=prefect_client,
                triggers=triggers,
                trigger_type=trigger_type,
            )  # type: ignore[misc]


@task(name="trigger-setup", task_run_name="Setup triggers", cache_policy=NONE)
async def setup_triggers(
    client: PrefectClient,
    triggers: list[TriggerDefinition],
    trigger_type: TriggerType | None = None,
    force_update: bool = False,
) -> TriggerSetupReport:
    log = get_run_logger()

    report = TriggerSetupReport()

    trigger_log_message = f"triggers of type {trigger_type.value}" if trigger_type else "all triggers"
    log.debug(f"Setting up {trigger_log_message}")

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

    existing_automations = {item.name: item for item in await gather_all_automations(client=client)}
    if trigger_type:
        # If a trigger type is provided, narrow down the list of existing triggers to know which one to delete
        existing_automations = {
            automation_name: automation
            for automation_name, automation in existing_automations.items()
            if automation_name.startswith(f"{trigger_type.value}::")
        }

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

        existing_automation = existing_automations.get(trigger.generate_name())

        if existing_automation:
            trigger_comparison = compare_automations(
                target=automation, existing=existing_automation, trigger_type=trigger_type, force_update=force_update
            )
            if trigger_comparison.update_prefect:
                await client.update_automation(automation_id=existing_automation.id, automation=automation)
                log.info(f"{trigger.generate_name()} Updated")
            report.add_with_comparison(trigger, trigger_comparison)
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
        try:
            await client.delete_automation(automation_id=existing_automation.id)
            log.info(f"{item_to_delete} Deleted")
        except PrefectHTTPStatusError as exc:
            if exc.response.status_code == 404:
                log.info(f"{item_to_delete} was already deleted")
            else:
                raise

    log.info(
        f"Processed {trigger_log_message}: {len(report.created)} created, {len(report.updated)} updated, "
        f"{len(report.refreshed)} refreshed, {len(report.unchanged)} unchanged, {len(report.deleted)} deleted"
    )

    return report


async def gather_all_automations(client: PrefectClient) -> list[Automation]:
    """Gather all automations from the Prefect server

    By default the Prefect client only retrieves a limited number of automations, this function
    retrieves them all by paginating through the results. The default within Prefect is 200 items,
    and client.read_automations() doesn't support pagination parameters.
    """
    offset = 0
    limit = 200
    automations: list[Automation] = []
    while True:
        response = await client.request("POST", "/automations/filter", json={"limit": limit, "offset": offset})
        response.raise_for_status()
        batch = Automation.model_validate_list(response.json())
        automations.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    return automations
