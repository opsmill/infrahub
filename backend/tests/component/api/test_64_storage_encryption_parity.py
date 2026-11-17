"""The route for one object and the route for several must give the same outcome for every file.

The cases of `backend/tests/unit/storage_encryption/test_migrate_parity.py` run there without a database; these
run through the real routes with the checksums that nodes record, including a file whose node was changed
to point at another stored object, which only the lookup of the checksums in the database can tell apart.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub import config
from infrahub.artifacts.queries import ArtifactChecksumsQuery
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.storage_encryption.crypto import StorageKey, open_envelope, seal
from infrahub.storage_encryption.migrate import get_recorded_checksums
from tests.helpers.artifact import create_stored_artifact
from tests.helpers.schema.file_contract import FILE_CONTRACT

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

ENVELOPE_MAGIC = b"IHSE"
UNPRIVILEGED_HEADERS = {"X-INFRAHUB-KEY": "unprivileged-token-parity"}
LIMIT_BYTES = 1024 * 1024


def sha1(content: bytes) -> str:
    return hashlib.sha1(content, usedforsecurity=False).hexdigest()


def md5(content: bytes) -> str:
    return hashlib.md5(content, usedforsecurity=False).hexdigest()


@dataclass
class StoredCase:
    name: str
    identifier: str
    content: bytes | None
    """What is stored under the identifier, or None when nothing is."""


ARTIFACT_CASE = StoredCase(name="artifact", identifier="0b9f9a8c-0000-4000-8000-0000000000a1", content=b'{"a": 1}')
FILE_CASE = StoredCase(name="file_object", identifier="0b9f9a8c-0000-4000-8000-0000000000f1", content=b"%PDF-1.7 one")
MODIFIED_CASE = StoredCase(
    name="modified_outside", identifier="0b9f9a8c-0000-4000-8000-0000000000f2", content=b"%PDF-1.7 changed"
)
REPLACED_OLD_CASE = StoredCase(
    name="replaced_file_old_object", identifier="0b9f9a8c-0000-4000-8000-0000000000f3", content=b"%PDF-1.7 second"
)
REPLACED_NEW_ID = "0b9f9a8c-0000-4000-8000-0000000000f4"
TOO_LARGE_CASE = StoredCase(
    name="verified_but_too_large", identifier="0b9f9a8c-0000-4000-8000-0000000000f5", content=b"b" * (LIMIT_BYTES + 1)
)
AT_LIMIT_CASE = StoredCase(
    name="verified_at_the_limit", identifier="0b9f9a8c-0000-4000-8000-0000000000f6", content=b"c" * LIMIT_BYTES
)
MISSING_CASE = StoredCase(name="recorded_but_missing", identifier="0b9f9a8c-0000-4000-8000-0000000000f7", content=None)
ORPHAN_CASE = StoredCase(name="orphan", identifier="0b9f9a8c-0000-4000-8000-0000000000b1", content=b"nobody refers")
ENCRYPTED_CASE = StoredCase(
    name="already_encrypted", identifier="0b9f9a8c-0000-4000-8000-0000000000e1", content=b"%PDF-1.7 sealed"
)
OTHER_KEY_CASE = StoredCase(
    name="sealed_with_another_key", identifier="0b9f9a8c-0000-4000-8000-0000000000e2", content=b"other key"
)
TRUNCATED_CASE = StoredCase(
    name="truncated_envelope", identifier="0b9f9a8c-0000-4000-8000-0000000000e3", content=b"truncated"
)
UNKNOWN_CASE = StoredCase(name="no_such_identifier", identifier="0b9f9a8c-0000-4000-8000-0000000000e4", content=None)
OTHER_KEY = StorageKey.derive("another-key-for-parity-tests-0123456789")


@pytest.fixture
def encryption_enabled(monkeypatch: pytest.MonkeyPatch) -> StorageKey:
    monkeypatch.setattr(config.SETTINGS.storage, "encryption_enabled", True)
    monkeypatch.setattr(config.SETTINGS.storage, "encryption_migration_max_size", 1)
    return StorageKey.derive(config.SETTINGS.security.secret_key)


@pytest.fixture
async def unprivileged_account(db: InfrahubDatabase, authentication_base: Node) -> Node:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="unprivileged-parity", account_type="User", password="UnprivilegedPassword123")
    await account.save(db=db)
    token = await Node.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
    await token.new(db=db, token=UNPRIVILEGED_HEADERS["X-INFRAHUB-KEY"], account=account)
    await token.save(db=db)
    return account


async def create_file_object(db: InfrahubDatabase, file_name: str, storage_id: str, checksum: str) -> Node:
    contract = await Node.init(db=db, schema="TestingFileContract")
    await contract.new(
        db=db, file_name=file_name, checksum=checksum, file_size=1, file_type="application/pdf", storage_id=storage_id
    )
    await contract.save(db=db)
    return contract


async def record_nodes(db: InfrahubDatabase, default_branch: Branch, car_person_data_generic: dict[str, Node]) -> None:
    """Create the nodes that record a checksum for some of the stored objects."""
    registry.schema.register_schema(schema=SchemaRoot(nodes=[FILE_CONTRACT]), branch=default_branch.name)
    await create_stored_artifact(
        db=db,
        car_person_data_generic=car_person_data_generic,
        storage_id=ARTIFACT_CASE.identifier,
        checksum=md5(ARTIFACT_CASE.content or b""),
    )
    await create_file_object(db, "one.pdf", FILE_CASE.identifier, sha1(FILE_CASE.content or b""))
    await create_file_object(db, "changed.pdf", MODIFIED_CASE.identifier, sha1(b"%PDF-1.7 what was recorded"))
    # The node first pointed at REPLACED_OLD_CASE with the checksum of another content, then at another object.
    replaced = await create_file_object(
        db, "replaced.pdf", REPLACED_OLD_CASE.identifier, sha1(b"%PDF-1.7 first version")
    )
    replaced.get_attribute(name="storage_id").value = REPLACED_NEW_ID
    replaced.get_attribute(name="checksum").value = sha1(REPLACED_OLD_CASE.content or b"")
    await replaced.save(db=db)
    await create_file_object(db, "large.pdf", TOO_LARGE_CASE.identifier, sha1(TOO_LARGE_CASE.content or b""))
    await create_file_object(db, "limit.pdf", AT_LIMIT_CASE.identifier, sha1(AT_LIMIT_CASE.content or b""))
    await create_file_object(db, "gone.pdf", MISSING_CASE.identifier, sha1(b"%PDF-1.7 gone"))
    await create_file_object(db, "sealed.pdf", ENCRYPTED_CASE.identifier, sha1(ENCRYPTED_CASE.content or b""))
    await create_file_object(db, "other.pdf", OTHER_KEY_CASE.identifier, sha1(OTHER_KEY_CASE.content or b""))
    await create_file_object(db, "cut.pdf", TRUNCATED_CASE.identifier, sha1(TRUNCATED_CASE.content or b""))


CASES = [
    ARTIFACT_CASE,
    FILE_CASE,
    MODIFIED_CASE,
    REPLACED_OLD_CASE,
    TOO_LARGE_CASE,
    AT_LIMIT_CASE,
    MISSING_CASE,
    ORPHAN_CASE,
    ENCRYPTED_CASE,
    OTHER_KEY_CASE,
    TRUNCATED_CASE,
    UNKNOWN_CASE,
]

EXPECTED_OUTCOMES = {
    # without and with `allow_unverified`
    ARTIFACT_CASE.name: ("encrypted", "encrypted"),
    FILE_CASE.name: ("encrypted", "encrypted"),
    MODIFIED_CASE.name: ("skipped_checksum_mismatch", "skipped_checksum_mismatch"),
    REPLACED_OLD_CASE.name: ("skipped_checksum_mismatch", "skipped_checksum_mismatch"),
    TOO_LARGE_CASE.name: ("skipped_too_large", "skipped_too_large"),
    AT_LIMIT_CASE.name: ("encrypted", "encrypted"),
    MISSING_CASE.name: ("missing", "missing"),
    ORPHAN_CASE.name: ("skipped_unverified", "encrypted"),
    ENCRYPTED_CASE.name: ("already_encrypted", "already_encrypted"),
    OTHER_KEY_CASE.name: ("failed", "failed"),
    TRUNCATED_CASE.name: ("failed", "failed"),
    UNKNOWN_CASE.name: ("missing", "missing"),
}


def stored_bytes(case: StoredCase, key: StorageKey) -> bytes | None:
    if case.name == ENCRYPTED_CASE.name:
        return seal(identifier=case.identifier, content=case.content or b"", key=key)
    if case.name == OTHER_KEY_CASE.name:
        return seal(identifier=case.identifier, content=case.content or b"", key=OTHER_KEY)
    if case.name == TRUNCATED_CASE.name:
        return seal(identifier=case.identifier, content=case.content or b"", key=key)[:25]
    return case.content


def restore_files(directory: Path, key: StorageKey) -> dict[str, bytes]:
    for entry in directory.iterdir():
        entry.unlink()
    originals: dict[str, bytes] = {}
    for case in CASES:
        data = stored_bytes(case, key)
        if data is not None:
            (directory / case.identifier).write_bytes(data)
            originals[case.identifier] = data
    return originals


def describe_files(directory: Path, originals: dict[str, bytes], key: StorageKey) -> dict[str, Any]:
    """Each file as `unchanged`, or as the plain content it holds after being sealed with the current key."""
    state: dict[str, Any] = {}
    for entry in sorted(directory.iterdir()):
        data = entry.read_bytes()
        if originals.get(entry.name) == data:
            state[entry.name] = "unchanged"
        else:
            state[entry.name] = ("sealed", open_envelope(identifier=entry.name, content=data, key=key))
    return state


def run_single(client: TestClient, headers: dict[str, str], allow_unverified: bool) -> dict[str, Any]:
    results = {}
    for case in CASES:
        flag = "?allow_unverified=true" if allow_unverified else ""
        response = client.post(url=f"/api/storage/object/{case.identifier}/encrypt{flag}", headers=headers)
        assert response.status_code == 200
        results[case.identifier] = response.json()
    return results


def run_batch(client: TestClient, headers: dict[str, str], allow_unverified: bool) -> dict[str, Any]:
    identifiers = [case.identifier for case in CASES]
    response = client.post(
        url="/api/storage/objects/encrypt",
        headers=headers,
        json={"identifiers": identifiers, "allow_unverified": allow_unverified},
    )
    assert response.status_code == 200
    return {entry["identifier"]: entry for entry in response.json()["results"]}


PATHS = {"single": run_single, "batch": run_batch}


async def test_both_routes_give_the_pinned_outcomes_and_the_same_files(
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
    await record_nodes(db=db, default_branch=default_branch, car_person_data_generic=car_person_data_generic)
    names = {case.identifier: case.name for case in CASES}
    key = encryption_enabled

    observed: dict[tuple[str, bool], tuple[dict[str, str], dict[str, Any]]] = {}
    with client:
        for allow_unverified in (False, True):
            for path_name, run in PATHS.items():
                originals = restore_files(local_storage_dir, key)
                results = run(client, admin_headers, allow_unverified)
                outcomes = {names[identifier]: entry["outcome"] for identifier, entry in results.items()}
                sizes_and_reasons = {
                    names[identifier]: (entry["size"], entry["reason"]) for identifier, entry in results.items()
                }
                observed[path_name, allow_unverified] = (
                    outcomes | {"_detail": sizes_and_reasons},
                    describe_files(local_storage_dir, originals, key),
                )

    for allow_unverified in (False, True):
        position = 1 if allow_unverified else 0
        pinned = {name: outcomes[position] for name, outcomes in EXPECTED_OUTCOMES.items()}
        reference_outcomes, reference_files = observed["single", allow_unverified]
        assert {name: value for name, value in reference_outcomes.items() if name != "_detail"} == pinned
        for path_name in PATHS:
            assert (path_name, allow_unverified, *observed[path_name, allow_unverified]) == (
                path_name,
                allow_unverified,
                reference_outcomes,
                reference_files,
            )


async def test_lookup_of_recorded_checksums_gives_the_checksums_of_the_identifier_at_that_time(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_builtin_models_schema: SchemaBranch,
    car_person_data_generic: dict[str, Node],
) -> None:
    await record_nodes(db=db, default_branch=default_branch, car_person_data_generic=car_person_data_generic)
    identifiers = [case.identifier for case in CASES] + [REPLACED_NEW_ID]

    looked_up = await get_recorded_checksums(db=db, storage_ids=identifiers)

    assert looked_up == {
        ARTIFACT_CASE.identifier: {md5(ARTIFACT_CASE.content or b"")},
        FILE_CASE.identifier: {sha1(FILE_CASE.content or b"")},
        MODIFIED_CASE.identifier: {sha1(b"%PDF-1.7 what was recorded")},
        REPLACED_OLD_CASE.identifier: {sha1(b"%PDF-1.7 first version")},
        REPLACED_NEW_ID: {sha1(REPLACED_OLD_CASE.content or b"")},
        TOO_LARGE_CASE.identifier: {sha1(TOO_LARGE_CASE.content or b"")},
        AT_LIMIT_CASE.identifier: {sha1(AT_LIMIT_CASE.content or b"")},
        MISSING_CASE.identifier: {sha1(b"%PDF-1.7 gone")},
        ORPHAN_CASE.identifier: frozenset(),
        ENCRYPTED_CASE.identifier: {sha1(ENCRYPTED_CASE.content or b"")},
        OTHER_KEY_CASE.identifier: {sha1(OTHER_KEY_CASE.content or b"")},
        TRUNCATED_CASE.identifier: {sha1(TRUNCATED_CASE.content or b"")},
        UNKNOWN_CASE.identifier: frozenset(),
    }


async def test_lookup_of_recorded_checksums_of_an_artifact_equals_the_one_that_serving_uses(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_builtin_models_schema: SchemaBranch,
    car_person_data_generic: dict[str, Node],
) -> None:
    await record_nodes(db=db, default_branch=default_branch, car_person_data_generic=car_person_data_generic)

    serving_query = await ArtifactChecksumsQuery.init(db=db, storage_id=ARTIFACT_CASE.identifier)
    await serving_query.execute(db=db)
    looked_up = await get_recorded_checksums(db=db, storage_ids=[ARTIFACT_CASE.identifier])

    assert looked_up[ARTIFACT_CASE.identifier] == serving_query.get_data().checksums


async def test_batch_route_refuses_the_callers_the_single_route_refuses(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    default_branch: Branch,
    authentication_base: Node,
    unprivileged_account: Node,
    encryption_enabled: StorageKey,
) -> None:
    (local_storage_dir / ORPHAN_CASE.identifier).write_bytes(ORPHAN_CASE.content or b"")
    body = {"identifiers": [ORPHAN_CASE.identifier], "allow_unverified": True}
    single_url = f"/api/storage/object/{ORPHAN_CASE.identifier}/encrypt?allow_unverified=true"

    with client:
        single = client.post(url=single_url, headers=UNPRIVILEGED_HEADERS)
        batch = client.post(url="/api/storage/objects/encrypt", headers=UNPRIVILEGED_HEADERS, json=body)
        anonymous_single = client.post(url=single_url)
        anonymous_batch = client.post(url="/api/storage/objects/encrypt", json=body)

    assert [response.status_code for response in (single, batch)] == [403, 403]
    assert [response.status_code for response in (anonymous_single, anonymous_batch)] == [401, 401]
    assert (local_storage_dir / ORPHAN_CASE.identifier).read_bytes() == ORPHAN_CASE.content
