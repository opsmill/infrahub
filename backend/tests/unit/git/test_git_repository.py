import asyncio
import logging
import re
import shutil
from collections.abc import Awaitable, Callable, Iterator
from contextlib import nullcontext as does_not_raise
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pydantic
import pytest
from git import Git, PushInfo, Remote, RemoteProgress, Repo
from git.exc import GitCommandError
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.branch import BranchData
from infrahub_sdk.uuidt import UUIDT
from pydantic import Field

from infrahub import config
from infrahub.core.constants import RepositoryInternalStatus, RepositoryOperationalStatus
from infrahub.core.registry import registry
from infrahub.exceptions import (
    RepositoryConnectionError,
    RepositoryCredentialsError,
    RepositoryError,
    RepositoryInvalidBranchError,
    RepositoryNotFoundError,
    RepositoryPushRejectedError,
)
from infrahub.git import InfrahubRepository
from infrahub.git.base import BranchInRemote
from infrahub.git.divergence.models import ReconciledBranch
from infrahub.git.models import GitRepositoryAdd, GitRepositoryMerge, PushRejectionReason
from infrahub.git.repository import FailedImport, ImportStep, InfrahubReadOnlyRepository, PendingObjectImport
from infrahub.git.worktree import Worktree
from tests.helpers.file_repo import MultipleStagesFileRepo
from tests.helpers.git import LocalRemote, clone_repository, open_repository
from tests.helpers.test_client import dummy_async_request

PREFECT_LOGGER_NAME = "infrahub.git.repository"


@pytest.fixture
def patch_prefect_logger() -> Iterator[None]:
    """Replace Prefect's `get_run_logger` with a stdlib logger so calls outside a flow context succeed."""
    with patch(
        "infrahub.git.repository.get_run_logger",
        return_value=logging.getLogger(PREFECT_LOGGER_NAME),
    ):
        yield


