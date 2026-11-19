from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.template_fingerprint.models import TemplateFamily
from infrahub.display_labels.tasks import display_labels_setup_jinja2
from infrahub.workflows.catalogue import TRIGGER_UPDATE_DISPLAY_LABELS
from tests.helpers.template_fingerprint import OWNER, TemplateSetupTestBase, schema_variant

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreAccount
    from infrahub.core.schema import SchemaRoot
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowRecorder

LABEL = TemplateFamily.DISPLAY_LABEL_JINJA2
DELETE_BATCH_SIZE = 100


class TestTemplateFingerprintCleanup(TemplateSetupTestBase):
    @staticmethod
    def diverging_schema() -> SchemaRoot:
        return schema_variant(owner_display_label="{{ name__value }} ({{ code__value }})")

    async def create_recorded_branch(
        self, db: InfrahubDatabase, admin_account: CoreAccount, branch_name: str
    ) -> None:
        await self.create_branch_with_schema(db=db, branch_name=branch_name, schema=self.diverging_schema())
        await display_labels_setup_jinja2(context=self.context(admin_account, branch_name), branch_name=branch_name)

    @staticmethod
    async def delete_branch(db: InfrahubDatabase, branch_name: str) -> None:
        branch = await Branch.get_by_name(db=db, name=branch_name)
        await BranchDataDeleter(db=db, batch_size=DELETE_BATCH_SIZE).delete(branch=branch)

    @staticmethod
    async def recorded_branches(db: InfrahubDatabase) -> set[str]:
        results = await db.execute_query(query="MATCH (f:TemplateFingerprint) RETURN DISTINCT f.branch AS branch")
        return {result["branch"] for result in results}

    async def test_delete_removes_only_the_branch_records(
        self, db: InfrahubDatabase, admin_account: CoreAccount
    ) -> None:
        await self.create_recorded_branch(db=db, admin_account=admin_account, branch_name="fp-deleted")
        main_before = await self.recorded(db=db, family=LABEL)
        main_before = {key: value for key, value in main_before.items() if key[0] == "main"}
        assert await self.recorded_branches(db=db) == {"main", "fp-deleted"}

        await self.delete_branch(db=db, branch_name="fp-deleted")
        await registry.purge_inactive_branches(db=db)

        assert await self.recorded_branches(db=db) == {"main"}
        assert await self.recorded(db=db, family=LABEL) == main_before

    async def test_setup_for_deleted_branch_still_in_registry_writes_no_record(
        self, db: InfrahubDatabase, admin_account: CoreAccount
    ) -> None:
        await self.create_recorded_branch(db=db, admin_account=admin_account, branch_name="fp-stale")
        await self.delete_branch(db=db, branch_name="fp-stale")
        assert "fp-stale" in registry.get_altered_schema_branches()

        try:
            await display_labels_setup_jinja2(context=self.context(admin_account, "fp-stale"), branch_name="fp-stale")

            assert "fp-stale" not in await self.recorded_branches(db=db)
        finally:
            await registry.purge_inactive_branches(db=db)

    async def test_recreated_branch_with_same_template_is_recomputed(
        self, db: InfrahubDatabase, workflow_recorder: WorkflowRecorder, admin_account: CoreAccount
    ) -> None:
        await self.create_recorded_branch(db=db, admin_account=admin_account, branch_name="fp-reused")
        await self.delete_branch(db=db, branch_name="fp-reused")
        await registry.purge_inactive_branches(db=db)
        workflow_recorder.reset()

        await self.create_recorded_branch(db=db, admin_account=admin_account, branch_name="fp-reused")

        assert self.submitted(workflow_recorder, TRIGGER_UPDATE_DISPLAY_LABELS) == [("fp-reused", OWNER)]
