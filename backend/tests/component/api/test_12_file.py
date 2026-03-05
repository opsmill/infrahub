from typing import Any

import pytest
from fastapi.testclient import TestClient

from infrahub import config
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.message_bus import messages


async def test_get_file(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers: dict[str, str],
    default_branch: Branch,
    rpc_bus: Any,
    register_core_models_schema: SchemaBranch,
) -> None:
    r1 = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await r1.new(db=db, name="repo01", location="git@github.com:user/repo01.git")
    await r1.save(db=db)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        mock_response = messages.GitFileGetResponse(
            data={"content": "file content"},
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


@pytest.mark.parametrize("allow_anonymous_access", [False, True])
async def test_get_file_anonymous_account(
    db: InfrahubDatabase,
    client: TestClient,
    default_branch: Branch,
    rpc_bus: Any,
    register_core_models_schema: SchemaBranch,
    allow_anonymous_access: bool,
) -> None:
    r1 = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await r1.new(
        db=db, name="repo01", location="git@github.com:user/repo01.git", commit="1345754212345678iuytrewqwertyu"
    )
    await r1.save(db=db)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        mock_response = messages.GitFileGetResponse(
            data={"content": "file content"},
        )
        rpc_bus.add_mock_reply(response=mock_response)

        config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

        response = client.get(f"/api/file/{r1.id}/myfile.text?commit=12345678iuytrewqwertyu")

        assert response.status_code == 200 if allow_anonymous_access else 401
