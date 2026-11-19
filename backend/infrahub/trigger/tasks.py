from prefect import flow
from prefect.client.orchestration import get_client

from infrahub.actions.gather import gather_trigger_action_rules
from infrahub.computed_attribute.gather import (
    gather_trigger_computed_attribute_jinja2,
    gather_trigger_computed_attribute_python,
)
from infrahub.core.template_fingerprint.collector import collect_schema_fingerprints
from infrahub.core.template_fingerprint.models import TemplateFamily
from infrahub.core.template_fingerprint.repository import TemplateFingerprintRepository
from infrahub.display_labels.gather import gather_trigger_display_labels_jinja2
from infrahub.hfid.gather import gather_trigger_hfid
from infrahub.profiles.gather import gather_trigger_profile_refresh
from infrahub.trigger.catalogue import builtin_triggers
from infrahub.webhook.gather import gather_trigger_webhook
from infrahub.workers.dependencies import get_database

from .placeholder_carry_over import carry_over_placeholder_fingerprints
from .setup import setup_triggers, template_fingerprint_locks


@flow(name="trigger-configure-all", flow_run_name="Configure all triggers")
async def trigger_configure_all() -> None:
    database = await get_database()
    async with database.start_session() as db:
        repository = TemplateFingerprintRepository(db=db)
        webhook_trigger = await gather_trigger_webhook(db=db)
        display_label_triggers = await gather_trigger_display_labels_jinja2()
        human_friendly_id_triggers = await gather_trigger_hfid()
        computed_attribute_j2_triggers = await gather_trigger_computed_attribute_jinja2()
        (
            computed_attribute_python_triggers,
            computed_attribute_python_query_triggers,
        ) = await gather_trigger_computed_attribute_python(db=db)
        action_rules = await gather_trigger_action_rules(db=db)
        profile_refresh_triggers = await gather_trigger_profile_refresh()
        triggers = (
            computed_attribute_j2_triggers
            + computed_attribute_python_triggers
            + computed_attribute_python_query_triggers
            + display_label_triggers
            + human_friendly_id_triggers
            + builtin_triggers
            + profile_refresh_triggers
            + webhook_trigger
            + action_rules
        )

        async with template_fingerprint_locks():
            async with get_client(sync_client=False) as prefect_client:
                report = await setup_triggers(client=prefect_client, triggers=triggers, force_update=True)

            await carry_over_placeholder_fingerprints(
                deleted=report.deleted,
                schemas=[collect_schema_fingerprints(family=family) for family in TemplateFamily],
                repository=repository,
            )
