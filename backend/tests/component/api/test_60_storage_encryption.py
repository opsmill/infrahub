from __future__ import annotations

import hashlib
import io
from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.exceptions import StorageEncryptionError
from infrahub.storage import InfrahubObjectStorage
from infrahub.storage_encryption.crypto import StorageKey
from tests.helpers.artifact import create_stored_artifact
from tests.helpers.schema.file_contract import FILE_CONTRACT

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

ARTIFACT_ID = "0b9f9a8c-0000-4000-8000-0000000000a1"
FILE_ID = "0b9f9a8c-0000-4000-8000-0000000000f1"
LOOSE_ID = "0b9f9a8c-0000-4000-8000-0000000000b1"
ARTIFACT = b'{"hostname": "leaf01"}'
FILE = b"%PDF-1.7 maintenance contract"


@pytest.fixture
def encryption_enabled(monkeypatch: pytest.MonkeyPatch) -> StorageKey:
    """Enable storage encryption for the application started by the test client."""
    monkeypatch.setattr(config.SETTINGS.storage, "encryption_enabled", True)
    return StorageKey.derive(config.SETTINGS.security.secret_key)


def refusal(identifier: str) -> dict:
    return {
        "data": None,
        "errors": [
            {
                "message": f"The stored content {identifier} failed its integrity check and was not served.",
                "extensions": {"code": 409},
            }
        ],
    }


async def test_uploaded_content_is_encrypted_at_rest_and_served_decrypted(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    encryption_enabled: StorageKey,
) -> None:
    with client:
        upload = client.post(
            url="/api/storage/upload/content", json={"content": ARTIFACT.decode()}, headers=admin_headers
        )
        identifier = upload.json()["identifier"]
        response = client.get(url=f"/api/storage/object/{identifier}", headers=admin_headers)

    stored = (local_storage_dir / identifier).read_bytes()
    assert stored[:13] == b"IHSE\x01" + bytes.fromhex(encryption_enabled.fingerprint)
    assert b"leaf01" not in stored
    assert (response.status_code, response.content) == (200, ARTIFACT)


async def test_artifact_is_served_only_while_it_is_unchanged(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    register_core_models_schema: SchemaBranch,
    register_builtin_models_schema: SchemaBranch,
    car_person_data_generic: dict[str, Node],
    encryption_enabled: StorageKey,
) -> None:
    artifact = await create_stored_artifact(
        db=db,
        car_person_data_generic=car_person_data_generic,
        storage_id=ARTIFACT_ID,
        checksum=hashlib.md5(ARTIFACT, usedforsecurity=False).hexdigest(),
    )
    urls = [f"/api/artifact/{artifact.id}", f"/api/storage/object/{ARTIFACT_ID}"]
    encrypted = InfrahubObjectStorage(settings=config.SETTINGS.storage, key=encryption_enabled)

    with client:
        (local_storage_dir / ARTIFACT_ID).write_bytes(ARTIFACT)
        stored_before_encryption = [client.get(url=url, headers=admin_headers) for url in urls]
        (local_storage_dir / ARTIFACT_ID).write_bytes(b'{"hostname": "leaf01", "backdoor": true}')
        modified_before_encryption = [client.get(url=url, headers=admin_headers) for url in urls]
        encrypted.store(identifier=ARTIFACT_ID, content=io.BytesIO(ARTIFACT))
        stored_encrypted = [client.get(url=url, headers=admin_headers) for url in urls]
        tampered = bytearray((local_storage_dir / ARTIFACT_ID).read_bytes())
        tampered[-1] ^= 0x01
        (local_storage_dir / ARTIFACT_ID).write_bytes(bytes(tampered))
        modified_encrypted = [client.get(url=url, headers=admin_headers) for url in urls]

    assert [(response.status_code, response.content) for response in stored_before_encryption + stored_encrypted] == [
        (200, ARTIFACT)
    ] * 4
    assert [
        (response.status_code, response.json()) for response in modified_before_encryption + modified_encrypted
    ] == [(409, refusal(ARTIFACT_ID))] * 4


async def test_file_object_stored_before_encryption_is_checked_against_its_checksum(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    encryption_enabled: StorageKey,
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(nodes=[FILE_CONTRACT]), branch=default_branch.name)
    contract = await Node.init(db=db, schema="TestingFileContract")
    await contract.new(
        db=db,
        file_name="contract.pdf",
        checksum=hashlib.sha1(FILE, usedforsecurity=False).hexdigest(),
        file_size=len(FILE),
        file_type="application/pdf",
        storage_id=FILE_ID,
    )
    await contract.save(db=db)
    (local_storage_dir / FILE_ID).write_bytes(FILE)

    with client:
        served = client.get(url=f"/api/storage/files/{contract.id}", headers=admin_headers)
        (local_storage_dir / FILE_ID).write_bytes(b"%PDF-1.7 replaced contract")
        refused = client.get(url=f"/api/storage/files/{contract.id}", headers=admin_headers)

    assert (served.status_code, served.content) == (200, FILE)
    assert (refused.status_code, refused.json()) == (409, refusal(FILE_ID))


async def test_object_nothing_records_a_checksum_for_is_served_as_it_is(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    encryption_enabled: StorageKey,
) -> None:
    (local_storage_dir / LOOSE_ID).write_bytes(b"content nobody references")

    with client:
        response = client.get(url=f"/api/storage/object/{LOOSE_ID}", headers=admin_headers)

    assert (response.status_code, response.content) == (200, b"content nobody references")


async def test_server_does_not_start_with_the_published_secret(
    db: InfrahubDatabase,
    client: TestClient,
    default_branch: Branch,
    authentication_base: Node,
    encryption_enabled: StorageKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.SETTINGS.security, "secret_key", "327f747f-efac-42be-9e73-999f08f86b92")

    with (
        pytest.raises(
            StorageEncryptionError,
            match=(
                r"^INFRAHUB_SECURITY_SECRET_KEY still has the value published in Infrahub's example deployment "
                r"files; set a unique random secret before using storage encryption$"
            ),
        ),
        client,
    ):
        pass
