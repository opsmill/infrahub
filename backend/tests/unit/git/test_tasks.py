import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Self
from uuid import uuid4

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.constants import RepositoryInternalStatus
from infrahub.core.registry import registry
from infrahub.git import InfrahubRepository, tasks
from infrahub.git.tasks import format_check_log_entry, resolve_initial_import_branch


@dataclass
class ImportBranchCase:
    name: str
    init_failed: bool
    reinitialized: bool
    expected: str | None


IMPORT_BRANCH_CASES = [
    # A fresh clone (init raised, recreated via new) must seed its git default branch.
    ImportBranchCase(name="freshly_created", init_failed=True, reinitialized=False, expected="production"),
    # A re-cloned local copy (local directory was missing) must seed its git default branch.
    ImportBranchCase(name="reinitialized", init_failed=False, reinitialized=True, expected="production"),
    # An already-present valid clone needs no initial import.
    ImportBranchCase(name="existing_clone", init_failed=False, reinitialized=False, expected=None),
]


@pytest.mark.parametrize("case", IMPORT_BRANCH_CASES, ids=[case.name for case in IMPORT_BRANCH_CASES])
def test_resolve_initial_import_branch_uses_git_default(
    case: ImportBranchCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The seeded branch must be the repository's git default branch, never the platform default."""
    monkeypatch.setattr(registry, "_default_branch", "main")
    # The repository's git default branch ("production") differs from Infrahub's default ("main").
    assert registry.default_branch != "production"
    repo = InfrahubRepository(
        id=uuid4(),
        name="test-repository",
        location="git@github.com:mock/test-repository.git",
        default_branch_name="production",
        has_origin=True,
        cache_repo=None,
        is_read_only=False,
        internal_status=RepositoryInternalStatus.ACTIVE.value,
        infrahub_branch_name=None,
        reinitialized=case.reinitialized,
    )

    assert resolve_initial_import_branch(repo, init_failed=case.init_failed) == case.expected


def test_format_check_log_entry_message_only() -> None:
    entry = {"level": "ERROR", "message": "boom", "branch": "main"}

    assert format_check_log_entry(entry) == "[ERROR] boom"


def test_format_check_log_entry_with_object_type_and_id() -> None:
    entry = {
        "level": "ERROR",
        "message": "Duplicate serial '12345' for manufacturer 'Acme'.",
        "branch": "main",
        "object_id": "abc-123",
        "object_type": "DcimDeviceAsset",
    }

    assert format_check_log_entry(entry) == (
        "[ERROR] Duplicate serial '12345' for manufacturer 'Acme'. (object_type=DcimDeviceAsset, object_id=abc-123)"
    )


def test_format_check_log_entry_with_object_id_only() -> None:
    entry = {
        "level": "INFO",
        "message": "validated",
        "branch": "main",
        "object_id": "abc-123",
    }

    assert format_check_log_entry(entry) == "[INFO] validated (object_id=abc-123)"


def test_format_check_log_entry_with_object_type_only() -> None:
    entry = {
        "level": "ERROR",
        "message": "missing description",
        "branch": "main",
        "object_type": "TestingCar",
    }

    assert format_check_log_entry(entry) == "[ERROR] missing description (object_type=TestingCar)"


def test_format_check_log_entry_produces_single_line_per_entry() -> None:
    """Regression: the formatter must emit exactly one line per log record."""
    entry = {
        "level": "ERROR",
        "message": "multi word message",
        "branch": "main",
        "object_id": "abc",
        "object_type": "Foo",
    }

    rendered = format_check_log_entry(entry)

    assert "\n" not in rendered
    assert rendered.count("[ERROR]") == 1


class _FakeSession:
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False


class _FakeDatabase:
    def start_session(self) -> _FakeSession:
        return _FakeSession()


class _FakeBranchManager:
    async def all(self) -> dict[str, SimpleNamespace]:
        return {"main": SimpleNamespace(id="main-branch-id")}


def _make_repository_data(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        repository=SimpleNamespace(name=SimpleNamespace(value=name)),
        branch_info={"main": SimpleNamespace(internal_status=RepositoryInternalStatus.ACTIVE.value)},
        get_staging_branch=lambda: None,
    )


async def test_sync_remote_repositories_isolates_single_repo_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """One repository failing to sync must not stop the rest of the batch from syncing.

    The recurring sync iterates every repository. When syncing one repository raises an error
    outside the RepositoryError family (here a GraphQLError from a graph update, which the sync
    path is documented to raise), the remaining repositories must still be synced rather than
    the whole run aborting at the failing repository.
    """
    monkeypatch.setattr(registry, "_default_branch", "main")
    # sync_remote_repositories may log the contained failure via the Prefect run logger; outside a
    # flow run context that helper is unavailable, so route it to a stdlib logger.
    monkeypatch.setattr(tasks, "get_run_logger", lambda: logging.getLogger("test-sync-remote-repositories"))

    async def fake_get_database() -> _FakeDatabase:
        return _FakeDatabase()

    monkeypatch.setattr(tasks, "get_database", fake_get_database)
    monkeypatch.setattr(tasks, "get_client", lambda: SimpleNamespace(branch=_FakeBranchManager()))

    repositories = {"repo-a": _make_repository_data("repo-a"), "repo-b": _make_repository_data("repo-b")}

    async def fake_get_repositories(**kwargs: object) -> dict[str, SimpleNamespace]:
        return repositories

    monkeypatch.setattr(tasks, "get_repositories_commit_per_branch", fake_get_repositories)

    async def fake_bootstrap(**kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(default_branch="main")

    monkeypatch.setattr(tasks, "bootstrap_local_repository", fake_bootstrap)

    processed: list[str] = []

    async def fake_sync(*, repository: SimpleNamespace, **kwargs: object) -> None:
        processed.append(repository.name.value)
        if repository.name.value == "repo-a":
            raise GraphQLError(errors=[{"message": "simulated graph update failure"}])

    monkeypatch.setattr(tasks, "sync_repository_from_origin", fake_sync)

    # Must complete without propagating the first repository's failure.
    await tasks.sync_remote_repositories.fn()

    assert processed == ["repo-a", "repo-b"]
