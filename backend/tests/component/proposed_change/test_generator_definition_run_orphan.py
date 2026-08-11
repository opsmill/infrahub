from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import GeneratorInstanceStatus, InfrahubKind
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
from infrahub.generators.tasks import request_generator_definition_run
from infrahub.server import app
from infrahub.workers.dependencies import build_client, build_workflow
from infrahub.workflows.catalogue import REQUEST_GENERATOR_RUN
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
query GetGenDevice($ids: [ID!]!) {
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
            uniqueness_constraints=[["name__value"]],
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="color", kind="Text", optional=True),
            ],
        )
    ]
)


class TestGeneratorDefinitionRunToleratesOrphanInstance(TestInfrahubAppBase):
    """The post-merge generator run skips a generator instance whose target was deleted.

    Deleting a target node does not cascade to its generator instance, leaving an instance whose
    object peer cannot be resolved. Building the member-to-instance map must skip that orphan rather
    than raise, so the run still dispatches for the live members.
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
        workflow_recorder.reset()

    def _context(self, account: CoreAccount, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext(
            branch=BranchContext(name=default_branch.name),
            account=AccountSession(account_id=account.id, auth_type=AuthType.API),
        )

    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient) -> dict[str, Any]:
        await load_schema(db=db, schema=DEVICE_SCHEMA, update_db=True)

        live = await Node.init(db=db, schema="TestNetworkDevice")
        await live.new(db=db, name="live", color="red")
        await live.save(db=db)
        orphaned_target = await Node.init(db=db, schema="TestNetworkDevice")
        await orphaned_target.new(db=db, name="orphan-target", color="blue")
        await orphaned_target.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(
            db=db,
            name="gen-orphan-repo",
            location="https://github.com/test/gen-orphan.git",
            commit="1234567890abcdef1234567890abcdef12345678",
        )
        await repo.save(db=db)

        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(db=db, name="GetGenDevice", query=DEVICE_QUERY, models=["TestNetworkDevice"])
        await query.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="regen-targets", members=[live])
        await group.save(db=db)

        gendef = await Node.init(db=db, schema=InfrahubKind.GENERATORDEFINITION)
        await gendef.new(
            db=db,
            name="device-generator",
            query=query,
            repository=repo,
            targets=group,
            file_path="generators/device.py",
            class_name="DeviceGenerator",
            parameters={"value": {"name": "name__value"}},
        )
        await gendef.save(db=db)

        instance_live = await Node.init(db=db, schema=InfrahubKind.GENERATORINSTANCE)
        await instance_live.new(
            db=db, name="inst-live", status=GeneratorInstanceStatus.READY.value, object=live, definition=gendef
        )
        await instance_live.save(db=db)
        instance_orphan = await Node.init(db=db, schema=InfrahubKind.GENERATORINSTANCE)
        await instance_orphan.new(
            db=db,
            name="inst-orphan",
            status=GeneratorInstanceStatus.READY.value,
            object=orphaned_target,
            definition=gendef,
        )
        await instance_orphan.save(db=db)

        # Delete the target: its generator instance stays behind with an unresolvable object peer.
        await orphaned_target.delete(db=db)

        return {
            "definition_id": gendef.id,
            "repository_id": repo.id,
            "group_id": group.id,
            "query_id": query.id,
            "live_id": live.id,
        }

    def _model(self, dataset: dict[str, Any], branch: str) -> RequestGeneratorDefinitionRun:
        return RequestGeneratorDefinitionRun(
            branch=branch,
            generator_definition=ProposedChangeGeneratorDefinition(
                definition_id=dataset["definition_id"],
                definition_name="device-generator",
                class_name="DeviceGenerator",
                file_path="generators/device.py",
                query_name="GetGenDevice",
                query_id=dataset["query_id"],
                query_models=["TestNetworkDevice"],
                query_payload=DEVICE_QUERY,
                repository_id=dataset["repository_id"],
                parameters={"name": "name__value"},
                group_id=dataset["group_id"],
                convert_query_response=False,
                execute_in_proposed_change=False,
                execute_after_merge=True,
            ),
        )

    async def test_orphan_instance_is_skipped_and_live_member_runs(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        # The orphan instance really survived the target deletion, so the run exercises the guard.
        instances = await client.filters(
            kind=InfrahubKind.GENERATORINSTANCE, definition__ids=[dataset["definition_id"]], branch=default_branch.name
        )
        assert len(instances) == 2

        state = await request_generator_definition_run(
            model=self._model(dataset, default_branch.name),
            context=self._context(admin_account, default_branch),
            return_state=True,
        )

        # The orphan is skipped instead of raising, and the live member still gets a generator run.
        assert state.is_completed()
        targets = [
            call["parameters"]["model"].target_id
            for call in workflow_recorder.get_execute_calls_for(REQUEST_GENERATOR_RUN)
        ]
        assert targets == [dataset["live_id"]]
