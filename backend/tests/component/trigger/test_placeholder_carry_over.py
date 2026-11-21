from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from prefect.client.orchestration import get_client as get_prefect_client

from infrahub.core.template_fingerprint.collector import collect_schema_fingerprints
from infrahub.core.template_fingerprint.models import FingerprintKey, TemplateFamily
from infrahub.core.template_fingerprint.repository import TemplateFingerprintRepository
from infrahub.display_labels.gather import gather_trigger_display_labels_jinja2
from infrahub.display_labels.models import DisplayLabelTriggerDefinition
from infrahub.display_labels.tasks import display_labels_setup_jinja2
from infrahub.hfid.gather import gather_trigger_hfid
from infrahub.hfid.models import HFIDTriggerDefinition
from infrahub.hfid.tasks import hfid_setup
from infrahub.trigger.constants import TRIGGER_PLACEHOLDER_FIELD
from infrahub.trigger.models import TriggerBranchDefinition, TriggerType
from infrahub.trigger.setup import gather_all_automations, setup_triggers
from infrahub.trigger.tasks import trigger_configure_all
from infrahub.workflows.catalogue import TRIGGER_UPDATE_DISPLAY_LABELS, TRIGGER_UPDATE_HFID
from tests.helpers.template_fingerprint import DEVICE, OWNER, TemplateSetupTestBase, schema_variant

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.trigger.models import TriggerDefinition
    from tests.adapters.workflow import WorkflowRecorder

BRANCHES = ["main", "carry-over-a", "carry-over/b"]
PLACEHOLDER_KINDS = [OWNER, DEVICE]
HAND_DELETED = f"display_label_jinja2::main::{OWNER}::by::{OWNER}"


def _placeholder(family: TemplateFamily, branch: str, kind: str, fingerprint: str) -> TriggerBranchDefinition:
    match family:
        case TemplateFamily.DISPLAY_LABEL_JINJA2:
            return DisplayLabelTriggerDefinition.new(
                branch=branch,
                node_kind=kind,
                target_kind=kind,
                template_hash=fingerprint,
                fields=[TRIGGER_PLACEHOLDER_FIELD],
            )
        case TemplateFamily.HUMAN_FRIENDLY_ID:
            return HFIDTriggerDefinition.new(
                branch=branch,
                node_kind=kind,
                target_kind=kind,
                hfid_hash=fingerprint,
                fields=[TRIGGER_PLACEHOLDER_FIELD],
            )


class TestPlaceholderCarryOver(TemplateSetupTestBase):
    """Upgrade from a release that kept one placeholder automation per kind and per branch in scope."""

    @pytest.fixture(scope="class")
    async def branches_in_scope(self, db: InfrahubDatabase, fingerprint_schema: None) -> None:
        for branch_name in BRANCHES[1:]:
            await self.create_branch_with_schema(db=db, branch_name=branch_name, schema=schema_variant(tag_note=True))

    @staticmethod
    def schema_fingerprints() -> dict[FingerprintKey, str]:
        return {
            FingerprintKey(family=family, branch=branch, kind=kind): fingerprints[kind]
            for family in TemplateFamily
            for branch, fingerprints in collect_schema_fingerprints(family).by_branch.items()
            for kind in PLACEHOLDER_KINDS
        }

    @staticmethod
    async def install_placeholders(fingerprints: dict[FingerprintKey, str]) -> None:
        """Configure the peer automations and the placeholder automations as the previous release did."""
        peer_triggers: dict[TemplateFamily, Sequence[TriggerDefinition]] = {
            TemplateFamily.DISPLAY_LABEL_JINJA2: await gather_trigger_display_labels_jinja2(),
            TemplateFamily.HUMAN_FRIENDLY_ID: await gather_trigger_hfid(),
        }
        async with get_prefect_client(sync_client=False) as prefect_client:
            for family, peers in peer_triggers.items():
                placeholders = [
                    _placeholder(family=key.family, branch=key.branch, kind=key.kind, fingerprint=fingerprint)
                    for key, fingerprint in fingerprints.items()
                    if key.family == family
                ]
                await setup_triggers(
                    client=prefect_client,
                    triggers=[*peers, *placeholders],
                    trigger_type=TriggerType(family.value),
                )

    @staticmethod
    async def placeholder_names() -> list[str]:
        async with get_prefect_client(sync_client=False) as prefect_client:
            automations = await gather_all_automations(client=prefect_client)
        return sorted(
            automation.name
            for automation in automations
            if TRIGGER_PLACEHOLDER_FIELD in automation.trigger.model_dump_json()
        )

    @staticmethod
    async def recorded_placeholder_kinds(db: InfrahubDatabase) -> dict[FingerprintKey, str]:
        repository = TemplateFingerprintRepository(db=db)
        return {
            record.key: record.fingerprint
            for family in TemplateFamily
            for record in await repository.get_by_family(family=family)
            if record.key.kind in PLACEHOLDER_KINDS
        }

    async def test_upgrade_carries_placeholder_fingerprints_over(
        self,
        db: InfrahubDatabase,
        branches_in_scope: None,
        workflow_recorder: WorkflowRecorder,
        admin_account: CoreAccount,
    ) -> None:
        fingerprints = self.schema_fingerprints()
        assert len(fingerprints) == len(TemplateFamily) * len(BRANCHES) * len(PLACEHOLDER_KINDS)
        await TemplateFingerprintRepository(db=db).delete(keys=list(fingerprints))
        await self.install_placeholders(fingerprints)
        async with get_prefect_client(sync_client=False) as prefect_client:
            hand_deleted = await prefect_client.read_automations_by_name(name=HAND_DELETED)
            await prefect_client.delete_automation(automation_id=hand_deleted[0].id)
        assert len(await self.placeholder_names()) == len(fingerprints) - 1

        await trigger_configure_all()

        assert await self.placeholder_names() == []
        hand_deleted_key = FingerprintKey(family=TemplateFamily.DISPLAY_LABEL_JINJA2, branch="main", kind=OWNER)
        carried_over = {key: value for key, value in fingerprints.items() if key != hand_deleted_key}
        assert await self.recorded_placeholder_kinds(db=db) == carried_over

        for branch_name in BRANCHES:
            context = self.context(admin_account, branch_name)
            await display_labels_setup_jinja2(context=context, branch_name=branch_name)
            await hfid_setup(context=context, branch_name=branch_name)

        assert self.submitted(workflow_recorder, TRIGGER_UPDATE_DISPLAY_LABELS) == [("main", OWNER)]
        assert self.submitted(workflow_recorder, TRIGGER_UPDATE_HFID) == []
        assert await self.recorded_placeholder_kinds(db=db) == fingerprints

    async def test_second_upgrade_keeps_existing_records(self, db: InfrahubDatabase, branches_in_scope: None) -> None:
        fingerprints = self.schema_fingerprints()
        assert await self.recorded_placeholder_kinds(db=db) == fingerprints
        await self.install_placeholders(dict.fromkeys(fingerprints, "stale-template"))

        await trigger_configure_all()

        assert await self.placeholder_names() == []
        assert await self.recorded_placeholder_kinds(db=db) == fingerprints
