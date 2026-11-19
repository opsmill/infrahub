from __future__ import annotations

from typing import TYPE_CHECKING

from prefect.client.orchestration import get_client as get_prefect_client

from infrahub.core import registry
from infrahub.core.template_fingerprint.models import TemplateFamily
from infrahub.display_labels.gather import gather_trigger_display_labels_jinja2
from infrahub.display_labels.models import DisplayLabelTriggerDefinition
from infrahub.display_labels.tasks import display_labels_setup_jinja2
from infrahub.trigger.constants import TRIGGER_PLACEHOLDER_FIELD
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import setup_triggers
from infrahub.workflows.catalogue import TRIGGER_UPDATE_DISPLAY_LABELS
from tests.helpers.template_fingerprint import DEVICE, OWNER, TemplateSetupScenarios, schema_variant

if TYPE_CHECKING:
    from infrahub.core.schema import SchemaRoot
    from infrahub.events.models import EventContext


class TestDisplayLabelSetup(TemplateSetupScenarios):
    FAMILY = TemplateFamily.DISPLAY_LABEL_JINJA2
    WORKFLOW = TRIGGER_UPDATE_DISPLAY_LABELS
    CHANGED_KIND = OWNER
    PEER_AUTOMATION = f"display_label_jinja2::main::{DEVICE}::by::{OWNER}"
    PLACEHOLDER_AUTOMATION = f"display_label_jinja2::main::{OWNER}::by::{OWNER}"
    BRANCH_PREFIX = "dl"

    async def run_setup(self, context: EventContext, branch_name: str, event_name: str | None = None) -> None:
        await display_labels_setup_jinja2(context=context, branch_name=branch_name, event_name=event_name)

    def changed_schema(self) -> SchemaRoot:
        return schema_variant(owner_display_label="{{ name__value }} ({{ code__value }})")

    async def build_placeholder(self, branch_name: str) -> None:
        template = registry.schema.get_schema_branch(name=branch_name).display_labels.get_template_node(kind=OWNER)
        placeholder = DisplayLabelTriggerDefinition.new(
            branch=branch_name,
            node_kind=OWNER,
            target_kind=OWNER,
            template_hash=template.get_hash(),
            fields=[TRIGGER_PLACEHOLDER_FIELD],
        )
        peer_triggers = await gather_trigger_display_labels_jinja2()
        async with get_prefect_client(sync_client=False) as prefect_client:
            await setup_triggers(
                client=prefect_client,
                triggers=[*peer_triggers, placeholder],
                trigger_type=TriggerType.DISPLAY_LABEL_JINJA2,
            )
