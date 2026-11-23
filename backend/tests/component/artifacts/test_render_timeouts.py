from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from infrahub_sdk.timestamp import Timestamp

from infrahub.artifacts.render_result import fail_undelivered_render
from infrahub.artifacts.render_token import RenderTokenRequest, mint_render_token
from infrahub.artifacts.timeouts import RENDER_TIMEOUT_MESSAGE, RenderTimeout, expire_overdue_renders
from infrahub.core import registry
from infrahub.core.constants import ArtifactStatus, InfrahubKind, ValidatorConclusion, ValidatorState
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.protocols import CoreArtifact, CoreArtifactCheck, CoreValidator
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.events.validator_action import ValidatorFailedEvent
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubAppWithoutLocalWorkflow

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.helpers.test_client import InfrahubTestClient

CONTENT_TYPE = "text/plain"
TRANSFORMATION_NAME = "device-config"
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
    deadline: datetime
    token: str


class TestRenderTimeouts(TestInfrahubAppWithoutLocalWorkflow):
    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, default_branch: Branch, admin_account: CoreAccount) -> dict[str, Any]:
        await load_schema(db=db, schema=SchemaRoot(nodes=[DEVICE]), update_db=True)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(db=db, name="render-repo", location="https://example.com/render-repo.git")
        await repo.save(db=db)

        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(db=db, name="get_device", query="query { TestingDevice { edges { node { id } } } }")
        await query.save(db=db)

        transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMEXTERNAL)
        await transform.new(db=db, name=TRANSFORMATION_NAME, version="1.5.0", query=query, repository=repo)
        await transform.save(db=db)

        devices = []
        for name in ("edge-01", "edge-02"):
            device = await Node.init(db=db, schema=DEVICE.kind)
            await device.new(db=db, name=name)
            await device.save(db=db)
            devices.append(device)

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

        return {
            "definition": definition,
            "artifacts": artifacts,
            "devices": devices,
            "query": query,
            "repo": repo,
            "group": group,
        }

    async def test_sweep_fails_only_the_overdue_render_and_its_check(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        test_client: InfrahubTestClient,
        dataset: dict[str, Any],
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

        overdue_artifact, on_time_artifact = dataset["artifacts"]
        check = await Node.init(db=db, schema=InfrahubKind.ARTIFACTCHECK)
        await check.new(
            db=db,
            name=f"device-config: {overdue_artifact.id}",
            origin="render-repo",
            kind="ArtifactDefinition",
            validator=validator,
            message="waiting for external engine",
            conclusion=ValidatorConclusion.UNKNOWN.value,
            severity="info",
            artifact_id=overdue_artifact.id,
        )
        await check.save(db=db)

        overdue = await _mark_pending(
            db=db, branch=branch, artifact_id=overdue_artifact.id, deadline=datetime.now(UTC) + timedelta(minutes=10)
        )
        on_time = await _mark_pending(
            db=db, branch=branch, artifact_id=on_time_artifact.id, deadline=overdue.deadline + timedelta(minutes=10)
        )

        # The sweep runs as if after the first deadline, so the engine's token is still valid for the late callback.
        event_service = MemoryInfrahubEvent()
        timeouts = await expire_overdue_renders(
            db=db, event_service=event_service, now=Timestamp((overdue.deadline + timedelta(seconds=1)).isoformat())
        )

        assert timeouts == [
            RenderTimeout(artifact_id=overdue.artifact_id, branch=branch.name, transformation_name=TRANSFORMATION_NAME)
        ]
        expired = await _get_artifact(db=db, branch=branch, artifact_id=overdue.artifact_id)
        assert expired.status.get_value() == ArtifactStatus.ERROR.value
        assert expired.render_deadline.value is None
        untouched = await _get_artifact(db=db, branch=branch, artifact_id=on_time.artifact_id)
        assert untouched.status.get_value() == ArtifactStatus.PENDING.value
        assert untouched.render_request_id.value == on_time.render_id
        assert untouched.render_deadline.value is not None

        stored_check = await registry.manager.get_one_by_id_or_default_filter(
            db=db, id=check.id, kind=CoreArtifactCheck, branch=default_branch
        )
        assert stored_check.conclusion.get_value() == ValidatorConclusion.FAILURE.value
        assert RENDER_TIMEOUT_MESSAGE in str(stored_check.message.value)
        stored_validator = await registry.manager.get_one_by_id_or_default_filter(
            db=db, id=validator.id, kind=CoreValidator, branch=default_branch
        )
        assert stored_validator.state.get_value() == ValidatorState.COMPLETED.value
        assert stored_validator.conclusion.get_value() == ValidatorConclusion.FAILURE.value
        assert [type(event) for event in event_service.events if isinstance(event, ValidatorFailedEvent)] == [
            ValidatorFailedEvent
        ]

        response = await test_client.post(
            f"/api/artifact/render/{overdue.render_id}",
            headers={"X-Infrahub-Render-Token": overdue.token},
            json={"status": "success", "content": "hostname edge-01\n"},
        )

        assert response.status_code == 409
        after_callback = await _get_artifact(db=db, branch=branch, artifact_id=overdue.artifact_id)
        assert after_callback.status.get_value() == ArtifactStatus.ERROR.value

    async def test_undelivered_request_fails_the_render_before_its_deadline(
        self, db: InfrahubDatabase, default_branch: Branch, dataset: dict[str, Any]
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
        artifact = dataset["artifacts"][0]
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
        pending = await _mark_pending(
            db=db, branch=branch, artifact_id=artifact.id, deadline=datetime.now(UTC) + timedelta(minutes=10)
        )
        event_service = MemoryInfrahubEvent()

        replaced = RenderTokenRequest(
            render_id=str(uuid4()), artifact_id=artifact.id, branch=branch.name, deadline=pending.deadline
        )
        assert not await fail_undelivered_render(
            db=db, event_service=event_service, request=replaced, reason="HTTP 503 from the engine"
        )
        still_pending = await _get_artifact(db=db, branch=branch, artifact_id=artifact.id)
        assert still_pending.status.get_value() == ArtifactStatus.PENDING.value

        current = RenderTokenRequest(
            render_id=pending.render_id, artifact_id=artifact.id, branch=branch.name, deadline=pending.deadline
        )
        assert await fail_undelivered_render(
            db=db, event_service=event_service, request=current, reason="HTTP 503 from the engine"
        )

        failed = await _get_artifact(db=db, branch=branch, artifact_id=artifact.id)
        assert failed.status.get_value() == ArtifactStatus.ERROR.value
        assert failed.render_deadline.value is None
        stored_check = await registry.manager.get_one_by_id_or_default_filter(
            db=db, id=check.id, kind=CoreArtifactCheck, branch=default_branch
        )
        assert stored_check.conclusion.get_value() == ValidatorConclusion.FAILURE.value
        assert (
            stored_check.message.value
            == "Failed to render artifact: render request could not be delivered: HTTP 503 from the engine"
        )
        stored_validator = await registry.manager.get_one_by_id_or_default_filter(
            db=db, id=validator.id, kind=CoreValidator, branch=default_branch
        )
        assert stored_validator.conclusion.get_value() == ValidatorConclusion.FAILURE.value

    async def test_progress_report_moves_the_deadline_and_returns_a_new_token(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        test_client: InfrahubTestClient,
        dataset: dict[str, Any],
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
        artifact = dataset["artifacts"][1]
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
        pending = await _mark_pending(
            db=db, branch=branch, artifact_id=artifact.id, deadline=datetime.now(UTC) + timedelta(seconds=10)
        )

        progress = await test_client.post(
            f"/api/artifact/render/{pending.render_id}",
            headers={"X-Infrahub-Render-Token": pending.token},
            json={"status": "running", "message": "pipeline 4812 queued"},
        )

        assert progress.status_code == 200
        body = progress.json()
        assert body["render_id"] == pending.render_id
        new_deadline = datetime.fromisoformat(body["deadline"])
        # The transformation has the schema's default timeout of 60 seconds.
        assert new_deadline > pending.deadline + timedelta(seconds=40)
        moved = await _get_artifact(db=db, branch=branch, artifact_id=artifact.id)
        assert moved.status.get_value() == ArtifactStatus.PENDING.value
        assert datetime.fromisoformat(str(moved.render_deadline.value)) == new_deadline
        waiting_check = await registry.manager.get_one_by_id_or_default_filter(
            db=db, id=check.id, kind=CoreArtifactCheck, branch=default_branch
        )
        assert waiting_check.conclusion.get_value() == ValidatorConclusion.UNKNOWN.value
        assert waiting_check.message.value == "waiting for external engine: pipeline 4812 queued"

        result = await test_client.post(
            f"/api/artifact/render/{pending.render_id}",
            headers={"X-Infrahub-Render-Token": body["token"]},
            json={"status": "success", "content": "hostname edge-02\n"},
        )

        assert result.status_code == 204
        rendered = await _get_artifact(db=db, branch=branch, artifact_id=artifact.id)
        assert rendered.status.get_value() == ArtifactStatus.READY.value

    async def test_sweep_expires_an_artifact_whose_transformation_is_gone(
        self, db: InfrahubDatabase, default_branch: Branch, dataset: dict[str, Any]
    ) -> None:
        orphan_transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMEXTERNAL)
        await orphan_transform.new(
            db=db, name="orphan", version="1.0.0", query=dataset["query"], repository=dataset["repo"]
        )
        await orphan_transform.save(db=db)
        orphan_definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await orphan_definition.new(
            db=db,
            name="orphan-config",
            artifact_name="orphan-config",
            targets=dataset["group"],
            transformation=orphan_transform,
            content_type=CONTENT_TYPE,
            parameters={"value": {"name": "name__value"}},
        )
        await orphan_definition.save(db=db)
        orphan = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
        await orphan.new(
            db=db,
            name="orphan-config",
            status="Ready",
            object=dataset["devices"][0],
            definition=orphan_definition,
            content_type=CONTENT_TYPE,
        )
        await orphan.save(db=db)

        branch = await create_branch(branch_name=f"sweep-{uuid4().hex[:8]}", db=db)
        branch_transform = await registry.manager.get_one(db=db, id=orphan_transform.id, branch=branch)
        assert branch_transform is not None
        await branch_transform.delete(db=db)
        deadline = datetime.now(UTC) + timedelta(minutes=10)
        broken = await _mark_pending(db=db, branch=branch, artifact_id=orphan.id, deadline=deadline)
        healthy = await _mark_pending(db=db, branch=branch, artifact_id=dataset["artifacts"][1].id, deadline=deadline)

        timeouts = await expire_overdue_renders(
            db=db, event_service=MemoryInfrahubEvent(), now=Timestamp((deadline + timedelta(seconds=1)).isoformat())
        )

        assert sorted(timeouts, key=lambda timeout: timeout.artifact_id == healthy.artifact_id) == [
            RenderTimeout(artifact_id=broken.artifact_id, branch=branch.name, transformation_name=None),
            RenderTimeout(artifact_id=healthy.artifact_id, branch=branch.name, transformation_name=TRANSFORMATION_NAME),
        ]
        for render in (broken, healthy):
            expired = await _get_artifact(db=db, branch=branch, artifact_id=render.artifact_id)
            assert expired.status.get_value() == ArtifactStatus.ERROR.value


async def _get_artifact(db: InfrahubDatabase, branch: Branch, artifact_id: str) -> CoreArtifact:
    return await registry.manager.get_one_by_id_or_default_filter(
        db=db, id=artifact_id, kind=CoreArtifact, branch=branch
    )


async def _mark_pending(db: InfrahubDatabase, branch: Branch, artifact_id: str, deadline: datetime) -> PendingRender:
    render_id = str(uuid4())
    artifact = await _get_artifact(db=db, branch=branch, artifact_id=artifact_id)
    artifact.get_attribute("status").value = ArtifactStatus.PENDING.value
    artifact.render_request_id.value = render_id
    artifact.render_deadline.value = deadline.isoformat()
    await artifact.save(db=db)
    token = mint_render_token(render_id=render_id, artifact_id=artifact_id, branch=branch.name, deadline=deadline)
    return PendingRender(artifact_id=artifact_id, render_id=render_id, deadline=deadline, token=token)
