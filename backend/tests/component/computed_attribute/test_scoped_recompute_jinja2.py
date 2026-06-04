from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Generator

import pytest

from infrahub import config
from infrahub.auth import AccountSession, AuthType
from infrahub.computed_attribute.tasks import computed_attribute_setup_jinja2
from infrahub.context import InfrahubContext
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.events.schema_action import ChangedElementsPayload
from infrahub.server import app
from infrahub.workers.dependencies import build_workflow
from infrahub.workflows.catalogue import TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES
from infrahub.workflows.initialization import setup_task_manager
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubAppBase

if TYPE_CHECKING:
    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


# local_label/local_tag read local fields (name/role); remote_label reads the owner
# peer's name across the relationship.
JINJA2_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="ComputeOwner",
            namespace="Test",
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
        ),
        NodeSchema(
            name="ComputeDevice",
            namespace="Test",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="role", kind="Text"),
                AttributeSchema(name="description", kind="Text", optional=True),
                AttributeSchema(
                    name="local_label",
                    kind="Text",
                    read_only=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.JINJA2,
                        jinja2_template="{{ name__value }}-{{ role__value }}",
                    ),
                ),
                AttributeSchema(
                    name="local_tag",
                    kind="Text",
                    optional=True,
                    read_only=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.JINJA2,
                        jinja2_template="{{ role__value }}:{{ name__value }}",
                    ),
                ),
                AttributeSchema(
                    name="remote_label",
                    kind="Text",
                    read_only=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.JINJA2,
                        jinja2_template="{{ owner__name__value }}'s {{ name__value }}",
                    ),
                ),
            ],
            relationships=[
                RelationshipSchema(
                    name="owner",
                    peer="TestComputeOwner",
                    optional=False,
                    cardinality=RelationshipCardinality.ONE,
                ),
            ],
        ),
    ]
)


class TestScopedRecomputeJinja2(TestInfrahubAppBase):
    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(
        self,
        prefect: Generator[str, None, None],
        dependency_provider: Provider,
    ) -> AsyncGenerator[WorkflowRecorder, None]:
        original = config.OVERRIDE.workflow
        recorder = WorkflowRecorder()
        await setup_task_manager()
        config.OVERRIDE.workflow = recorder
        with dependency_provider.scope(build_workflow, lambda: recorder):
            yield recorder
        config.OVERRIDE.workflow = original

    @pytest.fixture(scope="class", autouse=True)
    async def service(self, test_client: Any) -> InfrahubServices:
        return app.state.service

    @pytest.fixture(autouse=True)
    def clear_recorder(self, workflow_recorder: WorkflowRecorder) -> None:
        workflow_recorder.execute_calls.clear()
        workflow_recorder.submit_calls.clear()

    @pytest.fixture(scope="class")
    async def jinja2_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        admin_account: CoreAccount,
    ) -> None:
        await load_schema(db=db, schema=JINJA2_SCHEMA, update_db=True)

    def _context(self, admin_account: CoreAccount, branch: Branch) -> InfrahubContext:
        account = AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id=admin_account.id, role="admin")
        return InfrahubContext.init(branch=branch, account=account)

    @staticmethod
    def _submitted_attribute_names(recorder: WorkflowRecorder) -> set[str]:
        return {
            call["parameters"]["computed_attribute_name"]
            for call in recorder.get_submit_calls_for(TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES)
        }

    async def _run(
        self, default_branch: Branch, admin_account: CoreAccount, changed_elements: ChangedElementsPayload | None
    ) -> None:
        await computed_attribute_setup_jinja2(
            context=self._context(admin_account, default_branch),
            branch_name=default_branch.name,
            changed_elements=changed_elements,
        )

    async def test_unrelated_change_submits_no_jinja2_recompute(
        self,
        jinja2_dataset: None,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """A change to a field no template reads submits zero recompute jobs."""
        await self._run(
            default_branch,
            admin_account,
            ChangedElementsPayload(changed_fields={"TestComputeDevice": ["description"]}),
        )

        assert workflow_recorder.get_submit_calls_for(TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES) == []

    async def test_relationship_field_change_recomputes_dependent_attribute(
        self,
        jinja2_dataset: None,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """A change to a peer field read across the owner relationship recomputes the dependent attribute."""
        await self._run(
            default_branch,
            admin_account,
            ChangedElementsPayload(changed_fields={"TestComputeOwner": ["name"]}),
        )

        assert "remote_label" in self._submitted_attribute_names(workflow_recorder)

    async def test_local_field_change_recomputes_dependent_attribute(
        self,
        jinja2_dataset: None,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """A change to a locally-read field recomputes the dependent attribute."""
        await self._run(
            default_branch,
            admin_account,
            ChangedElementsPayload(changed_fields={"TestComputeDevice": ["role"]}),
        )

        submitted = self._submitted_attribute_names(workflow_recorder)
        # Both attributes that read `role` locally must recompute, not just the first match.
        assert "local_label" in submitted
        assert "local_tag" in submitted
        assert "remote_label" not in submitted

    async def test_own_definition_change_recomputes_attribute(
        self,
        jinja2_dataset: None,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """An edit to the attribute's own definition recomputes it."""
        await self._run(
            default_branch,
            admin_account,
            ChangedElementsPayload(changed_fields={"TestComputeDevice": ["local_label"]}),
        )

        assert "local_label" in self._submitted_attribute_names(workflow_recorder)

    async def test_no_changed_elements_triggers_full_recompute(
        self,
        jinja2_dataset: None,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """Without a change set, fall back to recomputing every computed attribute on the branch."""
        await self._run(default_branch, admin_account, None)

        assert self._submitted_attribute_names(workflow_recorder) == {"local_label", "local_tag", "remote_label"}
