from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from prefect.client.orchestration import get_client

from infrahub.computed_attribute.gather import gather_trigger_computed_attribute_jinja2
from infrahub.computed_attribute.models import ComputedAttrJinja2TriggerDefinition
from infrahub.computed_attribute.tasks import computed_attribute_setup_jinja2
from infrahub.core import registry
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch_computed.jinja2 import ComputedAttributeTriggerNode
from infrahub.trigger.constants import TRIGGER_PLACEHOLDER_FIELD
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import gather_all_automations, setup_triggers
from infrahub.workflows.catalogue import TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES
from tests.component.computed_attribute._base import ScopedRecomputeTestBase
from tests.helpers.schema import COLOR, TSHIRT, load_schema

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowRecorder

PEER_AUTOMATION = "computed_attr_jinja2::main::TestingTShirt_description::kind::TestingColor"
PLACEHOLDER_AUTOMATION = "computed_attr_jinja2::main::TestingTShirt_description::kind::TestingTShirt"


class TestPlaceholderRemoval(ScopedRecomputeTestBase):
    WORKFLOW = TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES

    @pytest.fixture(scope="class")
    async def tshirt_schema(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        await load_schema(db=db, schema=SchemaRoot(nodes=[COLOR, TSHIRT]), update_db=True)

    async def test_setup_deletes_placeholder_and_keeps_peer_automation(
        self,
        tshirt_schema: None,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        target = next(
            target
            for target in schema_branch.computed_attributes.get_jinja2_trigger_nodes()
            if target.kind == "TestingTShirt"
        )
        placeholder = ComputedAttrJinja2TriggerDefinition.from_computed_attribute(
            branch=default_branch.name,
            computed_attribute=target,
            trigger_node=ComputedAttributeTriggerNode(
                kind="TestingTShirt", attributes=[TRIGGER_PLACEHOLDER_FIELD], targets_self=True
            ),
        )
        peer_triggers = await gather_trigger_computed_attribute_jinja2()
        async with get_client(sync_client=False) as prefect_client:
            await setup_triggers(
                client=prefect_client,
                triggers=[*peer_triggers, placeholder],
                trigger_type=TriggerType.COMPUTED_ATTR_JINJA2,
            )
            before = await self._jinja2_automations(prefect_client=prefect_client)
        assert set(before) == {PEER_AUTOMATION, PLACEHOLDER_AUTOMATION}

        await computed_attribute_setup_jinja2(
            context=self._context(admin_account, default_branch),
            branch_name=default_branch.name,
            changed_elements=None,
        )

        async with get_client(sync_client=False) as prefect_client:
            after = await self._jinja2_automations(prefect_client=prefect_client)
        assert set(after) == {PEER_AUTOMATION}
        assert TRIGGER_PLACEHOLDER_FIELD not in after[PEER_AUTOMATION]
        assert self._submitted_attribute_names(workflow_recorder) == {"description"}

    @staticmethod
    async def _jinja2_automations(prefect_client: PrefectClient) -> dict[str, str]:
        """The serialized trigger of each automation of the Jinja2 computed attribute family, by name."""
        return {
            automation.name: automation.trigger.model_dump_json()
            for automation in await gather_all_automations(client=prefect_client)
            if automation.name.startswith(f"{TriggerType.COMPUTED_ATTR_JINJA2.value}::")
        }
