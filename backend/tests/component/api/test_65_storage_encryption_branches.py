"""Which recorded checksum a stored file is compared with when nodes live on several branches and change over time."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.artifacts.queries import ArtifactChecksumsQuery
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.storage_encryption.crypto import StorageKey
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
FILE_KIND = "TestingFileContract"
STORAGE_IDS = {name: f"0b9f9a8c-0000-4000-8000-0000000000{number:02x}" for number, name in enumerate("abcdefgh", 1)}


def sha1(content: bytes) -> str:
    return hashlib.sha1(content, usedforsecurity=False).hexdigest()


def md5(content: bytes) -> str:
    return hashlib.md5(content, usedforsecurity=False).hexdigest()


@pytest.fixture
def encryption_enabled(monkeypatch: pytest.MonkeyPatch) -> StorageKey:
    monkeypatch.setattr(config.SETTINGS.storage, "encryption_enabled", True)
    return StorageKey.derive(config.SETTINGS.security.secret_key)


@pytest.fixture
def file_schema(default_branch: Branch, register_core_models_schema: SchemaBranch) -> None:
    registry.schema.register_schema(schema=SchemaRoot(nodes=[FILE_CONTRACT]), branch=default_branch.name)


@pytest.fixture
async def branch(db: InfrahubDatabase, file_schema: None) -> Branch:
    return await create_branch(branch_name="feature", db=db)


async def create_file(db: InfrahubDatabase, storage_id: str, checksum: str, on: Branch | None = None) -> Node:
    contract = await Node.init(db=db, schema=FILE_KIND, branch=on)
    await contract.new(
        db=db, file_name="file.pdf", checksum=checksum, file_size=1, file_type="application/pdf", storage_id=storage_id
    )
    await contract.save(db=db)
    return contract


async def change_node(db: InfrahubDatabase, node: Node, on: Branch | None = None, **attributes: str) -> None:
    """Save new values of some attributes of a node, on a branch when one is given."""
    reloaded = await NodeManager.get_one(db=db, id=node.id, branch=on)
    assert reloaded is not None
    for name, value in attributes.items():
        reloaded.get_attribute(name=name).value = value
    await reloaded.save(db=db)


async def test_file_recorded_on_a_branch_that_was_never_merged_is_encrypted(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    branch: Branch,
    authentication_base: Node,
    encryption_enabled: StorageKey,
) -> None:
    content = b"%PDF-1.7 only on a branch"
    (local_storage_dir / STORAGE_IDS["a"]).write_bytes(content)
    await create_file(db=db, storage_id=STORAGE_IDS["a"], checksum=sha1(content), on=branch)

    with client:
        response = client.post(
            url="/api/storage/objects/encrypt", headers=admin_headers, json={"identifiers": [STORAGE_IDS["a"]]}
        )

    assert response.status_code == 200
    assert [(entry["outcome"], entry["reason"]) for entry in response.json()["results"]] == [("encrypted", None)]
    assert (local_storage_dir / STORAGE_IDS["a"]).read_bytes()[:4] == ENVELOPE_MAGIC


async def test_checksum_recorded_on_a_branch_is_not_applied_to_the_file_of_the_default_branch(
    db: InfrahubDatabase, file_schema: None, car_person_data_generic: dict[str, Node]
) -> None:
    """Nodes of the default branch whose file and checksum were both replaced on a branch created later."""
    file = await create_file(db=db, storage_id=STORAGE_IDS["a"], checksum=sha1(b"main version"))
    artifact = await create_stored_artifact(
        db=db, car_person_data_generic=car_person_data_generic, storage_id=STORAGE_IDS["c"], checksum=md5(b"main")
    )
    branch = await create_branch(branch_name="feature", db=db)
    await change_node(db=db, node=file, on=branch, storage_id=STORAGE_IDS["b"], checksum=sha1(b"branch version"))
    await change_node(db=db, node=artifact, on=branch, checksum=md5(b"branch"))

    looked_up = await get_recorded_checksums(db=db, storage_ids=[STORAGE_IDS[name] for name in "abc"])
    artifact_query = await ArtifactChecksumsQuery.init(db=db, storage_id=STORAGE_IDS["c"])
    await artifact_query.execute(db=db)

    assert looked_up == {
        STORAGE_IDS["a"]: {sha1(b"main version")},
        STORAGE_IDS["b"]: {sha1(b"branch version")},
        STORAGE_IDS["c"]: {md5(b"main")},
    }
    assert artifact_query.get_data().checksums == {md5(b"main")}


async def test_checksum_that_ended_before_the_identifier_was_recorded_is_not_applied(
    db: InfrahubDatabase, file_schema: None
) -> None:
    # The checksum is replaced first, then the identifier: the first checksum ended before the second identifier began.
    checksum_first = await create_file(db=db, storage_id=STORAGE_IDS["a"], checksum=sha1(b"first"))
    await change_node(db=db, node=checksum_first, checksum=sha1(b"second"))
    await change_node(db=db, node=checksum_first, storage_id=STORAGE_IDS["b"])
    # The identifier is replaced first, then the checksum: the second checksum began after the first identifier ended.
    storage_first = await create_file(db=db, storage_id=STORAGE_IDS["c"], checksum=sha1(b"third"))
    await change_node(db=db, node=storage_first, storage_id=STORAGE_IDS["d"])
    await change_node(db=db, node=storage_first, checksum=sha1(b"fourth"))

    looked_up = await get_recorded_checksums(db=db, storage_ids=[STORAGE_IDS[name] for name in "abcd"])

    assert looked_up == {
        STORAGE_IDS["a"]: {sha1(b"first"), sha1(b"second")},
        STORAGE_IDS["b"]: {sha1(b"second")},
        STORAGE_IDS["c"]: {sha1(b"third")},
        STORAGE_IDS["d"]: {sha1(b"third"), sha1(b"fourth")},
    }


async def test_artifact_checksum_that_ended_before_or_began_after_the_identifier_is_not_applied(
    db: InfrahubDatabase, car_person_data_generic: dict[str, Node]
) -> None:
    """The checksum is replaced, then the identifier, then the checksum again."""
    artifact = await create_stored_artifact(
        db=db, car_person_data_generic=car_person_data_generic, storage_id=STORAGE_IDS["e"], checksum=md5(b"first")
    )
    await change_node(db=db, node=artifact, checksum=md5(b"second"))
    await change_node(db=db, node=artifact, storage_id=STORAGE_IDS["f"])
    await change_node(db=db, node=artifact, checksum=md5(b"third"))

    queried = {}
    for name in "ef":
        query = await ArtifactChecksumsQuery.init(db=db, storage_id=STORAGE_IDS[name])
        await query.execute(db=db)
        queried[name] = query.get_data().checksums
    looked_up = await get_recorded_checksums(db=db, storage_ids=[STORAGE_IDS["e"], STORAGE_IDS["f"]])

    expected = {"e": {md5(b"first"), md5(b"second")}, "f": {md5(b"second"), md5(b"third")}}
    assert queried == expected
    assert looked_up == {STORAGE_IDS[name]: checksums for name, checksums in expected.items()}


async def test_file_of_a_deleted_artifact_or_file_object_is_still_checked_against_its_recorded_checksum(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    file_schema: None,
    authentication_base: Node,
    car_person_data_generic: dict[str, Node],
    encryption_enabled: StorageKey,
) -> None:
    file_content, artifact_content, altered_content = b"%PDF-1.7 deleted", b'{"deleted": true}', b"altered file"
    (local_storage_dir / STORAGE_IDS["a"]).write_bytes(file_content)
    (local_storage_dir / STORAGE_IDS["b"]).write_bytes(artifact_content)
    (local_storage_dir / STORAGE_IDS["c"]).write_bytes(altered_content)
    deleted_file = await create_file(db=db, storage_id=STORAGE_IDS["a"], checksum=sha1(file_content))
    await deleted_file.delete(db=db)
    deleted_artifact = await create_stored_artifact(
        db=db,
        car_person_data_generic=car_person_data_generic,
        storage_id=STORAGE_IDS["b"],
        checksum=md5(artifact_content),
    )
    await deleted_artifact.delete(db=db)
    altered_file = await create_file(db=db, storage_id=STORAGE_IDS["c"], checksum=sha1(b"what was recorded"))
    await altered_file.delete(db=db)

    with client:
        response = client.post(
            url="/api/storage/objects/encrypt",
            headers=admin_headers,
            json={"identifiers": [STORAGE_IDS[name] for name in "abc"]},
        )

    assert response.status_code == 200
    assert [(entry["identifier"], entry["outcome"]) for entry in response.json()["results"]] == [
        (STORAGE_IDS["a"], "encrypted"),
        (STORAGE_IDS["b"], "encrypted"),
        (STORAGE_IDS["c"], "skipped_checksum_mismatch"),
    ]
    assert (local_storage_dir / STORAGE_IDS["c"]).read_bytes() == altered_content


async def test_file_two_nodes_record_with_different_checksums_is_encrypted_only_when_it_matches_one_of_them(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    file_schema: None,
    authentication_base: Node,
    encryption_enabled: StorageKey,
) -> None:
    """Content that one of the nodes recorded is content Infrahub stored; content nobody recorded is left as it is."""
    (local_storage_dir / STORAGE_IDS["a"]).write_bytes(b"first node's content")
    (local_storage_dir / STORAGE_IDS["b"]).write_bytes(b"second node's content")
    (local_storage_dir / STORAGE_IDS["c"]).write_bytes(b"content of neither node")
    for storage_id, recorded in (("a", b"first node's content"), ("b", b"first node's content"), ("c", b"one")):
        await create_file(db=db, storage_id=STORAGE_IDS[storage_id], checksum=sha1(recorded))
    for storage_id, recorded in (("a", b"other"), ("b", b"second node's content"), ("c", b"two")):
        await create_file(db=db, storage_id=STORAGE_IDS[storage_id], checksum=sha1(recorded))

    with client:
        response = client.post(
            url="/api/storage/objects/encrypt",
            headers=admin_headers,
            json={"identifiers": [STORAGE_IDS[name] for name in "abc"]},
        )

    assert response.status_code == 200
    assert [(entry["identifier"], entry["outcome"]) for entry in response.json()["results"]] == [
        (STORAGE_IDS["a"], "encrypted"),
        (STORAGE_IDS["b"], "encrypted"),
        (STORAGE_IDS["c"], "skipped_checksum_mismatch"),
    ]
    assert (local_storage_dir / STORAGE_IDS["c"]).read_bytes() == b"content of neither node"
