from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.api.storage import encryption_migration
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.storage_encryption.crypto import StorageKey, seal
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
LOOSE = b"content nobody references"
ENVELOPE_MAGIC = b"IHSE"
UNPRIVILEGED_HEADERS = {"X-INFRAHUB-KEY": "unprivileged-token"}
MODIFIED_AT = datetime(2024, 5, 17, 10, 30, tzinfo=UTC)


@pytest.fixture
def encryption_enabled(monkeypatch: pytest.MonkeyPatch) -> StorageKey:
    """Enable storage encryption for the application started by the test client."""
    monkeypatch.setattr(config.SETTINGS.storage, "encryption_enabled", True)
    return StorageKey.derive(config.SETTINGS.security.secret_key)


@pytest.fixture
async def unprivileged_account(db: InfrahubDatabase, authentication_base: Node) -> Node:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="unprivileged", account_type="User", password="UnprivilegedPassword123")
    await account.save(db=db)
    token = await Node.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
    await token.new(db=db, token=UNPRIVILEGED_HEADERS["X-INFRAHUB-KEY"], account=account)
    await token.save(db=db)
    return account


def encrypt_url(identifier: str) -> str:
    return f"/api/storage/object/{identifier}/encrypt"


async def test_listing_returns_the_stored_objects_page_by_page_in_identifier_order(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
) -> None:
    for name in ("obj-c", "obj-a", "obj-e", "obj-b", "obj-d"):
        (local_storage_dir / name).write_bytes(name.encode() * 2)
        os.utime(local_storage_dir / name, (MODIFIED_AT.timestamp(), MODIFIED_AT.timestamp()))
    (local_storage_dir / ".obj-a.0123.tmp").write_bytes(b"unfinished write")

    with client:
        first = client.get(url="/api/storage/objects?limit=2", headers=admin_headers)
        second = client.get(url="/api/storage/objects?limit=2&start_after=obj-b", headers=admin_headers)
        third = client.get(url="/api/storage/objects?limit=2&start_after=obj-d", headers=admin_headers)
        everything = client.get(url="/api/storage/objects", headers=admin_headers)

    def entry(name: str) -> dict[str, str | int]:
        return {"identifier": name, "size": 10, "last_modified": "2024-05-17T10:30:00Z"}

    assert [response.status_code for response in (first, second, third, everything)] == [200] * 4
    assert first.json() == {"objects": [entry("obj-a"), entry("obj-b")], "next_start_after": "obj-b"}
    assert second.json() == {"objects": [entry("obj-c"), entry("obj-d")], "next_start_after": "obj-d"}
    assert third.json() == {"objects": [entry("obj-e")], "next_start_after": None}
    assert everything.json() == {
        "objects": [entry(name) for name in ("obj-a", "obj-b", "obj-c", "obj-d", "obj-e")],
        "next_start_after": None,
    }


async def test_listing_refuses_a_page_larger_than_the_maximum(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
) -> None:
    with client:
        at_maximum = client.get(url="/api/storage/objects?limit=5000", headers=admin_headers)
        over_maximum = client.get(url="/api/storage/objects?limit=5001", headers=admin_headers)

    assert (at_maximum.status_code, over_maximum.status_code) == (200, 422)


