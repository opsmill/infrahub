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
from tests.helpers.schema import load_schema
from tests.helpers.template_fingerprint import (
    DEVICE,
    FINGERPRINT_SCHEMA,
    OWNER,
    TemplateSetupScenarios,
    schema_variant,
)

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreAccount
    from infrahub.core.schema import SchemaRoot
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from tests.adapters.workflow import WorkflowRecorder


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

    async def test_branch_that_stops_owning_its_schema_loses_its_records(
        self, db: InfrahubDatabase, workflow_recorder: WorkflowRecorder, admin_account: CoreAccount
    ) -> None:
        branch_name = f"{self.BRANCH_PREFIX}-realigned"
        await self.create_branch_with_schema(db=db, branch_name=branch_name, schema=self.changed_schema())
        await self.run_setup(context=self.context(admin_account, branch_name), branch_name=branch_name)
        assert (branch_name, OWNER) in await self.recorded(db=db, family=self.FAMILY)

        await load_schema(db=db, schema=FINGERPRINT_SCHEMA, branch_name=branch_name, update_db=True)
        assert branch_name not in registry.get_altered_schema_branches()
        other_branch_records = {
            key: value
            for key, value in (await self.recorded(db=db, family=self.FAMILY)).items()
            if key[0] != branch_name
        }
        workflow_recorder.reset()

        await self.run_setup(context=self.context(admin_account, branch_name), branch_name=branch_name)

        assert self.submitted(workflow_recorder, self.WORKFLOW) == []
        assert await self.recorded(db=db, family=self.FAMILY) == other_branch_records
