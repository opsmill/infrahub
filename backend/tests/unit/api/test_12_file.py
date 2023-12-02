from fastapi.testclient import TestClient

from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.message_bus import InfrahubResponse


async def test_get_file(
    db: InfrahubDatabase,
    client_headers,
    default_branch,
    rpc_bus,
    register_core_models_schema,
):
    from infrahub.server import app

    client = TestClient(app)

    r1 = await Node.init(db=db, schema="CoreRepository")
    await r1.new(db=db, name="repo01", location="git@github.com:user/repo01.git")
    await r1.save(db=db)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        mock_response = InfrahubResponse(
            response_class="content_response",
            response_data={"content": "file content"},
        )
        # No commit yet
        response = client.get(
            f"/api/file/{r1.id}/myfile.text",
            headers=client_headers,
        )
        assert response.status_code == 400

        # With Manual Commit
        rpc_bus.add_mock_reply(response=mock_response)

        response = client.get(
            f"/api/file/{r1.id}/myfile.text?commit=12345678iuytrewqwertyu",
            headers=client_headers,
        )

        assert response.status_code == 200
        assert response.text == "file content"

        # With Commit associated with Repository Object
        r1.commit.value = "1345754212345678iuytrewqwertyu"
        await r1.save(db=db)

        rpc_bus.add_mock_reply(response=mock_response)

        response = client.get(
            f"/api/file/{r1.id}/myfile.text",
            headers=client_headers,
        )

        assert response.status_code == 200
        assert response.text == "file content"

        # Access Repo by name
        rpc_bus.add_mock_reply(response=mock_response)

        response = client.get(
            "/api/file/repo01/myfile.text",
            headers=client_headers,
        )

        assert response.status_code == 200
        assert response.text == "file content"
