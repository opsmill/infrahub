import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from infrahub.core.branch import Branch
from infrahub.message_bus.rpc import InfrahubRpcClientTesting


@pytest.fixture
def patch_rpc_client():
    import infrahub.message_bus.rpc

    infrahub.message_bus.rpc.InfrahubRpcClient = InfrahubRpcClientTesting


async def test_file_upload(
    session, helper, local_storage_dir: str, admin_headers, default_branch: Branch, authentication_base
):
    from infrahub.api.main import app

    client = TestClient(app)

    fixture_dir = helper.get_fixtures_dir()

    fixture_dir = helper.get_fixtures_dir()
    files_dir = os.path.join(fixture_dir, "schemas")
    filenames = [item.name for item in os.scandir(files_dir) if item.is_file()]

    file_content = Path(os.path.join(files_dir, filenames[0])).read_bytes()
    file_checksum = hashlib.md5(file_content).hexdigest()

    file = {"file": open(os.path.join(files_dir, filenames[0]), "rb")}

    with client:
        resp = client.post(url="/storage/upload", files=file, headers=admin_headers)
        data = resp.json()
        assert data["checksum"] == file_checksum
        assert data["identifier"]

        file_in_storage = Path(os.path.join(local_storage_dir, data["identifier"]))

        assert file_in_storage.exists()
        assert file_in_storage.read_bytes() == file_content


#     repositories = await NodeManager.query(session=session, schema="CoreRepository")
#     queries = await NodeManager.query(session=session, schema="CoreGraphQLQuery")

#     t1 = await Node.init(session=session, schema="CoreTransformPython")
#     await t1.new(
#         session=session,
#         name="transform01",
#         query=str(queries[0].id),
#         url="mytransform",
#         repository=str(repositories[0].id),
#         file_path="transform01.py",
#         class_name="Transform01",
#         rebase=False,
#     )
#     await t1.save(session=session)

#     # Must execute in a with block to execute the startup/shutdown events
#     with client:
#         mock_response = InfrahubRPCResponse(
#             status=RPCStatusCode.OK, response={"transformed_data": {"KEY1": "value1", "KEY2": "value2"}}
#         )
#         await client.app.state.rpc_client.add_response(
#             response=mock_response, message_type=MessageType.TRANSFORMATION, action=TransformMessageAction.PYTHON
#         )

#         response = client.get(
#             "/transform/mytransform",
#             headers=client_headers,
#         )

#     assert response.status_code == 200
#     assert response.json() is not None
#     result = response.json()

#     assert result == {"KEY1": "value1", "KEY2": "value2"}


# async def test_transform_endpoint_path(session, client_headers, patch_rpc_client, default_branch, car_person_data):
#     from infrahub.api.main import app

#     client = TestClient(app)

#     repositories = await NodeManager.query(session=session, schema="CoreRepository")
#     queries = await NodeManager.query(session=session, schema="CoreGraphQLQuery")

#     t1 = await Node.init(session=session, schema="CoreTransformPython")
#     await t1.new(
#         session=session,
#         name="transform01",
#         query=str(queries[0].id),
#         url="my/transform/function",
#         repository=str(repositories[0].id),
#         file_path="transform01.py",
#         class_name="Transform01",
#         rebase=False,
#     )
#     await t1.save(session=session)

#     # Must execute in a with block to execute the startup/shutdown events
#     with client:
#         mock_response = InfrahubRPCResponse(
#             status=RPCStatusCode.OK, response={"transformed_data": {"KEY1": "value1", "KEY2": "value2"}}
#         )
#         await client.app.state.rpc_client.add_response(
#             response=mock_response, message_type=MessageType.TRANSFORMATION, action=TransformMessageAction.PYTHON
#         )

#         response = client.get(
#             "/transform/my/transform/function",
#             headers=client_headers,
#         )

#     assert response.status_code == 200
#     assert response.json() is not None
#     result = response.json()

#     assert result == {"KEY1": "value1", "KEY2": "value2"}
