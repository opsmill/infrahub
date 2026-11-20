from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.protocols import CoreArtifact as SdkCoreArtifact

from infrahub.artifacts.render_request import request_external_render
from infrahub.artifacts.render_result import RenderResultAcceptor, RenderResultPayload
from infrahub.artifacts.render_token import RenderTokenClaims
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core import registry
from infrahub.core.constants import ArtifactStatus, EventType, InfrahubKind, ValidatorConclusion, ValidatorState
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.protocols import CoreArtifact, CoreArtifactCheck, CoreValidator
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.events.validator_action import ValidatorFailedEvent, ValidatorPassedEvent
from infrahub.exceptions import RenderRequestNotActiveError
from infrahub.git.models import RequestArtifactGenerate
from infrahub.workers.dependencies import build_client
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
    from tests.adapters.message_bus import BusSimulator
    from tests.helpers.test_client import InfrahubTestClient

CONTENT_TYPE = "text/plain"
PUBLIC_URL = "https://infrahub.example.com"
RENDER_TIMEOUT = 600
MAX_EVENT_SIZE_BYTES = 1_500_000
MAX_CONTENT_BYTES = 1024 * 1024
RACE_ROUNDS = 5
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


@dataclass
class PendingRender:
    artifact_id: str
    render_id: str
    claims: RenderTokenClaims


@dataclass
class ValidatorConcurrencyCase:
    name: str
    bodies: list[RenderResultPayload]
    expected_conclusion: ValidatorConclusion
    expected_events: list[type]


VALIDATOR_CASES = [
    ValidatorConcurrencyCase(
        name="both_succeed",
        bodies=[
            RenderResultPayload(status="success", content="hostname edge-01\n"),
            RenderResultPayload(status="success", content="hostname edge-02\n"),
        ],
        expected_conclusion=ValidatorConclusion.SUCCESS,
        expected_events=[ValidatorPassedEvent],
    ),
    ValidatorConcurrencyCase(
        name="one_fails",
        bodies=[
            RenderResultPayload(status="success", content="hostname edge-01\n"),
            RenderResultPayload(status="failure", message="template variable mtu undefined"),
        ],
        expected_conclusion=ValidatorConclusion.FAILURE,
        expected_events=[ValidatorFailedEvent],
    ),
]


