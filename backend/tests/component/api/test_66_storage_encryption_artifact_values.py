"""The stored encryption value of the artifacts whose file the migration routes encrypt or find encrypted."""

from __future__ import annotations

import asyncio
import hashlib
import threading
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from infrahub import config
from infrahub.api.storage.encryption_migration import encrypt_stored_object_route
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreArtifact
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.exceptions import DatabaseError, QueryTimeoutError
from infrahub.storage import InfrahubObjectStorage
from infrahub.storage_encryption import artifact_values
from infrahub.storage_encryption.codec import select_codec
from infrahub.storage_encryption.crypto import StorageKey, seal
from tests.adapters.cache import MemoryCache
from tests.helpers.artifact import create_sibling_artifact, create_stored_artifact, stored_artifact_encryption
from tests.helpers.schema.file_contract import FILE_CONTRACT

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType

    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.core.constants import ArtifactEncryption
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

STORAGE_IDS = {name: f"0b9f9a8c-0000-4000-8000-0000000000{number:02x}" for number, name in enumerate("abcdefg", 1)}
CONTENT = {name: f'{{"hostname": "leaf-{name}"}}'.encode() for name in "abcdefg"}
ENVELOPE_MAGIC = b"IHSE"


def md5(content: bytes) -> str:
    return hashlib.md5(content, usedforsecurity=False).hexdigest()


@pytest.fixture
def encryption_enabled(monkeypatch: pytest.MonkeyPatch) -> StorageKey:
    monkeypatch.setattr(config.SETTINGS.storage, "encryption_enabled", True)
    return StorageKey.derive(config.SETTINGS.security.secret_key)


@pytest.fixture
async def artifacts(
    db: InfrahubDatabase,
    default_branch: Branch,
    authentication_base: Node,
    register_core_models_schema: SchemaBranch,
    register_builtin_models_schema: SchemaBranch,
    car_person_data_generic: dict[str, Node],
) -> dict[str, Node]:
    """Three artifacts, each stored as a plain file, with the stored value `plaintext`."""
    first = await create_stored_artifact(
        db=db, car_person_data_generic=car_person_data_generic, storage_id=STORAGE_IDS["a"], checksum=md5(CONTENT["a"])
    )
    second = await create_sibling_artifact(
        db=db,
        artifact=first,
        target=car_person_data_generic["c2"],
        name="artifact-b",
        storage_id=STORAGE_IDS["b"],
        checksum=md5(CONTENT["b"]),
    )
    third = await create_sibling_artifact(
        db=db,
        artifact=first,
        target=car_person_data_generic["c3"],
        name="artifact-c",
        storage_id=STORAGE_IDS["c"],
        checksum=md5(CONTENT["c"]),
    )
    return {"a": first, "b": second, "c": third}


def write_plain_files(local_storage_dir: Path, names: str) -> None:
    for name in names:
        (local_storage_dir / STORAGE_IDS[name]).write_bytes(CONTENT[name])


async def stored_values(db: InfrahubDatabase, artifacts: dict[str, Node]) -> dict[str, str]:
    return {
        name: await stored_artifact_encryption(db=db, artifact_id=artifact.id) for name, artifact in artifacts.items()
    }


def outcomes(response_json: dict[str, list[dict[str, str]]]) -> list[tuple[str, str]]:
    return [(entry["identifier"], entry["outcome"]) for entry in response_json["results"]]


async def test_single_object_route_stores_encrypted_on_the_artifact_of_the_file(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    artifacts: dict[str, Node],
    encryption_enabled: StorageKey,
) -> None:
    write_plain_files(local_storage_dir, "abc")

    with client:
        response = client.post(f"/api/storage/object/{STORAGE_IDS['a']}/encrypt", headers=admin_headers)

    assert (response.status_code, response.json()["outcome"]) == (200, "encrypted")
    assert (local_storage_dir / STORAGE_IDS["a"]).read_bytes()[:4] == ENVELOPE_MAGIC
    assert await stored_values(db=db, artifacts=artifacts) == {"a": "encrypted", "b": "plaintext", "c": "plaintext"}


