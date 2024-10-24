from unittest.mock import call, patch

from starlette.testclient import TestClient

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.server import app
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE
from tests.helpers.test_app import TestInfrahubApp


class TestArtifact11(TestInfrahubApp):
    async def test_artifact_definition_endpoint(
        self,
        db: InfrahubDatabase,
        admin_headers,
        default_branch,
        register_core_models_schema,
        register_builtin_models_schema,
        car_person_data_generic,
        authentication_base,
        client,
    ):
        g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await g1.new(db=db, name="group1", members=[car_person_data_generic["c1"], car_person_data_generic["c2"]])
        await g1.save(db=db)

        t1 = await Node.init(db=db, schema="CoreTransformPython")
        await t1.new(
            db=db,
            name="transform01",
            query=str(car_person_data_generic["q1"].id),
            repository=str(car_person_data_generic["r1"].id),
            file_path="transform01.py",
            class_name="Transform01",
        )
        await t1.save(db=db)

        ad1 = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await ad1.new(
            db=db,
            name="artifactdef01",
            targets=g1,
            transformation=t1,
            content_type="application/json",
            artifact_name="myartifact",
            parameters={"value": {"name": "name__value"}},
        )
        await ad1.save(db=db)

        app_client = TestClient(app)

        # Must execute in a with block to execute the startup/shutdown events
        with (
            app_client,
            patch(
                "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.submit_workflow"
            ) as mock_submit_workflow,
        ):
            response = app_client.post(
                f"/api/artifact/generate/{ad1.id}",
                headers=admin_headers,
            )

            assert response.status_code == 200
            expected_calls = [
                call(
                    workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
                    parameters={
                        "model": RequestArtifactDefinitionGenerate(artifact_definition=ad1.id, branch="main", limit=[])
                    },
                ),
            ]
            mock_submit_workflow.assert_has_calls(expected_calls)

    async def test_artifact_endpoint(
        self,
        db: InfrahubDatabase,
        admin_headers,
        register_core_models_schema,
        register_builtin_models_schema,
        car_person_data_generic,
        authentication_base,
    ):
        app_client = TestClient(app)

        with app_client:
            response = app_client.get("/api/artifact/95008984-16ca-4e58-8323-0899bb60035f", headers=admin_headers)
        assert response.status_code == 404

        g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await g1.new(db=db, name="group1", members=[car_person_data_generic["c1"], car_person_data_generic["c2"]])
        await g1.save(db=db)

        t1 = await Node.init(db=db, schema="CoreTransformPython")
        await t1.new(
            db=db,
            name="transform01",
            query=str(car_person_data_generic["q1"].id),
            repository=str(car_person_data_generic["r1"].id),
            file_path="transform01.py",
            class_name="Transform01",
        )
        await t1.save(db=db)

        ad1 = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await ad1.new(
            db=db,
            name="artifactdef01",
            targets=g1,
            transformation=t1,
            content_type="application/json",
            artifact_name="myartifact",
            parameters={"value": {"name": "name__value"}},
        )
        await ad1.save(db=db)

        art1 = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
        await art1.new(
            db=db,
            name="myyartifact",
            definition=ad1,
            status="Ready",
            object=car_person_data_generic["c1"],
            storage_id="95008984-16ca-4e58-8323-0899bb60035f",
            checksum="60d39063c26263353de24e1b913e1e1c",
            content_type="application/json",
        )
        await art1.save(db=db)

        registry.storage.store(identifier="95008984-16ca-4e58-8323-0899bb60035f", content='{"test": true}'.encode())

        with app_client:
            response = app_client.get(f"/api/artifact/{art1.id}", headers=admin_headers)

        assert response.status_code == 200
        assert response.json() == {"test": True}
