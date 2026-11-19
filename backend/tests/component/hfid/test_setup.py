from __future__ import annotations

from typing import TYPE_CHECKING

from prefect.client.orchestration import get_client as get_prefect_client

from infrahub.core import registry
from infrahub.core.template_fingerprint.models import TemplateFamily
from infrahub.display_labels.tasks import display_labels_setup_jinja2
from infrahub.hfid.gather import gather_trigger_hfid
from infrahub.hfid.models import HFIDTriggerDefinition
from infrahub.hfid.tasks import hfid_setup
from infrahub.trigger.constants import TRIGGER_PLACEHOLDER_FIELD
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import setup_triggers
from infrahub.workflows.catalogue import TRIGGER_UPDATE_DISPLAY_LABELS, TRIGGER_UPDATE_HFID
from tests.helpers.template_fingerprint import DEVICE, OWNER, TAG, TemplateSetupScenarios, schema_variant

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreAccount
    from infrahub.core.schema import SchemaRoot
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from tests.adapters.workflow import WorkflowRecorder


class TestHFIDSetup(TemplateSetupScenarios):
    FAMILY = TemplateFamily.HUMAN_FRIENDLY_ID
    WORKFLOW = TRIGGER_UPDATE_HFID
    CHANGED_KIND = OWNER
    PEER_AUTOMATION = f"human_friendly_id::main::{DEVICE}::by::{OWNER}"
    PLACEHOLDER_AUTOMATION = f"human_friendly_id::main::{OWNER}::by::{OWNER}"
    BRANCH_PREFIX = "hfid"

    async def run_setup(self, context: EventContext, branch_name: str, event_name: str | None = None) -> None:
        await hfid_setup(context=context, branch_name=branch_name, event_name=event_name)

    def changed_schema(self) -> SchemaRoot:
        return schema_variant(owner_hfid=["code__value"])

    async def build_placeholder(self, branch_name: str) -> None:
        definition = registry.schema.get_schema_branch(name=branch_name).hfids.get_node_definition(kind=OWNER)
        placeholder = HFIDTriggerDefinition.new(
            branch=branch_name,
            node_kind=OWNER,
            target_kind=OWNER,
            hfid_hash=definition.get_hash(),
            fields=[TRIGGER_PLACEHOLDER_FIELD],
        )
        peer_triggers = await gather_trigger_hfid()
        async with get_prefect_client(sync_client=False) as prefect_client:
            await setup_triggers(
                client=prefect_client,
                triggers=[*peer_triggers, placeholder],
                trigger_type=TriggerType.HUMAN_FRIENDLY_ID,
            )

    async def test_hfid_added_to_kind_submits_that_kind(
        self, db: InfrahubDatabase, workflow_recorder: WorkflowRecorder, admin_account: CoreAccount
    ) -> None:
        await self.create_branch_with_schema(
            db=db, branch_name="hfid-added", schema=schema_variant(tag_hfid=["name__value"])
        )

        await self.run_setup(context=self.context(admin_account, "hfid-added"), branch_name="hfid-added")

        assert self.submitted(workflow_recorder, TRIGGER_UPDATE_HFID) == [("hfid-added", TAG)]

    async def test_one_update_changing_both_families_submits_once_per_family(
        self, db: InfrahubDatabase, workflow_recorder: WorkflowRecorder, admin_account: CoreAccount
    ) -> None:
        schema = schema_variant(owner_display_label="{{ code__value }}", device_hfid=["name__value"])
        await self.create_branch_with_schema(db=db, branch_name="hfid-both", schema=schema)
        context = self.context(admin_account, "hfid-both")

        await display_labels_setup_jinja2(context=context, branch_name="hfid-both")
        await hfid_setup(context=context, branch_name="hfid-both")

        assert self.submitted(workflow_recorder, TRIGGER_UPDATE_DISPLAY_LABELS) == [("hfid-both", OWNER)]
        assert self.submitted(workflow_recorder, TRIGGER_UPDATE_HFID) == [("hfid-both", DEVICE)]
