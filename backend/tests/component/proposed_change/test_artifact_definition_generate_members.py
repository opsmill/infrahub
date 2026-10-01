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
    """`generate_request_artifact_definition` fans out one artifact generation per target-group member.

    Drives the real flow against a recording workflow backend and reads back the per-artifact
    generations it submitted.
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

    async def test_only_a_limited_regeneration_checks_the_stored_file(
        self,
        db: InfrahubDatabase,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """Regenerating given artifacts checks their stored file; regenerating the whole definition does not."""
        artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
        await artifact.new(
            db=db,
            name="device-config",
            definition=dataset["artifact_definition_id"],
            object=dataset["device2_id"],
            status="Ready",
            content_type="text/plain",
        )
        await artifact.save(db=db)
        context = self._context(admin_account, default_branch)
        base = {
            "artifact_definition_id": dataset["artifact_definition_id"],
            "artifact_definition_name": "device-artifact",
            "branch": default_branch.name,
        }

        await generate_request_artifact_definition(
            model=RequestArtifactDefinitionGenerate(**base, limit=[artifact.id]), context=context
        )
        await generate_request_artifact_definition(model=RequestArtifactDefinitionGenerate(**base), context=context)

        requests = [
            (call["parameters"]["model"].target_id, call["parameters"]["model"].check_stored_file)
            for call in workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_GENERATE)
        ]
        limited, *whole_definition = requests
        assert limited == (dataset["device2_id"], True)
        assert sorted(whole_definition) == sorted([(dataset["device1_id"], False), (dataset["device2_id"], False)])
