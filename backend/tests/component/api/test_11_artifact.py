import io
from unittest.mock import call, patch

import pytest
from fastapi.testclient import TestClient

from infrahub import config
from infrahub.auth import AccountSession, AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE
from tests.helpers.test_app import TestInfrahubApp
from tests.helpers.test_client import InfrahubTestClient


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
            storage_id="95008984-16ca-4e58-8323-0899bb60035f",
            checksum="60d39063c26263353de24e1b913e1e1c",
            content_type="application/json",
        )
        await artifact.save(db=db)

        registry.storage.store(identifier="95008984-16ca-4e58-8323-0899bb60035f", content=io.BytesIO(b'{"test": true}'))

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
        response = await test_client.get("/api/artifact/95008984-16ca-4e58-8323-0899bb60035f", headers=admin_headers)
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
