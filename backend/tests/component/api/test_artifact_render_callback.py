from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from infrahub import config
from infrahub.artifacts.render_token import mint_render_token
from infrahub.core import registry
from infrahub.core.constants import ArtifactStatus, InfrahubKind
from infrahub.core.node import Node
from infrahub.core.protocols import CoreArtifact
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.events.artifact_action import ArtifactCreatedEvent, ArtifactUpdatedEvent
from infrahub.server import app
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubAppWithoutLocalWorkflow

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.helpers.test_client import InfrahubTestClient

CONTENT_TYPE = "text/plain"
RENDERED = "hostname edge-01\n"
BYTES_PER_MB = 1024 * 1024
DEVICE = NodeSchema(
    name="Device",
    namespace="Testing",
    default_filter="name__value",
    display_label="name__value",
    inherit_from=["CoreArtifactTarget"],
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)


@dataclass
class PendingRender:
    artifact_id: str
    render_id: str
    token: str
    headers: dict[str, str] = field(init=False)

    def __post_init__(self) -> None:
        self.headers = {"X-Infrahub-Render-Token": self.token}

    @property
    def url(self) -> str:
        return f"/api/artifact/render/{self.render_id}"


@dataclass
class RefusedCallbackTestCase:
    name: str
    body: dict[str, Any]
    expected_status: int


REFUSED_BODY_TEST_CASES = [
    RefusedCallbackTestCase(name="success_without_content", body={"status": "success"}, expected_status=400),
    RefusedCallbackTestCase(
        name="content_type_not_the_definition_one",
        body={"status": "success", "content": RENDERED, "content_type": "application/json"},
        expected_status=400,
    ),
    RefusedCallbackTestCase(name="failure_without_message", body={"status": "failure"}, expected_status=400),
    RefusedCallbackTestCase(name="unknown_status", body={"status": "done", "content": RENDERED}, expected_status=400),
]


