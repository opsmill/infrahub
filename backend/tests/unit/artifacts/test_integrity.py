from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest

from infrahub.artifacts.checksum import compute_artifact_checksum, compute_file_object_checksum
from infrahub.artifacts.integrity import ArtifactChecksumResolver, request_artifact_regeneration, verify_content
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.constants import InfrahubKind
from infrahub.core.query.artifact import RecordedArtifactChecksum
from infrahub.exceptions import StorageObjectIntegrityError

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

CONTENT = b"hostname leaf01\nenable secret s3cret\n"
MODIFIED_CONTENT = b"hostname leaf01\nusername backdoor privilege 15 secret attacker\n"
DATABASE = cast("InfrahubDatabase", object())


def test_artifact_checksum_is_the_md5_recorded_by_the_generation() -> None:
    assert compute_artifact_checksum(CONTENT) == "4566f014bb4ff52052a018218adc61aa"


def test_file_object_checksum_is_the_sha1_recorded_at_upload() -> None:
    assert compute_file_object_checksum(CONTENT) == "00c6fcbfcec793cc78af8f0528c356351756719f"


@dataclass
class VerifyContentTestCase:
    name: str
    content: bytes
    expected_checksums: set[str | None]
    compute: Callable[[bytes], str]
    object_label: str
    expected_error: str | None