async def test_batch_route_stores_encrypted_on_every_artifact_whose_file_it_encrypted(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    artifacts: dict[str, Node],
    encryption_enabled: StorageKey,
) -> None:
    write_plain_files(local_storage_dir, "abc")
    identifiers = [STORAGE_IDS["a"], STORAGE_IDS["b"], STORAGE_IDS["c"]]

    with client:
        response = client.post("/api/storage/objects/encrypt", headers=admin_headers, json={"identifiers": identifiers})

    assert response.status_code == 200
    assert outcomes(response.json()) == [(identifier, "encrypted") for identifier in identifiers]
    assert await stored_values(db=db, artifacts=artifacts) == {"a": "encrypted", "b": "encrypted", "c": "encrypted"}


async def test_rerun_corrects_the_stored_value_of_a_file_that_is_already_encrypted(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    artifacts: dict[str, Node],
    encryption_enabled: StorageKey,
) -> None:
    key = encryption_enabled
    (local_storage_dir / STORAGE_IDS["a"]).write_bytes(seal(identifier=STORAGE_IDS["a"], content=CONTENT["a"], key=key))

    with client:
        response = client.post(
            "/api/storage/objects/encrypt", headers=admin_headers, json={"identifiers": [STORAGE_IDS["a"]]}
        )
        again = client.post(
            "/api/storage/objects/encrypt", headers=admin_headers, json={"identifiers": [STORAGE_IDS["a"]]}
        )

    assert outcomes(response.json()) == [(STORAGE_IDS["a"], "already_encrypted")]
    assert outcomes(again.json()) == [(STORAGE_IDS["a"], "already_encrypted")]
    assert await stored_values(db=db, artifacts=artifacts) == {"a": "encrypted", "b": "plaintext", "c": "plaintext"}


async def test_artifact_whose_file_is_missing_or_was_skipped_keeps_its_value(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    artifacts: dict[str, Node],
    encryption_enabled: StorageKey,
) -> None:
    # a: no file stored; b: file modified outside Infrahub; c: intact file.
    (local_storage_dir / STORAGE_IDS["b"]).write_bytes(b'{"hostname": "tampered"}')
    write_plain_files(local_storage_dir, "c")
    identifiers = [STORAGE_IDS["a"], STORAGE_IDS["b"], STORAGE_IDS["c"]]

    with client:
        response = client.post("/api/storage/objects/encrypt", headers=admin_headers, json={"identifiers": identifiers})

    assert outcomes(response.json()) == [
        (STORAGE_IDS["a"], "missing"),
        (STORAGE_IDS["b"], "skipped_checksum_mismatch"),
        (STORAGE_IDS["c"], "encrypted"),
    ]
    assert await stored_values(db=db, artifacts=artifacts) == {"a": "plaintext", "b": "plaintext", "c": "encrypted"}