def _build_source_with_conflicting_branches(source_dir: Path) -> None:
    """Initialize a git source repo with `main` and `change1` whose tips edit the same lines."""
    source = Repo.init(source_dir, initial_branch="main")
    with source.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")
    target = source_dir / "data.txt"
    target.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
    source.index.add(["data.txt"])
    base_commit = source.index.commit("base")

    source.git.checkout("-b", "change1")
    target.write_text("change1 version\nline 2\nline 3\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("change on change1")

    source.git.checkout("main")
    source.git.reset("--hard", base_commit.hexsha)
    target.write_text("main version\nline 2\nline 3\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("change on main")


async def _build_repository_with_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, name: str = "conflicting-repo"
) -> InfrahubRepository:
    """Build an `InfrahubRepository` whose remote has `main` and a divergent `change1`.

    Raises:
        RuntimeError: When the constructed source repo no longer produces a conflict between `main` and `change1`.

    """
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()
    _build_source_with_conflicting_branches(source_dir)

    repository = await clone_repository(
        id=UUIDT.new(),
        name=name,
        location=str(source_dir),
        default_branch="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )
    if not repository.has_conflicting_changes(target_branch="main", source_branch="change1"):
        raise RuntimeError(
            "test helper drift: main and change1 must conflict for the conflict-import tests to be meaningful"
        )
    return repository


async def test_create_branch_in_git_with_conflicting_remote_lands_at_remote_tip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A remote branch that conflicts with the default branch must still be imported locally.

    The local branch should land at the remote tip so that downstream merge attempts can
    surface the conflict at merge time, rather than aborting the entire import.
    """
    repository = await _build_repository_with_conflict(tmp_path, monkeypatch)

    remote_branches = repository.get_branches_from_remote()
    expected_commit = remote_branches["change1"].commit

    await repository.create_branch_in_git(branch_name="change1", branch_id=str(UUIDT.new()))

    local_branches = repository.get_branches_from_local(include_worktree=False)
    assert "change1" in local_branches
    assert local_branches["change1"].commit == expected_commit


async def test_validate_remote_branch_allows_conflicting_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    patch_prefect_logger: None,
) -> None:
    """validate_remote_branch must accept a branch that conflicts with the default branch.

    Skipping the branch would prevent it from being imported. The conflict is surfaced at
    merge time instead.
    """
    repository = await _build_repository_with_conflict(tmp_path, monkeypatch)
    assert repository.validate_remote_branch(branch_name="change1") is True


async def test_has_conflicting_changes_no_false_positive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """has_conflicting_changes() must not flag a diff that only adds lines containing '======='."""
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    sources_dir = tmp_path / "source"
    sources_dir.mkdir()

    test_repo = MultipleStagesFileRepo(name="false-positive-conflicts", sources_directory=sources_dir)
    repository = await clone_repository(
        id=UUIDT.new(),
        name=test_repo.name,
        location=test_repo.path,
        default_branch="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    # Confirm the diff between the branches actually contains ======= to validate the test premise
    diff = test_repo.repo.git.diff("main", "change1")
    assert "=======" in diff

    # The branch adds a file containing ======= but has no actual conflicts with main
    assert not repository.has_conflicting_changes(target_branch="main", source_branch="change1")


async def test_init_repoints_origin_after_location_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reinitializing a repository after its location changed must re-point the cached clone's origin.

    When the location is updated to a remote that has advanced, opening the existing clone and fetching
    must surface the new remote's commit, not the commit baked in at the original clone location.
    """
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    # Remote A: the original location, main at commit 1.
    source_a = tmp_path / "source-a"
    source_a.mkdir()
    repo_a = Repo.init(source_a, initial_branch="main")
    with repo_a.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")
    (source_a / "data.txt").write_text("v1\n", encoding="utf-8")
    repo_a.index.add(["data.txt"])
    commit_a = repo_a.index.commit("commit 1").hexsha

    repo_id = str(UUIDT.new())
    client = InfrahubClient(config=Config(requester=dummy_async_request))
    repository = await clone_repository(
        id=repo_id,
        name="relocating-repo",
        location=str(source_a),
        default_branch="main",
        client=client,
    )
    assert repository.get_branches_from_remote()["main"].commit == commit_a

    # Remote B: the new location, a clone of A that has advanced with commit 2.
    source_b = tmp_path / "source-b"
    repo_b = repo_a.clone(str(source_b))
    with repo_b.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")
    (source_b / "data.txt").write_text("v2\n", encoding="utf-8")
    repo_b.index.add(["data.txt"])
    commit_b = repo_b.index.commit("commit 2").hexsha

    # Re-open the existing clone with the new location, as the periodic sync does after a location
    # change. Opening it must re-point origin and fetch on its own -- no explicit fetch here.
    relocated = await open_repository(
        id=repo_id,
        name="relocating-repo",
        location=str(source_b),
        default_branch="main",
        client=client,
    )

    assert relocated.get_git_repo_main().remotes.origin.url == str(source_b)
    assert relocated.get_branches_from_remote()["main"].commit == commit_b


async def test_pull_infrahub_default_branch_pulls_repository_default_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pulling the Infrahub default branch must pull the repository's own default branch.

    When the two differ, the remote has no branch named after the Infrahub default branch,
    so pulling the unmapped name fails and flips the repository into an error state.
    """
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()
    source = Repo.init(source_dir, initial_branch="production")
    with source.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")
    (source_dir / "data.txt").write_text("v1\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("commit 1")

    repository = await clone_repository(
        id=UUIDT.new(),
        name="production-default-repo",
        location=str(source_dir),
        default_branch="production",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    (source_dir / "data.txt").write_text("v2\n", encoding="utf-8")
    source.index.add(["data.txt"])
    new_commit = source.index.commit("commit 2").hexsha

    commit_after = await repository.pull(branch_name="main", update_commit_value=False)
    assert commit_after == new_commit


def _init_source_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the repositories directory into `tmp_path` and create a one-commit source repository on `main`."""
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))
    monkeypatch.setattr(registry, "_default_branch", "main")

    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()
    source = Repo.init(source_dir, initial_branch="main")
    with source.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")
    (source_dir / "data.txt").write_text("v1\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("commit 1")
    return source_dir


@dataclass
class _CloneSpy:
    """Counts clone attempts and records, for each failed one, whether it left a local copy behind."""

    attempts: int = 0
    failed_attempts_left_a_copy: list[bool] = field(default_factory=list)

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        create_locally = InfrahubRepository.create_locally

        async def spying_create_locally(repository: InfrahubRepository, *args: Any, **kwargs: Any) -> bool:
            self.attempts += 1
            # Hand control back to the event loop so concurrent initializations actually interleave.
            await asyncio.sleep(0)
            try:
                return await create_locally(repository, *args, **kwargs)
            except RepositoryError:
                self.failed_attempts_left_a_copy.append(repository.directory_default.is_dir())
                raise

        monkeypatch.setattr(InfrahubRepository, "create_locally", spying_create_locally)


async def test_concurrent_init_clones_the_missing_directory_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent initializations of an absent clone must produce exactly one clone.

    Cloning deletes whatever is on disk first, so a second clone running alongside would wipe the
    directory the first one just built and invalidate the git objects opened against it.
    """
    source_dir = _init_source_repository(tmp_path=tmp_path, monkeypatch=monkeypatch)
    clones = _CloneSpy()
    clones.install(monkeypatch=monkeypatch)

    init_kwargs: dict[str, Any] = {
        "id": UUIDT.new(),
        "name": "concurrently-initialized-repo",
        "location": str(source_dir),
        "default_branch": "main",
        "client": InfrahubClient(config=Config(requester=dummy_async_request)),
    }
    first, second = await asyncio.gather(
        open_repository(**init_kwargs),
        open_repository(**init_kwargs),
    )

    assert clones.attempts == 1
    assert [first.reinitialized, second.reinitialized].count(True) == 1
    for repository in (first, second):
        assert repository.validate_local_directories()


async def test_concurrent_init_clones_over_the_copy_a_failed_clone_left(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An initialization waiting on a concurrent clone that fails part-way must clone over what it left.

    The failed clone leaves a copy on disk that no longer validates; rejecting that copy would fail the
    waiting initialization along with the one that actually broke.
    """
    source_dir = _init_source_repository(tmp_path=tmp_path, monkeypatch=monkeypatch)
    clones = _CloneSpy()
    clones.install(monkeypatch=monkeypatch)

    shared_kwargs: dict[str, Any] = {
        "id": UUIDT.new(),
        "name": "concurrently-initialized-repo",
        "location": str(source_dir),
        "client": InfrahubClient(config=Config(requester=dummy_async_request)),
    }
    # The first clone succeeds, but checking out a branch the remote lacks fails and leaves it half-built.
    failed, waiting = await asyncio.gather(
        open_repository(**shared_kwargs, default_branch="missing-branch"),
        open_repository(**shared_kwargs, default_branch="main"),
        return_exceptions=True,
    )

    assert isinstance(failed, RepositoryInvalidBranchError)
    assert clones.failed_attempts_left_a_copy == [True]
    assert isinstance(waiting, InfrahubRepository)
    assert waiting.reinitialized is True
    assert waiting.validate_local_directories()
    assert clones.attempts == 2


class RecordingGraphqlClient(InfrahubClient):
    """An SDK client that records the branch of every GraphQL call instead of sending it."""

    def __init__(self) -> None:
        super().__init__(config=Config(requester=dummy_async_request))
        self.recorded_branches: list[str | None] = []

    async def execute_graphql(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.recorded_branches.append(kwargs.get("branch_name"))
        return {}


def build_read_write(default_branch: str) -> InfrahubRepository:
    """A read-write repository object with no local clone, for the pure mapping assertions below."""
    return InfrahubRepository(
        id=UUID(str(UUIDT.new())),
        name="mapping-repo",
        location="git@github.com:mock/mapping-repo.git",
        default_branch=default_branch,
        internal_status=RepositoryInternalStatus.ACTIVE,
        infrahub_branch_name="main",
    )


def build_read_only(ref: str) -> InfrahubReadOnlyRepository:
    return InfrahubReadOnlyRepository(
        id=UUID(str(UUIDT.new())),
        name="mapping-read-only-repo",
        location="git@github.com:mock/mapping-repo.git",
        ref=ref,
        infrahub_branch_name="main",
    )


@dataclass
class MappingCase:
    name: str
    branch_name: str
    expected_remote: str
    expected_target: str
    expected_worktree: str


MAPPING_CASES = [
    MappingCase(
        name="infrahub_default_maps_onto_the_trunk",
        branch_name="main",
        expected_remote="develop",
        expected_target="main",
        expected_worktree="main",
    ),
    MappingCase(
        name="trunk_maps_back_onto_the_infrahub_default",
        branch_name="develop",
        expected_remote="develop",
        expected_target="main",
        expected_worktree="main",
    ),
    MappingCase(
        name="any_other_branch_is_unchanged",
        branch_name="feature-1",
        expected_remote="feature-1",
        expected_target="feature-1",
        expected_worktree="feature-1",
    ),
]


@pytest.mark.parametrize("case", MAPPING_CASES, ids=[case.name for case in MAPPING_CASES])
def test_read_write_branch_mapping(case: MappingCase, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_default_branch", "main")
    repository = build_read_write(default_branch="develop")

    assert repository._get_mapped_remote_branch(branch_name=case.branch_name) == case.expected_remote
    assert repository._get_mapped_target_branch(branch_name=case.branch_name) == case.expected_target
    assert repository._resolve_worktree_identifier(branch_name=case.branch_name) == case.expected_worktree


@pytest.mark.parametrize("branch_name", ["main", "develop", "feature-1"])
def test_read_only_branch_mapping_is_identity(branch_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A read-only repository tracks one ref and maps no branch names."""
    monkeypatch.setattr(registry, "_default_branch", "main")
    repository = build_read_only(ref="develop")

    assert repository._get_mapped_remote_branch(branch_name=branch_name) == branch_name
    assert repository._get_mapped_target_branch(branch_name=branch_name) == branch_name
    assert repository._resolve_worktree_identifier(branch_name=branch_name) == branch_name


def test_worktree_identifier_when_remote_has_a_literal_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """The trunk's worktree is stored under `main`, which a remote branch literally named `main` shares.

    Documents the collision rather than fixing it: both resolve to the same on-disk identifier.
    """
    monkeypatch.setattr(registry, "_default_branch", "production")
    repository = build_read_write(default_branch="develop")

    assert repository._resolve_worktree_identifier(branch_name="develop") == "main"
    assert repository._resolve_worktree_identifier(branch_name="main") == "main"


@dataclass
class MissingFieldCase:
    name: str
    fields: dict[str, Any]
    missing: str


MISSING_FIELD_CASES = [
    MissingFieldCase(
        name="without_default_branch",
        fields={"name": "no-trunk-repo", "internal_status": RepositoryInternalStatus.ACTIVE},
        missing="default_branch",
    ),
    MissingFieldCase(
        name="without_internal_status",
        fields={"name": "no-status-repo", "default_branch": "develop"},
        missing="internal_status",
    ),
]


@pytest.mark.parametrize("case", MISSING_FIELD_CASES, ids=[case.name for case in MISSING_FIELD_CASES])
def test_read_write_construction_rejects_a_missing_field(case: MissingFieldCase) -> None:
    """Both values are required at construction, which is what makes the broken state unreachable.

    The fields are passed as a mapping so the omission is a runtime one, which is what is under test.
    """
    with pytest.raises(pydantic.ValidationError, match=case.missing):
        InfrahubRepository(id=UUID(str(UUIDT.new())), **case.fields)


def test_read_only_repository_has_no_trunk() -> None:
    """The base model drops an unknown keyword rather than rejecting it, so assert on the instance."""
    fields: dict[str, Any] = {"name": "read-only-repo", "ref": "develop", "default_branch": "develop"}
    repository = InfrahubReadOnlyRepository(id=UUID(str(UUIDT.new())), **fields)

    assert not hasattr(repository, "default_branch")


def test_message_models_no_longer_carry_a_trunk() -> None:
    assert "default_branch_name" not in GitRepositoryAdd.model_fields
    assert "default_branch" not in GitRepositoryMerge.model_fields


def test_a_merge_queued_by_an_older_version_still_loads() -> None:
    """Prefect stores the parameters of a queued run, and validates them again when the run starts."""
    model = GitRepositoryMerge.model_validate(
        {
            "repository_id": "repository-id",
            "repository_name": "network-repo",
            "internal_status": RepositoryInternalStatus.ACTIVE.value,
            "source_branch": "feature",
            "destination_branch": "main",
            "destination_branch_id": "main-id",
            "repository_kind": "CoreRepository",
        }
    )

    assert model.source_commit is None


async def test_read_only_fetch_failure_keeps_its_classified_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read-only repository whose remote disappears still raises a classified error.

    The failure path asks for no branch name, which the read-only kind cannot supply.
    """
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()
    source = Repo.init(source_dir, initial_branch="main")
    with source.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")
    (source_dir / "data.txt").write_text("v1\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("commit 1")

    repository = await InfrahubReadOnlyRepository.new(
        id=UUIDT.new(),
        name="vanishing-read-only-repo",
        location=str(source_dir),
        ref="main",
        infrahub_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    shutil.rmtree(source_dir)

    with pytest.raises(RepositoryError) as raised:
        await repository.fetch()

    assert isinstance(raised.value.__cause__, GitCommandError)


async def test_update_operational_status_writes_on_the_branch_the_object_was_resolved_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The status mutation names the branch the repository object carries, not the platform default."""
    monkeypatch.setattr(registry, "_default_branch", "main")
    repository = build_read_write(default_branch="develop")
    repository.infrahub_branch_name = "feature-branch"
    recorder = RecordingGraphqlClient()
    repository.client = recorder

    await repository._update_operational_status(status=RepositoryOperationalStatus.ONLINE)

    assert recorder.recorded_branches == ["feature-branch"]


class _ScriptedOrigin:
    """Stand-in for GitPython's `origin` remote whose push replays a scripted outcome.

    The push hands ``stderr_lines`` to the progress handler it receives, as GitPython does with Git's
    stderr, then raises ``error`` when one is set and returns ``push_infos`` otherwise. It records the
    ``kill_after_timeout`` of every call.
    """

    def __init__(
        self,
        stderr_lines: list[str] | None = None,
        push_infos: list[PushInfo] | None = None,
        error: GitCommandError | None = None,
    ) -> None:
        self.stderr_lines = stderr_lines or []
        self.push_infos = push_infos or []
        self.error = error
        self.kill_after_timeouts: list[float | None] = []

    def push(self, refspec: str, progress: RemoteProgress, kill_after_timeout: float | None) -> list[PushInfo]:
        self.kill_after_timeouts.append(kill_after_timeout)
        handle_line = progress.new_message_handler()
        for line in self.stderr_lines:
            handle_line(line)
        if self.error is not None:
            raise self.error
        return self.push_infos


class _ScriptedPushRepository(InfrahubRepository):
    """An InfrahubRepository whose worktree pushes through a scripted origin.

    Records every operational status write so the test can assert a failed push leaves the recorded
    status untouched. The double keeps it in memory; it does not persist.
    """

    origin: _ScriptedOrigin
    recorded_statuses: list[RepositoryOperationalStatus] = Field(default_factory=list)

    def get_git_repo_worktree(self, identifier: str) -> Any:
        return SimpleNamespace(remotes=SimpleNamespace(origin=self.origin))

    async def _update_operational_status(self, status: RepositoryOperationalStatus) -> None:
        self.recorded_statuses.append(status)


def build_scripted_push_repository(origin: _ScriptedOrigin) -> _ScriptedPushRepository:
    return _ScriptedPushRepository(
        id=UUIDT.new(),
        name="push-repo",
        default_branch="main",
        location="https://gitlab.example.com/net/repo.git",
        has_origin=True,
        internal_status=RepositoryInternalStatus.ACTIVE,
        infrahub_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
        origin=origin,
    )


@dataclass
class PushErrorCase:
    name: str
    stderr: str
    expected: type[RepositoryError]
    message: str | None = None


@pytest.mark.parametrize(
    "case",
    [
        PushErrorCase(
            name="credentials",
            stderr="fatal: Authentication failed for 'https://gitlab.example.com/net/repo.git/'",
            expected=RepositoryCredentialsError,
        ),
        PushErrorCase(
            name="connection",
            stderr="fatal: unable to access 'https://gitlab.example.com/net/repo.git/': "
            "Could not resolve host: gitlab.example.com",
            expected=RepositoryConnectionError,
        ),
        PushErrorCase(
            name="past_its_time_limit",
            stderr="error: process killed because it timed out. kill_after_timeout=300 seconds",
            expected=RepositoryConnectionError,
            message=(
                "The Git command for repository push-repo did not complete within its time limit, "
                "please check that the remote is reachable."
            ),
        ),
        PushErrorCase(
            name="repository_not_found",
            stderr="fatal: repository 'https://gitlab.example.com/net/repo.git/' not found",
            expected=RepositoryNotFoundError,
        ),
    ],
    ids=lambda c: c.name,
)
async def test_push_classifies_transport_error(case: PushErrorCase) -> None:
    """A transport-level push GitCommandError is classified into a typed RepositoryError without writing status."""
    repository = build_scripted_push_repository(
        origin=_ScriptedOrigin(error=GitCommandError(command=["git", "push"], status=128, stderr=case.stderr))
    )

    with pytest.raises(case.expected) as raised:
        await repository.push("main")

    assert type(raised.value) is case.expected
    if case.message is not None:
        assert raised.value.message == case.message
    assert repository.recorded_statuses == []


@dataclass
class PushRejectionCase:
    name: str
    flags: int
    summary: str
    stderr_lines: list[str]
    reason: PushRejectionReason
    remote_message: str
    message: str


PUSH_REJECTION_CASES = [
    PushRejectionCase(
        # A GitHub ruleset summary matches no wording of the message, so only the flags give the reason.
        name="github_ruleset",
        flags=PushInfo.ERROR | PushInfo.REMOTE_REJECTED,
        summary="[remote rejected] (push declined due to repository rule violations)\n",
        stderr_lines=[
            "Enumerating objects: 5, done.",
            "Counting objects: 100% (5/5), done.",
            "Writing objects: 100% (3/3), 290 bytes | 290.00 KiB/s, done.",
            "Total 3 (delta 1), reused 0 (delta 0), pack-reused 0 (from 0)",
            "remote: Resolving deltas: 100% (1/1), completed with 1 local object.",
            "remote: error: GH013: Repository rule violations found for refs/heads/main.        ",
            "remote: Review all repository rules at https://github.com/opsmill/net-repo/rules?ref=refs%2Fheads%2Fmain",
            "remote: ",
            "remote: - Changes must be made through a pull request.",
            "To https://github.com/opsmill/net-repo.git",
            "error: failed to push some refs to 'https://github.com/opsmill/net-repo.git'",
        ],
        reason=PushRejectionReason.POLICY,
        remote_message=(
            "remote: error: GH013: Repository rule violations found for refs/heads/main.\n"
            "remote: Review all repository rules at https://github.com/opsmill/net-repo/rules?ref=refs%2Fheads%2Fmain\n"
            "remote:\n"
            "remote: - Changes must be made through a pull request."
        ),
        message=(
            "Unable to push the branch main to the remote for repository push-repo: "
            "[remote rejected] (push declined due to repository rule violations)"
        ),
    ),
    PushRejectionCase(
        name="remote_failure",
        flags=PushInfo.ERROR | PushInfo.REMOTE_FAILURE,
        summary="[remote failure] (remote failed to report status)\n",
        stderr_lines=[
            "remote: fatal: Out of memory, malloc failed (tried to allocate 1048576 bytes)",
            "error: failed to push some refs to 'https://gitlab.example.com/net/repo.git'",
        ],
        reason=PushRejectionReason.UNKNOWN,
        remote_message="remote: fatal: Out of memory, malloc failed (tried to allocate 1048576 bytes)",
        message=(
            "Unable to push the branch main to the remote for repository push-repo: "
            "[remote failure] (remote failed to report status)"
        ),
    ),
]


@pytest.mark.parametrize("case", PUSH_REJECTION_CASES, ids=lambda c: c.name)
async def test_push_rejection_carries_the_reason_and_the_remote_lines(case: PushRejectionCase, tmp_path: Path) -> None:
    """A rejected ref raises a typed error with its reason from the flags and the remote's lines, and writes no status."""
    remote = Remote(repo=Repo.init(tmp_path / "local"), name="origin")
    push_info = PushInfo(
        flags=case.flags, local_ref=None, remote_ref_string="refs/heads/main", remote=remote, summary=case.summary
    )
    repository = build_scripted_push_repository(
        origin=_ScriptedOrigin(stderr_lines=case.stderr_lines, push_infos=[push_info])
    )

    with pytest.raises(RepositoryPushRejectedError, match=rf"^{re.escape(case.message)}$") as raised:
        await repository.push("main")

    assert raised.value.reason == case.reason
    assert raised.value.remote_message == case.remote_message
    assert repository.recorded_statuses == []


def _decline_in_a_pre_receive_hook(remote_directory: Path, source_directory: Path) -> None:
    hooks_directory = remote_directory / "test-hooks"
    hooks_directory.mkdir()
    hook = hooks_directory / "pre-receive"
    hook.write_text(
        "#!/bin/sh\necho 'branch main is protected' >&2\necho 'error: 2 commits are not signed' >&2\nexit 1\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    # Set in the remote's own configuration, which wins over any hooks path of the host's Git configuration.
    with Repo(remote_directory).config_writer() as cfg:
        cfg.set_value("core", "hooksPath", str(hooks_directory))


def _advance_the_remote(remote_directory: Path, source_directory: Path) -> None:
    source = Repo(source_directory)
    (source_directory / "data.txt").write_text("v2\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("commit 2")
    Repo(remote_directory).git.fetch(str(source_directory), "main:main")


@dataclass
class RealPushRejectionCase:
    name: str
    refuse: Callable[[Path, Path], None]
    """Makes the remote refuse the next push to main, given the remote and the source it was cloned from."""
    reason: PushRejectionReason
    remote_message: str
    message: str


@pytest.mark.parametrize(
    "case",
    [
        RealPushRejectionCase(
            name="pre_receive_hook_declines",
            refuse=_decline_in_a_pre_receive_hook,
            reason=PushRejectionReason.POLICY,
            # The second line has the shape of a progress line, which the base progress handler drops.
            remote_message="remote: branch main is protected\nremote: error: 2 commits are not signed",
            message=(
                "Unable to push the branch main to the remote for repository push-repo: the remote refused the "
                "update (for example missing push permission or branch protection): "
                "[remote rejected] (pre-receive hook declined)"
            ),
        ),
        RealPushRejectionCase(
            name="remote_has_new_commits",
            refuse=_advance_the_remote,
            reason=PushRejectionReason.NON_FAST_FORWARD,
            remote_message="",
            message=(
                "Unable to push the branch main to the remote for repository push-repo: the remote branch has "
                "commits that are missing locally (non-fast-forward): [rejected] (fetch first)"
            ),
        ),
    ],
    ids=lambda c: c.name,
)
async def test_push_refused_by_a_git_remote_carries_the_reason_and_the_remote_lines(
    case: RealPushRejectionCase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A push that a real Git remote refuses gives the reason and the remote's lines that Git itself reports."""
    source_directory = _init_source_repository(tmp_path=tmp_path, monkeypatch=monkeypatch)
    remote_directory = tmp_path / "remote.git"
    Repo(source_directory).clone(str(remote_directory), bare=True)
    repository = await clone_repository(
        id=UUIDT.new(),
        name="push-repo",
        location=str(remote_directory),
        default_branch="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )
    case.refuse(remote_directory, source_directory)
    local = repository.get_git_repo_main()
    (Path(str(local.working_dir)) / "local.txt").write_text("local\n", encoding="utf-8")
    local.index.add(["local.txt"])
    local.index.commit("local change")
    recorder = RecordingGraphqlClient()
    repository.client = recorder

    with pytest.raises(RepositoryPushRejectedError, match=rf"^{re.escape(case.message)}$") as raised:
        await repository.push("main")

    assert raised.value.reason == case.reason
    assert raised.value.remote_message == case.remote_message
    # The status write is a GraphQL call, so no call at all means no status was written.
    assert recorder.recorded_branches == []


@dataclass
class PushTimeoutCase:
    name: str
    push_kwargs: dict[str, float]
    kill_after_timeout: float | None


@pytest.mark.parametrize(
    "case",
    [
        PushTimeoutCase(name="no_time_limit_by_default", push_kwargs={}, kill_after_timeout=None),
        PushTimeoutCase(name="time_limit_passed_to_git", push_kwargs={"timeout_seconds": 300}, kill_after_timeout=300),
    ],
    ids=lambda c: c.name,
)
async def test_push_passes_its_timeout_to_git(case: PushTimeoutCase) -> None:
    origin = _ScriptedOrigin()
    repository = build_scripted_push_repository(origin=origin)

    assert await repository.push("main", **case.push_kwargs) is True

    assert origin.kill_after_timeouts == [case.kill_after_timeout]


class _GitWrappedRepository(InfrahubRepository):
    """An InfrahubRepository whose main clone runs every Git command through the wrapper that the test sets."""

    git_wrapper: Callable[[str], Git]

    def get_git_repo_main(self) -> Repo:
        repo = super().get_git_repo_main()
        repo.git = self.git_wrapper(str(repo.working_dir))
        return repo


async def clone_with_git_wrapper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_wrapper: Callable[[str], Git]
) -> _GitWrappedRepository:
    """Clone a local remote that has a `feature` branch, then open the clone with the given Git wrapper."""
    source_directory = _init_source_repository(tmp_path=tmp_path, monkeypatch=monkeypatch)
    source = Repo(source_directory)
    source.git.checkout("-b", "feature")
    (source_directory / "feature.txt").write_text("feature\n", encoding="utf-8")
    source.index.add(["feature.txt"])
    source.index.commit("feature commit")
    source.git.checkout("main")
    remote_directory = tmp_path / "remote.git"
    source.clone(str(remote_directory), bare=True)
    clone = await clone_repository(
        id=UUIDT.new(),
        name="local-repo",
        location=str(remote_directory),
        default_branch="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )
    return _GitWrappedRepository(
        id=clone.id,
        name=clone.name,
        location=clone.location,
        default_branch="main",
        has_origin=True,
        internal_status=RepositoryInternalStatus.ACTIVE,
        infrahub_branch_name="main",
        client=clone.client,
        git_wrapper=git_wrapper,
    )


class _TimeLimitGit(Git):
    """Fails every Git command as GitPython does when its watchdog stops a command at its time limit."""

    def execute(self, command: Any, *args: Any, **kwargs: Any) -> Any:
        quoted = " ".join(str(part) for part in command)
        raise GitCommandError(
            command, -9, f'Timeout: the command "{quoted}" did not complete in {kwargs["kill_after_timeout"]:g} secs.'
        )


async def test_create_commit_worktree_reports_a_worktree_listing_past_its_time_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `git worktree list` past its time limit raises a RepositoryError that names no argument or worker path."""
    repository = await clone_with_git_wrapper(tmp_path=tmp_path, monkeypatch=monkeypatch, git_wrapper=_TimeLimitGit)

    with pytest.raises(
        RepositoryError,
        match=r"^The command git worktree for repository local-repo did not complete within 7 seconds\.$",
    ) as raised:
        repository.create_commit_worktree(commit="abc", timeout_seconds=7)

    assert type(raised.value) is RepositoryError


async def clone_with_a_slow_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[InfrahubRepository, str]:
    """Clone a local remote, and return a commit whose checkout runs a smudge filter that waits one second."""
    source_directory = _init_source_repository(tmp_path=tmp_path, monkeypatch=monkeypatch)
    source = Repo(source_directory)
    source.git.checkout("-b", "slow")
    (source_directory / ".gitattributes").write_text("slow.txt filter=slow\n", encoding="utf-8")
    (source_directory / "slow.txt").write_text("slow\n", encoding="utf-8")
    source.index.add([".gitattributes", "slow.txt"])
    commit = source.index.commit("slow checkout").hexsha
    source.git.checkout("main")
    remote_directory = tmp_path / "remote.git"
    source.clone(str(remote_directory), bare=True)
    repository = await clone_repository(
        id=UUIDT.new(),
        name="local-repo",
        location=str(remote_directory),
        default_branch="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )
    with repository.get_git_repo_main().config_writer() as git_config:
        git_config.set_value('filter "slow"', "smudge", "sleep 1; cat")
        git_config.set_value('filter "slow"', "clean", "cat")
    return repository, commit


async def test_create_commit_worktree_removes_an_add_past_its_time_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `git worktree add` stopped at its time limit leaves no locked worktree, so the next call creates it."""
    repository, commit = await clone_with_a_slow_checkout(tmp_path=tmp_path, monkeypatch=monkeypatch)

    with pytest.raises(
        RepositoryError,
        match=r"^The command git worktree for repository local-repo did not complete within 0\.3 seconds\.$",
    ):
        repository.create_commit_worktree(commit=commit, timeout_seconds=0.3)

    worktree = repository.create_commit_worktree(commit=commit)

    assert isinstance(worktree, Worktree)
    assert (worktree.directory / "slow.txt").read_text(encoding="utf-8") == "slow\n"


class _WorktreeCheckMissesRepository(InfrahubRepository):
    """An InfrahubRepository whose worktree check misses every worktree, as when another process adds one in between."""

    def has_worktree(self, identifier: str, timeout_seconds: float | None = None) -> bool:
        return False


async def test_create_commit_worktree_keeps_a_worktree_that_already_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `git worktree add` that fails for a reason other than its time limit removes no worktree."""
    repository, commit = await clone_with_a_slow_checkout(tmp_path=tmp_path, monkeypatch=monkeypatch)
    worktree = repository.create_commit_worktree(commit=commit)
    assert isinstance(worktree, Worktree)
    racing_repository = _WorktreeCheckMissesRepository(
        id=repository.id,
        name=repository.name,
        location=repository.location,
        default_branch="main",
        has_origin=True,
        internal_status=RepositoryInternalStatus.ACTIVE,
        infrahub_branch_name="main",
        client=repository.client,
    )

    with pytest.raises(RepositoryError, match="already exists"):
        racing_repository.create_commit_worktree(commit=commit, timeout_seconds=7)

    assert repository.has_worktree(identifier=commit) is True
    assert (worktree.directory / "slow.txt").read_text(encoding="utf-8") == "slow\n"


TIME_LIMIT_SECONDS = 7.0


class _RecordingGit(Git):
    """Runs every Git command for real and keeps its subcommand with the time limit it received."""

    def __init__(self, working_dir: str | None, calls: list[tuple[str, float | None]]) -> None:
        super().__init__(working_dir)
        self.calls = calls

    def execute(self, command: Any, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((command[1], kwargs.get("kill_after_timeout")))
        return super().execute(command, *args, **kwargs)


async def _check_for_a_worktree(repository: _GitWrappedRepository) -> None:
    repository.has_worktree(identifier="feature", timeout_seconds=TIME_LIMIT_SECONDS)


async def _list_the_worktrees(repository: _GitWrappedRepository) -> None:
    repository.get_worktrees(timeout_seconds=TIME_LIMIT_SECONDS)


async def _create_a_commit_worktree(repository: _GitWrappedRepository) -> None:
    commit = Repo(repository.directory_default).commit("origin/feature").hexsha
    repository.create_commit_worktree(commit=commit, timeout_seconds=TIME_LIMIT_SECONDS)


async def _delete_the_remote_branch(repository: _GitWrappedRepository) -> None:
    await repository.delete_remote_branch(branch_name="feature", timeout_seconds=TIME_LIMIT_SECONDS)


async def _reset_the_main_clone(repository: _GitWrappedRepository) -> None:
    clone = repository.get_git_repo_main()
    repository._reset_to_pre_merge_commit(
        repo=clone, dest_branch="main", commit_before=clone.head.commit.hexsha, timeout_seconds=TIME_LIMIT_SECONDS
    )


@dataclass
class TimeLimitForwardingCase:
    name: str
    run: Callable[[_GitWrappedRepository], Awaitable[None]]
    git_commands: list[str]


@pytest.mark.parametrize(
    "case",
    [
        TimeLimitForwardingCase(name="has_worktree", run=_check_for_a_worktree, git_commands=["worktree"]),
        TimeLimitForwardingCase(name="get_worktrees", run=_list_the_worktrees, git_commands=["worktree"]),
        TimeLimitForwardingCase(
            name="create_commit_worktree", run=_create_a_commit_worktree, git_commands=["worktree", "worktree"]
        ),
        TimeLimitForwardingCase(name="delete_remote_branch", run=_delete_the_remote_branch, git_commands=["push"]),
        TimeLimitForwardingCase(name="reset_to_pre_merge_commit", run=_reset_the_main_clone, git_commands=["reset"]),
    ],
    ids=lambda c: c.name,
)
async def test_each_git_command_receives_the_time_limit_of_the_call(
    case: TimeLimitForwardingCase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, float | None]] = []
    repository = await clone_with_git_wrapper(
        tmp_path=tmp_path, monkeypatch=monkeypatch, git_wrapper=partial(_RecordingGit, calls=calls)
    )
    calls.clear()

    await case.run(repository)

    assert calls == [(command, TIME_LIMIT_SECONDS) for command in case.git_commands]


class _BranchSyncRepository(InfrahubRepository):
    """Stubs every collaborator of the collection loop with an in-memory result.

    One new branch's git push raises a connection error; the other succeeds. ``git_pushed_branches``
    holds the branches whose push succeeded.
    """

    connection_error_branch: str
    git_pushed_branches: list[str] = Field(default_factory=list)

    async def fetch(self, timeout_seconds: float | None = None) -> bool:
        return True

    async def compare_local_remote(self) -> tuple[list[str], list[str]]:
        return (["branch01", "branch02"], [])

    def get_branches_from_remote(self) -> dict[str, BranchInRemote]:
        return {}

    def _exclude_read_only_branches(
        self, new_branches: list[str], updated_branches: list[str], graph_branches: dict[str, BranchData]
    ) -> tuple[list[str], list[str]]:
        return (new_branches, updated_branches)

    def validate_remote_branch(self, branch_name: str) -> bool:
        return True

    def _get_mapped_target_branch(self, branch_name: str) -> str:
        return branch_name

    async def create_branch_in_graph(self, branch_name: str) -> BranchData:
        return BranchData(
            id=f"{branch_name}-id",
            name=branch_name,
            description=None,
            sync_with_git=True,
            is_default=False,
            has_schema_changes=False,
            graph_version=1,
            status="OPEN",
            origin_branch="main",
            branched_from="2024-01-01",
        )

    async def create_branch_in_git(
        self, branch_name: str, branch_id: str | None = None, push_origin: bool = True
    ) -> bool:
        if branch_name == self.connection_error_branch:
            raise RepositoryConnectionError(identifier=self.name)
        self.git_pushed_branches.append(branch_name)
        return True

    def get_commit_value(self, branch_name: str, remote: bool = False) -> str:
        return f"commit-{branch_name}"

    def create_commit_worktree(self, commit: str, timeout_seconds: float | None = None) -> bool:
        return True

    async def update_commit_value(self, branch_name: str, commit: str) -> bool:
        return True


async def test_collect_pending_imports_isolates_per_branch_push_failure() -> None:
    """A connection failure while pushing one new branch is recorded, not raised over the others."""
    repository = _BranchSyncRepository(
        id=UUIDT.new(),
        name="sync-repo",
        default_branch="main",
        location="https://gitlab.example.com/net/repo.git",
        has_origin=True,
        cache_repo=None,
        is_read_only=False,
        internal_status=RepositoryInternalStatus.ACTIVE,
        reinitialized=False,
        infrahub_branch_name="main",
        client=BranchListingClient(),
        connection_error_branch="branch01",
    )

    collected = await repository.collect_pending_imports()

    assert collected.imports == [
        PendingObjectImport(
            infrahub_branch_name="branch02",
            commit="commit-branch02",
            reconciled=ReconciledBranch(
                infrahub_branch_name="branch02", infrahub_branch_id="branch02-id", commit="commit-branch02"
            ),
        )
    ]
    assert collected.failed_imports == [
        FailedImport(
            branch_name="branch01",
            step=ImportStep.COLLECTION,
            reason=str(RepositoryConnectionError(identifier="sync-repo")),
        )
    ]
    assert repository.git_pushed_branches == ["branch02"]


@pytest.fixture
def stub_repo() -> InfrahubRepository:
    return InfrahubRepository(
        id=UUID(str(UUIDT.new())),
        name="test-repo",
        default_branch="main",
        internal_status=RepositoryInternalStatus.ACTIVE,
        infrahub_branch_name="main",
    )


@dataclass
class RaiseBranchesCase:
    name: str
    failed_imports: list[FailedImport]
    expectation: Any


@pytest.mark.parametrize(
    "case",
    [
        RaiseBranchesCase(
            name="empty_list_does_not_raise",
            failed_imports=[],
            expectation=does_not_raise(),
        ),
        RaiseBranchesCase(
            name="single_failure",
            failed_imports=[
                FailedImport(branch_name="branch01", step=ImportStep.COLLECTION, reason="schema validation failed"),
            ],
            expectation=pytest.raises(
                RepositoryError,
                match=rf"^{
                    re.escape(
                        'Unable to synchronize the following branches of repository test-repo:'
                        ' branch01 (step=collection): schema validation failed'
                    )
                }$",
            ),
        ),
        RaiseBranchesCase(
            name="multiple_failures",
            failed_imports=[
                FailedImport(branch_name="branch01", step=ImportStep.COLLECTION, reason="error 1"),
                FailedImport(branch_name="branch02", step=ImportStep.IMPORT, reason="error 2"),
            ],
            expectation=pytest.raises(
                RepositoryError,
                match=rf"^{
                    re.escape(
                        'Unable to synchronize the following branches of repository test-repo:'
                        ' branch01 (step=collection): error 1; branch02 (step=import): error 2'
                    )
                }$",
            ),
        ),
    ],
    ids=lambda c: c.name,
)
def test_raise_if_branches_failed(stub_repo: InfrahubRepository, case: RaiseBranchesCase) -> None:
    with case.expectation:
        stub_repo.raise_if_branches_failed(case.failed_imports)


def test_raise_if_branches_failed_logs_structured_fields(
    stub_repo: InfrahubRepository, caplog: pytest.LogCaptureFixture
) -> None:
    failed = FailedImport(branch_name="branch01", step=ImportStep.COLLECTION, reason="schema validation failed")
    with caplog.at_level(logging.WARNING, logger="infrahub.tasks"), pytest.raises(RepositoryError):
        stub_repo.raise_if_branches_failed([failed])
    assert len(caplog.records) == 1
    attrs = vars(caplog.records[0])
    assert attrs["branch"] == "branch01"
    assert attrs["step"] == "collection"
    assert attrs["reason"] == "schema validation failed"
    assert attrs["repository"] == "test-repo"


def test_raise_if_branches_failed_does_not_log_a_failed_import_or_record_again(
    stub_repo: InfrahubRepository, caplog: pytest.LogCaptureFixture
) -> None:
    failed_imports = [
        FailedImport(branch_name="branch01", step=ImportStep.COLLECTION, reason="error 1"),
        FailedImport(branch_name="branch02", step=ImportStep.IMPORT, reason="error 2"),
        FailedImport(branch_name="branch03", step=ImportStep.RECORD, reason="error 3"),
    ]
    with (
        caplog.at_level(logging.WARNING, logger="infrahub.tasks"),
        pytest.raises(
            RepositoryError,
            match=r"^Unable to synchronize the following branches of repository test-repo: "
            r"branch01 \(step=collection\): error 1; branch02 \(step=import\): error 2; "
            r"branch03 \(step=record\): error 3$",
        ),
    ):
        stub_repo.raise_if_branches_failed(failed_imports)
    assert [record.getMessage() for record in caplog.records] == [
        "Failed to synchronize branch branch01 of repository test-repo at step collection: error 1"
    ]


TRUNK = "develop"


class BranchListingClient(InfrahubClient):
    """An SDK client that answers every GraphQL call with an empty list of Infrahub branches."""

    def __init__(self) -> None:
        super().__init__(config=Config(requester=dummy_async_request))

    async def execute_graphql(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"Branch": []}


async def clone_trunk_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, remote: LocalRemote
) -> InfrahubRepository:
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))
    monkeypatch.setattr(config.SETTINGS.git, "import_sync_branch_names", [])
    return await clone_repository(
        id=UUIDT.new(),
        name="trunk-repo",
        location=str(remote.directory),
        default_branch=TRUNK,
        client=BranchListingClient(),
        update_commit_value=False,
    )


@dataclass
class ValidateRemoteBranchCase:
    name: str
    branch_name: str
    expected: bool


VALIDATE_REMOTE_BRANCH_CASES = [
    ValidateRemoteBranchCase(name="name_of_the_infrahub_default_branch", branch_name="main", expected=False),
    ValidateRemoteBranchCase(name="name_infrahub_cannot_store", branch_name="ab", expected=False),
    ValidateRemoteBranchCase(name="ordinary_branch", branch_name="feature-1", expected=True),
]


@pytest.mark.parametrize("case", VALIDATE_REMOTE_BRANCH_CASES, ids=[case.name for case in VALIDATE_REMOTE_BRANCH_CASES])
async def test_validate_remote_branch_decides_whether_a_branch_is_imported(
    case: ValidateRemoteBranchCase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_prefect_logger: None
) -> None:
    remote = LocalRemote.create(directory=tmp_path / "source-repo", trunk=TRUNK, branches=["main", "ab", "feature-1"])
    repository = await clone_trunk_repository(tmp_path, monkeypatch, remote)

    assert repository.validate_remote_branch(branch_name=case.branch_name) is case.expected


async def test_collect_pending_imports_records_a_new_colliding_branch_as_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_prefect_logger: None
) -> None:
    """A colliding branch with no local counterpart is new on every run, and is skipped as such."""
    remote = LocalRemote.create(directory=tmp_path / "source-repo", trunk=TRUNK, branches=["main", "ab"])
    repository = await clone_trunk_repository(tmp_path, monkeypatch, remote)

    collected = await repository.collect_pending_imports()

    assert collected.skipped_branches == ["main"]
    assert collected.imports == []
    assert collected.failed_imports == []


async def test_collect_pending_imports_records_an_updated_colliding_branch_as_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_prefect_logger: None
) -> None:
    """A colliding branch that exists locally is reported as updated when it moves, and is skipped too."""
    remote = LocalRemote.create(directory=tmp_path / "source-repo", trunk=TRUNK, branches=["main"])
    repository = await clone_trunk_repository(tmp_path, monkeypatch, remote)
    repository.get_git_repo_main().create_head("main", "origin/main")
    remote.commit(branch_name="main", files={"data.txt": "main v2\n"})

    new_branches, updated_branches = await repository.compare_local_remote()
    assert (new_branches, updated_branches) == ([], [])

    collected = await repository.collect_pending_imports()

    assert collected.skipped_branches == ["main"]
    assert collected.imports == []


async def test_collect_pending_imports_records_the_colliding_remote_head_as_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_prefect_logger: None
) -> None:
    """A clone holds the remote's HEAD as a local branch, so an unchanged colliding HEAD is neither new nor updated."""
    remote = LocalRemote.create(directory=tmp_path / "source-repo", trunk=TRUNK, branches=["main"], head="main")
    repository = await clone_trunk_repository(tmp_path, monkeypatch, remote)

    new_branches, updated_branches = await repository.compare_local_remote()
    assert (new_branches, updated_branches) == ([], [])

    collected = await repository.collect_pending_imports()

    assert collected.skipped_branches == ["main"]
    assert collected.advanced_skipped_branches == []
    assert collected.imports == []
    assert collected.failed_imports == []


@dataclass
class AdvanceCase:
    name: str
    colliding_branch_on_first_fetch: bool
    push_to_colliding_branch: bool
    expected_advanced: list[str]


ADVANCE_CASES = [
    AdvanceCase(
        name="unchanged_colliding_branch",
        colliding_branch_on_first_fetch=True,
        push_to_colliding_branch=False,
        expected_advanced=[],
    ),
    AdvanceCase(
        name="colliding_branch_received_a_commit",
        colliding_branch_on_first_fetch=True,
        push_to_colliding_branch=True,
        expected_advanced=["main"],
    ),
    AdvanceCase(
        name="colliding_branch_pushed_after_the_clone",
        colliding_branch_on_first_fetch=False,
        push_to_colliding_branch=False,
        expected_advanced=["main"],
    ),
]


@pytest.mark.parametrize("case", ADVANCE_CASES, ids=[case.name for case in ADVANCE_CASES])
async def test_collect_pending_imports_detects_a_skipped_branch_that_advanced(
    case: AdvanceCase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_prefect_logger: None
) -> None:
    """A skipped branch counts as advanced when its head moved, or when it appeared, since the last fetch.

    A clone already holds every branch the remote had, so an unchanged branch is never counted.
    """
    remote = LocalRemote.create(
        directory=tmp_path / "source-repo",
        trunk=TRUNK,
        branches=["main"] if case.colliding_branch_on_first_fetch else [],
    )
    repository = await clone_trunk_repository(tmp_path, monkeypatch, remote)

    if not case.colliding_branch_on_first_fetch:
        remote.create_branch("main")
    if case.push_to_colliding_branch:
        remote.commit(branch_name="main", files={"data.txt": "main v2\n"})

    collected = await repository.collect_pending_imports()

    assert collected.skipped_branches == ["main"]
    assert collected.advanced_skipped_branches == case.expected_advanced


async def test_collect_pending_imports_reports_an_advance_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_prefect_logger: None
) -> None:
    """A later run on the same clone with nothing further pushed does not count the branch as advanced again."""
    remote = LocalRemote.create(directory=tmp_path / "source-repo", trunk=TRUNK, branches=["main"])
    repository = await clone_trunk_repository(tmp_path, monkeypatch, remote)
    remote.commit(branch_name="main", files={"data.txt": "main v2\n"})

    first = await repository.collect_pending_imports()
    second = await repository.collect_pending_imports()

    assert first.advanced_skipped_branches == ["main"]
    assert second.skipped_branches == ["main"]
    assert second.advanced_skipped_branches == []