class TestRenderConcurrency(TestInfrahubAppWithoutLocalWorkflow):
    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(self, dependency_provider: Provider) -> AsyncGenerator[WorkflowRecorder, None]:
        with override_workflow(WorkflowRecorder(), dependency_provider=dependency_provider) as recorder:
            yield recorder

    @pytest.fixture(scope="class")
    async def client(
        self,
        workflow_recorder: WorkflowRecorder,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        bus_simulator: BusSimulator,
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

    @pytest.fixture(scope="class")
    async def dataset(
        self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient, admin_account: CoreAccount
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=SchemaRoot(nodes=[DEVICE]), update_db=True)

        devices = []
        for name in ("edge-01", "edge-02"):
            device = await Node.init(db=db, schema=DEVICE.kind)
            await device.new(db=db, name=name)
            await device.save(db=db)
            devices.append(device)

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
        await group.new(db=db, name="render-targets", members=devices)
        await group.save(db=db)

        definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await definition.new(
            db=db,
            name="device-config",
            artifact_name="device-config",
            targets=group,
            transformation=transform,
            content_type=CONTENT_TYPE,
            parameters={"value": {"name": "name__value"}},
        )
        await definition.save(db=db)

        artifacts = []
        for device in devices:
            artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
            await artifact.new(
                db=db,
                name="device-config",
                status="Ready",
                object=device,
                definition=definition,
                content_type=CONTENT_TYPE,
            )
            await artifact.save(db=db)
            artifacts.append(artifact)

        webhook = await Node.init(db=db, schema=InfrahubKind.STANDARDWEBHOOK)
        await webhook.new(
            db=db,
            name="render-engine",
            url="https://engine.example.com/render",
            shared_key="secret",
            event_type=EventType.ARTIFACT_RENDER_REQUESTED.value,
            branch_scope="all_branches",
        )
        await webhook.save(db=db)

        return {"devices": devices, "query": query, "definition": definition, "artifacts": artifacts}

    def _acceptor(self, db: InfrahubDatabase, event_service: MemoryInfrahubEvent) -> RenderResultAcceptor:
        return RenderResultAcceptor(
            db=db, storage=registry.storage, event_service=event_service, max_content_bytes=MAX_CONTENT_BYTES
        )

    async def test_callback_racing_a_new_request_never_leaves_its_content_on_the_new_request(
        self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient, dataset: dict[str, Any]
    ) -> None:
        artifact_id = dataset["artifacts"][0].id

        for round_number in range(RACE_ROUNDS):
            earlier = await _mark_pending(db=db, branch=default_branch, artifact_id=artifact_id)
            content = f"hostname edge-01 round {round_number}\n"
            sdk_artifact = await client.get(kind=SdkCoreArtifact, id=artifact_id, branch=default_branch.name)

            async with db.start_session() as callback_db:
                acceptor = self._acceptor(db=callback_db, event_service=MemoryInfrahubEvent())
                callback, request = await asyncio.gather(
                    acceptor.accept_render_result(
                        render_id=earlier.render_id,
                        claims=earlier.claims,
                        body=RenderResultPayload(status="success", content=content),
                    ),
                    request_external_render(
                        client=client,
                        event_service=MemoryInfrahubEvent(),
                        artifact=sdk_artifact,
                        model=_generate_model(dataset=dataset, branch=default_branch),
                        transformation_name="device-config",
                        transformation_version="1.5.0",
                        public_url=PUBLIC_URL,
                        max_event_size_bytes=MAX_EVENT_SIZE_BYTES,
                    ),
                    return_exceptions=True,
                )

            assert not isinstance(request, BaseException)
            assert request.error is None
            # The callback either stored its content before the new request, or was refused after it.
            if isinstance(callback, BaseException):
                assert isinstance(callback, RenderRequestNotActiveError)
            stored = await registry.manager.get_one_by_id_or_default_filter(
                db=db, id=artifact_id, kind=CoreArtifact, branch=default_branch
            )
            assert stored.render_request_id.value == request.render_id
            assert stored.status.get_value() == ArtifactStatus.PENDING.value
            assert stored.render_deadline.value is not None

    @pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in VALIDATOR_CASES])
    async def test_concurrent_callbacks_for_one_validator_complete_it_once(
        self, db: InfrahubDatabase, default_branch: Branch, dataset: dict[str, Any], case: ValidatorConcurrencyCase
    ) -> None:
        branch = await create_branch(branch_name=f"pc-{uuid4().hex[:8]}", db=db)
        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await proposed_change.new(
            db=db, name=f"render {branch.name}", source_branch=branch.name, destination_branch=default_branch.name
        )
        await proposed_change.save(db=db)

        validator = await Node.init(db=db, schema=InfrahubKind.ARTIFACTVALIDATOR)
        await validator.new(
            db=db,
            label="Artifact Validator: device-config",
            state=ValidatorState.IN_PROGRESS.value,
            conclusion=ValidatorConclusion.UNKNOWN.value,
            proposed_change=proposed_change,
            definition=dataset["definition"],
        )
        await validator.save(db=db)

        renders = []
        for artifact in dataset["artifacts"]:
            check = await Node.init(db=db, schema=InfrahubKind.ARTIFACTCHECK)
            await check.new(
                db=db,
                name=f"device-config: {artifact.id}",
                origin="render-repo",
                kind="ArtifactDefinition",
                validator=validator,
                message="waiting for external engine",
                conclusion=ValidatorConclusion.UNKNOWN.value,
                severity="info",
                artifact_id=artifact.id,
            )
            await check.save(db=db)
            renders.append(await _mark_pending(db=db, branch=branch, artifact_id=artifact.id))

        event_service = MemoryInfrahubEvent()
        async with db.start_session() as first_db, db.start_session() as second_db:
            await asyncio.gather(
                *[
                    self._acceptor(db=session, event_service=event_service).accept_render_result(
                        render_id=render.render_id, claims=render.claims, body=body
                    )
                    for session, render, body in zip((first_db, second_db), renders, case.bodies, strict=True)
                ]
            )

        stored = await registry.manager.get_one_by_id_or_default_filter(
            db=db, id=validator.id, kind=CoreValidator, branch=default_branch
        )
        assert stored.state.get_value() == ValidatorState.COMPLETED.value
        assert stored.conclusion.get_value() == case.expected_conclusion.value
        validator_events = [
            type(event)
            for event in event_service.events
            if isinstance(event, ValidatorPassedEvent | ValidatorFailedEvent)
        ]
        assert validator_events == case.expected_events
        checks = await stored.checks.get_peers(db=db, peer_type=CoreArtifactCheck)
        assert sorted(check.conclusion.get_value() for check in checks.values()) == sorted(
            ValidatorConclusion.SUCCESS.value if body.status == "success" else ValidatorConclusion.FAILURE.value
            for body in case.bodies
        )

    async def test_callback_keeps_a_recorded_failure_and_ignores_checks_of_earlier_runs(
        self, db: InfrahubDatabase, default_branch: Branch, dataset: dict[str, Any]
    ) -> None:
        branch = await create_branch(branch_name=f"pc-{uuid4().hex[:8]}", db=db)
        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await proposed_change.new(
            db=db, name=f"render {branch.name}", source_branch=branch.name, destination_branch=default_branch.name
        )
        await proposed_change.save(db=db)
        earlier_run = Timestamp()
        started_at = Timestamp()
        validators = []
        for previous_conclusion, earlier_check_conclusion in (
            (ValidatorConclusion.FAILURE, ValidatorConclusion.SUCCESS),
            (ValidatorConclusion.UNKNOWN, ValidatorConclusion.FAILURE),
        ):
            validator = await Node.init(db=db, schema=InfrahubKind.ARTIFACTVALIDATOR)
            await validator.new(
                db=db,
                label="Artifact Validator: device-config",
                state=ValidatorState.IN_PROGRESS.value,
                conclusion=previous_conclusion.value,
                started_at=started_at.to_string(),
                proposed_change=proposed_change,
                definition=dataset["definition"],
            )
            await validator.save(db=db)
            earlier_check = await Node.init(db=db, schema=InfrahubKind.ARTIFACTCHECK)
            await earlier_check.new(
                db=db,
                name="device-config: removed target",
                origin="render-repo",
                kind="ArtifactDefinition",
                validator=validator,
                conclusion=earlier_check_conclusion.value,
                severity="info",
                created_at=earlier_run.to_string(),
            )
            await earlier_check.save(db=db)
            validators.append(validator)

        artifact = dataset["artifacts"][0]
        for validator in validators:
            check = await Node.init(db=db, schema=InfrahubKind.ARTIFACTCHECK)
            await check.new(
                db=db,
                name=f"device-config: {artifact.id}",
                origin="render-repo",
                kind="ArtifactDefinition",
                validator=validator,
                message="waiting for external engine",
                conclusion=ValidatorConclusion.UNKNOWN.value,
                severity="info",
                artifact_id=artifact.id,
                created_at=Timestamp().to_string(),
            )
            await check.save(db=db)
        render = await _mark_pending(db=db, branch=branch, artifact_id=artifact.id)

        async with db.start_session() as session:
            await self._acceptor(db=session, event_service=MemoryInfrahubEvent()).accept_render_result(
                render_id=render.render_id,
                claims=render.claims,
                body=RenderResultPayload(status="success", content="hostname edge-01\n"),
            )

        conclusions = []
        for validator in validators:
            stored = await registry.manager.get_one_by_id_or_default_filter(
                db=db, id=validator.id, kind=CoreValidator, branch=default_branch
            )
            assert stored.state.get_value() == ValidatorState.COMPLETED.value
            conclusions.append(stored.conclusion.get_value())
        assert conclusions == [ValidatorConclusion.FAILURE.value, ValidatorConclusion.SUCCESS.value]