async def test_failed_value_write_keeps_the_encrypted_outcome_and_the_next_run_stores_the_value(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    artifacts: dict[str, Node],
    encryption_enabled: StorageKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_plain_files(local_storage_dir, "abc")
    identifiers = [STORAGE_IDS["a"], STORAGE_IDS["b"], STORAGE_IDS["c"]]
    store = artifact_values.store_artifact_encryption
    failed_for: list[str] = []

    async def failing_for_the_second_artifact(
        *, db: InfrahubDatabase, artifact: CoreArtifact, found: ArtifactEncryption, user_id: str
    ) -> bool:
        if artifact.id == artifacts["b"].id:
            failed_for.append(artifact.id)
            raise DatabaseError(message="Unable to connect to the database")
        return await store(db=db, artifact=artifact, found=found, user_id=user_id)

    with client:
        monkeypatch.setattr(artifact_values, "store_artifact_encryption", failing_for_the_second_artifact)
        first = client.post("/api/storage/objects/encrypt", headers=admin_headers, json={"identifiers": identifiers})
        after_failure = await stored_values(db=db, artifacts=artifacts)
        monkeypatch.setattr(artifact_values, "store_artifact_encryption", store)
        second = client.post("/api/storage/objects/encrypt", headers=admin_headers, json={"identifiers": identifiers})

    assert failed_for == [artifacts["b"].id]
    assert outcomes(first.json()) == [(identifier, "encrypted") for identifier in identifiers]
    assert after_failure == {"a": "encrypted", "b": "plaintext", "c": "encrypted"}
    assert outcomes(second.json()) == [(identifier, "already_encrypted") for identifier in identifiers]
    assert await stored_values(db=db, artifacts=artifacts) == {"a": "encrypted", "b": "encrypted", "c": "encrypted"}


async def test_failed_lookup_of_the_artifacts_keeps_the_encrypted_outcome_and_the_next_run_stores_the_values(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    artifacts: dict[str, Node],
    encryption_enabled: StorageKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_plain_files(local_storage_dir, "abc")
    identifiers = [STORAGE_IDS["a"], STORAGE_IDS["b"], STORAGE_IDS["c"]]

    async def failing_lookup(*_: object, **__: object) -> list[Node]:
        raise QueryTimeoutError

    with client:
        with monkeypatch.context() as patched:
            patched.setattr(NodeManager, "query", failing_lookup)
            first = client.post(
                "/api/storage/objects/encrypt", headers=admin_headers, json={"identifiers": identifiers}
            )
            after_failure = await stored_values(db=db, artifacts=artifacts)
        second = client.post("/api/storage/objects/encrypt", headers=admin_headers, json={"identifiers": identifiers})

    assert outcomes(first.json()) == [(identifier, "encrypted") for identifier in identifiers]
    assert after_failure == {"a": "plaintext", "b": "plaintext", "c": "plaintext"}
    assert outcomes(second.json()) == [(identifier, "already_encrypted") for identifier in identifiers]
    assert await stored_values(db=db, artifacts=artifacts) == {"a": "encrypted", "b": "encrypted", "c": "encrypted"}


async def test_file_objects_and_orphan_files_are_encrypted_and_no_artifact_value_changes(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    artifacts: dict[str, Node],
    default_branch: Branch,
    encryption_enabled: StorageKey,
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(nodes=[FILE_CONTRACT]), branch=default_branch.name)
    contract = await Node.init(db=db, schema="TestingFileContract")
    await contract.new(
        db=db,
        file_name="contract.pdf",
        checksum=hashlib.sha1(CONTENT["d"], usedforsecurity=False).hexdigest(),
        file_size=len(CONTENT["d"]),
        file_type="application/pdf",
        storage_id=STORAGE_IDS["d"],
    )
    await contract.save(db=db)
    write_plain_files(local_storage_dir, "abde")  # d: file object, e: orphan, a and b: artifacts not in the request
    identifiers = [STORAGE_IDS["d"], STORAGE_IDS["e"]]

    with client:
        response = client.post(
            "/api/storage/objects/encrypt",
            headers=admin_headers,
            json={"identifiers": identifiers, "allow_unverified": True},
        )

    assert outcomes(response.json()) == [(STORAGE_IDS["d"], "encrypted"), (STORAGE_IDS["e"], "encrypted")]
    assert await stored_values(db=db, artifacts=artifacts) == {"a": "plaintext", "b": "plaintext", "c": "plaintext"}
    assert (local_storage_dir / STORAGE_IDS["a"]).read_bytes() == CONTENT["a"]


async def test_artifact_that_replaced_its_file_is_not_changed_by_the_encryption_of_the_old_file(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    artifacts: dict[str, Node],
    encryption_enabled: StorageKey,
) -> None:
    artifact = await NodeManager.get_one(db=db, id=artifacts["a"].id, kind=CoreArtifact)
    assert artifact is not None
    artifact.storage_id.value = STORAGE_IDS["f"]
    artifact.checksum.value = md5(CONTENT["f"])
    await artifact.save(db=db)
    write_plain_files(local_storage_dir, "af")  # a: the file of an earlier version, f: the current file

    with client:
        response = client.post(
            "/api/storage/objects/encrypt", headers=admin_headers, json={"identifiers": [STORAGE_IDS["a"]]}
        )

    assert outcomes(response.json()) == [(STORAGE_IDS["a"], "encrypted")]
    assert await stored_values(db=db, artifacts=artifacts) == {"a": "plaintext", "b": "plaintext", "c": "plaintext"}


@pytest.mark.xfail(
    strict=True,
    reason="Only the artifacts that the default branch sees are updated; an artifact that exists only on a branch keeps its value",
)
async def test_artifact_that_exists_only_on_a_branch_gets_the_value_on_that_branch(
    db: InfrahubDatabase,
    client: TestClient,
    local_storage_dir: Path,
    admin_headers: dict[str, str],
    artifacts: dict[str, Node],
    car_person_data_generic: dict[str, Node],
    encryption_enabled: StorageKey,
) -> None:
    branch = await create_branch(branch_name="feature", db=db)
    on_branch = await create_sibling_artifact(
        db=db,
        artifact=artifacts["a"],
        target=car_person_data_generic["c4"],
        name="artifact-on-branch",
        storage_id=STORAGE_IDS["g"],
        checksum=md5(CONTENT["g"]),
        on=branch,
    )
    (local_storage_dir / STORAGE_IDS["g"]).write_bytes(CONTENT["g"])

    with client:
        response = client.post(f"/api/storage/object/{STORAGE_IDS['g']}/encrypt", headers=admin_headers)

    reloaded = await NodeManager.get_one(db=db, id=on_branch.id, branch=branch, kind=CoreArtifact)
    assert response.json()["outcome"] == "encrypted"
    assert reloaded is not None
    assert reloaded.encryption.value == "encrypted"


class HeldStorage(InfrahubObjectStorage):
    """A storage whose replacement of an object waits until the test lets it go on."""

    def __init__(self, settings: config.StorageSettings, key: StorageKey) -> None:
        super().__init__(settings=settings, codec=select_codec(encryption_enabled=True, key=key))
        self.replacing = threading.Event()
        self.go_on = threading.Event()

    def replace(self, identifier: str, content: bytes) -> None:
        self.replacing.set()
        assert self.go_on.wait(timeout=30)
        super().replace(identifier=identifier, content=content)


class AllowAllPermissions:
    def has_permission(self, permission: object) -> bool:
        return True

    def raise_for_permission(self, permission: object, message: str = "") -> None:
        return None


class RecordedSession:
    """A session of the database that tells when it was closed."""

    def __init__(self, session: InfrahubDatabase, closed: asyncio.Event) -> None:
        self._session = session
        self._closed = closed

    async def __aenter__(self) -> InfrahubDatabase:
        return await self._session.__aenter__()

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await self._session.__aexit__(exc_type, exc, traceback)
        self._closed.set()


class RecordingDatabase:
    """The database of the application, opening sessions that tell when they were closed."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self._db = db
        self.closed = asyncio.Event()

    def start_session(self) -> RecordedSession:
        return RecordedSession(session=self._db.start_session(), closed=self.closed)


async def test_artifact_value_is_stored_when_the_request_is_cancelled_while_the_object_is_written(
    db: InfrahubDatabase,
    local_storage_dir: Path,
    artifacts: dict[str, Node],
    authentication_base: Node,
    encryption_enabled: StorageKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_plain_files(local_storage_dir, "a")
    storage = HeldStorage(settings=config.SETTINGS.storage, key=encryption_enabled)
    monkeypatch.setattr(registry, "_storage", storage)
    application_db = RecordingDatabase(db=db)
    request: Any = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(service=SimpleNamespace(cache=MemoryCache()), db=application_db))
    )
    permission_manager: Any = AllowAllPermissions()
    account: Any = SimpleNamespace(account_id=authentication_base.id)
    handler = asyncio.create_task(
        encrypt_stored_object_route(
            request=request,
            identifier=STORAGE_IDS["a"],
            allow_unverified=False,
            permission_manager=permission_manager,
            account=account,
        )
    )
    await asyncio.to_thread(storage.replacing.wait, 30)

    handler.cancel()
    with pytest.raises(asyncio.CancelledError):
        await handler
    storage.go_on.set()
    await asyncio.wait_for(application_db.closed.wait(), timeout=30)

    assert (local_storage_dir / STORAGE_IDS["a"]).read_bytes()[:4] == ENVELOPE_MAGIC
    assert await stored_values(db=db, artifacts=artifacts) == {"a": "encrypted", "b": "plaintext", "c": "plaintext"}
