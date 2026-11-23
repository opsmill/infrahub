from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.protocols import CoreArtifact, CoreArtifactCheck

from infrahub import config
from infrahub.artifacts import tasks as artifact_tasks
from infrahub.artifacts.models import CheckArtifactCreate
from infrahub.artifacts.render_request import RenderRequestResult, request_external_render
from infrahub.artifacts.tasks import create
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import ArtifactStatus, EventType, InfrahubKind, ValidatorConclusion
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.validators.checks_runner import CheckPending
from infrahub.events.artifact_action import ArtifactRenderRequestedEvent
from infrahub.git import tasks as git_tasks
from infrahub.git.models import RequestArtifactGenerate
from infrahub.git.tasks import generate_artifact
from infrahub.server import app
from infrahub.workers.dependencies import build_client, build_event_service
from infrahub.workflows.catalogue import GRAPHQL_QUERY_GROUP_UPDATE
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.dependency_override import override_dependency
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubAppWithoutLocalWorkflow
from tests.helpers.workflow_override import override_workflow

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from tests.adapters.message_bus import BusSimulator
    from tests.helpers.test_client import InfrahubTestClient

PUBLIC_URL = "https://infrahub.example.com"
RENDER_TIMEOUT = 600
MAX_EVENT_SIZE_BYTES = 1_500_000
DEVICE = NodeSchema(
    name="Device",
    namespace="Testing",
    default_filter="name__value",
    display_label="name__value",
    inherit_from=["CoreArtifactTarget"],
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)
DEVICE_QUERY = """
query GetDevice($name: String!) {
  TestingDevice(name__value: $name) {
    edges { node { id name { value } } }
  }
}
"""


