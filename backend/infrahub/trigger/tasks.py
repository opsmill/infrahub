from prefect import flow
from prefect.client.orchestration import get_client

from infrahub.actions.gather import gather_trigger_action_rules
from infrahub.computed_attribute.gather import (
    gather_trigger_computed_attribute_jinja2,
    gather_trigger_computed_attribute_python,
)
from infrahub.services import InfrahubServices
from infrahub.trigger.catalogue import builtin_triggers
from infrahub.webhook.gather import gather_trigger_webhook

from .setup import setup_triggers


@flow(name="trigger-configure-all", flow_run_name="Configure all triggers")
async def trigger_configure_all(service: InfrahubServices) -> None:
    async with service.database.start_session() as db:
        webhook_trigger = await gather_trigger_webhook(db=db)
        computed_attribute_j2_triggers = await gather_trigger_computed_attribute_jinja2()
        (
            computed_attribute_python_triggers,
            computed_attribute_python_query_triggers,
        ) = await gather_trigger_computed_attribute_python(db=db)
        action_rules = await gather_trigger_action_rules(db=db)
        triggers = (
            computed_attribute_j2_triggers
            + computed_attribute_python_triggers
            + computed_attribute_python_query_triggers
            + builtin_triggers
            + webhook_trigger
            + action_rules
        )

        async with get_client(sync_client=False) as prefect_client:
            await setup_triggers(client=prefect_client, triggers=triggers, force_update=True)
