from fastapi.testclient import TestClient

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.message_bus.messages.transform_jinja_template import TransformJinjaTemplateResponse
from infrahub.message_bus.messages.transform_python_data import TransformPythonDataResponse


async def test_transform_endpoint(
    db: InfrahubDatabase, client_headers, default_branch, rpc_bus, register_core_models_schema, car_person_data
):
    from infrahub.server import app

    client = TestClient(app)

    repositories = await NodeManager.query(db=db, schema=InfrahubKind.REPOSITORY)
    queries = await NodeManager.query(db=db, schema=InfrahubKind.GRAPHQLQUERY)

    t1 = await Node.init(db=db, schema="CoreTransformPython")
    await t1.new(
        db=db,
        name="transform01",
        query=str(queries[0].id),
        repository=str(repositories[0].id),
        file_path="transform01.py",
        class_name="Transform01",
    )
    await t1.save(db=db)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        mock_response = TransformPythonDataResponse(
            data={"transformed_data": {"KEY1": "value1", "KEY2": "value2"}},
        )
        rpc_bus.add_mock_reply(response=mock_response)

        response = client.get(
            "/api/transform/python/transform01",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None
    result = response.json()

    assert result == {"KEY1": "value1", "KEY2": "value2"}


async def test_rfile_endpoint(
    db: InfrahubDatabase, client_headers, default_branch, rpc_bus, register_core_models_schema, car_person_data
):
    from infrahub.server import app

    client = TestClient(app)

    repositories = await NodeManager.query(db=db, schema=InfrahubKind.REPOSITORY)
    queries = await NodeManager.query(db=db, schema=InfrahubKind.GRAPHQLQUERY)

    t1 = await Node.init(db=db, schema=InfrahubKind.TRANSFORMJINJA2)
    await t1.new(
        db=db,
        name="test-rfile",
        query=str(queries[0].id),
        repository=str(repositories[0].id),
        template_path="templates/device_startup_config.tpl.j2",
    )
    await t1.save(db=db)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        mock_response = TransformJinjaTemplateResponse(
            data={"rendered_template": "Rendered by a mocked agent"},
        )
        rpc_bus.add_mock_reply(response=mock_response)

        response = client.get(
            "/api/transform/jinja2/test-rfile",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.text == "Rendered by a mocked agent"