class TestRequestExternalRender(TestInfrahubAppWithoutLocalWorkflow):
    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(self, dependency_provider: Provider) -> AsyncGenerator[WorkflowRecorder, None]:
        with override_workflow(WorkflowRecorder(), dependency_provider=dependency_provider) as recorder:
            yield recorder

    @pytest.fixture(scope="class")
    async def service(self, workflow_recorder: WorkflowRecorder, test_client: InfrahubTestClient) -> InfrahubServices:
        # The recorder is installed before the app starts so that the API's workflow submissions reach it.
        return app.state.service

    @pytest.fixture(scope="class")
    async def client(
        self,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        bus_simulator: BusSimulator,
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
        with override_dependency(build_client, lambda: sdk_client, dependency_provider=dependency_provider):
            yield sdk_client

    @pytest.fixture(autouse=True)
    def clear_recorder(self, workflow_recorder: WorkflowRecorder) -> None:
        workflow_recorder.reset()

    @pytest.fixture(scope="class")
    async def dataset(
        self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient, admin_account: CoreAccount
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=SchemaRoot(nodes=[DEVICE]), update_db=True)

        device = await Node.init(db=db, schema=DEVICE.kind)
        await device.new(db=db, name="edge-01")
        await device.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(db=db, name="render-repo", location="https://example.com/render-repo.git")
        await repo.save(db=db)

        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(db=db, name="get_device", query=DEVICE_QUERY)
        await query.save(db=db)

        transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMEXTERNAL)
        await transform.new(
            db=db, name="device-config", version="1.5.0", query=query, repository=repo, timeout=RENDER_TIMEOUT
        )
        await transform.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="render-targets", members=[device])
        await group.save(db=db)

        definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await definition.new(
            db=db,
            name="device-config",
            artifact_name="device-config",
            targets=group,
            transformation=transform,
            content_type="text/plain",
            parameters={"value": {"name": "name__value"}},
        )
        await definition.save(db=db)

        artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
        await artifact.new(
            db=db, name="device-config", status="Ready", object=device, definition=definition, content_type="text/plain"
        )
        await artifact.save(db=db)

        return {"device": device, "query": query, "definition": definition, "artifact": artifact}

    @pytest.fixture
    async def subscribed_webhook(self, db: InfrahubDatabase, dataset: dict[str, Any]) -> AsyncGenerator[Node, None]:
        webhook = await _create_webhook(
            db=db,
            name="render-engine",
            event_type=EventType.ARTIFACT_RENDER_REQUESTED.value,
            branch_scope="all_branches",
        )
        yield webhook
        await webhook.delete(db=db)

    @pytest.fixture
    async def unrelated_webhooks(self, db: InfrahubDatabase, dataset: dict[str, Any]) -> AsyncGenerator[None, None]:
        webhooks = [
            await _create_webhook(
                db=db, name="node-created", event_type=EventType.NODE_CREATED.value, branch_scope="all_branches"
            ),
            await _create_webhook(
                db=db,
                name="other-branches",
                event_type=EventType.ARTIFACT_RENDER_REQUESTED.value,
                branch_scope="other_branches",
            ),
            await _create_webhook(db=db, name="inactive", event_type="all", branch_scope="all_branches", active=False),
            await _create_webhook(db=db, name="audit", event_type="all", branch_scope="all_branches"),
            await _create_webhook(
                db=db,
                name="other-kind",
                event_type=EventType.ARTIFACT_RENDER_REQUESTED.value,
                branch_scope="all_branches",
                node_kind="TestingRouter",
            ),
        ]
        yield
        for webhook in webhooks:
            await webhook.delete(db=db)

    async def _request(
        self,
        client: InfrahubClient,
        dataset: dict[str, Any],
        event_service: MemoryInfrahubEvent,
        branch: Branch,
        public_url: str | None = PUBLIC_URL,
        max_event_size_bytes: int = MAX_EVENT_SIZE_BYTES,
    ) -> tuple[RenderRequestResult, CoreArtifact]:
        artifact = await client.get(kind=CoreArtifact, id=dataset["artifact"].id, branch=branch.name)
        artifact.status.value = ArtifactStatus.READY.value
        await artifact.save()
        result = await request_external_render(
            client=client,
            event_service=event_service,
            artifact=artifact,
            model=_generate_model(dataset=dataset, branch=branch),
            transformation_name="device-config",
            transformation_version="1.5.0",
            public_url=public_url,
            max_event_size_bytes=max_event_size_bytes,
        )
        stored = await client.get(kind=CoreArtifact, id=artifact.id, branch=branch.name)
        return result, stored

    async def test_request_emits_one_event_and_marks_the_artifact_pending(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        dataset: dict[str, Any],
        subscribed_webhook: Node,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        event_service = MemoryInfrahubEvent()
        before = datetime.now(UTC)

        result, stored = await self._request(
            client=client, dataset=dataset, event_service=event_service, branch=default_branch
        )

        assert result.error is None
        assert result.render_id
        assert stored.status.value == ArtifactStatus.PENDING.value
        assert stored.render_request_id.value == result.render_id
        assert stored.render_deadline.value is not None
        deadline = datetime.fromisoformat(stored.render_deadline.value)
        assert before + timedelta(seconds=RENDER_TIMEOUT) <= deadline + timedelta(seconds=1)
        assert deadline <= datetime.now(UTC) + timedelta(seconds=RENDER_TIMEOUT)

        group_updates = workflow_recorder.get_submit_calls_for(GRAPHQL_QUERY_GROUP_UPDATE)
        assert len(group_updates) == 1
        assert group_updates[0]["parameters"]["model"].subscribers == [stored.id]

        assert len(event_service.events) == 1
        event = event_service.events[0]
        assert isinstance(event, ArtifactRenderRequestedEvent)
        assert event.render_id == result.render_id
        assert event.callback_url == f"{PUBLIC_URL}/api/artifact/render/{result.render_id}"
        assert event.deadline == deadline
        assert event.artifact_id == stored.id
        assert event.target_id == dataset["device"].id
        assert event.target_kind == DEVICE.kind
        assert event.transformation_version == "1.5.0"
        assert event.branch == default_branch.name
        assert event.query_result == {
            "TestingDevice": {"edges": [{"node": {"id": dataset["device"].id, "name": {"value": "edge-01"}}}]}
        }

    async def test_request_without_subscribed_webhook_sets_error(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        dataset: dict[str, Any],
        unrelated_webhooks: None,
    ) -> None:
        event_service = MemoryInfrahubEvent()

        result, stored = await self._request(
            client=client, dataset=dataset, event_service=event_service, branch=default_branch
        )

        assert result.render_id is None
        assert result.error == "no webhook subscribed to infrahub.artifact.render_requested"
        assert stored.status.value == ArtifactStatus.ERROR.value
        assert event_service.events == []

    async def test_request_without_public_url_sets_error(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        dataset: dict[str, Any],
        subscribed_webhook: Node,
    ) -> None:
        event_service = MemoryInfrahubEvent()

        result, stored = await self._request(
            client=client, dataset=dataset, event_service=event_service, branch=default_branch, public_url=None
        )

        assert result.error == "main.public_url must be set for external transformations"
        assert stored.status.value == ArtifactStatus.ERROR.value
        assert event_service.events == []

    async def test_request_over_the_event_size_limit_sets_error(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        dataset: dict[str, Any],
        subscribed_webhook: Node,
    ) -> None:
        event_service = MemoryInfrahubEvent()

        result, stored = await self._request(
            client=client, dataset=dataset, event_service=event_service, branch=default_branch, max_event_size_bytes=100
        )

        assert result.error is not None
        assert re.fullmatch(r"query result too large for a render request \(\d+ bytes, limit 100\)", result.error)
        assert stored.status.value == ArtifactStatus.ERROR.value
        assert stored.render_request_id.value is None
        assert event_service.events == []

    async def test_proposed_change_check_waits_for_the_external_engine(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        dataset: dict[str, Any],
        subscribed_webhook: Node,
        dependency_provider: Provider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(config.SETTINGS.main, "public_url", PUBLIC_URL)
        branch = await create_branch(branch_name="pc-check-waits", db=db)
        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await proposed_change.new(
            db=db, name="check waits", source_branch=branch.name, destination_branch=default_branch.name
        )
        await proposed_change.save(db=db)
        validator = await Node.init(db=db, schema=InfrahubKind.ARTIFACTVALIDATOR)
        await validator.new(
            db=db, label="Artifact Validator", proposed_change=proposed_change, definition=dataset["definition"]
        )
        await validator.save(db=db)
        model = CheckArtifactCreate(
            **_generate_model(dataset=dataset, branch=branch).model_dump(exclude={"context"}),
            context=_generate_model(dataset=dataset, branch=branch).context,
            validator_id=validator.id,
        )
        event_service = MemoryInfrahubEvent()

        with override_dependency(build_event_service, lambda: event_service, dependency_provider=dependency_provider):
            result = await create(model=model)

        assert result == CheckPending.PENDING
        checks = await client.filters(kind=CoreArtifactCheck, validator__ids=[validator.id])
        assert [(check.conclusion.value, check.message.value, check.artifact_id.value) for check in checks] == [
            (ValidatorConclusion.UNKNOWN.value, "waiting for external engine", dataset["artifact"].id)
        ]
        assert [type(event) for event in event_service.events] == [ArtifactRenderRequestedEvent]

    async def test_proposed_change_check_fails_when_the_request_raises(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        dataset: dict[str, Any],
        subscribed_webhook: Node,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def _raise(**kwargs: Any) -> RenderRequestResult:
            raise RuntimeError("event broker unavailable")

        monkeypatch.setattr(artifact_tasks, "request_external_render", _raise)
        branch = await create_branch(branch_name="pc-check-raises", db=db)
        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await proposed_change.new(
            db=db, name="check raises", source_branch=branch.name, destination_branch=default_branch.name
        )
        await proposed_change.save(db=db)
        validator = await Node.init(db=db, schema=InfrahubKind.ARTIFACTVALIDATOR)
        await validator.new(
            db=db, label="Artifact Validator", proposed_change=proposed_change, definition=dataset["definition"]
        )
        await validator.save(db=db)
        generate_model = _generate_model(dataset=dataset, branch=branch)
        model = CheckArtifactCreate(
            **generate_model.model_dump(exclude={"context"}), context=generate_model.context, validator_id=validator.id
        )

        result = await create(model=model)

        assert result == ValidatorConclusion.FAILURE
        checks = await client.filters(kind=CoreArtifactCheck, validator__ids=[validator.id])
        assert [(check.conclusion.value, check.message.value) for check in checks] == [
            (ValidatorConclusion.FAILURE.value, "Failed to render artifact: event broker unavailable")
        ]
        stored = await client.get(kind=CoreArtifact, id=dataset["artifact"].id, branch=branch.name)
        assert stored.status.value == ArtifactStatus.ERROR.value

    async def test_generate_artifact_requests_an_external_render(
        self,
        default_branch: Branch,
        client: InfrahubClient,
        dataset: dict[str, Any],
        subscribed_webhook: Node,
        dependency_provider: Provider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(config.SETTINGS.main, "public_url", PUBLIC_URL)
        event_service = MemoryInfrahubEvent()

        with override_dependency(build_event_service, lambda: event_service, dependency_provider=dependency_provider):
            await generate_artifact(model=_generate_model(dataset=dataset, branch=default_branch))

        stored = await client.get(kind=CoreArtifact, id=dataset["artifact"].id, branch=default_branch.name)
        assert stored.status.value == ArtifactStatus.PENDING.value
        assert [type(event) for event in event_service.events] == [ArtifactRenderRequestedEvent]

    async def test_generate_artifact_sets_error_when_the_request_raises(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        dataset: dict[str, Any],
        subscribed_webhook: Node,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def _raise(**kwargs: Any) -> RenderRequestResult:
            raise RuntimeError("Cannot query field 'description' on type 'TestDevice'")

        monkeypatch.setattr(git_tasks, "request_external_render", _raise)
        branch = await create_branch(branch_name="generate-raises", db=db)

        with pytest.raises(RuntimeError, match="Cannot query field"):
            await generate_artifact(model=_generate_model(dataset=dataset, branch=branch))

        stored = await client.get(kind=CoreArtifact, id=dataset["artifact"].id, branch=branch.name)
        assert stored.status.value == ArtifactStatus.ERROR.value


async def _create_webhook(
    db: InfrahubDatabase,
    name: str,
    event_type: str,
    branch_scope: str,
    active: bool = True,
    node_kind: str | None = None,
) -> Node:
    webhook = await Node.init(db=db, schema=InfrahubKind.STANDARDWEBHOOK)
    await webhook.new(
        db=db,
        name=name,
        url="https://engine.example.com/render",
        shared_key="secret",
        event_type=event_type,
        branch_scope=branch_scope,
        active=active,
        node_kind=node_kind,
    )
    await webhook.save(db=db)
    return webhook


def _generate_model(dataset: dict[str, Any], branch: Branch) -> RequestArtifactGenerate:
    return RequestArtifactGenerate(
        artifact_name="device-config",
        artifact_definition=dataset["definition"].id,
        artifact_definition_name="device-config",
        commit="0000000",
        content_type="text/plain",
        transform_type=InfrahubKind.TRANSFORMEXTERNAL,
        transform_location="",
        repository_id="",
        repository_name="render-repo",
        repository_kind=InfrahubKind.REPOSITORY,
        branch_name=branch.name,
        target_id=dataset["device"].id,
        target_kind=DEVICE.kind,
        target_name="edge-01",
        artifact_id=dataset["artifact"].id,
        query="get_device",
        query_id=dataset["query"].id,
        timeout=RENDER_TIMEOUT,
        variables={"name": "edge-01"},
        context=InfrahubContext(
            branch=BranchContext(name=branch.name),
            account=AccountSession(account_id="admin", authenticated=True, auth_type=AuthType.API),
        ),
    )
