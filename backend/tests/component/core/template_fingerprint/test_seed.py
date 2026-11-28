from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.template_fingerprint.models import TemplateFamily
from infrahub.display_labels.tasks import display_labels_setup_jinja2
from infrahub.hfid.tasks import hfid_setup
from infrahub.workflows.initialization import seed_template_fingerprints, setup_task_manager_identifiers
from tests.helpers.template_fingerprint import DEVICE, OWNER, TAG, TemplateSetupTestBase

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowRecorder


class TestTemplateFingerprintSeed(TemplateSetupTestBase):
    async def test_first_start_records_every_template_and_next_update_submits_nothing(
        self, db: InfrahubDatabase, workflow_recorder: WorkflowRecorder, admin_account: CoreAccount
    ) -> None:
        await db.execute_query(query="MATCH (f:TemplateFingerprint) DETACH DELETE f")

        await setup_task_manager_identifiers()
        created = await seed_template_fingerprints(db=db)

        schema_branch = registry.schema.get_schema_branch(name="main")
        label_records = await self.recorded(db=db, family=TemplateFamily.DISPLAY_LABEL_JINJA2)
        hfid_records = await self.recorded(db=db, family=TemplateFamily.HUMAN_FRIENDLY_ID)
        assert set(label_records) == {("main", kind) for kind in schema_branch.display_labels.get_template_nodes()}
        assert set(hfid_records) == {("main", kind) for kind in schema_branch.hfids.get_template_nodes()}
        assert {("main", OWNER), ("main", DEVICE)} <= set(label_records) & set(hfid_records)
        assert ("main", TAG) not in hfid_records
        assert created == len(label_records) + len(hfid_records)

        context = self.context(admin_account, "main")
        await display_labels_setup_jinja2(context=context, branch_name="main")
        await hfid_setup(context=context, branch_name="main")

        assert workflow_recorder.submit_calls == []
