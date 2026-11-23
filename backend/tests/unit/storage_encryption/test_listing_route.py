"""The first page of the listing clears the temporary files that an interrupted replacement left behind."""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.api.storage.encryption_migration import list_stored_objects
from infrahub.config import FileSystemStorageSettings, StorageSettings
from infrahub.core.registry import registry
from infrahub.storage import InfrahubObjectStorage
from infrahub.storage_encryption.codec import PlainCodec
from tests.helpers.storage import vanishing_directory

if TYPE_CHECKING:
    from pathlib import Path

OBJECT_ONE = "18a3f2e4-0000-4b1e-a0f7-3c9d2b6e8f01"
OBJECT_TWO = "18a3f2e4-0000-4b1e-a0f7-3c9d2b6e8f02"
STALE_TEMPORARY = f".{OBJECT_ONE}.0123456789abcdef.tmp"
YOUNG_TEMPORARY = f".{OBJECT_TWO}.fedcba9876543210.tmp"
TWO_HOURS = 2 * 3600


def names_in(path: Path) -> list[str]:
    return sorted(entry.name for entry in path.iterdir())


class AllowAll:
    def raise_for_permission(self, permission: object, message: str = "") -> None:
        return None


ALLOW_ALL: Any = AllowAll()


@pytest.fixture
def storage_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / OBJECT_ONE).write_bytes(b"one")
    (tmp_path / OBJECT_TWO).write_bytes(b"two")
    (tmp_path / STALE_TEMPORARY).write_bytes(b"half written")
    (tmp_path / YOUNG_TEMPORARY).write_bytes(b"being written")
    aged = time.time() - TWO_HOURS
    os.utime(tmp_path / STALE_TEMPORARY, (aged, aged))
    storage = InfrahubObjectStorage(
        settings=StorageSettings(local=FileSystemStorageSettings.model_validate({"path": tmp_path})),
        codec=PlainCodec(),
    )
    monkeypatch.setattr(registry, "_storage", storage)
    return tmp_path


async def test_the_first_page_removes_the_stale_temporary_files_and_keeps_the_rest(storage_dir: Path) -> None:
    page = await list_stored_objects(start_after=None, limit=10, permission_manager=ALLOW_ALL)

    assert ([entry.identifier for entry in page.objects], names_in(storage_dir)) == (
        [OBJECT_ONE, OBJECT_TWO],
        sorted([OBJECT_ONE, OBJECT_TWO, YOUNG_TEMPORARY]),
    )


async def test_a_later_page_removes_nothing(storage_dir: Path) -> None:
    await list_stored_objects(start_after=OBJECT_ONE, limit=10, permission_manager=ALLOW_ALL)

    assert names_in(storage_dir) == sorted([OBJECT_ONE, OBJECT_TWO, STALE_TEMPORARY, YOUNG_TEMPORARY])


async def test_paging_the_route_reaches_every_object_when_one_vanishes_during_a_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("obj-0", "obj-1", "obj-2", "obj-3", "obj-4"):
        (tmp_path / name).write_bytes(name.encode())
    storage = InfrahubObjectStorage(
        settings=StorageSettings(local=FileSystemStorageSettings.model_validate({"path": tmp_path})),
        codec=PlainCodec(),
    )
    storage._storage._path = vanishing_directory(tmp_path, frozenset({"obj-1"}))
    monkeypatch.setattr(registry, "_storage", storage)

    pages = []
    start_after = None
    while True:
        page = await list_stored_objects(start_after=start_after, limit=3, permission_manager=ALLOW_ALL)
        pages.append(([entry.identifier for entry in page.objects], page.next_start_after))
        if page.next_start_after is None:
            break
        start_after = page.next_start_after

    assert pages == [(["obj-0", "obj-2"], "obj-2"), (["obj-3", "obj-4"], None)]