VERIFY_CONTENT_TEST_CASES: list[VerifyContentTestCase] = [
    VerifyContentTestCase(
        name="intact_artifact_is_accepted",
        content=CONTENT,
        expected_checksums={compute_artifact_checksum(CONTENT)},
        compute=compute_artifact_checksum,
        object_label="artifact",
        expected_error=None,
    ),
    VerifyContentTestCase(
        name="content_matching_one_of_several_recorded_checksums_is_accepted",
        content=CONTENT,
        expected_checksums={"0" * 32, compute_artifact_checksum(CONTENT)},
        compute=compute_artifact_checksum,
        object_label="artifact",
        expected_error=None,
    ),
    VerifyContentTestCase(
        name="modified_artifact_is_refused",
        content=MODIFIED_CONTENT,
        expected_checksums={compute_artifact_checksum(CONTENT)},
        compute=compute_artifact_checksum,
        object_label="artifact",
        expected_error=(
            "The content of the artifact stored as storage-1 does not match the recorded checksum and is not served."
        ),
    ),
    VerifyContentTestCase(
        name="artifact_without_recorded_checksum_is_refused",
        content=CONTENT,
        expected_checksums={None},
        compute=compute_artifact_checksum,
        object_label="artifact",
        expected_error="The artifact stored as storage-1 has no recorded checksum and is not served.",
    ),
    VerifyContentTestCase(
        name="modified_file_object_is_refused_with_its_own_label",
        content=MODIFIED_CONTENT,
        expected_checksums={compute_file_object_checksum(CONTENT)},
        compute=compute_file_object_checksum,
        object_label="file",
        expected_error=(
            "The content of the file stored as storage-1 does not match the recorded checksum and is not served."
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in VERIFY_CONTENT_TEST_CASES])
def test_verify_content(test_case: VerifyContentTestCase) -> None:
    if test_case.expected_error is None:
        verify_content(
            storage_id="storage-1",
            content=test_case.content,
            expected_checksums=test_case.expected_checksums,
            compute=test_case.compute,
            object_label=test_case.object_label,
        )
        return

    with pytest.raises(StorageObjectIntegrityError) as exc_info:
        verify_content(
            storage_id="storage-1",
            content=test_case.content,
            expected_checksums=test_case.expected_checksums,
            compute=test_case.compute,
            object_label=test_case.object_label,
        )
    assert exc_info.value.message == test_case.expected_error
    assert exc_info.value.HTTP_CODE == 409


class RecordingLookup:
    """Checksum lookup double returning canned answers and recording every storage id it was asked for."""

    def __init__(self, answers: dict[str, list[RecordedArtifactChecksum]]) -> None:
        self.answers = answers
        self.calls: list[str] = []

    async def __call__(self, db: InfrahubDatabase, storage_id: str) -> list[RecordedArtifactChecksum]:
        self.calls.append(storage_id)
        return self.answers.get(storage_id, [])


def recorded(node_id: str, checksum: str) -> list[RecordedArtifactChecksum]:
    return [RecordedArtifactChecksum(node_id=node_id, kind=InfrahubKind.ARTIFACT, branch="main", checksum=checksum)]


async def test_resolved_checksums_are_looked_up_once() -> None:
    lookup = RecordingLookup(answers={"storage-1": recorded(node_id="artifact-1", checksum="a" * 32)})
    resolver = ArtifactChecksumResolver(lookup=lookup)

    results = [await resolver.get_recorded_checksums(db=DATABASE, storage_id="storage-1") for _ in range(3)]

    assert results == [recorded(node_id="artifact-1", checksum="a" * 32)] * 3
    assert lookup.calls == ["storage-1"]


async def test_unreferenced_objects_are_looked_up_again() -> None:
    lookup = RecordingLookup(answers={})
    resolver = ArtifactChecksumResolver(lookup=lookup)

    results = [await resolver.get_recorded_checksums(db=DATABASE, storage_id="storage-1") for _ in range(2)]

    assert results == [[], []]
    assert lookup.calls == ["storage-1", "storage-1"]


async def test_object_referenced_after_a_first_lookup_is_resolved() -> None:
    lookup = RecordingLookup(answers={})
    resolver = ArtifactChecksumResolver(lookup=lookup)
    assert await resolver.get_recorded_checksums(db=DATABASE, storage_id="storage-1") == []

    lookup.answers["storage-1"] = recorded(node_id="artifact-1", checksum="a" * 32)

    assert await resolver.get_recorded_checksums(db=DATABASE, storage_id="storage-1") == recorded(
        node_id="artifact-1", checksum="a" * 32
    )
    assert lookup.calls == ["storage-1", "storage-1"]


async def test_cache_evicts_the_least_recently_used_object() -> None:
    lookup = RecordingLookup(
        answers={
            "storage-1": recorded(node_id="artifact-1", checksum="a" * 32),
            "storage-2": recorded(node_id="artifact-2", checksum="b" * 32),
        }
    )
    resolver = ArtifactChecksumResolver(lookup=lookup, cache_size=1)

    await resolver.get_recorded_checksums(db=DATABASE, storage_id="storage-1")
    await resolver.get_recorded_checksums(db=DATABASE, storage_id="storage-2")
    await resolver.get_recorded_checksums(db=DATABASE, storage_id="storage-1")

    assert lookup.calls == ["storage-1", "storage-2", "storage-1"]


class ClaimingCache:
    """Cache double honouring `not_exists`, recording every key it was asked to set or delete."""

    def __init__(self) -> None:
        self.storage: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []

    async def set(self, key: str, value: str, expires: int | None = None, not_exists: bool = False) -> bool:
        self.calls.append(("set", key))
        if not_exists and key in self.storage:
            return False
        self.storage[key] = value
        return True

    async def delete(self, key: str) -> None:
        self.calls.append(("delete", key))
        self.storage.pop(key, None)


@dataclass
class ServiceWithCache:
    cache: ClaimingCache


async def test_failed_regeneration_request_releases_its_claim() -> None:
    cache = ClaimingCache()
    service = cast("InfrahubServices", ServiceWithCache(cache=cache))
    account = AccountSession(authenticated=True, account_id="account-1", auth_type=AuthType.API)
    corrupted = recorded(node_id="artifact-1", checksum="a" * 32)
    key = "artifact_regeneration_request:main:artifact-1"

    # The branch cannot be resolved against this database, so queuing the regeneration fails.
    await request_artifact_regeneration(db=DATABASE, service=service, account=account, recorded=corrupted)
    await request_artifact_regeneration(db=DATABASE, service=service, account=account, recorded=corrupted)

    assert cache.calls == [("set", key), ("delete", key), ("set", key), ("delete", key)]
    assert cache.storage == {}


async def test_regeneration_already_claimed_is_not_requested_again() -> None:
    cache = ClaimingCache()
    key = "artifact_regeneration_request:main:artifact-1"
    cache.storage[key] = "requested"
    service = cast("InfrahubServices", ServiceWithCache(cache=cache))
    account = AccountSession(authenticated=True, account_id="account-1", auth_type=AuthType.API)

    await request_artifact_regeneration(
        db=DATABASE, service=service, account=account, recorded=recorded(node_id="artifact-1", checksum="a" * 32)
    )

    assert cache.calls == [("set", key)]
    assert cache.storage == {key: "requested"}


async def test_artifact_checks_are_never_regenerated() -> None:
    cache = ClaimingCache()
    service = cast("InfrahubServices", ServiceWithCache(cache=cache))
    account = AccountSession(authenticated=True, account_id="account-1", auth_type=AuthType.API)
    check = [
        RecordedArtifactChecksum(node_id="check-1", kind=InfrahubKind.ARTIFACTCHECK, branch="main", checksum="a" * 32)
    ]

    await request_artifact_regeneration(db=DATABASE, service=service, account=account, recorded=check)

    assert cache.calls == []
