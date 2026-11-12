from __future__ import annotations

import hashlib
import io
from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.storage import InfrahubObjectStorage
from infrahub.storage_encryption.crypto import StorageKey, seal
from tests.helpers.artifact import create_stored_artifact, stored_artifact_encryption

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

ARTIFACT_ID = "0b9f9a8c-0000-4000-8000-0000000000a1"
ARTIFACT = b'{"hostname": "leaf01"}'
OTHER_KEY = StorageKey.derive("another-key-for-artifact-tests-0123456789")


@pytest.fixture
def encryption_enabled(monkeypatch: pytest.MonkeyPatch) -> StorageKey:
    monkeypatch.setattr(config.SETTINGS.storage, "encryption_enabled", True)
    return StorageKey.derive(config.SETTINGS.security.secret_key)


async def create_artifact(db: InfrahubDatabase, car_person_data_generic: dict[str, Node]) -> Node:
    return await create_stored_artifact(
        db=db,
        car_person_data_generic=car_person_data_generic,
        storage_id=ARTIFACT_ID,
        checksum=hashlib.md5(ARTIFACT, usedforsecurity=False).hexdigest(),
    )


async def test_new_artifact_is_stored_as_plaintext(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_builtin_models_schema: SchemaBranch,
    car_person_data_generic: dict[str, Node],
) -> None:
    artifact = await create_artifact(db=db, car_person_data_generic=car_person_data_generic)

    assert await stored_artifact_encryption(db=db, artifact_id=artifact.id) == "plaintext"


async def test_check_follows_the_key_and_stores_what_it_finds(
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
    artifact = await create_artifact(db=db, car_person_data_generic=car_person_data_generic)
    url = f"/api/artifact/{artifact.id}/encryption"
    InfrahubObjectStorage(settings=config.SETTINGS.storage, key=encryption_enabled).store(
        identifier=ARTIFACT_ID, content=io.BytesIO(ARTIFACT)
    )

    with client:
        found = client.post(url=url, headers=admin_headers)
        again = client.post(url=url, headers=admin_headers)
        stored_after_found = await stored_artifact_encryption(db=db, artifact_id=artifact.id)
        (local_storage_dir / ARTIFACT_ID).write_bytes(seal(identifier=ARTIFACT_ID, content=ARTIFACT, key=OTHER_KEY))
        other_key = client.post(url=url, headers=admin_headers)
        stored_after_other_key = await stored_artifact_encryption(db=db, artifact_id=artifact.id)
        (local_storage_dir / ARTIFACT_ID).write_bytes(
            seal(identifier=ARTIFACT_ID, content=ARTIFACT, key=encryption_enabled)
        )
        restored = client.post(url=url, headers=admin_headers)

    assert [(response.status_code, response.json()) for response in (found, again, other_key, restored)] == [
        (200, {"encryption": "encrypted", "reason": None, "updated": True}),
        (200, {"encryption": "encrypted", "reason": None, "updated": False}),
        (200, {"encryption": "unreadable", "reason": "unknown_key", "updated": True}),
        (200, {"encryption": "encrypted", "reason": None, "updated": True}),
    ]
    assert (stored_after_found, stored_after_other_key) == ("encrypted", "unreadable")
    assert await stored_artifact_encryption(db=db, artifact_id=artifact.id) == "encrypted"


async def test_check_reports_a_plain_file_as_plaintext(
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
    artifact = await create_artifact(db=db, car_person_data_generic=car_person_data_generic)
    (local_storage_dir / ARTIFACT_ID).write_bytes(ARTIFACT)

    with client:
        response = client.post(url=f"/api/artifact/{artifact.id}/encryption", headers=admin_headers)

    assert (response.status_code, response.json()) == (
        200,
        {"encryption": "plaintext", "reason": None, "updated": False},
    )
    assert await stored_artifact_encryption(db=db, artifact_id=artifact.id) == "plaintext"


async def test_check_of_a_missing_file_leaves_the_stored_value(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    register_core_models_schema: SchemaBranch,
    register_builtin_models_schema: SchemaBranch,
    car_person_data_generic: dict[str, Node],
    encryption_enabled: StorageKey,
) -> None:
    artifact = await create_artifact(db=db, car_person_data_generic=car_person_data_generic)

    with client:
        response = client.post(url=f"/api/artifact/{artifact.id}/encryption", headers=admin_headers)

    assert (response.status_code, response.json()) == (
        200,
        {"encryption": "plaintext", "reason": "missing", "updated": False},
    )


async def test_check_of_an_unknown_artifact_is_refused(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
) -> None:
    with client:
        response = client.post(url="/api/artifact/unknown-artifact/encryption", headers=admin_headers)

    assert response.status_code == 404
