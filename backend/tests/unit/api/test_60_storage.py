import hashlib
import os
from pathlib import Path

from fastapi.testclient import TestClient

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase


async def test_file_upload(
    db: InfrahubDatabase, helper, local_storage_dir: str, admin_headers, default_branch: Branch, authentication_base
):
    from infrahub.server import app

    client = TestClient(app)

    fixture_dir = helper.get_fixtures_dir()

    fixture_dir = helper.get_fixtures_dir()
    files_dir = os.path.join(fixture_dir, "schemas")
    filenames = [item.name for item in os.scandir(files_dir) if item.is_file()]

    file_content = Path(os.path.join(files_dir, filenames[0])).read_bytes()
    file_checksum = hashlib.md5(file_content).hexdigest()

    file = {"file": open(os.path.join(files_dir, filenames[0]), "rb")}

    with client:
        resp = client.post(url="/api/storage/upload/file", files=file, headers=admin_headers)
        data = resp.json()
        assert data["checksum"] == file_checksum
        assert data["identifier"]

        file_in_storage = Path(os.path.join(local_storage_dir, data["identifier"]))

        assert file_in_storage.exists()
        assert file_in_storage.read_bytes() == file_content


async def test_content_upload(
    db: InfrahubDatabase, helper, local_storage_dir: str, admin_headers, default_branch: Branch, authentication_base
):
    from infrahub.server import app

    client = TestClient(app)

    fixture_dir = helper.get_fixtures_dir()

    fixture_dir = helper.get_fixtures_dir()
    files_dir = os.path.join(fixture_dir, "schemas")
    filenames = [item.name for item in os.scandir(files_dir) if item.is_file()]

    file_content = Path(os.path.join(files_dir, filenames[0])).read_bytes()
    file_checksum = hashlib.md5(file_content).hexdigest()

    with client:
        resp = client.post(
            url="/api/storage/upload/content", json={"content": file_content.decode("utf-8")}, headers=admin_headers
        )
        data = resp.json()
        assert data["checksum"] == file_checksum
        assert data["identifier"]

        file_in_storage = Path(os.path.join(local_storage_dir, data["identifier"]))

        assert file_in_storage.exists()
        assert file_in_storage.read_bytes() == file_content
