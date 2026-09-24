from __future__ import annotations

import hashlib
import io
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.server import app
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE
from tests.adapters.storage import DummyObjectStorage
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.test_app import TestInfrahubAppWithoutLocalWorkflow
from tests.helpers.workflow_override import override_workflow

if TYPE_CHECKING:
    from collections.abc import Generator

    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from tests.helpers.test_client import InfrahubTestClient

CONFIG = b"hostname leaf01\nenable secret s3cret\n"
TAMPERED_CONFIG = b"hostname leaf01\nusername backdoor privilege 15 secret attacker\n"


def refused_message(storage_id: str) -> str:
    return f"The content of the artifact stored as {storage_id} does not match the recorded checksum and is not served."


def missing_checksum_message(storage_id: str) -> str:
    return f"The artifact stored as {storage_id} has no recorded checksum and is not served."


def md5(content: bytes) -> str:
    return hashlib.md5(content, usedforsecurity=False).hexdigest()


class TestArtifactIntegrity(TestInfrahubAppWithoutLocalWorkflow):
    """Artifact content is compared against its recorded checksum before the API serves it."""

    @pytest.fixture(scope="class")
    def workflow_recorder(self, dependency_provider: Provider) -> Generator[WorkflowRecorder, None, None]:
        with override_workflow(WorkflowRecorder(), dependency_provider=dependency_provider) as recorder:
            yield recorder

    @pytest.fixture(scope="class", autouse=True)
    async def service(self, workflow_recorder: WorkflowRecorder, test_client: InfrahubTestClient) -> InfrahubServices:
        return app.state.service

    @pytest.fixture(scope="class")
    def dummy_storage(self) -> Generator[DummyObjectStorage, None, None]:
        storage = DummyObjectStorage()
        original_storage = registry._storage
        registry._storage = storage
        yield storage
        registry._storage = original_storage

    @pytest.fixture
    def admin_headers(self, api_admin_token: str) -> dict[str, str]:
        return {"X-INFRAHUB-KEY": api_admin_token}

    @pytest.fixture
    async def artifact_definition(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
    ) -> Node:
        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="devices", members=[car_person_data_generic["c1"], car_person_data_generic["c2"]])
        await group.save(db=db)

        transform = await Node.init(db=db, schema="CoreTransformPython")
        await transform.new(
            db=db,
            name="startup_config",
            query=str(car_person_data_generic["q1"].id),
            repository=str(car_person_data_generic["r1"].id),
            file_path="transform01.py",
            class_name="Transform01",
        )
        await transform.save(db=db)

        definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await definition.new(
            db=db,
            name="startup_config",
            targets=group,
            transformation=transform,
            content_type="text/plain",
            artifact_name="startup-config",
            parameters={"value": {"name": "name__value"}},
        )
        await definition.save(db=db)
        return definition

    async def create_artifact(
        self,
        db: InfrahubDatabase,
        dummy_storage: DummyObjectStorage,
        definition: Node,
        target: Node,
        storage_id: str,
        content: bytes,
        branch: Branch | None = None,
    ) -> Node:
        artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=branch)
        await artifact.new(
            db=db,
            name="startup-config",
            definition=definition,
            status="Ready",
            object=target,
            storage_id=storage_id,
            checksum=md5(content),
            content_type="text/plain",
        )
        await artifact.save(db=db)
        dummy_storage.store(identifier=storage_id, content=io.BytesIO(content))
        return artifact

    def regeneration_requests(self, workflow_recorder: WorkflowRecorder) -> list[RequestArtifactDefinitionGenerate]:
        return [
            call["parameters"]["model"]
            for call in workflow_recorder.get_submit_calls_for(workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE)
        ]

    async def test_intact_artifact_is_served_on_both_endpoints(
        self,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        admin_headers: dict[str, str],
        dummy_storage: DummyObjectStorage,
        artifact_definition: Node,
        car_person_data_generic: dict[str, Node],
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        workflow_recorder.reset()
        artifact = await self.create_artifact(
            db=db,
            dummy_storage=dummy_storage,
            definition=artifact_definition,
            target=car_person_data_generic["c1"],
            storage_id="intact-storage-id",
            content=CONFIG,
        )

        by_artifact = await test_client.get(f"/api/artifact/{artifact.id}", headers=admin_headers)
        by_storage_id = await test_client.get("/api/storage/object/intact-storage-id", headers=admin_headers)

        assert by_artifact.status_code == 200
        assert by_artifact.content == CONFIG
        assert by_storage_id.status_code == 200
        assert by_storage_id.content == CONFIG
        assert self.regeneration_requests(workflow_recorder=workflow_recorder) == []

    async def test_modified_artifact_is_refused_and_regenerated_once(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        test_client: InfrahubTestClient,
        admin_headers: dict[str, str],
        dummy_storage: DummyObjectStorage,
        artifact_definition: Node,
        car_person_data_generic: dict[str, Node],
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        workflow_recorder.reset()
        artifact = await self.create_artifact(
            db=db,
            dummy_storage=dummy_storage,
            definition=artifact_definition,
            target=car_person_data_generic["c1"],
            storage_id="modified-storage-id",
            content=CONFIG,
        )
        dummy_storage.store(identifier="modified-storage-id", content=io.BytesIO(TAMPERED_CONFIG))

        responses = [
            await test_client.get(f"/api/artifact/{artifact.id}", headers=admin_headers),
            await test_client.get("/api/storage/object/modified-storage-id", headers=admin_headers),
            await test_client.get("/api/storage/object/modified-storage-id", headers=admin_headers),
        ]

        for response in responses:
            assert response.status_code == 409
            assert response.json()["errors"][0]["message"] == refused_message(storage_id="modified-storage-id")
        assert self.regeneration_requests(workflow_recorder=workflow_recorder) == [
            RequestArtifactDefinitionGenerate(
                artifact_definition_id=artifact_definition.id,
                artifact_definition_name="startup_config",
                branch=default_branch.name,
                limit=[artifact.id],
            )
        ]

    async def test_missing_artifact_is_refused_and_regenerated_once(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        test_client: InfrahubTestClient,
        admin_headers: dict[str, str],
        dummy_storage: DummyObjectStorage,
        artifact_definition: Node,
        car_person_data_generic: dict[str, Node],
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        workflow_recorder.reset()
        artifact = await self.create_artifact(
            db=db,
            dummy_storage=dummy_storage,
            definition=artifact_definition,
            target=car_person_data_generic["c1"],
            storage_id="missing-storage-id",
            content=CONFIG,
        )
        dummy_storage.delete(identifier="missing-storage-id")

        responses = [
            await test_client.get(f"/api/artifact/{artifact.id}", headers=admin_headers),
            await test_client.get("/api/storage/object/missing-storage-id", headers=admin_headers),
        ]

        assert [response.status_code for response in responses] == [404, 404]
        assert self.regeneration_requests(workflow_recorder=workflow_recorder) == [
            RequestArtifactDefinitionGenerate(
                artifact_definition_id=artifact_definition.id,
                artifact_definition_name="startup_config",
                branch=default_branch.name,
                limit=[artifact.id],
            )
        ]

    async def test_unreferenced_object_is_served_unverified(
        self,
        test_client: InfrahubTestClient,
        admin_headers: dict[str, str],
        dummy_storage: DummyObjectStorage,
    ) -> None:
        dummy_storage.store(identifier="unreferenced-storage-id", content=io.BytesIO(TAMPERED_CONFIG))

        response = await test_client.get("/api/storage/object/unreferenced-storage-id", headers=admin_headers)

        assert response.status_code == 200
        assert response.content == TAMPERED_CONFIG

    async def test_branch_artifact_is_verified_without_branch_context(
        self,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        admin_headers: dict[str, str],
        dummy_storage: DummyObjectStorage,
        artifact_definition: Node,
        car_person_data_generic: dict[str, Node],
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        workflow_recorder.reset()
        branch = await create_branch(branch_name="rotate-secret", db=db)
        artifact = await self.create_artifact(
            db=db,
            dummy_storage=dummy_storage,
            definition=artifact_definition,
            target=car_person_data_generic["c2"],
            storage_id="branch-storage-id",
            content=CONFIG,
            branch=branch,
        )
        intact = await test_client.get("/api/storage/object/branch-storage-id", headers=admin_headers)
        dummy_storage.store(identifier="branch-storage-id", content=io.BytesIO(TAMPERED_CONFIG))

        refused = await test_client.get("/api/storage/object/branch-storage-id", headers=admin_headers)

        assert intact.status_code == 200
        assert refused.status_code == 409
        assert refused.json()["errors"][0]["message"] == refused_message(storage_id="branch-storage-id")
        assert [(request.branch, request.limit) for request in self.regeneration_requests(workflow_recorder)] == [
            ("rotate-secret", [artifact.id])
        ]

    async def test_previous_version_is_verified_against_its_own_checksum(
        self,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        admin_headers: dict[str, str],
        dummy_storage: DummyObjectStorage,
        artifact_definition: Node,
        car_person_data_generic: dict[str, Node],
    ) -> None:
        new_config = b"hostname leaf01\nenable secret rotated\n"
        artifact = await self.create_artifact(
            db=db,
            dummy_storage=dummy_storage,
            definition=artifact_definition,
            target=car_person_data_generic["c1"],
            storage_id="version-1-storage-id",
            content=CONFIG,
        )
        artifact.storage_id.value = "version-2-storage-id"
        artifact.checksum.value = md5(new_config)
        await artifact.save(db=db)
        dummy_storage.store(identifier="version-2-storage-id", content=io.BytesIO(new_config))

        previous = await test_client.get("/api/storage/object/version-1-storage-id", headers=admin_headers)
        current = await test_client.get("/api/storage/object/version-2-storage-id", headers=admin_headers)
        # The current content copied over the previous object must not pass for the previous version.
        dummy_storage.store(identifier="version-1-storage-id", content=io.BytesIO(new_config))
        swapped = await test_client.get("/api/storage/object/version-1-storage-id", headers=admin_headers)

        assert (previous.status_code, previous.content) == (200, CONFIG)
        assert (current.status_code, current.content) == (200, new_config)
        assert swapped.status_code == 409
        assert swapped.json()["errors"][0]["message"] == refused_message(storage_id="version-1-storage-id")

    async def test_artifact_without_recorded_checksum_is_refused(
        self,
        db: InfrahubDatabase,
        test_client: InfrahubTestClient,
        admin_headers: dict[str, str],
        dummy_storage: DummyObjectStorage,
        artifact_definition: Node,
        car_person_data_generic: dict[str, Node],
    ) -> None:
        artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
        await artifact.new(
            db=db,
            name="startup-config",
            definition=artifact_definition,
            status="Ready",
            object=car_person_data_generic["c2"],
            storage_id="no-checksum-storage-id",
            content_type="text/plain",
        )
        await artifact.save(db=db)
        dummy_storage.store(identifier="no-checksum-storage-id", content=io.BytesIO(CONFIG))

        by_artifact = await test_client.get(f"/api/artifact/{artifact.id}", headers=admin_headers)
        by_storage_id = await test_client.get("/api/storage/object/no-checksum-storage-id", headers=admin_headers)

        assert by_artifact.status_code == 409
        assert by_storage_id.status_code == 409
        assert by_artifact.json()["errors"][0]["message"] == missing_checksum_message(
            storage_id="no-checksum-storage-id"
        )
        assert by_storage_id.json()["errors"][0]["message"] == missing_checksum_message(
            storage_id="no-checksum-storage-id"
        )