async def test_artifact_file_with_a_recorded_checksum_is_encrypted_and_still_served(
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
    (local_storage_dir / ARTIFACT_ID).write_bytes(ARTIFACT)

    with client:
        encrypted = client.post(url=encrypt_url(ARTIFACT_ID), headers=admin_headers)
        stored = (local_storage_dir / ARTIFACT_ID).read_bytes()
        served = [
            client.get(url=url, headers=admin_headers)
            for url in (f"/api/artifact/{artifact.id}", f"/api/storage/object/{ARTIFACT_ID}")
        ]
        repeated = client.post(url=encrypt_url(ARTIFACT_ID), headers=admin_headers)

    assert (encrypted.status_code, encrypted.json()) == (
        200,
        {"identifier": ARTIFACT_ID, "outcome": "encrypted", "size": len(ARTIFACT), "reason": None},
    )
    assert stored[:13] == ENVELOPE_MAGIC + b"\x01" + bytes.fromhex(encryption_enabled.fingerprint)
    assert b"leaf01" not in stored
    assert [(response.status_code, response.content) for response in served] == [(200, ARTIFACT)] * 2
    assert (repeated.status_code, repeated.json()) == (
        200,
        {"identifier": ARTIFACT_ID, "outcome": "already_encrypted", "size": 0, "reason": None},
    )
    assert (local_storage_dir / ARTIFACT_ID).read_bytes() == stored


async def test_file_object_with_a_recorded_checksum_is_encrypted_and_still_served(
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
        encrypted = client.post(url=encrypt_url(FILE_ID), headers=admin_headers)
        stored = (local_storage_dir / FILE_ID).read_bytes()
        served = client.get(url=f"/api/storage/files/{contract.id}", headers=admin_headers)

    assert (encrypted.status_code, encrypted.json()) == (
        200,
        {"identifier": FILE_ID, "outcome": "encrypted", "size": len(FILE), "reason": None},
    )
    assert stored[:4] == ENVELOPE_MAGIC
    assert (served.status_code, served.content) == (200, FILE)


async def test_file_no_node_refers_to_is_encrypted_only_when_the_caller_accepts_it_unverified(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    encryption_enabled: StorageKey,
) -> None:
    (local_storage_dir / LOOSE_ID).write_bytes(LOOSE)

    with client:
        skipped = client.post(url=encrypt_url(LOOSE_ID), headers=admin_headers)
        stored_after_skip = (local_storage_dir / LOOSE_ID).read_bytes()
        accepted = client.post(url=f"{encrypt_url(LOOSE_ID)}?allow_unverified=true", headers=admin_headers)
        served = client.get(url=f"/api/storage/object/{LOOSE_ID}", headers=admin_headers)

    assert (skipped.status_code, skipped.json()) == (
        200,
        {
            "identifier": LOOSE_ID,
            "outcome": "skipped_unverified",
            "size": len(LOOSE),
            "reason": "no checksum is recorded for this object",
        },
    )
    assert stored_after_skip == LOOSE
    assert (accepted.status_code, accepted.json()) == (
        200,
        {"identifier": LOOSE_ID, "outcome": "encrypted", "size": len(LOOSE), "reason": None},
    )
    assert (local_storage_dir / LOOSE_ID).read_bytes()[:4] == ENVELOPE_MAGIC
    assert (served.status_code, served.content) == (200, LOOSE)


async def test_artifact_file_modified_outside_infrahub_is_left_unencrypted(
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
    await create_stored_artifact(
        db=db,
        car_person_data_generic=car_person_data_generic,
        storage_id=ARTIFACT_ID,
        checksum=hashlib.md5(ARTIFACT, usedforsecurity=False).hexdigest(),
    )
    tampered = b'{"hostname": "leaf01", "backdoor": true}'
    (local_storage_dir / ARTIFACT_ID).write_bytes(tampered)

    with client:
        response = client.post(url=f"{encrypt_url(ARTIFACT_ID)}?allow_unverified=true", headers=admin_headers)

    assert (response.status_code, response.json()) == (
        200,
        {
            "identifier": ARTIFACT_ID,
            "outcome": "skipped_checksum_mismatch",
            "size": len(tampered),
            "reason": "the content matches none of the checksums recorded for it",
        },
    )
    assert (local_storage_dir / ARTIFACT_ID).read_bytes() == tampered


async def test_file_encrypted_with_another_key_is_reported_as_failed(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    encryption_enabled: StorageKey,
) -> None:
    other_key = StorageKey.derive("another-key-for-migration-tests-0123456789")
    sealed = seal(identifier=LOOSE_ID, content=LOOSE, key=other_key)
    (local_storage_dir / LOOSE_ID).write_bytes(sealed)

    with client:
        response = client.post(url=f"{encrypt_url(LOOSE_ID)}?allow_unverified=true", headers=admin_headers)

    assert (response.status_code, response.json()) == (
        200,
        {
            "identifier": LOOSE_ID,
            "outcome": "failed",
            "size": 0,
            "reason": "the object starts like an encrypted one but is unreadable: unknown_key",
        },
    )
    assert (local_storage_dir / LOOSE_ID).read_bytes() == sealed


async def test_identifier_with_no_stored_file_is_reported_as_missing(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    encryption_enabled: StorageKey,
) -> None:
    with client:
        response = client.post(url=encrypt_url(LOOSE_ID), headers=admin_headers)

    assert (response.status_code, response.json()) == (
        200,
        {"identifier": LOOSE_ID, "outcome": "missing", "size": 0, "reason": None},
    )


async def test_file_larger_than_the_configured_maximum_is_skipped(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    encryption_enabled: StorageKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.SETTINGS.storage, "encryption_migration_max_size", 1)
    size = 1024 * 1024 + 1
    (local_storage_dir / LOOSE_ID).write_bytes(b"a" * size)

    with client:
        response = client.post(url=f"{encrypt_url(LOOSE_ID)}?allow_unverified=true", headers=admin_headers)

    assert (response.status_code, response.json()) == (
        200,
        {
            "identifier": LOOSE_ID,
            "outcome": "skipped_too_large",
            "size": size,
            "reason": f"{size} bytes is more than the limit of 1048576 bytes",
        },
    )
    assert (local_storage_dir / LOOSE_ID).read_bytes()[:4] == b"aaaa"


async def test_encrypting_is_refused_while_storage_encryption_is_disabled(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
) -> None:
    (local_storage_dir / LOOSE_ID).write_bytes(LOOSE)

    with client:
        response = client.post(url=f"{encrypt_url(LOOSE_ID)}?allow_unverified=true", headers=admin_headers)

    assert (response.status_code, response.json()) == (
        409,
        {
            "detail": (
                "Existing stored objects are not encrypted while storage encryption is disabled, because new files "
                "would still be stored unencrypted; set INFRAHUB_STORAGE_ENCRYPTION_ENABLED to true first"
            )
        },
    )
    assert (local_storage_dir / LOOSE_ID).read_bytes() == LOOSE


async def test_account_without_the_super_admin_permission_is_refused_on_both_routes(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    default_branch: Branch,
    authentication_base: Node,
    unprivileged_account: Node,
    encryption_enabled: StorageKey,
) -> None:
    (local_storage_dir / LOOSE_ID).write_bytes(LOOSE)

    with client:
        listing = client.get(url="/api/storage/objects", headers=UNPRIVILEGED_HEADERS)
        encrypt = client.post(url=f"{encrypt_url(LOOSE_ID)}?allow_unverified=true", headers=UNPRIVILEGED_HEADERS)
        anonymous_listing = client.get(url="/api/storage/objects")
        anonymous_encrypt = client.post(url=encrypt_url(LOOSE_ID))

    assert [response.status_code for response in (listing, encrypt)] == [403, 403]
    assert [response.status_code for response in (anonymous_listing, anonymous_encrypt)] == [403, 401]
    assert (local_storage_dir / LOOSE_ID).read_bytes() == LOOSE


@dataclass(frozen=True)
class BadIdentifierCase:
    name: str
    identifier: str


BAD_IDENTIFIER_CASES = [
    BadIdentifierCase(name="double-dot-inside", identifier="evil..name"),
    BadIdentifierCase(name="encoded-backslash", identifier="dir%5Cname"),
    BadIdentifierCase(name="encoded-parent-and-backslash", identifier="%2E%2E%5Csecret"),
]


@pytest.mark.parametrize("case", BAD_IDENTIFIER_CASES, ids=lambda case: case.name)
async def test_identifier_that_could_leave_the_storage_is_refused(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    encryption_enabled: StorageKey,
    case: BadIdentifierCase,
) -> None:
    with client:
        response = client.post(url=encrypt_url(case.identifier), headers=admin_headers)

    assert (response.status_code, response.json()) == (
        422,
        {"detail": "The identifier of a stored object cannot contain a path separator or '..'."},
    )


async def test_identifier_with_an_encoded_slash_reaches_no_route(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    encryption_enabled: StorageKey,
) -> None:
    outside = local_storage_dir.parent / "outside"
    outside.write_bytes(LOOSE)

    with client:
        response = client.post(url=f"{encrypt_url('..%2Foutside')}?allow_unverified=true", headers=admin_headers)

    assert response.status_code == 404
    assert outside.read_bytes() == LOOSE


async def test_request_is_answered_with_429_and_retry_after_when_no_memory_is_free(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    encryption_enabled: StorageKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(encryption_migration, "MEMORY_WAIT_SECONDS", 0.01)
    (local_storage_dir / LOOSE_ID).write_bytes(LOOSE)
    budget = encryption_migration.memory_budget()
    held = budget.claim(size=budget.largest_object, wait_seconds=0)

    with client:
        response = client.post(url=f"{encrypt_url(LOOSE_ID)}?allow_unverified=true", headers=admin_headers)
    budget.release(held)

    assert (response.status_code, response.headers["Retry-After"]) == (429, "1")
    assert (local_storage_dir / LOOSE_ID).read_bytes() == LOOSE
