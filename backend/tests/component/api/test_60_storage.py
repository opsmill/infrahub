import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from tests.conftest import TestHelper


async def test_file_upload(
    db: InfrahubDatabase,
    client: TestClient,
    helper: TestHelper,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
) -> None:
    files_dir = helper.get_fixtures_dir() / "schemas"
    filenames = [item.name for item in files_dir.iterdir() if item.is_file()]
    file_path = files_dir / filenames[0]

    file_content = file_path.read_bytes()
    file_checksum = hashlib.md5(file_content, usedforsecurity=False).hexdigest()

    file = {"file": file_path.open(mode="rb")}

    with client:
        resp = client.post(url="/api/storage/upload/file", files=file, headers=admin_headers)
        data = resp.json()
        assert data["checksum"] == file_checksum
        assert data["identifier"]

        file_in_storage: Path = local_storage_dir / data["identifier"]
        assert file_in_storage.exists()
        assert file_in_storage.read_bytes() == file_content


async def test_content_upload(
    db: InfrahubDatabase,
    client: TestClient,
    helper: TestHelper,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
) -> None:
    files_dir = helper.get_fixtures_dir() / "schemas"
    filenames = [item.name for item in files_dir.iterdir() if item.is_file()]

    file_content = (files_dir / filenames[0]).read_bytes()
    file_checksum = hashlib.md5(file_content, usedforsecurity=False).hexdigest()

    with client:
        resp = client.post(
            url="/api/storage/upload/content", json={"content": file_content.decode("utf-8")}, headers=admin_headers
        )
        data = resp.json()
        assert data["checksum"] == file_checksum
        assert data["identifier"]

        file_in_storage: Path = local_storage_dir / data["identifier"]
        assert file_in_storage.exists()
        assert file_in_storage.read_bytes() == file_content
