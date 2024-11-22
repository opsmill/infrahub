from __future__ import annotations

from datetime import timedelta

from prefect import flow
from prefect.automations import AutomationCore
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterName
from prefect.events.actions import RunDeployment
from prefect.events.schemas.automations import EventTrigger, Posture
from prefect.logging import get_run_logger

from infrahub.workflows.catalogue import COMPUTED_ATTRIBUTE_SETUP, COMPUTED_ATTRIBUTE_SETUP_PYTHON

from .constants import AUTOMATION_NAME


@flow(name="schema-updated-setup", flow_run_name="Setup schema updated event in task-manager")
async def schema_updated_setup() -> None:
    log = get_run_logger()

    async with get_client(sync_client=False) as client:
        deployments = {
            item.name: item
            for item in await client.read_deployments(
                deployment_filter=DeploymentFilter(
                    name=DeploymentFilterName(
                        any_=[COMPUTED_ATTRIBUTE_SETUP.name, COMPUTED_ATTRIBUTE_SETUP_PYTHON.name]
                    )
                )
            )
        }
        if COMPUTED_ATTRIBUTE_SETUP.name not in deployments:
            raise ValueError("Unable to find the deployment for PROCESS_COMPUTED_MACRO")

        deployment_id_computed_attribute_setup = deployments[COMPUTED_ATTRIBUTE_SETUP.name].id
        deployment_id_computed_attribute_setup_python = deployments[COMPUTED_ATTRIBUTE_SETUP_PYTHON.name].id

        schema_update_automation = await client.find_automation(id_or_name=AUTOMATION_NAME)

        automation = AutomationCore(
            name=AUTOMATION_NAME,
            description="Trigger actions on schema update event",
            enabled=True,
            trigger=EventTrigger(
                posture=Posture.Reactive,
                expect={"infrahub.schema.update"},
                within=timedelta(0),
                threshold=1,
            ),
            actions=[
                RunDeployment(
                    source="selected",
                    deployment_id=deployment_id_computed_attribute_setup,
                    parameters={
                        "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                    },
                    job_variables={},
                ),
                RunDeployment(
                    source="selected",
                    deployment_id=deployment_id_computed_attribute_setup_python,
                    parameters={
                        "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                    },
                    job_variables={},
                ),
            ],
        )

        if schema_update_automation:
            await client.update_automation(automation_id=schema_update_automation.id, automation=automation)
            log.info(f"{AUTOMATION_NAME} Updated")
        else:
            await client.create_automation(automation=automation)
            log.info(f"{AUTOMATION_NAME} Created")
