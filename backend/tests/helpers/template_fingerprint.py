"""Schema, adapters and shared scenarios for the display label and HFID setup flow tests."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, AsyncGenerator, ClassVar

import pytest
from prefect.client.orchestration import get_client as get_prefect_client

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.initialization import create_branch
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.template_fingerprint.collector import collect_schema_fingerprints
from infrahub.core.template_fingerprint.models import FingerprintKey, RecordedFingerprint, TemplateFamily
from infrahub.core.template_fingerprint.repository import TemplateFingerprintRepository
from infrahub.server import app
from infrahub.trigger.constants import TRIGGER_PLACEHOLDER_FIELD
from infrahub.trigger.setup import gather_all_automations
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubAppWithoutLocalWorkflow
from tests.helpers.workflow_override import override_workflow

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from infrahub.services import InfrahubServices
    from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

OWNER = "TestingFpOwner"
DEVICE = "TestingFpDevice"
TAG = "TestingFpTag"

# The device display label reads its owner's name, so each family keeps a peer automation for the owner.
FP_OWNER = NodeSchema(
    name="FpOwner",
    namespace="Testing",
    display_label="{{ name__value }}",
    human_friendly_id=["name__value"],
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="code", kind="Text", unique=True),
    ],
)
FP_DEVICE = NodeSchema(
    name="FpDevice",
    namespace="Testing",
    display_label="{{ name__value }} of {{ owner__name__value }}",
    human_friendly_id=["name__value", "owner__name__value"],
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(name="owner", peer=OWNER, optional=False, cardinality=RelationshipCardinality.ONE),
    ],
)
FP_TAG = NodeSchema(
    name="FpTag",
    namespace="Testing",
    attributes=[AttributeSchema(name="name", kind="Text")],
)
FINGERPRINT_SCHEMA = SchemaRoot(nodes=[FP_OWNER, FP_DEVICE, FP_TAG])


def schema_variant(
    owner_display_label: str | None = None,
    owner_hfid: list[str] | None = None,
    device_hfid: list[str] | None = None,
    tag_hfid: list[str] | None = None,
    tag_note: bool = False,
) -> SchemaRoot:
    """Return the test schema with the given templates replaced."""
    schema = deepcopy(FINGERPRINT_SCHEMA)
    owner, device, tag = schema.nodes
    if owner_display_label is not None:
        owner.display_label = owner_display_label
    if owner_hfid is not None:
        owner.human_friendly_id = owner_hfid
    if device_hfid is not None:
        device.human_friendly_id = device_hfid
    if tag_hfid is not None:
        tag.human_friendly_id = tag_hfid
    if tag_note:
        tag.attributes.append(AttributeSchema(name="note", kind="Text", optional=True))
    return schema


class FailingWorkflow(WorkflowRecorder):
    """Records the calls like its parent, and raises on every submission of one workflow."""

    def __init__(self, failing: WorkflowDefinition) -> None:
        super().__init__()
        self.failing = failing

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> WorkflowInfo:
        info = await super().submit_workflow(
            workflow=workflow, context=context, parameters=parameters, tags=tags, priority=priority
        )
        if workflow == self.failing:
            raise RuntimeError("submission refused")
        return info


class TemplateSetupTestBase(TestInfrahubAppWithoutLocalWorkflow):
    """Fixtures shared by the display label and HFID setup flow tests.

    Every test starts with one record per kind on the default branch and every branch in scope, matching
    the schema, the state a completed setup run leaves.
    """

    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(
        self, service: InfrahubServices, dependency_provider: Provider
    ) -> AsyncGenerator[WorkflowRecorder, None]:
        with override_workflow(WorkflowRecorder(), dependency_provider=dependency_provider) as recorder:
            yield recorder

    @pytest.fixture(scope="class", autouse=True)
    async def service(self, workflow_local: WorkflowLocalExecution, test_client: Any) -> InfrahubServices:
        return app.state.service

    @pytest.fixture(scope="class")
    async def fingerprint_schema(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        await load_schema(db=db, schema=FINGERPRINT_SCHEMA, update_db=True)

    @pytest.fixture(autouse=True)
    async def recorded_current_schema(
        self, db: InfrahubDatabase, fingerprint_schema: None, workflow_recorder: WorkflowRecorder
    ) -> None:
        await db.execute_query(query="MATCH (f:TemplateFingerprint) DETACH DELETE f")
        records = [record for family in TemplateFamily for record in collect_schema_fingerprints(family).as_records()]
        await TemplateFingerprintRepository(db=db).upsert(records=records)
        workflow_recorder.reset()

    @staticmethod
    def context(admin_account: CoreAccount, branch_name: str) -> EventContext:
        branch = registry.get_branch_from_registry(branch=branch_name)
        account = AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id=admin_account.id)
        return InfrahubContext.init(branch=branch, account=account).to_event_context()

    @staticmethod
    def submitted(recorder: WorkflowRecorder, workflow: WorkflowDefinition) -> list[tuple[str, str]]:
        return sorted(
            (call["parameters"]["branch_name"], call["parameters"]["kind"])
            for call in recorder.get_submit_calls_for(workflow)
        )

    @staticmethod
    async def recorded(db: InfrahubDatabase, family: TemplateFamily) -> dict[tuple[str, str], str]:
        return {
            (record.key.branch, record.key.kind): record.fingerprint
            for record in await TemplateFingerprintRepository(db=db).get_by_family(family=family)
        }

    @staticmethod
    async def record(db: InfrahubDatabase, family: TemplateFamily, branch: str, kind: str, fingerprint: str) -> None:
        await TemplateFingerprintRepository(db=db).upsert(
            records=[
                RecordedFingerprint(
                    key=FingerprintKey(family=family, branch=branch, kind=kind), fingerprint=fingerprint
                )
            ]
        )

    @staticmethod
    async def create_branch_with_schema(db: InfrahubDatabase, branch_name: str, schema: SchemaRoot) -> None:
        await create_branch(branch_name=branch_name, db=db)
        await load_schema(db=db, schema=schema, branch_name=branch_name, update_db=True)

    @staticmethod
    async def automation_triggers(prefix: str) -> dict[str, str]:
        """The serialized trigger of each automation whose name starts with ``prefix``, by automation name."""
        async with get_prefect_client(sync_client=False) as prefect_client:
            automations = await gather_all_automations(client=prefect_client)
        return {
            automation.name: automation.trigger.model_dump_json()
            for automation in automations
            if automation.name.startswith(prefix)
        }


class TemplateSetupScenarios(TemplateSetupTestBase):
    """Scenarios that both setup flows must satisfy; a subclass names the family and runs its flow."""

    FAMILY: ClassVar[TemplateFamily]
    WORKFLOW: ClassVar[WorkflowDefinition]
    # The kind whose template ``changed_schema`` changes, and the peer automation the family keeps.
    CHANGED_KIND: ClassVar[str]
    PEER_AUTOMATION: ClassVar[str]
    PLACEHOLDER_AUTOMATION: ClassVar[str]
    # Both families run in one database, so each names its own branches.
    BRANCH_PREFIX: ClassVar[str]

    async def run_setup(self, context: EventContext, branch_name: str, event_name: str | None = None) -> None:
        raise NotImplementedError

    def changed_schema(self) -> SchemaRoot:
        raise NotImplementedError

    async def build_placeholder(self, branch_name: str) -> None:
        """Configure the peer automations of the family and the placeholder automation of the previous release."""
        raise NotImplementedError

    async def test_unchanged_schema_submits_nothing(
        self, db: InfrahubDatabase, workflow_recorder: WorkflowRecorder, admin_account: CoreAccount
    ) -> None:
        before = await self.recorded(db=db, family=self.FAMILY)

        await self.run_setup(context=self.context(admin_account, "main"), branch_name="main")

        assert self.submitted(workflow_recorder, self.WORKFLOW) == []
        assert await self.recorded(db=db, family=self.FAMILY) == before

    async def test_default_branch_change_submits_kind_and_records_it(
        self, db: InfrahubDatabase, workflow_recorder: WorkflowRecorder, admin_account: CoreAccount
    ) -> None:
        await load_schema(db=db, schema=self.changed_schema(), update_db=True)
        try:
            expected = collect_schema_fingerprints(self.FAMILY).by_branch["main"][self.CHANGED_KIND]

            await self.run_setup(context=self.context(admin_account, "main"), branch_name="main")

            assert self.submitted(workflow_recorder, self.WORKFLOW) == [("main", self.CHANGED_KIND)]
            assert (await self.recorded(db=db, family=self.FAMILY))["main", self.CHANGED_KIND] == expected
        finally:
            await load_schema(db=db, schema=FINGERPRINT_SCHEMA, update_db=True)

    async def test_second_run_for_same_change_submits_nothing(
        self, db: InfrahubDatabase, workflow_recorder: WorkflowRecorder, admin_account: CoreAccount
    ) -> None:
        await self.record(db=db, family=self.FAMILY, branch="main", kind=OWNER, fingerprint="older-template")

        await self.run_setup(context=self.context(admin_account, "main"), branch_name="main")
        await self.run_setup(context=self.context(admin_account, "main"), branch_name="main")

        assert self.submitted(workflow_recorder, self.WORKFLOW) == [("main", OWNER)]

    async def test_branch_identical_to_default_records_without_submitting(
        self, db: InfrahubDatabase, workflow_recorder: WorkflowRecorder, admin_account: CoreAccount
    ) -> None:
        await self.create_branch_with_schema(
            db=db, branch_name=f"{self.BRANCH_PREFIX}-identical", schema=schema_variant(tag_note=True)
        )

        await self.run_setup(
            context=self.context(admin_account, f"{self.BRANCH_PREFIX}-identical"),
            branch_name=f"{self.BRANCH_PREFIX}-identical",
        )

        assert self.submitted(workflow_recorder, self.WORKFLOW) == []
        recorded = await self.recorded(db=db, family=self.FAMILY)
        assert recorded[f"{self.BRANCH_PREFIX}-identical", OWNER] == recorded["main", OWNER]
        assert recorded[f"{self.BRANCH_PREFIX}-identical", DEVICE] == recorded["main", DEVICE]

    async def test_branch_different_from_default_submits_on_that_branch_only(
        self, db: InfrahubDatabase, workflow_recorder: WorkflowRecorder, admin_account: CoreAccount
    ) -> None:
        await self.create_branch_with_schema(
            db=db, branch_name=f"{self.BRANCH_PREFIX}-diverging", schema=self.changed_schema()
        )
        main_before = (await self.recorded(db=db, family=self.FAMILY))["main", self.CHANGED_KIND]

        await self.run_setup(
            context=self.context(admin_account, f"{self.BRANCH_PREFIX}-diverging"),
            branch_name=f"{self.BRANCH_PREFIX}-diverging",
        )

        assert self.submitted(workflow_recorder, self.WORKFLOW) == [
            (f"{self.BRANCH_PREFIX}-diverging", self.CHANGED_KIND)
        ]
        recorded = await self.recorded(db=db, family=self.FAMILY)
        assert recorded["main", self.CHANGED_KIND] == main_before
        assert recorded[f"{self.BRANCH_PREFIX}-diverging", self.CHANGED_KIND] != main_before

    async def test_failed_submission_keeps_record_and_next_run_submits_again(
        self,
        db: InfrahubDatabase,
        workflow_recorder: WorkflowRecorder,
        admin_account: CoreAccount,
        dependency_provider: Provider,
    ) -> None:
        await self.record(db=db, family=self.FAMILY, branch="main", kind=OWNER, fingerprint="older-template")

        with (
            override_workflow(FailingWorkflow(failing=self.WORKFLOW), dependency_provider=dependency_provider),
            pytest.raises(RuntimeError, match=r"^submission refused$"),
        ):
            await self.run_setup(context=self.context(admin_account, "main"), branch_name="main")

        assert (await self.recorded(db=db, family=self.FAMILY))["main", OWNER] == "older-template"

        await self.run_setup(context=self.context(admin_account, "main"), branch_name="main")

        assert self.submitted(workflow_recorder, self.WORKFLOW) == [("main", OWNER)]

    async def test_removed_kind_record_deleted_without_submission(
        self, db: InfrahubDatabase, workflow_recorder: WorkflowRecorder, admin_account: CoreAccount
    ) -> None:
        await self.record(db=db, family=self.FAMILY, branch="main", kind="TestingFpGone", fingerprint="gone")

        await self.run_setup(context=self.context(admin_account, "main"), branch_name="main")

        assert self.submitted(workflow_recorder, self.WORKFLOW) == []
        assert ("main", "TestingFpGone") not in await self.recorded(db=db, family=self.FAMILY)

    async def test_setup_removes_placeholder_and_keeps_peer_automation(
        self, db: InfrahubDatabase, workflow_recorder: WorkflowRecorder, admin_account: CoreAccount
    ) -> None:
        await self.build_placeholder(branch_name="main")
        prefix = f"{self.FAMILY.value}::main::"
        before = await self.automation_triggers(prefix)
        assert TRIGGER_PLACEHOLDER_FIELD in before[self.PLACEHOLDER_AUTOMATION]

        await self.run_setup(context=self.context(admin_account, "main"), branch_name="main")

        after = await self.automation_triggers(prefix)
        assert [name for name, trigger in after.items() if TRIGGER_PLACEHOLDER_FIELD in trigger] == []
        assert self.PLACEHOLDER_AUTOMATION not in after
        assert self.PEER_AUTOMATION in after
