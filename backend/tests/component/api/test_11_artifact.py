import hashlib
import io
from unittest.mock import call, patch

import pytest
from fastapi.testclient import TestClient

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.protocols import CoreArtifact
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE
from tests.helpers.test_app import TestInfrahubApp
from tests.helpers.test_client import InfrahubTestClient

STORAGE_ID = "95008984-16ca-4e58-8323-0899bb60035f"
CONTENT = b'{"test": true}'


def md5(content: bytes) -> str:
    return hashlib.md5(content, usedforsecurity=False).hexdigest()


class TestArtifact11(TestInfrahubApp):
    async def setup_artifact_definition(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
    ) -> tuple[Node, Node, Node]:
        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="group1", members=[car_person_data_generic["c1"], car_person_data_generic["c2"]])
        await group.save(db=db)

        transform = await Node.init(db=db, schema="CoreTransformPython")
        await transform.new(
            db=db,
            name="transform01",
            query=str(car_person_data_generic["q1"].id),
            repository=str(car_person_data_generic["r1"].id),
            file_path="transform01.py",
            class_name="Transform01",
        )
        await transform.save(db=db)

        definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await definition.new(
            db=db,
            name="artifactdef01",
            targets=group,
            transformation=transform,
            content_type="application/json",
            artifact_name="myartifact",
            parameters={"value": {"name": "name__value"}},
        )
        await definition.save(db=db)

        return group, transform, definition

    async def setup_artifact(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
    ) -> Node:
        _, _, definition = await self.setup_artifact_definition(
            db=db,
            register_core_models_schema=register_core_models_schema,
            register_builtin_models_schema=register_builtin_models_schema,
            car_person_data_generic=car_person_data_generic,
        )

        artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
        await artifact.new(
            db=db,
            name="myyartifact",
            definition=definition,
            status="Ready",
            object=car_person_data_generic["c1"],
            storage_id=STORAGE_ID,
            checksum=md5(CONTENT),
            content_type="application/json",
        )
        await artifact.save(db=db)

        registry.storage.store(identifier=STORAGE_ID, content=io.BytesIO(CONTENT))

        return artifact

    async def test_artifact_definition_endpoint(
        self,
        db: InfrahubDatabase,
        admin_headers: dict[str, str],
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
        authentication_base: Node,
        client: TestClient,
        test_client: InfrahubTestClient,
    ) -> None:
        _, _, definition = await self.setup_artifact_definition(
            db=db,
            register_core_models_schema=register_core_models_schema,
            register_builtin_models_schema=register_builtin_models_schema,
            car_person_data_generic=car_person_data_generic,
        )

        # Must execute in a with block to execute the startup/shutdown events
        with (
            patch(
                "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.submit_workflow"
            ) as mock_submit_workflow,
        ):
            response = await test_client.post(
                f"/api/artifact/generate/{definition.id}",
                headers=admin_headers,
            )

            assert response.status_code == 200

            context = InfrahubContext(
                branch=BranchContext(name=default_branch.name, id=str(default_branch.get_uuid())),
                account=AccountSession(
                    authenticated=True, account_id=authentication_base.id, session_id=None, auth_type=AuthType.API
                ),
            )

            expected_calls = [
                call(
                    workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
                    parameters={
                        "model": RequestArtifactDefinitionGenerate(
                            artifact_definition_id=definition.id,
                            artifact_definition_name=definition.name.value,
                            branch="main",
                            limit=[],
                        )
                    },
                    context=context,
                ),
            ]
            mock_submit_workflow.assert_has_calls(expected_calls)

    async def test_artifact_endpoint(
        self,
        db: InfrahubDatabase,
        admin_headers: dict[str, str],
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
        authentication_base: Node,
        test_client: InfrahubTestClient,
    ) -> None:
        response = await test_client.get(f"/api/artifact/{STORAGE_ID}", headers=admin_headers)
        assert response.status_code == 404

        artifact = await self.setup_artifact(
            db=db,
            register_core_models_schema=register_core_models_schema,
            register_builtin_models_schema=register_builtin_models_schema,
            car_person_data_generic=car_person_data_generic,
        )

        response = await test_client.get(f"/api/artifact/{artifact.id}", headers=admin_headers)

        assert response.status_code == 200
        assert response.json() == {"test": True}

    @pytest.mark.parametrize("by_storage_id", [False, True], ids=["artifact-endpoint", "storage-endpoint"])
    @pytest.mark.parametrize(
        ("stored", "expected_status"),
        [(CONTENT, 200), (b'{"test": false}', 409), (None, 404)],
        ids=["unchanged", "modified", "missing"],
    )
    async def test_artifact_file_is_served_only_when_it_matches_its_checksum(
        self,
        db: InfrahubDatabase,
        admin_headers: dict[str, str],
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
        authentication_base: Node,
        test_client: InfrahubTestClient,
        by_storage_id: bool,
        stored: bytes | None,
        expected_status: int,
    ) -> None:
        artifact = await self.setup_artifact(
            db=db,
            register_core_models_schema=register_core_models_schema,
            register_builtin_models_schema=register_builtin_models_schema,
            car_person_data_generic=car_person_data_generic,
        )
        if stored is None:
            registry.storage.delete(identifier=STORAGE_ID)
        else:
            registry.storage.store(identifier=STORAGE_ID, content=io.BytesIO(stored))

        url = f"/api/storage/object/{STORAGE_ID}" if by_storage_id else f"/api/artifact/{artifact.id}"
        response = await test_client.get(url, headers=admin_headers)

        assert response.status_code == expected_status
        if expected_status == 200:
            assert response.content == CONTENT
        if expected_status == 409:
            assert response.json()["errors"][0]["message"] == (
                f"The stored file of this artifact ({STORAGE_ID}) does not match its checksum, so it was not served. "
                "It may have been modified outside of Infrahub. Regenerate the artifact to restore it."
            )

    async def test_artifact_file_is_served_unchecked_when_verification_is_off(
        self,
        db: InfrahubDatabase,
        admin_headers: dict[str, str],
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
        authentication_base: Node,
        test_client: InfrahubTestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        artifact = await self.setup_artifact(
            db=db,
            register_core_models_schema=register_core_models_schema,
            register_builtin_models_schema=register_builtin_models_schema,
            car_person_data_generic=car_person_data_generic,
        )
        registry.storage.store(identifier=STORAGE_ID, content=io.BytesIO(b'{"test": false}'))
        monkeypatch.setattr(config.SETTINGS.storage, "verify_artifact_checksum", False)

        for url in (f"/api/artifact/{artifact.id}", f"/api/storage/object/{STORAGE_ID}"):
            response = await test_client.get(url, headers=admin_headers)
            assert response.status_code == 200
            assert response.content == b'{"test": false}'

    async def test_storage_endpoint_serves_content_no_artifact_references(
        self,
        db: InfrahubDatabase,
        admin_headers: dict[str, str],
        default_branch: Branch,
        authentication_base: Node,
        test_client: InfrahubTestClient,
    ) -> None:
        registry.storage.store(identifier="unreferenced", content=io.BytesIO(b"anything"))

        response = await test_client.get("/api/storage/object/unreferenced", headers=admin_headers)

        assert response.status_code == 200
        assert response.content == b"anything"

    async def test_storage_endpoint_checks_each_version_against_its_own_checksum(
        self,
        db: InfrahubDatabase,
        admin_headers: dict[str, str],
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
        authentication_base: Node,
        test_client: InfrahubTestClient,
    ) -> None:
        artifact = await self.setup_artifact(
            db=db,
            register_core_models_schema=register_core_models_schema,
            register_builtin_models_schema=register_builtin_models_schema,
            car_person_data_generic=car_person_data_generic,
        )
        branch = await create_branch(branch_name="branch1", db=db)
        versions = [
            (branch, "branch-version", b'{"test": "branch"}'),
            (registry.get_branch_from_registry(), "main-version", b'{"test": "main"}'),
        ]
        for version_branch, storage_id, content in versions:
            registry.storage.store(identifier=storage_id, content=io.BytesIO(content))
            version = await registry.manager.get_one(
                db=db, id=artifact.id, branch=version_branch, kind=CoreArtifact, raise_on_error=True
            )
            version.storage_id.value = storage_id
            version.checksum.value = md5(content)
            await version.save(db=db)

        # Every version is served as long as it matches the checksum recorded with it, including the previous one
        for _, storage_id, content in [(None, STORAGE_ID, CONTENT), *versions]:
            response = await test_client.get(f"/api/storage/object/{storage_id}", headers=admin_headers)
            assert response.status_code == 200
            assert response.content == content

        # The content of another version does not match
        registry.storage.store(identifier="branch-version", content=io.BytesIO(b'{"test": "main"}'))
        registry.storage.store(identifier=STORAGE_ID, content=io.BytesIO(b'{"test": "main"}'))
        for storage_id in ("branch-version", STORAGE_ID):
            response = await test_client.get(f"/api/storage/object/{storage_id}", headers=admin_headers)
            assert response.status_code == 409

    async def test_artifact_endpoint_refuses_an_artifact_without_checksum(
        self,
        db: InfrahubDatabase,
        admin_headers: dict[str, str],
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
        authentication_base: Node,
        test_client: InfrahubTestClient,
    ) -> None:
        artifact = await self.setup_artifact(
            db=db,
            register_core_models_schema=register_core_models_schema,
            register_builtin_models_schema=register_builtin_models_schema,
            car_person_data_generic=car_person_data_generic,
        )
        artifact.checksum.value = None
        await artifact.save(db=db)

        response = await test_client.get(f"/api/artifact/{artifact.id}", headers=admin_headers)

        assert response.status_code == 409
        assert response.json()["errors"][0]["message"] == (
            f"This artifact has no recorded checksum to check its stored file ({STORAGE_ID}) against, "
            "so it was not served. Regenerate the artifact to restore it."
        )

    async def test_artifact_file_replaced_with_another_artifact_content_is_refused(
        self,
        db: InfrahubDatabase,
        admin_headers: dict[str, str],
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
        authentication_base: Node,
        test_client: InfrahubTestClient,
    ) -> None:
        artifact = await self.setup_artifact(
            db=db,
            register_core_models_schema=register_core_models_schema,
            register_builtin_models_schema=register_builtin_models_schema,
            car_person_data_generic=car_person_data_generic,
        )
        other_content = b'{"test": "other artifact"}'
        other = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
        await other.new(
            db=db,
            name="other",
            definition=await artifact.definition.get_peer(db=db),
            status="Ready",
            object=car_person_data_generic["c2"],
            storage_id="other-storage-id",
            checksum=md5(other_content),
            content_type="application/json",
        )
        await other.save(db=db)
        registry.storage.store(identifier=STORAGE_ID, content=io.BytesIO(other_content))

        for url in (f"/api/storage/object/{STORAGE_ID}", f"/api/artifact/{artifact.id}"):
            response = await test_client.get(url, headers=admin_headers)
            assert response.status_code == 409

    async def test_artifact_endpoint_checks_the_checksum_of_the_requested_branch(
        self,
        db: InfrahubDatabase,
        admin_headers: dict[str, str],
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
        authentication_base: Node,
        test_client: InfrahubTestClient,
    ) -> None:
        artifact = await self.setup_artifact(
            db=db,
            register_core_models_schema=register_core_models_schema,
            register_builtin_models_schema=register_builtin_models_schema,
            car_person_data_generic=car_person_data_generic,
        )
        # The file is stored again on the branch while the checksum stays the one recorded on main
        branch = await create_branch(branch_name="branch1", db=db)
        branch_artifact = await registry.manager.get_one(
            db=db, id=artifact.id, branch=branch, kind=CoreArtifact, raise_on_error=True
        )
        branch_artifact.storage_id.value = "branch-copy"
        await branch_artifact.save(db=db)
        registry.storage.store(identifier="branch-copy", content=io.BytesIO(b'{"test": false}'))

        response = await test_client.get(f"/api/artifact/{artifact.id}?branch={branch.name}", headers=admin_headers)

        assert response.status_code == 409

    @pytest.mark.parametrize("allow_anonymous_access", [False, True])
    async def test_artifact_endpoint_anonymous_account(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
        allow_anonymous_access: bool,
        test_client: InfrahubTestClient,
    ) -> None:
        artifact = await self.setup_artifact(
            db=db,
            register_core_models_schema=register_core_models_schema,
            register_builtin_models_schema=register_builtin_models_schema,
            car_person_data_generic=car_person_data_generic,
        )

        config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

        response = await test_client.get(f"/api/artifact/{artifact.id}")

        assert response.status_code == 200 if allow_anonymous_access else 401

    async def test_artifact_generate_blocked_on_merged_branch(
        self,
        db: InfrahubDatabase,
        admin_headers: dict[str, str],
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
        authentication_base: Node,
        test_client: InfrahubTestClient,
    ) -> None:
        """Test that artifact generation returns 422 on merged branches."""
        _, _, definition = await self.setup_artifact_definition(
            db=db,
            register_core_models_schema=register_core_models_schema,
            register_builtin_models_schema=register_builtin_models_schema,
            car_person_data_generic=car_person_data_generic,
        )

        branch = await create_branch(branch_name="merged-artifact-test", db=db)
        branch.status = BranchStatus.MERGED
        await branch.save(db=db)
        registry.branch[branch.name] = branch

        response = await test_client.post(
            f"/api/artifact/generate/{definition.id}?branch={branch.name}",
            headers=admin_headers,
        )

        assert response.status_code == 422
        assert "has been merged and is read-only" in response.json()["errors"][0]["message"]

    async def test_artifact_generate_blocked_on_need_rebase_branch(
        self,
        db: InfrahubDatabase,
        admin_headers: dict[str, str],
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
        authentication_base: Node,
        test_client: InfrahubTestClient,
    ) -> None:
        """Test that artifact generation returns 422 on branches needing rebase."""
        _, _, definition = await self.setup_artifact_definition(
            db=db,
            register_core_models_schema=register_core_models_schema,
            register_builtin_models_schema=register_builtin_models_schema,
            car_person_data_generic=car_person_data_generic,
        )

        branch = await create_branch(branch_name="rebase-artifact-test", db=db)
        branch.status = BranchStatus.NEED_REBASE
        await branch.save(db=db)
        registry.branch[branch.name] = branch

        response = await test_client.post(
            f"/api/artifact/generate/{definition.id}?branch={branch.name}",
            headers=admin_headers,
        )

        assert response.status_code == 422
        assert "must be rebased" in response.json()["errors"][0]["message"]
