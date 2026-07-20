from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.git.tasks import generate_request_artifact_definition
from infrahub.server import app
from infrahub.workers.dependencies import build_client, build_workflow
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_GENERATE
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubAppBase

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from tests.helpers.test_client import InfrahubTestClient

DEVICE_QUERY = """
query GetDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { name { value } } }
    }
}
"""

DEVICE_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="NetworkDevice",
            namespace="Test",
            default_filter="name__value",
            display_label="name__value",
            inherit_from=["CoreArtifactTarget"],
            uniqueness_constraints=[["name__value"]],
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="color", kind="Text", optional=True),
            ],
        )
    ]
)


class TestArtifactDefinitionGenerateMembers(TestInfrahubAppBase):
    """`generate_request_artifact_definition` honours the `members` filter without dropping new members.

    Selective regeneration narrows a definition to specific target-group members via `members`
    (member node ids), leaving `limit` (existing artifact ids) empty. A member with no existing
    artifact resolves to a null artifact id, so the legacy `limit` gate would skip it — the
    `members` path must not. Drives the real flow against a recording workflow backend and reads
    back which members a per-artifact generation was submitted for.
    """

    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(
        self,
        prefect: Generator[str, None, None],
        dependency_provider: Provider,
    ) -> AsyncGenerator[WorkflowRecorder, None]:
        original = config.OVERRIDE.workflow
        recorder = WorkflowRecorder()
        config.OVERRIDE.workflow = recorder
        with dependency_provider.scope(build_workflow, lambda: recorder):
            yield recorder
        config.OVERRIDE.workflow = original

    @pytest.fixture(scope="class", autouse=True)
    async def service(self, test_client: InfrahubTestClient) -> InfrahubServices:
        return app.state.service

    @pytest.fixture(scope="class")
    async def client(
        self,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        service: InfrahubServices,
        dependency_provider: Provider,
    ) -> AsyncGenerator[InfrahubClient, None]:
        sdk_client = InfrahubClient(
            config=Config(
                api_token=api_admin_token,
                requester=test_client.async_request,
                sync_requester=test_client.sync_request,
                schema_converge_timeout=5,
            )
        )
        original_client = service._client
        service._client = sdk_client
        with dependency_provider.scope(build_client, lambda: sdk_client):
            yield sdk_client
        service._client = original_client

    @pytest.fixture(autouse=True)
    def clear_recorder(self, workflow_recorder: WorkflowRecorder) -> None:
        workflow_recorder.execute_calls.clear()
        workflow_recorder.submit_calls.clear()

    def _context(self, account: CoreAccount, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext(
            branch=BranchContext(name=default_branch.name),
            account=AccountSession(account_id=account.id, auth_type=AuthType.API),
        )

    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient) -> dict[str, Any]:
        await load_schema(db=db, schema=DEVICE_SCHEMA, update_db=True)

        device1 = await Node.init(db=db, schema="TestNetworkDevice")
        await device1.new(db=db, name="dev1", color="red")
        await device1.save(db=db)
        device2 = await Node.init(db=db, schema="TestNetworkDevice")
        await device2.new(db=db, name="dev2", color="blue")
        await device2.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(
            db=db,
            name="artifact-members-repo",
            location="https://github.com/test/artifact-members.git",
            commit="1234567890abcdef1234567890abcdef12345678",
        )
        await repo.save(db=db)

        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(db=db, name="GetDevice", query=DEVICE_QUERY, models=["TestNetworkDevice"])
        await query.save(db=db)

        transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMJINJA2)
        await transform.new(db=db, name="render-jinja", query=query, repository=repo, template_path="templates/d.j2")
        await transform.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="regen-targets", members=[device1, device2])
        await group.save(db=db)

        artdef = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artdef.new(
            db=db,
            name="device-artifact",
            targets=group,
            transformation=transform,
            content_type="text/plain",
            artifact_name="device-config",
            parameters={"value": {"name": "name__value"}},
        )
        await artdef.save(db=db)

        return {"artifact_definition_id": artdef.id, "device1_id": device1.id, "device2_id": device2.id}

    async def test_members_filter_generates_new_member_and_excludes_the_rest(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """`members=[dev1]` generates for dev1 (which has no existing artifact) and skips dev2."""
        model = RequestArtifactDefinitionGenerate(
            artifact_definition_id=dataset["artifact_definition_id"],
            artifact_definition_name="device-artifact",
            branch=default_branch.name,
            members=[dataset["device1_id"]],
        )
        await generate_request_artifact_definition(model=model, context=self._context(admin_account, default_branch))
        targets = {
            call["parameters"]["model"].target_id
            for call in workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_GENERATE)
        }
        # dev1 has no existing artifact (null artifact id); the members path must still generate it,
        # and dev2 is excluded because it is not in the filter.
        assert targets == {dataset["device1_id"]}

    async def test_empty_members_generates_all(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """An empty `members` filter means every live member is generated."""
        model = RequestArtifactDefinitionGenerate(
            artifact_definition_id=dataset["artifact_definition_id"],
            artifact_definition_name="device-artifact",
            branch=default_branch.name,
            members=[],
        )
        await generate_request_artifact_definition(model=model, context=self._context(admin_account, default_branch))
        targets = {
            call["parameters"]["model"].target_id
            for call in workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_GENERATE)
        }
        assert targets == {dataset["device1_id"], dataset["device2_id"]}