class TestArtifactRenderCallback(TestInfrahubAppWithoutLocalWorkflow):
    @pytest.fixture(scope="class")
    async def dataset(
        self, db: InfrahubDatabase, default_branch: Branch, admin_account: CoreAccount
    ) -> dict[str, Node]:
        await load_schema(db=db, schema=SchemaRoot(nodes=[DEVICE]), update_db=True)

        device = await Node.init(db=db, schema=DEVICE.kind)
        await device.new(db=db, name="edge-01")
        await device.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(db=db, name="render-repo", location="https://example.com/render-repo.git")
        await repo.save(db=db)

        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(db=db, name="get_device", query="query { TestingDevice { edges { node { id } } } }")
        await query.save(db=db)

        transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMEXTERNAL)
        await transform.new(db=db, name="device-config", version="1.5.0", query=query, repository=repo)
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
            content_type=CONTENT_TYPE,
            parameters={"value": {"name": "name__value"}},
        )
        await definition.save(db=db)

        artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
        await artifact.new(
            db=db, name="device-config", status="Ready", object=device, definition=definition, content_type=CONTENT_TYPE
        )
        await artifact.save(db=db)

        return {"device": device, "definition": definition, "artifact": artifact}

    @pytest.fixture
    def events(self, test_client: InfrahubTestClient) -> Generator[MemoryInfrahubEvent, None, None]:
        service = app.state.service
        original = service.event
        service.event = MemoryInfrahubEvent()
        yield service.event
        service.event = original

    @pytest.fixture
    def max_file_size(self) -> Generator[int, None, None]:
        original = config.SETTINGS.storage.max_file_size
        config.SETTINGS.storage.max_file_size = 1
        yield config.SETTINGS.storage.max_file_size
        config.SETTINGS.storage.max_file_size = original

    @pytest.fixture
    async def pending(
        self, db: InfrahubDatabase, default_branch: Branch, dataset: dict[str, Node], max_file_size: int
    ) -> PendingRender:
        return await _mark_pending(db=db, branch=default_branch, artifact_id=dataset["artifact"].id)

    async def _get_artifact(self, db: InfrahubDatabase, branch: Branch, artifact_id: str) -> CoreArtifact:
        return await registry.manager.get_one_by_id_or_default_filter(
            db=db, id=artifact_id, kind=CoreArtifact, branch=branch
        )

    async def test_success_stores_the_content_and_marks_the_artifact_ready(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        test_client: InfrahubTestClient,
        pending: PendingRender,
        events: MemoryInfrahubEvent,
    ) -> None:
        response = await test_client.post(
            pending.url,
            headers=pending.headers,
            json={"status": "success", "content": RENDERED, "content_type": CONTENT_TYPE},
        )

        assert response.status_code == 204
        artifact = await self._get_artifact(db=db, branch=default_branch, artifact_id=pending.artifact_id)
        checksum = hashlib.md5(RENDERED.encode(), usedforsecurity=False).hexdigest()
        assert artifact.status.get_value() == ArtifactStatus.READY.value
        assert artifact.checksum.value == checksum
        assert artifact.render_deadline.value is None
        assert artifact.render_request_id.value == pending.render_id
        assert registry.storage.retrieve(identifier=artifact.storage_id.value) == RENDERED
        assert len(events.events) == 1
        event = events.events[0]
        assert isinstance(event, ArtifactCreatedEvent | ArtifactUpdatedEvent)
        assert event.node_id == pending.artifact_id
        assert event.checksum == checksum
        assert event.storage_id == artifact.storage_id.value

    async def test_unchanged_content_is_not_uploaded_again(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        test_client: InfrahubTestClient,
        pending: PendingRender,
        events: MemoryInfrahubEvent,
    ) -> None:
        first = await test_client.post(
            pending.url, headers=pending.headers, json={"status": "success", "content": RENDERED}
        )
        assert first.status_code == 204
        stored = await self._get_artifact(db=db, branch=default_branch, artifact_id=pending.artifact_id)
        events.events.clear()

        second_render = await _mark_pending(db=db, branch=default_branch, artifact_id=pending.artifact_id)
        response = await test_client.post(
            second_render.url, headers=second_render.headers, json={"status": "success", "content": RENDERED}
        )

        assert response.status_code == 204
        artifact = await self._get_artifact(db=db, branch=default_branch, artifact_id=pending.artifact_id)
        assert artifact.status.get_value() == ArtifactStatus.READY.value
        assert artifact.storage_id.value == stored.storage_id.value
        assert events.events == []

    async def test_failure_marks_the_artifact_in_error(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        test_client: InfrahubTestClient,
        pending: PendingRender,
        events: MemoryInfrahubEvent,
    ) -> None:
        response = await test_client.post(
            pending.url,
            headers=pending.headers,
            json={"status": "failure", "message": "template variable mtu undefined"},
        )

        assert response.status_code == 204
        artifact = await self._get_artifact(db=db, branch=default_branch, artifact_id=pending.artifact_id)
        assert artifact.status.get_value() == ArtifactStatus.ERROR.value
        assert artifact.render_deadline.value is None
        assert events.events == []

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REFUSED_BODY_TEST_CASES])
    async def test_invalid_body_is_refused(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        test_client: InfrahubTestClient,
        pending: PendingRender,
        test_case: RefusedCallbackTestCase,
    ) -> None:
        response = await test_client.post(pending.url, headers=pending.headers, json=test_case.body)

        assert response.status_code == test_case.expected_status
        assert response.json()["errors"][0]["extensions"]["code"] == test_case.expected_status
        await self._assert_still_pending(db=db, branch=default_branch, pending=pending)

    async def test_message_over_the_limit_is_refused(
        self, test_client: InfrahubTestClient, pending: PendingRender
    ) -> None:
        response = await test_client.post(
            pending.url, headers=pending.headers, json={"status": "failure", "message": "x" * 4097}
        )

        assert response.status_code == 400

    async def test_content_over_the_storage_limit_is_refused(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        test_client: InfrahubTestClient,
        pending: PendingRender,
        max_file_size: int,
    ) -> None:
        content = "x" * (max_file_size * BYTES_PER_MB + 1)

        response = await test_client.post(
            pending.url, headers=pending.headers, json={"status": "success", "content": content}
        )

        assert response.status_code == 413
        await self._assert_still_pending(db=db, branch=default_branch, pending=pending)

    async def test_request_without_token_is_refused(
        self, db: InfrahubDatabase, default_branch: Branch, test_client: InfrahubTestClient, pending: PendingRender
    ) -> None:
        response = await test_client.post(pending.url, json={"status": "success", "content": RENDERED})

        assert response.status_code == 401
        await self._assert_still_pending(db=db, branch=default_branch, pending=pending)

    async def test_expired_token_is_refused(
        self, db: InfrahubDatabase, default_branch: Branch, test_client: InfrahubTestClient, pending: PendingRender
    ) -> None:
        token = mint_render_token(
            render_id=pending.render_id,
            artifact_id=pending.artifact_id,
            branch=default_branch.name,
            deadline=datetime.now(UTC) - timedelta(minutes=1),
        )

        response = await test_client.post(
            pending.url,
            headers={"X-Infrahub-Render-Token": token},
            json={"status": "success", "content": RENDERED},
        )

        assert response.status_code == 401
        await self._assert_still_pending(db=db, branch=default_branch, pending=pending)

    async def test_api_key_is_refused(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        test_client: InfrahubTestClient,
        pending: PendingRender,
        api_admin_token: str,
    ) -> None:
        response = await test_client.post(
            pending.url, headers={"X-INFRAHUB-KEY": api_admin_token}, json={"status": "success", "content": RENDERED}
        )

        assert response.status_code == 401
        await self._assert_still_pending(db=db, branch=default_branch, pending=pending)

    async def test_token_for_another_render_is_forbidden(
        self, db: InfrahubDatabase, default_branch: Branch, test_client: InfrahubTestClient, pending: PendingRender
    ) -> None:
        response = await test_client.post(
            f"/api/artifact/render/{uuid4()}",
            headers=pending.headers,
            json={"status": "success", "content": RENDERED},
        )

        assert response.status_code == 403
        await self._assert_still_pending(db=db, branch=default_branch, pending=pending)

    async def test_replaced_request_is_a_conflict(
        self, db: InfrahubDatabase, default_branch: Branch, test_client: InfrahubTestClient, pending: PendingRender
    ) -> None:
        newer = await _mark_pending(db=db, branch=default_branch, artifact_id=pending.artifact_id)

        response = await test_client.post(
            pending.url, headers=pending.headers, json={"status": "success", "content": RENDERED}
        )

        assert response.status_code == 409
        await self._assert_still_pending(db=db, branch=default_branch, pending=newer)

    async def test_ended_request_is_a_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        test_client: InfrahubTestClient,
        pending: PendingRender,
        events: MemoryInfrahubEvent,
    ) -> None:
        first = await test_client.post(
            pending.url, headers=pending.headers, json={"status": "failure", "message": "engine crashed"}
        )
        assert first.status_code == 204

        response = await test_client.post(
            pending.url, headers=pending.headers, json={"status": "success", "content": RENDERED}
        )

        assert response.status_code == 409
        artifact = await self._get_artifact(db=db, branch=default_branch, artifact_id=pending.artifact_id)
        assert artifact.status.get_value() == ArtifactStatus.ERROR.value

    async def _assert_still_pending(self, db: InfrahubDatabase, branch: Branch, pending: PendingRender) -> None:
        artifact = await self._get_artifact(db=db, branch=branch, artifact_id=pending.artifact_id)
        assert artifact.status.get_value() == ArtifactStatus.PENDING.value
        assert artifact.render_request_id.value == pending.render_id
        assert artifact.render_deadline.value is not None


async def _mark_pending(db: InfrahubDatabase, branch: Branch, artifact_id: str) -> PendingRender:
    render_id = str(uuid4())
    deadline = datetime.now(UTC) + timedelta(minutes=10)
    artifact = await registry.manager.get_one_by_id_or_default_filter(
        db=db, id=artifact_id, kind=CoreArtifact, branch=branch
    )
    artifact.status.value = ArtifactStatus.PENDING.value
    artifact.render_request_id.value = render_id
    artifact.render_deadline.value = deadline.isoformat()
    await artifact.save(db=db)
    token = mint_render_token(render_id=render_id, artifact_id=artifact_id, branch=branch.name, deadline=deadline)
    return PendingRender(artifact_id=artifact_id, render_id=render_id, token=token)