async def _mark_pending(db: InfrahubDatabase, branch: Branch, artifact_id: str) -> PendingRender:
    render_id = str(uuid4())
    artifact = await registry.manager.get_one_by_id_or_default_filter(
        db=db, id=artifact_id, kind=CoreArtifact, branch=branch
    )
    artifact.get_attribute("status").value = ArtifactStatus.PENDING.value
    artifact.render_request_id.value = render_id
    artifact.render_deadline.value = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    await artifact.save(db=db)
    return PendingRender(
        artifact_id=artifact_id,
        render_id=render_id,
        claims=RenderTokenClaims(render_id=render_id, artifact_id=artifact_id, branch=branch.name),
    )


def _generate_model(dataset: dict[str, Any], branch: Branch) -> RequestArtifactGenerate:
    return RequestArtifactGenerate(
        artifact_name="device-config",
        artifact_definition=dataset["definition"].id,
        artifact_definition_name="device-config",
        commit="0000000",
        content_type=CONTENT_TYPE,
        transform_type=InfrahubKind.TRANSFORMEXTERNAL,
        transform_location="",
        repository_id="",
        repository_name="render-repo",
        repository_kind=InfrahubKind.REPOSITORY,
        branch_name=branch.name,
        target_id=dataset["devices"][0].id,
        target_kind=DEVICE.kind,
        target_name="edge-01",
        artifact_id=dataset["artifacts"][0].id,
        query="get_device",
        query_id=dataset["query"].id,
        timeout=RENDER_TIMEOUT,
        variables={"name": "edge-01"},
        context=InfrahubContext(
            branch=BranchContext(name=branch.name),
            account=AccountSession(account_id="admin", authenticated=True, auth_type=AuthType.API),
        ),
        transformation_name="device-config",
        transformation_version="1.5.0",
    )
